import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class QuotationService:
    def __init__(self):
        self.items: List[Dict] = []
        self.customer_info: Dict = {
            "customer_name": "",
            "contact_person": "",
            "sales_person": "",
            "customer_type": "commercial"
        }
        self.summary: Dict = {
            "subtotal": 0,
            "shipping": 0,
            "service_fee": 0,
            "discount": 0,
            "tax": 0,
            "grand_total": 0
        }
        self._load_config()

    def _load_config(self):
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        mapping_path = os.path.join(config_dir, "excel_mapping.json")
        
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r', encoding='utf-8') as f:
                self.mapping = json.load(f)
        else:
            self.mapping = {}

    def set_customer_info(self, customer_name: str, contact_person: str, 
                         sales_person: str, customer_type: str) -> None:
        self.customer_info = {
            "customer_name": customer_name,
            "contact_person": contact_person,
            "sales_person": sales_person,
            "customer_type": customer_type
        }

    def add_item(self, strain: str, genotype: str, age: str, sex: str, 
                 qty: int, price_info: Dict) -> Dict:
        unit_price = float(price_info.get("price", 0))
        amount = unit_price * qty
        
        item = {
            "id": len(self.items) + 1,
            "strain": strain,
            "name": price_info.get("strain_name", ""),
            "genotype": genotype,
            "age": age,
            "sex": sex,
            "qty": qty,
            "unit_price": unit_price,
            "amount": amount,
            "international_commercial": price_info.get("international_commercial", 0),
            "china_distributor_commercial": price_info.get("china_distributor_commercial", 0)
        }
        
        self.items.append(item)
        self._update_summary()
        
        return item

    def update_item(self, item_id: int, field: str, value) -> Optional[Dict]:
        for item in self.items:
            if item["id"] == item_id:
                if field == "qty":
                    item["qty"] = int(value)
                    item["amount"] = item["unit_price"] * item["qty"]
                elif field in ["strain", "name", "genotype", "age", "sex", "unit_price"]:
                    item[field] = value
                    if field == "unit_price":
                        item["amount"] = float(value) * item["qty"]
                
                self._update_summary()
                return item
        
        return None

    def delete_item(self, item_id: int) -> bool:
        original_length = len(self.items)
        self.items = [item for item in self.items if item["id"] != item_id]
        
        for i, item in enumerate(self.items):
            item["id"] = i + 1
        
        self._update_summary()
        
        return len(self.items) < original_length

    def _update_summary(self) -> None:
        subtotal = sum(item["amount"] for item in self.items)
        
        self.summary = {
            "subtotal": subtotal,
            "shipping": self.summary.get("shipping", 0),
            "service_fee": self.summary.get("service_fee", 0),
            "discount": self.summary.get("discount", 0),
            "tax": self.summary.get("tax", 0),
            "grand_total": subtotal + self.summary.get("shipping", 0) + 
                           self.summary.get("service_fee", 0) - 
                           self.summary.get("discount", 0) + 
                           self.summary.get("tax", 0)
        }

    def set_summary_field(self, field: str, value: float) -> None:
        if field in self.summary:
            self.summary[field] = value
            self._update_summary()

    def get_items(self) -> List[Dict]:
        return self.items

    def get_customer_info(self) -> Dict:
        return self.customer_info

    def get_summary(self) -> Dict:
        return self.summary

    def clear_all(self) -> None:
        self.items = []
        self.customer_info = {
            "customer_name": "",
            "contact_person": "",
            "sales_person": "",
            "customer_type": "commercial"
        }
        self.summary = {
            "subtotal": 0,
            "shipping": 0,
            "service_fee": 0,
            "discount": 0,
            "tax": 0,
            "grand_total": 0
        }

    def generate_quote_number(self, db_manager=None) -> str:
        """
        生成报价单号（优先使用数据库序号，降级扫描目录）

        Args:
            db_manager: 数据库管理器（可选）

        Returns:
            CT-YYYYMMDD-NNN 格式的报价单号
        """
        if db_manager and hasattr(db_manager, 'get_next_quote_number'):
            try:
                return db_manager.get_next_quote_number()
            except Exception:
                pass

        # 降级：扫描本地目录
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)

        existing_files = [f for f in os.listdir(export_dir) if f.startswith(f"CT-{date_str}")]

        if not existing_files:
            sequence = "001"
        else:
            max_seq = max(int(f.split("-")[-1].replace(".xlsx", "").replace(".pdf", "")) for f in existing_files)
            sequence = f"{max_seq + 1:03d}"

        return f"CT-{date_str}-{sequence}"

    def to_dict(self, db_manager=None) -> Dict:
        return {
            "customer_info": self.customer_info,
            "items": self.items,
            "summary": self.summary,
            "quote_number": self.generate_quote_number(db_manager),
            "quote_date": datetime.now().strftime("%Y-%m-%d")
        }

    def save_to_db(self, db_manager) -> int:
        """
        保存报价单到数据库

        Args:
            db_manager: 数据库管理器

        Returns:
            quotation_id
        """
        quotation_data = self.to_dict(db_manager)
        return db_manager.save_quotation(quotation_data)

    def load_from_db(self, db_manager, quote_id: int) -> bool:
        """
        从数据库加载报价单（用于复用历史报价）

        Args:
            db_manager: 数据库管理器
            quote_id: 报价单ID

        Returns:
            是否加载成功
        """
        quote = db_manager.get_quotation_by_id(quote_id) if hasattr(db_manager, 'get_quotation_by_id') else None
        if not quote:
            return False

        self.customer_info = {
            "customer_name": quote.get("customer_name", ""),
            "contact_person": quote.get("contact_person", ""),
            "sales_person": quote.get("sales_person", ""),
            "customer_type": quote.get("customer_type", "commercial"),
        }
        self.summary = {
            "subtotal": float(quote.get("subtotal", 0)),
            "shipping": float(quote.get("shipping", 0)),
            "service_fee": float(quote.get("service_fee", 0)),
            "discount": float(quote.get("discount", 0)),
            "tax": float(quote.get("tax", 0)),
            "grand_total": float(quote.get("grand_total", 0)),
        }

        items = quote.get("items", [])
        self.items = []
        for i, item in enumerate(items):
            self.items.append({
                "id": i + 1,
                "strain": item.get("strain", ""),
                "name": item.get("strain_name", ""),
                "genotype": item.get("genotype", ""),
                "age": item.get("age", ""),
                "sex": item.get("sex", ""),
                "qty": int(item.get("qty", 0)),
                "unit_price": float(item.get("unit_price", 0)),
                "amount": float(item.get("amount", 0)),
                "international_commercial": float(item.get("international_commercial") or 0),
                "china_distributor_commercial": float(item.get("china_distributor_commercial") or 0),
            })
        return True

    def get_total_items(self) -> int:
        return len(self.items)

    def get_total_amount(self) -> float:
        return self.summary.get("grand_total", 0)