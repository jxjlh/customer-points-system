import pandas as pd
from datetime import datetime

class CustomerAnalysis:
    def __init__(self, settings=None):
        if settings:
            self.NEW_CUSTOMER_START = datetime.strptime(settings.get("新客户判断起始日期", "2024-01-01"), "%Y-%m-%d")
            self.NEW_CUSTOMER_END = datetime.strptime(settings.get("新客户判断截止日期", "2026-04-20"), "%Y-%m-%d")
        else:
            self.NEW_CUSTOMER_START = datetime(2024, 1, 1)
            self.NEW_CUSTOMER_END = datetime(2026, 4, 20)
    
    def analyze_customer_attributes(self, df_raw, column_mapping):
        if df_raw is None or df_raw.empty:
            return pd.DataFrame()
        
        df = df_raw.copy()
        
        date_col = column_mapping.get("date")
        customer_col = column_mapping.get("customer")
        amount_col = column_mapping.get("amount_cny", column_mapping.get("amount"))
        
        if not date_col or not customer_col:
            return pd.DataFrame()
        
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        
        customer_group = df.groupby(customer_col).agg(
            首次订单日期=(date_col, "min"),
            最近订单日期=(date_col, "max"),
            订单次数=(date_col, "count")
        ).reset_index()
        
        if amount_col:
            amount_group = df.groupby(customer_col).agg(
                累计销售金额=(amount_col, "sum")
            ).reset_index()
            customer_group = customer_group.merge(amount_group, on=customer_col, how="left")
        else:
            customer_group["累计销售金额"] = 0
        
        customer_group["客户属性"] = customer_group["首次订单日期"].apply(
            lambda x: "新客户" if x > self.NEW_CUSTOMER_END else "老客户"
        )
        
        customer_group["首次订单日期"] = customer_group["首次订单日期"].dt.strftime("%Y-%m-%d")
        customer_group["最近订单日期"] = customer_group["最近订单日期"].dt.strftime("%Y-%m-%d")
        
        customer_group.columns = ["客户", "首次订单日期", "最近订单日期", "订单次数", "累计销售金额", "客户属性"]
        
        return customer_group
    
    def get_new_customer_count(self, df_customer):
        if df_customer is None or df_customer.empty:
            return 0
        return int(df_customer[df_customer["客户属性"] == "新客户"]["客户"].count())
    
    def get_old_customer_count(self, df_customer):
        if df_customer is None or df_customer.empty:
            return 0
        return int(df_customer[df_customer["客户属性"] == "老客户"]["客户"].count())
    
    def get_new_customer_ratio(self, df_customer):
        total = len(df_customer)
        if total == 0:
            return 0
        return round(self.get_new_customer_count(df_customer) / total * 100, 2)
    
    def get_customer_value_rank(self, df_customer, top_n=10):
        if df_customer is None or df_customer.empty:
            return pd.DataFrame()
        return df_customer.sort_values("累计销售金额", ascending=False).head(top_n)
    
    def get_customer_order_frequency(self, df_customer):
        if df_customer is None or df_customer.empty:
            return pd.DataFrame()
        
        bins = [0, 1, 3, 5, 10, float("inf")]
        labels = ["1次", "2-3次", "4-5次", "6-10次", "10次以上"]
        
        df_customer["订单频次区间"] = pd.cut(df_customer["订单次数"], bins=bins, labels=labels, right=False)
        frequency = df_customer.groupby("订单频次区间").size().reset_index(name="客户数量")
        
        return frequency
