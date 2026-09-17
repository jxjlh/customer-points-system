"""
首页模块卡片组件
"""
import streamlit as st
from modules.theme import render_home_cards


def show_home_cards(cards_config):
    """渲染首页卡片网格。"""
    render_home_cards()

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
                st.session_state["selected_main"] = card["session_value"]
                if card.get("session_sub"):
                    st.session_state["selected_sub"] = card["session_sub"]
                st.rerun()
