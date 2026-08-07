import pandas as pd
from datetime import datetime, timedelta
import random

excel_path = "c:\\Users\\Admin\\Desktop\\test\\customer_points_system\\data\\customer.xlsx"

customers_new = ["新客户A", "新客户B", "新客户C", "新客户D", "新客户E", "新客户F", "新客户G", "新客户H", "新客户I", "新客户J"]
customers_old = ["老客户A", "老客户B", "老客户C", "老客户D", "老客户E", "老客户F", "老客户G", "老客户H", "老客户I", "老客户J"]
products = ["产品A", "产品B", "产品C", "产品D", "产品E"]

raw_data = []
start_date = datetime(2026, 1, 1)

for i in range(200):
    if i < 100:
        customer = random.choice(customers_new)
        order_date = start_date + timedelta(days=random.randint(0, 100))
    else:
        customer = random.choice(customers_old)
        order_date = start_date + timedelta(days=random.randint(0, 100))
    
    amount = round(random.uniform(100, 5000), 2)
    raw_data.append({
        "日期": order_date.strftime("%Y-%m-%d"),
        "单据编号": f"DD{order_date.strftime('%Y%m%d')}{str(i).zfill(4)}",
        "在线订单跟踪号": f"TRK{str(i).zfill(6)}",
        "客户": customer,
        "货号": random.choice(products),
        "金额": amount,
        "金额（本位币）": amount,
        "价税合计（本位币）": round(amount * 1.13, 2)
    })

df_raw = pd.DataFrame(raw_data)

df_settings = pd.DataFrame({
    "参数名称": ["新客户积分倍率", "老客户积分倍率", "积分兑换比例"],
    "参数值": [2, 1, 0.3],
    "说明": ["新客户享受双倍积分", "老客户享受普通积分", "1积分=0.3元"]
})

df_exchange = pd.DataFrame({
    "兑换编号": ["DH001", "DH002", "DH003", "DH004", "DH005"],
    "客户": ["老客户A", "新客户B", "老客户C", "新客户D", "老客户E"],
    "兑换日期": ["2026-06-01", "2026-06-05", "2026-06-10", "2026-06-15", "2026-06-20"],
    "兑换积分数量": [5000, 3000, 8000, 4500, 6000],
    "兑换金额": [1500, 900, 2400, 1350, 1800],
    "兑换方式": ["线上兑换", "线下兑换", "线上兑换", "线上兑换", "线下兑换"],
    "兑换产品": ["礼品卡", "实物礼品", "代金券", "礼品卡", "实物礼品"],
    "操作人员": ["张三", "李四", "张三", "王五", "李四"],
    "备注": ["", "", "", "", ""]
})

with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
    df_raw.to_excel(writer, sheet_name="原始数据", index=False)
    df_settings.to_excel(writer, sheet_name="测算", index=False)
    df_exchange.to_excel(writer, sheet_name="积分兑换记录", index=False)

print(f"Excel文件已创建: {excel_path}")
