"""
首页模块卡片组件（极简）

- 用原生 streamlit.button 渲染按钮并触发路由
- 按钮外额外渲染一组自定义 HTML 卡片（视觉用），点击卡片时调用同名按钮的 .click() 触发 rerun
- 卡片本体下方由 st.button 渲染的 button 通过 .hidden-home-card-button button { display:none } 隐藏，
  从而实现「卡片视觉 + 原生 button 路由行为」的解耦
"""
import textwrap
import streamlit as st
from modules.theme import render_home_card, render_home_cards


def show_home_cards(cards_config):
    """
    渲染首页卡片网格。

    实现要点：
    1. render_home_cards() 先注入 home-card-container / home-card 的 grid 样式
    2. 用 st.markdown 渲染一套视觉 HTML 卡片（home-card），每个卡片的 onclick
       会触发『同名 title 』按钮的 click()，从而把视觉交互与 Streamlit 的 rerun
       机制连通（st.button 需要用户点击 button 才会进入回调，我们用自定义卡片的
       onclick 代理这一步）
    3. 为了让卡片下方不露出一串原始 Streamlit 按钮，给每个 button 外层容器加
       .hidden-home-card-button（由 theme.py 的全局 CSS display:none 掉）
    """
    render_home_cards()

    parts = ['<div class="home-card-container">']
    for card in cards_config:
        parts.append(
            render_home_card(
                icon=card["icon"],
                title=card["title"],
                desc=card["desc"],
                color_class=card.get("color_class", "card-blue"),
            )
        )
    parts.append("</div>")
    cards_html = textwrap.dedent("".join(parts))

    st.markdown(cards_html, unsafe_allow_html=True)

    # 实际触发路由的 button：隐藏在 DOM 里（theme.css 给 .hidden-home-card-button 做 display:none）
    for card in cards_config:
        with st.container():
            st.markdown('<div class="hidden-home-card-button">', unsafe_allow_html=True)
            if st.button(
                card["title"],
                key=card["key"],
                help=card.get("help", ""),
                use_container_width=True,
                type="primary",
            ):
                st.session_state["selected_main"] = card["session_value"]
                if "session_sub" in card:
                    st.session_state["selected_sub"] = card["session_sub"]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
