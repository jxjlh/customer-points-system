"""
PostgreSQL 数据库访问层

提供报价单、价格库、发票数据的持久化存储。
使用 psycopg2 连接池，通过 st.secrets 读取连接配置。

使用方式：
    from modules.pg_database import get_pg_manager
    db = get_pg_manager()
    db.init_schema()
    db.save_quotation(quotation_data)
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from typing import Dict, List, Optional

from modules.database_config import postgres_dsn_from_secrets

import pandas as pd

from modules.inventory.errors import (
    InsufficientStockError,
    ItemArchivedError,
    ItemNotFoundError,
    ValidationError,
)

try:
    from psycopg2.pool import SimpleConnectionPool
    from psycopg2.extras import RealDictCursor
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


# ============================================================
# DDL 定义
# ============================================================
_SCHEMA_STATEMENTS = [
    # 报价单主表
    """CREATE TABLE IF NOT EXISTS quotations (
        id              SERIAL PRIMARY KEY,
        quote_number    VARCHAR(50)  NOT NULL UNIQUE,
        quote_date      DATE         NOT NULL,
        customer_name   VARCHAR(200) NOT NULL,
        contact_person  VARCHAR(100),
        sales_person    VARCHAR(100),
        customer_type   VARCHAR(20)  NOT NULL
                        CHECK (customer_type IN ('commercial','npo','ka')),
        subtotal        NUMERIC(14,2) DEFAULT 0,
        shipping        NUMERIC(14,2) DEFAULT 0,
        service_fee     NUMERIC(14,2) DEFAULT 0,
        discount        NUMERIC(14,2) DEFAULT 0,
        tax             NUMERIC(14,2) DEFAULT 0,
        grand_total     NUMERIC(14,2) DEFAULT 0,
        total_qty       INTEGER       DEFAULT 0,
        remark          TEXT,
        created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_quotations_quote_date ON quotations(quote_date)",
    "CREATE INDEX IF NOT EXISTS idx_quotations_customer   ON quotations(customer_name)",
    "CREATE INDEX IF NOT EXISTS idx_quotations_cust_type  ON quotations(customer_type)",

    # 报价单流水号序列表
    """CREATE TABLE IF NOT EXISTS quotation_seq (
        quote_day   DATE         NOT NULL UNIQUE,
        next_seq    INTEGER      NOT NULL DEFAULT 1
    )""",

    # 报价明细子表
    """CREATE TABLE IF NOT EXISTS quotation_items (
        id                           SERIAL PRIMARY KEY,
        quotation_id                 INTEGER NOT NULL
                                     REFERENCES quotations(id) ON DELETE CASCADE,
        seq                          INTEGER NOT NULL,
        strain                       VARCHAR(50)  NOT NULL,
        strain_name                  VARCHAR(200),
        genotype                     VARCHAR(200),
        age                          VARCHAR(20),
        sex                          VARCHAR(10),
        qty                          INTEGER      NOT NULL,
        unit_price                   NUMERIC(14,2) NOT NULL,
        amount                       NUMERIC(14,2) NOT NULL,
        international_commercial     NUMERIC(14,2),
        china_distributor_commercial NUMERIC(14,2),
        created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_qi_quotation_id ON quotation_items(quotation_id)",
    "CREATE INDEX IF NOT EXISTS idx_qi_strain       ON quotation_items(strain)",

    # 价格库表
    """CREATE TABLE IF NOT EXISTS price_library (
        id                           SERIAL PRIMARY KEY,
        customer_type                VARCHAR(20) NOT NULL
                                     CHECK (customer_type IN ('commercial','npo','ka')),
        strain                       VARCHAR(50)  NOT NULL,
        strain_name                  VARCHAR(200),
        long_genotype                VARCHAR(200),
        age                          VARCHAR(20),
        sex                          VARCHAR(10),
        price                        NUMERIC(14,2),
        international_commercial     NUMERIC(14,2),
        china_distributor_commercial NUMERIC(14,2),
        npo_price                    NUMERIC(14,2),
        ka_price                     NUMERIC(14,2),
        created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (customer_type, strain, long_genotype, age, sex)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_price_lookup ON price_library(customer_type, strain, long_genotype, age, sex)",
    "CREATE INDEX IF NOT EXISTS idx_price_strain ON price_library(strain)",

    # 发票记录表
    """CREATE TABLE IF NOT EXISTS invoice_records (
        id              SERIAL PRIMARY KEY,
        invoice_date    DATE,
        subject         TEXT,
        buyer           VARCHAR(200),
        amount          VARCHAR(50),
        filename        VARCHAR(255),
        filepath        TEXT,
        source          VARCHAR(20),
        folder          VARCHAR(100),
        status          VARCHAR(20) NOT NULL
                        CHECK (status IN ('success','failed')),
        reason          TEXT,
        email_uid       VARCHAR(100),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_invoice_date   ON invoice_records(invoice_date)",
    "CREATE INDEX IF NOT EXISTS idx_invoice_status ON invoice_records(status)",
    "CREATE INDEX IF NOT EXISTS idx_invoice_buyer  ON invoice_records(buyer)",
    "CREATE INDEX IF NOT EXISTS idx_invoice_uid    ON invoice_records(email_uid)",

    # 通用同步状态表
    """CREATE TABLE IF NOT EXISTS sync_state (
        state_key    VARCHAR(100) PRIMARY KEY,
        state_value  TEXT,
        updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # 系统日志表
    """CREATE TABLE IF NOT EXISTS system_logs (
        id          SERIAL PRIMARY KEY,
        log_type    VARCHAR(20),
        message     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at DESC)",

    # 兼容旧 SQLite 的表
    """CREATE TABLE IF NOT EXISTS exchange_records (
        id                SERIAL PRIMARY KEY,
        exchange_no       VARCHAR(100) UNIQUE,
        customer          TEXT,
        exchange_date     TEXT,
        points_exchanged  INTEGER,
        amount_exchanged  REAL,
        exchange_method   TEXT,
        exchange_product  TEXT,
        operator          TEXT,
        remark            TEXT,
        created_at        TEXT,
        updated_at        TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_exrec_date ON exchange_records(exchange_date DESC)",

    """CREATE TABLE IF NOT EXISTS customer_points_history (
        id                      SERIAL PRIMARY KEY,
        customer                TEXT,
        period                  TEXT,
        total_points_earned     INTEGER,
        total_points_exchanged  INTEGER,
        remaining_points        INTEGER,
        created_at              TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cph_customer ON customer_points_history(customer)",

    """CREATE TABLE IF NOT EXISTS raw_data_backup (
        id          SERIAL PRIMARY KEY,
        date        TEXT,
        order_no    TEXT,
        customer    TEXT,
        amount      REAL,
        amount_cny  REAL,
        product     TEXT,
        created_at  TEXT
    )""",

    # 库存管理表
    """CREATE TABLE IF NOT EXISTS inventory_items (
        id           SERIAL PRIMARY KEY,
        item_code    VARCHAR(100)  NOT NULL,
        title        VARCHAR(200)  NOT NULL,
        category     VARCHAR(100),
        location     VARCHAR(200),
        quantity     INTEGER       DEFAULT 0,
        extra_fields TEXT,
        is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
        created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
        updated_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
    )""",
    # 迁移：为旧表添加缺失的列（必须在 CREATE INDEX 之前）
    "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    # 迁移：移除 item_code 的 UNIQUE 约束（允许编号重复）
    "ALTER TABLE inventory_items DROP CONSTRAINT IF EXISTS inventory_items_item_code_key",
    "CREATE INDEX IF NOT EXISTS idx_inv_code ON inventory_items(item_code)",
    "CREATE INDEX IF NOT EXISTS idx_inv_category ON inventory_items(category)",
    "CREATE INDEX IF NOT EXISTS idx_inv_location ON inventory_items(location)",
    "CREATE INDEX IF NOT EXISTS idx_inv_title ON inventory_items(title)",
    "CREATE INDEX IF NOT EXISTS idx_inv_active ON inventory_items(is_active)",

    """CREATE TABLE IF NOT EXISTS inventory_transactions (
        id               SERIAL PRIMARY KEY,
        item_id          INTEGER       NOT NULL,
        transaction_type VARCHAR(20)   NOT NULL,
        quantity         INTEGER       NOT NULL,
        remark           TEXT,
        operator         VARCHAR(100),
        stock_before     INTEGER,
        stock_after      INTEGER,
        created_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
    )""",
    # 迁移：为旧表添加缺失的列（必须在 CREATE INDEX 之前）
    "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_before INTEGER",
    "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_after INTEGER",
    "CREATE INDEX IF NOT EXISTS idx_trans_item ON inventory_transactions(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_trans_type ON inventory_transactions(transaction_type)",
    "CREATE INDEX IF NOT EXISTS idx_trans_created ON inventory_transactions(created_at DESC)",

    # 库存字段配置表
    """CREATE TABLE IF NOT EXISTS inventory_fields (
        id          SERIAL PRIMARY KEY,
        field_name  VARCHAR(100) NOT NULL UNIQUE,
        field_label VARCHAR(200),
        field_type  VARCHAR(20)  DEFAULT 'text',
        sort_order  INTEGER      DEFAULT 0,
        created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS inventory_hidden_history_values (
        field_name  VARCHAR(20)  NOT NULL,
        value       VARCHAR(200) NOT NULL,
        created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (field_name, value)
    )""",
]

_INVENTORY_SCHEMA_STATEMENTS = tuple(
    statement for statement in _SCHEMA_STATEMENTS if "inventory_" in statement
)

# 保留向后兼容
SCHEMA_DDL = "\n".join(_SCHEMA_STATEMENTS)


class PgDatabaseManager:
    """PostgreSQL 数据库管理器"""

    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 5, pool=None):
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 未安装，请运行: pip install psycopg2-binary")
        self.dsn = dsn
        if pool is not None:
            self._pool = pool
            self._owns_pool = False
        else:
            self._pool = SimpleConnectionPool(minconn, maxconn, dsn)
            self._owns_pool = True

    @classmethod
    def from_secrets(cls) -> "PgDatabaseManager":
        """从 st.secrets 读取 PostgreSQL 连接配置"""
        import streamlit as st
        return cls(postgres_dsn_from_secrets(st.secrets))

    @contextmanager
    def _conn(self):
        """获取/归还连接的上下文管理器"""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def init_schema(self) -> None:
        """幂等执行全部 DDL（autocommit 模式 + 预检迁移）"""
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                # 第零步：预检——先确保关键表的列存在
                self._preflight_migration(cur)

                for statement in _SCHEMA_STATEMENTS:
                    try:
                        cur.execute(statement)
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "already exists" in err_msg or "already been taken" in err_msg:
                            continue
                        # 如果是列不存在，迁移后重试
                        if "column" in err_msg and "does not exist" in err_msg:
                            self._preflight_migration(cur)
                            cur.execute(statement)
                            continue
                        raise
                self._ensure_inventory_columns(cur)
        finally:
            self._pool.putconn(conn)

    def ensure_inventory_schema(self) -> None:
        """Ensure inventory tables exist even when unrelated schema setup failed."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                for statement in _INVENTORY_SCHEMA_STATEMENTS:
                    cur.execute(statement)

    def _preflight_migration(self, cur) -> None:
        """预检迁移：在任何 DDL 之前先补上缺失的列"""
        column_checks = [
            "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_before INTEGER",
            "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_after INTEGER",
        ]
        for sql in column_checks:
            try:
                cur.execute(sql)
            except Exception:
                pass

    def _ensure_inventory_columns(self, cur) -> None:
        """确保库存表有必要的列（兼容旧表结构）"""
        migrations = [
            ("inventory_items", "is_active", "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"),
            ("inventory_items", "updated_at", "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("inventory_transactions", "stock_before", "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_before INTEGER"),
            ("inventory_transactions", "stock_after", "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_after INTEGER"),
        ]
        for table, column, sql in migrations:
            try:
                cur.execute(sql)
            except Exception as e:
                err_msg = str(e).lower()
                if "already exists" in err_msg or "already been taken" in err_msg:
                    continue
                # 检查表是否存在
                if 'relation' in err_msg and 'does not exist' in err_msg:
                    continue
                raise

    def _migrate_missing_columns(self) -> None:
        """在出错时迁移缺失的列（autocommit 模式）"""
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                self._ensure_inventory_columns(cur)
        finally:
            self._pool.putconn(conn)

    def ping(self) -> bool:
        """健康检查"""
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._owns_pool and self._pool and not self._pool.closed:
            self._pool.closeall()

    # ============================================================
    # 日志（内部使用）
    # ============================================================
    def add_log(self, log_type: str, message: str) -> bool:
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO system_logs (log_type, message) VALUES (%s, %s)",
                        (log_type, message),
                    )
            return True
        except Exception:
            return False

    def get_logs(self, limit: int = 100) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]

    # ============================================================
    # 报价单
    # ============================================================
    def get_next_quote_number(self, quote_date: Optional[date] = None) -> str:
        """生成 CT-YYYYMMDD-NNN 格式的报价单号"""
        if quote_date is None:
            quote_date = date.today()
        day_str = quote_date.strftime("%Y%m%d")
        day_date = quote_date

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quotation_seq (quote_day, next_seq)
                    VALUES (%s, 1)
                    ON CONFLICT (quote_day)
                    DO UPDATE SET next_seq = quotation_seq.next_seq + 1
                    RETURNING next_seq
                    """,
                    (day_date,),
                )
                seq = cur.fetchone()[0]

        return f"CT-{day_str}-{seq:03d}"

    def save_quotation(self, quotation_data: Dict) -> int:
        """
        保存报价单到数据库

        Args:
            quotation_data: QuotationService.to_dict() 的输出
                {customer_info, items, summary, quote_number, quote_date}

        Returns:
            quotation_id
        """
        ci = quotation_data.get("customer_info", {})
        sm = quotation_data.get("summary", {})
        items = quotation_data.get("items", [])
        quote_number = quotation_data.get("quote_number", "")
        quote_date_str = quotation_data.get("quote_date", datetime.now().strftime("%Y-%m-%d"))

        total_qty = sum(int(i.get("qty", 0)) for i in items)

        with self._conn() as conn:
            with conn.cursor() as cur:
                # 插入主表
                cur.execute(
                    """
                    INSERT INTO quotations
                        (quote_number, quote_date, customer_name, contact_person,
                         sales_person, customer_type, subtotal, shipping, service_fee,
                         discount, tax, grand_total, total_qty)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        quote_number,
                        quote_date_str,
                        ci.get("customer_name", ""),
                        ci.get("contact_person", ""),
                        ci.get("sales_person", ""),
                        ci.get("customer_type", "commercial"),
                        sm.get("subtotal", 0),
                        sm.get("shipping", 0),
                        sm.get("service_fee", 0),
                        sm.get("discount", 0),
                        sm.get("tax", 0),
                        sm.get("grand_total", 0),
                        total_qty,
                    ),
                )
                quotation_id = cur.fetchone()[0]

                # 批量插入明细
                for seq, item in enumerate(items, 1):
                    cur.execute(
                        """
                        INSERT INTO quotation_items
                            (quotation_id, seq, strain, strain_name, genotype,
                             age, sex, qty, unit_price, amount,
                             international_commercial, china_distributor_commercial)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            quotation_id,
                            seq,
                            item.get("strain", ""),
                            item.get("name", ""),
                            item.get("genotype", ""),
                            item.get("age", ""),
                            item.get("sex", ""),
                            int(item.get("qty", 0)),
                            float(item.get("unit_price", 0)),
                            float(item.get("amount", 0)),
                            float(item.get("international_commercial", 0)) if item.get("international_commercial") else None,
                            float(item.get("china_distributor_commercial", 0)) if item.get("china_distributor_commercial") else None,
                        ),
                    )

        self.add_log("INFO", f"保存报价单: {quote_number} (ID={quotation_id})")
        return quotation_id

    def get_quotation(self, quote_number: str) -> Optional[Dict]:
        """获取完整报价单（主表 + 明细）"""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM quotations WHERE quote_number = %s", (quote_number,))
                main = cur.fetchone()
                if not main:
                    return None
                main = dict(main)

                cur.execute(
                    "SELECT * FROM quotation_items WHERE quotation_id = %s ORDER BY seq",
                    (main["id"],),
                )
                main["items"] = [dict(r) for r in cur.fetchall()]
        return main

    def list_quotations(
        self,
        customer_name: Optional[str] = None,
        customer_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """查询报价单列表（带 items_count）"""
        query = """
            SELECT q.*,
                   COUNT(qi.id) AS items_count
            FROM quotations q
            LEFT JOIN quotation_items qi ON qi.quotation_id = q.id
            WHERE 1=1
        """
        params = []
        if customer_name:
            query += " AND q.customer_name ILIKE %s"
            params.append(f"%{customer_name}%")
        if customer_type:
            query += " AND q.customer_type = %s"
            params.append(customer_type)
        if date_from:
            query += " AND q.quote_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND q.quote_date <= %s"
            params.append(date_to)

        query += " GROUP BY q.id ORDER BY q.quote_date DESC, q.id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]

    def delete_quotation(self, quote_id: int) -> bool:
        """删除报价单（CASCADE 自动清理明细）"""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quotations WHERE id = %s", (quote_id,))
                deleted = cur.rowcount > 0
        if deleted:
            self.add_log("INFO", f"删除报价单 ID={quote_id}")
        return deleted

    # ============================================================
    # 价格库
    # ============================================================
    def upsert_price_items(self, customer_type: str, df: pd.DataFrame) -> int:
        """批量 upsert 价格库数据"""
        if df is None or df.empty:
            return 0

        count = 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                for _, row in df.iterrows():
                    cur.execute(
                        """
                        INSERT INTO price_library
                            (customer_type, strain, strain_name, long_genotype,
                             age, sex, price, international_commercial,
                             china_distributor_commercial, npo_price, ka_price, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (customer_type, strain, long_genotype, age, sex)
                        DO UPDATE SET
                            strain_name = EXCLUDED.strain_name,
                            price = EXCLUDED.price,
                            international_commercial = EXCLUDED.international_commercial,
                            china_distributor_commercial = EXCLUDED.china_distributor_commercial,
                            npo_price = EXCLUDED.npo_price,
                            ka_price = EXCLUDED.ka_price,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            customer_type,
                            str(row.get("strain", "")),
                            str(row.get("strain_name", "")),
                            str(row.get("long_genotype", "")),
                            str(row.get("age", "")),
                            str(row.get("sex", "")),
                            float(row.get("price", 0)) if pd.notna(row.get("price")) else None,
                            float(row.get("international_commercial", 0)) if pd.notna(row.get("international_commercial")) else None,
                            float(row.get("china_distributor_commercial", 0)) if pd.notna(row.get("china_distributor_commercial")) else None,
                            float(row.get("npo_price", 0)) if pd.notna(row.get("npo_price")) else None,
                            float(row.get("ka_price", 0)) if pd.notna(row.get("ka_price")) else None,
                        ),
                    )
                    count += 1

        self.add_log("INFO", f"价格库 upsert: {customer_type} {count} 条")
        return count

    def bulk_upsert_price_items(self, dataframes: Dict[str, pd.DataFrame]) -> Dict:
        """批量导入多个客户类型的价格数据"""
        result = {}
        for customer_type, df in dataframes.items():
            result[customer_type] = self.upsert_price_items(customer_type, df)
        return result

    def query_price(
        self,
        strain: str,
        long_genotype: str,
        age: str,
        sex: str,
        customer_type: str = "commercial",
    ) -> Dict:
        """查询价格（返回结构与 PriceService.query_price 一致）"""
        from modules.price_normalizer import normalize_age, normalize_sex

        age_n = normalize_age(age)
        sex_n = normalize_sex(sex)

        price_key_map = {
            "commercial": "china_distributor_commercial",
            "npo": "npo_price",
            "ka": "ka_price",
        }
        price_col = price_key_map.get(customer_type, "price")

        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT * FROM price_library
                    WHERE customer_type = %s
                      AND TRIM(strain) = %s
                      AND TRIM(long_genotype) = %s
                      AND TRIM(age) = %s
                      AND TRIM(sex) = %s
                    """,
                    (customer_type, strain.strip(), long_genotype.strip(), age_n, sex_n),
                )
                rows = cur.fetchall()

        if len(rows) == 0:
            return {"error": "未找到对应价格", "found": False}
        if len(rows) > 1:
            return {"error": "价格库存在重复数据", "found": False, "count": len(rows)}

        row = dict(rows[0])
        return {
            "found": True,
            "strain": row.get("strain", strain),
            "strain_name": row.get("strain_name", ""),
            "long_genotype": row.get("long_genotype", long_genotype),
            "age": row.get("age", age),
            "sex": row.get("sex", sex),
            "price": float(row.get(price_col) or row.get("price") or 0),
            "international_commercial": float(row.get("international_commercial") or 0),
            "china_distributor_commercial": float(row.get("china_distributor_commercial") or 0),
            "customer_type": customer_type,
        }

    def get_all_strains(self, customer_type: str = "commercial") -> List[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT strain FROM price_library WHERE customer_type = %s ORDER BY strain",
                    (customer_type,),
                )
                return [r[0] for r in cur.fetchall()]

    def get_strain_info(self, strain: str, customer_type: str = "commercial") -> Optional[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM price_library
                    WHERE customer_type = %s AND TRIM(strain) = %s
                    """,
                    (customer_type, strain.strip()),
                )
                rows = cur.fetchall()
        if not rows:
            return None
        row = dict(rows[0])
        return {
            "strain": row.get("strain", strain),
            "strain_name": row.get("strain_name", ""),
            "long_genotype": row.get("long_genotype", ""),
            "available_ages": list(set(r["age"] for r in [dict(x) for x in rows] if r.get("age"))),
            "available_sexes": list(set(r["sex"] for r in [dict(x) for x in rows] if r.get("sex"))),
        }

    def is_price_loaded(self, customer_type: Optional[str] = None) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                if customer_type:
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM price_library WHERE customer_type = %s LIMIT 1)",
                        (customer_type,),
                    )
                else:
                    cur.execute("SELECT EXISTS(SELECT 1 FROM price_library LIMIT 1)")
                return cur.fetchone()[0]

    def get_price_library_as_dataframe(self, customer_type: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """从数据库加载价格库为 DataFrame（按客户类型分组）"""
        with self._conn() as conn:
            if customer_type:
                df = pd.read_sql(
                    "SELECT * FROM price_library WHERE customer_type = %s",
                    conn,
                    params=(customer_type,),
                )
                return {customer_type: df}
            else:
                df = pd.read_sql("SELECT * FROM price_library", conn)
                return {ct: group for ct, group in df.groupby("customer_type")}

    def clear_price_library(self, customer_type: Optional[str] = None) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                if customer_type:
                    cur.execute("DELETE FROM price_library WHERE customer_type = %s", (customer_type,))
                else:
                    cur.execute("DELETE FROM price_library")
                return cur.rowcount

    # ============================================================
    # 发票
    # ============================================================
    def add_invoice_record(self, record: Dict) -> int:
        """插入单条发票记录"""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoice_records
                        (invoice_date, subject, buyer, amount, filename, filepath,
                         source, folder, status, reason, email_uid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        record.get("date"),
                        record.get("subject"),
                        record.get("buyer"),
                        str(record.get("amount", "")),
                        record.get("filename"),
                        record.get("filepath"),
                        record.get("source"),
                        record.get("folder"),
                        record.get("status", "success"),
                        record.get("reason"),
                        record.get("email_uid"),
                    ),
                )
                result = cur.fetchone()
                return result[0] if result else 0

    def add_invoice_records(self, records: List[Dict]) -> int:
        """批量插入发票记录"""
        count = 0
        for record in records:
            if self.add_invoice_record(record):
                count += 1
        return count

    def get_invoice_records(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        buyer: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        query = "SELECT * FROM invoice_records WHERE 1=1"
        params = []
        if date_from:
            query += " AND invoice_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND invoice_date <= %s"
            params.append(date_to)
        if status:
            query += " AND status = %s"
            params.append(status)
        if buyer:
            query += " AND buyer ILIKE %s"
            params.append(f"%{buyer}%")
        query += " ORDER BY invoice_date DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]

    def is_invoice_processed(self, email_uid: str) -> bool:
        if not email_uid:
            return False
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM invoice_records WHERE email_uid = %s LIMIT 1",
                    (email_uid,),
                )
                return cur.fetchone() is not None

    def get_processed_invoice_uids(self) -> set:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT email_uid FROM invoice_records WHERE email_uid IS NOT NULL")
                return {r[0] for r in cur.fetchall()}

    def delete_invoice_record(self, record_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM invoice_records WHERE id = %s", (record_id,))
                return cur.rowcount > 0

    # ============================================================
    # 通用同步状态
    # ============================================================
    def get_state(self, state_key: str) -> Optional[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state_value FROM sync_state WHERE state_key = %s", (state_key,))
                result = cur.fetchone()
                return result[0] if result else None

    def set_state(self, state_key: str, state_value: str) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sync_state (state_key, state_value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (state_key)
                    DO UPDATE SET state_value = EXCLUDED.state_value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (state_key, state_value),
                )
        return True

    # ============================================================
    # 兼容旧 SQLite 方法（ExchangeRecords / PointsHistory / RawData）
    # ============================================================
    def add_exchange_record(self, exchange_no, customer, exchange_date, points_exchanged,
                            amount_exchanged, exchange_method, exchange_product,
                            operator, remark="") -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO exchange_records
                            (exchange_no, customer, exchange_date, points_exchanged,
                             amount_exchanged, exchange_method, exchange_product,
                             operator, remark, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (exchange_no) DO UPDATE SET
                            customer=EXCLUDED.customer, exchange_date=EXCLUDED.exchange_date,
                            points_exchanged=EXCLUDED.points_exchanged,
                            amount_exchanged=EXCLUDED.amount_exchanged,
                            exchange_method=EXCLUDED.exchange_method,
                            exchange_product=EXCLUDED.exchange_product,
                            operator=EXCLUDED.operator, remark=EXCLUDED.remark,
                            updated_at=EXCLUDED.updated_at
                        """,
                        (exchange_no, customer, exchange_date, points_exchanged,
                         amount_exchanged, exchange_method, exchange_product,
                         operator, remark, now, now),
                    )
            self.add_log("INFO", f"添加兑换记录: {exchange_no} - {customer}")
            return True
        except Exception as e:
            self.add_log("ERROR", f"添加兑换记录失败: {str(e)}")
            return False

    def get_exchange_records(self) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM exchange_records ORDER BY exchange_date DESC")
                return [dict(r) for r in cur.fetchall()]

    def get_exchange_record_by_no(self, exchange_no: str) -> Optional[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM exchange_records WHERE exchange_no = %s", (exchange_no,))
                row = cur.fetchone()
                return dict(row) if row else None

    def delete_exchange_record(self, exchange_no: str) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM exchange_records WHERE exchange_no = %s", (exchange_no,))
                return cur.rowcount > 0

    def save_customer_points_history(self, customer, period, total_points_earned,
                                     total_points_exchanged, remaining_points) -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO customer_points_history
                            (customer, period, total_points_earned,
                             total_points_exchanged, remaining_points, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (customer, period, total_points_earned,
                         total_points_exchanged, remaining_points, now),
                    )
            return True
        except Exception as e:
            self.add_log("ERROR", f"保存积分历史失败: {str(e)}")
            return False

    def get_customer_points_history(self, customer: Optional[str] = None) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if customer:
                    cur.execute(
                        "SELECT * FROM customer_points_history WHERE customer = %s ORDER BY period DESC",
                        (customer,),
                    )
                else:
                    cur.execute("SELECT * FROM customer_points_history ORDER BY period DESC")
                return [dict(r) for r in cur.fetchall()]

    def backup_raw_data(self, df_raw: pd.DataFrame) -> int:
        if df_raw is None or df_raw.empty:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                for _, row in df_raw.iterrows():
                    cur.execute(
                        """
                        INSERT INTO raw_data_backup
                            (date, order_no, customer, amount, amount_cny, product, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(row.get("日期", "")),
                            str(row.get("单据编号", "")),
                            str(row.get("客户", "")),
                            float(row.get("金额", 0)),
                            float(row.get("金额（本位币）", 0)),
                            str(row.get("货号", "")),
                            now,
                        ),
                    )
                    count += 1
        self.add_log("INFO", f"备份原始数据: {count} 条")
        return count

    def sync_exchange_from_excel(self, df_exchange: pd.DataFrame) -> int:
        if df_exchange is None or df_exchange.empty:
            return 0
        count = 0
        for _, row in df_exchange.iterrows():
            exchange_no = str(row.get("兑换编号", ""))
            if exchange_no:
                success = self.add_exchange_record(
                    exchange_no=exchange_no,
                    customer=str(row.get("客户", "")),
                    exchange_date=str(row.get("兑换日期", "")),
                    points_exchanged=int(row.get("兑换积分数量", 0)),
                    amount_exchanged=float(row.get("兑换金额", 0)),
                    exchange_method=str(row.get("兑换方式", "")),
                    exchange_product=str(row.get("兑换产品", "")),
                    operator=str(row.get("操作人员", "")),
                    remark=str(row.get("备注", "")),
                )
                if success:
                    count += 1
        return count

    # ============================================================
    # 库存管理
    # ============================================================
    def list_inventory_items(self) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM inventory_items ORDER BY id DESC")
                return [dict(r) for r in cur.fetchall()]

    def add_inventory_item(self, item: Dict) -> int:
        import json as _json
        extra = _json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inventory_items
                        (item_code, title, category, location, quantity, extra_fields)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (item.get("item_code", ""), item.get("title", ""),
                     item.get("category", ""), item.get("location", ""),
                     int(item.get("quantity", 0)), extra),
                )
                item_id = cur.fetchone()[0]
                self._restore_inventory_history_values(cur, item)
                return item_id

    def update_inventory_item(self, item_id: int, item: Dict) -> bool:
        import json as _json
        extra = _json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE inventory_items SET
                        item_code=%s, title=%s, category=%s, location=%s, extra_fields=%s
                       WHERE id=%s""",
                    (item.get("item_code", ""), item.get("title", ""),
                     item.get("category", ""), item.get("location", ""), extra, item_id),
                )
                self._restore_inventory_history_values(cur, item)
                return cur.rowcount > 0

    def delete_inventory_item(self, item_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM inventory_transactions WHERE item_id=%s", (item_id,))
                cur.execute("DELETE FROM inventory_items WHERE id=%s", (item_id,))
                return True

    def inventory_transaction(self, item_id: int, txn_type: str, qty: int,
                              remark: str = "", operator: str = "") -> bool:
        delta = -abs(qty) if txn_type == "out" else abs(qty)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inventory_transactions
                        (item_id, transaction_type, quantity, remark, operator)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (item_id, txn_type, abs(qty), remark, operator),
                )
                cur.execute(
                    "UPDATE inventory_items SET quantity = quantity + %s WHERE id = %s",
                    (delta, item_id),
                )
                return True

    def list_inventory_transactions(self, item_id=None, limit=100) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if item_id:
                    cur.execute(
                        """SELECT t.*, i.item_code, i.title
                           FROM inventory_transactions t
                           LEFT JOIN inventory_items i ON t.item_id = i.id
                           WHERE t.item_id = %s
                           ORDER BY t.created_at DESC LIMIT %s""",
                        (item_id, limit),
                    )
                else:
                    cur.execute(
                        """SELECT t.*, i.item_code, i.title
                           FROM inventory_transactions t
                           LEFT JOIN inventory_items i ON t.item_id = i.id
                           ORDER BY t.created_at DESC LIMIT %s""",
                        (limit,),
                    )
                return [dict(r) for r in cur.fetchall()]

    def list_inventory_fields(self) -> List[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM inventory_fields ORDER BY sort_order, id")
                return [dict(r) for r in cur.fetchall()]

    def add_inventory_field(self, field_name: str, field_label: str,
                            field_type: str = "text") -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inventory_fields (field_name, field_label, field_type)
                       VALUES (%s, %s, %s)""",
                    (field_name, field_label, field_type),
                )
                return True

    def delete_inventory_field(self, field_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM inventory_fields WHERE id=%s", (field_id,))
                return True

    def get_distinct_categories(self) -> List[str]:
        return self.get_inventory_history_values("category")

    def get_distinct_locations(self) -> List[str]:
        return self.get_inventory_history_values("location")

    def get_inventory_item(self, item_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM inventory_items WHERE id=%s", (item_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def inventory_code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                if exclude_item_id is None:
                    cur.execute(
                        """SELECT 1 FROM inventory_items
                           WHERE item_code=%s AND COALESCE(is_active, TRUE) = TRUE
                           LIMIT 1""",
                        (item_code,),
                    )
                else:
                    cur.execute(
                        """SELECT 1 FROM inventory_items
                           WHERE item_code=%s AND id<>%s
                           AND COALESCE(is_active, TRUE) = TRUE
                           LIMIT 1""",
                        (item_code, exclude_item_id),
                    )
                return cur.fetchone() is not None

    def get_inventory_history_values(self, column: str) -> List[str]:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        with self._conn() as conn:
            with conn.cursor() as cur:
                self._ensure_inventory_history_table(cur)
                cur.execute(
                    f"""SELECT DISTINCT BTRIM(i.{column}) AS value
                        FROM inventory_items i
                        WHERE i.{column} IS NOT NULL AND BTRIM(i.{column}) != ''
                          AND NOT EXISTS (
                              SELECT 1
                              FROM inventory_hidden_history_values h
                              WHERE h.field_name=%s AND h.value=BTRIM(i.{column})
                          )
                        ORDER BY value""",
                    (column,),
                )
                return [row[0] for row in cur.fetchall()]

    def delete_inventory_history_value(self, column: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if column not in {"category", "location"}:
            raise ValueError(f"不支持的库存历史字段: {column}")
        if not normalized_value:
            return False
        with self._conn() as conn:
            with conn.cursor() as cur:
                self._ensure_inventory_history_table(cur)
                cur.execute(
                    """INSERT INTO inventory_hidden_history_values (field_name, value)
                       VALUES (%s, %s)
                       ON CONFLICT (field_name, value)
                       DO UPDATE SET created_at=CURRENT_TIMESTAMP""",
                    (column, normalized_value),
                )
        return True

    @staticmethod
    def _ensure_inventory_history_table(cur) -> None:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS inventory_hidden_history_values (
                field_name VARCHAR(20) NOT NULL,
                value VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (field_name, value)
            )"""
        )

    @classmethod
    def _restore_inventory_history_values(cls, cur, item: Dict) -> None:
        cls._ensure_inventory_history_table(cur)
        for column in ("category", "location"):
            value = str(item.get(column) or "").strip()
            if value:
                cur.execute(
                    """DELETE FROM inventory_hidden_history_values
                       WHERE field_name=%s AND value=%s""",
                    (column, value),
                )

    def get_inventory_titles_by_category(self, category: str) -> List[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT BTRIM(title) AS value
                       FROM inventory_items
                       WHERE title IS NOT NULL AND BTRIM(title) != ''
                         AND BTRIM(category) = %s
                       ORDER BY value""",
                    (category,),
                )
                return [row[0] for row in cur.fetchall()]

    def clear_inventory_history_value(self, column: str, value: str) -> None:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE inventory_items
                       SET {column} = NULL
                       WHERE BTRIM({column}) = %s""",
                    (value,),
                )

    def count_inventory_transactions(self, item_id: int) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM inventory_transactions WHERE item_id=%s",
                    (item_id,),
                )
                return int(cur.fetchone()[0])

    def set_inventory_item_active(self, item_id: int, is_active: bool) -> bool:
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE inventory_items
                           SET is_active=%s, updated_at=CURRENT_TIMESTAMP
                           WHERE id=%s""",
                        (is_active, item_id),
                    )
                    return cur.rowcount > 0
        except Exception as e:
            err_msg = str(e).lower()
            if "column" in err_msg and "does not exist" in err_msg:
                self._migrate_missing_columns()
                with self._conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE inventory_items
                               SET is_active=%s, updated_at=CURRENT_TIMESTAMP
                               WHERE id=%s""",
                            (is_active, item_id),
                        )
                        return cur.rowcount > 0
            raise

    def delete_inventory_item_without_history(self, item_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM inventory_transactions WHERE item_id=%s LIMIT 1 FOR UPDATE",
                    (item_id,),
                )
                if cur.fetchone():
                    return False
                cur.execute("DELETE FROM inventory_items WHERE id=%s", (item_id,))
                return cur.rowcount > 0

    def inventory_transaction_atomic(
        self,
        item_id: int,
        txn_type: str,
        qty: int,
        remark: str = "",
        operator: str = "",
    ) -> bool:
        if txn_type not in {"in", "out"}:
            raise ValidationError("出入库类型无效")
        quantity = int(qty)
        if quantity <= 0:
            raise ValidationError("出入库数量必须大于0")

        def _do_transaction():
            with self._conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 使用 COALESCE 兼容 is_active 列不存在的情况
                    cur.execute(
                        """SELECT id, quantity,
                                  COALESCE(is_active, TRUE) AS is_active
                           FROM inventory_items WHERE id=%s FOR UPDATE""",
                        (item_id,),
                    )
                    item = cur.fetchone()
                    if not item:
                        raise ItemNotFoundError("库存物品不存在")
                    if not bool(item.get("is_active", True)):
                        raise ItemArchivedError("该物品已归档，不能继续出入库")
                    stock_before = int(item.get("quantity") or 0)
                    if txn_type == "out" and quantity > stock_before:
                        raise InsufficientStockError(
                            f"当前库存为{stock_before}，本次最多可出库{stock_before}"
                        )
                    stock_after = stock_before + quantity if txn_type == "in" else stock_before - quantity
                    cur.execute(
                        """INSERT INTO inventory_transactions
                            (item_id, transaction_type, quantity, remark, operator, stock_before, stock_after)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (item_id, txn_type, quantity, remark, operator, stock_before, stock_after),
                    )
                    cur.execute(
                        """UPDATE inventory_items
                           SET quantity=%s, updated_at=CURRENT_TIMESTAMP
                           WHERE id=%s""",
                        (stock_after, item_id),
                    )
                    return True

        try:
            return _do_transaction()
        except Exception as e:
            err_msg = str(e).lower()
            if "column" in err_msg and "does not exist" in err_msg:
                self._migrate_missing_columns()
                return _do_transaction()
            raise

    # ============================================================
    # 迁移工具
    # ============================================================
    def migrate_from_sqlite(self, sqlite_path: str) -> Dict:
        """从 SQLite 迁移数据到 PostgreSQL"""
        if not os.path.exists(sqlite_path):
            return {"error": f"SQLite 文件不存在: {sqlite_path}"}

        result = {}
        conn_sqlite = sqlite3.connect(sqlite_path)
        conn_sqlite.row_factory = sqlite3.Row

        try:
            # exchange_records
            rows = conn_sqlite.execute("SELECT * FROM exchange_records").fetchall()
            count = 0
            for row in rows:
                d = dict(row)
                success = self.add_exchange_record(
                    exchange_no=d.get("exchange_no", ""),
                    customer=d.get("customer", ""),
                    exchange_date=d.get("exchange_date", ""),
                    points_exchanged=d.get("points_exchanged", 0),
                    amount_exchanged=d.get("amount_exchanged", 0),
                    exchange_method=d.get("exchange_method", ""),
                    exchange_product=d.get("exchange_product", ""),
                    operator=d.get("operator", ""),
                    remark=d.get("remark", ""),
                )
                if success:
                    count += 1
            result["exchange_records"] = count

            # customer_points_history
            rows = conn_sqlite.execute("SELECT * FROM customer_points_history").fetchall()
            count = 0
            for row in rows:
                d = dict(row)
                if self.save_customer_points_history(
                    customer=d.get("customer", ""),
                    period=d.get("period", ""),
                    total_points_earned=d.get("total_points_earned", 0),
                    total_points_exchanged=d.get("total_points_exchanged", 0),
                    remaining_points=d.get("remaining_points", 0),
                ):
                    count += 1
            result["customer_points_history"] = count

            # raw_data_backup
            rows = conn_sqlite.execute("SELECT * FROM raw_data_backup").fetchall()
            count = 0
            for row in rows:
                d = dict(row)
                with self._conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO raw_data_backup
                                (date, order_no, customer, amount, amount_cny, product, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (d.get("date", ""), d.get("order_no", ""), d.get("customer", ""),
                             d.get("amount", 0), d.get("amount_cny", 0), d.get("product", ""),
                             d.get("created_at", "")),
                        )
                count += 1
            result["raw_data_backup"] = count

            # system_logs
            rows = conn_sqlite.execute("SELECT * FROM system_logs").fetchall()
            count = 0
            for row in rows:
                d = dict(row)
                self.add_log(d.get("log_type", "INFO"), d.get("message", ""))
                count += 1
            result["system_logs"] = count

        finally:
            conn_sqlite.close()

        self.add_log("INFO", f"SQLite 迁移完成: {result}")
        return result


# ============================================================
# Streamlit 缓存工厂
# ============================================================
def get_pg_manager() -> PgDatabaseManager:
    """
    获取 PostgreSQL 数据库管理器（通过 st.cache_resource 缓存）
    """
    import streamlit as st

    @st.cache_resource
    def _get_manager():
        mgr = PgDatabaseManager.from_secrets()
        mgr.init_schema()
        return mgr

    return _get_manager()
