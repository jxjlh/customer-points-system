import unittest

from modules.inventory.errors import ValidationError
from modules.inventory.field_values import normalize_options, resolve_reusable_value


class InventoryFieldValueTests(unittest.TestCase):
    def test_normalize_options_strips_deduplicates_and_sorts(self):
        self.assertEqual(
            normalize_options([" B ", "A", "", None, "A"]),
            ["A", "B"],
        )

    def test_current_value_is_preserved_for_editing(self):
        self.assertEqual(
            normalize_options(["A"], current_value="旧位置"),
            ["A", "旧位置"],
        )

    def test_new_value_overrides_selected_history(self):
        self.assertEqual(
            resolve_reusable_value("已有值", " 新值 "),
            "新值",
        )

    def test_selected_history_is_used_when_new_value_is_empty(self):
        self.assertEqual(
            resolve_reusable_value("已有值", "  "),
            "已有值",
        )

    def test_required_value_rejects_empty_result(self):
        with self.assertRaisesRegex(ValidationError, "title不能为空"):
            resolve_reusable_value("", "", required=True, field_label="title")


if __name__ == "__main__":
    unittest.main()
