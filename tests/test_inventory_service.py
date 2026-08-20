import unittest

from modules.inventory.errors import (
    DuplicateItemCodeError,
    InsufficientStockError,
    ValidationError,
)
from modules.inventory.service import InventoryService


class FakeInventoryRepository:
    def __init__(self):
        self.items = {}
        self.transactions = []
        self.deleted = []
        self.deleted_history_values = []
        self.next_id = 1

    def list_items(self):
        return list(self.items.values())

    def get_item(self, item_id):
        return self.items.get(item_id)

    def code_exists(self, item_code, exclude_item_id=None):
        return any(
            item["item_code"] == item_code and item_id != exclude_item_id
            for item_id, item in self.items.items()
        )

    def create_item(self, item):
        item_id = self.next_id
        self.next_id += 1
        self.items[item_id] = {
            "id": item_id,
            "quantity": 0,
            "is_active": 1,
            **item,
        }
        return item_id

    def update_item(self, item_id, item):
        self.items[item_id].update(item)

    def change_stock(self, item_id, transaction_type, quantity, remark, operator):
        item = self.items[item_id]
        before = item["quantity"]
        if transaction_type == "out" and quantity > before:
            raise InsufficientStockError("库存不足")
        after = before + quantity if transaction_type == "in" else before - quantity
        item["quantity"] = after
        self.transactions.append(
            {
                "item_id": item_id,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "stock_before": before,
                "stock_after": after,
                "remark": remark,
                "operator": operator,
            }
        )

    def transaction_count(self, item_id):
        return sum(record["item_id"] == item_id for record in self.transactions)

    def set_active(self, item_id, is_active):
        self.items[item_id]["is_active"] = 1 if is_active else 0

    def delete_without_history(self, item_id):
        self.deleted.append(item_id)
        del self.items[item_id]
        return True

    def history_values(self, column):
        return [item.get(column, "") for item in self.items.values()]

    def delete_history_value(self, column, value):
        self.deleted_history_values.append((column, value))
        return bool(value)


class InventoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeInventoryRepository()
        self.service = InventoryService(self.repository)

    def test_create_allows_duplicate_manual_code(self):
        self.repository.create_item(
            {
                "item_code": "M-001",
                "title": "模型A",
                "category": "小鼠",
                "location": "A1",
                "extra_fields": {},
            }
        )

        item_id = self.service.create_item(
            {
                "item_code": "M-001",
                "title_new": "模型B",
            }
        )

        self.assertEqual(self.repository.get_item(item_id)["item_code"], "M-001")

    def test_create_uses_new_reusable_values_and_records_initial_stock(self):
        item_id = self.service.create_item(
            {
                "item_code": " M-002 ",
                "title_selected": "旧名称",
                "title_new": " 新名称 ",
                "category_selected": "旧类别",
                "category_new": "新类别",
                "location_selected": "A1",
                "location_new": "B2",
                "quantity": 3,
                "remark": "首次入库",
            },
            operator="tester",
        )

        item = self.repository.get_item(item_id)
        self.assertEqual(item["item_code"], "M-002")
        self.assertEqual(item["title"], "新名称")
        self.assertEqual(item["category"], "新类别")
        self.assertEqual(item["location"], "B2")
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(self.repository.transactions[0]["remark"], "首次入库")

    def test_outbound_rejects_quantity_above_current_stock(self):
        item_id = self.repository.create_item(
            {
                "item_code": "M-003",
                "title": "模型C",
                "category": "",
                "location": "",
                "quantity": 2,
                "extra_fields": {},
            }
        )

        with self.assertRaisesRegex(InsufficientStockError, "当前库存为2"):
            self.service.change_stock(item_id, "out", 3)

        self.assertEqual(self.repository.get_item(item_id)["quantity"], 2)
        self.assertEqual(self.repository.transactions, [])

    def test_item_with_history_is_archived(self):
        item_id = self.repository.create_item(
            {
                "item_code": "M-004",
                "title": "模型D",
                "category": "",
                "location": "",
                "quantity": 0,
                "extra_fields": {},
            }
        )
        self.repository.transactions.append({"item_id": item_id})

        result = self.service.archive_or_delete(item_id)

        self.assertEqual(result, "archived")
        self.assertEqual(self.repository.get_item(item_id)["is_active"], 0)

    def test_item_without_history_is_deleted(self):
        item_id = self.repository.create_item(
            {
                "item_code": "M-005",
                "title": "模型E",
                "category": "",
                "location": "",
                "quantity": 0,
                "extra_fields": {},
            }
        )

        result = self.service.archive_or_delete(item_id)

        self.assertEqual(result, "deleted")
        self.assertIsNone(self.repository.get_item(item_id))

    def test_negative_initial_quantity_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "初始数量不能小于0"):
            self.service.create_item(
                {
                    "item_code": "M-006",
                    "title_new": "模型F",
                    "quantity": -1,
                }
            )

    def test_history_value_can_be_deleted(self):
        self.service.delete_history_value("location", " A1 ")

        self.assertEqual(self.repository.deleted_history_values, [("location", "A1")])

    def test_history_options_only_include_category_and_location(self):
        self.repository.create_item(
            {
                "item_code": "M-007",
                "title": "模型G",
                "category": "实验鼠",
                "location": "A1",
                "extra_fields": {},
            }
        )

        self.assertEqual(
            self.service.history_options(),
            {"category": ["实验鼠"], "location": ["A1"]},
        )

    def test_title_history_value_cannot_be_deleted(self):
        with self.assertRaisesRegex(ValidationError, "不支持"):
            self.service.delete_history_value("title", "模型G")


if __name__ == "__main__":
    unittest.main()
