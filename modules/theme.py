"""
澄天小助手统一样式主题模块

提供整体UI美化方案，包括：
- 渐变色主题
- 卡片悬浮动画
- 按钮丝滑过渡
- 滚动动画
- 玻璃态效果
- 数据可视化样式
"""


def apply_theme():
    """应用全局主题样式"""
    st_markdown = _get_global_css()
    import streamlit as st
    st.markdown(st_markdown, unsafe_allow_html=True)


def render_home_cards():
    """渲染首页卡片的HTML（带动画）"""
    import streamlit as st
    st.markdown(_get_home_cards_css(), unsafe_allow_html=True)


def render_metric_cards():
    """渲染指标卡片的样式"""
    import streamlit as st
    st.markdown(_get_metric_css(), unsafe_allow_html=True)


def render_page_transition():
    """渲染页面切换过渡效果"""
    import streamlit as st
    st.markdown(_get_transition_css(), unsafe_allow_html=True)


def _get_global_css() -> str:
    """获取全局CSS样式"""
    return """
    <style>
    /* ===== 全局字体与背景 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft YaHei', '微软雅黑', sans-serif !important;
    }
    
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e8edf3 100%);
        background-attachment: fixed;
    }
    
    /* 隐藏默认Streamlit元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* ===== 滚动条美化 ===== */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    
    /* ===== 标题样式 ===== */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        animation: fadeInDown 0.8s ease;
    }
    
    h2, h3 {
        color: #2c3e50 !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }
    
    /* ===== 按钮美化 ===== */
    .stButton > button {
        border-radius: 12px !important;
        border: none !important;
        font-weight: 500 !important;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05) !important;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    
    .stButton > button:hover::before {
        width: 300px;
        height: 300px;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 12px 24px rgba(102, 126, 234, 0.25) !important;
    }
    
    .stButton > button:active {
        transform: translateY(-1px) !important;
    }
    
    /* Primary按钮渐变 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        background-size: 200% 200% !important;
        animation: gradientShift 3s ease infinite;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-position: right center !important;
    }
    
    /* ===== 输入框美化 ===== */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        border-radius: 10px !important;
        border: 2px solid #e8edf3 !important;
        transition: all 0.3s ease !important;
        background: white !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* ===== 表格美化 ===== */
    .stDataFrame, .stTable {
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
    }
    
    /* ===== 侧边栏美化 ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%) !important;
        border-right: 1px solid #e8edf3 !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        transition: all 0.3s ease;
    }
    
    /* ===== Tab样式 ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        padding: 8px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 10px 20px !important;
        transition: all 0.3s ease !important;
        font-weight: 500 !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    /* ===== 动画关键帧 ===== */
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
    }
    
    /* 元素入场动画 */
    .stMarkdown, .stDataFrame, .stPlotlyChart, .stMetric {
        animation: fadeInUp 0.6s ease;
    }
    
    /* ===== 暗色模式适配 ===== */
    @media (prefers-color-scheme: dark) {
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }
    }
    </style>
    """


def _get_home_cards_css() -> str:
    """获取首页卡片样式"""
    return """
    <style>
    /* ===== 首页模块卡片 ===== */
    .home-card-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 20px;
        margin: 20px 0;
    }
    
    .home-card {
        background: white;
        border-radius: 20px;
        padding: 28px 24px;
        cursor: pointer;
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
    
    .home-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--card-color-1, #667eea), var(--card-color-2, #764ba2));
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.5s ease;
    }
    
    .home-card:hover::before {
        transform: scaleX(1);
    }
    
    .home-card::after {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, var(--card-color-1, #667eea) 0%, transparent 70%);
        opacity: 0;
        transition: opacity 0.5s ease;
        pointer-events: none;
    }
    
    .home-card:hover::after {
        opacity: 0.05;
    }
    
    .home-card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 40px rgba(102, 126, 234, 0.2);
    }
    
    .home-card-icon {
        font-size: 48px;
        margin-bottom: 16px;
        display: inline-block;
        animation: float 3s ease-in-out infinite;
    }
    
    .home-card-title {
        font-size: 20px;
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 8px;
    }
    
    .home-card-desc {
        font-size: 13px;
        color: #7f8c8d;
        line-height: 1.6;
        margin-bottom: 16px;
    }
    
    .home-card-arrow {
        display: inline-block;
        color: #667eea;
        font-weight: 600;
        transition: transform 0.3s ease;
    }
    
    .home-card:hover .home-card-arrow {
        transform: translateX(8px);
    }
    
    /* 卡片渐变色变量 */
    .card-blue { --card-color-1: #667eea; --card-color-2: #764ba2; }
    .card-green { --card-color-1: #11998e; --card-color-2: #38ef7d; }
    .card-orange { --card-color-1: #f12711; --card-color-2: #f5af19; }
    .card-purple { --card-color-1: #8e2de2; --card-color-2: #4a00e0; }
    .card-pink { --card-color-1: #ee9ca7; --card-color-2: #ffdde1; }
    </style>
    """


def _get_metric_css() -> str:
    """获取指标卡片样式"""
    return """
    <style>
    /* ===== 指标卡片美化 ===== */
    [data-testid="stMetric"] {
        background: white;
        padding: 20px !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: 1px solid rgba(0, 0, 0, 0.02) !important;
        position: relative;
        overflow: hidden;
    }
    
    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        transform: scaleY(0);
        transform-origin: top;
        transition: transform 0.4s ease;
    }
    
    [data-testid="stMetric"]:hover::before {
        transform: scaleY(1);
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 12px 24px rgba(102, 126, 234, 0.12) !important;
    }
    
    [data-testid="stMetric"] label {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #7f8c8d !important;
        letter-spacing: 0.3px;
    }
    
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    </style>
    """


def _get_transition_css() -> str:
    """获取页面切换过渡效果"""
    return """
    <style>
    /* 页面切换动画 */
    .stApp > div > div > div {
        animation: pageEnter 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    @keyframes pageEnter {
        from {
            opacity: 0;
            transform: translateX(20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* 内容区块动画 */
    .stMarkdown, .stDataFrame, .stPlotlyChart {
        animation: contentSlideIn 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    @keyframes contentSlideIn {
        from {
            opacity: 0;
            transform: translateY(15px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* 加载动画 */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    </style>
    """


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue") -> str:
    """
    渲染单个首页卡片的HTML
    
    Args:
        icon: 图标emoji
        title: 卡片标题
        desc: 卡片描述
        color_class: 颜色类名
        
    Returns:
        HTML字符串
    """
    return f"""
    <div class="home-card {color_class}" onclick="this.querySelector('button').click()">
        <div class="home-card-icon">{icon}</div>
        <div class="home-card-title">{title}</div>
        <div class="home-card-desc">{desc}</div>
        <span class="home-card-arrow">点击进入 →</span>
    </div>
    """


def apply_all_styles():
    """一次性应用所有样式"""
    import streamlit as st
    css = _get_global_css() + _get_home_cards_css() + _get_metric_css() + _get_transition_css()
    st.markdown(css, unsafe_allow_html=True)
