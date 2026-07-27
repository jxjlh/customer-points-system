import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from typing import Dict, List


def show_quotation():
    st.title("📋 报价助手")

    if 'price_service' not in st.session_state:
        st.warning("价格库尚未加载，请先上传价格文件")
        
        price_file = st.file_uploader("选择JAX价格库Excel文件", type=["xlsx", "xls"])
        if price_file is not None:
            from modules.price_service import PriceService
            price_service = PriceService()
            try:
                price_service.load_price_data(file_bytes=price_file.getvalue())
                st.session_state['price_service'] = price_service
                st.success("价格库加载成功！")
                st.rerun()
            except Exception as e:
                st.error(f"价格库加载失败: {str(e)}")
        return

    if 'quotation_service' not in st.session_state:
        from modules.quotation_service import QuotationService
        st.session_state['quotation_service'] = QuotationService()

    price_service = st.session_state['price_service']
    quotation_service = st.session_state['quotation_service']

    st.markdown("""
    **使用说明：**
    1. 填写客户信息
    2. 添加小鼠品系
    3. 系统自动查询价格并计算金额
    4. 生成报价单Excel
    """)

    st.header("👥 客户信息")
    col1, col2, col3, col4 = st.columns(4)
    
    customer_name = col1.text_input("客户名称", value=quotation_service.get_customer_info().get("customer_name", ""))
    contact_person = col2.text_input("联系人", value=quotation_service.get_customer_info().get("contact_person", ""))
    sales_person = col3.text_input("销售", value=quotation_service.get_customer_info().get("sales_person", ""))
    
    customer_type_options = ["commercial", "npo", "ka"]
    customer_type_labels = {"commercial": "Commercial", "npo": "NPO", "ka": "KA"}
    selected_type = col4.selectbox("客户类型", customer_type_options, 
                                  format_func=lambda x: customer_type_labels[x],
                                  index=customer_type_options.index(quotation_service.get_customer_info().get("customer_type", "commercial")))
    
    quotation_service.set_customer_info(customer_name, contact_person, sales_person, selected_type)

    st.header("🐭 添加小鼠")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    strain = col1.text_input("品系号 (Strain)", key="strain_input", placeholder="例如: 000664")
    genotype = col2.text_input("基因型 (Genotype)", key="genotype_input", placeholder="例如: +/+")
    age = col3.text_input("周龄 (Age)", key="age_input", placeholder="例如: 6")
    sex = col4.selectbox("性别 (Sex)", ["M", "F"], key="sex_input")
    qty = col5.number_input("数量 (Qty)", min_value=1, max_value=1000, value=1, key="qty_input")

    if st.button("➕ 添加到报价单", type="primary", use_container_width=True):
        if not strain or not genotype or not age:
            st.error("请填写完整的品系信息（品系号、基因型、周龄）")
        else:
            price_result = price_service.query_price(strain, genotype, age, sex, selected_type)
            
            if price_result.get("found"):
                quotation_service.add_item(strain, genotype, age, sex, qty, price_result)
                st.success(f"已添加: {strain} x {qty}")
            else:
                st.error(price_result.get("error", "未找到对应价格"))

    st.header("📝 报价列表")
    items = quotation_service.get_items()
    
    if items:
        df_items = pd.DataFrame(items)
        df_items = df_items[["id", "strain", "name", "genotype", "age", "sex", "qty", "unit_price", "amount"]]
        df_items.columns = ["序号", "品系号", "品系名称", "基因型", "周龄", "性别", "数量", "单价", "金额"]
        
        gb = GridOptionsBuilder.from_dataframe(df_items)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False)
        gb.configure_column("序号", width=60)
        gb.configure_column("品系号", width=100)
        gb.configure_column("品系名称", width=200)
        gb.configure_column("基因型", width=150)
        gb.configure_column("周龄", width=60)
        gb.configure_column("性别", width=60)
        gb.configure_column("数量", width=80)
        gb.configure_column("单价", width=100)
        gb.configure_column("金额", width=120)
        
        grid_options = gb.build()
        
        AgGrid(df_items, gridOptions=grid_options, height=300,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)

        col_delete, col_clear = st.columns(2)
        delete_id = col_delete.number_input("删除序号", min_value=1, max_value=len(items), value=1)
        if col_delete.button("🗑️ 删除选中项"):
            quotation_service.delete_item(delete_id)
            st.rerun()
        
        if col_clear.button("🗑️ 清空报价单"):
            quotation_service.clear_all()
            st.rerun()
    else:
        st.info("暂无报价项，请添加小鼠")

    st.header("💰 金额汇总")
    summary = quotation_service.get_summary()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("明细")
        st.write(f"- 小计: ¥{summary['subtotal']:,.2f}")
        st.write(f"- 数量: {sum(item['qty'] for item in items)} 只")
    
    with col2:
        st.subheader("费用调整")
        shipping = st.number_input("运费", value=float(summary.get("shipping", 0)), step=100.0)
        service_fee = st.number_input("服务费", value=float(summary.get("service_fee", 0)), step=50.0)
        discount = st.number_input("折扣", value=float(summary.get("discount", 0)), step=100.0)
        tax = st.number_input("税费", value=float(summary.get("tax", 0)), step=50.0)
        
        quotation_service.set_summary_field("shipping", shipping)
        quotation_service.set_summary_field("service_fee", service_fee)
        quotation_service.set_summary_field("discount", discount)
        quotation_service.set_summary_field("tax", tax)
    
    with col3:
        st.subheader("总计")
        st.metric("Grand Total", f"¥{summary['grand_total']:,.2f}")
    
    st.header("📥 生成报价单")
    col_pdf, col_excel = st.columns(2)
    
    with col_pdf:
        if st.button("📄 生成报价单PDF", type="primary", use_container_width=True):
            if not items:
                st.error("请先添加报价项")
            elif not customer_name:
                st.error("请填写客户名称")
            else:
                try:
                    from modules.quotation_pdf_service import QuotationPDFService
                    
                    pdf_service = QuotationPDFService()
                    quotation_data = quotation_service.to_dict()
                    buffer = pdf_service.export_quotation(quotation_data)
                    
                    quote_number = quotation_data.get("quote_number", "")
                    file_name = f"{quote_number}.pdf" if quote_number else f"报价单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    st.download_button(
                        label="📥 下载PDF报价单",
                        data=buffer,
                        file_name=file_name,
                        mime="application/pdf",
                        key="download_pdf"
                    )
                    
                    st.success("PDF报价单生成成功！")
                except Exception as e:
                    st.error(f"生成PDF报价单失败: {str(e)}")
    
    with col_excel:
        if st.button("📊 生成报价单Excel", use_container_width=True):
            if not items:
                st.error("请先添加报价项")
            elif not customer_name:
                st.error("请填写客户名称")
            else:
                try:
                    from modules.quotation_export_service import QuotationExportService
                    
                    export_service = QuotationExportService()
                    template_path = st.session_state.get("template_path")
                    if template_path:
                        export_service.set_template_path(template_path)
                    
                    quotation_data = quotation_service.to_dict()
                    buffer = export_service.export_to_buffer(quotation_data)
                    
                    quote_number = quotation_data.get("quote_number", "")
                    file_name = f"{quote_number}.xlsx" if quote_number else f"报价单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    
                    st.download_button(
                        label="📥 下载Excel报价单",
                        data=buffer,
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_excel"
                    )
                    
                    st.success("Excel报价单生成成功！")
                except Exception as e:
                    st.error(f"生成Excel报价单失败: {str(e)}")

    st.header("🔍 价格查询")
    search_col1, search_col2, search_col3, search_col4 = st.columns(4)
    search_strain = search_col1.text_input("搜索品系号", key="search_strain")
    
    if search_strain:
        strain_info = price_service.get_strain_info(search_strain, selected_type)
        if strain_info:
            st.info(f"品系名称: {strain_info.get('strain_name', '')}")
            st.info(f"基因型: {strain_info.get('long_genotype', '')}")
            st.info(f"可用周龄: {', '.join(strain_info.get('available_ages', []))}")
            st.info(f"可用性别: {', '.join(strain_info.get('available_sexes', []))}")
        else:
            st.warning("未找到该品系")

from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode
from st_aggrid.grid_options_builder import GridOptionsBuilder