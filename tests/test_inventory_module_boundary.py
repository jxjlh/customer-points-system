import ast
import unittest
from pathlib import Path


class InventoryModuleBoundaryTests(unittest.TestCase):
    def test_app_inventory_entry_only_delegates_to_inventory_module(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "show_inventory"
        ]
        self.assertEqual(len(functions), 1)
        function_source = ast.get_source_segment(source, functions[0]) or ""
        self.assertIn("show_inventory_page", function_source)
        self.assertNotIn("inv_qadd_cat_sel", function_source)
        self.assertLess(len(function_source.splitlines()), 20)

    def test_item_form_places_new_values_before_direct_history_choices(self):
        ui_path = Path(__file__).resolve().parents[1] / "modules" / "inventory" / "ui.py"
        source = ui_path.read_text(encoding="utf-8")

        self.assertNotIn("搜索已有值", source)
        self.assertIn('f"{label}（新增值）"', source)
        self.assertIn('f"已有{label}（可选，直接选择）"', source)


if __name__ == "__main__":
    unittest.main()
