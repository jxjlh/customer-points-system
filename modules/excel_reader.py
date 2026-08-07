import pandas as pd
import os
from datetime import datetime
from io import BytesIO

class ExcelReader:
    def __init__(self, excel_path=None, file_bytes=None):
        self.excel_path = excel_path
        self.file_bytes = file_bytes
        self.data = {}
        self.settings = {}
        self.file_name = ""
    
    def read_excel(self):
        if self.file_bytes:
            try:
                xls = pd.ExcelFile(BytesIO(self.file_bytes), engine="openpyxl")
                self.file_name = "上传文件"
            except Exception as e:
                raise RuntimeError(f"读取上传文件失败: {str(e)}")
        elif self.excel_path:
            if not os.path.exists(self.excel_path):
                raise FileNotFoundError(f"Excel文件不存在: {self.excel_path}")
            
            try:
                xls = pd.ExcelFile(self.excel_path, engine="openpyxl")
                self.file_name = os.path.basename(self.excel_path)
            except Exception as e:
                raise RuntimeError(f"读取Excel文件失败: {str(e)}")
        else:
            raise ValueError("请提供Excel文件路径或文件字节流")
        
        sheets = xls.sheet_names
        
        if "原始数据" in sheets:
            self.data["原始数据"] = pd.read_excel(xls, sheet_name="原始数据")
        
        if "积分兑换记录" in sheets:
            self.data["积分兑换记录"] = pd.read_excel(xls, sheet_name="积分兑换记录")
        
        self.load_settings(xls, sheets)
        
        return True
    
    def load_settings(self, xls, sheets):
        defaults = {
            "新客户积分倍率": 2,
            "老客户积分倍率": 1,
            "积分兑换比例": 0.3,
            "新客户判断起始日期": "2024-01-01",
            "新客户判断截止日期": "2026-04-20"
        }
        
        if "测算" in sheets:
            try:
                df_settings = pd.read_excel(xls, sheet_name="测算")
                if "参数名称" in df_settings.columns and "参数值" in df_settings.columns:
                    for _, row in df_settings.iterrows():
                        defaults[str(row["参数名称"]).strip()] = row["参数值"]
            except:
                pass
        
        self.settings = defaults
    
    def get_raw_data(self):
        if "原始数据" not in self.data:
            return pd.DataFrame()
        return self.data["原始数据"]
    
    def get_settings(self):
        return self.settings
    
    def get_exchange_records(self):
        if "积分兑换记录" not in self.data:
            return pd.DataFrame()
        return self.data["积分兑换记录"]
    
    def get_column_mapping(self):
        df = self.get_raw_data()
        if df is None or df.empty:
            return {}
        
        mapping = {}
        columns = df.columns.tolist()
        
        for col in columns:
            col_str = str(col).strip()
            if "日期" in col_str and "日期" not in mapping:
                mapping["date"] = col_str
            elif "单据编号" in col_str and "order_no" not in mapping:
                mapping["order_no"] = col_str
            elif ("在线订单跟踪号" in col_str or "跟踪号" in col_str) and "tracking_no" not in mapping:
                mapping["tracking_no"] = col_str
            elif "客户" in col_str and "customer" not in mapping:
                mapping["customer"] = col_str
            elif ("货号" in col_str or "物料编码" in col_str) and "product" not in mapping:
                mapping["product"] = col_str
            elif "金额（本位币）" in col_str and "amount_cny" not in mapping:
                mapping["amount_cny"] = col_str
            elif "价税合计" in col_str and "total_amount" not in mapping:
                mapping["total_amount"] = col_str
            elif "金额" == col_str and "amount" not in mapping:
                mapping["amount"] = col_str
        
        return mapping
    
    def add_raw_data(self, new_data):
        df = self.get_raw_data()
        new_df = pd.DataFrame([new_data])
        self.data["原始数据"] = pd.concat([df, new_df], ignore_index=True)
    
    def add_exchange_record(self, new_record):
        df = self.get_exchange_records()
        new_df = pd.DataFrame([new_record])
        self.data["积分兑换记录"] = pd.concat([df, new_df], ignore_index=True)
    
    def get_update_time(self):
        if self.excel_path and os.path.exists(self.excel_path):
            return datetime.fromtimestamp(os.path.getmtime(self.excel_path)).strftime("%Y-%m-%d %H:%M:%S")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_file_name(self):
        return self.file_name
    
    def save_excel(self, output_path=None):
        save_path = output_path if output_path else self.excel_path
        
        if not save_path:
            raise ValueError("请提供保存路径")
        
        try:
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                if "原始数据" in self.data:
                    self.data["原始数据"].to_excel(writer, sheet_name="原始数据", index=False)
                
                if "积分兑换记录" in self.data:
                    self.data["积分兑换记录"].to_excel(writer, sheet_name="积分兑换记录", index=False)
                
                df_settings = pd.DataFrame(list(self.settings.items()), columns=["参数名称", "参数值"])
                df_settings["说明"] = [
                    "新客户享受的积分倍率",
                    "老客户享受的积分倍率",
                    "1积分兑换金额（元）",
                    "新客户判断起始日期",
                    "新客户判断截止日期"
                ]
                df_settings.to_excel(writer, sheet_name="测算", index=False)
            
            return True
        except Exception as e:
            raise RuntimeError(f"保存Excel文件失败: {str(e)}")
    
    def update_raw_data(self, updated_df):
        self.data["原始数据"] = updated_df
    
    def update_exchange_records(self, updated_df):
        self.data["积分兑换记录"] = updated_df
