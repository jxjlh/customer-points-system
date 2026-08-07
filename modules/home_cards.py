"""
首页模块卡片组件

使用HTML+CSS渲染美观的卡片，替代Streamlit默认按钮
"""
import re
import streamlit as st
from modules.theme import render_home_card, render_home_cards


def _collapse_html(html: str) -> str:
    """
    把多行 HTML 压缩成单行、去除标签间多余空白。

    关键目的：避免 st.markdown(unsafe_allow_html=True) 里的 Markdown 解析器
    把『行首 4 空格』识别为缩进代码块，导致卡片 HTML 同时被渲染成
    灰色 <pre><code> 代码块（每张卡片旁边多一个代码块的 bug 根因）。

    压缩成一行后不存在"行首"，从根本上消除了被 Markdown 当作缩进代码块的可能。
    """
    # 1) 去掉所有换行
    s = html.replace("\r", "").replace("\n", "")
    # 2) 连续空白（空格/tab）替换成单个空格
    s = re.sub(r"[ \t]+", " ", s)
    # 3) 标签之间的空白可以直接删掉（HTML 标签间空白无意义），比如 ">   <" → "><"
    s = re.sub(r"> +<", "><", s)
    return s.strip()


def show_home_cards(cards_config):
    """
    渲染首页卡片网格

    实现约束：
      - 卡片 HTML 与隐藏的 st.button 必须在**同一个 Streamlit 主文档 DOM**里。
        不能用 streamlit.components.v1.html（它会把 HTML 塞到 iframe 里，
        卡片 onclick 找不到外层的 button，路由点击会完全失效）。
      - 必须通过 st.markdown(unsafe_allow_html=True) 渲染，
        但又要避免 Markdown 的『行首 4 空格 = 代码块』规则，
        因此最终传给 st.markdown 的卡片 HTML 必须是**一行紧凑形式**。
    """
    render_home_cards()

    # 拼接外层容器 + 每个卡片，最后统一用 _collapse_html 压成单行
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
    cards_html = _collapse_html("".join(parts))

    # 单行走 unsafe_allow_html：不会被 Markdown 识别为缩进代码块，
    # 同时卡片 onclick 能定位到下方同一文档里的 st.button
    st.markdown(cards_html, unsafe_allow_html=True)

    # 隐藏的按钮：卡片 div 会在点击时触发这里同名 title 的 button.click()，
    # 从而进入 Streamlit 原生 rerun 流程，实现页面跳转
    for card in cards_config:
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
