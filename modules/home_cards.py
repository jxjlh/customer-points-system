"""
首页模块卡片组件

- 使用 st.button 直接渲染卡片（图标+标题）
- 点击按钮触发导航
"""
import streamlit as st
from modules.theme import render_home_cards


def show_home_cards(cards_config):
    """渲染首页卡片网格。"""
    render_home_cards()

    clicked_key = st.session_state.pop("_home_card_clicked", None)
    if clicked_key:
        for card in cards_config:
            if card["key"] == clicked_key:
                st.session_state["selected_main"] = card["session_value"]
                if "session_sub" in card:
                    st.session_state["selected_sub"] = card["session_sub"]
                st.rerun()

    cols = st.columns(len(cards_config))
    for i, card in enumerate(cards_config):
        with cols[i]:
            label = f"{card['icon']}  {card['title']}"
            if st.button(
                label,
                key=card["key"],
                use_container_width=True,
                help=f"点击进入{card['title']}",
            ):
                st.session_state["_home_card_clicked"] = card["key"]
                st.rerun()
