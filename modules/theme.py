"""
澄天小助手 - 极简主题（普通、干净、接近 Streamlit 默认）

设计原则：
- 不覆盖 .stApp / [data-testid=stAppViewContainer] 背景，保持 Streamlit 原生白底
- 尽量用 Streamlit 原生按钮/输入框/表格样式，只在必须适配现有功能时加最轻量 CSS
- 去掉所有「霓虹/玻璃态/发光/网格背景/浮动动画/自定义字体」的装饰效果
- 保持向后兼容：class 名（home-card-container / home-card / login-container / card-blue 等）不变，
  这样 app.py / home_cards.py / video_editor.py 里的引用无需改名
"""
import textwrap


def apply_theme():
    """应用全局主题样式（极简）"""
    import streamlit as st
    st.markdown(_get_global_css(), unsafe_allow_html=True)


def render_home_cards():
    """首页卡片 CSS：只保留 grid 排版和普通 hover，去掉发光/浮动动画"""
    import streamlit as st
    st.markdown(_get_home_cards_css(), unsafe_allow_html=True)


def render_metric_cards():
    """指标卡片样式：不额外美化，空实现即可保留 Streamlit 原生"""
    # 故意留空：极简模式不再重写 stMetric 外观，保持 Streamlit 默认样式
    pass


def render_page_transition():
    """页面切换动画：极简模式下关闭动画，避免卡顿和视觉装饰"""
    # 故意留空：不注入入场/过渡动画
    pass


def apply_all_styles():
    """一次性应用所有样式"""
    import streamlit as st
    css = _get_global_css() + _get_home_cards_css()
    st.markdown(css, unsafe_allow_html=True)


def _get_global_css() -> str:
    """
    全局 CSS（极简）。

    保留的必要性样式：
    - 隐藏 Streamlit 的页脚（不是为了美观，而是版权文字干扰页面内容）
    - 隐藏登录路由时的侧边栏（配合 app.py 里 [data-testid=stSidebar] display:none 使用）
    - 给自定义的 .login-container 一个简单的居中宽度，让登录页不会撑满整个屏幕
    - 让 app.py 里的 .sub-nav-container 能横向排列子导航按钮
    """
    return """
    <style>
    /* 只隐藏无用的页脚/顶部三滴水菜单；不改变 Streamlit 原生白底背景 */
    footer {visibility: hidden;}

    /* 登录路由时，侧边栏不再显示。其他路由用 Streamlit 默认。 */
    [data-testid="stSidebar"].no-show {
        display: none;
    }

    /* 登录容器：简单居中，不再使用渐变/发光边框 */
    .login-container {
        max-width: 460px;
        margin: 40px auto;
        padding: 16px;
    }

    /* 子导航：横向排布 + 圆角 + 轻边框，不用发光/渐变 */
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

    /* 首页卡片下方由 home_cards.py 生成了同名隐藏 button，
       用来驱动卡片点击后的 rerun 路由。
       彻底隐藏整个容器及其内部所有元素。 */
    .hidden-home-card-button {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    </style>
    """


def _get_home_cards_css() -> str:
    """
    首页模块卡片 CSS。
    """
    return """
    <style>
    .home-card-wrapper {
        position: relative;
        overflow: visible;
    }

    .home-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 24px 16px;
        cursor: pointer;
        transition: all 0.2s ease;
        border-left: 4px solid var(--card-color-1, #9ca3af);
        text-align: center;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100px;
        margin-bottom: 0;
    }

    .home-card:hover {
        background: #f0f4ff;
        border-color: var(--card-color-1, #3b82f6);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

    .home-card-icon {
        font-size: 42px;
        line-height: 1;
        display: inline-block;
    }

    /* stButton 容器 - 向上移动覆盖卡片 */
    div[data-testid="stButton"] {
        margin-top: -100px !important;
        margin-bottom: 0 !important;
        position: relative !important;
        z-index: 10 !important;
    }

    /* 所有按钮完全透明 */
    div[data-testid="stButton"] button,
    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        min-height: 100px !important;
        height: 100px !important;
        padding: 0 !important;
        cursor: pointer !important;
        width: 100% !important;
        color: transparent !important;
    }

    /* 彻底隐藏按钮内所有文字内容 */
    div[data-testid="stButton"] p,
    div[data-testid="stButton"] span,
    div[data-testid="stButton"] div,
    div[data-testid="stButton"] label {
        display: none !important;
        font-size: 0 !important;
        line-height: 0 !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }

    /* Tooltip 图标也隐藏 */
    div[data-testid="stTooltipIcon"],
    div[data-testid="stTooltipHoverTarget"] {
        display: none !important;
    }

    /* 兼容原有颜色 class */
    .card-blue   { --card-color-1: #3b82f6; --card-color-2: #3b82f6; }
    .card-green  { --card-color-1: #10b981; --card-color-2: #10b981; }
    .card-orange { --card-color-1: #f97316; --card-color-2: #f97316; }
    .card-purple { --card-color-1: #8b5cf6; --card-color-2: #8b5cf6; }
    .card-pink   { --card-color-1: #ec4899; --card-color-2: #ec4899; }
    .card-cyan   { --card-color-1: #0ea5e9; --card-color-2: #0ea5e9; }
    </style>
    """


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue", card_key: str = "") -> str:
    """
    渲染单个首页卡片的 HTML（仅图标）。
    """
    import html
    icon_safe = html.escape(str(icon))
    color_safe = html.escape(str(color_class), quote=True)
    key_safe = html.escape(str(card_key), quote=True)
    return textwrap.dedent(
        f"""
        <div class="home-card {color_safe}" data-key="{key_safe}">
          <div class="home-card-icon">{icon_safe}</div>
        </div>
        """
    ).strip() + "\n"
