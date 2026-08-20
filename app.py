import os
import sys
import traceback

# Ensure app directory is on sys.path BEFORE any other imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import streamlit as st
import textwrap
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
import base64

# Import app modules with full error diagnostics
try:
    from modules.excel_reader import ExcelReader
    from modules.customer_analysis import CustomerAnalysis
    from modules.point_calculation import PointCalculation
    from modules.database import DatabaseManager
    from modules.invoice_fetcher import InvoiceFetcher
    from modules.quotation_ui import show_quotation
    from modules.db_manager import get_db_manager
    from logo_base64 import get_logo_html, get_avatar_html, get_logo_data_url, get_avatar_data_url
except Exception as e:
    st.set_page_config(page_title="诊断错误", layout="wide")
    st.error(f"模块导入失败: {type(e).__name__}: {e}")
    st.subheader("诊断信息")
    st.text(f"Python 版本: {sys.version}")
    st.text(f"应用目录: {_APP_DIR}")
    st.text(f"应用目录存在: {os.path.isdir(_APP_DIR)}")
    st.text(f"modules 目录存在: {os.path.isdir(os.path.join(_APP_DIR, 'modules'))}")
    st.text(f"modules/__init__.py 存在: {os.path.isfile(os.path.join(_APP_DIR, 'modules', '__init__.py'))}")
    _modules_dir = os.path.join(_APP_DIR, 'modules')
    if os.path.isdir(_modules_dir):
        st.text(f"modules 目录内容: {os.listdir(_modules_dir)}")
    st.text(f"\nsys.path:")
    for p in sys.path:
        st.text(f"  {p}")
    st.text(f"\n完整错误堆栈:")
    st.code(traceback.format_exc())
    st.stop()

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
    
    current_user = st.session_state.get('username')
    is_admin = False
    if current_user and config['credentials']['usernames'].get(current_user, {}).get('role') == 'admin':
        is_admin = True
    
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.markdown(get_logo_html(80), unsafe_allow_html=True)
    with col_title:
        user_display = config['credentials']['usernames'].get(current_user, {}).get('name', current_user) if current_user else ''
        admin_badge = (
            ' <span style="background:#fef3c7;color:#92400e;'
            'padding:2px 8px;border-radius:4px;font-size:12px;margin-left:8px;border:1px solid #fcd34d;">ADMIN</span>'
            if is_admin
            else ""
        )
        st.title("🏠 澄天小助手")
        st.caption(f"欢迎回来，{user_display}{admin_badge}")

    # 极简模式下不再用自定义装饰 banner（渐变/发光/阴影），直接原生 Streamlit
    st.subheader("👋 欢迎使用澄天小助手")
    st.write("一站式管理您的客户积分、邮件、发票和报价，请选择您需要的功能模块：")
    
    # 数据库连接状态检查
    try:
        db_mgr = get_db_manager()
        db_status = db_mgr.get_connection_status()
        if db_status.get('connection_info', {}).get('is_fallback'):
            fallback_reason = db_status.get('connection_info', {}).get('fallback_reason', '未知原因')
            st.warning(f"⚠️ 数据库连接降级为本地 SQLite。原因: {fallback_reason}")
            with st.expander("查看详细诊断信息"):
                st.code(str(db_status), language="text")
                if st.button("🔄 重新检测数据库连接", key="btn-db-diagnose"):
                    st.cache_resource.clear()
                    st.rerun()
        elif db_status.get('db_type', '').startswith('PostgreSQL'):
            st.success("✅ PostgreSQL 数据库连接正常")
        elif db_status.get('db_type', '').startswith('MySQL'):
            st.success("✅ MySQL 数据库连接正常")
        elif db_status.get('db_type', '').startswith('SQLite'):
            st.info("ℹ️ 使用本地 SQLite 数据库")
    except Exception as db_err:
        st.error(f"❌ 数据库管理器初始化失败: {db_err}")
    
    st.divider()

    cards_config = [
        {
            "icon": "📊",
            "title": "客户积分智能分析",
            "desc": "数据概览 · 客户管理 · 积分管理 · 数据导入 · 报表导出",
            "color_class": "card-blue",
            "key": "btn-customer",
            "session_value": "📊 客户积分智能分析",
            "session_sub": "📈 数据概览",
            "help": "点击进入客户积分智能分析模块",
            "emojis": "📊,✨,💖,⭐,🎉,📈,🏆"
        },
        {
            "icon": "📧",
            "title": "JAX邮件生成器",
            "desc": "自动生成JAX小鼠发货通知邮件",
            "color_class": "card-green",
            "key": "btn-email",
            "session_value": "📧 JAX邮件生成器",
            "help": "点击进入JAX邮件生成器模块",
            "emojis": "📧,✨,🚀,💫,🎉,😄"
        },
        {
            "icon": "🧾",
            "title": "红冲发票自动登记",
            "desc": "自动从邮箱下载并登记电子发票",
            "color_class": "card-orange",
            "key": "btn-invoice",
            "session_value": "🧾 红冲发票自动登记",
            "help": "点击进入红冲发票自动登记模块",
            "emojis": "🧾,✨,💥,🎊,🔥,⭐"
        },
        {
            "icon": "📋",
            "title": "报价助手",
            "desc": "自动查询价格并生成报价单",
            "color_class": "card-purple",
            "key": "btn-quotation",
            "session_value": "📋 报价助手",
            "help": "点击进入报价助手模块",
            "emojis": "💰,✨,💎,⭐,📋,🚀"
        },
        {
            "icon": "🎬",
            "title": "AI 视频剪辑",
            "desc": "Crayotter 多模态Agent · 一句话自动出片",
            "color_class": "card-cyan",
            "key": "btn-video-editor",
            "session_value": "🎬 AI 视频剪辑",
            "help": "点击进入 AI 视频剪辑（Crayotter）模块",
            "emojis": "🎬,✨,🎨,🚀,💫,😄"
        },
        {
            "icon": "📦",
            "title": "库存管理",
            "desc": "物品出入库 · 库存追踪 · 自定义字段",
            "color_class": "card-blue",
            "key": "btn-inventory",
            "session_value": "📦 库存管理",
            "help": "点击进入库存管理模块",
            "emojis": "📦,✨,📊,🔍,💡,🎉"
        },
        {
            "icon": "📨",
            "title": "邮件群发",
            "desc": "Excel批量导入 · 模板变量 · 一键群发",
            "color_class": "card-purple",
            "key": "btn-mass-email",
            "session_value": "📨 邮件群发",
            "help": "点击进入邮件群发模块",
            "emojis": "📨,✨,🚀,💫,🎉,📋"
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
            "help": "点击进入用户管理模块",
            "emojis": "👑,✨,🎉,🔥,⭐,💎"
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
                      color_discrete_sequence=["#00d4ff"],
                      template="plotly_dark")
        fig.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
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
                      color_continuous_scale=["#00d4ff", "#00ffd5"],
                      template="plotly_dark")
        fig2.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
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
                      color_continuous_scale=["#00d4ff", "#00ffd5"],
                      orientation="h",
                      template="plotly_dark")
        fig4.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
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
                      color_discrete_sequence=["#00d4ff", "#00ffd5"],
                      template="plotly_dark")
        fig3.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        fig3.update_traces(
            hoverinfo="label+percent+value",
            textinfo="label+percent",
            textfont=dict(size=14),
            marker=dict(line=dict(color="#1a1f3a", width=2))
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


def read_shipping_list(file_bytes):
    """从发货清单子表读取小鼠详细信息（货号、基因型、性别、周龄、数量）"""
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheet_names = xls.sheet_names
    debug_info = f"所有子表: {sheet_names}\n"
    
    # 查找发货清单子表 - 按名称匹配
    target_sheet = None
    for name in sheet_names:
        if "发货清单" in name or "shipping" in name.lower() or "Shipping" in name:
            target_sheet = name
            break
    # 没找到则用第二个子表
    if target_sheet is None and len(sheet_names) > 1:
        target_sheet = sheet_names[1]
    if target_sheet is None:
        return pd.DataFrame(), debug_info + "未找到发货清单子表"
    
    debug_info += f"使用子表: {target_sheet}\n"
    df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    debug_info += f"行数: {len(df_raw)}, 列数: {len(df_raw.columns)}\n"
    
    # 预览前15行
    debug_info += "\n前15行预览:\n"
    for idx in range(min(15, len(df_raw))):
        row_vals = [str(v)[:25] for v in df_raw.iloc[idx].tolist()]
        debug_info += f"  行{idx}: {row_vals}\n"
    
    # 列别名映射
    field_aliases = {
        "货号": ["Stock Number", "Strock Number", "stock number", "货号", "Stock_No", "StockNumber", "stock"],
        "基因型": ["Genotype", "genotype", "基因型", "GENOTYPE"],
        "性别": ["SEX", "Sex", "sex", "性别"],
        "年龄": ["AGE", "Age", "age", "年龄", "周龄"],
        "数量": ["Qty", "qty", "QTY", "数量", "Quantity", "quantity"],
        "Individual PO Number": ["Individual PO Number", "PO Number", "Individual_PO_Number", "Individual PO"],
        "Job No": ["Job No", "Job_No", "JobNo", "job no"],
    }
    
    # 扫描每一行找表头
    header_idx = None
    found_cols = {}
    
    for idx, row in df_raw.iterrows():
        row_values = [str(v).strip() for v in row.tolist()]
        temp_found = {}
        for field, aliases in field_aliases.items():
            for col_idx, val in enumerate(row_values):
                if val in aliases or val.lower() in [a.lower() for a in aliases]:
                    temp_found[field] = (col_idx, val)
                    break
        # 找到货号+数量即认为是表头行
        if "货号" in temp_found and "数量" in temp_found:
            header_idx = idx
            found_cols = temp_found
            break
    
    if header_idx is None:
        return pd.DataFrame(), debug_info + "\n未找到包含Stock Number和Qty的表头行"
    
    debug_info += f"\n表头行: 行{header_idx}\n"
    debug_info += f"匹配到的列: "
    for field, (col_idx, col_name) in found_cols.items():
        debug_info += f"\n  {field} → 列{col_idx} ({col_name})"
    debug_info += "\n"
    
    # 读取数据
    df_data = df_raw.iloc[header_idx + 1:].copy().reset_index(drop=True)
    
    # 构建结果DataFrame
    result = pd.DataFrame()
    for field, (col_idx, _) in found_cols.items():
        result[field] = df_data.iloc[:, col_idx]
    
    # 清理：去掉全空行、表头重复行
    result = result.dropna(how='all')
    if "数量" in result.columns:
        result = result[result["数量"].notna()]
        result = result[result["数量"].astype(str).str.strip() != ""]
        result = result[~result["数量"].astype(str).str.contains("Qty|数量|Quantity", na=False, case=False)]
    if "货号" in result.columns:
        result = result[result["货号"].notna()]
        result = result[result["货号"].astype(str).str.strip() != ""]
        result = result[~result["货号"].astype(str).str.contains("Stock|货号", na=False, case=False)]
    
    # 数量转数值
    if "数量" in result.columns:
        result["数量"] = pd.to_numeric(result["数量"], errors='coerce')
        result = result.dropna(subset=["数量"])
    
    result = result.reset_index(drop=True)
    
    debug_info += f"\n提取数据行数: {len(result)}\n"
    if len(result) > 0:
        debug_info += f"\n前5行数据:\n{result.head().to_string()}\n"
    
    return result, debug_info


def format_date_email(date_value):
    if pd.isna(date_value):
        return ""
    
    import re
    
    # 如果是datetime对象
    if hasattr(date_value, 'month') and hasattr(date_value, 'day'):
        return f"{date_value.month}月{date_value.day}日"
    
    # 尝试用pandas统一转换
    try:
        date_obj = pd.to_datetime(date_value)
        return f"{date_obj.month}月{date_obj.day}日"
    except (ValueError, TypeError):
        pass
    
    # 字符串处理
    if isinstance(date_value, str):
        clean_str = str(date_value).strip()
        
        # 处理非标准格式如 "18上午5:00" 或 "8月19日上午5:00"
        # 用正则提取所有连续数字
        numbers = re.findall(r'\d+', clean_str)
        
        # 尝试标准格式
        if '-' in clean_str or '/' in clean_str:
            try:
                date_obj = pd.to_datetime(clean_str)
                return f"{date_obj.month}月{date_obj.day}日"
            except:
                pass
        
        # 处理中文日期格式 "X月X日"
        month_match = re.search(r'(\d+)月', clean_str)
        day_match = re.search(r'(\d+)日', clean_str)
        if month_match and day_match:
            return f"{month_match.group(1)}月{day_match.group(1)}日"
        
        # 只有日的情况 "18上午5:00"
        if len(numbers) >= 1:
            # 取第一个数字作为日
            return f"{numbers[0]}日"
        
        return clean_str
    
    return str(date_value)


def build_strain_list(group_df):
    """构建小鼠列表文本
    新格式：您订购的JAX小鼠# {货号},基因型：{基因型} -性别：{性别} -发货周龄：{周龄} -数量：{数量}
    返回字符串列表，每个元素代表一组小鼠
    """
    # 确保必要列存在
    if "货号" not in group_df.columns:
        group_df["货号"] = ""
    if "基因型" not in group_df.columns:
        group_df["基因型"] = ""
    if "性别" not in group_df.columns:
        group_df["性别"] = ""
    if "年龄" not in group_df.columns:
        group_df["年龄"] = ""
    if "数量" not in group_df.columns:
        group_df["数量"] = 1

    # 分组：货号+基因型+性别相同则合并数量
    group_keys = ["货号", "基因型", "性别"]
    grouped = group_df.groupby(group_keys, dropna=False)

    lines = []
    for key_tuple, group in grouped:
        stock = str(key_tuple[0]).strip() if key_tuple[0] is not None else ""
        if stock.lower() in ("nan", "none", ""):
            stock = ""
        genotype = str(key_tuple[1]).strip() if key_tuple[1] is not None else ""
        if genotype.lower() in ("nan", "none"):
            genotype = ""
        sex = str(key_tuple[2]).strip() if key_tuple[2] is not None else ""

        # 数量合并
        qty_vals = pd.to_numeric(group["数量"], errors='coerce')
        qty = qty_vals.sum()
        if pd.isna(qty) or qty == 0:
            qty = len(group)
        qty = int(qty) if float(qty).is_integer() else qty

        # 年龄取第一条
        first_row = group.iloc[0]
        age = str(first_row["年龄"]).strip() if pd.notna(first_row["年龄"]) else ""
        if age.lower() in ("nan", "none"):
            age = ""

        # 性别转换
        if sex.upper() in ("F", "FEMALE") or sex == "雌":
            sex_text = "雌"
        elif sex.upper() in ("M", "MALE") or sex == "雄":
            sex_text = "雄"
        else:
            sex_text = sex

        # 周龄
        age_text = f"{age}周" if age else ""

        line = f"您订购的JAX小鼠# {stock},基因型：{genotype} -性别：{sex_text} -发货周龄：{age_text} -数量：{qty}"
        lines.append(line)

    return lines


def render_mail(surname, strain_lines, receive_date, delivery_address):
    """生成邮件正文
    每组小鼠一行，最后一行连接"预计将在..."配送信息
    """
    if not strain_lines:
        strain_lines = ["（未找到小鼠信息）"]

    if len(strain_lines) == 1:
        strain_text = strain_lines[0] + f" ，预计将在{receive_date}下午17:00前送到您合同指定收货地址：{delivery_address}。请问当天是否方便接收小鼠呢？"
    else:
        parts = []
        for i, line in enumerate(strain_lines):
            if i < len(strain_lines) - 1:
                parts.append(line + "。")
            else:
                parts.append(line + f" ，预计将在{receive_date}下午17:00前送到您合同指定收货地址：{delivery_address}。请问当天是否方便接收小鼠呢？")
        strain_text = "\n".join(parts)

    mail_body = f"""尊敬的{surname}老师：

您好！

本封邮件为JAX小鼠配送通知。

{strain_text}

附件是本批小鼠的相关文件：美国健康证书AHC，JAX鼠房微生物报告， 隔离场微生物报告以及JAX小鼠接收指南。

为了确保小鼠在接收后可以尽快的服务于您的研究，建议您：

1.严格遵照随附的《JAX 小鼠接收指南》开展相关操作。小鼠签收时，请即刻检查外包装完整性，并仔细核验小鼠核心信息（品系、数量、性别等）。所有问题须在24 小时内反馈至北京澄天生物科技有限公司，逾期将视为验收合格。请注意，退款及补发政策申请需满足以下条件：相关问题需在小鼠送达贵单位后48 小时内，由贵方提供有效证明材料并提交反馈；后续需经北京澄天生物科技有限公司及JAX 联合核验通过，方可启动对应流程。

2. 建议您收到小鼠后尽快按照官网上提供的基因鉴定方案对小鼠进行鉴定核实，以便于您后续合理的制定繁育/使用方案。

若有问题欢迎随时与我们联系。

预祝您实验一切顺利！"""

    return mail_body


def process_excel_email(file_bytes):
    # 1. 读取出隔离场 - 获取PO级别的收货地址、提货人、拟收货时间
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

    # 2. 读取发货清单 - 获取小鼠详细信息
    shipping_df, ship_debug = read_shipping_list(file_bytes)

    debug_info = "========== 发货清单读取 ==========\n" + ship_debug + "\n"

    # 3. 构建 Job No → PO 映射（用于关联发货清单和出隔离场）
    job_to_po = {}
    if "Job No" in df.columns and "Individual PO Number" in df.columns:
        for _, row in df.iterrows():
            job = str(row["Job No"]).strip() if pd.notna(row["Job No"]) else ""
            po = str(row["Individual PO Number"]).strip() if pd.notna(row["Individual PO Number"]) else ""
            if job and po and job.lower() not in ("nan", ""):
                job_to_po[job] = po

    debug_info += f"出隔离场 Job No→PO 映射: {len(job_to_po)}条\n"

    # 4. 为发货清单数据补充PO信息
    if len(shipping_df) > 0:
        if "Individual PO Number" not in shipping_df.columns:
            # 尝试用Job No关联
            if "Job No" in shipping_df.columns:
                shipping_df["Individual PO Number"] = shipping_df["Job No"].astype(str).str.strip().map(job_to_po).fillna("")
                debug_info += f"用Job No关联PO，匹配{(shipping_df['Individual PO Number'] != '').sum()}条\n"
            else:
                shipping_df["Individual PO Number"] = ""
                debug_info += "发货清单无PO和Job No列，无法关联\n"

    # 5. 为每个PO生成邮件
    po_order = df["Individual PO Number"].dropna().unique().tolist()

    result_rows = []
    for po_number in po_order:
        po_rows = df[df["Individual PO Number"] == po_number]
        first_row = po_rows.iloc[0]

        # 收货地址（从出隔离场的"送货地址"列）
        delivery_address = ""
        if "送货地址" in po_rows.columns:
            delivery_address = str(first_row["送货地址"]).strip() if pd.notna(first_row["送货地址"]) else ""

        # 提货人 → 姓氏（优先提货人，其次收货人）
        contact = ""
        if "提货人" in po_rows.columns:
            contact = str(first_row["提货人"]).strip() if pd.notna(first_row["提货人"]) else ""
        if not contact or contact.lower() in ("nan", ""):
            if "收货人" in po_rows.columns:
                contact = str(first_row["收货人"]).strip() if pd.notna(first_row["收货人"]) else ""
        surname = contact[0] if contact and contact.lower() not in ("nan", "") else ""

        # 拟收货时间
        receive_date = ""
        if "拟收货时间" in po_rows.columns:
            receive_date = format_date_email(first_row["拟收货时间"]) if pd.notna(first_row["拟收货时间"]) else ""

        # 从发货清单获取该PO的小鼠信息
        po_mice = pd.DataFrame()
        if len(shipping_df) > 0 and "Individual PO Number" in shipping_df.columns:
            po_mice = shipping_df[
                shipping_df["Individual PO Number"].astype(str).str.strip() == str(po_number).strip()
            ].copy()

        debug_info += f"\nPO {po_number}: 发货清单匹配{len(po_mice)}条小鼠记录\n"

        if len(po_mice) == 0:
            strain_lines = []
        else:
            strain_lines = build_strain_list(po_mice)

        mail_body = render_mail(surname, strain_lines, receive_date, delivery_address)

        result_rows.append({
            "Individual PO Number": po_number,
            "单位名称": first_row.get("单位名称", ""),
            "收货人": contact,
            "邮件内容": mail_body
        })

    result_df = pd.DataFrame(result_rows)
    result_df['po_order'] = result_df['Individual PO Number'].map(lambda x: po_order.index(x) if x in po_order else len(po_order))
    result_df = result_df.sort_values('po_order').drop('po_order', axis=1)

    # 保存调试信息
    process_excel_email._debug_info = debug_info

    return result_df


def show_email_generator():
    from modules.email_sender import test_smtp_connection, send_bulk_emails, guess_smtp_config

    st.title("📧 JAX小鼠发货通知邮件生成器")

    st.markdown(textwrap.dedent(
        """
    **使用说明：**
    1. 上传Excel文件（需包含【出隔离场】和【发货清单】Sheet）
    2. 小鼠详细信息（货号、基因型、性别、周龄、数量）从「发货清单」读取
    3. 收货地址、提货人、拟收货时间从「出隔离场」读取
    4. 配置SMTP后可直接批量发送邮件
    """))

    with st.expander("🔐 SMTP邮箱配置", expanded=False):
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            smtp_user = st.text_input("邮箱地址", value=st.session_state.get("email_smtp_user", "1392039316@qq.com"), key="eg_smtp_user")
        with cfg_col2:
            smtp_password = st.text_input("SMTP授权码", type="password", value=st.session_state.get("email_smtp_password", "dtepljmsauzgjbfa"), key="eg_smtp_password")
        with cfg_col3:
            sender_name = st.text_input("发件人名称", value=st.session_state.get("email_sender_name", "Cindy 张茹"), key="eg_sender_name")

        if smtp_user:
            host, port, ssl_flag = guess_smtp_config(smtp_user)
            st.caption(f"自动识别SMTP: {host}:{port} {'(SSL)' if ssl_flag else '(STARTTLS)'}")

        test_col1, test_col2 = st.columns([1, 3])
        with test_col1:
            if st.button("🔌 测试连接", key="eg_test_conn", use_container_width=True):
                with st.spinner("测试SMTP连接..."):
                    conn_result = test_smtp_connection(smtp_user, smtp_password)
                    if conn_result["status"] == "success":
                        st.success(f"✅ 连接成功！{conn_result['smtp_host']}:{conn_result['smtp_port']} ({conn_result['elapsed_seconds']}s)")
                    else:
                        st.error(f"❌ 连接失败: {conn_result.get('message', '未知错误')}")

        st.session_state["email_smtp_user"] = smtp_user
        st.session_state["email_smtp_password"] = smtp_password
        st.session_state["email_sender_name"] = sender_name

    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])

    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                result_df = process_excel_email(uploaded_file.getvalue())

                st.success(f"邮件生成完成！共 {len(result_df)} 封邮件")

                debug_info = getattr(process_excel_email, '_debug_info', '')

                with st.expander("🔍 调试信息（发货清单解析详情）", expanded=False):
                    if debug_info:
                        st.text(debug_info)
                    else:
                        st.info("无调试信息")

                st.subheader("生成的邮件列表")
                st.dataframe(result_df, width="stretch", height=300)

                excel_buffer = BytesIO()
                result_df.to_excel(excel_buffer, index=False, sheet_name="邮件生成结果")
                excel_buffer.seek(0)

                st.download_button(
                    label="📥 下载邮件结果",
                    data=excel_buffer,
                    file_name=f"JAX邮件生成结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.subheader("📧 邮件预览")
                for _, row in result_df.iterrows():
                    with st.expander(f"📧 {row['Individual PO Number']} - {row['单位名称']}"):
                        st.text(row['邮件内容'])

                st.divider()

                st.subheader("📤 批量发送邮件")

                send_col1, send_col2 = st.columns([1, 2])
                with send_col1:
                    delay_seconds = st.number_input("发送间隔(秒)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="eg_delay")
                    dry_run = st.checkbox("演练模式（不实际发送）", value=True, key="eg_dry_run")

                recipient_emails = st.text_area(
                    "收件人邮箱列表（每行一个，对应上面邮件列表顺序）",
                    key="eg_recipients",
                    height=100,
                    placeholder="heng.li@lab-direct.com\niblcs01@ibiologistics.com\n..."
                )

                email_list_for_send = []
                for idx, row in result_df.iterrows():
                    lines = recipient_emails.strip().split("\n") if recipient_emails.strip() else []
                    to_email = lines[idx].strip() if idx < len(lines) else ""
                    if to_email:
                        email_list_for_send.append({
                            "email": to_email,
                            "name": row.get("收货人", ""),
                            "subject": f"JAX小鼠发货通知 - {row['Individual PO Number']}",
                            "body": row["邮件内容"],
                        })

                if email_list_for_send:
                    st.info(f"待发送 {len(email_list_for_send)} 封邮件：" + ", ".join(
                        f"{r['name']}→{r['email']}" for r in email_list_for_send
                    ))

                    if st.button("🚀 " + ("演练预览" if dry_run else "立即发送"), key="eg_send", type="primary", use_container_width=True):
                        if not smtp_user or not smtp_password:
                            st.error("请先在上方配置SMTP邮箱信息")
                        elif dry_run:
                            with st.spinner("演练预览中..."):
                                result = send_bulk_emails(
                                    smtp_user=smtp_user, smtp_password=smtp_password,
                                    email_list=email_list_for_send, sender_name=sender_name,
                                    delay_seconds=delay_seconds, dry_run=True,
                                )
                            st.success(f"演练完成！共 {result['total']} 封邮件待发送")
                            for r in result["results"]:
                                with st.expander(f"📧 [{r['index']}] {r['name']} <{r['email']}>"):
                                    st.write(f"主题: {r['subject']}")
                        else:
                            progress = st.progress(0)
                            status_text = st.empty()
                            success_count = 0
                            fail_count = 0

                            for i, item in enumerate(email_list_for_send):
                                status_text.write(f"发送中 [{i+1}/{len(email_list_for_send)}] {item['email']}...")
                                single_result = send_bulk_emails(
                                    smtp_user=smtp_user, smtp_password=smtp_password,
                                    email_list=[item], sender_name=sender_name,
                                    dry_run=False,
                                )
                                if single_result["success_count"] > 0:
                                    success_count += 1
                                else:
                                    fail_count += 1
                                progress.progress((i + 1) / len(email_list_for_send))
                                if i < len(email_list_for_send) - 1 and delay_seconds > 0:
                                    import time
                                    time.sleep(delay_seconds)

                            status_text.empty()
                            st.success(f"✅ 发送完成！成功 {success_count} 封，失败 {fail_count} 封")

                            if success_count > 0:
                                st.session_state["last_send_result"] = {
                                    "total": len(email_list_for_send),
                                    "success": success_count,
                                    "failed": fail_count,
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                }
                elif not recipient_emails.strip():
                    st.warning("请填写收件人邮箱列表")

            except Exception as e:
                st.error(f"处理过程中发生错误：\n\n{str(e)}")
                import traceback
                with st.expander("查看详细错误信息"):
                    st.code(traceback.format_exc())


def _extract_surname(name: str) -> str:
    if not name:
        return ""
    surname_map = [
        "欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟",
        "闻人", "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政",
        "濮阳", "公冶", "太叔", "申屠", "公孙", "慕容", "仲孙", "钟离", "长孙",
        "宇文", "司徒", "鲜于", "司空", "闾丘", "子车", "亓官", "司寇", "巫马",
        "公西", "颛孙", "壤驷", "公良", "漆雕", "乐正", "宰父", "谷梁", "拓跋",
        "夹谷", "轩辕", "令狐", "段干", "百里", "呼延", "东郭", "南门", "羊舌",
        "微生", "公户", "公玉", "公仪", "梁丘", "公仲", "公上", "公门", "公山",
        "公坚", "左丘", "公伯", "西门", "公祖", "第五", "公乘", "贯丘", "公皙",
        "南荣", "东里", "东宫", "仲长", "子书", "子桑", "即墨", "达奚", "褚师"
    ]
    for compound in surname_map:
        if name.startswith(compound):
            return compound
    return name[0] if name else ""


def show_email_blast():
    from modules.email_sender import test_smtp_connection, send_bulk_emails, guess_smtp_config

    st.title("📨 邮件群发")

    st.markdown(textwrap.dedent(
        """
    **使用说明：**
    1. 上传Excel文件（须包含「姓名」和「邮箱」列）
    2. 输入邮件主题和正文，支持模板变量：{{姓氏}} {{姓名}} {{名字}} {{邮箱}} 以及Excel中的任意列名
    3. 演练预览确认后，一键批量发送
    """))

    with st.expander("🔐 SMTP邮箱配置", expanded=True):
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            smtp_user = st.text_input("邮箱地址", value=st.session_state.get("email_smtp_user", "1392039316@qq.com"), key="mb_smtp_user")
        with cfg_col2:
            smtp_password = st.text_input("SMTP授权码", type="password", value=st.session_state.get("email_smtp_password", "dtepljmsauzgjbfa"), key="mb_smtp_password")
        with cfg_col3:
            sender_name = st.text_input("发件人名称", value=st.session_state.get("email_sender_name", "Cindy 张茹"), key="mb_sender_name")

        if smtp_user:
            host, port, ssl_flag = guess_smtp_config(smtp_user)
            st.caption(f"自动识别SMTP: {host}:{port} {'(SSL)' if ssl_flag else '(STARTTLS)'}")

        if st.button("🔌 测试连接", key="mb_test_conn", use_container_width=True):
            with st.spinner("测试SMTP连接..."):
                conn_result = test_smtp_connection(smtp_user, smtp_password)
                if conn_result["status"] == "success":
                    st.success(f"✅ 连接成功！{conn_result['smtp_host']}:{conn_result['smtp_port']} ({conn_result['elapsed_seconds']}s)")
                else:
                    st.error(f"❌ 连接失败: {conn_result.get('message', '未知错误')}")

        st.session_state["email_smtp_user"] = smtp_user
        st.session_state["email_smtp_password"] = smtp_password
        st.session_state["email_sender_name"] = sender_name

    st.subheader("1. 上传Excel")
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"], key="mb_excel")

    recipients_data = []
    if uploaded_file is not None:
        with st.spinner("正在读取Excel文件..."):
            try:
                df = pd.read_excel(uploaded_file)
                df.columns = [str(c).strip() for c in df.columns]
                st.success(f"读取成功！共 {len(df)} 行数据")

                name_col = None
                email_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if col in ("姓名", "客户", "名称", "联系人") or col_lower in ("name", "customer", "contact"):
                        if name_col is None:
                            name_col = col
                    if col in ("邮箱", "邮件", "email", "e-mail", "mail") or any(kw in col_lower for kw in ["email", "邮箱", "邮件"]):
                        if email_col is None:
                            email_col = col

                if name_col:
                    st.caption(f"自动识别姓名字段: {name_col}")
                if email_col:
                    st.caption(f"自动识别邮箱字段: {email_col}")

                recipients_data = []
                for _, row in df.iterrows():
                    name = str(row.get(name_col, "")).strip() if name_col else ""
                    email = str(row.get(email_col, "")).strip() if email_col else ""
                    if email:
                        entry = {"email": email, "name": name}
                        entry["surname"] = _extract_surname(name)
                        entry["given_name"] = name[len(entry["surname"]):] if name and entry["surname"] else name
                        for col in df.columns:
                            entry[str(col)] = str(row[col]).strip() if pd.notna(row[col]) else ""
                        recipients_data.append(entry)

                if recipients_data:
                    preview_cols = [c for c in ["name", "email", "surname", "given_name"] if c in recipients_data[0]]
                    preview_df = pd.DataFrame([{k: r.get(k, "") for k in preview_cols} for r in recipients_data[:10]])
                    st.dataframe(preview_df, use_container_width=True)
                    if len(recipients_data) > 10:
                        st.caption(f"... 还有 {len(recipients_data) - 10} 条")
                else:
                    st.warning("未找到有效收件人，请确认Excel包含邮箱列")

            except Exception as e:
                st.error(f"读取失败: {e}")
                import traceback
                with st.expander("详细错误"):
                    st.code(traceback.format_exc())

    st.divider()
    st.subheader("2. 编辑邮件内容")

    subject_template = st.text_input(
        "邮件主题",
        value=st.session_state.get("mb_subject", "尊敬的{{姓氏}}老师，您好"),
        key="mb_subject",
    )

    body_template = st.text_area(
        "邮件正文",
        value=st.session_state.get("mb_body", "尊敬的{{姓氏}}老师：\n\n您好！\n\n（在此编写邮件内容，支持{{姓氏}} {{姓名}}等变量）\n\n祝好！"),
        key="mb_body",
        height=250,
    )

    if "{{" in subject_template or "{{" in body_template:
        st.caption("💡 可用变量: {{姓氏}} {{姓名}} {{名字}} {{邮箱}} 以及Excel中的任意列名")

    st.divider()
    st.subheader("3. 预览与发送")

    col1, col2 = st.columns([1, 3])
    with col1:
        delay_seconds = st.number_input("发送间隔(秒)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="mb_delay")
        dry_run = st.checkbox("演练模式（不实际发送）", value=True, key="mb_dry_run")

    if recipients_data and (subject_template or body_template):
        email_list_for_send = []
        for r in recipients_data:
            subject = subject_template
            body = body_template
            for key, val in r.items():
                subject = subject.replace("{{" + key + "}}", str(val))
                body = body.replace("{{" + key + "}}", str(val))
            email_list_for_send.append({
                "email": r["email"],
                "name": r.get("name", ""),
                "subject": subject,
                "body": body,
            })

        missing_vars = set()
        import re
        for item in email_list_for_send:
            remaining = re.findall(r'\{\{(\w+)\}\}', item["subject"] + item["body"])
            missing_vars.update(remaining)
        if missing_vars:
            st.warning(f"⚠️ 模板中存在未替换的变量: {', '.join(missing_vars)}")

        st.info(f"待发送 {len(email_list_for_send)} 封邮件")

        with st.expander("📧 预览前3封"):
            for item in email_list_for_send[:3]:
                st.markdown(f"**收件人:** {item['name']} ({item['email']})")
                st.markdown(f"**主题:** {item['subject']}")
                st.text(item['body'][:300] + "..." if len(item['body']) > 300 else item['body'])
                st.divider()

        if st.button("🚀 " + ("演练预览" if dry_run else "立即发送"), key="mb_send", type="primary", use_container_width=True):
            if not smtp_user or not smtp_password:
                st.error("请先在上方配置SMTP邮箱信息")
            elif dry_run:
                with st.spinner("演练预览中..."):
                    result = send_bulk_emails(
                        smtp_user=smtp_user, smtp_password=smtp_password,
                        email_list=email_list_for_send, sender_name=sender_name,
                        delay_seconds=delay_seconds, dry_run=True,
                    )
                st.success(f"演练完成！共 {result['total']} 封邮件")
                for r in result["results"]:
                    st.write(f"  [{r['index']}] {r['name']} <{r['email']}> - {r['subject']}")
            else:
                progress = st.progress(0)
                status_text = st.empty()
                success_count = 0
                fail_count = 0

                for i, item in enumerate(email_list_for_send):
                    status_text.write(f"发送中 [{i+1}/{len(email_list_for_send)}] {item['email']}...")
                    single_result = send_bulk_emails(
                        smtp_user=smtp_user, smtp_password=smtp_password,
                        email_list=[item], sender_name=sender_name,
                        dry_run=False,
                    )
                    if single_result["success_count"] > 0:
                        success_count += 1
                    else:
                        fail_count += 1
                    progress.progress((i + 1) / len(email_list_for_send))
                    if i < len(email_list_for_send) - 1 and delay_seconds > 0:
                        import time
                        time.sleep(delay_seconds)

                status_text.empty()
                st.success(f"✅ 发送完成！成功 {success_count} 封，失败 {fail_count} 封")

                if success_count > 0:
                    st.session_state["last_blast_result"] = {
                        "total": len(email_list_for_send),
                        "success": success_count,
                        "failed": fail_count,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
    elif not recipients_data:
        st.info("请先上传Excel文件")
    else:
        st.info("请填写邮件主题和正文")


def show_inventory():
    from modules.inventory.ui import show_inventory_page

    try:
        db = get_db_manager()
    except Exception as exc:
        st.error(f"数据库连接失败：{exc}")
        return
    show_inventory_page(db, operator=st.session_state.get("username", ""))


def show_user_management(config):
    st.title("👑 用户管理")
    
    st.markdown(textwrap.dedent(
        """
    **功能说明：**
    管理员可以查看所有用户信息、登录状态和域名信息。
    """))
    
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
    
    st.markdown(textwrap.dedent(
        """
    **功能说明：**
    通过IMAP连接邮箱，自动检索发票邮件，下载PDF发票并按规则命名保存到本地目录。
    """))
    
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
    
    # 配置Plotly深色主题
    try:
        px.defaults.template = "plotly_dark"
        # 设置自定义颜色
        import plotly.graph_objects as go
        go.layout.Template()
    except:
        pass
    
    from modules.theme import apply_all_styles
    apply_all_styles()

    # 登录路由下隐藏侧边栏：用 class 匹配 theme.py 的 .no-show 规则，其他路由侧边栏默认保留
    hide_sidebar_css = textwrap.dedent(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        </style>
        """
    )
    st.markdown(hide_sidebar_css, unsafe_allow_html=True)
    
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    if st.session_state.get('authentication_status') != True:
        # 极简模式：theme.py 已提供 .login-container 最小居中样式（max-width 460 + margin auto），
        # 此处仅开一个简单容器 div 包裹内容，去掉科技风发光/渐变装饰。
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.markdown(get_logo_html(90), unsafe_allow_html=True)
        with col_title:
            st.title("澄天小助手")
            st.caption("TECH ASSISTANT SYSTEM")

        st.divider()

        login_tab, register_tab = st.tabs(["登录系统", "新用户注册"])

        with login_tab:
            authenticator.login(location="main")

        with register_tab:
            st.subheader("创建新账号")
            
            new_username = st.text_input("用户名", key="reg_username", placeholder="请输入用户名")
            new_email = st.text_input("邮箱", key="reg_email", placeholder="请输入邮箱地址")
            new_password = st.text_input("密码", type="password", key="reg_password", placeholder="至少8位字符")
            confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password", placeholder="再次输入密码")
            
            if st.button("注册新账号", key="btn_register", use_container_width=True, type="primary"):
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
                    
                    st.success("🎉 注册成功！请切换到登录页面登录")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.get('authentication_status') == False:
            st.error("❌ 用户名或密码错误")
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

            st.divider()
            
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
        
        elif selected_main == '🎬 AI 视频剪辑':
            try:
                from modules.video_editor import show_video_editor
                show_video_editor()
            except Exception as exc:
                st.error(f"视频剪辑模块加载失败：{exc}")
                st.info("请确认视频剪辑相关依赖已安装。")

        elif selected_main == '📦 库存管理':
            show_inventory()

        elif selected_main == '📨 邮件群发':
            show_email_blast()

        elif selected_main == '👑 用户管理':
            show_user_management(config)


if __name__ == "__main__":
    main()
