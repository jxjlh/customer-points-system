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
import bcrypt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.excel_reader import ExcelReader
from modules.customer_analysis import CustomerAnalysis
from modules.point_calculation import PointCalculation
from modules.database import DatabaseManager
from modules.invoice_fetcher import InvoiceFetcher
from modules.quotation_ui import show_quotation
from modules.db_manager import get_db_manager

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
        
        db_manager = get_db_manager()
        db_manager.sync_exchange_from_excel(df_exchange)
        
        return {
            "df_raw": df_raw,
            "df_customer": df_customer,
            "df_points": df_points,
            "df_account": df_account,
            "df_exchange": df_exchange,
            "settings": settings,
            "column_mapping": column_mapping,
            "excel_reader": excel_reader
        }
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return None


def show_home(config):
    from modules.theme import apply_all_styles
    from modules.home_cards import show_home_cards
    
    apply_all_styles()
    
    st.title("🏠 澄天小助手")
    
    current_user = st.session_state.get('username')
    is_admin = False
    if current_user and config['credentials']['usernames'].get(current_user, {}).get('role') == 'admin':
        is_admin = True
    
    st.markdown("""
    <div style='
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 30px;
        border-left: 4px solid #667eea;
        animation: fadeInDown 0.8s ease;
    '>
        <h3 style='color: #2c3e50; margin-bottom: 8px;'>👋 欢迎使用澄天小助手</h3>
        <p style='color: #7f8c8d; margin: 0;'>一站式管理您的客户积分、邮件、发票和报价，请选择您需要的功能模块：</p>
    </div>
    """, unsafe_allow_html=True)
    
    cards_config = [
        {
            "icon": "📊",
            "title": "客户积分智能分析",
            "desc": "数据概览 · 客户管理 · 积分管理 · 数据导入 · 报表导出",
            "color_class": "card-blue",
            "key": "btn-customer",
            "session_value": "📊 客户积分智能分析",
            "session_sub": "📈 数据概览",
            "help": "点击进入客户积分智能分析模块"
        },
        {
            "icon": "📧",
            "title": "JAX邮件生成器",
            "desc": "自动生成JAX小鼠发货通知邮件",
            "color_class": "card-green",
            "key": "btn-email",
            "session_value": "📧 JAX邮件生成器",
            "help": "点击进入JAX邮件生成器模块"
        },
        {
            "icon": "🧾",
            "title": "红冲发票自动登记",
            "desc": "自动从邮箱下载并登记电子发票",
            "color_class": "card-orange",
            "key": "btn-invoice",
            "session_value": "🧾 红冲发票自动登记",
            "help": "点击进入红冲发票自动登记模块"
        },
        {
            "icon": "📋",
            "title": "报价助手",
            "desc": "自动查询价格并生成报价单",
            "color_class": "card-purple",
            "key": "btn-quotation",
            "session_value": "📋 报价助手",
            "help": "点击进入报价助手模块"
        }
    ]
    
    if is_admin:
        cards_config.append({
            "icon": "👑",
            "title": "用户管理",
            "desc": "查看所有用户信息和登录状态",
            "color_class": "card-pink",
            "key": "btn-admin",
            "session_value": "👑 用户管理",
            "help": "点击进入用户管理模块"
        })
    
    show_home_cards(cards_config)


def show_dashboard(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_customer = data["df_customer"]
    df_exchange = data["df_exchange"]
    df_account = data["df_account"]
    settings = data["settings"]
    
    st.title("📊 数据概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_points = PointCalculation(settings).get_total_points(df_points)
    total_value = PointCalculation(settings).get_total_point_value(df_points)
    total_exchanged = PointCalculation(settings).get_total_exchanged_points(df_exchange)
    exchange_count = PointCalculation(settings).get_exchange_customer_count(df_exchange)
    
    col1.metric("累计获得积分", f"{total_points:,}")
    col2.metric("积分总价值", f"¥{total_value:,}")
    col3.metric("累计兑换积分", f"{total_exchanged:,}")
    col4.metric("兑换客户数", exchange_count)
    
    col5, col6, col7, col8 = st.columns(4)
    
    new_customers = CustomerAnalysis(settings).get_new_customer_count(df_customer)
    old_customers = CustomerAnalysis(settings).get_old_customer_count(df_customer)
    total_customers = len(df_customer)
    new_ratio = CustomerAnalysis(settings).get_new_customer_ratio(df_customer)
    
    col5.metric("新客户数", new_customers)
    col6.metric("老客户数", old_customers)
    col7.metric("总客户数", total_customers)
    col8.metric("新客户占比", f"{new_ratio}%")
    
    st.subheader("📈 积分趋势分析")
    trend_df = PointCalculation(settings).get_points_trend(df_points)
    
    if not trend_df.empty:
        fig = px.line(trend_df, x="月份", y="积分数量", 
                      title="📉 月度积分获得趋势", 
                      labels={"积分数量": "积分数量", "月份": "月份"},
                      markers=True,
                      color_discrete_sequence=["#667eea"],
                      template="plotly_white")
        fig.update_layout(
            title_font=dict(size=18, color="#333"),
            xaxis_title_font=dict(size=14, color="#666"),
            yaxis_title_font=dict(size=14, color="#666"),
            hovermode="x unified",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=8, symbol="circle"))
        st.plotly_chart(fig, use_container_width=True)
        
        fig2 = px.bar(trend_df, x="月份", y="订单数",
                      title="📊 月度订单数量",
                      labels={"订单数": "订单数", "月份": "月份"},
                      color="订单数",
                      color_continuous_scale="Blues",
                      template="plotly_white")
        fig2.update_layout(
            title_font=dict(size=18, color="#333"),
            xaxis_title_font=dict(size=14, color="#666"),
            yaxis_title_font=dict(size=14, color="#666"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    st.subheader("🏆 客户积分排名")
    top_customers = PointCalculation(settings).get_top_customers_by_points(df_points)
    
    if not top_customers.empty:
        fig4 = px.bar(top_customers, y="客户", x="累计积分",
                      title="🥇 客户积分排名Top20",
                      labels={"累计积分": "累计积分", "客户": "客户名称"},
                      color="累计积分",
                      color_continuous_scale=["#667eea", "#764ba2"],
                      orientation="h",
                      template="plotly_white")
        fig4.update_layout(
            title_font=dict(size=18, color="#333"),
            xaxis_title_font=dict(size=14, color="#666"),
            yaxis_title_font=dict(size=14, color="#666"),
            height=500,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=120, r=50, t=60, b=50)
        )
        fig4.update_traces(
            hovertemplate="客户: %{y}<br>累计积分: %{x:,}",
            marker=dict(line=dict(width=0))
        )
        st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader("📋 客户积分排名详情")
        gb = GridOptionsBuilder.from_dataframe(top_customers)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(top_customers, gridOptions=grid_options, height=300,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("👥 客户属性分布")
    if not df_customer.empty:
        attribute_counts = df_customer["客户属性"].value_counts()
        
        fig3 = px.pie(values=attribute_counts.values, names=attribute_counts.index,
                      title="👨‍👩‍👧‍👦 新老客户分布",
                      hole=0.4,
                      color_discrete_sequence=["#667eea", "#f093fb"],
                      template="plotly_white")
        fig3.update_layout(
            title_font=dict(size=18, color="#333"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        fig3.update_traces(
            hoverinfo="label+percent+value",
            textinfo="label+percent",
            textfont=dict(size=14),
            marker=dict(line=dict(color="#ffffff", width=2))
        )
        st.plotly_chart(fig3, use_container_width=True)


def show_customer_management(data):
    if data is None:
        return
    
    df_customer = data["df_customer"]
    df_account = data["df_account"]
    
    st.title("👥 客户管理")
    
    st.subheader("客户列表")
    if not df_customer.empty:
        gb = GridOptionsBuilder.from_dataframe(df_customer)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_customer, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("客户积分账户")
    if not df_account.empty:
        gb = GridOptionsBuilder.from_dataframe(df_account)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_account, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("客户搜索")
    search_name = st.text_input("输入客户名称搜索")
    
    if search_name:
        filtered = df_customer[df_customer["客户"].str.contains(search_name, na=False)]
        if not filtered.empty:
            st.dataframe(filtered)
        else:
            st.warning("未找到匹配的客户")


def show_point_management(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_exchange = data["df_exchange"]
    settings = data["settings"]
    
    st.title("🏆 积分管理")
    
    st.subheader("积分明细")
    if not df_points.empty:
        gb = GridOptionsBuilder.from_dataframe(df_points)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_points, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("积分兑换记录")
    if not df_exchange.empty:
        gb = GridOptionsBuilder.from_dataframe(df_exchange)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_exchange, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("积分参数设置")
    col1, col2, col3 = st.columns(3)
    
    new_multiplier = col1.number_input("新客户积分倍率", min_value=1, max_value=10, 
                                       value=int(settings.get("新客户积分倍率", 2)))
    old_multiplier = col2.number_input("老客户积分倍率", min_value=1, max_value=10,
                                       value=int(settings.get("老客户积分倍率", 1)))
    exchange_rate = col3.number_input("积分兑换比例", min_value=0.1, max_value=1.0,
                                      value=float(settings.get("积分兑换比例", 0.3)), step=0.1)
    
    if st.button("保存设置"):
        settings["新客户积分倍率"] = new_multiplier
        settings["老客户积分倍率"] = old_multiplier
        settings["积分兑换比例"] = exchange_rate
        st.success("设置已保存")
    
    st.subheader("兑换趋势")
    exchange_trend = PointCalculation(settings).get_exchange_trend(df_exchange)
    
    if not exchange_trend.empty:
        fig = px.line(exchange_trend, x="月份", y="兑换积分",
                      title="月度兑换积分趋势",
                      markers=True)
        st.plotly_chart(fig, use_container_width=True)


def show_data_import():
    st.title("📥 数据导入")
    
    st.subheader("上传Excel文件")
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                data = load_data(file_bytes=uploaded_file.getvalue())
                if data:
                    st.success("数据导入成功！")
                    st.session_state['data'] = data
                    
                    st.subheader("导入数据预览")
                    st.dataframe(data["df_raw"].head(20))
                    
                    st.download_button(
                        label="下载导入的数据",
                        data=uploaded_file.getvalue(),
                        file_name=f"导入数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"数据导入失败: {str(e)}")
    
    st.subheader("使用默认数据")
    if st.button("加载默认数据"):
        with st.spinner("正在加载默认数据..."):
            try:
                data = load_data()
                if data:
                    st.success("默认数据加载成功！")
                    st.session_state['data'] = data
            except Exception as e:
                st.error(f"加载默认数据失败: {str(e)}")


def show_reports(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_customer = data["df_customer"]
    df_exchange = data["df_exchange"]
    settings = data["settings"]
    
    st.title("📝 报表导出")
    
    st.subheader("选择报表类型")
    report_type = st.selectbox("请选择报表类型", [
        "客户积分汇总报表",
        "积分兑换明细报表",
        "客户属性分析报表",
        "积分趋势报表"
    ])
    
    if st.button("生成报表"):
        buffer = BytesIO()
        
        if report_type == "客户积分汇总报表":
            top_customers = PointCalculation(settings).get_top_customers_by_points(df_points)
            
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                top_customers.to_excel(writer, sheet_name="客户积分排名", index=False)
                data["df_account"].to_excel(writer, sheet_name="客户积分账户", index=False)
        
        elif report_type == "积分兑换明细报表":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_exchange.to_excel(writer, sheet_name="积分兑换记录", index=False)
        
        elif report_type == "客户属性分析报表":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_customer.to_excel(writer, sheet_name="客户属性分析", index=False)
        
        elif report_type == "积分趋势报表":
            trend_df = PointCalculation(settings).get_points_trend(df_points)
            exchange_trend = PointCalculation(settings).get_exchange_trend(df_exchange)
            
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                trend_df.to_excel(writer, sheet_name="积分获得趋势", index=False)
                exchange_trend.to_excel(writer, sheet_name="积分兑换趋势", index=False)
        
        buffer.seek(0)
        
        st.download_button(
            label="下载报表",
            data=buffer,
            file_name=f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success("报表生成成功！")


def validate_columns_email(df):
    required_columns = [
        "Job No",
        "Individual PO Number",
        "JAX销售",
        "单位名称",
        "品系号",
        "年龄",
        "性别",
        "数量",
        "发运笼数",
        "隔离后预估笼数",
        "实际出运笼数",
        "提货时间",
        "承运方",
        "城市",
        "收货人",
        "送货地址",
        "拟收货时间",
        "收货备注"
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Excel文件缺少必要的列：{', '.join(missing_columns)}")


def format_date_email(date_value):
    if pd.isna(date_value):
        return ""
    
    if hasattr(date_value, 'month') and hasattr(date_value, 'day'):
        return f"{date_value.month}月{date_value.day}日"
    
    try:
        if isinstance(date_value, str):
            clean_str = date_value.split(' ')[0]
            if '-' in clean_str:
                parts = clean_str.split('-')
                if len(parts) == 3:
                    return f"{int(parts[1])}月{int(parts[2])}日"
            if '/' in clean_str:
                parts = clean_str.split('/')
                if len(parts) == 3 and len(parts[0]) == 4:
                    return f"{int(parts[1])}月{int(parts[2])}日"
                elif len(parts) >= 2:
                    return f"{int(parts[0])}月{int(parts[1])}日"
            date_obj = pd.to_datetime(date_value)
            return f"{date_obj.month}月{date_obj.day}日"
    except (ValueError, TypeError):
        pass
    
    return str(date_value)


def build_strain_list(group_df):
    strain_groups = group_df.groupby("品系号")
    
    strain_items = []
    for strain_id, strain_df in strain_groups:
        strain_parts = []
        
        for _, row in strain_df.iterrows():
            gender = str(row["性别"]).strip().upper()
            quantity = int(row["数量"]) if pd.notna(row["数量"]) else 0
            age = str(row["年龄"]).strip()
            
            gender_text = "雌" if gender in ("雌", "F", "FEMALE") else "雄"
            
            if age.isdigit():
                ship_age = int(age)
                arrive_min = ship_age + 3
                arrive_max = ship_age + 4
                age_text = f"{ship_age}周（到货周龄约{arrive_min}-{arrive_max}周）"
            else:
                age_text = f"{age}周"
            
            strain_parts.append(f"{quantity}{gender_text}-发货周龄{age_text}")
        
        strain_items.append(f"https://www.jax.org/strain/{strain_id}：{'、'.join(strain_parts)}")
    
    return "、".join(strain_items)


def render_mail(receiver, strain_list, ship_date, receive_date):
    mail_body = f"""让您久等了。

您的小鼠{strain_list}，预计于{ship_date}从美国发货，并将在{receive_date}左右的工作日送货。

随附小鼠的鼠房微生物检测报告及隔离场的微生物检测报告，烦请查收。

麻烦您确认小鼠发货周龄及送货时间能否接受？

感谢您的支持并期待您的回复，祝好！"""
    
    return mail_body


def process_excel_email(file_bytes):
    df = pd.read_excel(BytesIO(file_bytes), sheet_name='出隔离场', header=None)
    
    header_row_index = None
    for idx, row in df.iterrows():
        first_cell = str(row.iloc[0]).strip()
        if first_cell == "Job No":
            second_cell = str(row.iloc[1]).strip()
            if second_cell == "Individual PO Number":
                third_cell = str(row.iloc[2]).strip()
                if third_cell == "JAX销售":
                    header_row_index = idx
                    break
    
    if header_row_index is None:
        raise ValueError("未找到表头行，请确保Excel文件包含正确的表头")
    
    new_header = df.iloc[header_row_index].tolist()
    df = df.iloc[header_row_index + 2:]
    df.columns = new_header
    
    df = df.dropna(how='all')
    df = df[~df["Job No"].astype(str).str.contains("Job No|Quantity", na=False)]
    
    validate_columns_email(df)
    
    po_order = df["Individual PO Number"].dropna().unique().tolist()
    
    result_rows = []
    for po_number, group_data in df.groupby("Individual PO Number"):
        first_row = group_data.iloc[0]
        strain_list = build_strain_list(group_data)
        
        receiver = str(first_row["收货人"]).strip() if pd.notna(first_row["收货人"]) else "老师"
        ship_date = format_date_email(first_row["提货时间"])
        receive_date = format_date_email(first_row["拟收货时间"])
        
        mail_body = render_mail(receiver, strain_list, ship_date, receive_date)
        
        full_content = f"JAX小鼠发货通知\n\n{mail_body}"
        result_rows.append({
            "Individual PO Number": po_number,
            "单位名称": first_row["单位名称"],
            "收货人": first_row["收货人"],
            "邮件内容": full_content
        })
    
    result_df = pd.DataFrame(result_rows)
    result_df['po_order'] = result_df['Individual PO Number'].map(lambda x: po_order.index(x) if x in po_order else len(po_order))
    result_df = result_df.sort_values('po_order').drop('po_order', axis=1)
    
    return result_df


def show_email_generator():
    st.title("📧 JAX小鼠发货通知邮件生成器")
    
    st.markdown("""
    **使用说明：**
    1. 上传Excel文件（需包含【出隔离场】Sheet）
    2. 系统自动解析数据并生成邮件内容
    3. 下载生成的邮件结果Excel文件
    """)
    
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                result_df = process_excel_email(uploaded_file.getvalue())
                
                st.success("邮件生成完成！")
                
                st.subheader("生成的邮件列表")
                st.dataframe(result_df, width="stretch", height=400)
                
                excel_buffer = BytesIO()
                result_df.to_excel(excel_buffer, index=False, sheet_name="邮件生成结果")
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 下载邮件结果",
                    data=excel_buffer,
                    file_name=f"JAX邮件生成结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.subheader("邮件预览")
                for _, row in result_df.iterrows():
                    with st.expander(f"📧 {row['Individual PO Number']} - {row['单位名称']}"):
                        st.text(row['邮件内容'])
            
            except Exception as e:
                st.error(f"处理过程中发生错误：\n\n{str(e)}")


def show_user_management(config):
    st.title("👑 用户管理")
    
    st.markdown("""
    **功能说明：**
    管理员可以查看所有用户信息、登录状态和域名信息。
    """)
    
    st.subheader("📊 当前域名")
    domain = st.secrets.get("domain", "customer-points-system.streamlit.app") if hasattr(st, 'secrets') else "customer-points-system.streamlit.app"
    st.info(f"当前域名：{domain}")
    
    st.subheader("👥 用户列表")
    
    users_data = []
    for username, info in config['credentials']['usernames'].items():
        is_logged_in = st.session_state.get('username') == username
        users_data.append({
            "用户名": username,
            "姓名": info.get('name', ''),
            "邮箱": info.get('email', ''),
            "角色": info.get('role', 'user'),
            "登录状态": "✅ 在线" if is_logged_in else "❌ 离线"
        })
    
    if users_data:
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True)
        
        st.subheader("📈 用户统计")
        col1, col2, col3 = st.columns(3)
        col1.metric("总用户数", len(users_data))
        col2.metric("管理员数", len([u for u in users_data if u['角色'] == 'admin']))
        col3.metric("在线用户", len([u for u in users_data if u['登录状态'] == '✅ 在线']))
    else:
        st.warning("暂无用户数据")


def show_invoice_registration():
    st.title("🧾 红冲发票自动登记")
    
    st.markdown("""
    **功能说明：**
    通过IMAP连接邮箱，自动检索发票邮件，下载PDF发票并按规则命名保存到本地目录。
    """)
    
    config = {
        "imap_server": st.text_input("IMAP服务器", "imap.qiye.163.com"),
        "imap_port": st.number_input("IMAP端口", min_value=1, max_value=65535, value=993),
        "email": st.text_input("邮箱地址", "huiyin.guo@ibiologistics.com"),
        "password": st.text_input("客户端授权码", type="password"),
        "sender": st.text_input("发件人过滤", "百旺金穗云dzfpfwpt@hnfapiao.com"),
        "subject_filter": st.text_input("主题关键字", "开具的发票"),
        "output_dir": st.text_input("保存目录", r"C:\Users\Admin\Downloads\发票汇总"),
        "days_back": st.number_input("检索天数", min_value=1, max_value=30, value=5),
    }
    
    dry_run = st.checkbox("试运行（不实际下载）", value=False)

    if st.button("开始下载发票", key="btn-fetch-invoices", type="primary", use_container_width=True):
        db_manager = get_db_manager()
        invoice_fetcher = InvoiceFetcher(config, db_manager=db_manager)

        errors = invoice_fetcher.validate_config()
        if errors:
            for error in errors:
                st.error(error)
            return

        with st.spinner("正在连接邮箱并下载发票..."):
            results, summary = invoice_fetcher.fetch_invoices(days=config["days_back"], dry_run=dry_run)

        if results is None:
            st.error(summary)
            return

        st.success(f"处理完成！共处理 {summary['total_processed']} 封邮件，成功 {summary['success_count']} 封，失败 {summary['failed_count']} 封")

        st.subheader(f"📂 保存目录: {summary['output_dir']}")

        success_results = [r for r in results if r["status"] == "success"]
        failed_results = [r for r in results if r["status"] == "failed"]

        if success_results:
            st.subheader("✅ 成功下载的发票")
            success_df = pd.DataFrame(success_results)
            success_df = success_df[["date", "buyer", "amount", "filename", "source", "folder"]]
            st.dataframe(success_df, use_container_width=True)

        if failed_results:
            st.subheader("❌ 失败的邮件")
            failed_df = pd.DataFrame(failed_results)
            failed_df = failed_df[["date", "subject", "folder", "reason"]]
            st.dataframe(failed_df, use_container_width=True)

    # 历史发票记录（从数据库加载）
    try:
        db_manager = get_db_manager()
        if hasattr(db_manager, 'get_invoice_records'):
            st.header("📚 历史发票记录")

            with st.expander("查看历史发票记录", expanded=False):
                hist_col1, hist_col2 = st.columns(2)
                with hist_col1:
                    hist_status = st.selectbox("状态筛选", ["全部", "success", "failed"], key="hist_inv_status")
                with hist_col2:
                    hist_buyer = st.text_input("购方名称筛选", key="hist_inv_buyer")

                try:
                    history = db_manager.get_invoice_records(
                        status=None if hist_status == "全部" else hist_status,
                        buyer=hist_buyer if hist_buyer else None,
                        limit=100,
                    )
                    if history:
                        hist_df = pd.DataFrame(history)
                        display_cols = ["id", "invoice_date", "subject", "buyer", "amount",
                                        "status", "filename", "source"]
                        available_cols = [c for c in display_cols if c in hist_df.columns]
                        st.dataframe(hist_df[available_cols], use_container_width=True, hide_index=True)
                        st.caption(f"共 {len(history)} 条记录")
                    else:
                        st.info("暂无历史发票记录")
                except Exception as e:
                    st.warning(f"加载历史发票失败: {e}")
    except Exception:
        pass


def main():
    st.set_page_config(
        page_title="澄天小助手",
        page_icon="🐭",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    from modules.theme import apply_all_styles
    apply_all_styles()
    
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    if st.session_state.get('authentication_status') != True:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
            try:
                with open(logo_path, "rb") as f:
                    logo_bytes = f.read()
                st.image(logo_bytes, width=150)
            except Exception as e:
                pass
            st.title("澄天小助手")
            
            login_tab, register_tab = st.tabs(["登录", "注册"])
            
            with login_tab:
                authenticator.login(location="main")
            
            with register_tab:
                st.subheader("用户注册")
                
                new_username = st.text_input("用户名", key="reg_username")
                new_email = st.text_input("邮箱", key="reg_email")
                new_password = st.text_input("密码", type="password", key="reg_password")
                confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password")
                
                if st.button("注册", key="btn_register", use_container_width=True, type="primary"):
                    if not new_username or not new_email or not new_password:
                        st.error("请填写所有必填字段")
                    elif new_password != confirm_password:
                        st.error("两次输入的密码不一致")
                    elif new_username in config['credentials']['usernames']:
                        st.error("该用户名已存在")
                    else:
                        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        
                        config['credentials']['usernames'][new_username] = {
                            "email": new_email,
                            "name": new_username,
                            "password": hashed_password,
                            "role": "user"
                        }
                        
                        with open(CONFIG_PATH, 'w') as file:
                            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
                        
                        st.success("注册成功！请返回登录页面登录")
        
        if st.session_state.get('authentication_status') == False:
            st.error("用户名或密码错误")
            return
        
        if st.session_state.get('authentication_status') == None:
            return
    
    if st.session_state.get('authentication_status'):
        selected_main = st.session_state.get('selected_main', '🏠 首页')
        data = st.session_state.get('data')
        
        col_header_left, col_header_right = st.columns([4, 1])
        with col_header_right:
            col_btns = st.columns([1, 1])
            with col_btns[0]:
                if selected_main != '🏠 首页':
                    if st.button("← 返回首页", key="btn-back", use_container_width=True):
                        st.session_state['selected_main'] = '🏠 首页'
                        st.rerun()
            with col_btns[1]:
                if st.button("退出登录", key="btn-logout", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
        
        if selected_main == '🏠 首页':
            show_home(config)
        elif selected_main == '📊 客户积分智能分析':
            selected_sub = st.session_state.get('selected_sub', '📈 数据概览')
            
            st.markdown("""
            <style>
            .sub-nav-container {
                display: flex;
                gap: 8px;
                margin-bottom: 24px;
                padding: 8px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
                overflow-x: auto;
            }
            </style>
            """, unsafe_allow_html=True)
            
            sub_options = [
                ("📈 数据概览", "数据概览"),
                ("👥 客户管理", "客户管理"),
                ("🏆 积分管理", "积分管理"),
                ("📥 数据导入", "数据导入"),
                ("📝 报表导出", "报表导出")
            ]
            
            sub_cols = st.columns(len(sub_options))
            for i, (icon, label) in enumerate(sub_options):
                btn_key = f"btn-sub-{label}"
                is_active = selected_sub == icon
                
                with sub_cols[i]:
                    if is_active:
                        if st.button(icon, key=btn_key, use_container_width=True, type="primary"):
                            st.session_state['selected_sub'] = icon
                            st.rerun()
                    else:
                        if st.button(icon, key=btn_key, use_container_width=True):
                            st.session_state['selected_sub'] = icon
                            st.rerun()
            
            st.markdown("---")
            
            if selected_sub == "📈 数据概览":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_dashboard(data)
            elif selected_sub == "👥 客户管理":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_customer_management(data)
            elif selected_sub == "🏆 积分管理":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_point_management(data)
            elif selected_sub == "📥 数据导入":
                show_data_import()
            elif selected_sub == "📝 报表导出":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_reports(data)
        
        elif selected_main == '📧 JAX邮件生成器':
            show_email_generator()
        
        elif selected_main == '🧾 红冲发票自动登记':
            show_invoice_registration()
        
        elif selected_main == '📋 报价助手':
            show_quotation()
        
        elif selected_main == '👑 用户管理':
            show_user_management(config)


if __name__ == "__main__":
    main()
