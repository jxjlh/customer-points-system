"""
首页模块卡片组件

- 卡片用 HTML 渲染（纯图标）
- st.button 透明覆盖在卡片上处理点击导航
"""
import textwrap
import streamlit as st
from modules.theme import render_home_card, render_home_cards


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
            card_html = render_home_card(
                icon=card["icon"],
                title=card["title"],
                desc=card["desc"],
                color_class=card.get("color_class", "card-blue"),
                card_key=card["key"],
            )
            st.markdown(card_html, unsafe_allow_html=True)

            if st.button(
                card["title"],
                key=card["key"],
                use_container_width=True,
                help=f"点击进入{card['title']}",
            ):
                st.session_state["_home_card_clicked"] = card["key"]
                st.rerun()
