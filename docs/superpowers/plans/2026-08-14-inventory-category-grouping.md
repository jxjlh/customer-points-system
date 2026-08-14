# Inventory Category Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate filtered inventory into independent tables and operation areas by `title 类别（大分类）`.

**Architecture:** Keep grouping logic in `modules/inventory/presentation.py` so it can be tested without Streamlit. The inventory page will first apply existing filters, then render one Streamlit expander per category with a concise table followed by the existing per-item operation cards. Items with an empty category are grouped under `未分类`.

**Tech Stack:** Python, Streamlit, unittest.

## Global Constraints

- Do not modify inventory database schemas, history-value behavior, or CRUD rules.
- Apply search, location, status, and low-stock filters before grouping.
- Keep metrics and exports based on all filtered items.
- Keep existing edit, stock transaction, archive, and deletion controls available.
- Render categories in deterministic text order and place `未分类` last.

---

### Task 1: Add tested category grouping presentation logic

**Files:**
- Modify: `modules/inventory/presentation.py`
- Modify: `tests/test_inventory_presentation.py`

**Interfaces:**
- Produces: `group_items_by_category(items: Iterable[dict]) -> list[tuple[str, list[dict]]]`
- Consumes: inventory rows that include optional `category` values.
- Used by: `modules/inventory/ui.py` after `filter_items`.

- [ ] **Step 1: Write the failing test**

```python
def test_group_items_by_category_keeps_titles_together_and_unclassified_last(self):
    grouped = group_items_by_category([
        {"id": 1, "title": "title A", "category": "仪器"},
        {"id": 2, "title": "title B", "category": "耗材"},
        {"id": 3, "title": "title C", "category": "仪器"},
        {"id": 4, "title": "title D", "category": "  "},
    ])

    self.assertEqual(
        [(name, [item["id"] for item in rows]) for name, rows in grouped],
        [("仪器", [1, 3]), ("耗材", [2]), ("未分类", [4])],
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_inventory_presentation.InventoryPresentationTests.test_group_items_by_category_keeps_titles_together_and_unclassified_last -v`

Expected: FAIL because `group_items_by_category` is not defined.

- [ ] **Step 3: Write minimal implementation**

```python
def group_items_by_category(items: Iterable[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for item in items:
        category = str(item.get("category") or "").strip() or "未分类"
        groups.setdefault(category, []).append(item)
    return [
        (category, groups[category])
        for category in sorted(groups, key=lambda value: (value == "未分类", value.casefold()))
    ]
```

- [ ] **Step 4: Run presentation tests to verify they pass**

Run: `python -m unittest tests.test_inventory_presentation -v`

Expected: PASS.

- [ ] **Step 5: Commit the completed presentation change**

```bash
git add modules/inventory/presentation.py tests/test_inventory_presentation.py
git commit -m "feat: group inventory items by category"
```

### Task 2: Render separate category tables and operation areas

**Files:**
- Modify: `modules/inventory/ui.py`
- Test: `tests/test_inventory_presentation.py`

**Interfaces:**
- Consumes: `group_items_by_category(filtered_items)` from `modules/inventory/presentation.py`.
- Produces: One `st.expander` per category containing a table and the existing `_render_item_card` controls.

- [ ] **Step 1: Add the presentation import**

Replace the presentation import with:

```python
from modules.inventory.presentation import (
    filter_items,
    group_items_by_category,
    inventory_metrics,
    transaction_rows,
)
```

- [ ] **Step 2: Replace the flat item rendering loop**

After the empty-state check in `_render_inventory_tab`, replace the existing flat loop with category groups. Each group must show the category name and count, a table with `编号`、`title`、`存放位置`、`库存`、`状态`, then invoke `_render_item_card` for every item in that group.

```python
for category_name, category_items in group_items_by_category(filtered_items):
    with st.expander(f"{category_name}（{len(category_items)} 个物品）", expanded=True):
        st.dataframe(
            [{
                "编号": item.get("item_code", ""),
                "title": item.get("title", ""),
                "存放位置": item.get("location", ""),
                "库存": item.get("quantity", 0),
                "状态": "启用" if item.get("is_active", 1) else "已归档",
            } for item in category_items],
            hide_index=True,
            use_container_width=True,
        )
        for item in category_items:
            _render_item_card(service, item, history_options, custom_fields, operator)
```

- [ ] **Step 3: Run focused and syntax verification**

Run: `python -m unittest tests.test_inventory_presentation -v && python -m py_compile modules/inventory/ui.py modules/inventory/presentation.py`

Expected: PASS with no syntax errors.

- [ ] **Step 4: Commit the UI grouping change**

```bash
git add modules/inventory/ui.py
git commit -m "feat: render inventory tables by category"
```

### Task 3: Validate final behavior and push

**Files:**
- Verify: `modules/inventory/presentation.py`
- Verify: `modules/inventory/ui.py`
- Verify: `tests/test_inventory_presentation.py`

- [ ] **Step 1: Run the complete inventory presentation test suite**

Run: `python -m unittest tests.test_inventory_presentation -v`

Expected: PASS.

- [ ] **Step 2: Verify the final diff and branch state**

Run: `git diff HEAD~2..HEAD --check && git status -sb`

Expected: no whitespace errors and no uncommitted changes.

- [ ] **Step 3: Push the completed commits**

Run: `git push origin main`

Expected: both grouping commits are accepted by `origin/main`.
