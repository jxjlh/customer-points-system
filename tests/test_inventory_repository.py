import sqlite3
import tempfile
import unittest
from pathlib import Path

from modules.db_manager import _SQLiteManager
from modules.inventory.errors import InsufficientStockError


class InventoryRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "inventory.db")
        self.manager = _SQLiteManager(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_existing_schema_is_extended_idempotently(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT,
                location TEXT,
                quantity INTEGER DEFAULT 0,
                extra_fields TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE TABLE inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                remark TEXT,
                operator TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.commit()
        conn.close()

        self.manager._inv_ensure_tables()
        self.manager._inv_ensure_tables()
        item_id = self.manager.add_inventory_item(
            {
                "item_code": "M-001",
                "title": "模型",
                "category": "小鼠",
                "location": "A1",
                "quantity": 0,
            }
        )

        item = self.manager.get_inventory_item(item_id)
        self.assertEqual(item["is_active"], 1)

    def test_existing_unique_item_code_constraint_is_removed(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT,
                location TEXT,
                quantity INTEGER DEFAULT 0,
                extra_fields TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE TABLE inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                remark TEXT,
                operator TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.commit()
        conn.close()

        self.manager.add_inventory_item({"item_code": "M-001", "title": "模型A"})
        self.manager.add_inventory_item({"item_code": "M-001", "title": "模型B"})

        self.assertEqual(len(self.manager.list_inventory_items()), 2)

    def test_saved_values_are_returned_as_history(self):
        self.manager.add_inventory_item(
            {
                "item_code": "M-002",
                "title": " 模型B ",
                "category": "实验鼠",
                "location": "B2",
                "quantity": 0,
            }
        )
        self.assertEqual(self.manager.get_inventory_history_values("title"), ["模型B"])
        self.assertEqual(self.manager.get_inventory_history_values("category"), ["实验鼠"])
        self.assertEqual(self.manager.get_inventory_history_values("location"), ["B2"])

    def test_history_value_can_be_hidden_without_changing_inventory_item(self):
        item_id = self.manager.add_inventory_item(
            {
                "item_code": "M-002-H",
                "title": "模型历史值",
                "category": "实验鼠",
                "location": "B2",
                "quantity": 0,
            }
        )

        self.assertTrue(self.manager.delete_inventory_history_value("location", "B2"))
        self.assertEqual(self.manager.get_inventory_history_values("location"), [])
        self.assertEqual(self.manager.get_inventory_item(item_id)["location"], "B2")

        self.manager.add_inventory_item(
            {
                "item_code": "M-002-H2",
                "title": "模型历史值2",
                "category": "实验鼠",
                "location": "B2",
                "quantity": 0,
            }
        )
        self.assertEqual(self.manager.get_inventory_history_values("location"), ["B2"])

    def test_inventory_transaction_is_atomic_and_records_stock_snapshots(self):
        item_id = self.manager.add_inventory_item(
            {
                "item_code": "M-003",
                "title": "模型C",
                "category": "",
                "location": "C3",
                "quantity": 5,
            }
        )

        self.manager.inventory_transaction_atomic(item_id, "out", 2, "领用", "tester")

        item = self.manager.get_inventory_item(item_id)
        record = self.manager.list_inventory_transactions(item_id=item_id, limit=1)[0]
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(record["stock_before"], 5)
        self.assertEqual(record["stock_after"], 3)

    def test_insufficient_stock_changes_neither_item_nor_history(self):
        item_id = self.manager.add_inventory_item(
            {
                "item_code": "M-004",
                "title": "模型D",
                "category": "",
                "location": "D4",
                "quantity": 1,
            }
        )

        with self.assertRaises(InsufficientStockError):
            self.manager.inventory_transaction_atomic(item_id, "out", 2, "", "tester")

        self.assertEqual(self.manager.get_inventory_item(item_id)["quantity"], 1)
        self.assertEqual(self.manager.count_inventory_transactions(item_id), 0)

    def test_manual_code_checks_and_archive_operations(self):
        item_id = self.manager.add_inventory_item(
            {
                "item_code": "M-005",
                "title": "模型E",
                "category": "",
                "location": "E5",
                "quantity": 0,
            }
        )
        self.assertTrue(self.manager.inventory_code_exists("M-005"))
        self.assertFalse(self.manager.inventory_code_exists("M-005", exclude_item_id=item_id))

        self.manager.set_inventory_item_active(item_id, False)
        self.assertEqual(self.manager.get_inventory_item(item_id)["is_active"], 0)
        self.manager.set_inventory_item_active(item_id, True)
        self.assertEqual(self.manager.get_inventory_item(item_id)["is_active"], 1)


if __name__ == "__main__":
    unittest.main()
