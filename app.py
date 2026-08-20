import os, sys, traceback, logging

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
_log = logging.getLogger("crayotter")

try:
    import streamlit as st
    st.set_page_config(page_title="澄天小助手", page_icon="🐭", layout="wide")
    st.title("🏠 澄天小助手")
    st.success("✅ 系统启动成功！")
    st.info("如果您看到此页面，说明基础 Streamlit 运行正常。请等待完整功能加载...")
    
    _log.info("基础页面加载成功")
    
    # 尝试加载完整功能
    try:
        import pandas as pd
        import plotly.express as px
        import yaml
        from yaml.loader import SafeLoader
        import streamlit_authenticator as stauth
        import bcrypt
        
        _log.info("基础依赖OK")
        
        _APP_DIR = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, _APP_DIR)
        
        from modules.excel_reader import ExcelReader
        from modules.customer_analysis import CustomerAnalysis
        from modules.point_calculation import PointCalculation
        from modules.database import DatabaseManager
        from modules.invoice_fetcher import InvoiceFetcher
        from modules.quotation_ui import show_quotation
        from modules.db_manager import get_db_manager
        from logo_base64 import get_logo_html, get_avatar_html
        
        _log.info("所有模块加载成功")
        
        st.success("✅ 所有模块加载成功！")
        st.balloons()
        
    except Exception as inner_e:
        _log.error(f"功能加载失败: {inner_e}")
        _log.error(traceback.format_exc())
        st.error(f"功能加载失败: {type(inner_e).__name__}: {inner_e}")
        st.code(traceback.format_exc(), language="python")
        
except Exception as e:
    _log.error(f"启动失败: {e}")
    _log.error(traceback.format_exc())
    try:
        import streamlit as st
        st.error(f"❌ 启动失败: {e}")
        st.code(traceback.format_exc())
    except:
        print(f"FATAL: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
