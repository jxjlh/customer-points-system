import unittest

from modules.database_config import postgres_dsn_from_secrets


class PostgresConfigTests(unittest.TestCase):
    def test_uses_database_url_for_supabase_pooler(self):
        url = (
            "postgresql://postgres.project:secret@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
        )

        self.assertEqual(
            postgres_dsn_from_secrets({"database_url": url}),
            url,
        )

    def test_uses_postgres_section_url_before_split_fields(self):
        url = "postgresql://postgres:secret@db.example.com:6543/postgres?sslmode=require"
        secrets = {
            "postgres": {
                "url": url,
                "host": "ignored.example.com",
                "port": 5432,
                "dbname": "ignored",
                "user": "ignored",
                "password": "ignored",
            }
        }

        self.assertEqual(postgres_dsn_from_secrets(secrets), url)

    def test_builds_escaped_dsn_from_split_fields(self):
        dsn = postgres_dsn_from_secrets(
            {
                "postgres": {
                    "host": "db.example.com",
                    "port": 6543,
                    "dbname": "postgres",
                    "user": "postgres.user",
                    "password": "pa ss'word",
                    "sslmode": "require",
                    "connect_timeout": 15,
                }
            }
        )

        self.assertIn("host='db.example.com'", dsn)
        self.assertIn("port='6543'", dsn)
        self.assertIn("password='pa ss\\'word'", dsn)
        self.assertIn("sslmode='require'", dsn)
        self.assertIn("connect_timeout='15'", dsn)


if __name__ == "__main__":
    unittest.main()

