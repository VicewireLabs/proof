import copy
import json
from pathlib import Path
import unittest

from verify import GENESIS, verify

EVIDENCE = Path(__file__).parent / "evidence"


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((EVIDENCE/"devnet-rehearsal.json").read_text())
        cls.receipt = json.loads((EVIDENCE/"finalized-transaction.json").read_text())

    def test_recorded_receipt(self):
        verify(self.summary, self.receipt, GENESIS)

    def test_wrong_cluster_is_rejected(self):
        with self.assertRaises(ValueError):
            verify(self.summary, self.receipt, "other-network")

    def test_changed_transfer_and_fee_are_rejected(self):
        for field in ("amount", "fee", "destination", "balance", "signature"):
            with self.subTest(field=field):
                tx = copy.deepcopy(self.receipt)
                info = tx["transaction"]["message"]["instructions"][0]["parsed"]["info"]
                if field == "amount": info["lamports"] += 1
                if field == "fee": tx["meta"]["fee"] += 1
                if field == "destination": info["destination"] = info["source"]
                if field == "balance": tx["meta"]["postBalances"][0] += 1
                if field == "signature": tx["transaction"]["signatures"] = []
                with self.assertRaises(ValueError):
                    verify(self.summary, tx, GENESIS)
