import copy
import json
from pathlib import Path
import unittest

from verify_mainnet import GENESIS, verify

ROOT = Path(__file__).parent


class MainnetLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((ROOT/"evidence/mainnet-launches.json").read_text())
        cls.launches = [(launch, json.loads((ROOT/launch["transaction_file"]).read_text()))
                        for launch in cls.summary["launches"]]

    def test_recorded_launches(self):
        self.assertEqual(len(self.launches), 2)
        for launch, tx in self.launches:
            verify(self.summary, launch, tx, GENESIS)

    def test_devnet_is_rejected(self):
        launch, tx = self.launches[0]
        with self.assertRaises(ValueError):
            verify(self.summary, launch, tx, "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG")

    def test_changed_records_are_rejected(self):
        launch, original = self.launches[0]
        for field in ("payer", "fee", "balance", "signature", "program", "failed", "other_coin"):
            with self.subTest(field=field):
                tx, claim = copy.deepcopy(original), dict(launch)
                message = tx["transaction"]["message"]
                if field == "payer": message["accountKeys"][0]["pubkey"] = launch["mint"]
                if field == "fee": tx["meta"]["fee"] += 1
                if field == "balance": tx["meta"]["postBalances"][0] += 1
                if field == "signature": tx["transaction"]["signatures"][0] = "other"
                if field == "program": message["instructions"][-1]["programId"] = "11111111111111111111111111111111"
                if field == "failed": tx["meta"]["err"] = {"InstructionError": [2, "Custom"]}
                if field == "other_coin": claim["mint"] = self.launches[1][0]["mint"]
                with self.assertRaises(ValueError):
                    verify(self.summary, claim, tx, GENESIS)
