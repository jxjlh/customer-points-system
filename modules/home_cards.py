"""
首页模块卡片组件

- 使用 st.button 直接渲染卡片（图标+标题）
- 点击按钮触发 Emoji Burst 动画 + 导航
"""
import streamlit as st
import time
from modules.theme import render_home_cards, trigger_emoji_burst


def show_home_cards(cards_config):
    """渲染首页卡片网格。"""
    render_home_cards()

    clicked_key = st.session_state.pop("_home_card_clicked", None)
    if clicked_key:
        for card in cards_config:
            if card["key"] == clicked_key:
                # 先触发 Emoji Burst 动画
                emojis = card.get("emojis", "🎉,✨,😄,🔥,💥,⭐,💖,🤩,👍,🥳")
                trigger_emoji_burst(emojis)
                # 设置延迟导航
                st.session_state["_pending_navigation"] = {
                    "session_value": card["session_value"],
                    "session_sub": card.get("session_sub"),
                }
                break

    # 如果有待执行的导航，先显示动画再跳转
    pending_nav = st.session_state.get("_pending_navigation")
    if pending_nav:
        # 检查是否需要等待动画播放
        if not st.session_state.get("_animation_started"):
            st.session_state["_animation_started"] = True
            st.rerun()
        else:
            # 动画已开始，执行导航
            st.session_state["selected_main"] = pending_nav["session_value"]
            if pending_nav.get("session_sub"):
                st.session_state["selected_sub"] = pending_nav["session_sub"]
            st.session_state.pop("_pending_navigation", None)
            st.session_state.pop("_animation_started", None)
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
