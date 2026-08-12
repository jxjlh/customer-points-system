"""Remote database configuration helpers shared by PostgreSQL managers."""
from __future__ import annotations

from typing import Any


def _value(section: Any, name: str, default: Any = "") -> Any:
    if section is None:
        return default
    try:
        return section.get(name, default)
    except AttributeError:
        try:
            return section[name]
        except Exception:
            return default


def _section(secrets: Any, name: str) -> Any:
    try:
        return secrets[name] if name in secrets else None
    except Exception:
        return None


def _conninfo_value(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace("'", "\\'")


def postgres_dsn_from_secrets(secrets: Any) -> str:
    """Return a psycopg-compatible DSN from a URL or split Streamlit Secrets."""
    for key in ("database_url", "DATABASE_URL", "postgres_url", "POSTGRES_URL"):
        url = str(_value(secrets, key, "") or "").strip()
        if url:
            return url

    postgres = _section(secrets, "postgres")
    for key in ("url", "database_url", "DATABASE_URL"):
        url = str(_value(postgres, key, "") or "").strip()
        if url:
            return url

    required = {
        "host": _value(postgres, "host"),
        "port": _value(postgres, "port", 6543),
        "dbname": _value(postgres, "dbname", "postgres"),
        "user": _value(postgres, "user"),
        "password": _value(postgres, "password"),
        "sslmode": _value(postgres, "sslmode", "require"),
        "connect_timeout": _value(postgres, "connect_timeout", 15),
    }
    missing = [name for name in ("host", "user", "password") if not str(required[name] or "").strip()]
    if missing:
        raise ValueError(f"PostgreSQL 配置缺少：{', '.join(missing)}")

    return " ".join(
        f"{name}='{_conninfo_value(value)}'"
        for name, value in required.items()
    )


def redact_database_error(error: Exception | str) -> str:
    """Keep connection diagnostics useful without disclosing a password or URL query."""
    text = str(error or "数据库连接失败")
    for marker in ("password=", "password:"):
        if marker not in text:
            continue
        prefix, suffix = text.split(marker, 1)
        delimiter = " " if marker == "password=" else "@"
        rest = suffix.split(delimiter, 1)
        text = prefix + marker + "***" + (delimiter + rest[1] if len(rest) > 1 else "")
    return text[:500]
