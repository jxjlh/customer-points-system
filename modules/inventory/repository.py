from typing import Any, Optional


class InventoryRepositoryAdapter:
    def __init__(self, manager: Any):
        self.manager = manager

    def list_items(self):
        return self.manager.list_inventory_items()

    def get_item(self, item_id: int):
        return self.manager.get_inventory_item(item_id)

    def code_exists(self, item_code: str, exclude_item_id: Optional[int] = None) -> bool:
        return self.manager.inventory_code_exists(item_code, exclude_item_id)

    def create_item(self, item: dict) -> int:
        return self.manager.add_inventory_item(item)

    def update_item(self, item_id: int, item: dict) -> bool:
        return self.manager.update_inventory_item(item_id, item)

    def change_stock(
        self,
        item_id: int,
        transaction_type: str,
        quantity: int,
        remark: str,
        operator: str,
    ) -> bool:
        return self.manager.inventory_transaction_atomic(
            item_id,
            transaction_type,
            quantity,
            remark,
            operator,
        )

    def list_transactions(self, item_id: Optional[int] = None, limit: int = 500):
        return self.manager.list_inventory_transactions(item_id=item_id, limit=limit)

    def transaction_count(self, item_id: int) -> int:
        return self.manager.count_inventory_transactions(item_id)

    def set_active(self, item_id: int, is_active: bool) -> bool:
        return self.manager.set_inventory_item_active(item_id, is_active)

    def delete_without_history(self, item_id: int) -> bool:
        return self.manager.delete_inventory_item_without_history(item_id)

    def history_values(self, column: str):
        return self.manager.get_inventory_history_values(column)

    def clear_history_value(self, column: str, value: str):
        return self.manager.clear_inventory_history_value(column, value)

    def list_fields(self):
        return self.manager.list_inventory_fields()

    def add_field(self, field_name: str, field_label: str, field_type: str) -> bool:
        return self.manager.add_inventory_field(field_name, field_label, field_type)

    def delete_field(self, field_id: int) -> bool:
        return self.manager.delete_inventory_field(field_id)
