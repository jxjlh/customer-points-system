import json
import logging
from io import BytesIO

import pandas as pd
import streamlit as st

from modules.inventory.errors import InventoryError
from modules.inventory.field_values import normalize_options
from modules.inventory.presentation import filter_items, inventory_metrics, transaction_rows
from modules.inventory.repository import InventoryRepositoryAdapter
from modules.inventory.service import InventoryService


logger = logging.getLogger(__name__)


def show_inventory_page(db_manager, operator: str = "") -> None:
    service = InventoryService(InventoryRepositoryAdapter(db_manager))
    st.title("📦 库存管理")
    st.caption("库存物品、出入库记录和自定义字段统一管理")

    backend_name = getattr(db_manager, "_backend_name", "数据库")
    if backend_name:
        st.info(f"当前库存数据库：{backend_name}")
    fallback_note = getattr(db_manager, "_fallback_note", "")
    if fallback_note:
        st.warning(
            "远程数据库连接异常，当前使用本地 SQLite；部署重启后数据可能丢失。"
            f"错误原因：{fallback_note}"
        )

    tab_items, tab_transactions, tab_fields = st.tabs(
        ["📦 库存列表", "📋 出入库记录", "⚙️ 字段管理"]
    )

    with tab_items:
        _render_inventory_tab(service, operator)
    with tab_transactions:
        _render_transactions_tab(service)
    with tab_fields:
        _render_fields_tab(service)


def _render_inventory_tab(service: InventoryService, operator: str) -> None:
    history_options = _safe_call(
        service.history_options,
        {"title": [], "category": [], "location": []},
        "读取历史选项失败",
    )
    custom_fields = _safe_call(service.list_fields, [], "读取自定义字段失败")
    items = _safe_call(service.list_items, [], "读取库存失败")

    with st.expander("➕ 新增库存物品", expanded=not items):
        _render_item_form(
            service,
            history_options,
            custom_fields,
            operator,
            form_key="inventory_create",
        )

    filter_columns = st.columns([2, 1, 1, 1, 1])
    with filter_columns[0]:
        keyword = st.text_input(
            "🔍 搜索",
            key="inventory_filter_keyword",
            placeholder="编号、title、类别或位置",
        )
    categories = ["全部"] + normalize_options(item.get("category") for item in items)
    locations = ["全部"] + normalize_options(item.get("location") for item in items)
    with filter_columns[1]:
        category = st.selectbox("类别", categories, key="inventory_filter_category")
    with filter_columns[2]:
        location = st.selectbox("位置", locations, key="inventory_filter_location")
    with filter_columns[3]:
        status = st.selectbox(
            "状态",
            ["启用", "已归档", "全部"],
            key="inventory_filter_status",
        )
    with filter_columns[4]:
        low_stock_only = st.checkbox(
            "仅低库存",
            key="inventory_filter_low_stock",
            help="显示库存数量小于或等于5的物品",
        )

    filtered_items = filter_items(
        items,
        keyword=keyword,
        category=category,
        location=location,
        status=status,
        low_stock_only=low_stock_only,
    )
    metrics = inventory_metrics(filtered_items)
    metric_columns = st.columns(4)
    metric_columns[0].metric("物品种类", metrics["item_count"])
    metric_columns[1].metric("库存总量", metrics["total_quantity"])
    metric_columns[2].metric("低库存", metrics["low_stock"])
    metric_columns[3].metric("零库存", metrics["zero_stock"])

    _render_inventory_exports(filtered_items)

    if not filtered_items:
        st.info("暂无符合条件的库存物品。")
        return

    for item in filtered_items:
        _render_item_card(
            service,
            item,
            history_options,
            custom_fields,
            operator,
        )


def _render_item_form(
    service: InventoryService,
    history_options: dict[str, list[str]],
    custom_fields: list[dict],
    operator: str,
    form_key: str,
    item: dict | None = None,
) -> None:
    current = item or {}
    item_id = current.get("id")
    extra_fields = _parse_extra_fields(current.get("extra_fields"))

    with st.form(form_key):
        top_columns = st.columns(2)
        with top_columns[0]:
            item_code = st.text_input(
                "编号 *",
                value=str(current.get("item_code", "")),
                key=f"{form_key}_code",
                help="编号由你手动输入，且不能与已有编号重复",
            )
        with top_columns[1]:
            quantity = st.number_input(
                "初始数量",
                min_value=0,
                value=0,
                step=1,
                key=f"{form_key}_quantity",
                disabled=item is not None,
                help="编辑物品时请使用入库或出库调整数量",
            )

        title_selected, title_new = _reusable_value_inputs(
            "title",
            history_options.get("title", []),
            f"{form_key}_title",
            current.get("title", ""),
            required=True,
        )
        category_selected, category_new = _direct_value_input(
            "title类别",
            f"{form_key}_category",
            current.get("category", ""),
        )
        location_selected, location_new = _reusable_value_inputs(
            "存放位置",
            history_options.get("location", []),
            f"{form_key}_location",
            current.get("location", ""),
        )

        remark = ""
        if item is None:
            remark = st.text_input(
                "初始入库备注",
                key=f"{form_key}_remark",
                placeholder="例如：首次入库、采购入库",
            )

        submitted_extra = {}
        if custom_fields:
            st.markdown("**自定义字段**")
            field_columns = st.columns(2)
            for index, field in enumerate(custom_fields):
                with field_columns[index % 2]:
                    field_name = field.get("field_name", "")
                    label = field.get("field_label") or field_name
                    submitted_extra[field_name] = st.text_input(
                        label,
                        value=str(extra_fields.get(field_name, "")),
                        key=f"{form_key}_extra_{field.get('id')}",
                    )

        submitted = st.form_submit_button(
            "💾 保存修改" if item is not None else "✅ 添加物品",
            type="primary",
            use_container_width=True,
        )
        if submitted:
            payload = {
                "item_code": item_code,
                "title_selected": title_selected,
                "title_new": title_new,
                "category_selected": category_selected,
                "category_new": category_new,
                "location_selected": location_selected,
                "location_new": location_new,
                "quantity": int(quantity),
                "remark": remark,
                "extra_fields": submitted_extra,
            }
            try:
                if item_id is None:
                    service.create_item(payload, operator=operator)
                    st.success("库存物品添加成功")
                else:
                    service.update_item(int(item_id), payload)
                    st.success("库存物品修改成功")
                st.rerun()
            except InventoryError as exc:
                st.error(str(exc))
            except Exception:
                logger.exception("保存库存物品失败")
                st.error("保存失败，请稍后重试")


def _reusable_value_inputs(
    label: str,
    options: list[str],
    key_prefix: str,
    current_value: str = "",
    required: bool = False,
) -> tuple[str, str]:
    normalized = normalize_options(options, current_value=current_value)
    select_options = [""] + normalized
    current = str(current_value or "").strip()
    index = select_options.index(current) if current in select_options else 0
    new_value = st.text_input(
        f"{label}（新增值）",
        value=current if not normalized else "",
        key=f"{key_prefix}_new",
        placeholder="填写后保存，并自动加入下方历史值",
    )
    selected = st.selectbox(
        f"已有{label}（可选，直接选择）",
        select_options,
        index=index,
        key=f"{key_prefix}_selected",
        format_func=lambda value: value or "不选择历史值",
    )
    return selected, new_value


def _direct_value_input(
    label: str,
    key_prefix: str,
    current_value: str = "",
) -> tuple[str, str]:
    value = st.text_input(
        label,
        value=str(current_value or ""),
        key=f"{key_prefix}_new",
        placeholder="直接输入类别，例如：实验耗材",
    )
    return "", value


def _render_item_card(
    service: InventoryService,
    item: dict,
    history_options: dict[str, list[str]],
    custom_fields: list[dict],
    operator: str,
) -> None:
    item_id = int(item["id"])
    is_active = bool(item.get("is_active", 1))
    quantity = int(item.get("quantity", 0) or 0)
    status_text = "启用" if is_active else "已归档"
    title = item.get("title", "")
    code = item.get("item_code", "")

    with st.expander(f"{code} · {title} · 库存 {quantity} · {status_text}"):
        info_columns = st.columns(4)
        info_columns[0].metric("当前库存", quantity)
        info_columns[1].write(f"**类别**\n\n{item.get('category') or '未填写'}")
        info_columns[2].write(f"**存放位置**\n\n{item.get('location') or '未填写'}")
        info_columns[3].write(f"**状态**\n\n{status_text}")

        if is_active:
            _render_stock_form(service, item, operator)
            with st.expander("✏️ 编辑物品"):
                _render_item_form(
                    service,
                    history_options,
                    custom_fields,
                    operator,
                    form_key=f"inventory_edit_{item_id}",
                    item=item,
                )
            _render_archive_delete_actions(service, item)
        else:
            if st.button("♻️ 恢复启用", key=f"inventory_restore_{item_id}"):
                try:
                    service.restore_item(item_id)
                    st.success("物品已恢复启用")
                    st.rerun()
                except InventoryError as exc:
                    st.error(str(exc))


def _render_stock_form(service: InventoryService, item: dict, operator: str) -> None:
    item_id = int(item["id"])
    current_stock = int(item.get("quantity", 0) or 0)
    with st.form(f"inventory_stock_{item_id}"):
        columns = st.columns([1, 1, 2])
        with columns[0]:
            transaction_label = st.selectbox(
                "操作类型",
                ["入库", "出库"],
                key=f"inventory_stock_type_{item_id}",
            )
        with columns[1]:
            quantity = st.number_input(
                "数量",
                min_value=1,
                value=1,
                step=1,
                key=f"inventory_stock_quantity_{item_id}",
            )
        with columns[2]:
            remark = st.text_input(
                "备注",
                key=f"inventory_stock_remark_{item_id}",
                placeholder=f"当前库存：{current_stock}",
            )
        if st.form_submit_button("确认操作", type="primary", use_container_width=True):
            try:
                service.change_stock(
                    item_id,
                    "in" if transaction_label == "入库" else "out",
                    int(quantity),
                    remark=remark,
                    operator=operator,
                )
                st.success(f"{transaction_label}成功")
                st.rerun()
            except InventoryError as exc:
                st.error(str(exc))
            except Exception:
                logger.exception("库存数量调整失败")
                st.error("操作失败，请稍后重试")


def _render_archive_delete_actions(service: InventoryService, item: dict) -> None:
    item_id = int(item["id"])
    confirm_key = f"inventory_confirm_remove_{item_id}"
    if st.button("🗄️ 归档或删除", key=f"inventory_remove_{item_id}"):
        st.session_state[confirm_key] = True
    if st.session_state.get(confirm_key):
        st.warning("有出入库记录的物品将归档；无记录的物品将彻底删除。")
        columns = st.columns(2)
        if columns[0].button("确认执行", key=f"inventory_remove_confirm_{item_id}"):
            try:
                result = service.archive_or_delete(item_id)
                st.success("物品已归档" if result == "archived" else "物品已删除")
                st.session_state.pop(confirm_key, None)
                st.rerun()
            except InventoryError as exc:
                st.error(str(exc))
        if columns[1].button("取消", key=f"inventory_remove_cancel_{item_id}"):
            st.session_state.pop(confirm_key, None)
            st.rerun()


def _render_inventory_exports(items: list[dict]) -> None:
    rows = []
    for item in items:
        rows.append(
            {
                "编号": item.get("item_code", ""),
                "title": item.get("title", ""),
                "title类别": item.get("category", ""),
                "存放位置": item.get("location", ""),
                "数量": int(item.get("quantity", 0) or 0),
                "状态": "启用" if bool(item.get("is_active", 1)) else "已归档",
            }
        )
    frame = pd.DataFrame(rows)
    columns = st.columns([3, 1, 1])
    columns[0].caption(f"共 {len(rows)} 条记录，可导出当前筛选结果")
    columns[1].download_button(
        "导出 Excel",
        data=_excel_bytes(frame, "库存列表"),
        file_name="库存列表.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        disabled=frame.empty,
    )
    columns[2].download_button(
        "导出 CSV",
        data=frame.to_csv(index=False).encode("utf-8-sig"),
        file_name="库存列表.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=frame.empty,
    )


def _render_transactions_tab(service: InventoryService) -> None:
    records = _safe_call(service.list_transactions, [], "读取出入库记录失败")
    rows = transaction_rows(records)
    filter_columns = st.columns([2, 1])
    keyword = filter_columns[0].text_input(
        "搜索记录",
        key="inventory_transaction_keyword",
        placeholder="编号、title、备注或操作人",
    )
    transaction_type = filter_columns[1].selectbox(
        "类型",
        ["全部", "入库", "出库"],
        key="inventory_transaction_type",
    )
    normalized_keyword = keyword.strip().casefold()
    filtered_rows = []
    for row in rows:
        if transaction_type != "全部" and row["类型"] != transaction_type:
            continue
        if normalized_keyword and not any(
            normalized_keyword in str(row.get(key, "")).casefold()
            for key in ("编号", "title", "备注", "操作人")
        ):
            continue
        filtered_rows.append(row)
    if not filtered_rows:
        st.info("暂无符合条件的出入库记录。")
        return
    frame = pd.DataFrame(filtered_rows)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button(
        "导出出入库记录 CSV",
        data=frame.to_csv(index=False).encode("utf-8-sig"),
        file_name="出入库记录.csv",
        mime="text/csv",
    )


def _render_fields_tab(service: InventoryService) -> None:
    fields = _safe_call(service.list_fields, [], "读取自定义字段失败")
    if fields:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": field.get("id"),
                        "字段名": field.get("field_name", ""),
                        "显示标签": field.get("field_label", ""),
                        "类型": field.get("field_type", "text"),
                    }
                    for field in fields
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        field_options = {
            f"{field.get('field_label') or field.get('field_name')} ({field.get('field_name')})": field
            for field in fields
        }
        selected_label = st.selectbox(
            "选择字段",
            list(field_options),
            key="inventory_field_delete_selection",
        )
        if st.button("删除所选字段", key="inventory_field_delete_button"):
            try:
                service.delete_field(int(field_options[selected_label]["id"]))
                st.success("字段删除成功")
                st.rerun()
            except InventoryError as exc:
                st.error(str(exc))
    else:
        st.info("暂无自定义字段。")

    st.divider()
    st.subheader("添加自定义字段")
    with st.form("inventory_field_create"):
        columns = st.columns(3)
        field_name = columns[0].text_input(
            "字段名 *",
            placeholder="例如 batch_no",
        )
        field_label = columns[1].text_input(
            "显示标签 *",
            placeholder="例如 批次号",
        )
        field_type = columns[2].selectbox("字段类型", ["text", "number"])
        if st.form_submit_button("添加字段", type="primary"):
            try:
                service.add_field(field_name, field_label, field_type)
                st.success("字段添加成功")
                st.rerun()
            except InventoryError as exc:
                st.error(str(exc))


def _parse_extra_fields(raw_value) -> dict:
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _excel_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def _safe_call(callable_obj, default, error_message: str):
    try:
        return callable_obj()
    except Exception:
        logger.exception(error_message)
        st.error(error_message)
        return default
