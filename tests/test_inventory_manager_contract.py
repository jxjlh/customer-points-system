import unittest

from modules.db_manager import _BaseManager, _MySQLManager, _PostgresManager, _SQLiteManager
from modules.pg_database import PgDatabaseManager


REQUIRED_METHODS = {
    "get_inventory_item",
    "inventory_code_exists",
    "get_inventory_history_values",
    "count_inventory_transactions",
    "set_inventory_item_active",
    "delete_inventory_item_without_history",
    "inventory_transaction_atomic",
}


class InventoryManagerContractTests(unittest.TestCase):
    def test_all_inventory_managers_define_required_methods(self):
        for manager_class in (
            _BaseManager,
            _MySQLManager,
            _PostgresManager,
            _SQLiteManager,
            PgDatabaseManager,
        ):
            with self.subTest(manager=manager_class.__name__):
                missing = [
                    method_name
                    for method_name in REQUIRED_METHODS
                    if not callable(getattr(manager_class, method_name, None))
                ]
                self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
