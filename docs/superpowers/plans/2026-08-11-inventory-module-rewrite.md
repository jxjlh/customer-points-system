# Inventory Module Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic inventory implementation with a modular, tested inventory subsystem that preserves existing data, supports reusable searchable values, prevents duplicate codes and negative stock, and archives items with history.

**Architecture:** Pure domain helpers and an `InventoryService` contain validation and business rules. An `InventoryRepositoryAdapter` delegates persistence to the configured MySQL, PostgreSQL, or SQLite manager. Streamlit rendering moves to `modules/inventory/ui.py`, leaving `app.py` with a single entry call.

**Tech Stack:** Python 3, Streamlit >=1.36, standard-library `unittest`, SQLite integration tests, existing MySQL/PostgreSQL drivers.

## Global Constraints

- Preserve all existing inventory items, transactions, and custom fields.
- Keep item codes manually entered and unique.
- Make `title`, category, and location searchable from historical values and allow new values.
- Reject outbound quantities greater than current stock.
- Archive items with transactions; hard-delete only items without transactions.
- Do not modify non-inventory product behavior.
- Do not commit or push until the user explicitly requests it.

---

### Task 1: Domain Values And Errors

**Files:**
- Create: `modules/inventory/__init__.py`
- Create: `modules/inventory/errors.py`
- Create: `modules/inventory/field_values.py`
- Create: `tests/__init__.py`
- Create: `tests/test_inventory_field_values.py`

**Interfaces:**
- Produces: `normalize_options(values, current_value="") -> list[str]`
- Produces: `resolve_reusable_value(selected_value, new_value, required=False, field_label="字段") -> str`
- Produces: `InventoryError`, `ValidationError`, `DuplicateItemCodeError`, `InsufficientStockError`, `ItemNotFoundError`, `ItemArchivedError`, `DeleteRestrictedError`

- [ ] **Step 1: Write failing field-value tests**

```python
import unittest

from modules.inventory.errors import ValidationError
from modules.inventory.field_values import normalize_options, resolve_reusable_value


class InventoryFieldValueTests(unittest.TestCase):
    def test_normalize_options_strips_deduplicates_and_sorts(self):
        self.assertEqual(normalize_options([" B ", "A", "", None, "A"]), ["A", "B"])

    def test_current_value_is_preserved_for_editing(self):
        self.assertEqual(normalize_options(["A"], current_value="旧位置"), ["A", "旧位置"])

    def test_new_value_overrides_selected_history(self):
        self.assertEqual(resolve_reusable_value("已有值", " 新值 "), "新值")

    def test_selected_history_is_used_when_new_value_is_empty(self):
        self.assertEqual(resolve_reusable_value("已有值", "  "), "已有值")

    def test_required_value_rejects_empty_result(self):
        with self.assertRaisesRegex(ValidationError, "title不能为空"):
            resolve_reusable_value("", "", required=True, field_label="title")
```

- [ ] **Step 2: Run tests and verify missing-module failure**

Run: `python -m unittest tests.test_inventory_field_values -v`

Expected: import failure because `modules.inventory` does not exist.

- [ ] **Step 3: Implement errors and value helpers**

```python
def normalize_options(values, current_value=""):
    cleaned = {str(value).strip() for value in values if value is not None and str(value).strip()}
    current = str(current_value or "").strip()
    if current:
        cleaned.add(current)
    return sorted(cleaned, key=lambda value: value.casefold())


def resolve_reusable_value(selected_value, new_value, required=False, field_label="字段"):
    resolved = str(new_value or "").strip() or str(selected_value or "").strip()
    if required and not resolved:
        raise ValidationError(f"{field_label}不能为空")
    return resolved
```

- [ ] **Step 4: Run field-value tests**

Run: `python -m unittest tests.test_inventory_field_values -v`

Expected: all tests pass.

---

### Task 2: Repository Contract And SQLite Migration

**Files:**
- Create: `modules/inventory/repository.py`
- Modify: `modules/db_manager.py`
- Test: `tests/test_inventory_repository.py`

**Interfaces:**
- Produces: `InventoryRepositoryAdapter(manager)`
- Manager methods added: `get_inventory_item(item_id)`, `inventory_code_exists(item_code, exclude_item_id=None)`, `get_inventory_history_values(column)`, `count_inventory_transactions(item_id)`, `set_inventory_item_active(item_id, is_active)`, `delete_inventory_item_without_history(item_id)`, `inventory_transaction_atomic(item_id, txn_type, quantity, remark, operator)`

- [ ] **Step 1: Write failing SQLite migration and persistence tests**

```python
import tempfile
import unittest
from pathlib import Path

from modules.db_manager import _SQLiteManager


class InventoryRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = _SQLiteManager(str(Path(self.temp_dir.name) / "inventory.db"))
        self.manager.init_schema()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_existing_schema_is_extended_idempotently(self):
        self.manager.init_schema()
        item_id = self.manager.add_inventory_item({
            "item_code": "M-001", "title": "模型", "category": "小鼠", "location": "A1", "quantity": 0,
        })
        item = self.manager.get_inventory_item(item_id)
        self.assertEqual(item["is_active"], 1)

    def test_saved_values_are_returned_as_history(self):
        self.manager.add_inventory_item({
            "item_code": "M-002", "title": "模型B", "category": "实验鼠", "location": "B2", "quantity": 0,
        })
        self.assertEqual(self.manager.get_inventory_history_values("title"), ["模型B"])
        self.assertEqual(self.manager.get_inventory_history_values("category"), ["实验鼠"])
        self.assertEqual(self.manager.get_inventory_history_values("location"), ["B2"])
```

- [ ] **Step 2: Run repository tests and verify missing-method failure**

Run: `python -m unittest tests.test_inventory_repository -v`

Expected: failure because the new manager methods and migration columns do not exist.

- [ ] **Step 3: Add base-manager method declarations and SQLite migrations**

Use `PRAGMA table_info` to add missing columns safely:

```python
def _ensure_column(conn, table_name, column_name, ddl):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")
```

Add `is_active INTEGER NOT NULL DEFAULT 1`, `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`, `stock_before INTEGER`, and `stock_after INTEGER`.

- [ ] **Step 4: Implement SQLite repository methods and adapter**

Restrict `get_inventory_history_values` to the allowlist `{"title", "category", "location"}` before interpolating a column name.

Implement atomic inventory changes with `BEGIN IMMEDIATE`, item lookup, outbound stock validation, record insert with stock snapshots, item update, commit, and rollback on error.

- [ ] **Step 5: Run repository tests**

Run: `python -m unittest tests.test_inventory_repository -v`

Expected: all tests pass.

---

### Task 3: Inventory Service Rules

**Files:**
- Create: `modules/inventory/service.py`
- Test: `tests/test_inventory_service.py`

**Interfaces:**
- Produces: `InventoryService(repository)`
- Produces: `create_item(data, operator="") -> int`
- Produces: `update_item(item_id, data) -> None`
- Produces: `change_stock(item_id, transaction_type, quantity, remark="", operator="") -> None`
- Produces: `archive_or_delete(item_id) -> str`
- Produces: `restore_item(item_id) -> None`
- Produces: `history_options() -> dict[str, list[str]]`

- [ ] **Step 1: Write failing service tests with an in-memory fake repository**

Cover:

```python
def test_create_rejects_duplicate_manual_code(self): ...
def test_create_uses_new_reusable_values(self): ...
def test_outbound_rejects_quantity_above_current_stock(self): ...
def test_item_with_history_is_archived(self): ...
def test_item_without_history_is_deleted(self): ...
```

Assertions must use the public service API and inspect fake-repository state.

- [ ] **Step 2: Run service tests and verify missing-service failure**

Run: `python -m unittest tests.test_inventory_service -v`

Expected: import failure for `InventoryService`.

- [ ] **Step 3: Implement minimal service rules**

```python
class InventoryService:
    def create_item(self, data, operator=""):
        item_code = str(data.get("item_code") or "").strip()
        if not item_code:
            raise ValidationError("编号不能为空")
        if self.repository.code_exists(item_code):
            raise DuplicateItemCodeError("编号已存在，请输入其他编号")
        title = resolve_reusable_value(data.get("title_selected"), data.get("title_new"), True, "title")
        category = resolve_reusable_value(data.get("category_selected"), data.get("category_new"))
        location = resolve_reusable_value(data.get("location_selected"), data.get("location_new"))
        return self.repository.create_item({...})
```

Map low-level uniqueness exceptions to `DuplicateItemCodeError` as a race-condition fallback.

- [ ] **Step 4: Run service tests**

Run: `python -m unittest tests.test_inventory_service -v`

Expected: all tests pass.

---

### Task 4: MySQL And PostgreSQL Parity

**Files:**
- Modify: `modules/db_manager.py`
- Modify: `modules/pg_database.py`
- Test: `tests/test_inventory_manager_contract.py`

**Interfaces:**
- All configured managers expose the method set consumed by `InventoryRepositoryAdapter`.

- [ ] **Step 1: Write failing manager-contract tests**

```python
REQUIRED_METHODS = {
    "get_inventory_item",
    "inventory_code_exists",
    "get_inventory_history_values",
    "count_inventory_transactions",
    "set_inventory_item_active",
    "delete_inventory_item_without_history",
    "inventory_transaction_atomic",
}
```

Assert the base manager and MySQL, PostgreSQL wrapper, SQLite, and `PgDatabaseManager` classes define every required callable.

- [ ] **Step 2: Run contract tests and verify failures**

Run: `python -m unittest tests.test_inventory_manager_contract -v`

Expected: missing methods on non-SQLite managers.

- [ ] **Step 3: Implement MySQL migrations and atomic operations**

Use `SHOW COLUMNS` before `ALTER TABLE`, lock the selected item row with `SELECT ... FOR UPDATE`, validate stock, insert the snapshot record, and update quantity in one transaction.

- [ ] **Step 4: Implement PostgreSQL migrations and atomic operations**

Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `SELECT ... FOR UPDATE`, and the existing `_conn()` transaction context.

- [ ] **Step 5: Implement PostgreSQL wrapper delegation**

Delegate every new method in `_PostgresManager` to `PgDatabaseManager`.

- [ ] **Step 6: Run manager-contract and SQLite integration tests**

Run: `python -m unittest tests.test_inventory_manager_contract tests.test_inventory_repository -v`

Expected: all tests pass without requiring remote database credentials.

---

### Task 5: Streamlit Inventory UI Rewrite

**Files:**
- Create: `modules/inventory/ui.py`
- Create: `modules/inventory/presentation.py`
- Test: `tests/test_inventory_presentation.py`

**Interfaces:**
- Produces: `show_inventory_page(db_manager, operator="") -> None`
- Produces pure helpers: `filter_items(items, keyword="", category="全部", location="全部", status="启用")`, `inventory_metrics(items)`, `transaction_rows(records)`

- [ ] **Step 1: Write failing presentation tests**

Cover keyword matching across code/title/category/location, archived filtering, low-stock metrics, and signed display quantities for inbound/outbound records.

- [ ] **Step 2: Run presentation tests and verify missing-module failure**

Run: `python -m unittest tests.test_inventory_presentation -v`

Expected: import failure for the presentation helpers.

- [ ] **Step 3: Implement pure presentation helpers**

Keep Streamlit calls out of `presentation.py` so filters and metrics are testable without browser rendering.

- [ ] **Step 4: Implement the new page layout**

Build three tabs:

1. Inventory list with search, category, location, status and low-stock filters.
2. Transaction history with item/type/date filters and export.
3. Custom-field management with validation and protected deletion.

For title, category, and location forms, always render both the searchable history selectbox and optional new-value text input. Do not conditionally reveal inputs from inside a form.

Catch `InventoryError` and show its Chinese message. Log unexpected exceptions and show “操作失败，请稍后重试”.

- [ ] **Step 5: Run presentation tests**

Run: `python -m unittest tests.test_inventory_presentation -v`

Expected: all tests pass.

---

### Task 6: Replace App Entry And Remove Legacy UI

**Files:**
- Modify: `app.py`
- Modify: `modules/inventory/__init__.py`
- Test: `tests/test_inventory_module_boundary.py`

**Interfaces:**
- `app.show_inventory()` obtains the database manager and delegates to `show_inventory_page`.

- [ ] **Step 1: Write failing module-boundary test**

Read `app.py` as text and assert the old form keys such as `inv_qadd_cat_sel` and raw `duplicate key` handling are absent, while `show_inventory_page` is imported and called.

- [ ] **Step 2: Run boundary test and verify failure**

Run: `python -m unittest tests.test_inventory_module_boundary -v`

Expected: failure because the legacy implementation still exists.

- [ ] **Step 3: Replace the monolithic inventory function**

```python
def show_inventory():
    from modules.inventory.ui import show_inventory_page

    try:
        db = get_db_manager()
    except Exception:
        st.error("数据库连接失败，请检查配置后重试")
        return
    show_inventory_page(db, operator=st.session_state.get("username", ""))
```

Remove the legacy inventory page body from `app.py` without changing the navigation call.

- [ ] **Step 4: Run boundary and focused tests**

Run: `python -m unittest discover -s tests -p 'test_inventory*.py' -v`

Expected: all inventory tests pass.

---

### Task 7: Verification And Handoff

**Files:**
- Modify only if verification reveals an inventory-specific defect.

- [ ] **Step 1: Compile changed Python files**

Run: `python -m py_compile app.py modules/db_manager.py modules/pg_database.py modules/inventory/*.py`

Expected: no output and exit code 0.

- [ ] **Step 2: Run all inventory tests**

Run: `python -m unittest discover -s tests -p 'test_inventory*.py' -v`

Expected: all tests pass.

- [ ] **Step 3: Run import smoke test**

Run: `python -c "import app; from modules.inventory.service import InventoryService; print('inventory import ok')"`

Expected: `inventory import ok`.

- [ ] **Step 4: Review diff and secret exposure**

Run: `git diff --check && git status --short && git diff --stat`

Expected: only inventory code, tests, and design/plan documents changed; no credentials or generated database files are added.

- [ ] **Step 5: Report unverified remote behavior separately**

State clearly whether Streamlit Community Cloud deployment and remote MySQL/PostgreSQL behavior were tested. Do not claim production deployment without an actual deployment and live check.
