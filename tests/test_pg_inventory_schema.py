import unittest
from contextlib import contextmanager
import sys
import types

sys.modules.setdefault("pandas", types.SimpleNamespace(DataFrame=object))
from modules.pg_database import PgDatabaseManager


class _Cursor:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class PgInventorySchemaTests(unittest.TestCase):
    def test_inventory_schema_creates_all_inventory_tables(self):
        manager = object.__new__(PgDatabaseManager)
        connection = _Connection()

        @contextmanager
        def connection_context():
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        manager._conn = connection_context
        manager.ensure_inventory_schema()

        statements = "\n".join(connection.cursor_instance.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_items", statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_transactions", statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_fields", statements)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS inventory_hidden_history_values", statements
        )
        self.assertIn(
            "DROP CONSTRAINT IF EXISTS inventory_items_item_code_key", statements
        )
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
