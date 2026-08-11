import unittest

from modules.inventory.presentation import (
    filter_items,
    inventory_metrics,
    transaction_rows,
)


ITEMS = [
    {
        "id": 1,
        "item_code": "M-001",
        "title": "杰克森小鼠",
        "category": "实验动物",
        "location": "A1",
        "quantity": 8,
        "is_active": 1,
    },
    {
        "id": 2,
        "item_code": "R-002",
        "title": "冻存胚胎",
        "category": "生物样本",
        "location": "B2",
        "quantity": 0,
        "is_active": 1,
    },
    {
        "id": 3,
        "item_code": "OLD-003",
        "title": "历史物品",
        "category": "实验动物",
        "location": "仓库",
        "quantity": 2,
        "is_active": 0,
    },
]


class InventoryPresentationTests(unittest.TestCase):
    def test_filter_items_searches_all_visible_identity_fields(self):
        self.assertEqual(
            [item["id"] for item in filter_items(ITEMS, keyword="B2", status="全部")],
            [2],
        )

    def test_filter_items_applies_category_location_and_status(self):
        result = filter_items(
            ITEMS,
            category="实验动物",
            location="A1",
            status="启用",
        )
        self.assertEqual([item["id"] for item in result], [1])

    def test_filter_items_can_show_archived_and_low_stock(self):
        archived = filter_items(ITEMS, status="已归档")
        low_stock = filter_items(ITEMS, status="全部", low_stock_only=True)
        self.assertEqual([item["id"] for item in archived], [3])
        self.assertEqual([item["id"] for item in low_stock], [2, 3])

    def test_inventory_metrics_reports_counts_and_quantity(self):
        self.assertEqual(
            inventory_metrics(ITEMS),
            {"item_count": 3, "total_quantity": 10, "low_stock": 2, "zero_stock": 1},
        )

    def test_transaction_rows_adds_chinese_type_and_signed_quantity(self):
        rows = transaction_rows(
            [
                {
                    "id": 1,
                    "item_code": "M-001",
                    "title": "杰克森小鼠",
                    "transaction_type": "out",
                    "quantity": 2,
                    "stock_before": 8,
                    "stock_after": 6,
                    "remark": "领用",
                    "operator": "tester",
                    "created_at": "2026-08-11 10:00:00",
                }
            ]
        )
        self.assertEqual(rows[0]["类型"], "出库")
        self.assertEqual(rows[0]["数量变化"], -2)
        self.assertEqual(rows[0]["操作后库存"], 6)


if __name__ == "__main__":
    unittest.main()
