import unittest

from modules.db_manager import _detect_db_type


class DatabaseSelectionTests(unittest.TestCase):
    def test_valid_postgres_is_used_when_mysql_section_contains_example_values(self):
        secrets = {
            "mysql": {
                "host": "your-mysql-host.com",
                "user": "root",
                "password": "your-password-here",
                "database": "customer_points",
            },
            "postgres": {
                "host": "db.example.supabase.co",
                "port": 5432,
                "dbname": "postgres",
                "user": "postgres",
                "password": "actual-password",
            },
        }

        self.assertEqual(_detect_db_type(secrets), "postgres")

    def test_valid_mysql_configuration_is_selected(self):
        secrets = {
            "mysql": {
                "host": "db.example.com",
                "port": 3306,
                "user": "inventory_user",
                "password": "actual-password",
                "database": "inventory",
            }
        }

        self.assertEqual(_detect_db_type(secrets), "mysql")


if __name__ == "__main__":
    unittest.main()

