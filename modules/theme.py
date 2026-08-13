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
    """首页卡片 CSS + Emoji Burst 点击特效"""
    import streamlit as st
    import streamlit.components.v1 as components
    st.markdown(_get_home_cards_css(), unsafe_allow_html=True)
    
    # 检查是否需要触发 Emoji Burst
    burst_triggered = st.session_state.get("_emoji_burst_triggered")
    if burst_triggered:
        # 显示 Emoji Burst 动画
        html_content = _get_emoji_burst_animation(burst_triggered)
        # 使用 st.markdown 渲染一个覆盖层
        st.markdown(f"""
        <div style="position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:999999;pointer-events:none;overflow:hidden;">
            {html_content}
        </div>
        """, unsafe_allow_html=True)
        # 清除触发标记
        st.session_state.pop("_emoji_burst_triggered", None)


def trigger_emoji_burst(emojis: str = "🎉,✨,😄,🔥,💥,⭐,💖,🤩,👍,🥳"):
    """设置 session state 以触发 Emoji Burst 动画"""
    import streamlit as st
    st.session_state["_emoji_burst_triggered"] = emojis


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
    首页模块卡片 CSS - 直接美化 st.button 为卡片样式。
    """
    return """
    <style>
    /* 首页卡片按钮样式 */
    div[data-testid="stButton"] {
        margin-top: 0 !important;
        margin-bottom: 8px !important;
    }

    div[data-testid="stButton"] button,
    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {
        background: #ffffff !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 10px !important;
        padding: 20px 16px !important;
        min-height: 100px !important;
        height: auto !important;
        cursor: pointer !important;
        width: 100% !important;
        color: #374151 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        line-height: 1.4 !important;
        transition: all 0.2s ease !important;
        border-left: 4px solid #3b82f6 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
        text-align: center !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
    }

    div[data-testid="stButton"] button:hover,
    div[data-testid="stButton"] button:focus {
        background: #f0f4ff !important;
        border-color: #3b82f6 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }

    /* 按钮文字和图标 */
    div[data-testid="stButton"] p {
        margin: 0 !important;
        padding: 0 !important;
        font-size: 14px !important;
        color: #374151 !important;
        line-height: 1.4 !important;
        text-align: center !important;
    }

    /* 不同卡片颜色 - 通过 nth-child 模拟 */
    div[data-testid="stButton"]:nth-child(6n+1) button { border-left-color: #3b82f6 !important; }
    div[data-testid="stButton"]:nth-child(6n+2) button { border-left-color: #10b981 !important; }
    div[data-testid="stButton"]:nth-child(6n+3) button { border-left-color: #f97316 !important; }
    div[data-testid="stButton"]:nth-child(6n+4) button { border-left-color: #8b5cf6 !important; }
    div[data-testid="stButton"]:nth-child(6n+5) button { border-left-color: #0ea5e9 !important; }
    div[data-testid="stButton"]:nth-child(6n+6) button { border-left-color: #ec4899 !important; }

    /* Tooltip 隐藏 */
    div[data-testid="stTooltipIcon"] {
        display: none !important;
    }
    </style>
    """


def _get_emoji_burst_animation(emojis_str: str) -> str:
    """生成 Emoji Burst 动画 HTML（使用 CSS 动画）"""
    import math
    emojis_list = [e.strip() for e in emojis_str.split(",") if e.strip()]
    
    emojis_html = []
    for i in range(25):
        emoji = emojis_list[i % len(emojis_list)]
        angle = (360 * i) / 25
        distance = 100 + (i % 5) * 30
        x = int(distance * math.cos(math.radians(angle)))
        y = int(distance * math.sin(math.radians(angle)))
        size = 20 + (i % 4) * 5
        rot = (i * 30) % 360
        
        emojis_html.append(
            f'<div class="emoji-burst-item" style="--tx:{x}px;--ty:{y}px;--rot:{rot}deg;font-size:{size}px;">{emoji}</div>'
        )
    
    return f"""
    <style>
        .emoji-burst-item {{
            position: absolute;
            left: 50%;
            top: 50%;
            pointer-events: none;
            animation: emojiBurst 1.2s ease-out forwards;
        }}
        @keyframes emojiBurst {{
            0% {{
                transform: translate(-50%, -50%) scale(0.3);
                opacity: 1;
            }}
            100% {{
                transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(1.2) rotate(var(--rot));
                opacity: 0;
            }}
        }}
    </style>
    {''.join(emojis_html)}
    """


def _get_emoji_burst_js() -> str:
    """注入 Emoji Burst 点击特效 JavaScript - 在 iframe 中运行但作用于父页面"""
    return """
    <script>
    (function() {
        const emojis = ['🎉','✨','😄','🔥','💥','⭐','💖','🤩','👍','🥳','🎊','😎','🚀','💫','🌟','💎','📊','📧','🧾','📋','🎬','📦','👑'];
        
        // 获取父窗口（Streamlit 主页面）
        const targetWindow = window.parent || window;
        const targetDocument = targetWindow.document;
        
        function createEmojiBurst(x, y) {
            const burstCount = 15 + Math.floor(Math.random() * 10);
            const container = targetDocument.createElement('div');
            container.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;pointer-events:none;z-index:2147483647;';
            targetDocument.body.appendChild(container);
            
            for (let i = 0; i < burstCount; i++) {
                const emoji = targetDocument.createElement('div');
                emoji.textContent = emojis[Math.floor(Math.random() * emojis.length)];
                const angle = (Math.PI * 2 * i) / burstCount + Math.random() * 0.5;
                const power = 80 + Math.random() * 100;
                const vx = Math.cos(angle) * power;
                const vy = Math.sin(angle) * power - 50;
                
                const size = 20 + Math.random() * 16;
                emoji.style.cssText = 'position:absolute;font-size:' + size + 'px;left:' + x + 'px;top:' + y + 'px;pointer-events:none;will-change:transform,opacity;transition:transform 1s ease-out,opacity 1s ease-out;';
                
                container.appendChild(emoji);
                
                requestAnimationFrame(function() {
                    emoji.style.transform = 'translate(' + vx + 'px,' + (vy + 150) + 'px) rotate(' + (Math.random() * 720 - 360) + 'deg)';
                    emoji.style.opacity = '0';
                });
                
                setTimeout(function() {
                    emoji.remove();
                }, 1100);
            }
            
            setTimeout(function() {
                container.remove();
            }, 1200);
        }
        
        function initBurst() {
            const buttons = targetDocument.querySelectorAll('div[data-testid="stButton"] button');
            buttons.forEach(function(btn) {
                if (btn.dataset.burstInitialized) return;
                btn.dataset.burstInitialized = 'true';
                btn.addEventListener('click', function(e) {
                    const rect = btn.getBoundingClientRect();
                    const x = rect.left + rect.width / 2;
                    const y = rect.top + rect.height / 2;
                    createEmojiBurst(x, y);
                });
            });
        }
        
        // 立即初始化 + 定时检测新按钮
        setTimeout(initBurst, 100);
        setInterval(initBurst, 500);
        
        // 监听 DOM 变化
        if (targetDocument.body) {
            const observer = new MutationObserver(function() {
                initBurst();
            });
            observer.observe(targetDocument.body, { childList: true, subtree: true });
        }
    })();
    </script>
    """


def render_home_card(icon: str, title: str, desc: str, color_class: str = "card-blue", card_key: str = "") -> str:
    """
    渲染单个首页卡片的 HTML（图标+标题）。
    """
    import html
    icon_safe = html.escape(str(icon))
    title_safe = html.escape(str(title))
    color_safe = html.escape(str(color_class), quote=True)
    key_safe = html.escape(str(card_key), quote=True)
    return textwrap.dedent(
        f"""
        <div class="home-card {color_safe}" data-key="{key_safe}">
          <div class="home-card-icon">{icon_safe}</div>
          <div class="home-card-title">{title_safe}</div>
        </div>
        """
    ).strip() + "\n"
