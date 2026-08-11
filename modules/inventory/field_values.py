from typing import Any, Iterable

from modules.inventory.errors import ValidationError


def normalize_options(values: Iterable[Any], current_value: Any = "") -> list[str]:
    cleaned = {
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    }
    current = str(current_value or "").strip()
    if current:
        cleaned.add(current)
    return sorted(cleaned, key=str.casefold)


def resolve_reusable_value(
    selected_value: Any,
    new_value: Any,
    required: bool = False,
    field_label: str = "字段",
) -> str:
    resolved = str(new_value or "").strip() or str(selected_value or "").strip()
    if required and not resolved:
        raise ValidationError(f"{field_label}不能为空")
    return resolved
