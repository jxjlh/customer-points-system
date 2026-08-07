"""
澄天小助手 - 科技风黑蓝色主题

配色方案（科技风）：
- 背景：深蓝渐变 #0a0e27 → #121629
- 主色：霓虹蓝 #00d4ff
- 强调色：青色 #00ffd5
- 文字：白色/浅灰
- 效果：发光边框、玻璃态、霓虹辉光
"""


def apply_theme():
    """应用全局主题样式"""
    import streamlit as st
    st.markdown(_get_global_css(), unsafe_allow_html=True)


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
    """获取全局CSS样式 - 科技风黑蓝色"""
    return """
    <style>
    /* ===== CSS变量 - 科技风配色 ===== */
    :root {
        --bg-primary: #0a0e27;
        --bg-secondary: #121629;
        --bg-card: #1a1f3a;
        --bg-card-hover: #222a50;
        --primary: #00d4ff;
        --primary-glow: rgba(0, 212, 255, 0.4);
        --primary-dark: #0099cc;
        --accent: #00ffd5;
        --accent-glow: rgba(0, 255, 213, 0.3);
        --text-primary: #ffffff;
        --text-secondary: #b8c1ec;
        --text-muted: #8892b0;
        --border: #2a3050;
        --border-glow: rgba(0, 212, 255, 0.3);
        --danger: #ff6b6b;
        --success: #51cf66;
        --warning: #fcc419;
    }

    /* ===== 全局字体与背景 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft YaHei', '微软雅黑', sans-serif !important;
        color: var(--text-primary);
    }
    
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%) !important;
        background-attachment: fixed;
    }

    /* 背景网格效果 */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
        background-size: 50px 50px;
        pointer-events: none;
        z-index: 0;
    }
    
    /* 隐藏默认Streamlit元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Streamlit容器背景透明 */
    [data-testid="stAppViewContainer"] > .main {
        background: transparent !important;
    }
    
    [data-testid="stHeader"] {
        background: rgba(10, 14, 39, 0.8) !important;
        backdrop-filter: blur(10px);
        border-bottom: 1px solid var(--border);
    }
    
    /* ===== 滚动条美化 ===== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, var(--primary) 0%, var(--accent) 100%);
        border-radius: 4px;
        transition: all 0.3s ease;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, var(--accent) 0%, var(--primary) 100%);
        box-shadow: 0 0 10px var(--primary-glow);
    }
    
    /* ===== 标题样式 - 霓虹发光 ===== */
    h1 {
        font-family: 'Orbitron', sans-serif !important;
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800 !important;
        letter-spacing: 1px;
        animation: neonPulse 2s ease-in-out infinite, fadeInDown 0.8s ease;
        text-shadow: 0 0 30px var(--primary-glow);
    }
    
    h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }

    h2 {
        border-left: 3px solid var(--primary);
        padding-left: 12px;
    }

    /* ===== 文本样式 ===== */
    p, span, label, div {
        color: var(--text-secondary);
    }

    .stMarkdown p {
        color: var(--text-secondary);
        line-height: 1.7;
    }
    
    /* ===== 登录表单样式 ===== */
    [data-testid="stForm"] {
        background: var(--bg-card) !important;
        padding: 32px !important;
        border-radius: 20px !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 0 40px rgba(0, 212, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05) !important;
        backdrop-filter: blur(10px);
    }
    
    [data-testid="stForm"] label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }

    /* ===== 按钮美化 - 科技风 ===== */
    .stButton > button {
        border-radius: 10px !important;
        border: 1px solid var(--primary) !important;
        background: transparent !important;
        color: var(--primary) !important;
        font-weight: 600 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        transition: all 0.3s ease !important;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.2), transparent);
        transition: left 0.5s ease;
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    .stButton > button:hover {
        background: rgba(0, 212, 255, 0.1) !important;
        box-shadow: 0 0 20px var(--primary-glow), 0 0 40px rgba(0, 212, 255, 0.15) !important;
        transform: translateY(-2px);
        color: var(--primary) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Primary按钮 - 实心霓虹 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%) !important;
        color: var(--bg-primary) !important;
        border: none !important;
        font-weight: 700 !important;
        box-shadow: 0 0 20px var(--primary-glow);
        animation: buttonGlow 2s ease-in-out infinite;
    }
    
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 30px var(--primary-glow), 0 0 60px rgba(0, 255, 213, 0.3) !important;
        transform: translateY(-2px) scale(1.02);
    }

    /* ===== 输入框美化 ===== */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
        transition: all 0.3s ease !important;
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    .stTextInput label,
    .stNumberInput label,
    .stTextArea label,
    .stSelectbox label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }

    /* 输入框容器样式 */
    .stTextInput > div,
    .stNumberInput > div,
    .stTextArea > div,
    .stSelectbox > div {
        color: var(--text-primary) !important;
    }

    /* 登录表单输入框特殊处理 */
    [data-testid="stForm"] .stTextInput label,
    [data-testid="stForm"] .stTextInput p,
    [data-testid="stForm"] label {
        color: var(--text-primary) !important;
    }

    .stTextInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: var(--text-muted) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px var(--primary-glow), 0 0 20px rgba(0, 212, 255, 0.1) !important;
    }

    /* Selectbox深色模式 */
    [data-baseweb="select"] > div {
        background-color: var(--bg-secondary) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
    }

    [data-baseweb="select"] [data-baseweb="tag"] {
        background: var(--primary) !important;
        color: var(--bg-primary) !important;
        border: none !important;
    }
    
    /* ===== 表格美化 ===== */
    .stDataFrame, .stTable {
        border-radius: 12px !important;
        overflow: hidden;
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
    }

    /* DataFrame深色模式 */
    [data-testid="stDataFrame"] {
        background: var(--bg-card) !important;
    }

    /* 表格表头 */
    thead th {
        background: var(--bg-secondary) !important;
        color: var(--primary) !important;
        font-weight: 600 !important;
        border-bottom: 2px solid var(--primary) !important;
    }

    /* 表格单元格 */
    tbody td {
        color: var(--text-secondary) !important;
        border-bottom: 1px solid var(--border) !important;
    }

    tbody tr:hover {
        background: rgba(0, 212, 255, 0.05) !important;
    }

    /* AgGrid深色模式 */
    .ag-theme-alpine {
        --ag-header-background-color: var(--bg-secondary) !important;
        --ag-odd-row-background-color: var(--bg-card) !important;
        --ag-row-hover-color: rgba(0, 212, 255, 0.1) !important;
        --ag-column-hover-color: rgba(0, 212, 255, 0.05) !important;
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
    }

    .ag-theme-alpine .ag-header-cell {
        color: var(--primary) !important;
        border-color: var(--border) !important;
    }

    .ag-theme-alpine .ag-cell {
        color: var(--text-secondary) !important;
        border-color: var(--border) !important;
    }

    /* ===== 侧边栏美化 ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%) !important;
        border-right: 1px solid var(--border) !important;
    }

    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 2rem;
    }
    
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        transition: all 0.3s ease;
        background: transparent !important;
        border: 1px solid transparent !important;
        color: var(--text-secondary) !important;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(0, 212, 255, 0.1) !important;
        border-color: var(--primary) !important;
        color: var(--primary) !important;
        box-shadow: 0 0 15px var(--primary-glow) !important;
    }

    /* Sidebar用户信息 */
    section[data-testid="stSidebar"] .stMarkdown p {
        color: var(--text-secondary);
    }
    
    /* ===== Tab样式 - 科技风 ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--bg-secondary);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 10px 20px !important;
        transition: all 0.3s ease !important;
        font-weight: 500 !important;
        color: var(--text-muted) !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%) !important;
    }
    
    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span,
    .stTabs [aria-selected="true"] div {
        color: var(--bg-primary) !important;
        font-weight: 600 !important;
    }

    .stTabs [aria-selected="false"] p,
    .stTabs [aria-selected="false"] span {
        color: var(--text-muted) !important;
    }
    
    .stTabs [aria-selected="false"]:hover p,
    .stTabs [aria-selected="false"]:hover span {
        color: var(--primary) !important;
    }
    
    /* ===== 分隔线 ===== */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border-glow), transparent);
        margin: 2rem 0;
    }

    /* stMarkdown分隔线 */
    .stMarkdown hr {
        background: linear-gradient(90deg, transparent, var(--primary), transparent);
        height: 1px;
        border: none;
    }

    /* ===== 信息框美化 ===== */
    [data-testid="stAlertContainer"] > div {
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        background: var(--bg-card) !important;
    }

    /* Success */
    [data-testid="stAlertContainer"] [data-testid="stMarkdown"] {
        background: var(--bg-card) !important;
    }
    
    /* ===== 动画关键帧 ===== */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes neonPulse {
        0%, 100% { 
            filter: drop-shadow(0 0 10px var(--primary-glow));
        }
        50% { 
            filter: drop-shadow(0 0 20px var(--primary-glow)) drop-shadow(0 0 30px rgba(0, 255, 213, 0.3));
        }
    }

    @keyframes buttonGlow {
        0%, 100% { 
            box-shadow: 0 0 20px var(--primary-glow);
        }
        50% { 
            box-shadow: 0 0 30px var(--primary-glow), 0 0 50px rgba(0, 255, 213, 0.2);
        }
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
    }

    @keyframes scanLine {
        0% { transform: translateY(-100%); }
        100% { transform: translateY(100vh); }
    }
    
    /* 元素入场动画 */
    .stMarkdown, .stDataFrame, .stPlotlyChart, .stMetric {
        animation: fadeInUp 0.6s ease;
    }

    /* ===== Plotly图表深色模式 ===== */
    .js-plotly-plot .plotly .modebar {
        background: transparent !important;
    }

    /* Plotly图表容器 */
    .js-plotly-plot {
        background: var(--bg-card) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        padding: 12px !important;
    }
    
    /* ===== 加载动画 ===== */
    .stSpinner > div {
        border-top-color: var(--primary) !important;
        border-right-color: var(--accent) !important;
    }

    /* ===== 复选框和单选 ===== */
    [data-testid="stCheckbox"] label,
    [data-testid="stRadio"] label {
        color: var(--text-secondary) !important;
    }

    /* ===== 滑块 ===== */
    [data-testid="stSlider"] [role="slider"] {
        background: var(--primary) !important;
    }

    /* ===== 进度条 ===== */
    [data-testid="stProgress"] > div > div,
    [data-testid="stProgress"] [role="progressbar"] > div {
        background: linear-gradient(90deg, var(--primary), var(--accent)) !important;
    }

    /* ===== Expander ===== */
    [data-testid="stExpander"] {
        border-color: var(--border) !important;
        background: var(--bg-card) !important;
        border-radius: 12px !important;
    }

    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }

    /* ===== 文件上传 ===== */
    [data-testid="stFileUploader"] {
        border-color: var(--border) !important;
        background: var(--bg-secondary) !important;
    }

    [data-testid="stFileUploader"] section {
        background: transparent !important;
    }

    /* ===== 登录容器 ===== */
    .login-container {
        max-width: 500px;
        margin: 0 auto;
        padding: 40px 20px;
        position: relative;
        z-index: 1;
    }

    /* Logo发光效果 */
    .login-container img {
        filter: drop-shadow(0 0 20px var(--primary-glow));
    }
    
    /* ===== 移动端适配 ===== */
    @media (max-width: 768px) {
        .login-container {
            padding: 20px 10px;
        }
        h1 {
            font-size: 24px !important;
        }
    }
    </style>
    """


def _get_home_cards_css() -> str:
    """获取首页卡片样式 - 科技风"""
    return """
    <style>
    /* ===== 首页模块卡片 - 科技风 ===== */
    .home-card-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 20px;
        margin: 20px 0;
    }
    
    .home-card {
        background: var(--bg-card) !important;
        border-radius: 16px !important;
        padding: 28px 24px !important;
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
        position: relative;
        overflow: hidden;
        border: 1px solid var(--border) !important;
        backdrop-filter: blur(10px);
    }

    /* 卡片顶部发光线 */
    .home-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--card-color-1, #00d4ff), var(--card-color-2, #00ffd5));
        transform: scaleX(0);
        transform-origin: center;
        transition: transform 0.5s ease;
    }
    
    .home-card:hover::before {
        transform: scaleX(1);
    }

    /* 卡片悬停发光效果 */
    .home-card::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, var(--card-color-1, #00d4ff) 0%, transparent 60%);
        opacity: 0;
        transition: opacity 0.5s ease;
        pointer-events: none;
    }
    
    .home-card:hover::after {
        opacity: 0.08;
    }
    
    .home-card:hover {
        transform: translateY(-8px);
        border-color: var(--primary) !important;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 30px var(--primary-glow) !important;
    }
    
    .home-card-icon {
        font-size: 48px;
        margin-bottom: 16px;
        display: inline-block;
        animation: float 3s ease-in-out infinite;
        filter: drop-shadow(0 0 10px var(--card-color-1, #00d4ff));
    }
    
    .home-card-title {
        font-size: 20px;
        font-weight: 700;
        color: var(--text-primary) !important;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }
    
    .home-card-desc {
        font-size: 13px;
        color: var(--text-muted) !important;
        line-height: 1.6;
        margin-bottom: 16px;
    }
    
    .home-card-arrow {
        display: inline-block;
        color: var(--primary) !important;
        font-weight: 600;
        transition: transform 0.3s ease;
        letter-spacing: 1px;
    }
    
    .home-card:hover .home-card-arrow {
        transform: translateX(8px);
    }
    
    /* 卡片渐变色变量 - 科技蓝系 */
    .card-blue { --card-color-1: #00d4ff; --card-color-2: #0099cc; }
    .card-green { --card-color-1: #00ffd5; --card-color-2: #00b3a0; }
    .card-orange { --card-color-1: #ff6b6b; --card-color-2: #ee5a5a; }
    .card-purple { --card-color-1: #a855f7; --card-color-2: #7c3aed; }
    .card-pink { --card-color-1: #ec4899; --card-color-2: #db2777; }
    </style>
    """


def _get_metric_css() -> str:
    """获取指标卡片样式 - 科技风"""
    return """
    <style>
    /* ===== 指标卡片美化 - 科技风 ===== */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        padding: 24px !important;
        border-radius: 16px !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(10px);
    }
    
    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 3px;
        height: 100%;
        background: linear-gradient(180deg, var(--primary) 0%, var(--accent) 100%);
        box-shadow: 0 0 10px var(--primary-glow);
    }
    
    [data-testid="stMetric"]::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 3px;
        height: 100%;
        background: linear-gradient(180deg, var(--accent) 0%, var(--primary) 100%);
        box-shadow: 0 0 10px var(--primary-glow);
        opacity: 0.5;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        border-color: var(--primary) !important;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4), 0 0 20px var(--primary-glow) !important;
    }
    
    [data-testid="stMetric"] label {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--text-muted) !important;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 32px !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
    }

    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: var(--success) !important;
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
        border-top-color: var(--primary) !important;
        border-right-color: var(--accent) !important;
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
