"""Independently verify the Vicewire mainnet coin launches using only Solana's public, read-only RPC."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MAINNET = "https://api.mainnet-beta.solana.com"
GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
COMPUTE_BUDGET = "ComputeBudget111111111111111111111111111111"


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = Request(MAINNET, data=body, headers={"Content-Type": "application/json", "User-Agent": "vicewire-proof"})
    with urlopen(req, timeout=30) as response:
        result = json.load(response)
    if result.get("error") or result.get("result") is None:
        raise ValueError(f"{method} did not return the required record.")
    return result["result"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(summary, launch, tx, genesis):
    """Check one launch: real network, the game wallet paid, and the only program work is one Pump.fun create."""
    require(genesis == GENESIS == summary["genesis"], "Wrong cluster.")
    meta = tx["meta"]
    require(meta["err"] is None, "Failed transaction.")
    require(tx["slot"] == launch["finalized_slot"], "Slot mismatch.")
    require(tx["transaction"]["signatures"][0] == launch["signature"], "Signature mismatch.")
    message = tx["transaction"]["message"]
    keys = message["accountKeys"]
    wallet, mint = summary["game_wallet"], launch["mint"]
    require(keys[0]["pubkey"] == wallet and keys[0]["signer"], "The game wallet is not the fee payer.")
    signers = sorted(k["pubkey"] for k in keys if k["signer"])
    require(signers == sorted([wallet, mint]), "Unexpected signers.")
    programs = [i["programId"] for i in message["instructions"]]
    require(programs.count(PUMP_PROGRAM) == 1 and set(programs) == {PUMP_PROGRAM, COMPUTE_BUDGET},
            "Expected one Pump.fun instruction and nothing else.")
    require(any(line == "Program log: Instruction: CreateV2" for line in meta["logMessages"]),
            "The Pump.fun instruction is not a coin creation.")
    require(any(b["mint"] == mint for b in meta["postTokenBalances"]), "The new coin has no token balance.")
    require(meta["fee"] == launch["network_fee_lamports"], "Fee differs.")
    require(meta["postBalances"][0] - meta["preBalances"][0] == -launch["wallet_paid_lamports"],
            "The wallet's balance change differs.")
    require(meta["preBalances"][0] == launch["wallet_before_lamports"], "The wallet's starting balance differs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Read the finalized transactions from public mainnet.")
    options = parser.parse_args()
    summary = json.loads((ROOT/"evidence/mainnet-launches.json").read_text(encoding="utf-8"))
    genesis = rpc("getGenesisHash", []) if options.live else summary["genesis"]
    source = "Public mainnet RPC" if options.live else "Bundled transaction"
    for launch in summary["launches"]:
        if options.live:
            tx = rpc("getTransaction", [launch["signature"], {"encoding": "jsonParsed", "commitment": "finalized",
                                                              "maxSupportedTransactionVersion": 0}])
        else:
            tx = json.loads((ROOT/launch["transaction_file"]).read_text(encoding="utf-8"))
        verify(summary, launch, tx, genesis)
        print(f"{source}: coin {launch['mint']} created on Pump.fun, "
              f"{launch['wallet_paid_lamports'] / 1e9:.6f} SOL paid by the game wallet, slot {tx['slot']}.")


if __name__ == "__main__":
    main()
