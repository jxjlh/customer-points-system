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

    def test_item_form_uses_composite_history_inputs(self):
        ui_path = Path(__file__).resolve().parents[1] / "modules" / "inventory" / "ui.py"
        source = ui_path.read_text(encoding="utf-8")

        self.assertNotIn("搜索已有值", source)
        self.assertIn('"title 类别（大分类）"', source)
        self.assertIn('"存放位置"', source)
        self.assertIn('placeholder="输入新值或选择历史值"', source)
        self.assertIn("accept_new_options=True", source)


if __name__ == "__main__":
    unittest.main()
