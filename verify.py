"""Independently verify the Vicewire rehearsal using only Solana's public, read-only RPC."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEVNET = "https://api.devnet.solana.com"
GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
SYSTEM_PROGRAM = "11111111111111111111111111111111"


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = Request(DEVNET, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as response:
        result = json.load(response)
    if result.get("error") or result.get("result") is None:
        raise ValueError(f"{method} did not return the required record.")
    return result["result"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(summary, tx, genesis):
    require(genesis == GENESIS == summary["genesis"], "Wrong cluster.")
    meta = tx["meta"]
    require(meta["err"] is None, "Failed transaction.")
    require(tx["slot"] == summary["finalized_slot"], "Slot mismatch.")
    require(tx["transaction"]["signatures"] == [summary["signature"]], "Signature mismatch.")
    message = tx["transaction"]["message"]
    instructions = message["instructions"]
    require(len(instructions) == 1 and instructions[0]["programId"] == SYSTEM_PROGRAM,
            "Expected one native SOL transfer.")
    instruction = instructions[0]["parsed"]
    require(instruction["type"] == "transfer", "Unexpected operation.")
    payer, recipient = summary["treasury"], summary["recipient"]
    require(instruction["info"] == {"source": payer, "destination": recipient, "lamports": 2_000_000},
            "Transfer details differ.")
    keys = message["accountKeys"]
    require(keys[0]["pubkey"] == payer and keys[0]["signer"] and payer != recipient, "Unexpected fee payer.")
    deltas = {k["pubkey"]: after-before for k,before,after in
              zip(keys, meta["preBalances"], meta["postBalances"], strict=True)}
    require(deltas[recipient] == summary["player_lamports"] == 2_000_000, "Recipient delta differs.")
    require(meta["fee"] == summary["network_fee_lamports"] == 5_000, "Fee differs.")
    require(deltas[payer] == summary["treasury_lamports"] == -2_005_000, "Treasury delta differs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Read the finalized receipt from public devnet.")
    options = parser.parse_args()
    summary = json.loads((ROOT/"evidence/devnet-rehearsal.json").read_text(encoding="utf-8"))
    if options.live:
        genesis = rpc("getGenesisHash", [])
        receipt = rpc("getTransaction", [summary["signature"], {"encoding": "jsonParsed", "commitment": "finalized",
                                                                  "maxSupportedTransactionVersion": 0}])
    else:
        genesis = summary["genesis"]
        receipt = json.loads((ROOT/"evidence/finalized-transaction.json").read_text(encoding="utf-8"))
    verify(summary, receipt, genesis)
    source = "Public devnet RPC" if options.live else "Bundled receipt"
    print(f"{source}: 0.002 SOL to the test player, 0.000005 SOL fee, slot {receipt['slot']}.")


if __name__ == "__main__":
    main()
