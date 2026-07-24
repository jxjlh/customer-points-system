import streamlit as st
import os
import sys
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.excel_reader import ExcelReader
from modules.customer_analysis import CustomerAnalysis
from modules.point_calculation import PointCalculation
from modules.database import DatabaseManager

DEFAULT_EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "2026春夏促销活动清单-7.16.xlsx")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "points.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

def load_data(excel_path=None, file_bytes=None):
    try:
        if file_bytes:
            excel_reader = ExcelReader(file_bytes=file_bytes)
        elif excel_path:
            excel_reader = ExcelReader(excel_path=excel_path)
        else:
            excel_reader = ExcelReader(excel_path=DEFAULT_EXCEL_PATH)
        
        excel_reader.read_excel()
        
        df_raw = excel_reader.get_raw_data()
        settings = excel_reader.get_settings()
        df_exchange = excel_reader.get_exchange_records()
        column_mapping = excel_reader.get_column_mapping()
        
        customer_analysis = CustomerAnalysis(settings)
        df_customer = customer_analysis.analyze_customer_attributes(df_raw, column_mapping)
        
        point_calculation = PointCalculation(settings)
        df_points = point_calculation.calculate_points(df_raw, df_customer, column_mapping)
        df_account = point_calculation.calculate_point_account(df_points, df_exchange)
        
        db_manager = DatabaseManager(DB_PATH)
        db_manager.sync_exchange_from_excel(df_exchange)
        
        return {
            "excel_reader": excel_reader,
            "df_raw": df_raw,
            "df_customer": df_customer,
            "df_points": df_points,
            "df_exchange": df_exchange,
            "df_account": df_account,
            "settings": settings,
            "column_mapping": column_mapping,
            "customer_analysis": customer_analysis,
            "point_calculation": point_calculation,
            "db_manager": db_manager,
            "update_time": excel_reader.get_update_time(),
            "file_name": excel_reader.get_file_name(),
            "excel_path": excel_reader.excel_path
        }
    except Exception as e:
        st.error(f"加载数据失败: {str(e)}")
        return None

def init_session_state():
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "data" not in st.session_state:
        st.session_state.data = None
    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None
    if "edited_raw_data" not in st.session_state:
        st.session_state.edited_raw_data = None
    if "edited_exchange_data" not in st.session_state:
        st.session_state.edited_exchange_data = None
    if "last_save_path" not in st.session_state:
        st.session_state.last_save_path = None

def main():
    st.set_page_config(
        page_title="客户积分智能分析系统",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    authenticator.login(location="main")
    
    if st.session_state.get('authentication_status') == False:
        st.error("用户名或密码错误")
        return
    
    if st.session_state.get('authentication_status') == None:
        st.warning("请输入用户名和密码")
        return
    
    if st.session_state.get('authentication_status'):
        st.sidebar.title("客户积分智能分析系统")
        authenticator.logout("退出登录", "sidebar")
        st.sidebar.write(f"欢迎回来, **{st.session_state['name']}**")
        
        uploaded_file = st.sidebar.file_uploader("上传Excel文件", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            st.session_state.uploaded_file = uploaded_file.getvalue()
            with st.spinner("正在解析上传的文件..."):
                st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file)
                st.session_state.data_loaded = True
                st.session_state.refresh_key += 1
            st.success("文件上传成功！")
        
        if st.sidebar.button("🔄 刷新数据"):
            with st.spinner("正在刷新数据..."):
                if st.session_state.uploaded_file:
                    st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file)
                elif st.session_state.get("last_save_path"):
                    st.session_state.data = load_data(excel_path=st.session_state["last_save_path"])
                else:
                    st.session_state.data = load_data()
                st.session_state.data_loaded = True
                st.session_state.refresh_key += 1
            st.success("数据刷新成功！")
        
        if not st.session_state.data_loaded or st.session_state.data is None:
            with st.spinner("正在加载数据..."):
                if st.session_state.get("last_save_path"):
                    st.session_state.data = load_data(excel_path=st.session_state["last_save_path"])
                else:
                    st.session_state.data = load_data()
                st.session_state.data_loaded = True
        
        data = st.session_state.data
        
        if data is None:
            st.warning("无法加载数据，请上传Excel文件或检查文件格式是否正确。")
            return
        
        update_time = data["update_time"]
        file_name = data["file_name"]
        
        st.sidebar.markdown(f"""
        **数据更新时间**: {update_time}
        
        **当前文件**: {file_name}
        """)
        
        menu_options = [
            "🏠 原始数据分析",
            "👥 客户属性分析",
            "📈 积分产生分析",
            "💳 积分兑换分析",
            "💰 积分余额查询",
            "📝 手动录入",
            "📋 数据管理"
        ]
        
        selected_menu = st.sidebar.radio("功能菜单", menu_options)
        
        if selected_menu == "🏠 原始数据分析":
            show_dashboard(data)
        elif selected_menu == "👥 客户属性分析":
            show_customer_analysis(data)
        elif selected_menu == "📈 积分产生分析":
            show_points_analysis(data)
        elif selected_menu == "💳 积分兑换分析":
            show_exchange_analysis(data)
        elif selected_menu == "💰 积分余额查询":
            show_balance_query(data)
        elif selected_menu == "📝 手动录入":
            show_manual_entry(data)
        elif selected_menu == "📋 数据管理":
            show_data_management(data)

def show_dashboard(data):
    st.title("原始数据分析")
    
    df_raw = data["df_raw"]
    column_mapping = data["column_mapping"]
    
    if df_raw is None or df_raw.empty:
        st.warning("没有原始数据")
        return
    
    date_col = column_mapping.get("date")
    customer_col = column_mapping.get("customer")
    amount_col = column_mapping.get("amount_cny", column_mapping.get("amount"))
    
    if not date_col or not customer_col:
        st.warning("无法识别日期或客户字段")
        return
    
    df_raw[date_col] = pd.to_datetime(df_raw[date_col], errors="coerce")
    
    total_orders = len(df_raw)
    total_customers = df_raw[customer_col].nunique()
    total_amount = df_raw[amount_col].sum() if amount_col else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总订单数", total_orders)
    with col2:
        st.metric("总客户数", total_customers)
    with col3:
        st.metric("总销售金额", f"¥{total_amount:,.2f}")
    
    st.subheader("销售趋势")
    df_trend = df_raw.copy()
    df_trend["月份"] = df_trend[date_col].dt.to_period("M")
    sales_trend = df_trend.groupby("月份").agg(
        订单数=("日期", "count"),
        销售额=(amount_col, "sum")
    ).reset_index()
    sales_trend["月份"] = sales_trend["月份"].astype(str)
    
    fig_trend = px.line(sales_trend, x="月份", y="销售额", 
                        title="销售趋势折线图",
                        labels={"销售额": "销售额(元)"},
                        template="plotly_white")
    st.plotly_chart(fig_trend, width="stretch")
    
    st.subheader("客户销售TOP10")
    customer_sales = df_trend.groupby(customer_col).agg(
        销售金额=(amount_col, "sum"),
        订单数=("日期", "count")
    ).reset_index().sort_values("销售金额", ascending=False).head(10)
    
    fig_customer = px.bar(customer_sales, x=customer_col, y="销售金额",
                          title="客户销售TOP10柱状图",
                          labels={"销售金额": "销售金额(元)"},
                          template="plotly_white",
                          text_auto=True)
    st.plotly_chart(fig_customer, width="stretch")
    
    st.subheader("产品销售排行")
    product_col = column_mapping.get("product")
    if product_col:
        product_sales = df_trend.groupby(product_col).agg(
            销售金额=(amount_col, "sum"),
            订单数=("日期", "count")
        ).reset_index().sort_values("销售金额", ascending=False)
        
        fig_product = px.bar(product_sales, x=product_col, y="销售金额",
                             title="产品销售排行",
                             labels={"销售金额": "销售金额(元)"},
                             template="plotly_white",
                             text_auto=True)
        st.plotly_chart(fig_product, width="stretch")
    
    st.subheader("原始数据表")
    
    search_text = st.text_input("搜索", "")
    if search_text:
        mask = df_raw.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)
        df_display = df_raw[mask]
    else:
        df_display = df_raw
    
    st.dataframe(df_display, width="stretch", height=400)

def show_customer_analysis(data):
    st.title("客户属性分析")
    
    df_customer = data["df_customer"]
    customer_analysis = data["customer_analysis"]
    
    if df_customer is None or df_customer.empty:
        st.warning("没有客户数据")
        return
    
    new_count = customer_analysis.get_new_customer_count(df_customer)
    old_count = customer_analysis.get_old_customer_count(df_customer)
    new_ratio = customer_analysis.get_new_customer_ratio(df_customer)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("新客户数量", new_count)
    with col2:
        st.metric("老客户数量", old_count)
    with col3:
        st.metric("新客户占比", f"{new_ratio}%")
    
    st.subheader("新老客户比例")
    pie_data = pd.DataFrame({
        "客户属性": ["新客户", "老客户"],
        "数量": [new_count, old_count]
    })
    fig_pie = px.pie(pie_data, values="数量", names="客户属性",
                     title="新老客户比例饼图",
                     color_discrete_map={"新客户": "#10B981", "老客户": "#3B82F6"},
                     template="plotly_white")
    st.plotly_chart(fig_pie, width="stretch")
    
    st.subheader("客户价值排行TOP10")
    value_rank = customer_analysis.get_customer_value_rank(df_customer, 10)
    
    fig_value = px.bar(value_rank, x="客户", y="累计销售金额",
                       title="客户价值排行",
                       labels={"累计销售金额": "累计销售金额(元)"},
                       template="plotly_white",
                       text_auto=True)
    st.plotly_chart(fig_value, width="stretch")
    
    st.subheader("客户订单次数分析")
    frequency = customer_analysis.get_customer_order_frequency(df_customer.copy())
    
    fig_freq = px.bar(frequency, x="订单频次区间", y="客户数量",
                      title="客户订单频次分布",
                      labels={"客户数量": "客户数量"},
                      template="plotly_white",
                      text_auto=True)
    st.plotly_chart(fig_freq, width="stretch")
    
    st.subheader("客户属性明细表")
    st.dataframe(df_customer, width="stretch", height=400)

def show_points_analysis(data):
    st.title("积分产生分析")
    
    df_points = data["df_points"]
    point_calculation = data["point_calculation"]
    
    if df_points is None or df_points.empty:
        st.warning("没有积分数据")
        return
    
    total_points = point_calculation.get_total_points(df_points)
    total_value = point_calculation.get_total_point_value(df_points)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("累计产生积分", total_points)
    with col2:
        st.metric("积分总价值", f"¥{total_value:,.2f}")
    
    st.subheader("客户积分排行榜TOP20")
    top_customers = point_calculation.get_top_customers_by_points(df_points, 20)
    
    fig_top = px.bar(top_customers, x="客户", y="累计积分",
                     title="客户积分排行榜TOP20",
                     labels={"累计积分": "累计积分"},
                     template="plotly_white",
                     text_auto=True)
    st.plotly_chart(fig_top, width="stretch")
    
    st.subheader("积分产生趋势")
    points_trend = point_calculation.get_points_trend(df_points)
    
    if not points_trend.empty:
        fig_trend = px.line(points_trend, x="月份", y="积分数量",
                            title="积分产生趋势",
                            labels={"积分数量": "积分数量"},
                            template="plotly_white")
        st.plotly_chart(fig_trend, width="stretch")
    
    st.subheader("积分明细表")
    st.dataframe(df_points, width="stretch", height=400)

def show_exchange_analysis(data):
    st.title("积分兑换分析")
    
    df_exchange = data["df_exchange"]
    point_calculation = data["point_calculation"]
    
    if df_exchange is None or df_exchange.empty:
        st.warning("没有兑换记录")
        return
    
    total_exchanged_points = point_calculation.get_total_exchanged_points(df_exchange)
    total_exchanged_amount = point_calculation.get_total_exchanged_amount(df_exchange)
    exchange_customer_count = point_calculation.get_exchange_customer_count(df_exchange)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("累计兑换积分", total_exchanged_points)
    with col2:
        st.metric("兑换金额", f"¥{total_exchanged_amount:,.2f}")
    with col3:
        st.metric("兑换客户数量", exchange_customer_count)
    
    st.subheader("积分兑换趋势")
    exchange_trend = point_calculation.get_exchange_trend(df_exchange)
    
    if not exchange_trend.empty:
        fig_trend = px.line(exchange_trend, x="月份", y="兑换积分",
                            title="积分兑换趋势",
                            labels={"兑换积分": "兑换积分数量"},
                            template="plotly_white")
        st.plotly_chart(fig_trend, width="stretch")
    
    st.subheader("客户兑换排行")
    exchange_rank = point_calculation.get_exchange_customer_rank(df_exchange, 10)
    
    if not exchange_rank.empty:
        fig_rank = px.bar(exchange_rank, x="客户", y="累计兑换积分",
                          title="客户兑换排行TOP10",
                          labels={"累计兑换积分": "累计兑换积分"},
                          template="plotly_white",
                          text_auto=True)
        st.plotly_chart(fig_rank, width="stretch")
    
    st.subheader("兑换明细表")
    st.dataframe(df_exchange, width="stretch", height=400)

def show_balance_query(data):
    st.title("积分余额查询")
    
    df_account = data["df_account"]
    df_customer = data["df_customer"]
    df_points = data["df_points"]
    
    if df_account is None or df_account.empty:
        st.warning("没有积分账户数据")
        return
    
    customer_names = sorted(df_account["客户"].unique().tolist())
    
    selected_customer = st.selectbox("选择客户", customer_names)
    
    if selected_customer:
        customer_data = df_account[df_account["客户"] == selected_customer]
        
        if not customer_data.empty:
            row = customer_data.iloc[0]
            
            customer_attr = ""
            if df_customer is not None and not df_customer.empty:
                attr_data = df_customer[df_customer["客户"] == selected_customer]
                if not attr_data.empty:
                    customer_attr = attr_data.iloc[0]["客户属性"]
            
            st.subheader(f"客户信息 - {selected_customer}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**客户属性**: {customer_attr}")
                st.info(f"**累计获得积分**: {int(row['累计获得积分'])}")
                st.info(f"**已兑换积分**: {int(row['累计兑换积分'])}")
            with col2:
                st.success(f"**剩余积分**: {int(row['剩余积分'])}")
                st.success(f"**剩余积分价值**: ¥{row['剩余积分价值']:,.2f}")
                st.info(f"**兑换次数**: {int(row['兑换次数'])}")
            
            if row.get("最近兑换时间"):
                st.info(f"**最近兑换时间**: {row['最近兑换时间']}")
            
            st.subheader("积分分布")
            pie_data = pd.DataFrame({
                "分类": ["累计获得积分", "已兑换积分", "剩余积分"],
                "数量": [row['累计获得积分'], row['累计兑换积分'], row['剩余积分']],
                "颜色": ["#10B981", "#EF4444", "#3B82F6"]
            })
            
            fig_pie = px.pie(pie_data, values="数量", names="分类",
                             title="积分分布饼图",
                             color_discrete_map={"累计获得积分": "#10B981", 
                                                "已兑换积分": "#EF4444", 
                                                "剩余积分": "#3B82F6"},
                             template="plotly_white",
                             hole=0.4)
            st.plotly_chart(fig_pie, width="stretch")
            
            st.subheader("积分余额进度")
            total_points = row['累计获得积分']
            remaining_points = row['剩余积分']
            progress_percent = (remaining_points / total_points * 100) if total_points > 0 else 0
            
            st.progress(int(progress_percent))
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between;">
                <span>已消耗: {total_points - remaining_points} 积分</span>
                <span>剩余: {remaining_points} 积分</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.subheader("客户积分排名")
            df_account_sorted = df_account.sort_values("剩余积分", ascending=False).reset_index(drop=True)
            customer_rank = df_account_sorted[df_account_sorted["客户"] == selected_customer].index[0] + 1
            total_customers = len(df_account_sorted)
            
            top5 = df_account_sorted.head(5)
            fig_rank = px.bar(top5, x="客户", y="剩余积分",
                              title=f"积分余额TOP5排名（当前客户排名第 {customer_rank} 位）",
                              labels={"剩余积分": "剩余积分"},
                              template="plotly_white",
                              color="客户",
                              color_discrete_sequence=["#3B82F6" if c == selected_customer else "#9CA3AF" for c in top5["客户"]],
                              text_auto=True)
            st.plotly_chart(fig_rank, width="stretch")
            
            if df_points is not None and not df_points.empty:
                st.subheader("积分获取趋势")
                customer_points = df_points[df_points["客户"] == selected_customer]
                if not customer_points.empty:
                    customer_points["订单日期"] = pd.to_datetime(customer_points["订单日期"], errors="coerce")
                    customer_points = customer_points.dropna(subset=["订单日期"])
                    customer_points["月份"] = customer_points["订单日期"].dt.to_period("M")
                    
                    trend = customer_points.groupby("月份").agg(
                        获得积分=("最终积分", "sum"),
                        订单数=("订单编号", "count")
                    ).reset_index()
                    trend["月份"] = trend["月份"].astype(str)
                    
                    fig_trend = px.line(trend, x="月份", y="获得积分",
                                        title="每月获得积分趋势",
                                        labels={"获得积分": "获得积分"},
                                        template="plotly_white",
                                        markers=True)
                    st.plotly_chart(fig_trend, width="stretch")
        else:
            st.warning("未找到该客户的积分账户信息")

def show_manual_entry(data):
    st.title("手动录入")
    
    tab1, tab2 = st.tabs(["📋 录入订单", "🎫 录入兑换记录"])
    
    with tab1:
        st.subheader("录入新订单")
        
        df_raw = data["df_raw"]
        column_mapping = data["column_mapping"]
        
        date_col = column_mapping.get("date")
        customer_col = column_mapping.get("customer")
        amount_col = column_mapping.get("amount_cny", column_mapping.get("amount"))
        
        with st.form("order_form"):
            order_date = st.date_input("订单日期", datetime.now())
            order_no = st.text_input("单据编号")
            customer = st.text_input("客户名称")
            amount = st.number_input("销售金额", min_value=0.0, step=0.01)
            
            submitted = st.form_submit_button("提交订单")
            
            if submitted:
                if not customer or amount <= 0:
                    st.error("请填写客户名称和销售金额")
                else:
                    new_order = {
                        date_col: order_date.strftime("%Y-%m-%d"),
                        customer_col: customer,
                        amount_col: amount
                    }
                    
                    if "订单编号" in df_raw.columns:
                        new_order["订单编号"] = order_no
                    
                    data["excel_reader"].add_raw_data(new_order)
                    
                    st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                    st.session_state.data_loaded = True
                    st.session_state.refresh_key += 1
                    
                    st.success("订单录入成功！")
    
    with tab2:
        st.subheader("录入积分兑换记录")
        
        tab2_1, tab2_2 = st.tabs(["📝 单个录入", "🎫 批量录入"])
        
        with tab2_1:
            st.subheader("单个录入兑换记录")
            
            df_account = data["df_account"]
            customer_options = []
            if df_account is not None and not df_account.empty:
                customer_options = sorted(df_account["客户"].unique().tolist())
            
            with st.form("exchange_form"):
                exchange_no = st.text_input("兑换编号")
                
                search_customer = st.text_input("🔍 搜索客户")
                filtered_customers = [c for c in customer_options if search_customer.lower() in str(c).lower()] if search_customer else customer_options
                
                if filtered_customers:
                    customer = st.selectbox("选择客户", filtered_customers)
                else:
                    customer = st.text_input("客户名称")
                
                exchange_date = st.date_input("兑换日期", datetime.now())
                points_exchanged = st.number_input("兑换积分数量", min_value=0, step=1)
                exchange_amount = st.number_input("兑换金额", min_value=0.0, step=0.01)
                exchange_method = st.selectbox("兑换方式", ["线上兑换", "线下兑换"])
                exchange_product = st.text_input("兑换产品")
                operator = st.text_input("操作人员")
                remark = st.text_area("备注")
                
                submitted = st.form_submit_button("提交兑换记录")
                
                if submitted:
                    if not customer or points_exchanged <= 0:
                        st.error("请填写客户名称和兑换积分数量")
                    else:
                        new_exchange = {
                            "兑换编号": exchange_no,
                            "客户": customer,
                            "兑换日期": exchange_date.strftime("%Y-%m-%d"),
                            "兑换积分数量": points_exchanged,
                            "兑换金额": exchange_amount,
                            "兑换方式": exchange_method,
                            "兑换产品": exchange_product,
                            "操作人员": operator,
                            "备注": remark
                        }
                        
                        data["excel_reader"].add_exchange_record(new_exchange)
                        
                        st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                        st.session_state.data_loaded = True
                        st.session_state.refresh_key += 1
                        
                        st.success("兑换记录录入成功！")
        
        with tab2_2:
            st.subheader("批量录入兑换记录")
            
            df_account = data["df_account"]
            customer_options = []
            if df_account is not None and not df_account.empty:
                customer_options = sorted(df_account["客户"].unique().tolist())
            
            search_customer = st.text_input("🔍 搜索客户")
            filtered_customers = [c for c in customer_options if search_customer.lower() in str(c).lower()] if search_customer else customer_options
            
            selected_customers = st.multiselect("选择多个客户（可搜索）", filtered_customers)
            
            if selected_customers:
                st.info(f"已选择 {len(selected_customers)} 个客户")
                st.write("客户列表: " + ", ".join(str(c) for c in selected_customers))
                
                with st.form("batch_exchange_form_manual"):
                    exchange_no = st.text_input("兑换编号")
                    exchange_date = st.date_input("兑换日期", datetime.now())
                    points_exchanged = st.number_input("兑换积分数量（每个客户）", min_value=0, step=1)
                    exchange_amount = st.number_input("兑换金额（每个客户）", min_value=0.0, step=0.01)
                    exchange_method = st.selectbox("兑换方式", ["线上兑换", "线下兑换"])
                    exchange_product = st.text_input("兑换产品")
                    operator = st.text_input("操作人员")
                    remark = st.text_area("备注")
                    
                    submitted = st.form_submit_button("提交批量兑换记录")
                    
                    if submitted:
                        if not exchange_no or points_exchanged <= 0:
                            st.error("请填写兑换编号和兑换积分数量")
                        else:
                            total_created = 0
                            for customer in selected_customers:
                                new_exchange = {
                                    "兑换编号": exchange_no,
                                    "客户": customer,
                                    "兑换日期": exchange_date.strftime("%Y-%m-%d"),
                                    "兑换积分数量": points_exchanged,
                                    "兑换金额": exchange_amount,
                                    "兑换方式": exchange_method,
                                    "兑换产品": exchange_product,
                                    "操作人员": operator,
                                    "备注": remark
                                }
                                data["excel_reader"].add_exchange_record(new_exchange)
                                total_created += 1
                            
                            st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                            st.session_state.data_loaded = True
                            st.session_state.refresh_key += 1
                            
                            st.success(f"已为 {total_created} 个客户创建兑换记录！")
            else:
                st.warning("请选择需要兑换积分的客户")

def show_data_management(data):
    st.title("数据管理")
    
    tab1, tab2 = st.tabs(["📊 原始数据", "🎫 积分兑换记录"])
    
    with tab1:
        st.subheader("原始数据 - 在线编辑")
        
        df_raw = data["df_raw"]
        column_mapping = data["column_mapping"]
        customer_col = column_mapping.get("customer")
        amount_col = column_mapping.get("amount_cny", column_mapping.get("amount"))
        
        if df_raw is None or df_raw.empty:
            st.warning("没有原始数据")
            return
        
        search_text = st.text_input("🔍 搜索原始数据", "")
        if search_text:
            mask = df_raw.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)
            df_display = df_raw[mask]
        else:
            df_display = df_raw
        
        gb = GridOptionsBuilder.from_dataframe(df_display)
        gb.configure_default_column(editable=True, resizable=True, sortable=True, filter=True)
        gb.configure_selection(selection_mode="multiple", use_checkbox=True)
        
        for col in df_display.columns:
            gb.configure_column(col, autoWidth=True, minWidth=80, maxWidth=200)
        
        grid_options = gb.build()
        
        st.info("💡 提示：勾选左侧复选框可多选，双击单元格即可编辑，编辑完成后点击下方的【保存修改】按钮")
        
        grid_response = AgGrid(
            df_display,
            gridOptions=grid_options,
            height=500,
            width="stretch",
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            fit_columns_on_grid_load=True,
            custom_css="""
                .ag-header-cell-label {
                    justify-content: center !important;
                }
                .ag-header-cell {
                    text-align: center !important;
                    white-space: normal !important;
                    height: auto !important;
                }
                .ag-header-row {
                    height: auto !important;
                }
            """
        )
        
        selected_rows = grid_response.get("selected_rows", [])
        updated_df = grid_response["data"]
        updated_df = pd.DataFrame(updated_df)
        
        if selected_rows:
            st.subheader(f"已选中 {len(selected_rows)} 条记录")
            selected_df = pd.DataFrame(selected_rows)
            
            if customer_col:
                unique_customers = selected_df[customer_col].unique()
                st.info(f"涉及客户: {', '.join(str(c) for c in unique_customers)}")
            
            if amount_col and amount_col in selected_df.columns:
                total_amount = selected_df[amount_col].sum()
                st.info(f"总金额: ¥{total_amount:,.2f}")
            
            action_col1, action_col2, action_col3 = st.columns(3)
            with action_col1:
                if st.button("🎫 批量兑换积分"):
                    st.session_state["selected_for_exchange"] = selected_df
                    st.session_state["exchange_mode"] = "batch"
            
            if st.session_state.get("exchange_mode") == "batch":
                st.subheader("批量兑换积分")
                st.write(f"正在为以下客户兑换积分：")
                
                if customer_col:
                    unique_customers = selected_df[customer_col].unique()
                    st.info(f"客户列表: {', '.join(str(c) for c in unique_customers)}")
                
                with st.form("batch_exchange_form"):
                    exchange_no = st.text_input("兑换编号")
                    exchange_date = st.date_input("兑换日期", datetime.now())
                    exchange_method = st.selectbox("兑换方式", ["线上兑换", "线下兑换"])
                    exchange_product = st.text_input("兑换产品")
                    operator = st.text_input("操作人员")
                    remark = st.text_area("备注")
                    
                    points_input = st.number_input("兑换积分数量", min_value=0, step=1)
                    exchange_amount = st.number_input("兑换金额", min_value=0.0, step=0.01)
                    
                    submitted = st.form_submit_button("确认兑换")
                    
                    if submitted:
                        if not exchange_no or points_input <= 0:
                            st.error("请填写兑换编号和兑换积分数量")
                        else:
                            for customer in unique_customers:
                                new_exchange = {
                                    "兑换编号": exchange_no,
                                    "客户": customer,
                                    "兑换日期": exchange_date.strftime("%Y-%m-%d"),
                                    "兑换积分数量": points_input,
                                    "兑换金额": exchange_amount,
                                    "兑换方式": exchange_method,
                                    "兑换产品": exchange_product,
                                    "操作人员": operator,
                                    "备注": remark
                                }
                                data["excel_reader"].add_exchange_record(new_exchange)
                            
                            st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                            st.session_state.data_loaded = True
                            st.session_state.refresh_key += 1
                            st.session_state["exchange_mode"] = None
                            st.success(f"已为 {len(unique_customers)} 个客户创建兑换记录！")
            
            with action_col2:
                if st.button("🗑️ 批量删除"):
                    st.session_state["delete_confirm_items"] = len(selected_rows)
                    st.session_state["delete_confirm_df"] = selected_df
                    st.session_state["delete_confirm_type"] = "raw"
            
            if st.session_state.get("delete_confirm_type") == "raw":
                with st.expander(f"⚠️ 确认删除 {st.session_state.get('delete_confirm_items', 0)} 条记录？", expanded=True):
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("✅ 确认删除", key="confirm_delete_btn"):
                            selected_df = st.session_state.get("delete_confirm_df")
                            df_raw = df_raw[~df_raw.isin(selected_df.to_dict('records')).all(axis=1)]
                            data["excel_reader"].update_raw_data(df_raw)
                            st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                            st.session_state.data_loaded = True
                            st.session_state.refresh_key += 1
                            st.success(f"已删除 {st.session_state.get('delete_confirm_items', 0)} 条记录！")
                            st.session_state["delete_confirm_type"] = None
                    with col_conf2:
                        if st.button("❌ 取消", key="cancel_delete_btn"):
                            st.session_state["delete_confirm_type"] = None
            
            with action_col3:
                excel_buffer = BytesIO()
                selected_df.to_excel(excel_buffer, index=False, sheet_name="选中记录")
                excel_buffer.seek(0)
                st.download_button(
                    label="📋 导出选中记录",
                    data=excel_buffer,
                    file_name=f"selected_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        col_save1, col_save2 = st.columns([1, 2])
        with col_save1:
            default_save_path = st.session_state.get("last_save_path", data.get("excel_path", r"C:\Users\Admin\Desktop\test\customer_updated.xlsx"))
            save_path = st.text_input("保存路径", value=default_save_path)
        
        with col_save2:
            if st.button("💾 保存修改到Excel"):
                try:
                    if not save_path:
                        save_path = r"C:\Users\Admin\Desktop\test\customer_updated.xlsx"
                    
                    data["excel_reader"].update_raw_data(updated_df)
                    data["excel_reader"].save_excel(save_path)
                    st.success(f"原始数据已保存到: {save_path}")
                    
                    st.session_state.last_save_path = save_path
                    st.session_state.data = load_data(excel_path=save_path)
                    st.session_state.data_loaded = True
                    st.session_state.refresh_key += 1
                    st.session_state.uploaded_file = None
                    
                    st.success("数据已更新，所有分析图表将自动刷新！")
                except Exception as e:
                    st.error(f"保存失败: {str(e)}")
    
    with tab2:
        st.subheader("积分兑换记录 - 在线编辑")
        
        df_exchange = data["df_exchange"]
        
        if df_exchange is None or df_exchange.empty:
            st.warning("没有兑换记录")
            return
        
        search_text = st.text_input("🔍 搜索兑换记录", "")
        if search_text:
            mask = df_exchange.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any(axis=1)
            df_display = df_exchange[mask]
        else:
            df_display = df_exchange
        
        gb = GridOptionsBuilder.from_dataframe(df_display)
        gb.configure_default_column(editable=True, resizable=True, sortable=True, filter=True)
        gb.configure_selection(selection_mode="multiple", use_checkbox=True)
        
        for col in df_display.columns:
            gb.configure_column(col, autoWidth=True, minWidth=80, maxWidth=200)
        
        grid_options = gb.build()
        
        st.info("💡 提示：勾选左侧复选框可多选，双击单元格即可编辑，编辑完成后点击下方的【保存修改】按钮")
        
        grid_response = AgGrid(
            df_display,
            gridOptions=grid_options,
            height=500,
            width="stretch",
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            fit_columns_on_grid_load=True,
            custom_css="""
                .ag-header-cell-label {
                    justify-content: center !important;
                }
                .ag-header-cell {
                    text-align: center !important;
                    white-space: normal !important;
                    height: auto !important;
                }
                .ag-header-row {
                    height: auto !important;
                }
            """
        )
        
        selected_rows = grid_response.get("selected_rows", [])
        updated_df = grid_response["data"]
        updated_df = pd.DataFrame(updated_df)
        
        if selected_rows:
            st.subheader(f"已选中 {len(selected_rows)} 条兑换记录")
            selected_df = pd.DataFrame(selected_rows)
            
            total_points = selected_df["兑换积分数量"].sum() if "兑换积分数量" in selected_df.columns else 0
            total_amount = selected_df["兑换金额"].sum() if "兑换金额" in selected_df.columns else 0
            
            st.info(f"总兑换积分: {total_points}")
            st.info(f"总兑换金额: ¥{total_amount:,.2f}")
            
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("🗑️ 批量删除"):
                    st.session_state["delete_confirm_items"] = len(selected_rows)
                    st.session_state["delete_confirm_df"] = selected_df
                    st.session_state["delete_confirm_type"] = "exchange"
            
            if st.session_state.get("delete_confirm_type") == "exchange":
                with st.expander(f"⚠️ 确认删除 {st.session_state.get('delete_confirm_items', 0)} 条兑换记录？", expanded=True):
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("✅ 确认删除", key="confirm_delete_exchange_btn"):
                            selected_df = st.session_state.get("delete_confirm_df")
                            df_exchange = df_exchange[~df_exchange.isin(selected_df.to_dict('records')).all(axis=1)]
                            data["excel_reader"].update_exchange_records(df_exchange)
                            st.session_state.data = load_data(file_bytes=st.session_state.uploaded_file) if st.session_state.uploaded_file else load_data()
                            st.session_state.data_loaded = True
                            st.session_state.refresh_key += 1
                            st.success(f"已删除 {st.session_state.get('delete_confirm_items', 0)} 条兑换记录！")
                            st.session_state["delete_confirm_type"] = None
                    with col_conf2:
                        if st.button("❌ 取消", key="cancel_delete_exchange_btn"):
                            st.session_state["delete_confirm_type"] = None
            
            with action_col2:
                excel_buffer = BytesIO()
                selected_df.to_excel(excel_buffer, index=False, sheet_name="选中兑换记录")
                excel_buffer.seek(0)
                st.download_button(
                    label="📋 导出选中记录",
                    data=excel_buffer,
                    file_name=f"selected_exchanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        col_save1, col_save2 = st.columns([1, 2])
        with col_save1:
            default_save_path = st.session_state.get("last_save_path", data.get("excel_path", r"C:\Users\Admin\Desktop\test\customer_updated.xlsx"))
            save_path = st.text_input("保存路径", value=default_save_path)
        
        with col_save2:
            if st.button("💾 保存兑换记录到Excel"):
                try:
                    if not save_path:
                        save_path = r"C:\Users\Admin\Desktop\test\customer_updated.xlsx"
                    
                    data["excel_reader"].update_exchange_records(updated_df)
                    data["excel_reader"].save_excel(save_path)
                    st.success(f"兑换记录已保存到: {save_path}")
                    
                    st.session_state.last_save_path = save_path
                    st.session_state.data = load_data(excel_path=save_path)
                    st.session_state.data_loaded = True
                    st.session_state.refresh_key += 1
                    st.session_state.uploaded_file = None
                    
                    st.success("数据已更新，所有分析图表将自动刷新！")
                except Exception as e:
                    st.error(f"保存失败: {str(e)}")

if __name__ == "__main__":
    main()
