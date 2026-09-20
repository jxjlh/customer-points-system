"""
首页模块卡片组件
"""
import streamlit as st
from modules.theme import render_home_cards


def show_home_cards(cards_config):
    """渲染首页卡片网格（3列布局，卡片式按钮）。"""
    render_home_cards()

    cols_per_row = 3
    total = len(cards_config)
    rows = (total + cols_per_row - 1) // cols_per_row

    for row_idx in range(rows):
        row_cards = cards_config[row_idx * cols_per_row:(row_idx + 1) * cols_per_row]
        cols = st.columns(len(row_cards), gap="medium")
        for i, card in enumerate(row_cards):
            with cols[i]:
                title = card['title']
                desc = card.get('desc', '')
                label = f"{card['icon']}  {title}\n{desc}" if desc else f"{card['icon']}  {title}"
                clicked = st.button(
                    label,
                    key=card["key"],
                    use_container_width=True,
                    help=card.get("help", f"点击进入{card['title']}"),
                )
                if clicked:
                    st.session_state["selected_main"] = card["session_value"]
                    if card.get("session_sub"):
                        st.session_state["selected_sub"] = card["session_sub"]
                    st.rerun()
