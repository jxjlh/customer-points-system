"""
首页模块卡片组件

使用HTML+CSS渲染美观的卡片，替代Streamlit默认按钮
"""
import streamlit as st
from modules.theme import render_home_card, render_home_cards


def show_home_cards(cards_config):
    """
    渲染首页卡片网格
    
    Args:
        cards_config: 卡片配置列表
            [
                {
                    "icon": "📊",
                    "title": "客户积分智能分析",
                    "desc": "数据概览 · 客户管理 · 积分管理",
                    "color_class": "card-blue",
                    "key": "btn-customer",
                    "session_value": "📊 客户积分智能分析",
                    "session_sub": "📈 数据概览"
                },
                ...
            ]
    """
    render_home_cards()
    
    # 创建卡片HTML
    cards_html = '<div class="home-card-container">'
    for card in cards_config:
        cards_html += render_home_card(
            icon=card["icon"],
            title=card["title"],
            desc=card["desc"],
            color_class=card.get("color_class", "card-blue")
        )
    cards_html += '</div>'
    
    st.markdown(cards_html, unsafe_allow_html=True)
    
    # 隐藏的按钮用于触发点击事件
    for card in cards_config:
        if st.button(card["title"], key=card["key"], 
                     help=card.get("help", ""), 
                     use_container_width=True,
                     type="primary"):
            st.session_state['selected_main'] = card["session_value"]
            if "session_sub" in card:
                st.session_state['selected_sub'] = card["session_sub"]
            st.rerun()
