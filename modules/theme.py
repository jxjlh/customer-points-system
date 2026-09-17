"""
澄天小助手 - 现代企业 SaaS 主题
基于参考图设计的浅色主题：蓝色主色调(#2563EB)，白底卡片，浅灰背景
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
    """页面切换动画：不注入动画"""
    pass


def apply_all_styles():
    """一次性应用所有样式"""
    import streamlit as st
    css = _get_global_css() + _get_sidebar_css() + _get_home_cards_css() + _get_kpi_css() + _get_misc_css()
    st.markdown(css, unsafe_allow_html=True)


def apply_login_styles():
    """登录页专用样式：分屏布局"""
    import streamlit as st
    css = _get_global_css() + _get_login_css()
    st.markdown(css, unsafe_allow_html=True)


def apply_app_styles():
    """应用页面样式（侧边栏 + 卡片等）"""
    import streamlit as st
    css = _get_global_css() + _get_sidebar_css() + _get_home_cards_css() + _get_kpi_css() + _get_misc_css()
    st.markdown(css, unsafe_allow_html=True)


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue") -> str:
    """渲染单个首页卡片的 HTML"""
    icon_safe = html.escape(str(icon))
    title_safe = html.escape(str(title))
    desc_safe = html.escape(str(desc))
    color_safe = html.escape(str(color_class), quote=True)
    return textwrap.dedent(
        f"""
        <div class="home-card {color_safe}" onclick="this.querySelector('button').click()">
          <div class="home-card-icon">{icon_safe}</div>
          <div class="home-card-title">{title_safe}</div>
          <div class="home-card-desc">{desc_safe}</div>
          <span class="home-card-arrow">点击进入 →</span>
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
    /* 页面背景：浅灰 */
    [data-testid="stAppViewContainer"] {
        background: #f8fafc;
    }
    /* 主内容区宽度 */
    [data-testid="stMainBlockContainer"] {
        max-width: 1400px;
        padding-top: 2rem;
    }
    /* 隐藏页脚 */
    footer {visibility: hidden;}
    /* 隐藏顶部三滴水菜单 */
    [data-testid="stMainMenu"] {visibility: hidden;}
    /* 隐藏首页卡片下方的隐藏按钮 */
    .hidden-home-card-button button {display: none !important;}
    /* 子导航横向排布 */
    .sub-nav-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 16px;
        padding: 6px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #ffffff;
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
        margin-bottom: 8px;
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

    /* 侧边栏导航按钮 */
    .nav-item button,
    .nav-item-active button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 10px 12px !important;
        border: none !important;
        background: transparent !important;
        color: #4b5563 !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        border-left: 3px solid transparent !important;
        margin-bottom: 2px !important;
        height: auto !important;
        min-height: 40px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .nav-item button:hover {
        background: #f3f4f6 !important;
        border-color: #d1d5db !important;
        color: #111827 !important;
    }
    .nav-item-active button {
        background: #eff6ff !important;
        color: #2563eb !important;
        border-left: 3px solid #2563eb !important;
        font-weight: 600 !important;
    }

    /* 侧边栏用户信息区域 */
    .sidebar-user {
        padding: 16px 12px;
        border-top: 1px solid #f3f4f6;
        margin-top: 8px;
    }
    .sidebar-user-info {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }
    .sidebar-user-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #2563eb;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 600;
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
    /* ===== 登录页：浅蓝底、全宽无边距 ===== */
    /* 部署环境可能是暗色主题：强制覆盖主题变量，让所有控件回到浅色 */
    :root {
        --background-color: #EAF2FB;
        --secondary-background-color: #ffffff;
        --text-color: #1F2937;
        --primary-color: #2563EB;
    }
    [data-testid="stAppViewContainer"] {
        background: #EAF2FB;
    }
    /* 登录页隐藏顶部工具栏和底部运行状态条 */
    [data-testid="stHeader"], [data-testid="stBottom"], [data-testid="stStatusWidget"] {
        display: none !important;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        padding: 0 !important;
    }

    /* ---- 左侧品牌区：按内容定位顶层列（跨版本稳定） ---- */
    [data-testid="stColumn"]:has(.login-brand-panel) {
        background: linear-gradient(155deg, #F6FAFE 0%, #E9F1FB 55%, #DEEAF8 100%);
        min-height: 100vh;
    }

    .login-brand-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 92vh;
        padding: 48px 56px 36px;
        box-sizing: border-box;
        color: #1F2937;
    }
    .login-brand-header {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .login-brand-name {
        font-size: 26px;
        font-weight: 700;
        color: #1F2937;
        letter-spacing: 2px;
    }
    .login-brand-tagline {
        font-size: 14px;
        color: #6B7C93;
        margin-top: 14px;
        letter-spacing: 1px;
    }
    .login-brand-illustration {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 12px 0 24px;
        min-height: 180px;
        overflow: hidden;
    }
    .login-brand-illustration img {
        width: 100%;
        max-width: 520px;
        max-height: 38vh;
        object-fit: contain;
        mix-blend-mode: multiply;
    }
    /* 特性区：整体收进白色卡片，避免文字与渐变底色重叠、字段分散 */
    .login-brand-features {
        display: flex;
        gap: 32px;
        padding: 18px 24px;
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid rgba(37, 99, 235, 0.10);
        border-radius: 12px;
        box-shadow: 0 4px 14px rgba(31, 86, 201, 0.06);
    }
    .login-brand-feature {
        flex: none;
    }
    .login-feature-icon {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: #DBEAFE;
        border: 1px solid #BFDBFE;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .login-feature-title {
        font-size: 14px;
        font-weight: 600;
        color: #111827;
        margin-top: 10px;
    }
    .login-feature-desc {
        font-size: 12px;
        color: #4B5563;
        margin-top: 4px;
    }

    /* ---- 右侧表单区：透明底，白色卡片居中 ---- */
    [data-testid="stMainBlockContainer"] > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        background: transparent;
    }
    [data-testid="stMainBlockContainer"] > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child
    > [data-testid="stVerticalBlock"] {
        padding: 48px 40px;
        justify-content: center;
        height: 100%;
        box-sizing: border-box;
    }

    /* 登录卡片：白底圆角轻阴影 */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 6px 24px rgba(31, 86, 201, 0.10) !important;
        padding: 28px 40px 36px !important;
        max-width: 460px !important;
        width: 100%;
        margin: 0 auto !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlockBorderWrapper"] * {
        color: #334155 !important;
    }

    /* Tabs：等分两半，激活蓝色下划线 */
    [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="tab-list"] {
        display: flex;
        width: 100%;
        border-bottom: 1px solid #E8EDF3;
        margin-bottom: 24px;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="tab"] {
        flex: 1;
        display: flex;
        justify-content: center;
        padding: 12px 0;
        font-size: 14px;
        color: #6B7C93;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [aria-selected="true"] {
        color: #2563EB !important;
        font-weight: 600;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="tab-border"] {
        border-bottom: 2px solid #2563EB !important;
    }

    /* 表单标题：左对齐 */
    .login-form-title {
        font-size: 18px;
        font-weight: 600;
        color: #1F2937;
        text-align: left;
        margin: 4px 0 20px;
    }

    /* 输入框：细边框 + 内置图标 */
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stTextInput"] > div:has(input) {
        position: relative;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stTextInput"] > div:has(input)::before {
        content: "";
        position: absolute;
        left: 12px;
        top: 50%;
        transform: translateY(-50%);
        width: 16px;
        height: 16px;
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
        z-index: 2;
        pointer-events: none;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stTextInput"]:has(input[type="text"]) > div:has(input)::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2398A4B3'%3E%3Cpath d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/%3E%3C/svg%3E");
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stTextInput"]:has(input[type="password"]) > div:has(input)::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2398A4B3'%3E%3Cpath d='M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z'/%3E%3C/svg%3E");
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stTextInput"]:has(input[type="password"]) > div:has(input)::after {
        content: "";
        position: absolute;
        right: 12px;
        top: 50%;
        transform: translateY(-50%);
        width: 16px;
        height: 16px;
        background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2398A4B3'%3E%3Cpath d='M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z'/%3E%3C/svg%3E") no-repeat center / contain;
        pointer-events: none;
    }
    [data-testid="stVerticalBlockBorderWrapper"] input[type="text"],
    [data-testid="stVerticalBlockBorderWrapper"] input[type="password"] {
        border: 1px solid #DCE3EB !important;
        border-radius: 6px !important;
        background: #ffffff !important;
        color: #1F2937 !important;
        padding: 0 36px !important;
        font-size: 13px !important;
        height: 42px !important;
        -webkit-text-fill-color: #1F2937 !important;
        caret-color: #2563eb !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] input[type="text"]:focus,
    [data-testid="stVerticalBlockBorderWrapper"] input[type="password"]:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] input::placeholder {
        color: #A6B0BD !important;
        -webkit-text-fill-color: #A6B0BD !important;
    }

    /* 记住账号 / 忘记密码 行 */
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCheckbox"] label span {
        font-size: 13px;
        color: #334155 !important;
    }
    .login-forgot {
        text-align: right;
        padding-top: 4px;
    }
    .login-forgot p {
        margin: 0;
        line-height: 24px;
    }
    .login-forgot a {
        color: #2563EB !important;
        font-size: 13px;
        text-decoration: none;
    }

    /* 登录按钮 */
    [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
        background: #2563EB !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        height: 42px !important;
        width: 100% !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"]:hover {
        background: #1D54D8 !important;
    }

    /* 分隔线 */
    .login-divider {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #9AA6B5;
        font-size: 12px;
        margin: 22px 0 16px;
    }
    .login-divider::before,
    .login-divider::after {
        content: "";
        flex: 1;
        height: 1px;
        background: #E8EDF3;
    }

    /* 企业微信登录按钮 */
    .login-wecom-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        height: 42px;
        border: 1px solid #DCE3EB;
        border-radius: 6px;
        background: #ffffff;
        color: #334155;
        font-size: 13px;
        cursor: pointer;
        width: 100%;
    }
    .login-wecom-btn:hover {
        background: #F7FAFD;
        border-color: #C9D6E8;
    }

    /* 登录页底部版权 */
    .login-footer {
        text-align: center;
        font-size: 12px;
        color: #9AA6B5;
        padding: 20px 0 28px;
    }
    .login-footer p { margin: 0; }
    </style>
    """


def _get_home_cards_css() -> str:
    return """
    <style>
    .home-card-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin: 16px 0 24px;
    }
    @media (max-width: 1024px) {
        .home-card-container {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    @media (max-width: 640px) {
        .home-card-container {
            grid-template-columns: 1fr;
        }
    }
    .home-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px 20px;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .home-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
        border-color: #d1d5db;
    }
    .home-card-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        margin-bottom: 16px;
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
        margin-bottom: 12px;
    }
    .home-card-arrow {
        display: inline-block;
        color: #2563eb;
        font-size: 13px;
        font-weight: 500;
        transition: transform 0.15s ease;
    }
    .home-card:hover .home-card-arrow {
        transform: translateX(4px);
    }
    /* 各颜色 class：图标背景色 */
    .card-blue   .home-card-icon { background: #dbeafe; color: #2563eb; }
    .card-indigo .home-card-icon { background: #e0e7ff; color: #4f46e5; }
    .card-green  .home-card-icon { background: #d1fae5; color: #059669; }
    .card-orange .home-card-icon { background: #ffedd5; color: #ea580c; }
    .card-purple .home-card-icon { background: #ede9fe; color: #7c3aed; }
    .card-pink   .home-card-icon { background: #fce7f3; color: #db2777; }
    .card-cyan   .home-card-icon { background: #cffafe; color: #0891b2; }
    .card-teal   .home-card-icon { background: #ccfbf1; color: #0d9488; }

    /* 首页头部问候区域 */
    .home-greeting {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
    }
    .home-greeting-text h2 {
        font-size: 24px;
        font-weight: 700;
        color: #111827;
        margin: 0 0 4px;
    }
    .home-system-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #6b7280;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #22c55e;
        display: inline-block;
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
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
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
    .trend-up {
        color: #16a34a;
        background: #dcfce7;
    }
    .trend-down {
        color: #dc2626;
        background: #fee2e2;
    }

    /* 日期筛选栏 */
    .date-filter-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        padding: 12px 16px;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
    }
    .date-filter-label {
        font-size: 14px;
        color: #4b5563;
        font-weight: 500;
    }

    /* 图表卡片容器 */
    .chart-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
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
    /* 客户管理：搜索筛选栏 */
    .search-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;
        padding: 16px;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
    }

    /* 详情面板 */
    .detail-panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .detail-panel-title {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #f3f4f6;
    }
    .detail-section {
        margin-bottom: 20px;
    }
    .detail-section-title {
        font-size: 13px;
        font-weight: 600;
        color: #6b7280;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .detail-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 6px;
        font-size: 14px;
    }
    .detail-label {
        color: #6b7280;
    }
    .detail-value {
        color: #111827;
        font-weight: 500;
    }
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

    /* Streamlit 标签按钮（子导航）样式 */
    .sub-nav-container button {
        border: 1px solid #e5e7eb !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        font-size: 13px !important;
    }
    .sub-nav-container button[kind="primary"] {
        background: #2563eb !important;
        color: white !important;
        border-color: #2563eb !important;
    }
    </style>
    """
