import pandas as pd
import os
import json
from io import BytesIO
from typing import Dict, Optional, Tuple, List


class PriceService:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, price_file_path: str = None):
        if self._initialized:
            return
        
        self.price_file_path = price_file_path
        self.dataframes: Dict[str, pd.DataFrame] = {}
        self.mapping = {}
        self.sheet_mapping = {}
        self._load_config()
        self._initialized = True

    def _load_config(self):
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        
        mapping_path = os.path.join(config_dir, "excel_mapping.json")
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r', encoding='utf-8') as f:
                self.mapping = json.load(f)
        
        sheet_mapping_path = os.path.join(config_dir, "price_sheet_mapping.json")
        if os.path.exists(sheet_mapping_path):
            with open(sheet_mapping_path, 'r', encoding='utf-8') as f:
                self.sheet_mapping = json.load(f)

    def load_price_data(self, file_path: str = None, file_bytes: bytes = None) -> bool:
        if file_bytes:
            xls = pd.ExcelFile(BytesIO(file_bytes), engine="openpyxl")
        elif file_path:
            self.price_file_path = file_path
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"价格文件不存在: {file_path}")
            xls = pd.ExcelFile(file_path, engine="openpyxl")
        elif self.price_file_path:
            xls = pd.ExcelFile(self.price_file_path, engine="openpyxl")
        else:
            raise ValueError("请提供价格文件路径或文件字节流")

        available_sheets = xls.sheet_names
        self.dataframes = {}

        for customer_type, sheet_names in self.sheet_mapping.get("sheets", {}).items():
            for sheet_name in sheet_names:
                if sheet_name in available_sheets:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    df = self._normalize_columns(df)
                    self.dataframes[customer_type] = df
                    break

        if not self.dataframes:
            for sheet_name in available_sheets:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                df = self._normalize_columns(df)
                self.dataframes[sheet_name] = df

        return True

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        column_mapping = {}
        price_columns = self.mapping.get("price_columns", {})

        for key, aliases in price_columns.items():
            for alias in aliases:
                if alias in df.columns:
                    column_mapping[alias] = key
                    break

        if column_mapping:
            df = df.rename(columns=column_mapping)

        required_columns = ["strain", "long_genotype", "age", "sex"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def _normalize_sex(self, sex: str) -> str:
        sex = str(sex).strip().upper()
        sex_mapping = self.mapping.get("sex_mapping", {})
        
        for standard, aliases in sex_mapping.items():
            if sex in [a.upper() for a in aliases]:
                return standard
        
        return sex

    def _normalize_age(self, age: str) -> str:
        age = str(age).strip()
        if age.isdigit():
            return age
        if age.endswith("w") or age.endswith("周"):
            return age[:-1].strip()
        return age

    def query_price(self, strain: str, long_genotype: str, age: str, sex: str, 
                    customer_type: str = "commercial") -> Dict:
        df = self.dataframes.get(customer_type)
        if df is None:
            df = self.dataframes.get(self.sheet_mapping.get("fallback_sheet", "commercial"))
        
        if df is None or df.empty:
            return {"error": "未找到价格数据", "found": False}

        strain = str(strain).strip()
        long_genotype = str(long_genotype).strip()
        age = self._normalize_age(age)
        sex = self._normalize_sex(sex)

        query = (
            (df["strain"].astype(str).str.strip() == strain) &
            (df["long_genotype"].astype(str).str.strip() == long_genotype) &
            (df["age"].astype(str).apply(self._normalize_age) == age) &
            (df["sex"].astype(str).apply(self._normalize_sex) == sex)
        )

        results = df[query]

        if len(results) == 0:
            return {"error": "未找到对应价格", "found": False}
        
        if len(results) > 1:
            return {"error": "价格库存在重复数据", "found": False, "count": len(results)}

        row = results.iloc[0]
        
        price_columns = self.mapping.get("price_columns", {})
        price_key = self._get_price_key(customer_type)
        
        result = {
            "found": True,
            "strain": row.get("strain", strain),
            "strain_name": row.get("strain_name", ""),
            "long_genotype": row.get("long_genotype", long_genotype),
            "age": row.get("age", age),
            "sex": row.get("sex", sex),
            "price": row.get(price_key, row.get("price", 0)),
            "international_commercial": row.get("international_commercial", 0),
            "china_distributor_commercial": row.get("china_distributor_commercial", 0),
            "customer_type": customer_type
        }

        return result

    def _get_price_key(self, customer_type: str) -> str:
        price_key_map = {
            "commercial": "china_distributor_commercial",
            "npo": "npo_price",
            "ka": "ka_price"
        }
        return price_key_map.get(customer_type, "price")

    def get_all_strains(self, customer_type: str = "commercial") -> List[str]:
        df = self.dataframes.get(customer_type)
        if df is None:
            df = self.dataframes.get(self.sheet_mapping.get("fallback_sheet", "commercial"))
        
        if df is None or df.empty:
            return []
        
        return df["strain"].astype(str).str.strip().unique().tolist()

    def get_strain_info(self, strain: str, customer_type: str = "commercial") -> Optional[Dict]:
        df = self.dataframes.get(customer_type)
        if df is None:
            df = self.dataframes.get(self.sheet_mapping.get("fallback_sheet", "commercial"))
        
        if df is None or df.empty:
            return None
        
        results = df[df["strain"].astype(str).str.strip() == strain.strip()]
        
        if results.empty:
            return None
        
        row = results.iloc[0]
        return {
            "strain": row.get("strain", strain),
            "strain_name": row.get("strain_name", ""),
            "long_genotype": row.get("long_genotype", ""),
            "available_ages": results["age"].astype(str).unique().tolist(),
            "available_sexes": results["sex"].astype(str).unique().tolist()
        }

    def is_loaded(self) -> bool:
        return len(self.dataframes) > 0

    def get_available_customer_types(self) -> List[str]:
        return list(self.dataframes.keys())

    def get_dataframe_info(self) -> Dict:
        info = {}
        for customer_type, df in self.dataframes.items():
            info[customer_type] = {
                "rows": len(df),
                "columns": df.columns.tolist()
            }
        return info