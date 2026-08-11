from typing import Any, Iterable


def filter_items(
    items: Iterable[dict],
    keyword: str = "",
    category: str = "全部",
    location: str = "全部",
    status: str = "启用",
    low_stock_only: bool = False,
) -> list[dict]:
    normalized_keyword = str(keyword or "").strip().casefold()
    filtered = []
    for item in items:
        is_active = bool(item.get("is_active", 1))
        if status == "启用" and not is_active:
            continue
        if status == "已归档" and is_active:
            continue
        if category != "全部" and str(item.get("category", "")) != category:
            continue
        if location != "全部" and str(item.get("location", "")) != location:
            continue
        if low_stock_only and int(item.get("quantity", 0) or 0) > 5:
            continue
        if normalized_keyword:
            searchable = (
                item.get("item_code", ""),
                item.get("title", ""),
                item.get("category", ""),
                item.get("location", ""),
            )
            if not any(normalized_keyword in str(value).casefold() for value in searchable):
                continue
        filtered.append(item)
    return filtered


def inventory_metrics(items: Iterable[dict]) -> dict[str, int]:
    rows = list(items)
    quantities = [int(item.get("quantity", 0) or 0) for item in rows]
    return {
        "item_count": len(rows),
        "total_quantity": sum(quantities),
        "low_stock": sum(quantity <= 5 for quantity in quantities),
        "zero_stock": sum(quantity == 0 for quantity in quantities),
    }


def transaction_rows(records: Iterable[dict]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        transaction_type = record.get("transaction_type", "")
        quantity = int(record.get("quantity", 0) or 0)
        rows.append(
            {
                "时间": record.get("created_at", ""),
                "编号": record.get("item_code", ""),
                "title": record.get("title", ""),
                "类型": "入库" if transaction_type == "in" else "出库",
                "数量变化": quantity if transaction_type == "in" else -quantity,
                "操作前库存": record.get("stock_before"),
                "操作后库存": record.get("stock_after"),
                "备注": record.get("remark", ""),
                "操作人": record.get("operator", ""),
            }
        )
    return rows
