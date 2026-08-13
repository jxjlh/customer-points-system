import json
import re
from typing import Any

from modules.inventory.errors import (
    DeleteRestrictedError,
    DuplicateItemCodeError,
    InsufficientStockError,
    ItemArchivedError,
    ItemNotFoundError,
    ValidationError,
)
from modules.inventory.field_values import normalize_options, resolve_reusable_value


class InventoryService:
    def __init__(self, repository: Any):
        self.repository = repository

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def list_items(self):
        return self.repository.list_items()

    def get_item(self, item_id: int):
        item = self.repository.get_item(item_id)
        if not item:
            raise ItemNotFoundError("库存物品不存在")
        return item

    def create_item(self, data: dict, operator: str = "") -> int:
        item_code = self._required_text(data.get("item_code"), "编号")

        title, category, location = self._resolve_reusable_fields(data)
        initial_quantity = self._non_negative_int(data.get("quantity", 0), "初始数量")
        item = {
            "item_code": item_code,
            "title": title,
            "category": category,
            "location": location,
            "quantity": 0,
            "extra_fields": self._clean_extra_fields(data.get("extra_fields", {})),
        }

        item_id = self.repository.create_item(item)

        if initial_quantity > 0:
            try:
                self.repository.change_stock(
                    item_id,
                    "in",
                    initial_quantity,
                    str(data.get("remark") or "").strip() or "初始入库",
                    operator,
                )
            except Exception:
                self.repository.delete_without_history(item_id)
                raise
        return item_id

    def update_item(self, item_id: int, data: dict) -> None:
        current = self.get_item(item_id)
        item_code = self._required_text(data.get("item_code"), "编号")

        title, category, location = self._resolve_reusable_fields(data)
        self.repository.update_item(
            item_id,
            {
                "item_code": item_code,
                "title": title,
                "category": category,
                "location": location,
                "extra_fields": self._clean_extra_fields(data.get("extra_fields", {})),
                "quantity": current.get("quantity", 0),
            },
        )

    def change_stock(
        self,
        item_id: int,
        transaction_type: str,
        quantity: int,
        remark: str = "",
        operator: str = "",
    ) -> None:
        item = self.get_item(item_id)
        if not int(item.get("is_active", 1)):
            raise ItemArchivedError("该物品已归档，不能继续出入库")
        if transaction_type not in {"in", "out"}:
            raise ValidationError("出入库类型无效")
        normalized_quantity = self._positive_int(quantity, "出入库数量")
        current_stock = int(item.get("quantity", 0) or 0)
        if transaction_type == "out" and normalized_quantity > current_stock:
            raise InsufficientStockError(
                f"当前库存为{current_stock}，本次最多可出库{current_stock}"
            )
        self.repository.change_stock(
            item_id,
            transaction_type,
            normalized_quantity,
            str(remark or "").strip(),
            str(operator or "").strip(),
        )

    def archive_or_delete(self, item_id: int) -> str:
        self.get_item(item_id)
        if self.repository.transaction_count(item_id) > 0:
            self.repository.set_active(item_id, False)
            return "archived"
        if not self.repository.delete_without_history(item_id):
            raise ItemNotFoundError("库存物品不存在")
        return "deleted"

    def restore_item(self, item_id: int) -> None:
        self.get_item(item_id)
        self.repository.set_active(item_id, True)

    def history_options(self) -> dict[str, list[str]]:
        return {
            column: normalize_options(self.repository.history_values(column))
            for column in ("category", "location")
        }

    def delete_history_value(self, column: str, value: str) -> None:
        labels = {"category": "title 类别（大分类）", "location": "存放位置"}
        if column not in labels:
            raise ValidationError("不支持的库存历史字段")
        normalized = self._required_text(value, labels[column])
        if not self.repository.delete_history_value(column, normalized):
            raise ValidationError("请选择要删除的历史值")

    def list_transactions(self, item_id: int | None = None, limit: int = 500):
        return self.repository.list_transactions(item_id=item_id, limit=limit)

    def list_fields(self):
        return self.repository.list_fields()

    def add_field(self, field_name: str, field_label: str, field_type: str) -> None:
        normalized_name = str(field_name or "").strip()
        normalized_label = str(field_label or "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", normalized_name):
            raise ValidationError("字段名必须以英文字母开头，且只能包含字母、数字和下划线")
        if not normalized_label:
            raise ValidationError("显示标签不能为空")
        if field_type not in {"text", "number"}:
            raise ValidationError("字段类型无效")
        self.repository.add_field(normalized_name, normalized_label, field_type)

    def delete_field(self, field_id: int) -> None:
        field = next(
            (row for row in self.repository.list_fields() if int(row.get("id")) == int(field_id)),
            None,
        )
        if not field:
            raise ItemNotFoundError("自定义字段不存在")
        field_name = field.get("field_name", "")
        for item in self.repository.list_items():
            raw_extra = item.get("extra_fields") or {}
            if isinstance(raw_extra, str):
                try:
                    raw_extra = json.loads(raw_extra)
                except (TypeError, ValueError):
                    raw_extra = {}
            if isinstance(raw_extra, dict) and str(raw_extra.get(field_name, "")).strip():
                raise DeleteRestrictedError("该字段已有库存数据，不能删除")
        self.repository.delete_field(field_id)

    @staticmethod
    def _resolve_reusable_fields(data: dict) -> tuple[str, str, str]:
        # 新格式：直接传 title/category/location 字符串
        # 旧格式兼容：title_selected + title_new
        title = str(data.get("title", "")).strip()
        if not title:
            title = resolve_reusable_value(
                data.get("title_selected", ""),
                data.get("title_new", ""),
                required=True,
                field_label="title",
            )

        category = str(data.get("category", "")).strip()
        if not category:
            category = resolve_reusable_value(
                data.get("category_selected", ""),
                data.get("category_new", ""),
            )

        location = str(data.get("location", "")).strip()
        if not location:
            location = resolve_reusable_value(
                data.get("location_selected", ""),
                data.get("location_new", ""),
            )
        return title, category, location

    @staticmethod
    def _required_text(value: Any, field_label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValidationError(f"{field_label}不能为空")
        return normalized

    @staticmethod
    def _non_negative_int(value: Any, field_label: str) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field_label}必须是整数") from exc
        if normalized < 0:
            raise ValidationError(f"{field_label}不能小于0")
        return normalized

    @staticmethod
    def _positive_int(value: Any, field_label: str) -> int:
        normalized = InventoryService._non_negative_int(value, field_label)
        if normalized == 0:
            raise ValidationError(f"{field_label}必须大于0")
        return normalized

    @staticmethod
    def _clean_extra_fields(extra_fields: Any) -> dict:
        if not isinstance(extra_fields, dict):
            return {}
        return {
            str(key): str(value).strip()
            for key, value in extra_fields.items()
            if value is not None and str(value).strip()
        }

    @staticmethod
    def _looks_like_duplicate(exc: Exception) -> bool:
        message = str(exc).lower()
        return "duplicate" in message or "unique constraint" in message
