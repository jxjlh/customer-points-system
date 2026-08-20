"""原生 Streamlit Crayotter AI 视频剪辑工作台。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import streamlit as st

from modules.crayotter_client import (
    BACKEND_LOG,
    RUNTIME_ROOT,
    CrayotterClient,
    CrayotterError,
    backend_status,
    ensure_runtime_layout,
    merge_profile_config,
    read_backend_log,
    runtime_diagnostics,
    save_uploaded_files,
    start_backend,
    stop_backend,
)


VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
STATUS_LABELS = {
    "queued": "排队中",
    "running": "处理中",
    "interrupted": "已中断",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}


def _format_bytes(size: int | float | None) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _status_text(status: str) -> str:
    return STATUS_LABELS.get(status, status or "未知")


def _selected_job_id(jobs: list[dict[str, Any]]) -> str | None:
    if not jobs:
        return None
    ids = [str(job.get("job_id") or "") for job in jobs if job.get("job_id")]
    current = st.session_state.get("crayotter_selected_job")
    if current not in ids:
        st.session_state["crayotter_selected_job"] = ids[0]
    return st.session_state.get("crayotter_selected_job")


def _ensure_backend(client: CrayotterClient) -> dict[str, Any]:
    status = backend_status(client)
    if status["healthy"] or st.session_state.get("crayotter_autostart_attempted"):
        return status
    st.session_state["crayotter_autostart_attempted"] = True
    with st.spinner("正在启动 AI 视频剪辑服务，首次启动可能需要几十秒……"):
        ok, message = start_backend(client)
    st.session_state["crayotter_start_message"] = (ok, message)
    return backend_status(client)


def _render_service_header(client: CrayotterClient, status: dict[str, Any]) -> None:
    st.header("🎬 AI 视频剪辑")
    st.caption(
        "原生 Streamlit 工作台 · 素材上传 · Agent 自动剪辑 · 任务追踪 · 成片下载 · API 随时切换"
    )

    service_col, ffmpeg_col, api_col = st.columns(3)
    service_col.metric("剪辑服务", "运行中" if status["healthy"] else "未启动")
    diagnostics = runtime_diagnostics()
    ffmpeg_col.metric("FFmpeg", "可用" if diagnostics["ffmpeg"] else "缺失")

    api_ready = False
    if status["healthy"]:
        try:
            profile = client.get_config().get("profiles", {}).get("default", {})
            api_ready = bool(profile.get("api_key"))
        except CrayotterError:
            pass
    api_col.metric("主模型 API", "已配置" if api_ready else "未配置")

    start_message = st.session_state.pop("crayotter_start_message", None)
    if start_message:
        ok, message = start_message
        (st.success if ok else st.error)(message)

    if status["healthy"]:
        st.success("剪辑后端仅在服务器内部运行，不再使用浏览器 localhost iframe。")
        return

    st.error("剪辑服务尚未就绪。请检查依赖与运行日志后重试。")
    col_retry, col_log = st.columns(2)
    with col_retry:
        if st.button("重新启动剪辑服务", type="primary", use_container_width=True):
            st.session_state["crayotter_autostart_attempted"] = False
            st.rerun()
    with col_log:
        if st.button("刷新状态", use_container_width=True):
            st.rerun()


def _render_create_task(client: CrayotterClient) -> None:
    st.subheader("创建剪辑任务")
    st.write("上传已有素材并描述成片要求。没有本地素材时，Agent 也可以按配置搜索公开素材。")

    uploaded_files = st.file_uploader(
        "上传视频素材",
        type=["mp4", "mov", "webm", "m4v", "avi", "mkv"],
        accept_multiple_files=True,
        help="保存后会自动加入本次任务的本地素材列表。",
    )

    with st.form("crayotter_create_job"):
        task = st.text_area(
            "剪辑要求",
            height=150,
            placeholder="例如：把上传的实验室素材剪成 60 秒宣传片，节奏清晰，添加中文字幕和自然旁白。",
        )
        col_duration, col_mode, col_deadline = st.columns(3)
        with col_duration:
            target_duration = st.number_input(
                "目标时长（秒）",
                min_value=0,
                max_value=3600,
                value=60,
                step=5,
                help="填写 0 表示由 Agent 自行决定。",
            )
        with col_mode:
            processing_mode = st.selectbox(
                "处理模式",
                options=["auto", "speed", "quality"],
                format_func=lambda value: {"auto": "自动", "speed": "速度优先", "quality": "质量优先"}[value],
            )
        with col_deadline:
            deadline_seconds = st.number_input(
                "任务时限（秒）",
                min_value=60,
                max_value=7200,
                value=600,
                step=60,
            )

        col_research, col_review, col_direct = st.columns(3)
        with col_research:
            enable_research = st.checkbox("启用深度剪辑研究", value=True)
        with col_review:
            enable_plan_review = st.checkbox("剪辑蓝图需人工确认", value=False)
        with col_direct:
            direct_execution = st.checkbox("只使用已有素材", value=bool(uploaded_files))

        submitted = st.form_submit_button("开始 AI 剪辑", type="primary", use_container_width=True)

    if not submitted:
        return
    if not task.strip():
        st.error("请先填写剪辑要求。")
        return

    try:
        saved_files = save_uploaded_files(uploaded_files or [])
        material_lines = [item["display_path"] for item in saved_files]
        task_text = task.strip()
        if material_lines:
            task_text += "\n\n已上传本地素材：\n" + "\n".join(f"- {path}" for path in material_lines)
        payload: dict[str, Any] = {
            "task": task_text,
            "mode": "agent",
            "profile": "default",
            "enable_phase2_research": enable_research,
            "enable_plan_review": enable_plan_review,
            "direct_phase3_execution": direct_execution,
            "prefer_local_materials": bool(saved_files),
            "deadline_seconds": int(deadline_seconds),
            "processing_mode": processing_mode,
        }
        if target_duration:
            payload["target_duration_seconds"] = float(target_duration)
        record = client.create_job(payload)
    except (CrayotterError, OSError, ValueError) as exc:
        st.error(f"创建任务失败：{exc}")
        return

    st.session_state["crayotter_selected_job"] = record.get("job_id")
    st.success(f"任务已创建：{record.get('job_id')}。请前往“任务中心”查看进度。")


def _render_plan_review(client: CrayotterClient, job: dict[str, Any]) -> None:
    if job.get("current_checkpoint") != "plan_review" and job.get("steering_status") != "waiting_user":
        return
    try:
        response = client.get_current_plan(str(job["job_id"]))
    except CrayotterError:
        return
    plan = response.get("plan") if isinstance(response, dict) else None
    if not isinstance(plan, dict):
        return
    st.warning("该任务正在等待剪辑蓝图确认。")
    with st.expander("查看剪辑蓝图", expanded=True):
        st.json(plan)
        version = str(plan.get("version") or "")
        approve_col, reject_col = st.columns(2)
        with approve_col:
            if st.button("批准蓝图并继续", type="primary", use_container_width=True):
                client.approve_plan(str(job["job_id"]), version)
                st.rerun()
        with reject_col:
            if st.button("拒绝蓝图", use_container_width=True):
                client.reject_plan(str(job["job_id"]), version)
                st.rerun()


def _event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events[-100:]:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        summary = payload.get("message") or payload.get("summary") or payload.get("status") or ""
        rows.append(
            {
                "序号": event.get("sequence", ""),
                "时间": event.get("timestamp", ""),
                "事件": event.get("type", ""),
                "摘要": str(summary)[:300],
            }
        )
    return rows


def _render_artifacts(client: CrayotterClient, job_id: str) -> None:
    try:
        artifacts = client.list_artifacts(job_id)
    except CrayotterError as exc:
        st.warning(f"读取产物失败：{exc}")
        return
    if not artifacts:
        st.info("任务尚未生成可下载产物。")
        return

    for index, artifact in enumerate(artifacts):
        path = str(artifact.get("path") or "")
        name = str(artifact.get("name") or Path(path).name or f"artifact-{index + 1}")
        suffix = str(artifact.get("suffix") or Path(name).suffix).lower()
        size = int(artifact.get("size_bytes") or 0)
        with st.container(border=True):
            st.write(f"**{name}** · {_format_bytes(size)}")
            st.caption(str(artifact.get("display_path") or path))
            if st.button("加载预览与下载", key=f"artifact_load_{job_id}_{index}"):
                try:
                    data = client.read_artifact(path)
                except CrayotterError as exc:
                    st.error(f"读取文件失败：{exc}")
                    continue
                if suffix in VIDEO_SUFFIXES:
                    st.video(data)
                st.download_button(
                    "下载文件",
                    data=data,
                    file_name=name,
                    mime="video/mp4" if suffix == ".mp4" else "application/octet-stream",
                    key=f"artifact_download_{job_id}_{index}",
                )


def _render_job_center(client: CrayotterClient) -> None:
    st.subheader("任务中心")
    refresh_col, hint_col = st.columns([1, 4])
    with refresh_col:
        if st.button("刷新任务", use_container_width=True):
            st.rerun()
    with hint_col:
        st.caption("视频处理期间可随时刷新；后端任务会继续在服务器中运行。")

    try:
        jobs = sorted(client.list_jobs(), key=lambda item: str(item.get("created_at") or ""), reverse=True)
    except CrayotterError as exc:
        st.error(f"读取任务列表失败：{exc}")
        return
    if not jobs:
        st.info("还没有剪辑任务。")
        return

    selected_id = _selected_job_id(jobs)
    job_by_id = {str(job["job_id"]): job for job in jobs}
    selected_id = st.selectbox(
        "选择任务",
        options=list(job_by_id),
        index=list(job_by_id).index(selected_id) if selected_id in job_by_id else 0,
        format_func=lambda job_id: (
            f"{_status_text(str(job_by_id[job_id].get('status')))} · "
            f"{str(job_by_id[job_id].get('title') or job_by_id[job_id].get('task') or job_id)[:45]}"
        ),
    )
    st.session_state["crayotter_selected_job"] = selected_id

    try:
        job = client.get_job(selected_id)
    except CrayotterError as exc:
        st.error(f"读取任务详情失败：{exc}")
        return

    status = str(job.get("status") or "")
    metric_status, metric_checkpoint, metric_elapsed = st.columns(3)
    metric_status.metric("状态", _status_text(status))
    metric_checkpoint.metric("当前阶段", str(job.get("current_checkpoint") or "—"))
    metric_elapsed.metric("耗时", f"{float(job.get('total_wall_seconds') or 0):.1f} 秒")
    st.write(str(job.get("task") or ""))
    if job.get("error"):
        st.error(str(job["error"]))
    if job.get("final_output"):
        st.success(str(job["final_output"]))

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button(
            "取消任务",
            disabled=status in TERMINAL_STATUSES,
            use_container_width=True,
        ):
            client.cancel_job(selected_id)
            st.rerun()
    with action_col2:
        if st.button(
            "恢复任务",
            disabled=status != "interrupted",
            use_container_width=True,
        ):
            client.resume_job(selected_id)
            st.rerun()
    with action_col3:
        guidance = st.text_input("运行中补充要求", key=f"guidance_{selected_id}", label_visibility="collapsed", placeholder="输入补充要求")
        if st.button("发送补充要求", disabled=not guidance.strip(), use_container_width=True):
            client.send_message(selected_id, guidance.strip())
            st.success("补充要求已发送。")

    _render_plan_review(client, job)

    artifact_tab, event_tab, raw_tab = st.tabs(["成片与文件", "运行事件", "任务详情"])
    with artifact_tab:
        _render_artifacts(client, selected_id)
    with event_tab:
        try:
            rows = _event_rows(client.list_events(selected_id))
        except CrayotterError as exc:
            st.warning(f"读取事件失败：{exc}")
        else:
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                st.info("暂无运行事件。")
    with raw_tab:
        st.json(job)


def _render_api_config(client: CrayotterClient) -> None:
    st.subheader("API 与模型配置")
    st.caption("密码框留空会保留当前 Key；填写新值后即可切换 API 服务商或模型。")
    try:
        config = client.get_config()
    except CrayotterError as exc:
        st.error(f"读取配置失败：{exc}")
        return
    profile = dict(config.get("profiles", {}).get("default", {}))

    with st.form("crayotter_native_config"):
        st.markdown("#### 主文本模型")
        main_col1, main_col2 = st.columns(2)
        with main_col1:
            api_key = st.text_input(
                "API Key",
                type="password",
                value="",
                placeholder="已配置" if profile.get("api_key") else "请输入 API Key",
            )
            base_url = st.text_input("Base URL", value=str(profile.get("base_url") or ""))
        with main_col2:
            model_name = st.text_input("模型名称", value=str(profile.get("model_name") or ""))
            st.text_input("当前 Key 状态", value="已配置" if profile.get("api_key") else "未配置", disabled=True)

        st.markdown("#### 视频理解模型")
        video_col1, video_col2 = st.columns(2)
        with video_col1:
            video_api_key = st.text_input(
                "视频 API Key",
                type="password",
                value="",
                placeholder="留空则保留当前配置/复用主 Key",
            )
            video_base_url = st.text_input("视频 Base URL", value=str(profile.get("video_base_url") or ""))
        with video_col2:
            video_model = st.text_input("视频模型", value=str(profile.get("video_model_name") or ""))
            st.text_input(
                "视频 Key 状态",
                value="已单独配置" if profile.get("video_api_key") else "复用主 Key",
                disabled=True,
            )

        st.markdown("#### TTS 配音模型")
        tts_col1, tts_col2 = st.columns(2)
        with tts_col1:
            tts_api_key = st.text_input(
                "TTS API Key",
                type="password",
                value="",
                placeholder="留空则保留当前配置/复用主 Key",
            )
            tts_base_url = st.text_input("TTS Base URL", value=str(profile.get("tts_base_url") or ""))
        with tts_col2:
            tts_model = st.text_input("TTS 模型", value=str(profile.get("tts_model_name") or ""))
            st.text_input(
                "TTS Key 状态",
                value="已单独配置" if profile.get("tts_api_key") else "复用主 Key",
                disabled=True,
            )

        st.markdown("#### 工作流默认设置")
        option_col1, option_col2 = st.columns(2)
        with option_col1:
            enable_research = st.checkbox(
                "默认启用深度剪辑研究",
                value=config.get("enable_phase2_research") is not False,
            )
            enable_review = st.checkbox(
                "默认需要人工确认剪辑蓝图",
                value=config.get("enable_plan_review") is not False,
            )
        with option_col2:
            default_deadline = st.number_input(
                "默认任务时限（秒）",
                min_value=60,
                max_value=7200,
                value=int(config.get("default_deadline_seconds") or 600),
                step=60,
            )
            processing_mode = st.selectbox(
                "默认处理模式",
                options=["auto", "speed", "quality"],
                index=["auto", "speed", "quality"].index(str(config.get("processing_mode") or "auto")),
            )

        save_config = st.form_submit_button("保存并立即使用新 API", type="primary", use_container_width=True)

    if not save_config:
        return
    submitted_profile = {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
        "video_api_key": video_api_key,
        "video_base_url": video_base_url,
        "video_model_name": video_model,
        "tts_api_key": tts_api_key,
        "tts_base_url": tts_base_url,
        "tts_model_name": tts_model,
    }
    payload = dict(config)
    payload["active_profile"] = "default"
    payload["profiles"] = {"default": merge_profile_config(profile, submitted_profile)}
    payload["enable_phase2_research"] = enable_research
    payload["enable_plan_review"] = enable_review
    payload["default_deadline_seconds"] = int(default_deadline)
    payload["processing_mode"] = processing_mode
    try:
        client.update_config(payload)
    except CrayotterError as exc:
        st.error(f"保存配置失败：{exc}")
        return
    st.success("API 与模型配置已保存，新任务会立即使用该配置。")
    time.sleep(0.5)
    st.rerun()


def _render_diagnostics(client: CrayotterClient, status: dict[str, Any]) -> None:
    st.subheader("运行诊断")
    diagnostics = runtime_diagnostics()
    st.json(
        {
            "backend_healthy": status["healthy"],
            "backend_pid": status["pid"],
            "backend_bind": f"{client.host}:{client.port}",
            "python": diagnostics["python"],
            "ffmpeg": diagnostics["ffmpeg"] or "未找到",
            "runtime_root": diagnostics["runtime_root"],
            "python_modules": diagnostics["modules"],
        }
    )
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("重启剪辑服务", use_container_width=True):
            stop_backend()
            st.session_state["crayotter_autostart_attempted"] = False
            st.rerun()
    with action_col2:
        if st.button("停止剪辑服务", use_container_width=True):
            ok, message = stop_backend()
            (st.success if ok else st.error)(message)

    st.markdown(f"- 运行目录：`{RUNTIME_ROOT}`")
    st.markdown(f"- 后端日志：`{BACKEND_LOG}`")
    st.code(read_backend_log(120), language="text")


def show_video_editor() -> None:
    ensure_runtime_layout()
    client = CrayotterClient()
    status = _ensure_backend(client)
    _render_service_header(client, status)

    if not status["healthy"]:
        _render_diagnostics(client, status)
        return

    create_tab, jobs_tab, config_tab, diagnostics_tab = st.tabs(
        ["创建任务", "任务中心", "API 配置", "运行诊断"]
    )
    with create_tab:
        _render_create_task(client)
    with jobs_tab:
        _render_job_center(client)
    with config_tab:
        _render_api_config(client)
    with diagnostics_tab:
        _render_diagnostics(client, status)
