import tempfile
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path

from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import Transaction

from rehearse_local import REWARD, prepare_fixture


class MissionRehearsalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "reward.db"
        self.sender, self.player = Keypair(), Keypair().pubkey()
        self.block = {"blockhash": str(Hash.new_unique()), "lastValidBlockHeight": 109}
        self.fee, self.rent = 5_000, 890_880
        self.budget = REWARD + self.fee + self.rent

    def prepare(self, *, recipient=None, budget=None):
        return prepare_fixture(self.db, "fixture-chain", self.sender, recipient or self.player, self.block,
                               self.budget if budget is None else budget, self.fee, self.rent)

    def test_underfunded_does_not_consume_claim(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.prepare(budget=self.budget-1)
        Transaction.from_bytes(self.prepare()).verify()

    def test_reloaded_save_reuses_wire_with_new_blockhash_and_depleted_budget(self):
        initial = self.prepare()
        self.block["blockhash"] = str(Hash.new_unique())
        self.assertEqual(self.prepare(budget=0), initial)

    def test_wallet_change_cannot_move_an_existing_claim(self):
        initial = self.prepare()
        with self.assertRaisesRegex(ValueError, "binding changed"):
            self.prepare(recipient=Keypair().pubkey())
        self.assertEqual(self.prepare(), initial)

    def test_changed_treasury_cannot_replace_claim(self):
        initial = self.prepare()
        with self.assertRaisesRegex(ValueError, "binding changed"):
            prepare_fixture(self.db, "fixture-chain", Keypair(), self.player, self.block,
                            self.budget, self.fee, self.rent)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT wire FROM reward").fetchall(), [(initial,)])
