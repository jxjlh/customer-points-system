"""
澄天小助手 - 现代企业 SaaS 主题
浅色主题：蓝色主色调(#2563EB)，白底卡片，浅灰背景
"""
import textwrap
import html


def apply_theme():
    """应用全局主题样式"""
    import streamlit as st
    st.markdown(_get_global_css(), unsafe_allow_html=True)


def render_home_cards():
    """首页卡片 CSS"""
    import streamlit as st
    st.markdown(_get_home_cards_css(), unsafe_allow_html=True)


def render_metric_cards():
    """KPI 指标卡片 CSS"""
    import streamlit as st
    st.markdown(_get_kpi_css(), unsafe_allow_html=True)


def render_page_transition():
    """页面切换动画"""
    pass


def apply_all_styles():
    """一次性应用所有样式"""
    import streamlit as st
    css = (_get_global_css() + _get_sidebar_css() + _get_home_cards_css()
           + _get_kpi_css() + _get_misc_css())
    st.markdown(css, unsafe_allow_html=True)


def apply_login_styles():
    """登录页专用样式"""
    import streamlit as st
    css = _get_global_css() + _get_login_css()
    st.markdown(css, unsafe_allow_html=True)


def apply_app_styles():
    """应用页面样式（侧边栏 + 卡片等）"""
    import streamlit as st
    css = (_get_global_css() + _get_sidebar_css() + _get_home_cards_css()
           + _get_kpi_css() + _get_misc_css())
    st.markdown(css, unsafe_allow_html=True)


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue") -> str:
    """渲染单个首页卡片的 HTML"""
    icon_safe = html.escape(str(icon))
    title_safe = html.escape(str(title))
    desc_safe = html.escape(str(desc))
    color_safe = html.escape(str(color_class), quote=True)
    return textwrap.dedent(
        f"""
        <div class="home-card {color_safe}">
          <div class="home-card-icon">{icon_safe}</div>
          <div class="home-card-title">{title_safe}</div>
          <div class="home-card-desc">{desc_safe}</div>
        </div>
        """
    ).strip() + "\n"


def render_kpi_card(icon: str, value, label: str, trend=None, trend_up=True, color="blue") -> str:
    """渲染单个 KPI 指标卡片 HTML"""
    icon_safe = html.escape(str(icon))
    value_safe = str(value)
    label_safe = html.escape(str(label))
    color_map = {
        "blue": ("#dbeafe", "#2563eb"),
        "green": ("#d1fae5", "#059669"),
        "orange": ("#ffedd5", "#ea580c"),
        "purple": ("#ede9fe", "#7c3aed"),
        "teal": ("#ccfbf1", "#0d9488"),
        "indigo": ("#e0e7ff", "#4f46e5"),
        "cyan": ("#cffafe", "#0891b2"),
        "pink": ("#fce7f3", "#db2777"),
    }
    bg, fg = color_map.get(color, color_map["blue"])
    trend_html = ""
    if trend is not None:
        trend_class = "trend-up" if trend_up else "trend-down"
        arrow = "↑" if trend_up else "↓"
        trend_html = f'<span class="kpi-trend {trend_class}">{arrow} {trend}% 较上月</span>'
    return textwrap.dedent(
        f"""
        <div class="kpi-card">
          <div class="kpi-icon" style="background:{bg};color:{fg};">{icon_safe}</div>
          <div class="kpi-value">{value_safe}</div>
          <div class="kpi-label">{label_safe}</div>
          {trend_html}
        </div>
        """
    ).strip() + "\n"


def render_kpi_grid(cards_html_list) -> str:
    """渲染 KPI 卡片网格"""
    inner = "".join(cards_html_list)
    return f'<div class="kpi-grid">{inner}</div>'


# ---------------------------------------------------------------------------
# CSS getters
# ---------------------------------------------------------------------------

def _get_global_css() -> str:
    return """
    <style>
    /* ===== 全局浅色主题基础 ===== */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #f8fafc;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1200px;
        padding-top: 1.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }

    /* 隐藏 Streamlit 顶部黑栏（含 Fork/Deploy 按钮） */
    [data-testid="stHeader"] {
        display: none !important;
    }
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* 隐藏页脚 */
    footer {visibility: hidden;}
    [data-testid="stFooter"] {display: none !important;}

    /* 隐藏右上角菜单 */
    [data-testid="stMainMenu"] {visibility: hidden;}

    /* 输入框文字颜色 */
    input, textarea, select {
        color: #111827;
    }
    input::placeholder, textarea::placeholder {
        color: #9ca3af;
    }

    /* 通用标题样式 */
    .page-title {
        font-size: 22px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 4px;
    }
    .page-subtitle {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 20px;
    }

    /* 子导航横向排布 */
    .sub-nav-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 16px;
        padding: 8px;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        background: #ffffff;
    }
    .sub-nav-container button {
        border: 1px solid #e5e7eb !important;
        border-radius: 8px !important;
        padding: 6px 14px !important;
        font-size: 13px !important;
        background: #ffffff !important;
        color: #4b5563 !important;
    }
    .sub-nav-container button:hover {
        border-color: #2563eb !important;
        color: #2563eb !important;
    }
    .sub-nav-container button[kind="primary"],
    .sub-nav-container button[data-testid="baseButton-primary"] {
        background: #2563eb !important;
        color: #ffffff !important;
        border-color: #2563eb !important;
    }

    /* 全局按钮圆角 */
    button[kind="primary"], .stButton > button[kind="primary"] {
        border-radius: 8px;
    }

    /* 分隔线颜色 */
    hr, [data-testid="stDivider"] {
        border-color: #e5e7eb !important;
    }
    </style>
    """


def _get_sidebar_css() -> str:
    return """
    <style>
    /* 侧边栏整体 */
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0;
        padding-top: 0;
    }

    /* 侧边栏 Logo 区域 */
    .sidebar-logo {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 20px 16px 16px;
        border-bottom: 1px solid #f3f4f6;
        margin-bottom: 12px;
    }
    .sidebar-logo-text {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
    }
    .sidebar-logo-sub {
        font-size: 11px;
        color: #9ca3af;
        letter-spacing: 1px;
    }

    /* 侧边栏导航按钮：重置为干净的菜单样式 */
    section[data-testid="stSidebar"] .nav-item,
    section[data-testid="stSidebar"] .nav-item-active {
        margin-bottom: 2px;
    }
    section[data-testid="stSidebar"] .nav-item button,
    section[data-testid="stSidebar"] .nav-item-active button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 10px 14px !important;
        border: none !important;
        border-radius: 8px !important;
        background: transparent !important;
        color: #4b5563 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-left: 3px solid transparent !important;
        margin-bottom: 2px !important;
        height: auto !important;
        min-height: 42px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    section[data-testid="stSidebar"] .nav-item button p,
    section[data-testid="stSidebar"] .nav-item-active button p {
        color: inherit !important;
        font-size: 14px !important;
    }
    section[data-testid="stSidebar"] .nav-item button:hover {
        background: #f3f4f6 !important;
        color: #111827 !important;
    }
    section[data-testid="stSidebar"] .nav-item-active button {
        background: #eff6ff !important;
        color: #2563eb !important;
        border-left: 3px solid #2563eb !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] .nav-item-active button p {
        color: #2563eb !important;
    }

    /* 侧边栏用户信息区域 */
    .sidebar-user {
        padding: 16px 12px;
        border-top: 1px solid #f3f4f6;
        margin-top: 12px;
    }
    .sidebar-user-info {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .sidebar-user-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #2563eb;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 600;
        flex-shrink: 0;
    }
    .sidebar-user-name {
        font-size: 13px;
        font-weight: 600;
        color: #111827;
    }
    .sidebar-user-role {
        font-size: 11px;
        color: #9ca3af;
    }
    </style>
    """


def _get_login_css() -> str:
    return """
    <style>
    /* ===== 登录页（顶部品牌横幅 + 居中卡片） ===== */
    [data-testid="stAppViewContainer"] {
        background: #eef3fb;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        padding: 0 !important;
    }
    [data-testid="stMainBlockContainer"] > div {
        padding: 0 !important;
    }

    /* 顶部品牌横幅 */
    .login-header {
        background: linear-gradient(180deg, #d9e6f7 0%, #e7eef9 55%, #eef3fb 100%);
        padding: 34px 48px 28px;
    }
    .login-header-top {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .login-header-name {
        font-size: 30px;
        font-weight: 700;
        color: #1f2937;
        letter-spacing: 0.5px;
    }
    .login-header-tagline {
        margin-top: 12px;
        font-size: 14px;
        color: #64748b;
    }

    /* 居中登录卡片 */
    [data-testid="stVerticalBlockBorderWrapper"] {
        max-width: 560px !important;
        margin: 60px auto 10px !important;
        border: none !important;
        border-radius: 16px !important;
        background: #ffffff !important;
        box-shadow: 0 12px 36px rgba(15, 23, 42, 0.10) !important;
        padding: 6px 40px 30px !important;
    }

    /* 选项卡：登录系统 / 新用户注册 */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        border-bottom: 1px solid #e5e7eb;
        gap: 4px;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 12px 18px;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] p {
        font-size: 15px;
        font-weight: 600;
        color: #6b7280;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {
        color: #2563eb;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: #2563eb !important;
        height: 3px !important;
        border-radius: 2px !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none;
    }

    /* 表单标题 */
    .login-form-title {
        font-size: 19px;
        font-weight: 700;
        color: #111827;
        margin: 8px 0 20px;
    }

    /* 输入框：浅灰圆角 + 左侧图标 */
    [data-testid="stTextInput"] input {
        height: 46px !important;
        border: 1px solid #d1d5db !important;
        border-radius: 10px !important;
        background-color: #ffffff !important;
        background-repeat: no-repeat !important;
        background-position: 12px center !important;
        background-size: 18px 18px !important;
        padding-left: 40px !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
    }
    input[aria-label="用户名"] {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%233b82f6'%3E%3Cpath d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/%3E%3C/svg%3E") !important;
    }
    input[aria-label="密码"] {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%233b82f6'%3E%3Cpath d='M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z'/%3E%3C/svg%3E") !important;
    }

    /* 记住账号 / 忘记密码 */
    .login-forgot {
        text-align: right;
        font-size: 13px;
        padding-top: 6px;
    }
    .login-forgot a {
        color: #2563eb;
        text-decoration: none;
        font-weight: 500;
    }
    .login-forgot a:hover {
        text-decoration: underline;
    }

    /* 主按钮（登 录 / 注册） */
    [data-testid="stButton"] button[kind="primary"] {
        background: #2563eb !important;
        border: none !important;
        height: 46px !important;
        border-radius: 10px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25) !important;
    }
    [data-testid="stButton"] button[kind="primary"]:hover {
        background: #1d4ed8 !important;
    }

    /* 其他登录方式分隔 */
    .login-divider {
        text-align: center;
        color: #9ca3af;
        font-size: 12px;
        margin: 18px 0 10px;
    }

    /* 页脚版权 */
    .login-footer {
        text-align: center;
        font-size: 12px;
        color: #94a3b8;
        padding: 10px 0 30px;
    }
    </style>
    """


def _get_home_cards_css() -> str:
    return """
    <style>
    /* ===== 首页问候区 ===== */
    .home-greeting {
        margin-bottom: 8px;
    }
    .home-greeting-text h2 {
        font-size: 26px;
        font-weight: 700;
        color: #111827;
        margin: 0 0 6px;
    }
    .home-system-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 16px;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #22c55e;
        display: inline-block;
    }

    /* ===== 首页功能卡片按钮 ===== */
    /* 定位主内容区 columns 中的按钮（排除侧边栏和子导航） */
    [data-testid="stMainBlockContainer"] [data-testid="stColumn"] [data-testid="stButton"] button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 18px 18px !important;
        background: #ffffff !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 14px !important;
        color: #111827 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        min-height: 90px !important;
        height: auto !important;
        line-height: 1.5 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        transition: all 0.2s ease !important;
        white-space: pre-line !important;
        overflow: visible !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stColumn"] [data-testid="stButton"] button p {
        color: #111827 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        margin: 0 !important;
        white-space: pre-line !important;
        line-height: 1.5 !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stColumn"] [data-testid="stButton"] button:hover {
        border-color: #2563eb !important;
        box-shadow: 0 6px 20px rgba(37,99,235,0.12) !important;
        transform: translateY(-2px) !important;
        background: #f8faff !important;
    }

    /* 子导航按钮不使用卡片样式 */
    .sub-nav-container [data-testid="stButton"] button {
        min-height: auto !important;
        height: auto !important;
        padding: 6px 14px !important;
        border-radius: 8px !important;
    }

    /* 原生 home-card（HTML 版，备用） */
    .home-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 24px 20px;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .home-card:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.08);
        transform: translateY(-2px);
        border-color: #bfdbfe;
    }
    .home-card-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        margin-bottom: 14px;
    }
    .home-card-title {
        font-size: 16px;
        font-weight: 600;
        color: #111827;
        margin: 0 0 6px;
    }
    .home-card-desc {
        font-size: 13px;
        color: #6b7280;
        line-height: 1.5;
    }
    </style>
    """


def _get_kpi_css() -> str:
    return """
    <style>
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin: 16px 0 24px;
    }
    @media (max-width: 1024px) {
        .kpi-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .kpi-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        margin-bottom: 12px;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 13px;
        color: #6b7280;
        margin-top: 4px;
    }
    .kpi-trend {
        font-size: 12px;
        margin-top: 8px;
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .trend-up { color: #16a34a; background: #dcfce7; }
    .trend-down { color: #dc2626; background: #fee2e2; }

    .date-filter-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        padding: 12px 16px;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
    }
    .date-filter-label {
        font-size: 14px;
        color: #4b5563;
        font-weight: 500;
    }

    .chart-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .chart-card-title {
        font-size: 16px;
        font-weight: 600;
        color: #111827;
        margin-bottom: 16px;
    }
    </style>
    """


def _get_misc_css() -> str:
    return """
    <style>
    .search-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;
        padding: 16px;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
    }
    .detail-panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .detail-panel-title {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #f3f4f6;
    }
    .detail-section { margin-bottom: 20px; }
    .detail-section-title {
        font-size: 13px;
        font-weight: 600;
        color: #6b7280;
        margin-bottom: 8px;
    }
    .detail-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 6px;
        font-size: 14px;
    }
    .detail-label { color: #6b7280; }
    .detail-value { color: #111827; font-weight: 500; }
    .detail-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .tag-blue { background: #dbeafe; color: #2563eb; }
    .tag-green { background: #d1fae5; color: #059669; }
    .tag-orange { background: #ffedd5; color: #ea580c; }
    .tag-purple { background: #ede9fe; color: #7c3aed; }

    /* Streamlit 表格优化 */
    [data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
    """
