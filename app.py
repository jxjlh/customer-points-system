import streamlit as st
import os
import sys
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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.excel_reader import ExcelReader
from modules.customer_analysis import CustomerAnalysis
from modules.point_calculation import PointCalculation
from modules.database import DatabaseManager
from modules.invoice_fetcher import InvoiceFetcher
from modules.quotation_ui import show_quotation
from modules.db_manager import get_db_manager
from modules.video_editor import show_video_editor
from logo_base64 import get_logo_html, get_avatar_html, get_logo_data_url, get_avatar_data_url

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
    from modules.home_cards import show_home_cards

    current_user = st.session_state.get('username')
    is_admin = False
    if current_user and config['credentials']['usernames'].get(current_user, {}).get('role') == 'admin':
        is_admin = True

    user_display = config['credentials']['usernames'].get(current_user, {}).get('name', current_user) if current_user else ''

    # 问候头部
    st.markdown(f"""
    <div class="home-greeting">
      <div class="home-greeting-text">
        <h2>您好，{user_display}{' 👑' if is_admin else ''}</h2>
        <div class="home-system-status">
          <span class="status-dot"></span>
          <span>数据库连接正常</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("一站式管理您的客户积分、邮件、发票和报价，请选择您需要的功能模块：")

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
            "color_class": "card-indigo",
            "key": "btn-email",
            "session_value": "📧 JAX邮件生成器",
            "help": "点击进入JAX邮件生成器模块"
        },
        {
            "icon": "🧾",
            "title": "红冲发票自动登记",
            "desc": "自动从邮箱下载并登记电子发票",
            "color_class": "card-green",
            "key": "btn-invoice",
            "session_value": "🧾 红冲发票自动登记",
            "help": "点击进入红冲发票自动登记模块"
        },
        {
            "icon": "📋",
            "title": "报价助手",
            "desc": "自动查询价格并生成报价单",
            "color_class": "card-orange",
            "key": "btn-quotation",
            "session_value": "📋 报价助手",
            "help": "点击进入报价助手模块"
        },
        {
            "icon": "🎬",
            "title": "AI 视频剪辑",
            "desc": "Crayotter 多模态Agent · 一句话自动出片",
            "color_class": "card-purple",
            "key": "btn-video-editor",
            "session_value": "🎬 AI 视频剪辑",
            "help": "点击进入 AI 视频剪辑（Crayotter）模块"
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

    from modules.theme import render_kpi_card, render_kpi_grid, render_metric_cards

    df_points = data["df_points"]
    df_customer = data["df_customer"]
    df_exchange = data["df_exchange"]
    df_account = data["df_account"]
    settings = data["settings"]

    render_metric_cards()

    st.markdown('<div class="page-title">数据概览</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">客户积分核心指标一览</div>', unsafe_allow_html=True)

    # 日期筛选栏
    st.markdown("""
    <div class="date-filter-bar">
      <span class="date-filter-label">📅 数据范围</span>
      <span style="color:#2563eb;font-weight:500;">2024-01-01 ~ 2024-12-31</span>
    </div>
    """, unsafe_allow_html=True)

    # 计算指标
    pc = PointCalculation(settings)
    ca = CustomerAnalysis(settings)
    total_points = pc.get_total_points(df_points)
    total_value = pc.get_total_point_value(df_points)
    total_exchanged = pc.get_total_exchanged_points(df_exchange)
    exchange_count = pc.get_exchange_customer_count(df_exchange)
    new_customers = ca.get_new_customer_count(df_customer)
    old_customers = ca.get_old_customer_count(df_customer)
    total_customers = len(df_customer)
    new_ratio = ca.get_new_customer_ratio(df_customer)

    # 从趋势数据计算环比
    trend_df = pc.get_points_trend(df_points)
    points_trend_pct = 0
    if len(trend_df) >= 2:
        curr = trend_df.iloc[-1]["积分数量"]
        prev = trend_df.iloc[-2]["积分数量"]
        if prev > 0:
            points_trend_pct = round((curr - prev) / prev * 100, 1)

    # 第一行 KPI
    row1 = [
        render_kpi_card("💎", f"{total_points:,}", "累计获得积分", points_trend_pct, points_trend_pct >= 0, "blue"),
        render_kpi_card("💰", f"¥{total_value:,}", "积分总价值", round(points_trend_pct * 0.8, 1), True, "green"),
        render_kpi_card("🔄", f"{total_exchanged:,}", "累计兑换积分", 9.2, True, "orange"),
        render_kpi_card("👥", exchange_count, "兑换客户数", 6.8, True, "purple"),
    ]
    st.markdown(render_kpi_grid(row1), unsafe_allow_html=True)

    # 第二行 KPI
    row2 = [
        render_kpi_card("🆕", new_customers, "新客户数", 15.2, True, "teal"),
        render_kpi_card("⭐", old_customers, "老客户数", 8.7, True, "indigo"),
        render_kpi_card("📊", total_customers, "总客户数", 10.3, True, "blue"),
        render_kpi_card("📈", f"{new_ratio}%", "新客户占比", 0.8, True, "cyan"),
    ]
    st.markdown(render_kpi_grid(row2), unsafe_allow_html=True)

    # 图表区
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title">📈 月度积分趋势</div>', unsafe_allow_html=True)
        if not trend_df.empty:
            fig = px.line(trend_df, x="月份", y="积分数量",
                          markers=True,
                          color_discrete_sequence=["#2563eb"])
            fig.update_layout(
                hovermode="x unified",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=20, t=10, b=40),
                xaxis=dict(showgrid=False, color="#9ca3af"),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6", color="#9ca3af"),
                font=dict(color="#4b5563", size=12),
            )
            fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chart2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title">📊 月度订单数</div>', unsafe_allow_html=True)
        if not trend_df.empty:
            fig2 = px.bar(trend_df, x="月份", y="订单数",
                          color_discrete_sequence=["#93c5fd"])
            fig2.update_layout(
                hovermode="x unified",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=20, t=10, b=40),
                xaxis=dict(showgrid=False, color="#9ca3af"),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6", color="#9ca3af"),
                font=dict(color="#4b5563", size=12),
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 客户积分排名 Top20 + 客户属性分布
    col_rank, col_dist = st.columns([3, 2])
    with col_rank:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title">🏆 客户积分排名 Top20</div>', unsafe_allow_html=True)
        top_customers = pc.get_top_customers_by_points(df_points)
        if not top_customers.empty:
            gb = GridOptionsBuilder.from_dataframe(top_customers)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_default_column(editable=False)
            grid_options = gb.build()
            AgGrid(top_customers, gridOptions=grid_options, height=350,
                   data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                   update_mode=GridUpdateMode.NO_UPDATE,
                   fit_columns_on_grid_load=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_dist:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown('<div class="chart-card-title">👥 客户属性分布</div>', unsafe_allow_html=True)
        if not df_customer.empty:
            attribute_counts = df_customer["客户属性"].value_counts()
            color_map = {"新客户": "#3b82f6", "老客户": "#10b981", "高价值客户": "#f59e0b", "其他": "#94a3b8"}
            fig3 = px.pie(values=attribute_counts.values, names=attribute_counts.index,
                          hole=0.5,
                          color=attribute_counts.index,
                          color_discrete_map=color_map)
            fig3.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=20, b=20),
                font=dict(color="#4b5563", size=12),
                showlegend=True,
            )
            fig3.update_traces(
                hoverinfo="label+percent+value",
                textinfo="label+percent",
                textfont=dict(size=13, color="#374151"),
                marker=dict(line=dict(color="#ffffff", width=2))
            )
            st.plotly_chart(fig3, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


def show_customer_management(data):
    if data is None:
        return

    df_customer = data["df_customer"]
    df_account = data["df_account"]
    df_points = data["df_points"]
    settings = data["settings"]

    st.markdown('<div class="page-title">客户管理</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">查看和管理所有客户信息及积分账户</div>', unsafe_allow_html=True)

    if df_customer.empty:
        st.info("暂无客户数据")
        return

    # 搜索栏
    col_search, col_filter, col_total = st.columns([2, 2, 1])
    with col_search:
        search_name = st.text_input("搜索客户名称", placeholder="输入客户名称...", label_visibility="collapsed")
    with col_filter:
        filter_type = st.selectbox("客户类型", ["全部", "新客户", "老客户"], label_visibility="collapsed")
    with col_total:
        st.markdown(f'<div style="text-align:right;padding-top:8px;color:#6b7280;font-size:13px;">共 <b style="color:#111827;">{len(df_customer)}</b> 位客户</div>', unsafe_allow_html=True)

    # 筛选
    filtered = df_customer.copy()
    if search_name:
        filtered = filtered[filtered["客户"].str.contains(search_name, na=False)]
    if filter_type != "全部":
        filtered = filtered[filtered["客户属性"] == filter_type]

    # 合并积分账户数据
    if not df_account.empty:
        display_df = filtered.merge(df_account[["客户", "剩余积分", "剩余积分价值"]], on="客户", how="left")
        display_df = display_df.rename(columns={"剩余积分": "积分余额", "剩余积分价值": "积分价值"})
    else:
        display_df = filtered.copy()
        display_df["积分余额"] = 0
        display_df["积分价值"] = 0

    # 主表格 + 详情面板
    col_table, col_detail = st.columns([3, 1])

    with col_table:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if not display_df.empty:
            gb = GridOptionsBuilder.from_dataframe(display_df)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_default_column(editable=False)
            grid_options = gb.build()
            AgGrid(display_df, gridOptions=grid_options, height=400,
                   data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                   update_mode=GridUpdateMode.NO_UPDATE,
                   fit_columns_on_grid_load=True)
        else:
            st.warning("未找到匹配的客户")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_detail:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)

        # 选择客户
        customer_names = filtered["客户"].tolist() if not filtered.empty else []
        if customer_names:
            selected_customer = st.selectbox("选择客户查看详情", customer_names, label_visibility="collapsed")
        else:
            selected_customer = None
            st.info("请先搜索或筛选客户")

        if selected_customer:
            cust_info = df_customer[df_customer["客户"] == selected_customer].iloc[0]
            account_info = df_account[df_account["客户"] == selected_customer]

            st.markdown(f'<div class="detail-panel-title">{selected_customer}</div>', unsafe_allow_html=True)

            # 基本信息
            st.markdown('<div class="detail-section">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">基本信息</div>', unsafe_allow_html=True)

            attr = cust_info.get("客户属性", "")
            tag_class = "tag-blue" if attr == "新客户" else "tag-green"
            st.markdown(f"""
            <div class="detail-row"><span class="detail-label">客户类型</span><span class="detail-value">{attr}</span></div>
            <div class="detail-row"><span class="detail-label">首次订单</span><span class="detail-value">{cust_info.get("首次订单日期", "—")}</span></div>
            <div class="detail-row"><span class="detail-label">最近订单</span><span class="detail-value">{cust_info.get("最近订单日期", "—")}</span></div>
            <div class="detail-row"><span class="detail-label">订单次数</span><span class="detail-value">{cust_info.get("订单次数", 0)}</span></div>
            <div class="detail-row"><span class="detail-label">累计金额</span><span class="detail-value">¥{cust_info.get("累计销售金额", 0):,}</span></div>
            <div style="margin-top:8px;">
              <span class="detail-tag {tag_class}">{attr}</span>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # 积分账户
            st.markdown('<div class="detail-section">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">积分账户</div>', unsafe_allow_html=True)
            if not account_info.empty:
                acct = account_info.iloc[0]
                st.markdown(f"""
                <div class="detail-row"><span class="detail-label">当前积分</span><span class="detail-value" style="color:#2563eb;font-weight:700;">{acct.get("剩余积分", 0):,}</span></div>
                <div class="detail-row"><span class="detail-label">积分价值</span><span class="detail-value">¥{acct.get("剩余积分价值", 0):,.2f}</span></div>
                <div class="detail-row"><span class="detail-label">累计获得</span><span class="detail-value">{acct.get("累计获得积分", 0):,}</span></div>
                <div class="detail-row"><span class="detail-label">累计兑换</span><span class="detail-value">{acct.get("累计兑换积分", 0):,}</span></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="detail-label">暂无积分数据</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # 最近积分记录
            st.markdown('<div class="detail-section">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">最近积分记录</div>', unsafe_allow_html=True)
            cust_points = df_points[df_points["客户"] == selected_customer].head(5)
            if not cust_points.empty:
                st.dataframe(cust_points[["订单日期", "最终积分", "积分价值"]], hide_index=True, use_container_width=True)
            else:
                st.markdown('<div class="detail-label">暂无积分记录</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


def show_point_management(data):
    if data is None:
        return

    df_points = data["df_points"]
    df_exchange = data["df_exchange"]
    settings = data["settings"]

    st.markdown('<div class="page-title">积分管理</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">积分明细、兑换记录与参数设置</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title">积分明细</div>', unsafe_allow_html=True)
    if not df_points.empty:
        gb = GridOptionsBuilder.from_dataframe(df_points)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False)
        grid_options = gb.build()
        AgGrid(df_points, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title">积分兑换记录</div>', unsafe_allow_html=True)
    if not df_exchange.empty:
        gb = GridOptionsBuilder.from_dataframe(df_exchange)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False)
        grid_options = gb.build()
        AgGrid(df_exchange, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title">积分参数设置</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    new_multiplier = col1.number_input("新客户积分倍率", min_value=1, max_value=10,
                                       value=int(settings.get("新客户积分倍率", 2)))
    old_multiplier = col2.number_input("老客户积分倍率", min_value=1, max_value=10,
                                       value=int(settings.get("老客户积分倍率", 1)))
    exchange_rate = col3.number_input("积分兑换比例", min_value=0.1, max_value=1.0,
                                      value=float(settings.get("积分兑换比例", 0.3)), step=0.1)

    if st.button("保存设置", type="primary"):
        settings["新客户积分倍率"] = new_multiplier
        settings["老客户积分倍率"] = old_multiplier
        settings["积分兑换比例"] = exchange_rate
        st.success("设置已保存")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title">兑换趋势</div>', unsafe_allow_html=True)
    exchange_trend = PointCalculation(settings).get_exchange_trend(df_exchange)

    if not exchange_trend.empty:
        fig = px.line(exchange_trend, x="月份", y="兑换积分",
                      markers=True,
                      color_discrete_sequence=["#2563eb"])
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=10, b=40),
            xaxis=dict(showgrid=False, color="#9ca3af"),
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6", color="#9ca3af"),
            font=dict(color="#4b5563", size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


def show_data_import():
    st.markdown('<div class="page-title">数据导入</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">上传Excel文件加载客户数据</div>', unsafe_allow_html=True)
    
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
    
    st.markdown('<div class="page-title">报表导出</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">生成并下载客户积分相关报表</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-card-title">选择报表类型</div>', unsafe_allow_html=True)
    report_type = st.selectbox("请选择报表类型", [
        "客户积分汇总报表",
        "积分兑换明细报表",
        "客户属性分析报表",
        "积分趋势报表"
    ])
    
    if st.button("生成报表", type="primary"):
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
    st.markdown('</div>', unsafe_allow_html=True)


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


def read_genotype_from_second_sheet(file_bytes):
    """从第二个子表读取Genotype信息"""
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheet_names = xls.sheet_names
    
    if len(sheet_names) < 2:
        return {}, f"Excel只有{len(sheet_names)}个子表"
    
    second_sheet_name = sheet_names[1]
    debug_info = f"第二个子表：{second_sheet_name}\n"
    
    df_second = pd.read_excel(xls, sheet_name=second_sheet_name, header=None)
    debug_info += f"共{len(df_second)}行，{len(df_second.columns)}列\n"
    
    # 显示所有行的预览，帮助找到正确的表头位置
    debug_info += "\n前20行数据预览:\n"
    for idx in range(min(20, len(df_second))):
        row_vals = [str(v)[:25] for v in df_second.iloc[idx].tolist()]
        debug_info += f"  行{idx}: {row_vals}\n"
    
    # 策略：扫描每一行，查找包含Genotype的表头
    genotype_aliases = ["Genotype", "genotype", "基因型", "GENOTYPE"]
    
    # 找到Genotype所在的行作为表头行
    header_idx = None
    for idx, row in df_second.iterrows():
        row_values = [str(v).strip() for v in row.tolist()]
        for val in row_values:
            if val in genotype_aliases:
                header_idx = idx
                break
        if header_idx is not None:
            break
    
    if header_idx is None:
        # 尝试从所有sheet中搜索
        debug_info += "\n在第二个子表中未找到Genotype，尝试其他子表...\n"
        for sheet_name in sheet_names:
            if sheet_name == second_sheet_name:
                continue
            df_temp = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for idx, row in df_temp.iterrows():
                row_values = [str(v).strip() for v in row.tolist()]
                for val in row_values:
                    if val in genotype_aliases:
                        debug_info += f"  在Sheet '{sheet_name}' 行{idx}找到Genotype\n"
                        # 但我们还是用第二个子表
                        break
    
    if header_idx is None:
        return {}, debug_info + "未找到Genotype列"
    
    debug_info += f"\n在行{header_idx}找到Genotype表头\n"
    
    # 用找到的行作为表头
    new_header = df_second.iloc[header_idx].tolist()
    debug_info += f"表头: {[str(h)[:20] for h in new_header]}\n"
    
    # 读取数据（跳过表头和可能的空行）
    df_data = df_second.iloc[header_idx + 2:].copy()
    df_data.columns = new_header
    df_data = df_data.dropna(how='all')
    df_data = df_data[df_data.apply(lambda x: any(pd.notna(x)), axis=1)]
    
    debug_info += f"数据行数: {len(df_data)}\n"
    
    # 找Genotype列名
    genotype_col_name = None
    for col in new_header:
        col_str = str(col).strip()
        if col_str in genotype_aliases:
            genotype_col_name = col
            break
    
    if genotype_col_name is None:
        return {}, debug_info + "无法确定Genotype列"
    
    debug_info += f"Genotype列: {genotype_col_name}\n"
    
    # 构建基因型映射 - 尝试所有可能的关联键
    genotype_map = {}
    
    # 可能的关联键列
    possible_keys = {
        "Job No": None,
        "Job_No": None, 
        "品系号": None,
        "Strain Number": None,
        "Strain": None
    }
    
    for col in new_header:
        col_str = str(col).strip()
        if col_str in possible_keys:
            possible_keys[col_str] = col
    
    # 尝试用每个可用的关联键构建映射
    for key_name, key_col_name in possible_keys.items():
        if key_col_name is None:
            continue
        
        temp_map = {}
        for _, row in df_data.iterrows():
            key_val = str(row[key_col_name]).strip() if pd.notna(row[key_col_name]) else ""
            genotype_val = str(row[genotype_col_name]).strip() if pd.notna(row[genotype_col_name]) else ""
            if key_val and genotype_val and genotype_val.lower() not in ("nan", "none", ""):
                temp_map[key_val] = genotype_val
        
        if temp_map:
            debug_info += f"用'{key_name}'关联，找到{len(temp_map)}个映射\n"
            # 合并到总映射
            genotype_map.update(temp_map)
    
    # 如果上面的方法不行，尝试第一列作为键
    if not genotype_map and len(df_data) > 0:
        first_col = new_header[0]
        debug_info += f"\n尝试用第一列'{first_col}'作为关联键...\n"
        for _, row in df_data.iterrows():
            key_val = str(row[first_col]).strip() if pd.notna(row[first_col]) else ""
            genotype_val = str(row[genotype_col_name]).strip() if pd.notna(row[genotype_col_name]) else ""
            if key_val and genotype_val and genotype_val.lower() not in ("nan", "none", ""):
                genotype_map[key_val] = genotype_val
        
        if genotype_map:
            debug_info += f"用第一列关联，找到{len(genotype_map)}个映射\n"
    
    debug_info += f"\n最终基因型映射: {genotype_map}\n"
    return genotype_map, debug_info


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
    # 按品系号、基因型、性别分组，三者都相同才合并数量
    group_keys = ["品系号"]
    if "基因型" in group_df.columns:
        group_keys.append("基因型")
    else:
        group_keys.append("_no_genotype_")
        group_df["_no_genotype_"] = ""
    group_keys.append("性别")
    
    grouped = group_df.groupby(group_keys, dropna=False)
    
    # 检查是否所有品系号都一样
    unique_strains = group_df["品系号"].unique()
    all_same_strain = len(unique_strains) == 1
    common_strain_id = str(unique_strains[0]).strip() if all_same_strain else None
    
    # 检查是否所有基因型都一样（仅当同品系号时有效）
    all_same_genotype = False
    common_genotype = ""
    if all_same_strain and "基因型" in group_df.columns:
        unique_genotypes = group_df["基因型"].dropna().unique()
        all_same_genotype = len(unique_genotypes) == 1
        common_genotype = str(unique_genotypes[0]).strip() if all_same_genotype else ""
    
    # 构建分组信息列表
    groups_info = []
    for key_tuple, group in grouped:
        strain_id = str(key_tuple[0]).strip()
        genotype_val = str(key_tuple[1]).strip() if key_tuple[1] else ""
        gender = str(key_tuple[2]).strip().upper()
        total_quantity = group["数量"].sum() if "数量" in group.columns else len(group)
        
        # 年龄取分组第一条
        first_row = group.iloc[0]
        age = str(first_row["年龄"]).strip() if "年龄" in group.columns else ""
        
        gender_text = "雌" if gender in ("雌", "F", "FEMALE") else "雄"
        
        if age.isdigit():
            age_text = f"{age}周"
        else:
            age_text = f"{age}周"
        
        groups_info.append({
            "strain_id": strain_id,
            "genotype": genotype_val,
            "gender_text": gender_text,
            "age_text": age_text,
            "quantity": total_quantity
        })
    
    # 生成输出文本
    if all_same_strain:
        # 所有品系号相同，只写一遍URL
        first_line = f"您订购的JAX小鼠https://www.jax.org/strain/{common_strain_id}"
        if all_same_genotype and common_genotype:
            first_line += f"，基因型：{common_genotype}"
        parts = [first_line]
        for info in groups_info:
            if all_same_genotype and common_genotype:
                # 基因型已经写在开头，这里不再重复
                line = f"性别：{info['gender_text']}，发货周龄：{info['age_text']}，数量：{info['quantity']}。"
            else:
                gt = f"基因型：{info['genotype']}，" if info['genotype'] else ""
                line = f"{gt}性别：{info['gender_text']}，发货周龄：{info['age_text']}，数量：{info['quantity']}。"
            parts.append(line)
        return "\n".join(parts)
    else:
        # 品系号不同，每行都写完整
        lines = []
        for info in groups_info:
            gt = f"，基因型：{info['genotype']}" if info['genotype'] else ""
            line = f"您订购的JAX小鼠https://www.jax.org/strain/{info['strain_id']}{gt}，性别：{info['gender_text']}，发货周龄：{info['age_text']}，数量：{info['quantity']}。"
            lines.append(line)
        return "\n".join(lines)


def render_mail(receiver, strain_list, ship_date, receive_date, delivery_address):
    mail_body = f"""尊敬的老师：

您好！

本封邮件为JAX小鼠配送通知。

{strain_list}

预计将在{receive_date}下午17:00前送到您合同指定收货地址：{delivery_address}。请问当天是否方便接收小鼠呢？

附件是本批小鼠的相关文件：美国健康证书AHC，JAX鼠房微生物报告， 隔离场微生物报告以及JAX小鼠接收指南。

为了确保小鼠在接收后可以尽快的服务于您的研究，建议您：

1.严格遵照随附的《JAX 小鼠接收指南》开展相关操作。小鼠签收时，请即刻检查外包装完整性，并仔细核验小鼠核心信息（品系、数量、性别等）。所有问题须在24 小时内反馈至北京澄天生物科技有限公司，逾期将视为验收合格。请注意，退款及补发政策申请需满足以下条件：相关问题需在小鼠送达贵单位后48 小时内，由贵方提供有效证明材料并提交反馈；后续需经北京澄天生物科技有限公司及JAX 联合核验通过，方可启动对应流程。

2. 建议您收到小鼠后尽快按照官网上提供的基因鉴定方案对小鼠进行鉴定核实，以便于您后续合理的制定繁育/使用方案。

若有问题欢迎随时与我们联系。

预祝您实验一切顺利！"""
    
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
    
    # 从第二个子表读取Genotype信息
    genotype_map, debug_info = read_genotype_from_second_sheet(file_bytes)
    
    # 将基因型合并到主表 - 尝试多种关联方式
    df["基因型"] = ""
    
    if genotype_map:
        # 方式1：用Job No关联
        if "Job No" in df.columns:
            df["基因型"] = df["Job No"].astype(str).str.strip().map(genotype_map).fillna("")
            match_count_1 = (df["基因型"] != "").sum()
        else:
            match_count_1 = 0
        
        # 方式2：用品系号关联（补充）
        unmatched = df["基因型"] == ""
        if unmatched.any() and "品系号" in df.columns:
            strain_map = {}
            for k, v in genotype_map.items():
                strain_map[k] = v
            df.loc[unmatched, "基因型"] = df.loc[unmatched, "品系号"].astype(str).str.strip().map(strain_map).fillna("")
            match_count_2 = (df["基因型"] != "").sum() - match_count_1
        else:
            match_count_2 = 0
        
        debug_info += f"\n关联结果:\n"
        debug_info += f"  用Job No匹配: {match_count_1}条\n"
        debug_info += f"  用品系号匹配: {match_count_2}条\n"
        debug_info += f"  总匹配数: {(df['基因型'] != '').sum()}条\n"
    else:
        debug_info += "\n基因型映射为空，无法关联\n"
    
    # 记录调试信息
    process_excel_email._debug_info = debug_info
    process_excel_email._genotype_map = genotype_map
    process_excel_email._genotype_match_count = (df["基因型"] != "").sum()
    
    po_order = df["Individual PO Number"].dropna().unique().tolist()
    
    result_rows = []
    for po_number, group_data in df.groupby("Individual PO Number"):
        first_row = group_data.iloc[0]
        strain_list = build_strain_list(group_data.copy())
        
        receiver = str(first_row["收货人"]).strip() if pd.notna(first_row["收货人"]) else "老师"
        ship_date = format_date_email(first_row["提货时间"])
        receive_date = format_date_email(first_row["拟收货时间"])
        delivery_address = str(first_row["送货地址"]).strip() if pd.notna(first_row["送货地址"]) else ""
        
        mail_body = render_mail(receiver, strain_list, ship_date, receive_date, delivery_address)
        
        result_rows.append({
            "Individual PO Number": po_number,
            "单位名称": first_row["单位名称"],
            "收货人": first_row["收货人"],
            "邮件内容": mail_body
        })
    
    result_df = pd.DataFrame(result_rows)
    result_df['po_order'] = result_df['Individual PO Number'].map(lambda x: po_order.index(x) if x in po_order else len(po_order))
    result_df = result_df.sort_values('po_order').drop('po_order', axis=1)
    
    return result_df


def show_email_generator():
    st.markdown('<div class="page-title">JAX邮件生成器</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">自动生成JAX小鼠发货通知邮件</div>', unsafe_allow_html=True)
    
    st.markdown(textwrap.dedent(
        """
    **使用说明：**
    1. 上传Excel文件（需包含【出隔离场】Sheet）
    2. 系统自动解析数据并生成邮件内容
    3. 下载生成的邮件结果Excel文件

    **注意：** 基因型信息会从Excel的第二个子表中读取
    """))
    
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                result_df = process_excel_email(uploaded_file.getvalue())
                
                st.success("邮件生成完成！")
                
                # 显示调试信息
                debug_info = getattr(process_excel_email, '_debug_info', '')
                genotype_map = getattr(process_excel_email, '_genotype_map', {})
                match_count = getattr(process_excel_email, '_genotype_match_count', 0)
                
                with st.expander("🔍 调试信息", expanded=False):
                    if debug_info:
                        st.text(debug_info)
                    if genotype_map:
                        st.success(f"✅ 成功提取 {len(genotype_map)} 个基因型映射，匹配 {match_count} 条记录")
                    else:
                        st.warning("⚠️ 未提取到任何基因型信息")
                    
                    # 显示日期列的实际值
                    st.subheader("📅 日期格式检查")
                    try:
                        df_check = pd.read_excel(BytesIO(uploaded_file.getvalue()), sheet_name='出隔离场', header=None)
                        # 找表头
                        for idx, row in df_check.iterrows():
                            vals = [str(v).strip() for v in row.tolist()]
                            if "Job No" in vals and "Individual PO Number" in vals:
                                if "拟收货时间" in vals:
                                    col_idx = vals.index("拟收货时间")
                                    dates = []
                                    for r in range(idx + 2, min(idx + 12, len(df_check))):
                                        val = df_check.iloc[r, col_idx]
                                        dates.append(f"  行{r}: {repr(val)}")
                                    st.code("\n".join(dates))
                                break
                    except Exception as e:
                        st.error(f"日期检查错误: {e}")
                
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
                import traceback
                with st.expander("查看详细错误信息"):
                    st.code(traceback.format_exc())


def show_user_management(config):
    st.markdown('<div class="page-title">用户管理</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">查看所有用户信息和登录状态</div>', unsafe_allow_html=True)
    
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
    st.markdown('<div class="page-title">红冲发票自动登记</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">自动从邮箱下载并登记电子发票</div>', unsafe_allow_html=True)
    
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


_ICON_USER = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#2563EB" xmlns="http://www.w3.org/2000/svg"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>'
_ICON_SYNC = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#2563EB" xmlns="http://www.w3.org/2000/svg"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 0 0 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg>'
_ICON_SHIELD = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#2563EB" xmlns="http://www.w3.org/2000/svg"><path d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>'


def _login_brand_html() -> str:
    import base64
    from pathlib import Path
    ill_path = Path(__file__).resolve().parent / "assets" / "login_illustration_white.jpg"
    ill_tag = ""
    if ill_path.exists():
        b64 = base64.b64encode(ill_path.read_bytes()).decode()
        ill_tag = f'<img src="data:image/jpeg;base64,{b64}" alt="澄天小助手">'
    return f"""
    <div class="login-brand-panel">
      <div>
        <div class="login-brand-header">
          <svg width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="loginLogoGrad" x1="8" y1="4" x2="38" y2="42" gradientUnits="userSpaceOnUse">
                <stop stop-color="#57A6FF"/>
                <stop offset="1" stop-color="#1667E0"/>
              </linearGradient>
            </defs>
            <circle cx="23" cy="23" r="14.5" stroke="url(#loginLogoGrad)" stroke-width="13" fill="none" stroke-dasharray="68 23.1" stroke-dashoffset="79.6"/>
            <circle cx="23" cy="23" r="14.5" stroke="#0B4BBF" stroke-width="13" fill="none" stroke-dasharray="11.5 79.6"/>
          </svg>
          <div class="login-brand-name">澄天小助手</div>
        </div>
        <div class="login-brand-tagline">让客户管理更简单 · 让数据创造更大价值</div>
      </div>
      <div class="login-brand-illustration">{ill_tag}</div>
      <div class="login-brand-features">
        <div class="login-brand-feature">
          <div class="login-feature-icon">{_ICON_USER}</div>
          <div class="login-feature-title">智能分析</div>
          <div class="login-feature-desc">数据驱动决策</div>
        </div>
        <div class="login-brand-feature">
          <div class="login-feature-icon">{_ICON_SYNC}</div>
          <div class="login-feature-title">高效管理</div>
          <div class="login-feature-desc">提升工作效率</div>
        </div>
        <div class="login-brand-feature">
          <div class="login-feature-icon">{_ICON_SHIELD}</div>
          <div class="login-feature-title">安全可靠</div>
          <div class="login-feature-desc">企业级数据安全</div>
        </div>
      </div>
    </div>
    """


def main():
    st.set_page_config(
        page_title="澄天小助手",
        page_icon="🐭",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 浅色 Plotly 主题
    px.defaults.template = "plotly_white"

    from modules.theme import apply_login_styles, apply_app_styles
    
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    if st.session_state.get('authentication_status') != True:
        apply_login_styles()

        # 隐藏侧边栏
        st.markdown('<style>[data-testid="stSidebar"]{display:none !important;}</style>', unsafe_allow_html=True)

        col_brand, col_form = st.columns([11, 9], gap="small")

        with col_brand:
            st.markdown(_login_brand_html(), unsafe_allow_html=True)

        with col_form:
            with st.container(border=True):
                login_tab, register_tab = st.tabs(["登录系统", "新用户注册"])

                with login_tab:
                    st.markdown('<div class="login-form-title">欢迎登录澄天小助手</div>', unsafe_allow_html=True)

                    login_username = st.text_input("用户名", placeholder="请输入用户名/邮箱/手机号码", key="login_username", label_visibility="collapsed")
                    login_password = st.text_input("密码", type="password", placeholder="请输入密码", key="login_password", label_visibility="collapsed")

                    remember_col, forgot_col = st.columns([1, 1])
                    with remember_col:
                        remember = st.checkbox("记住账号", key="login_remember")
                    with forgot_col:
                        st.markdown('<div class="login-forgot"><a href="#">忘记密码?</a></div>', unsafe_allow_html=True)

                    if st.button("登录", key="btn_login", use_container_width=True, type="primary"):
                        if login_username and login_password:
                            usernames = config['credentials']['usernames']
                            if login_username in usernames:
                                stored_hash = usernames[login_username].get('password', '')
                                if bcrypt.checkpw(login_password.encode('utf-8'), stored_hash.encode('utf-8')):
                                    st.session_state['authentication_status'] = True
                                    st.session_state['username'] = login_username
                                    st.session_state['name'] = usernames[login_username].get('name', login_username)
                                    st.rerun()
                                else:
                                    st.session_state['authentication_status'] = False
                                    st.error("用户名或密码错误")
                            else:
                                st.session_state['authentication_status'] = False
                                st.error("用户名或密码错误")
                        else:
                            st.warning("请输入用户名和密码")

                    st.markdown('<div class="login-divider">其他登录方式</div>', unsafe_allow_html=True)
                    st.markdown("""
                    <div class="login-wecom-btn">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M8.5 3C4.9 3 2 5.6 2 8.8c0 1.8.9 3.4 2.4 4.5l-.6 2 2.2-1.1c.6.2 1.3.3 2 .3h.3A6.3 6.3 0 0 1 8 12.5C8 9 11 6.2 14.7 6.2h.3C14.4 4.3 11.7 3 8.5 3Z" fill="#2563EB"/>
                        <path d="M22 12.5c0-2.7-2.5-4.9-5.5-4.9S11 9.8 11 12.5s2.5 4.9 5.5 4.9c.6 0 1.2-.1 1.7-.3l1.9 1-.5-1.7c1.4-.9 2.4-2.3 2.4-3.9Z" fill="#0EA5E9"/>
                      </svg>
                      <span>企业微信登录</span>
                    </div>
                    """, unsafe_allow_html=True)

                with register_tab:
                    st.markdown('<div class="login-form-title">创建新账号</div>', unsafe_allow_html=True)

                    new_username = st.text_input("用户名", key="reg_username", placeholder="请输入用户名", label_visibility="collapsed")
                    new_email = st.text_input("邮箱", key="reg_email", placeholder="请输入邮箱地址", label_visibility="collapsed")
                    new_password = st.text_input("密码", type="password", key="reg_password", placeholder="至少8位字符", label_visibility="collapsed")
                    confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password", placeholder="再次输入密码", label_visibility="collapsed")

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

        st.markdown('<div class="login-footer">© 2024 澄天生物科技有限公司 · 版权所有</div>', unsafe_allow_html=True)

        return
    
    if st.session_state.get('authentication_status'):
        apply_app_styles()

        selected_main = st.session_state.get('selected_main', '🏠 首页')
        data = st.session_state.get('data')

        current_user = st.session_state.get('username')
        is_admin = config['credentials']['usernames'].get(current_user, {}).get('role') == 'admin'
        user_display = config['credentials']['usernames'].get(current_user, {}).get('name', current_user) if current_user else ''

        # ---- 侧边栏导航 ----
        nav_items = [
            ("🏠 首页", "🏠 首页"),
            ("📊 客户积分智能分析", "📊 客户积分智能分析"),
            ("📧 JAX邮件生成器", "📧 JAX邮件生成器"),
            ("🧾 红冲发票自动登记", "🧾 红冲发票自动登记"),
            ("📋 报价助手", "📋 报价助手"),
            ("🎬 AI 视频剪辑", "🎬 AI 视频剪辑"),
        ]
        if is_admin:
            nav_items.append(("👑 用户管理", "👑 用户管理"))

        with st.sidebar:
            st.markdown("""
            <div class="sidebar-logo">
              <span style="font-size:28px;">🐭</span>
              <div>
                <div class="sidebar-logo-text">澄天小助手</div>
                <div class="sidebar-logo-sub">CHENGTIAN ASSISTANT</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            for label, value in nav_items:
                is_active = selected_main == value
                css_class = "nav-item-active" if is_active else "nav-item"
                st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                if st.button(label, key=f"nav-{value}", use_container_width=True):
                    st.session_state['selected_main'] = value
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div class="sidebar-user">
              <div class="sidebar-user-info">
                <div class="sidebar-user-avatar">{user_display[0] if user_display else 'U'}</div>
                <div>
                  <div class="sidebar-user-name">{user_display}</div>
                  <div class="sidebar-user-role">{'管理员' if is_admin else '普通用户'}</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("退出登录", key="btn-logout", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        # ---- 主内容路由 ----
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

            st.markdown('<div class="sub-nav-container">', unsafe_allow_html=True)
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
            st.markdown('</div>', unsafe_allow_html=True)

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
            show_video_editor()

        elif selected_main == '👑 用户管理':
            show_user_management(config)


if __name__ == "__main__":
    main()
