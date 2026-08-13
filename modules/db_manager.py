"""
通用数据库管理器（支持 MySQL / PostgreSQL）

根据 secrets.toml 中的配置自动选择数据库类型。
如果配置了 [mysql] 则使用 MySQL，配置了 [postgres] 则使用 PostgreSQL。
两者都没有时回退到本地 SQLite。

使用方式：
    from modules.db_manager import get_db_manager
    db = get_db_manager()
    db.init_schema()
    db.save_quotation(quotation_data)
"""
import os
import sqlite3
import json
import threading
from contextlib import contextmanager
from datetime import datetime, date
from typing import Dict, List, Optional

import pandas as pd

from modules.inventory.errors import (
    InsufficientStockError,
    ItemArchivedError,
    ItemNotFoundError,
    ValidationError,
)
from modules.database_config import postgres_dsn_from_secrets, redact_database_error

# ============================================================
# 数据库类型检测
# ============================================================
_PLACEHOLDER_DATABASE_VALUES = {
    "your-mysql-host.com",
    "your-db-host.supabase.co",
    "your-password-here",
}


def _secret_section(secrets, name: str):
    try:
        return secrets[name] if name in secrets else None
    except Exception:
        return None


def _secret_value(section, name: str) -> str:
    if section is None:
        return ""
    try:
        value = section.get(name, "")
    except AttributeError:
        try:
            value = section[name]
        except Exception:
            value = ""
    return str(value or "").strip()


def _is_real_database_section(section, required_keys: tuple[str, ...]) -> bool:
    values = [_secret_value(section, key) for key in required_keys]
    return bool(values) and all(
        value and value.casefold() not in _PLACEHOLDER_DATABASE_VALUES
        for value in values
    )


def _detect_db_type(secrets=None) -> str:
    """只选择填写完整且不是示例值的远程数据库配置。"""
    if secrets is None:
        try:
            import streamlit as st

            secrets = st.secrets
        except Exception:
            return "sqlite"

    requested_backend = _secret_value(secrets, "database_backend").casefold()
    mysql = _secret_section(secrets, "mysql")
    postgres = _secret_section(secrets, "postgres")
    is_mysql_ready = _is_real_database_section(
        mysql, ("host", "user", "password", "database")
    )
    try:
        postgres_dsn_from_secrets(secrets)
        is_postgres_ready = True
    except ValueError:
        is_postgres_ready = False

    if requested_backend == "mysql" and is_mysql_ready:
        return "mysql"
    if requested_backend in {"postgres", "postgresql"} and is_postgres_ready:
        return "postgres"
    if is_postgres_ready:
        return "postgres"
    if is_mysql_ready:
        return "mysql"
    return "sqlite"


def get_db_manager():
    """
    获取数据库管理器（通过 st.cache_resource 缓存）
    优先使用 PostgreSQL/MySQL，连接失败时自动降级到 SQLite
    自动初始化数据库表结构
    
    返回值包含数据库管理器实例，可通过 manager.get_connection_status() 获取连接状态
    """
    import streamlit as st

    @st.cache_resource
    def _get_manager():
        db_type = _detect_db_type()
        errors = []
        db_info = {
            "db_type": db_type,
            "primary_connection": None,
            "fallback_reason": None,
        }

        if db_type == "mysql":
            try:
                mgr = _MySQLManager.from_secrets()
                mgr.init_schema()
                db_info["primary_connection"] = "MySQL 连接成功"
                mgr._connection_info = db_info
                mgr._backend_name = "MySQL"
                return mgr
            except Exception as e:
                error_detail = f"MySQL: {type(e).__name__}: {e}"
                errors.append(error_detail)
                db_info["fallback_reason"] = error_detail
        elif db_type == "postgres":
            try:
                mgr = _PostgresManager.from_secrets()
                ping_result = mgr.ping_with_detail()
                if ping_result["success"]:
                    # 尝试初始化 schema（失败不阻塞连接）
                    try:
                        mgr.init_schema()
                    except Exception as schema_err:
                        err_str = str(schema_err).lower()
                        if "column" in err_str and "does not exist" in err_str:
                            # 列不存在：强制迁移后重试
                            try:
                                mgr._force_migration()
                                mgr.init_schema()
                            except Exception:
                                pass  # 迁移也失败就跳过，不阻塞
                        else:
                            pass  # 其他 schema 错误也不阻塞连接
                    db_info["primary_connection"] = "PostgreSQL 连接成功"
                    mgr._connection_info = db_info
                    mgr._backend_name = "PostgreSQL"
                    return mgr
                else:
                    error_detail = f"PostgreSQL ping 失败: {ping_result['message']}"
                    errors.append(error_detail)
                    db_info["fallback_reason"] = error_detail
            except Exception as e:
                error_detail = f"PostgreSQL: {redact_database_error(e)}"
                errors.append(error_detail)
                db_info["fallback_reason"] = error_detail

        # 降级到 SQLite（不抛出异常）
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "database",
            "points.db",
        )
        sqlite_mgr = _SQLiteManager(db_path)
        sqlite_mgr.init_schema()
        sqlite_mgr._backend_name = "SQLite（本地临时数据库）"
        sqlite_mgr._fallback_note = "; ".join(errors) if errors else ""
        sqlite_mgr._connection_info = {
            "db_type": "sqlite",
            "primary_connection": None,
            "fallback_reason": sqlite_mgr._fallback_note or "无主数据库配置",
            "is_fallback": True,
        }
        return sqlite_mgr

    return _get_manager()


# ============================================================
# 通用基类
# ============================================================
class _BaseManager:
    """通用数据库管理器基类"""

    def __init__(self):
        self._initialized = False

    def init_schema(self) -> None:
        raise NotImplementedError

    def ping(self) -> bool:
        raise NotImplementedError

    def add_log(self, log_type: str, message: str) -> bool:
        raise NotImplementedError

    # ---------- 报价单 ----------
    def get_next_quote_number(self) -> str:
        raise NotImplementedError

    def save_quotation(self, quotation_data: Dict) -> int:
        raise NotImplementedError

    def get_quotation(self, quote_number: str) -> Optional[Dict]:
        raise NotImplementedError

    def list_quotations(self, **kwargs) -> List[Dict]:
        raise NotImplementedError

    def delete_quotation(self, quote_id: int) -> bool:
        raise NotImplementedError

    # ---------- 价格库 ----------
    def upsert_price_items(self, customer_type: str, df: pd.DataFrame) -> int:
        raise NotImplementedError

    def query_price(self, strain: str, long_genotype: str, age: str, sex: str,
                    customer_type: str = "commercial") -> Dict:
        raise NotImplementedError

    def is_price_loaded(self, customer_type: Optional[str] = None) -> bool:
        raise NotImplementedError

    def get_price_library_as_dataframe(self, customer_type: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError

    # ---------- 发票 ----------
    def add_invoice_record(self, record: Dict) -> int:
        raise NotImplementedError

    def get_invoice_records(self, **kwargs) -> List[Dict]:
        raise NotImplementedError

    def is_invoice_processed(self, email_uid: str) -> bool:
        raise NotImplementedError

    def get_processed_invoice_uids(self) -> set:
        raise NotImplementedError

    # ---------- 兼容旧 SQLite ----------
    def add_exchange_record(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    def get_exchange_records(self) -> List[Dict]:
        raise NotImplementedError

    def save_customer_points_history(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    def get_customer_points_history(self, customer: Optional[str] = None) -> List[Dict]:
        raise NotImplementedError

    def backup_raw_data(self, df_raw: pd.DataFrame) -> int:
        raise NotImplementedError

    def sync_exchange_from_excel(self, df_exchange: pd.DataFrame) -> int:
        raise NotImplementedError

    # ---------- 库存管理 ----------
    def list_inventory_items(self) -> List[Dict]:
        raise NotImplementedError

    def add_inventory_item(self, item: Dict) -> int:
        raise NotImplementedError

    def update_inventory_item(self, item_id: int, item: Dict) -> bool:
        raise NotImplementedError

    def delete_inventory_item(self, item_id: int) -> bool:
        raise NotImplementedError

    def inventory_transaction(self, item_id: int, txn_type: str, qty: int,
                              remark: str = "", operator: str = "") -> bool:
        raise NotImplementedError

    def list_inventory_transactions(self, item_id: Optional[int] = None,
                                    limit: int = 100) -> List[Dict]:
        raise NotImplementedError

    def list_inventory_fields(self) -> List[Dict]:
        raise NotImplementedError

    def add_inventory_field(self, field_name: str, field_label: str,
                            field_type: str = "text") -> bool:
        raise NotImplementedError

    def delete_inventory_field(self, field_id: int) -> bool:
        raise NotImplementedError

    def get_distinct_categories(self) -> List[str]:
        """获取所有不重复的 title类别"""
        raise NotImplementedError

    def get_distinct_locations(self) -> List[str]:
        """获取所有不重复的存放位置"""
        raise NotImplementedError

    def get_inventory_item(self, item_id: int) -> Optional[Dict]:
        raise NotImplementedError

    def inventory_code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        raise NotImplementedError

    def get_inventory_history_values(self, column: str) -> List[str]:
        raise NotImplementedError

    def get_inventory_titles_by_category(self, category: str) -> List[str]:
        raise NotImplementedError

    def clear_inventory_history_value(self, column: str, value: str) -> None:
        raise NotImplementedError

    def delete_inventory_history_value(self, column: str, value: str) -> bool:
        raise NotImplementedError

    def count_inventory_transactions(self, item_id: int) -> int:
        raise NotImplementedError

    def set_inventory_item_active(self, item_id: int, is_active: bool) -> bool:
        raise NotImplementedError

    def delete_inventory_item_without_history(self, item_id: int) -> bool:
        raise NotImplementedError

    def inventory_transaction_atomic(
        self,
        item_id: int,
        txn_type: str,
        qty: int,
        remark: str = "",
        operator: str = "",
    ) -> bool:
        raise NotImplementedError


# ============================================================
# MySQL 实现
# ============================================================
try:
    import pymysql
    import pymysql.cursors
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class _MySQLManager(_BaseManager):
    """MySQL 数据库管理器"""

    def __init__(self, config: Dict):
        if not MYSQL_AVAILABLE:
            raise ImportError("pymysql 未安装，请运行: pip install pymysql")
        self.config = config
        self._lock = threading.Lock()
        self._conn = None

    @classmethod
    def from_secrets(cls) -> "_MySQLManager":
        import streamlit as st
        cfg = st.secrets["mysql"]
        return cls({
            "host": cfg.get("host", "localhost"),
            "port": int(cfg.get("port", 3306)),
            "user": cfg.get("user", "root"),
            "password": cfg.get("password", ""),
            "database": cfg.get("database", "customer_points"),
            "charset": cfg.get("charset", "utf8mb4"),
        })

    def _get_conn(self):
        """获取/创建连接"""
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"],
                charset=self.config["charset"],
                cursorclass=pymysql.cursors.DictCursor,
            )
        return self._conn

    def _execute(self, sql: str, params=None, fetch=False):
        """执行SQL"""
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(sql, params or ())
                if fetch:
                    result = cur.fetchall()
                else:
                    conn.commit()
                    result = cur.lastrowid
                return result
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def ping(self) -> bool:
        try:
            conn = self._get_conn()
            conn.ping(reconnect=True)
            return True
        except Exception:
            return False

    def ping_with_detail(self) -> Dict:
        """带详细错误信息的连接测试"""
        result = {"success": False, "message": "", "details": {}}
        try:
            conn = self._get_conn()
            conn.ping(reconnect=True)
            result["success"] = True
            result["message"] = "连接成功"
            result["details"]["host"] = self.config.get("host", "")
            result["details"]["port"] = self.config.get("port", "")
            result["details"]["database"] = self.config.get("database", "")
            return result
        except Exception as e:
            result["message"] = f"{type(e).__name__}: {e}"
            result["details"]["exception_type"] = type(e).__name__
            error_str = str(e).lower()
            if "access denied" in error_str:
                result["details"]["possible_cause"] = "用户名或密码错误"
            elif "unknown database" in error_str:
                result["details"]["possible_cause"] = "数据库不存在"
            elif "connection refused" in error_str:
                result["details"]["possible_cause"] = "连接被拒绝，请检查主机和端口"
            elif "timeout" in error_str:
                result["details"]["possible_cause"] = "连接超时"
            elif "host" in error_str:
                result["details"]["possible_cause"] = "主机名无法解析"
            return result

    def get_connection_status(self) -> Dict:
        """获取当前连接状态"""
        return {
            "db_type": "MySQL",
            "config": {
                "host": self.config.get("host", ""),
                "port": self.config.get("port", ""),
                "database": self.config.get("database", ""),
            },
            "connection_info": getattr(self, '_connection_info', {}),
        }

    def init_schema(self) -> None:
        """创建表结构（MySQL语法）"""
        ddl = """
        CREATE TABLE IF NOT EXISTS quotations (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            quote_number    VARCHAR(50)  NOT NULL UNIQUE,
            quote_date      DATE         NOT NULL,
            customer_name   VARCHAR(200) NOT NULL,
            contact_person  VARCHAR(100),
            sales_person    VARCHAR(100),
            customer_type   VARCHAR(20)  NOT NULL,
            subtotal        DECIMAL(14,2) DEFAULT 0,
            shipping        DECIMAL(14,2) DEFAULT 0,
            service_fee     DECIMAL(14,2) DEFAULT 0,
            discount        DECIMAL(14,2) DEFAULT 0,
            tax             DECIMAL(14,2) DEFAULT 0,
            grand_total     DECIMAL(14,2) DEFAULT 0,
            total_qty       INT          DEFAULT 0,
            remark          TEXT,
            created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_q_date (quote_date),
            INDEX idx_q_customer (customer_name),
            INDEX idx_q_type (customer_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS quotation_items (
            id                           INT AUTO_INCREMENT PRIMARY KEY,
            quotation_id                 INT NOT NULL,
            seq                          INT NOT NULL,
            strain                       VARCHAR(50)  NOT NULL,
            strain_name                  VARCHAR(200),
            genotype                     VARCHAR(200),
            age                          VARCHAR(20),
            sex                          VARCHAR(10),
            qty                          INT          NOT NULL,
            unit_price                   DECIMAL(14,2) NOT NULL,
            amount                       DECIMAL(14,2) NOT NULL,
            international_commercial     DECIMAL(14,2),
            china_distributor_commercial DECIMAL(14,2),
            created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_qi_quote (quotation_id),
            INDEX idx_qi_strain (strain)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS quotation_seq (
            quote_day   DATE    NOT NULL PRIMARY KEY,
            next_seq    INT     NOT NULL DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS price_library (
            id                           INT AUTO_INCREMENT PRIMARY KEY,
            customer_type                VARCHAR(20) NOT NULL,
            strain                       VARCHAR(50)  NOT NULL,
            strain_name                  VARCHAR(200),
            long_genotype                VARCHAR(200),
            age                          VARCHAR(20),
            sex                          VARCHAR(10),
            price                        DECIMAL(14,2),
            international_commercial     DECIMAL(14,2),
            china_distributor_commercial DECIMAL(14,2),
            npo_price                    DECIMAL(14,2),
            ka_price                     DECIMAL(14,2),
            created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_lookup (customer_type, strain, long_genotype, age, sex),
            INDEX idx_p_strain (strain)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS invoice_records (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            invoice_date    DATE,
            subject         TEXT,
            buyer           VARCHAR(200),
            amount          VARCHAR(50),
            filename        VARCHAR(255),
            filepath        TEXT,
            source          VARCHAR(20),
            folder          VARCHAR(100),
            status          VARCHAR(20) NOT NULL,
            reason          TEXT,
            email_uid       VARCHAR(100),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_i_date (invoice_date),
            INDEX idx_i_status (status),
            INDEX idx_i_buyer (buyer),
            INDEX idx_i_uid (email_uid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS system_logs (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            log_type    VARCHAR(20),
            message     TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_l_created (created_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS exchange_records (
            id                INT AUTO_INCREMENT PRIMARY KEY,
            exchange_no       VARCHAR(100) UNIQUE,
            customer          TEXT,
            exchange_date     TEXT,
            points_exchanged  INT,
            amount_exchanged  REAL,
            exchange_method   TEXT,
            exchange_product  TEXT,
            operator          TEXT,
            remark            TEXT,
            created_at        TEXT,
            updated_at        TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS customer_points_history (
            id                      INT AUTO_INCREMENT PRIMARY KEY,
            customer                TEXT,
            period                  TEXT,
            total_points_earned     INT,
            total_points_exchanged  INT,
            remaining_points        INT,
            created_at              TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS raw_data_backup (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            date        TEXT,
            order_no    TEXT,
            customer    TEXT,
            amount      REAL,
            amount_cny  REAL,
            product     TEXT,
            created_at  TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS inventory_items (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            item_code    VARCHAR(100)  NOT NULL UNIQUE,
            title        VARCHAR(200)  NOT NULL,
            category     VARCHAR(100),
            location     VARCHAR(200),
            quantity     INT            DEFAULT 0,
            extra_fields TEXT,
            is_active   TINYINT(1)     NOT NULL DEFAULT 1,
            created_at   TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_inv_code (item_code),
            INDEX idx_inv_category (category),
            INDEX idx_inv_location (location),
            INDEX idx_inv_title (title),
            INDEX idx_inv_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            item_id          INT            NOT NULL,
            transaction_type VARCHAR(20)    NOT NULL,
            quantity         INT            NOT NULL,
            remark           TEXT,
            operator         VARCHAR(100),
            stock_before     INT,
            stock_after      INT,
            created_at       TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_trans_item (item_id),
            INDEX idx_trans_type (transaction_type),
            INDEX idx_trans_created (created_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS inventory_fields (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            field_name  VARCHAR(100) NOT NULL UNIQUE,
            field_label VARCHAR(200),
            field_type  VARCHAR(20)  DEFAULT 'text',
            sort_order  INT          DEFAULT 0,
            created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS inventory_hidden_history_values (
            field_name  VARCHAR(20)  NOT NULL,
            value       VARCHAR(200) NOT NULL,
            created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (field_name, value)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                self._execute(stmt)
        self._ensure_inventory_migrations()

    def _ensure_inventory_migrations(self) -> None:
        migrations = (
            ("inventory_items", "is_active", "is_active TINYINT(1) NOT NULL DEFAULT 1"),
            ("inventory_items", "updated_at", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ("inventory_transactions", "stock_before", "stock_before INT"),
            ("inventory_transactions", "stock_after", "stock_after INT"),
        )
        for table_name, column_name, column_ddl in migrations:
            rows = self._execute(
                f"SHOW COLUMNS FROM {table_name} LIKE %s",
                (column_name,),
                fetch=True,
            )
            if not rows:
                self._execute(f"ALTER TABLE {table_name} ADD COLUMN {column_ddl}")

        indexes = (
            ("idx_inv_location", "location"),
            ("idx_inv_title", "title"),
            ("idx_inv_active", "is_active"),
        )
        for index_name, column_name in indexes:
            rows = self._execute(
                "SHOW INDEX FROM inventory_items WHERE Key_name=%s",
                (index_name,),
                fetch=True,
            )
            if not rows:
                self._execute(
                    f"CREATE INDEX {index_name} ON inventory_items({column_name})"
                )

    def add_log(self, log_type: str, message: str) -> bool:
        try:
            self._execute(
                "INSERT INTO system_logs (log_type, message) VALUES (%s, %s)",
                (log_type, message),
            )
            return True
        except Exception:
            return False

    def get_next_quote_number(self) -> str:
        """生成 CT-YYYYMMDD-NNN"""
        today = date.today()
        day_str = today.strftime("%Y%m%d")

        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    """INSERT INTO quotation_seq (quote_day, next_seq) VALUES (%s, 1)
                       ON DUPLICATE KEY UPDATE next_seq = next_seq + 1""",
                    (today,),
                )
                conn.commit()
                cur.execute("SELECT next_seq FROM quotation_seq WHERE quote_day = %s", (today,))
                row = cur.fetchone()
                seq = row["next_seq"] if row else 1
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

        return f"CT-{day_str}-{seq:03d}"

    def save_quotation(self, quotation_data: Dict) -> int:
        ci = quotation_data.get("customer_info", {})
        sm = quotation_data.get("summary", {})
        items = quotation_data.get("items", [])
        quote_number = quotation_data.get("quote_number", "")
        quote_date_str = quotation_data.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
        total_qty = sum(int(i.get("qty", 0)) for i in items)

        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    """INSERT INTO quotations
                        (quote_number, quote_date, customer_name, contact_person,
                         sales_person, customer_type, subtotal, shipping, service_fee,
                         discount, tax, grand_total, total_qty)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (quote_number, quote_date_str,
                     ci.get("customer_name", ""), ci.get("contact_person", ""),
                     ci.get("sales_person", ""), ci.get("customer_type", "commercial"),
                     sm.get("subtotal", 0), sm.get("shipping", 0),
                     sm.get("service_fee", 0), sm.get("discount", 0),
                     sm.get("tax", 0), sm.get("grand_total", 0), total_qty),
                )
                quotation_id = cur.lastrowid

                for seq, item in enumerate(items, 1):
                    cur.execute(
                        """INSERT INTO quotation_items
                            (quotation_id, seq, strain, strain_name, genotype,
                             age, sex, qty, unit_price, amount,
                             international_commercial, china_distributor_commercial)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (quotation_id, seq, item.get("strain", ""), item.get("name", ""),
                         item.get("genotype", ""), item.get("age", ""), item.get("sex", ""),
                         int(item.get("qty", 0)), float(item.get("unit_price", 0)),
                         float(item.get("amount", 0)),
                         float(item.get("international_commercial", 0)) if item.get("international_commercial") else None,
                         float(item.get("china_distributor_commercial", 0)) if item.get("china_distributor_commercial") else None),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

        self.add_log("INFO", f"保存报价单: {quote_number} (ID={quotation_id})")
        return quotation_id

    def get_quotation(self, quote_number: str) -> Optional[Dict]:
        result = self._execute(
            "SELECT * FROM quotations WHERE quote_number = %s", (quote_number,), fetch=True
        )
        if not result:
            return None
        main = result[0]
        main["items"] = self._execute(
            "SELECT * FROM quotation_items WHERE quotation_id = %s ORDER BY seq",
            (main["id"],), fetch=True,
        )
        return main

    def get_quotation_by_id(self, quote_id: int) -> Optional[Dict]:
        result = self._execute(
            "SELECT * FROM quotations WHERE id = %s", (quote_id,), fetch=True
        )
        if not result:
            return None
        main = result[0]
        main["items"] = self._execute(
            "SELECT * FROM quotation_items WHERE quotation_id = %s ORDER BY seq",
            (quote_id,), fetch=True,
        )
        return main

    def list_quotations(self, customer_name=None, customer_type=None,
                        date_from=None, date_to=None, limit=100, offset=0) -> List[Dict]:
        query = """SELECT q.*, COUNT(qi.id) AS items_count
                   FROM quotations q LEFT JOIN quotation_items qi ON qi.quotation_id = q.id
                   WHERE 1=1"""
        params = []
        if customer_name:
            query += " AND q.customer_name LIKE %s"
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
        query += " GROUP BY q.id ORDER BY q.quote_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self._execute(query, params, fetch=True)

    def delete_quotation(self, quote_id: int) -> bool:
        # MySQL 没有 ON DELETE CASCADE，手动删除
        self._execute("DELETE FROM quotation_items WHERE quotation_id = %s", (quote_id,))
        result = self._execute("DELETE FROM quotations WHERE id = %s", (quote_id,))
        return result > 0

    # ---------- 价格库 ----------
    def upsert_price_items(self, customer_type: str, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        count = 0
        for _, row in df.iterrows():
            self._execute(
                """INSERT INTO price_library
                    (customer_type, strain, strain_name, long_genotype,
                     age, sex, price, international_commercial,
                     china_distributor_commercial, npo_price, ka_price)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                    strain_name=VALUES(strain_name),
                    price=VALUES(price),
                    international_commercial=VALUES(international_commercial),
                    china_distributor_commercial=VALUES(china_distributor_commercial),
                    npo_price=VALUES(npo_price),
                    ka_price=VALUES(ka_price),
                    updated_at=CURRENT_TIMESTAMP""",
                (customer_type,
                 str(row.get("strain", "")), str(row.get("strain_name", "")),
                 str(row.get("long_genotype", "")), str(row.get("age", "")),
                 str(row.get("sex", "")),
                 float(row.get("price", 0)) if pd.notna(row.get("price")) else None,
                 float(row.get("international_commercial", 0)) if pd.notna(row.get("international_commercial")) else None,
                 float(row.get("china_distributor_commercial", 0)) if pd.notna(row.get("china_distributor_commercial")) else None,
                 float(row.get("npo_price", 0)) if pd.notna(row.get("npo_price")) else None,
                 float(row.get("ka_price", 0)) if pd.notna(row.get("ka_price")) else None),
            )
            count += 1
        self.add_log("INFO", f"价格库 upsert: {customer_type} {count} 条")
        return count

    def query_price(self, strain: str, long_genotype: str, age: str, sex: str,
                    customer_type: str = "commercial") -> Dict:
        from modules.price_normalizer import normalize_age, normalize_sex
        age_n = normalize_age(age)
        sex_n = normalize_sex(sex)
        price_key_map = {"commercial": "china_distributor_commercial", "npo": "npo_price", "ka": "ka_price"}
        price_col = price_key_map.get(customer_type, "price")

        rows = self._execute(
            """SELECT * FROM price_library
               WHERE customer_type = %s AND TRIM(strain) = %s
                 AND TRIM(long_genotype) = %s AND TRIM(age) = %s AND TRIM(sex) = %s""",
            (customer_type, strain.strip(), long_genotype.strip(), age_n, sex_n),
            fetch=True,
        )
        if len(rows) == 0:
            return {"error": "未找到对应价格", "found": False}
        if len(rows) > 1:
            return {"error": "价格库存在重复数据", "found": False, "count": len(rows)}
        row = rows[0]
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

    def is_price_loaded(self, customer_type: Optional[str] = None) -> bool:
        if customer_type:
            result = self._execute(
                "SELECT COUNT(*) as cnt FROM price_library WHERE customer_type = %s",
                (customer_type,), fetch=True,
            )
        else:
            result = self._execute("SELECT COUNT(*) as cnt FROM price_library", fetch=True)
        return result[0]["cnt"] > 0 if result else False

    def get_price_library_as_dataframe(self, customer_type: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        if customer_type:
            df = pd.read_sql(
                "SELECT * FROM price_library WHERE customer_type = %s",
                self._get_conn(), params=(customer_type,)
            )
            return {customer_type: df}
        else:
            df = pd.read_sql("SELECT * FROM price_library", self._get_conn())
            return {ct: group for ct, group in df.groupby("customer_type")}

    # ---------- 发票 ----------
    def add_invoice_record(self, record: Dict) -> int:
        result = self._execute(
            """INSERT INTO invoice_records
                (invoice_date, subject, buyer, amount, filename, filepath,
                 source, folder, status, reason, email_uid)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (record.get("date"), record.get("subject"), record.get("buyer"),
             str(record.get("amount", "")), record.get("filename"),
             record.get("filepath"), record.get("source"), record.get("folder"),
             record.get("status", "success"), record.get("reason"),
             record.get("email_uid")),
        )
        return result

    def get_invoice_records(self, date_from=None, date_to=None, status=None,
                            buyer=None, limit=100, offset=0) -> List[Dict]:
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
            query += " AND buyer LIKE %s"
            params.append(f"%{buyer}%")
        query += " ORDER BY invoice_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self._execute(query, params, fetch=True)

    def is_invoice_processed(self, email_uid: str) -> bool:
        if not email_uid:
            return False
        result = self._execute(
            "SELECT id FROM invoice_records WHERE email_uid = %s LIMIT 1",
            (email_uid,), fetch=True,
        )
        return len(result) > 0

    def get_processed_invoice_uids(self) -> set:
        rows = self._execute(
            "SELECT DISTINCT email_uid FROM invoice_records WHERE email_uid IS NOT NULL",
            fetch=True,
        )
        return {r["email_uid"] for r in rows}

    # ---------- 兼容旧 SQLite ----------
    def add_exchange_record(self, exchange_no, customer, exchange_date, points_exchanged,
                            amount_exchanged, exchange_method, exchange_product,
                            operator, remark="") -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._execute(
                """INSERT INTO exchange_records
                    (exchange_no, customer, exchange_date, points_exchanged,
                     amount_exchanged, exchange_method, exchange_product,
                     operator, remark, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                    customer=VALUES(customer), exchange_date=VALUES(exchange_date),
                    points_exchanged=VALUES(points_exchanged),
                    amount_exchanged=VALUES(amount_exchanged),
                    exchange_method=VALUES(exchange_method),
                    exchange_product=VALUES(exchange_product),
                    operator=VALUES(operator), remark=VALUES(remark),
                    updated_at=VALUES(updated_at)""",
                (exchange_no, customer, exchange_date, points_exchanged,
                 amount_exchanged, exchange_method, exchange_product,
                 operator, remark, now, now),
            )
            self.add_log("INFO", f"添加兑换记录: {exchange_no}")
            return True
        except Exception as e:
            self.add_log("ERROR", f"添加兑换记录失败: {str(e)}")
            return False

    def get_exchange_records(self) -> List[Dict]:
        return self._execute(
            "SELECT * FROM exchange_records ORDER BY exchange_date DESC", fetch=True
        )

    def save_customer_points_history(self, customer, period, total_points_earned,
                                     total_points_exchanged, remaining_points) -> bool:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._execute(
                """INSERT INTO customer_points_history
                    (customer, period, total_points_earned,
                     total_points_exchanged, remaining_points, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (customer, period, total_points_earned,
                 total_points_exchanged, remaining_points, now),
            )
            return True
        except Exception as e:
            self.add_log("ERROR", f"保存积分历史失败: {str(e)}")
            return False

    def get_customer_points_history(self, customer: Optional[str] = None) -> List[Dict]:
        if customer:
            return self._execute(
                "SELECT * FROM customer_points_history WHERE customer = %s ORDER BY period DESC",
                (customer,), fetch=True,
            )
        return self._execute(
            "SELECT * FROM customer_points_history ORDER BY period DESC", fetch=True
        )

    def sync_exchange_from_excel(self, df_exchange: pd.DataFrame) -> int:
        if df_exchange is None or df_exchange.empty:
            return 0
        count = 0
        for _, row in df_exchange.iterrows():
            exchange_no = str(row.get("兑换编号", ""))
            if exchange_no:
                if self.add_exchange_record(
                    exchange_no=exchange_no,
                    customer=str(row.get("客户", "")),
                    exchange_date=str(row.get("兑换日期", "")),
                    points_exchanged=int(row.get("兑换积分数量", 0)),
                    amount_exchanged=float(row.get("兑换金额", 0)),
                    exchange_method=str(row.get("兑换方式", "")),
                    exchange_product=str(row.get("兑换产品", "")),
                    operator=str(row.get("操作人员", "")),
                    remark=str(row.get("备注", "")),
                ):
                    count += 1
        return count

    # ---------- 库存管理 ----------
    def list_inventory_items(self) -> List[Dict]:
        return self._execute(
            "SELECT * FROM inventory_items ORDER BY id DESC", fetch=True
        )

    def add_inventory_item(self, item: Dict) -> int:
        extra = json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        item_id = self._execute(
            """INSERT INTO inventory_items
                (item_code, title, category, location, quantity, extra_fields)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (item.get("item_code", ""), item.get("title", ""),
             item.get("category", ""), item.get("location", ""),
             int(item.get("quantity", 0)), extra),
        )
        self._restore_inventory_history_values(item)
        return item_id

    def update_inventory_item(self, item_id: int, item: Dict) -> bool:
        extra = json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        self._execute(
            """UPDATE inventory_items SET
                item_code=%s, title=%s, category=%s, location=%s, extra_fields=%s
               WHERE id=%s""",
            (item.get("item_code", ""), item.get("title", ""),
             item.get("category", ""), item.get("location", ""), extra, item_id),
        )
        self._restore_inventory_history_values(item)
        return True

    def delete_inventory_item(self, item_id: int) -> bool:
        self._execute("DELETE FROM inventory_transactions WHERE item_id=%s", (item_id,))
        self._execute("DELETE FROM inventory_items WHERE id=%s", (item_id,))
        return True

    def inventory_transaction(self, item_id: int, txn_type: str, qty: int,
                              remark: str = "", operator: str = "") -> bool:
        if txn_type == "out":
            qty = -abs(qty)
        else:
            qty = abs(qty)
        self._execute(
            """INSERT INTO inventory_transactions
                (item_id, transaction_type, quantity, remark, operator)
               VALUES (%s, %s, %s, %s, %s)""",
            (item_id, txn_type, abs(qty), remark, operator),
        )
        self._execute(
            "UPDATE inventory_items SET quantity = quantity + %s WHERE id = %s",
            (qty, item_id),
        )
        return True

    def list_inventory_transactions(self, item_id: Optional[int] = None,
                                    limit: int = 100) -> List[Dict]:
        if item_id:
            sql = """SELECT t.*, i.item_code, i.title
                     FROM inventory_transactions t
                     LEFT JOIN inventory_items i ON t.item_id = i.id
                     WHERE t.item_id = %s
                     ORDER BY t.created_at DESC LIMIT %s"""
            return self._execute(sql, (item_id, limit), fetch=True)
        else:
            sql = """SELECT t.*, i.item_code, i.title
                     FROM inventory_transactions t
                     LEFT JOIN inventory_items i ON t.item_id = i.id
                     ORDER BY t.created_at DESC LIMIT %s"""
            return self._execute(sql, (limit,), fetch=True)

    def list_inventory_fields(self) -> List[Dict]:
        return self._execute(
            "SELECT * FROM inventory_fields ORDER BY sort_order, id", fetch=True
        )

    def add_inventory_field(self, field_name: str, field_label: str,
                            field_type: str = "text") -> bool:
        self._execute(
            """INSERT INTO inventory_fields (field_name, field_label, field_type)
               VALUES (%s, %s, %s)""",
            (field_name, field_label, field_type),
        )
        return True

    def delete_inventory_field(self, field_id: int) -> bool:
        self._execute("DELETE FROM inventory_fields WHERE id=%s", (field_id,))
        return True

    def get_distinct_categories(self) -> List[str]:
        return self.get_inventory_history_values("category")

    def get_distinct_locations(self) -> List[str]:
        return self.get_inventory_history_values("location")

    def get_inventory_item(self, item_id: int) -> Optional[Dict]:
        rows = self._execute(
            "SELECT * FROM inventory_items WHERE id=%s",
            (item_id,),
            fetch=True,
        )
        return rows[0] if rows else None

    def inventory_code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        if exclude_item_id is None:
            rows = self._execute(
                "SELECT 1 FROM inventory_items WHERE item_code=%s AND COALESCE(is_active, 1)=1 LIMIT 1",
                (item_code,),
                fetch=True,
            )
        else:
            rows = self._execute(
                "SELECT 1 FROM inventory_items WHERE item_code=%s AND id<>%s AND COALESCE(is_active, 1)=1 LIMIT 1",
                (item_code, exclude_item_id),
                fetch=True,
            )
        return bool(rows)

    def get_inventory_history_values(self, column: str) -> List[str]:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        self._ensure_inventory_history_table()
        rows = self._execute(
            f"""SELECT DISTINCT TRIM(i.{column}) AS value
                FROM inventory_items i
                WHERE i.{column} IS NOT NULL AND TRIM(i.{column}) != ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM inventory_hidden_history_values h
                      WHERE h.field_name=%s AND h.value=TRIM(i.{column})
                  )
                ORDER BY value""",
            (column,),
            fetch=True,
        )
        return [row["value"] for row in rows]

    def delete_inventory_history_value(self, column: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if column not in {"category", "location"}:
            raise ValueError(f"不支持的库存历史字段: {column}")
        if not normalized_value:
            return False
        self._ensure_inventory_history_table()
        self._execute(
            """INSERT INTO inventory_hidden_history_values (field_name, value)
               VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE created_at=CURRENT_TIMESTAMP""",
            (column, normalized_value),
        )
        return True

    def _restore_inventory_history_values(self, item: Dict) -> None:
        self._ensure_inventory_history_table()
        for column in ("category", "location"):
            value = str(item.get(column) or "").strip()
            if value:
                self._execute(
                    """DELETE FROM inventory_hidden_history_values
                       WHERE field_name=%s AND value=%s""",
                    (column, value),
                )

    def _ensure_inventory_history_table(self) -> None:
        self._execute(
            """CREATE TABLE IF NOT EXISTS inventory_hidden_history_values (
                field_name VARCHAR(20) NOT NULL,
                value VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (field_name, value)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        )

    def get_inventory_titles_by_category(self, category: str) -> List[str]:
        rows = self._execute(
            """SELECT DISTINCT TRIM(title) AS value
               FROM inventory_items
               WHERE title IS NOT NULL AND TRIM(title) != ''
                 AND TRIM(category) = %s
               ORDER BY value""",
            (category,),
            fetch=True,
        )
        return [row["value"] for row in rows]

    def clear_inventory_history_value(self, column: str, value: str) -> None:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        self._execute(
            f"UPDATE inventory_items SET {column} = NULL WHERE TRIM({column}) = %s",
            (value,),
        )

    def count_inventory_transactions(self, item_id: int) -> int:
        rows = self._execute(
            "SELECT COUNT(*) AS count FROM inventory_transactions WHERE item_id=%s",
            (item_id,),
            fetch=True,
        )
        return int(rows[0]["count"] if rows else 0)

    def set_inventory_item_active(self, item_id: int, is_active: bool) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE inventory_items SET is_active=%s WHERE id=%s",
                    (1 if is_active else 0, item_id),
                )
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def delete_inventory_item_without_history(self, item_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT id FROM inventory_transactions WHERE item_id=%s LIMIT 1 FOR UPDATE",
                    (item_id,),
                )
                if cur.fetchone():
                    conn.rollback()
                    return False
                cur.execute("DELETE FROM inventory_items WHERE id=%s", (item_id,))
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

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

        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT id, quantity, is_active FROM inventory_items WHERE id=%s FOR UPDATE",
                    (item_id,),
                )
                item = cur.fetchone()
                if not item:
                    raise ItemNotFoundError("库存物品不存在")
                if not int(item.get("is_active", 1)):
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
                    "UPDATE inventory_items SET quantity=%s WHERE id=%s",
                    (stock_after, item_id),
                )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()


# ============================================================
# PostgreSQL 实现（保留兼容性）
# ============================================================
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.pool import SimpleConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class _PostgresManager(_BaseManager):
    """PostgreSQL 数据库管理器（兼容）"""

    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 5):
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 未安装")
        self.dsn = dsn
        self._pool = SimpleConnectionPool(minconn, maxconn, dsn)

    @classmethod
    def from_secrets(cls) -> "_PostgresManager":
        import streamlit as st
        return cls(postgres_dsn_from_secrets(st.secrets))

    @contextmanager
    def _conn(self):
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
                # 第零步：预检——先确保关键表的列存在（防止后续 DDL 引用不存在的列）
                self._preflight_migration(cur)

                from modules.pg_database import _SCHEMA_STATEMENTS
                for statement in _SCHEMA_STATEMENTS:
                    try:
                        cur.execute(statement)
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "already exists" in err_msg or "already been taken" in err_msg:
                            continue
                        # 如果是列不存在，尝试预检迁移后重试
                        if "column" in err_msg and "does not exist" in err_msg:
                            self._preflight_migration(cur)
                            # 重试当前语句
                            cur.execute(statement)
                            continue
                        raise
                self._ensure_inventory_columns(cur)
        finally:
            self._pool.putconn(conn)

    def _preflight_migration(self, cur) -> None:
        """预检迁移：在任何 DDL 之前先补上缺失的列"""
        column_checks = [
            ("inventory_items", "is_active",
             "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"),
            ("inventory_items", "updated_at",
             "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("inventory_transactions", "stock_before",
             "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_before INTEGER"),
            ("inventory_transactions", "stock_after",
             "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_after INTEGER"),
        ]
        for table, column, sql in column_checks:
            try:
                cur.execute(sql)
            except Exception:
                pass

    def _force_migration(self) -> None:
        """强制迁移：添加缺失的列"""
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                self._preflight_migration(cur)
        finally:
            self._pool.putconn(conn)

    def _ensure_inventory_columns(self, cur) -> None:
        """确保库存表有必要的列（兼容旧表结构）"""
        migrations = [
            "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_before INTEGER",
            "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS stock_after INTEGER",
        ]
        for sql in migrations:
            try:
                cur.execute(sql)
            except Exception as e:
                err_msg = str(e).lower()
                if "already exists" in err_msg or "already been taken" in err_msg:
                    continue
                if 'relation' in err_msg and 'does not exist' in err_msg:
                    continue
                raise

    def ping(self) -> bool:
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def ping_with_detail(self) -> Dict:
        """带详细错误信息的连接测试"""
        result = {"success": False, "message": "", "details": {}}
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS test")
                    row = cur.fetchone()
                    result["details"]["query_result"] = str(row)
            result["success"] = True
            result["message"] = "连接成功"
            result["details"]["dsn_preview"] = self.dsn[:100] + "..." if len(self.dsn) > 100 else self.dsn
            return result
        except Exception as e:
            result["message"] = f"{type(e).__name__}: {e}"
            result["details"]["exception_type"] = type(e).__name__
            if hasattr(e, 'pgcode'):
                result["details"]["pgcode"] = e.pgcode
            if hasattr(e, 'pgerror'):
                result["details"]["pgerror"] = str(e.pgerror)
            # 分析常见错误
            error_str = str(e).lower()
            if "timeout" in error_str:
                result["details"]["possible_cause"] = "连接超时，请检查网络或防火墙"
            elif "password" in error_str:
                result["details"]["possible_cause"] = "密码错误"
            elif "role" in error_str or "user" in error_str:
                result["details"]["possible_cause"] = "用户名或角色不存在"
            elif "database" in error_str and "does not exist" in error_str:
                result["details"]["possible_cause"] = "数据库不存在"
            elif "ssl" in error_str:
                result["details"]["possible_cause"] = "SSL 连接失败"
            elif "connection refused" in error_str:
                result["details"]["possible_cause"] = "连接被拒绝，请检查主机和端口"
            return result

    def get_connection_status(self) -> Dict:
        """获取当前连接状态"""
        status = {
            "db_type": "PostgreSQL",
            "pool_closed": self._pool.closed if hasattr(self._pool, 'closed') else False,
            "connection_info": getattr(self, '_connection_info', {}),
        }
        if hasattr(self._pool, '_pool'):
            pool_size = len(self._pool._pool) if self._pool._pool else 0
            status["pool_size"] = pool_size
        return status

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

    def _get_pg_mgr(self):
        """获取共享连接池的 PgDatabaseManager"""
        from modules.pg_database import PgDatabaseManager
        return PgDatabaseManager(self.dsn, pool=self._pool)

    def get_next_quote_number(self) -> str:
        from modules.pg_database import PgDatabaseManager
        # 委托给 PgDatabaseManager 的实现（共享连接池）
        mgr = self._get_pg_mgr()
        return mgr.get_next_quote_number()

    def save_quotation(self, quotation_data: Dict) -> int:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.save_quotation(quotation_data)

    def get_quotation(self, quote_number: str) -> Optional[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_quotation(quote_number)

    def get_quotation_by_id(self, quote_id: int) -> Optional[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM quotations WHERE id = %s", (quote_id,))
                main = cur.fetchone()
                if not main:
                    return None
                main = dict(main)
                cur.execute(
                    "SELECT * FROM quotation_items WHERE quotation_id = %s ORDER BY seq",
                    (quote_id,),
                )
                main["items"] = [dict(r) for r in cur.fetchall()]
                return main

    def list_quotations(self, customer_name=None, customer_type=None,
                        date_from=None, date_to=None, limit=100, offset=0) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.list_quotations(
            customer_name=customer_name, customer_type=customer_type,
            date_from=date_from, date_to=date_to, limit=limit, offset=offset,
        )

    def delete_quotation(self, quote_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quotations WHERE id = %s", (quote_id,))
                return cur.rowcount > 0

    def upsert_price_items(self, customer_type: str, df: pd.DataFrame) -> int:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.upsert_price_items(customer_type, df)

    def query_price(self, strain: str, long_genotype: str, age: str, sex: str,
                    customer_type: str = "commercial") -> Dict:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.query_price(strain, long_genotype, age, sex, customer_type)

    def is_price_loaded(self, customer_type: Optional[str] = None) -> bool:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.is_price_loaded(customer_type)

    def get_price_library_as_dataframe(self, customer_type: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_price_library_as_dataframe(customer_type)

    def add_invoice_record(self, record: Dict) -> int:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.add_invoice_record(record)

    def get_invoice_records(self, **kwargs) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_invoice_records(**kwargs)

    def is_invoice_processed(self, email_uid: str) -> bool:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.is_invoice_processed(email_uid)

    def get_processed_invoice_uids(self) -> set:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_processed_invoice_uids()

    def add_exchange_record(self, *args, **kwargs) -> bool:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.add_exchange_record(*args, **kwargs)

    def get_exchange_records(self) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_exchange_records()

    def save_customer_points_history(self, *args, **kwargs) -> bool:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.save_customer_points_history(*args, **kwargs)

    def get_customer_points_history(self, customer=None) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.get_customer_points_history(customer)

    def sync_exchange_from_excel(self, df_exchange: pd.DataFrame) -> int:
        from modules.pg_database import PgDatabaseManager
        mgr = self._get_pg_mgr()
        return mgr.sync_exchange_from_excel(df_exchange)

    # ---------- 库存管理 ----------
    def list_inventory_items(self) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().list_inventory_items()

    def add_inventory_item(self, item: Dict) -> int:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().add_inventory_item(item)

    def update_inventory_item(self, item_id: int, item: Dict) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().update_inventory_item(item_id, item)

    def delete_inventory_item(self, item_id: int) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().delete_inventory_item(item_id)

    def inventory_transaction(self, item_id: int, txn_type: str, qty: int,
                              remark: str = "", operator: str = "") -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().inventory_transaction(item_id, txn_type, qty, remark, operator)

    def list_inventory_transactions(self, item_id: Optional[int] = None,
                                    limit: int = 100) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().list_inventory_transactions(item_id, limit)

    def list_inventory_fields(self) -> List[Dict]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().list_inventory_fields()

    def add_inventory_field(self, field_name: str, field_label: str,
                            field_type: str = "text") -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().add_inventory_field(field_name, field_label, field_type)

    def delete_inventory_field(self, field_id: int) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().delete_inventory_field(field_id)

    def get_distinct_categories(self) -> List[str]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().get_distinct_categories()

    def get_distinct_locations(self) -> List[str]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().get_distinct_locations()

    def get_inventory_item(self, item_id: int) -> Optional[Dict]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().get_inventory_item(item_id)

    def inventory_code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        return self._get_pg_mgr().inventory_code_exists(item_code, exclude_item_id)

    def get_inventory_history_values(self, column: str) -> List[str]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().get_inventory_history_values(column)

    def get_inventory_titles_by_category(self, category: str) -> List[str]:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().get_inventory_titles_by_category(category)

    def clear_inventory_history_value(self, column: str, value: str) -> None:
        from modules.pg_database import PgDatabaseManager
        self._get_pg_mgr().clear_inventory_history_value(column, value)

    def delete_inventory_history_value(self, column: str, value: str) -> bool:
        return self._get_pg_mgr().delete_inventory_history_value(column, value)

    def count_inventory_transactions(self, item_id: int) -> int:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().count_inventory_transactions(item_id)

    def set_inventory_item_active(self, item_id: int, is_active: bool) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().set_inventory_item_active(item_id, is_active)

    def delete_inventory_item_without_history(self, item_id: int) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().delete_inventory_item_without_history(item_id)

    def inventory_transaction_atomic(
        self,
        item_id: int,
        txn_type: str,
        qty: int,
        remark: str = "",
        operator: str = "",
    ) -> bool:
        from modules.pg_database import PgDatabaseManager
        return self._get_pg_mgr().inventory_transaction_atomic(
            item_id,
            txn_type,
            qty,
            remark,
            operator,
        )


# ============================================================
# SQLite 降级实现
# ============================================================
class _SQLiteManager(_BaseManager):
    """SQLite 降级管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def init_schema(self) -> None:
        from modules.database import DatabaseManager
        # 使用现有 DatabaseManager 创建表
        DatabaseManager(self.db_path)

    def ping(self) -> bool:
        try:
            conn = self._get_conn()
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False

    def get_connection_status(self) -> Dict:
        """获取当前连接状态"""
        return {
            "db_type": "SQLite (降级模式)",
            "db_path": self.db_path,
            "file_exists": os.path.exists(self.db_path),
            "file_size_mb": round(os.path.getsize(self.db_path) / 1024 / 1024, 2) if os.path.exists(self.db_path) else 0,
            "connection_info": getattr(self, '_connection_info', {}),
        }

    def add_log(self, log_type: str, message: str) -> bool:
        try:
            conn = self._get_conn()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS system_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_type TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "INSERT INTO system_logs (log_type, message) VALUES (?, ?)",
                (log_type, message),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_next_quote_number(self) -> str:
        # 降级：扫描本地目录
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        existing = [f for f in os.listdir(export_dir) if f.startswith(f"CT-{date_str}")]
        if not existing:
            seq = 1
        else:
            seq = max(int(f.split("-")[-1].replace(".xlsx", "").replace(".pdf", "")) for f in existing) + 1
        return f"CT-{date_str}-{seq:03d}"

    def save_quotation(self, quotation_data: Dict) -> int:
        # SQLite 降级：不保存，仅返回模拟ID
        quote_number = quotation_data.get("quote_number", "")
        self.add_log("INFO", f"SQLite降级模式 - 报价单 {quote_number} 仅保存到内存")
        return 0

    def get_quotation(self, quote_number: str) -> Optional[Dict]:
        return None

    def get_quotation_by_id(self, quote_id: int) -> Optional[Dict]:
        return None

    def list_quotations(self, **kwargs) -> List[Dict]:
        return []

    def delete_quotation(self, quote_id: int) -> bool:
        return False

    def upsert_price_items(self, customer_type: str, df: pd.DataFrame) -> int:
        # SQLite 降级：保存为CSV
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "price_library")
        os.makedirs(export_dir, exist_ok=True)
        if df is not None and not df.empty:
            df.to_csv(os.path.join(export_dir, f"{customer_type}_price.csv"), index=False)
            return len(df)
        return 0

    def query_price(self, strain: str, long_genotype: str, age: str, sex: str,
                    customer_type: str = "commercial") -> Dict:
        # SQLite 降级：不支持数据库查询
        return {"error": "SQLite降级模式不支持数据库查询", "found": False}

    def is_price_loaded(self, customer_type: Optional[str] = None) -> bool:
        return False

    def get_price_library_as_dataframe(self, customer_type: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        return {}

    def add_invoice_record(self, record: Dict) -> int:
        self.add_log("INFO", f"SQLite降级 - 发票记录仅保存到内存: {record.get('filename', '')}")
        return 0

    def get_invoice_records(self, **kwargs) -> List[Dict]:
        return []

    def is_invoice_processed(self, email_uid: str) -> bool:
        return False

    def get_processed_invoice_uids(self) -> set:
        return set()

    def add_exchange_record(self, *args, **kwargs) -> bool:
        from modules.database import DatabaseManager
        mgr = DatabaseManager(self.db_path)
        return mgr.add_exchange_record(*args, **kwargs)

    def get_exchange_records(self) -> List[Dict]:
        from modules.database import DatabaseManager
        mgr = DatabaseManager(self.db_path)
        return mgr.get_exchange_records()

    def save_customer_points_history(self, *args, **kwargs) -> bool:
        from modules.database import DatabaseManager
        mgr = DatabaseManager(self.db_path)
        return mgr.save_customer_points_history(*args, **kwargs)

    def get_customer_points_history(self, customer=None) -> List[Dict]:
        from modules.database import DatabaseManager
        mgr = DatabaseManager(self.db_path)
        return mgr.get_customer_points_history(customer)

    def sync_exchange_from_excel(self, df_exchange: pd.DataFrame) -> int:
        from modules.database import DatabaseManager
        mgr = DatabaseManager(self.db_path)
        return mgr.sync_exchange_from_excel(df_exchange)

    # ---------- 库存管理（SQLite降级） ----------
    def _inv_ensure_tables(self):
        conn = self._get_conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            category TEXT,
            location TEXT,
            quantity INTEGER DEFAULT 0,
            extra_fields TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            remark TEXT,
            operator TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL UNIQUE,
            field_label TEXT,
            field_type TEXT DEFAULT 'text',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory_hidden_history_values (
            field_name TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (field_name, value)
        )""")
        item_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(inventory_items)").fetchall()
        }
        if "is_active" not in item_columns:
            conn.execute(
                "ALTER TABLE inventory_items ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )
        if "updated_at" not in item_columns:
            conn.execute(
                "ALTER TABLE inventory_items ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP"
            )

        transaction_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(inventory_transactions)").fetchall()
        }
        if "stock_before" not in transaction_columns:
            conn.execute(
                "ALTER TABLE inventory_transactions ADD COLUMN stock_before INTEGER"
            )
        if "stock_after" not in transaction_columns:
            conn.execute(
                "ALTER TABLE inventory_transactions ADD COLUMN stock_after INTEGER"
            )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventory_active ON inventory_items(is_active)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventory_title ON inventory_items(title)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory_items(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory_items(location)"
        )
        conn.commit()
        conn.close()

    def list_inventory_items(self) -> List[Dict]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM inventory_items ORDER BY id DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_inventory_item(self, item: Dict) -> int:
        self._inv_ensure_tables()
        extra = json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO inventory_items (item_code, title, category, location, quantity, extra_fields) VALUES (?, ?, ?, ?, ?, ?)",
            (item.get("item_code", ""), item.get("title", ""),
             item.get("category", ""), item.get("location", ""),
             int(item.get("quantity", 0)), extra),
        )
        self._inv_restore_history_values(conn, item)
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def update_inventory_item(self, item_id: int, item: Dict) -> bool:
        self._inv_ensure_tables()
        extra = json.dumps(item.get("extra_fields", {}), ensure_ascii=False)
        conn = self._get_conn()
        conn.execute(
            """UPDATE inventory_items SET
                item_code=?, title=?, category=?, location=?, extra_fields=?,
                updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (item.get("item_code", ""), item.get("title", ""),
             item.get("category", ""), item.get("location", ""), extra, item_id),
        )
        self._inv_restore_history_values(conn, item)
        conn.commit()
        conn.close()
        return True

    def delete_inventory_item(self, item_id: int) -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.execute("DELETE FROM inventory_transactions WHERE item_id=?", (item_id,))
        conn.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        return True

    def inventory_transaction(self, item_id: int, txn_type: str, qty: int,
                              remark: str = "", operator: str = "") -> bool:
        self._inv_ensure_tables()
        delta = -abs(qty) if txn_type == "out" else abs(qty)
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO inventory_transactions (item_id, transaction_type, quantity, remark, operator) VALUES (?, ?, ?, ?, ?)",
            (item_id, txn_type, abs(qty), remark, operator),
        )
        conn.execute(
            "UPDATE inventory_items SET quantity = quantity + ? WHERE id = ?",
            (delta, item_id),
        )
        conn.commit()
        conn.close()
        return True

    def list_inventory_transactions(self, item_id: Optional[int] = None,
                                    limit: int = 100) -> List[Dict]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        if item_id:
            rows = conn.execute(
                """SELECT t.*, i.item_code, i.title
                   FROM inventory_transactions t
                   LEFT JOIN inventory_items i ON t.item_id = i.id
                   WHERE t.item_id = ?
                   ORDER BY t.created_at DESC LIMIT ?""",
                (item_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT t.*, i.item_code, i.title
                   FROM inventory_transactions t
                   LEFT JOIN inventory_items i ON t.item_id = i.id
                   ORDER BY t.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_inventory_fields(self) -> List[Dict]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM inventory_fields ORDER BY sort_order, id").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_inventory_field(self, field_name: str, field_label: str,
                            field_type: str = "text") -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO inventory_fields (field_name, field_label, field_type) VALUES (?, ?, ?)",
            (field_name, field_label, field_type),
        )
        conn.commit()
        conn.close()
        return True

    def delete_inventory_field(self, field_id: int) -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.execute("DELETE FROM inventory_fields WHERE id=?", (field_id,))
        conn.commit()
        conn.close()
        return True

    def get_distinct_categories(self) -> List[str]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        cur = conn.execute(
            "SELECT DISTINCT category FROM inventory_items WHERE category IS NOT NULL AND category != '' ORDER BY category"
        )
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_distinct_locations(self) -> List[str]:
        return self.get_inventory_history_values("location")

    def get_inventory_item(self, item_id: int) -> Optional[Dict]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM inventory_items WHERE id=?",
            (item_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def inventory_code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        if exclude_item_id is None:
            row = conn.execute(
                "SELECT 1 FROM inventory_items WHERE item_code=? AND COALESCE(is_active, 1)=1 LIMIT 1",
                (item_code,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM inventory_items WHERE item_code=? AND id<>? AND COALESCE(is_active, 1)=1 LIMIT 1",
                (item_code, exclude_item_id),
            ).fetchone()
        conn.close()
        return row is not None

    def get_inventory_history_values(self, column: str) -> List[str]:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        self._inv_ensure_tables()
        conn = self._get_conn()
        rows = conn.execute(
            f"""SELECT DISTINCT TRIM(i.{column})
                FROM inventory_items i
                WHERE i.{column} IS NOT NULL AND TRIM(i.{column}) != ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM inventory_hidden_history_values h
                      WHERE h.field_name=? AND h.value=TRIM(i.{column})
                  )
                ORDER BY TRIM(i.{column})""",
            (column,),
        ).fetchall()
        conn.close()
        return [row[0] for row in rows]

    def delete_inventory_history_value(self, column: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if column not in {"category", "location"}:
            raise ValueError(f"不支持的库存历史字段: {column}")
        if not normalized_value:
            return False
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO inventory_hidden_history_values (field_name, value)
               VALUES (?, ?)""",
            (column, normalized_value),
        )
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def _inv_restore_history_values(conn, item: Dict) -> None:
        for column in ("category", "location"):
            value = str(item.get(column) or "").strip()
            if value:
                conn.execute(
                    """DELETE FROM inventory_hidden_history_values
                       WHERE field_name=? AND value=?""",
                    (column, value),
                )

    def get_inventory_titles_by_category(self, category: str) -> List[str]:
        self._inv_ensure_tables()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT DISTINCT TRIM(title)
               FROM inventory_items
               WHERE title IS NOT NULL AND TRIM(title) != ''
                 AND TRIM(category) = ?
               ORDER BY TRIM(title)""",
            (category,),
        ).fetchall()
        conn.close()
        return [row[0] for row in rows]

    def clear_inventory_history_value(self, column: str, value: str) -> None:
        allowed_columns = {"title", "category", "location"}
        if column not in allowed_columns:
            raise ValueError(f"不支持的库存历史字段: {column}")
        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.execute(
            f"UPDATE inventory_items SET {column} = NULL WHERE TRIM({column}) = ?",
            (value,),
        )
        conn.commit()
        conn.close()

    def count_inventory_transactions(self, item_id: int) -> int:
        self._inv_ensure_tables()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE item_id=?",
            (item_id,),
        ).fetchone()
        conn.close()
        return int(row[0])

    def set_inventory_item_active(self, item_id: int, is_active: bool) -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        cur = conn.execute(
            """UPDATE inventory_items
               SET is_active=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (1 if is_active else 0, item_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def delete_inventory_item_without_history(self, item_id: int) -> bool:
        self._inv_ensure_tables()
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            history_count = conn.execute(
                "SELECT COUNT(*) FROM inventory_transactions WHERE item_id=?",
                (item_id,),
            ).fetchone()[0]
            if history_count:
                conn.rollback()
                return False
            cur = conn.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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

        self._inv_ensure_tables()
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            item = conn.execute(
                "SELECT id, quantity, is_active FROM inventory_items WHERE id=?",
                (item_id,),
            ).fetchone()
            if not item:
                raise ItemNotFoundError("库存物品不存在")
            if not int(item["is_active"]):
                raise ItemArchivedError("该物品已归档，不能继续出入库")

            stock_before = int(item["quantity"] or 0)
            if txn_type == "out" and quantity > stock_before:
                raise InsufficientStockError(
                    f"当前库存为{stock_before}，本次最多可出库{stock_before}"
                )
            stock_after = stock_before + quantity if txn_type == "in" else stock_before - quantity

            conn.execute(
                """INSERT INTO inventory_transactions
                    (item_id, transaction_type, quantity, remark, operator, stock_before, stock_after)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    txn_type,
                    quantity,
                    remark,
                    operator,
                    stock_before,
                    stock_after,
                ),
            )
            conn.execute(
                """UPDATE inventory_items
                   SET quantity=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (stock_after, item_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
