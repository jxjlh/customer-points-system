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


if __name__ == "__main__":
    unittest.main()
