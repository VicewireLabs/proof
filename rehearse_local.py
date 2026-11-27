"""Reproduce the simulated mission payout on an isolated local Solana validator."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from solders.hash import Hash
from solders.keypair import Keypair
from solders.message import Message
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

PUBLIC_NETWORKS = {
    "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG",
    "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d",
    "4uhcVJyU9pJkvQyS88uRDiswHXSCkY3zQawwpjk2NsNY",
}
PLAYER = "fixture-player"
MISSION = "vicewire-test-delivery"
REWARD = 2_000_000
FAUCET_AMOUNT = 4_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


class TestNetwork:
    def __init__(self, port):
        require(1 <= port <= 65535, "Invalid loopback port.")
        self.url = f"http://127.0.0.1:{port}"
        self.genesis = self.rpc("getGenesisHash", [])
        require(isinstance(self.genesis, str) and self.genesis not in PUBLIC_NETWORKS,
                "This reproduction requires an isolated local validator.")

    def rpc(self, method, params):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"{method} returned HTTP {exc.code}.") from None
        if "error" in result:
            raise RuntimeError(f"{method} returned RPC error {result['error'].get('code')}: "
                               f"{str(result['error'].get('message', ''))[:180]}")
        return result["result"]

    def wait_final(self, signature):
        for _ in range(90):
            status = self.rpc("getSignatureStatuses", [[signature], {"searchTransactionHistory": True}])["value"][0]
            if status and status["confirmationStatus"] == "finalized":
                require(status["err"] is None, "Transaction finalized with an error.")
                return
            time.sleep(.65)
        raise TimeoutError("No finalized signature was observed.")


def prepare_fixture(db_path, genesis, treasury, recipient, block, balance, fee, rent):
    with closing(sqlite3.connect(db_path, timeout=8)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS reward (
            network TEXT, player TEXT, mission TEXT, recipient TEXT NOT NULL, treasury TEXT NOT NULL,
            signature TEXT NOT NULL UNIQUE, wire BLOB NOT NULL, valid_height INTEGER NOT NULL,
            PRIMARY KEY(network, player, mission))""")
        key = (genesis, PLAYER, MISSION)
        found = db.execute("""SELECT recipient, treasury, wire FROM reward
            WHERE network=? AND player=? AND mission=?""", key).fetchone()
        if found:
            require(found[:2] == (str(recipient), str(treasury.pubkey())), "Fixture wallet binding changed.")
            return found[2]
        require(type(fee) is int and fee > 0 and rent > 0, "Missing network fee or rent floor.")
        require(REWARD >= rent and balance >= REWARD + fee + rent, "Insufficient reward budget.")
        ix = transfer(TransferParams(from_pubkey=treasury.pubkey(), to_pubkey=recipient, lamports=REWARD))
        tx = Transaction.new_signed_with_payer([ix], treasury.pubkey(), [treasury], Hash.from_string(block["blockhash"]))
        wire = bytes(tx)
        db.execute("INSERT INTO reward VALUES(?,?,?,?,?,?,?,?)", (*key, str(recipient),
                   str(treasury.pubkey()), str(tx.signatures[0]), wire, block["lastValidBlockHeight"]))
        return wire


def recover_fixture(db_path, network):
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("""SELECT signature, wire, treasury, recipient FROM reward
            WHERE network=? AND player=? AND mission=?""", (network.genesis, PLAYER, MISSION)).fetchall()
    require(len(rows) == 1, "Expected one recorded reward.")
    signature, wire, treasury, player = rows[0]
    tx = Transaction.from_bytes(wire)
    tx.verify()
    require(signature == str(tx.signatures[0]), "Signature differs from recorded transaction.")
    network.wait_final(signature)
    receipt = network.rpc("getTransaction", [signature, {"encoding": "base64", "commitment": "finalized"}])
    require(receipt and receipt["meta"]["err"] is None, "Missing successful finalized receipt.")
    require(base64.b64decode(receipt["transaction"][0], validate=True) == wire, "Finalized bytes differ.")
    meta = receipt["meta"]
    keys = list(map(str, tx.message.account_keys))
    deltas = dict(zip(keys, (b-a for a,b in zip(meta["preBalances"], meta["postBalances"], strict=True)), strict=True))
    require(deltas[player] == REWARD and deltas[treasury] == -REWARD-meta["fee"], "Balance deltas differ.")
    return {"signature": signature, "finalized_slot": receipt["slot"], "player_lamports": deltas[player],
            "treasury_lamports": deltas[treasury], "network_fee_lamports": meta["fee"]}


@contextmanager
def fixture_journal():
    temp = TemporaryDirectory(prefix="vicewire-test-", delete=False)
    path = Path(temp.name) / "mission.db"
    try:
        yield path
    except BaseException:
        print(f"Fixture journal retained at {path}", file=sys.stderr)
        raise
    else:
        temp.cleanup()


def rehearse(port):
    network = TestNetwork(port)
    treasury, player = Keypair(), Keypair()
    sender, recipient = map(str, (treasury.pubkey(), player.pubkey()))
    config = {"commitment": "finalized"}
    require(network.rpc("getBalance", [sender, config])["value"] == 0, "Expected an unfunded test treasury.")
    funding = network.rpc("requestAirdrop", [sender, FAUCET_AMOUNT])
    network.wait_final(funding)
    balance = network.rpc("getBalance", [sender, config])["value"]
    require(balance == FAUCET_AMOUNT, "Treasury funding differs from the requested test airdrop.")
    require(network.rpc("getBalance", [recipient, config])["value"] == 0, "Expected new fixture recipient.")
    rent = network.rpc("getMinimumBalanceForRentExemption", [0, config])
    blocks = []
    for _ in range(45):
        block = network.rpc("getLatestBlockhash", [config])["value"]
        if not blocks or blocks[-1]["blockhash"] != block["blockhash"]:
            blocks.append(block)
        if len(blocks) == 4:
            break
        time.sleep(.4)
    require(len({b["blockhash"] for b in blocks}) == 4, "Expected four distinct valid blockhashes.")
    ix = transfer(TransferParams(from_pubkey=treasury.pubkey(), to_pubkey=player.pubkey(), lamports=REWARD))
    msg = Message.new_with_blockhash([ix], treasury.pubkey(), Hash.from_string(block["blockhash"]))
    fee = network.rpc("getFeeForMessage", [base64.b64encode(bytes(msg)).decode(), config])["value"]
    with fixture_journal() as db_path:
        def prepare(candidate):
            return prepare_fixture(db_path, network.genesis, treasury, player.pubkey(), candidate, balance, fee, rent)
        with ThreadPoolExecutor(max_workers=4) as pool:
            wires = list(pool.map(prepare, blocks))
        require(len(set(wires)) == 1, "Concurrent completions generated multiple transfers.")
        with closing(sqlite3.connect(db_path)) as db:
            count = db.execute("SELECT COUNT(*) FROM reward").fetchone()[0]
        require(count == 1, "Duplicate reward journal entries.")
        encoded = base64.b64encode(wires[0]).decode()
        sim = network.rpc("simulateTransaction", [encoded, {"encoding": "base64", "sigVerify": True,
                                                             "commitment": "confirmed"}])
        require(sim["value"]["err"] is None, "Payout preflight failed.")
        # Deliberately discard the acknowledgement. Restart recovery uses only the committed journal.
        network.rpc("sendTransaction", [encoded, {"encoding": "base64", "preflightCommitment": "confirmed"}])
        proc = subprocess.run([sys.executable, "-B", __file__, "--port", str(port), "--recover", str(db_path)],
                              capture_output=True, text=True, timeout=110)
        require(proc.returncode == 0, f"Read-only recovery failed: {proc.stderr[-1200:]}")
        proof = json.loads(proc.stdout)
        replay = prepare(blocks[-1])
        require(replay == wires[0], "Reload replaced the signed transfer.")
        # A duplicate completion after restart is reconciled read-only.
        require(recover_fixture(db_path, network) == proof, "Replay changed the finalized receipt.")
        require(network.rpc("getBalance", [recipient, config])["value"] == REWARD, "Unexpected final player balance.")
        require(network.rpc("getBalance", [sender, config])["value"] == balance-REWARD-proof["network_fee_lamports"],
                "Unexpected final treasury balance.")
        history = network.rpc("getSignaturesForAddress", [recipient, {"commitment":"finalized", "limit":2}])
        require([entry["signature"] for entry in history] == [proof["signature"]], "Unexpected player transfer history.")
        return {"network": "local validator", "genesis": network.genesis, "completion_source": "simulated delivery",
                "funding_source": "test faucet", "concurrent_completions": len(wires), "wire_transactions": count,
                "recipient_history_count": len(history), "distinct_candidate_blockhashes": len(blocks),
                "restart_reconciled": True, "reload_reconciled": True, "recipient": recipient,
                "treasury": sender, **proof}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8899, help="RPC port of the local test validator.")
    parser.add_argument("--recover", type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.recover:
        result = recover_fixture(options.recover, TestNetwork(options.port))
    else:
        result = rehearse(options.port)
    print(json.dumps(result, indent=2))
