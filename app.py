import streamlit as st
import os
import sys
import pandas as pd
from datetime import datetime
from io import BytesIO
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

def validate_columns(df):
    required_columns = [
        "Job No",
        "Individual PO Number",
        "JAX销售",
        "单位名称",
        "品系号",
        "年龄",
        "性别",
        "数量",
        "发运笼数",
        "隔离后预估笼数",
        "实际出运笼数",
        "提货时间",
        "承运方",
        "城市",
        "收货人",
        "送货地址",
        "拟收货时间",
        "收货备注"
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Excel文件缺少必要的列：{', '.join(missing_columns)}")


def format_date(date_value):
    if pd.isna(date_value):
        return ""
    
    if hasattr(date_value, 'month') and hasattr(date_value, 'day'):
        return f"{date_value.month}月{date_value.day}日"
    
    try:
        if isinstance(date_value, str):
            clean_str = date_value.split(' ')[0]
            if '-' in clean_str:
                parts = clean_str.split('-')
                if len(parts) == 3:
                    return f"{int(parts[1])}月{int(parts[2])}日"
            if '/' in clean_str:
                parts = clean_str.split('/')
                if len(parts) == 3 and len(parts[0]) == 4:
                    return f"{int(parts[1])}月{int(parts[2])}日"
                elif len(parts) >= 2:
                    return f"{int(parts[0])}月{int(parts[1])}日"
            date_obj = pd.to_datetime(date_value)
            return f"{date_obj.month}月{date_obj.day}日"
    except (ValueError, TypeError):
        pass
    
    return str(date_value)


def build_strain_list(group_df):
    strain_groups = group_df.groupby("品系号")
    
    strain_items = []
    for strain_id, strain_df in strain_groups:
        strain_parts = []
        
        for _, row in strain_df.iterrows():
            gender = str(row["性别"]).strip().upper()
            quantity = int(row["数量"]) if pd.notna(row["数量"]) else 0
            age = str(row["年龄"]).strip()
            
            gender_text = "雌" if gender in ("雌", "F", "FEMALE") else "雄"
            
            if age.isdigit():
                ship_age = int(age)
                arrive_min = ship_age + 3
                arrive_max = ship_age + 4
                age_text = f"{ship_age}周（到货周龄约{arrive_min}-{arrive_max}周）"
            else:
                age_text = f"{age}周"
            
            strain_parts.append(f"{quantity}{gender_text}-发货周龄{age_text}")
        
        strain_items.append(f"https://www.jax.org/strain/{strain_id}：{'、'.join(strain_parts)}")
    
    return "、".join(strain_items)


def render_mail(receiver, strain_list, ship_date, receive_date):
    mail_body = f"""让您久等了。

您的小鼠{strain_list}，预计于{ship_date}从美国发货，并将在{receive_date}左右的工作日送货。

随附小鼠的鼠房微生物检测报告及隔离场的微生物检测报告，烦请查收。

麻烦您确认小鼠发货周龄及送货时间能否接受？

感谢您的支持并期待您的回复，祝好！"""
    
    return mail_body


def process_excel(file_bytes):
    df = pd.read_excel(BytesIO(file_bytes), sheet_name='出隔离场', header=None)
    
    header_row_index = None
    for idx, row in df.iterrows():
        first_cell = str(row.iloc[0]).strip()
        if first_cell == "Job No":
            second_cell = str(row.iloc[1]).strip()
            if second_cell == "Individual PO Number":
                third_cell = str(row.iloc[2]).strip()
                if third_cell == "JAX销售":
                    header_row_index = idx
                    break
    
    if header_row_index is None:
        raise ValueError("未找到表头行，请确保Excel文件包含正确的表头")
    
    new_header = df.iloc[header_row_index].tolist()
    df = df.iloc[header_row_index + 2:]
    df.columns = new_header
    
    df = df.dropna(how='all')
    
    df = df[~df["Job No"].astype(str).str.contains("Job No|Quantity", na=False)]
    
    validate_columns(df)
    
    po_order = df["Individual PO Number"].dropna().unique().tolist()
    
    result_rows = []
    
    for po_number, group_data in df.groupby("Individual PO Number"):
        first_row = group_data.iloc[0]
        strain_list = build_strain_list(group_data)
        
        receiver = str(first_row["收货人"]).strip() if pd.notna(first_row["收货人"]) else "老师"
        ship_date = format_date(first_row["提货时间"])
        receive_date = format_date(first_row["拟收货时间"])
        
        mail_body = render_mail(receiver, strain_list, ship_date, receive_date)
        
        full_content = f"JAX小鼠发货通知\n\n{mail_body}"
        result_rows.append({
            "Individual PO Number": po_number,
            "单位名称": first_row["单位名称"],
            "收货人": first_row["收货人"],
            "邮件内容": full_content
        })
    
    result_df = pd.DataFrame(result_rows)
    
    result_df['po_order'] = result_df['Individual PO Number'].map(lambda x: po_order.index(x) if x in po_order else len(po_order))
    result_df = result_df.sort_values('po_order').drop('po_order', axis=1)
    
    return result_df


def show_email_generator():
    st.title("📧 JAX小鼠发货通知邮件生成器")
    
    st.markdown("""
    **使用说明：**
    1. 上传Excel文件（需包含【出隔离场】Sheet）
    2. 系统自动解析数据并生成邮件内容
    3. 下载生成的邮件结果Excel文件
    """)
    
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                result_df = process_excel(uploaded_file.getvalue())
                
                st.success("邮件生成完成！")
                
                st.subheader("生成的邮件列表")
                st.dataframe(result_df, width="stretch", height=400)
                
                excel_buffer = BytesIO()
                result_df.to_excel(excel_buffer, index=False, sheet_name="邮件生成结果")
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 下载邮件结果",
                    data=excel_buffer,
                    file_name=f"JAX邮件生成结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.subheader("邮件预览")
                for _, row in result_df.iterrows():
                    with st.expander(f"📧 {row['Individual PO Number']} - {row['单位名称']}"):
                        st.text(row['邮件内容'])
            
            except Exception as e:
                st.error(f"处理过程中发生错误：\n\n{str(e)}")


def show_about():
    st.title("关于澄天小助手")
    
    st.markdown("""
    **澄天小助手** 是北京澄天生物科技有限公司开发的内部办公辅助工具。
    
    **功能特性：**
    - 📧 JAX小鼠发货通知邮件自动生成
    - 📊 数据可视化分析
    - 🔐 用户身份认证
    - 💾 数据导出功能
    
    **技术支持：**
    - 邮箱：support@chengtian-bio.com
    - 电话：400-xxx-xxxx
    """)


def main():
    st.set_page_config(
        page_title="澄天小助手",
        page_icon="🐭",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    with open(CONFIG_PATH) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    if st.session_state.get('authentication_status') != True:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
            try:
                with open(logo_path, "rb") as f:
                    logo_bytes = f.read()
                st.image(logo_bytes, width=150)
            except Exception as e:
                pass
            st.title("澄天小助手")
            authenticator.login(location="main")
        
        if st.session_state.get('authentication_status') == False:
            st.error("用户名或密码错误")
            return
        
        if st.session_state.get('authentication_status') == None:
            return
    
    if st.session_state.get('authentication_status'):
        st.sidebar.title("澄天小助手")
        authenticator.logout("退出登录", "sidebar")
        st.sidebar.write(f"欢迎回来, **{st.session_state['name']}**")
        
        menu_options = [
            "📧 JAX邮件生成器",
            "ℹ️ 关于我们"
        ]
        
        selected_menu = st.sidebar.radio("功能菜单", menu_options)
        
        if selected_menu == "📧 JAX邮件生成器":
            show_email_generator()
        elif selected_menu == "ℹ️ 关于我们":
            show_about()


if __name__ == "__main__":
    main()
