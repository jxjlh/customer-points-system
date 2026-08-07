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
       用来驱动卡片点击后的 rerun 路由。默认情况下 Streamlit 会把这些
       button 显示在卡片下面，视觉上是多余的——display:none 隐藏它们，
       同时保留 button 在 DOM 里，保证 home-card 的 onclick 能触发。 */
    .hidden-home-card-button button {
        display: none !important;
    }
    </style>
    """


def _get_home_cards_css() -> str:
    """
    首页模块卡片 CSS（极简）。

    功能上只保留：
    - grid auto-fit 自适应宽度；
    - 普通浅灰卡片背景、圆角、hover 时淡一点背景色；
    - 图标/标题/描述的基础排版、颜色（用系统默认文字色即可，不加霓虹/渐变）；
    - 卡片「点击进入 →」hover 时向右挪一点点；
    - 原有的 card-blue / card-green 等 class 保留兼容，但只给一个很浅的左色条，
      不再使用发光/渐变/浮动动画。
    """
    return """
    <style>
    .home-card-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 16px;
        margin: 16px 0 24px;
    }

    .home-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 20px 18px;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease;
        /* 左侧浅颜色条：取当前卡片 class 设置的 --card-color-1，没有就用浅灰 */
        border-left: 4px solid var(--card-color-1, #9ca3af);
    }

    .home-card:hover {
        background: #f9fafb;
        border-color: #d1d5db;
    }

    .home-card-icon {
        font-size: 34px;
        line-height: 1;
        margin-bottom: 10px;
        display: inline-block;
    }

    .home-card-title {
        font-size: 17px;
        font-weight: 600;
        color: #111827;
        margin: 0 0 6px;
    }

    .home-card-desc {
        font-size: 13px;
        color: #4b5563;
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

    /* 兼容原有颜色 class：不再用发光/渐变，只给一个浅色左侧色条 */
    .card-blue   { --card-color-1: #3b82f6; --card-color-2: #3b82f6; }
    .card-green  { --card-color-1: #10b981; --card-color-2: #10b981; }
    .card-orange { --card-color-1: #f97316; --card-color-2: #f97316; }
    .card-purple { --card-color-1: #8b5cf6; --card-color-2: #8b5cf6; }
    .card-pink   { --card-color-1: #ec4899; --card-color-2: #ec4899; }
    .card-cyan   { --card-color-1: #0ea5e9; --card-color-2: #0ea5e9; }
    </style>
    """


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue") -> str:
    """
    渲染单个首页卡片的 HTML。

    注意：返回的 HTML 必须行首无缩进/无多余空行——调用方会把字符串塞进
    st.markdown(unsafe_allow_html=True)，Markdown 解析器对『行首 ≥4 空格』
    会当成缩进代码块渲染成 <pre><code>，导致卡片旁边多一个灰色代码块。
    """
    import html
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
