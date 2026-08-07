"""
🎬 AI 视频剪辑板块（Crayotter 嵌入模块）

将 Crayotter 的完整多模态三阶段 Agent 工作流集成到澄天小助手内：
- 作为独立的 Streamlit 页面板块，与其他模块风格一致
- 启动/监控 Crayotter 后端（独立进程，避免阻塞 Streamlit）
- 通过 iframe 嵌入完整的 Crayotter Workbench UI
- 提供一键配置 API Key、资源池参数、启动/停止后端等管理入口

所有 Crayotter 运行态数据放在 repo 根目录的 `crayotter_runtime/` 下
（.env / logs / temp / user_temp / app_state），与积分系统隔离。
Crayotter 源码位于 `crayotter/` 子目录。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import streamlit as st

# ---------- 路径常量 ---------- #
REPO_ROOT = Path(__file__).resolve().parent.parent
CRAYOTTER_SRC = REPO_ROOT / "crayotter"
RUNTIME_ROOT = REPO_ROOT / "crayotter_runtime"
ENV_PATH = RUNTIME_ROOT / ".env"
ENV_EXAMPLE = CRAYOTTER_SRC / ".env.example"
RUNTIME_BACKEND_LOG = RUNTIME_ROOT / "backend.log"
RUNTIME_BACKEND_META = RUNTIME_ROOT / "backend_meta.json"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18765


def _ensure_runtime_layout() -> None:
    for sub in ("logs", "temp", "user_temp", "app_state", "app_state/jobs", "memory_experience"):
        (RUNTIME_ROOT / sub).mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists() and ENV_EXAMPLE.exists():
        ENV_PATH.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    seed_src = CRAYOTTER_SRC / "memory_experience"
    seed_dst = RUNTIME_ROOT / "memory_experience"
    if seed_src.exists() and seed_dst.exists():
        for file in seed_src.iterdir():
            if file.is_file() and not (seed_dst / file.name).exists():
                try:
                    (seed_dst / file.name).write_bytes(file.read_bytes())
                except Exception:
                    pass


def _python_bin() -> str:
    return sys.executable or "python"


def _read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    data: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _write_env(kv: dict[str, str]) -> None:
    current = _read_env()
    merged = dict(current)
    order = list(current.keys())
    for k in kv:
        if k not in order:
            order.append(k)
    for k, v in kv.items():
        v = (v or "").strip()
        if v:
            merged[k] = v
        else:
            merged.pop(k, None)
    lines = [f"{k}={merged[k]}" for k in order if k in merged]
    ENV_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _backend_url(path: str = "/") -> str:
    host = _read_env().get("CRAYOTTER_WORKBENCH_HOST") or DEFAULT_HOST
    port = int(_read_env().get("CRAYOTTER_WORKBENCH_PORT") or DEFAULT_PORT)
    return f"http://{host}:{port}{path}"


def _http_json(method: str, path: str, body: dict[str, Any] | None = None, timeout: float = 6.0):
    url = _backend_url(path)
    try:
        data: bytes | None = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return code, json.loads(raw), ""
            except Exception:
                return code, raw, ""
    except Exception as exc:
        return 0, None, str(exc)


# ---------- 后端生命周期 ---------- #


def _save_meta(meta: dict[str, Any]) -> None:
    RUNTIME_BACKEND_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_meta() -> dict[str, Any]:
    if RUNTIME_BACKEND_META.exists():
        try:
            return json.loads(RUNTIME_BACKEND_META.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def backend_status() -> dict[str, Any]:
    meta = _load_meta()
    pid = meta.get("pid")
    alive_by_pid = _pid_alive(pid)
    code, payload, err = _http_json("GET", "/health", timeout=3.0)
    healthy = code == 200 and isinstance(payload, dict) and payload.get("ok") is True
    return {
        "pid": pid,
        "pid_alive": alive_by_pid,
        "healthy": healthy,
        "host": meta.get("host") or _read_env().get("CRAYOTTER_WORKBENCH_HOST") or DEFAULT_HOST,
        "port": meta.get("port") or int(_read_env().get("CRAYOTTER_WORKBENCH_PORT") or DEFAULT_PORT),
        "health_code": code,
        "health_err": err,
    }


def start_backend():
    status = backend_status()
    if status["healthy"]:
        return True, f"后端已经在运行（PID {status['pid'] or 'N/A'}）"

    _ensure_runtime_layout()
    host = _read_env().get("CRAYOTTER_WORKBENCH_HOST") or DEFAULT_HOST
    port = int(_read_env().get("CRAYOTTER_WORKBENCH_PORT") or DEFAULT_PORT)

    env = os.environ.copy()
    env["CRAYOTTER_RUNTIME_ROOT"] = str(RUNTIME_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    startup_source = rf"""
import sys, os, runpy
src = r"{CRAYOTTER_SRC}"
sys.path.insert(0, src)
sys.argv = ['run_backend.py', '--host', r"{host}", '--port', str({port})]
runpy.run_path(os.path.join(src, 'script', 'run_backend.py'), run_name='__main__')
"""

    RUNTIME_BACKEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_fh = RUNTIME_BACKEND_LOG.open("ab")

    try:
        proc = subprocess.Popen(
            [_python_bin(), "-c", startup_source],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            env=env,
            start_new_session=True,
        )
    except Exception as exc:
        log_fh.close()
        return False, f"启动失败：{exc}"

    deadline = time.time() + 60
    last_err = "后端未在规定时间内就绪"
    while time.time() < deadline:
        if proc.poll() is not None:
            proc.wait()
            log_fh.close()
            lines = RUNTIME_BACKEND_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            return False, "后端启动后立即退出，最近日志：\n" + "\n".join(lines)
        code, payload, err = _http_json("GET", "/health", timeout=2.0)
        if code == 200 and isinstance(payload, dict) and payload.get("ok") is True:
            _save_meta({"pid": proc.pid, "host": host, "port": port, "started_at": time.time()})
            log_fh.close()
            return True, f"✅ 启动成功（PID {proc.pid}）：http://{host}:{port}/ui/"
        last_err = err or f"/health 未就绪 (HTTP {code})"
        time.sleep(1.5)

    log_fh.close()
    return False, f"启动超时：{last_err}"


def stop_backend():
    meta = _load_meta()
    pid = meta.get("pid")
    if not pid or not _pid_alive(pid):
        if RUNTIME_BACKEND_META.exists():
            RUNTIME_BACKEND_META.unlink(missing_ok=True)
        return True, "后端没有在运行"

    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as exc:
            return False, f"停止失败：{exc}"

    deadline = time.time() + 15
    killed = False
    while time.time() < deadline:
        if not _pid_alive(pid):
            killed = True
            break
        time.sleep(0.5)

    if not killed:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception as exc:
                return False, f"强制停止失败：{exc}"
        time.sleep(1.0)

    RUNTIME_BACKEND_META.unlink(missing_ok=True)
    return True, "🛑 已停止后端"


# ---------- UI ---------- #


CONFIG_FIELDS = [
    ("CRAYOTTER_API_KEY", "API Key（DashScope / OpenAI 兼容）", "password"),
    ("CRAYOTTER_BASE_URL", "Base URL", "default"),
    ("CRAYOTTER_MODEL_NAME", "文本模型", "default"),
    ("CRAYOTTER_VIDEO_MODEL_NAME", "视频理解模型", "default"),
    ("CRAYOTTER_TTS_MODEL_NAME", "配音模型", "default"),
    ("CRAYOTTER_ENABLE_PHASE2_RESEARCH", "启用阶段2（深度剪辑研究）", "bool"),
    ("CRAYOTTER_ENABLE_PLAN_REVIEW", "生成剪辑蓝图后等我审核", "bool"),
    ("CRAYOTTER_DIRECT_PHASE3_EXECUTION", "跳过素材搜索，直接剪辑已有素材", "bool"),
    ("CRAYOTTER_PREFER_LOCAL_MATERIALS", "优先使用本地上传素材", "bool"),
    ("CRAYOTTER_SEARCH_POOL_SIZE", "搜索并发数", "int"),
    ("CRAYOTTER_DOWNLOAD_POOL_SIZE", "下载并发数", "int"),
    ("CRAYOTTER_VIDEO_ANALYSIS_POOL_SIZE", "视频分析并发数", "int"),
    ("CRAYOTTER_LLM_POOL_SIZE", "LLM 并发数", "int"),
    ("CRAYOTTER_FFMPEG_POOL_SIZE", "FFmpeg 并发数", "int"),
    ("CRAYOTTER_TTS_POOL_SIZE", "TTS 并发数", "int"),
    ("CRAYOTTER_WORKBENCH_HOST", "工作台监听地址（重启生效）", "default"),
    ("CRAYOTTER_WORKBENCH_PORT", "工作台端口（重启生效）", "int"),
]


def show_video_editor() -> None:
    _ensure_runtime_layout()
    status = backend_status()

    st.markdown(
        """
    <div style='
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.12) 0%, rgba(0, 255, 213, 0.06) 100%);
        padding: 28px; border-radius: 20px; margin-bottom: 24px;
        border: 1px solid var(--border-glow);
        box-shadow: 0 0 30px rgba(0, 212, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative; overflow: hidden;
    '>
        <div style='position:absolute;top:0;left:0;right:0;height:3px;
             background:linear-gradient(90deg, var(--primary), var(--accent));
             box-shadow:0 0 15px var(--primary-glow);'></div>
        <h3 style='color: var(--text-primary); margin-bottom: 12px; font-weight: 700;'>
          🎬 AI 视频剪辑 · Crayotter
        </h3>
        <p style='color: var(--text-secondary); line-height: 1.8; margin: 0;'>
          一句话需求驱动三阶段工作流：<strong>Planner</strong> 素材规划 → <strong>Editing Research</strong>
          剪辑研究蓝图 → <strong>ReAct Editor</strong> 工具执行出片。支持 B 站/抖音/小红书/YouTube 素材搜索、
          多模态视频分析、专业转场、配音、字幕与日志轨迹可视化。
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    status_col1, status_col2, status_col3 = st.columns([3, 2, 2])
    badge_ok = (
        '<span style="background:rgba(81,207,102,0.15);color:#51cf66;border:1px solid rgba(81,207,102,0.4);'
        'padding:4px 12px;border-radius:20px;">● 运行中</span>'
    )
    badge_bad = (
        '<span style="background:rgba(255,107,107,0.15);color:#ff6b6b;border:1px solid rgba(255,107,107,0.4);'
        'padding:4px 12px;border-radius:20px;">● 未启动</span>'
    )
    status_col1.markdown(
        f"<div style='color:var(--text-secondary);font-size:13px;margin-top:6px;'>"
        f"后端状态：{badge_ok if status['healthy'] else badge_bad}"
        f" &nbsp; <span style='color:var(--text-muted);'>PID {status['pid'] or '—'} · "
        f"{status['host']}:{status['port']}</span></div>",
        unsafe_allow_html=True,
    )
    with status_col2:
        if st.button("🚀 启动后端", type="primary", use_container_width=True, disabled=status["healthy"]):
            with st.spinner("正在启动 Crayotter 后端..."):
                ok, msg = start_backend()
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
                time.sleep(0.5)
                st.rerun()
    with status_col3:
        if st.button("🛑 停止后端", use_container_width=True, disabled=not (status["pid"] and status["pid_alive"])):
            ok, msg = stop_backend()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            time.sleep(0.5)
            st.rerun()

    tab_workbench, tab_config, tab_logs = st.tabs(["🎛️ 工作台", "⚙️ 配置", "📜 日志"])

    with tab_workbench:
        if status["healthy"]:
            ui_url = _backend_url("/ui/")
            st.caption(f"直接在新窗口打开：{ui_url}")
            st.markdown(
                f"""
                <div style='border:1px solid var(--border); border-radius:16px; overflow:hidden;
                            background:#0a0e27; box-shadow: 0 8px 30px rgba(0,0,0,0.5);'>
                  <div style='height: 6px; background: linear-gradient(90deg, var(--primary), var(--accent));'></div>
                  <iframe src='{ui_url}' width='100%' height='1000px'
                          style='border:none; background:#0a0e27;'
                          title='Crayotter Workbench'
                          allow='clipboard-read; clipboard-write'></iframe>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("🎬 先点击右上角「🚀 启动后端」，然后就能在下方直接使用 Crayotter 工作台啦。")
            with st.expander("🧭 使用流程速览", expanded=True):
                st.markdown(
                    """
                **1. 在「⚙️ 配置」页填好 API Key（默认为阿里云百炼 Qwen 系列）。**
                - `CRAYOTTER_API_KEY`：主模型 key（百炼 DashScope）
                - 视频理解与 TTS 默认复用主 key，需要单独 key 可在下方填写

                **2. 回到「🎛️ 工作台」启动后端。**

                **3. 在工作台里输入一句话需求，例如：**
                > 做一个 1 分钟实验室小鼠配送宣传片，清新科技风，配字幕和旁白

                **4. 日志轨迹可视化：**
                任务完成后，在 Crayotter 的产物区可下载成片，日志文件保存在 `crayotter_runtime/logs/`，
                可以用 Crayotter 自带的 `crayotter/script/visualize.py` 再做可视化。
                """
                )

    with tab_config:
        _render_config_form()

    with tab_logs:
        _render_logs_tab(status)


def _render_config_form() -> None:
    env = _read_env()
    api_rows = [f for f in CONFIG_FIELDS
                if f[0].startswith("CRAYOTTER_API")
                or f[0].startswith("CRAYOTTER_BASE")
                or "MODEL_NAME" in f[0]]
    runtime_rows = [f for f in CONFIG_FIELDS if f[2] == "bool"]
    pool_rows = [f for f in CONFIG_FIELDS if f[2] == "int"]
    bind_rows = [f for f in CONFIG_FIELDS if f[0].startswith("CRAYOTTER_WORKBENCH_")]

    def val_for(key: str) -> str:
        return env.get(key, "")

    changed: dict[str, str] = {}

    st.subheader("🔑 API / 模型配置")
    with st.form("crayotter_api_form", border=False):
        cols = st.columns(2)
        for idx, (key, label, kind) in enumerate(api_rows):
            col = cols[idx % 2]
            cur = val_for(key)
            with col:
                if kind == "password":
                    v = st.text_input(label, value=cur, type="password", key=f"f_{key}")
                else:
                    v = st.text_input(label, value=cur, key=f"f_{key}")
                if v != cur:
                    changed[key] = v
        if st.form_submit_button("💾 保存 API 配置", use_container_width=True):
            _write_env(changed)
            st.success("已写入配置，新任务立即生效。")
            changed.clear()
            st.rerun()

    st.subheader("🧠 运行时开关")
    with st.form("crayotter_runtime_form", border=False):
        cols = st.columns(2)
        for idx, (key, label, _) in enumerate(runtime_rows):
            col = cols[idx % 2]
            cur = (val_for(key) or "false").lower() in ("1", "true", "yes", "y", "on")
            with col:
                v = st.checkbox(label, value=cur, key=f"f_{key}")
                if bool(v) != cur:
                    changed[key] = "true" if v else "false"
        if st.form_submit_button("💾 保存运行时开关", use_container_width=True):
            _write_env(changed)
            st.success("已更新运行时开关。")
            changed.clear()
            st.rerun()

    st.subheader("🧵 并发池 / 绑定地址")
    with st.form("crayotter_pool_form", border=False):
        cols = st.columns(2)
        all_pool = pool_rows + bind_rows
        for idx, (key, label, kind) in enumerate(all_pool):
            col = cols[idx % 2]
            cur = val_for(key)
            with col:
                if kind == "int":
                    try:
                        cv = int(cur) if cur else 1
                    except Exception:
                        cv = 1
                    v = st.number_input(label, min_value=1, max_value=64, value=cv, key=f"f_{key}")
                    if int(v) != cv:
                        changed[key] = str(int(v))
                else:
                    v = st.text_input(label, value=cur, key=f"f_{key}")
                    if v != cur:
                        changed[key] = v
        if st.form_submit_button("💾 保存并发/绑定", use_container_width=True):
            _write_env(changed)
            st.success("已保存并发/绑定配置，绑定地址变更需重启后端生效。")
            changed.clear()
            st.rerun()


def _render_logs_tab(status: dict[str, Any]) -> None:
    st.markdown(f"- 运行时根目录：`{RUNTIME_ROOT}`")
    st.markdown(f"- .env 位置：`{ENV_PATH}`")
    st.markdown(f"- 后端日志：`{RUNTIME_BACKEND_LOG}`")
    st.markdown(f"- Agent 日志目录：`{RUNTIME_ROOT / 'logs'}`")
    st.markdown(f"- Crayotter 源码：`{CRAYOTTER_SRC}`")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 刷新健康检查", use_container_width=True):
            code, payload, err = _http_json("GET", "/health", timeout=3.0)
            if code == 200:
                st.success(f"/health → {payload}")
            else:
                st.warning(f"未就绪：HTTP {code} · {err}")
    with col_b:
        if st.button("🔍 请求 /config 概览", use_container_width=True):
            code, payload, err = _http_json("GET", "/config", timeout=4.0)
            if code != 200:
                st.warning(f"/config 不可用：HTTP {code} · {err}")
            else:
                if isinstance(payload, dict):
                    pf = payload.get("profiles", {}).get("default", {})
                    st.success(
                        f"api_key 已设置：{bool(pf.get('api_key'))} · "
                        f"model={pf.get('model_name')} · video={pf.get('video_model_name')} · "
                        f"tts={pf.get('tts_model_name')}"
                    )
                else:
                    st.json(payload)

    if RUNTIME_BACKEND_LOG.exists():
        st.subheader("🪵 后端最近 100 行")
        text = RUNTIME_BACKEND_LOG.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[-100:]
        st.code("\n".join(lines), language="text")
    else:
        st.info("后端日志还不存在，启动后端后会写到 `crayotter_runtime/backend.log`。")
