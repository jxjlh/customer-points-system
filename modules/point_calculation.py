import pandas as pd

class PointCalculation:
    def __init__(self, settings):
        self.new_customer_multiplier = float(settings.get("新客户积分倍率", 2))
        self.old_customer_multiplier = float(settings.get("老客户积分倍率", 1))
        self.point_exchange_rate = float(settings.get("积分兑换比例", 0.3))
    
    def calculate_points(self, df_raw, df_customer, column_mapping):
        if df_raw is None or df_raw.empty or df_customer is None or df_customer.empty:
            return pd.DataFrame()
        
        df = df_raw.copy()
        
        date_col = column_mapping.get("date")
        customer_col = column_mapping.get("customer")
        order_no_col = column_mapping.get("order_no", column_mapping.get("tracking_no"))
        amount_col = column_mapping.get("amount_cny", column_mapping.get("amount"))
        
        if not date_col or not customer_col:
            return pd.DataFrame()
        
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        
        df = df.merge(df_customer[["客户", "客户属性"]], left_on=customer_col, right_on="客户", how="left")
        
        df["销售金额"] = df[amount_col].fillna(0) if amount_col else 0
        df["基础积分"] = df["销售金额"].apply(lambda x: int(x) if pd.notna(x) and x > 0 else 0)
        
        df["积分倍率"] = df["客户属性"].apply(
            lambda x: self.new_customer_multiplier if x == "新客户" else self.old_customer_multiplier
        )
        
        df["最终积分"] = (df["基础积分"] * df["积分倍率"]).astype(int)
        df["积分价值"] = df["最终积分"] * self.point_exchange_rate
        
        df["订单日期"] = df[date_col].dt.strftime("%Y-%m-%d")
        df["订单编号"] = df[order_no_col] if order_no_col else ""
        
        result = df[[customer_col, "订单编号", "订单日期", "销售金额", "客户属性", 
                     "基础积分", "积分倍率", "最终积分", "积分价值"]].copy()
        result.columns = ["客户", "订单编号", "订单日期", "销售金额", "客户属性", 
                          "基础积分", "积分倍率", "最终积分", "积分价值"]
        
        return result
    
    def calculate_point_account(self, df_points, df_exchange):
        if df_points is None or df_points.empty:
            return pd.DataFrame()
        
        customer_points = df_points.groupby("客户").agg(
            累计获得积分=("最终积分", "sum")
        ).reset_index()
        
        if df_exchange is not None and not df_exchange.empty:
            customer_exchange = df_exchange.groupby("客户").agg(
                累计兑换积分=("兑换积分数量", "sum"),
                兑换次数=("兑换编号", "count"),
                最近兑换时间=("兑换日期", "max")
            ).reset_index()
            
            customer_points = customer_points.merge(customer_exchange, on="客户", how="left")
            customer_points["累计兑换积分"] = customer_points["累计兑换积分"].fillna(0).astype(int)
            customer_points["兑换次数"] = customer_points["兑换次数"].fillna(0).astype(int)
        else:
            customer_points["累计兑换积分"] = 0
            customer_points["兑换次数"] = 0
            customer_points["最近兑换时间"] = ""
        
        customer_points["剩余积分"] = customer_points["累计获得积分"] - customer_points["累计兑换积分"]
        customer_points["剩余积分价值"] = customer_points["剩余积分"] * self.point_exchange_rate
        
        return customer_points
    
    def get_total_points(self, df_points):
        if df_points is None or df_points.empty:
            return 0
        return int(df_points["最终积分"].sum())
    
    def get_total_point_value(self, df_points):
        if df_points is None or df_points.empty:
            return 0
        return round(df_points["积分价值"].sum(), 2)
    
    def get_top_customers_by_points(self, df_points, top_n=20):
        if df_points is None or df_points.empty:
            return pd.DataFrame()
        
        customer_points = df_points.groupby("客户").agg(
            累计积分=("最终积分", "sum"),
            积分价值=("积分价值", "sum")
        ).reset_index()
        
        return customer_points.sort_values("累计积分", ascending=False).head(top_n)
    
    def get_points_trend(self, df_points):
        if df_points is None or df_points.empty:
            return pd.DataFrame()
        
        df = df_points.copy()
        df["订单日期"] = pd.to_datetime(df["订单日期"], errors="coerce")
        df = df.dropna(subset=["订单日期"])
        
        df["月份"] = df["订单日期"].dt.to_period("M")
        trend = df.groupby("月份").agg(
            积分数量=("最终积分", "sum"),
            订单数=("订单编号", "count")
        ).reset_index()
        
        trend["月份"] = trend["月份"].astype(str)
        
        return trend
    
    def get_total_exchanged_points(self, df_exchange):
        if df_exchange is None or df_exchange.empty:
            return 0
        return int(df_exchange["兑换积分数量"].sum())
    
    def get_total_exchanged_amount(self, df_exchange):
        if df_exchange is None or df_exchange.empty:
            return 0
        return round(df_exchange["兑换金额"].sum(), 2)
    
    def get_exchange_customer_count(self, df_exchange):
        if df_exchange is None or df_exchange.empty:
            return 0
        return int(df_exchange["客户"].nunique())
    
    def get_exchange_trend(self, df_exchange):
        if df_exchange is None or df_exchange.empty:
            return pd.DataFrame()
        
        df = df_exchange.copy()
        df["兑换日期"] = pd.to_datetime(df["兑换日期"], errors="coerce")
        df = df.dropna(subset=["兑换日期"])
        
        df["月份"] = df["兑换日期"].dt.to_period("M")
        trend = df.groupby("月份").agg(
            兑换积分=("兑换积分数量", "sum"),
            兑换金额=("兑换金额", "sum"),
            兑换次数=("兑换编号", "count")
        ).reset_index()
        
        trend["月份"] = trend["月份"].astype(str)
        
        return trend
    
    def get_exchange_customer_rank(self, df_exchange, top_n=10):
        if df_exchange is None or df_exchange.empty:
            return pd.DataFrame()
        
        customer_exchange = df_exchange.groupby("客户").agg(
            累计兑换积分=("兑换积分数量", "sum"),
            累计兑换金额=("兑换金额", "sum"),
            兑换次数=("兑换编号", "count")
        ).reset_index()
        
        return customer_exchange.sort_values("累计兑换积分", ascending=False).head(top_n)
    
    def get_customer_balance(self, df_account, customer_name):
        if df_account is None or df_account.empty:
            return None
        
        result = df_account[df_account["客户"] == customer_name]
        
        if result.empty:
            return None
        
        return result.iloc[0].to_dict()
