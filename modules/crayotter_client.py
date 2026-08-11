from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
CRAYOTTER_SRC = REPO_ROOT / "crayotter"
RUNTIME_ROOT = Path(
    os.environ.get("CRAYOTTER_RUNTIME_ROOT", REPO_ROOT / "crayotter_runtime")
).expanduser().resolve()
ENV_PATH = RUNTIME_ROOT / ".env"
ENV_EXAMPLE = CRAYOTTER_SRC / ".env.example"
BACKEND_LOG = RUNTIME_ROOT / "backend.log"
BACKEND_META = RUNTIME_ROOT / "backend_meta.json"
UPLOADS_DIR = RUNTIME_ROOT / "user_temp"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18765
SECRET_FIELDS = {"api_key", "video_api_key", "tts_api_key"}


class CrayotterError(RuntimeError):
    pass


def _read_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _write_env_file(updates: dict[str, str]) -> None:
    current = _read_env_file()
    order = list(current)
    for key in updates:
        if key not in order:
            order.append(key)
    for key, raw_value in updates.items():
        value = str(raw_value or "").strip()
        if value:
            current[key] = value
        else:
            current.pop(key, None)
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={_quote_env_value(current[key])}" for key in order if key in current]
    ENV_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def ensure_runtime_layout() -> None:
    for relative in (
        "logs",
        "runtime_logs",
        "temp",
        "user_temp",
        "app_state",
        "app_state/jobs",
        "memory_experience",
    ):
        (RUNTIME_ROOT / relative).mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists() and ENV_EXAMPLE.exists():
        ENV_PATH.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    seed_dir = CRAYOTTER_SRC / "memory_experience"
    if seed_dir.exists():
        target_dir = RUNTIME_ROOT / "memory_experience"
        for source in seed_dir.iterdir():
            target = target_dir / source.name
            if source.is_file() and not target.exists():
                target.write_bytes(source.read_bytes())


def seed_config_from_environment() -> None:
    ensure_runtime_layout()
    current = _read_env_file()
    keys = (
        "CRAYOTTER_API_KEY",
        "CRAYOTTER_BASE_URL",
        "CRAYOTTER_MODEL_NAME",
        "CRAYOTTER_VIDEO_API_KEY",
        "CRAYOTTER_VIDEO_BASE_URL",
        "CRAYOTTER_VIDEO_MODEL_NAME",
        "CRAYOTTER_TTS_API_KEY",
        "CRAYOTTER_TTS_BASE_URL",
        "CRAYOTTER_TTS_MODEL_NAME",
    )
    updates = {
        key: os.environ[key]
        for key in keys
        if os.environ.get(key, "").strip() and not current.get(key, "").strip()
    }
    if updates:
        _write_env_file(updates)


def merge_profile_config(existing: dict[str, Any], submitted: dict[str, Any]) -> dict[str, str]:
    merged = {key: str(value or "").strip() for key, value in existing.items()}
    for key, raw_value in submitted.items():
        value = str(raw_value or "").strip()
        if key in SECRET_FIELDS and not value:
            continue
        merged[key] = value
    return merged


def safe_upload_name(filename: str) -> str:
    raw_name = Path(filename or "").name.strip()
    stem = Path(raw_name).stem or "uploaded_video"
    suffix = Path(raw_name).suffix.lower()
    safe_stem = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", stem).strip("_")
    safe_stem = safe_stem or "uploaded_video"
    safe_suffix = suffix if re.fullmatch(r"\.[0-9A-Za-z]{1,10}", suffix or "") else ""
    return f"{safe_stem}{safe_suffix}"


def _allocate_upload_path(upload_dir: Path, filename: str) -> Path:
    candidate = upload_dir / filename
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = upload_dir / f"{Path(filename).stem}_{index}{Path(filename).suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def save_uploaded_files(uploaded_files: Iterable[Any], upload_dir: Path = UPLOADS_DIR) -> list[dict[str, Any]]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    for uploaded_file in uploaded_files:
        name = safe_upload_name(getattr(uploaded_file, "name", ""))
        target = _allocate_upload_path(upload_dir, name)
        payload = bytes(uploaded_file.getbuffer())
        target.write_bytes(payload)
        saved.append(
            {
                "name": target.name,
                "path": str(target.resolve()),
                "display_path": (Path("user_temp") / target.name).as_posix(),
                "size_bytes": len(payload),
            }
        )
    return saved


class CrayotterClient:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = 8.0,
    ) -> None:
        if host != DEFAULT_HOST:
            raise ValueError("Crayotter backend must remain bound to 127.0.0.1.")
        self.host = host
        self.port = int(port)
        self.timeout = timeout

    def url(self, path: str) -> str:
        normalized = "/" + str(path or "").lstrip("/")
        return f"http://{self.host}:{self.port}{normalized}"

    def request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.url(path),
            data=data,
            method=method.upper(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(raw).get("error", raw)
            except json.JSONDecodeError:
                message = raw
            raise CrayotterError(f"HTTP {exc.code}: {message}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CrayotterError(str(exc)) from exc
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def request_bytes(self, path: str, *, timeout: float = 60.0) -> bytes:
        try:
            with urllib.request.urlopen(self.url(path), timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise CrayotterError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CrayotterError(str(exc)) from exc

    def health(self) -> bool:
        try:
            return self.request_json("GET", "/health", timeout=3.0) == {"ok": True}
        except CrayotterError:
            return False

    def get_config(self) -> dict[str, Any]:
        return self.request_json("GET", "/config")

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PUT", "/config", payload)

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.request_json("GET", "/jobs").get("items", [])

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/jobs/{urllib.parse.quote(job_id)}")

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", "/jobs", payload, timeout=20.0)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self.request_json("POST", f"/jobs/{urllib.parse.quote(job_id)}/cancel", {})

    def resume_job(self, job_id: str) -> dict[str, Any]:
        return self.request_json("POST", f"/jobs/{urllib.parse.quote(job_id)}/resume", {})

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        payload = self.request_json("GET", f"/jobs/{urllib.parse.quote(job_id)}/events")
        return payload.get("items", [])

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        payload = self.request_json("GET", f"/jobs/{urllib.parse.quote(job_id)}/artifacts")
        return payload.get("items", [])

    def get_current_plan(self, job_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/jobs/{urllib.parse.quote(job_id)}/plans/current")

    def approve_plan(self, job_id: str, version: str) -> dict[str, Any]:
        path = f"/jobs/{urllib.parse.quote(job_id)}/plans/{urllib.parse.quote(version)}/approve"
        return self.request_json("POST", path, {})

    def reject_plan(self, job_id: str, version: str) -> dict[str, Any]:
        path = f"/jobs/{urllib.parse.quote(job_id)}/plans/{urllib.parse.quote(version)}/reject"
        return self.request_json("POST", path, {})

    def send_message(self, job_id: str, content: str) -> dict[str, Any]:
        path = f"/jobs/{urllib.parse.quote(job_id)}/messages"
        return self.request_json("POST", path, {"content": content})

    def read_artifact(self, path: str) -> bytes:
        query = urllib.parse.urlencode({"path": path, "download": "1"})
        return self.request_bytes(f"/files?{query}", timeout=120.0)


def _load_meta() -> dict[str, Any]:
    if not BACKEND_META.exists():
        return {}
    try:
        return json.loads(BACKEND_META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def backend_status(client: CrayotterClient | None = None) -> dict[str, Any]:
    client = client or CrayotterClient()
    meta = _load_meta()
    pid = meta.get("pid")
    return {
        "healthy": client.health(),
        "pid": pid,
        "pid_alive": _pid_alive(pid),
        "host": client.host,
        "port": client.port,
    }


def build_backend_startup_source(port: int) -> str:
    return (
        "import os, runpy, sys\n"
        f"src = {str(CRAYOTTER_SRC)!r}\n"
        "sys.path.insert(0, src)\n"
        f"sys.argv = ['run_backend.py', '--host', {DEFAULT_HOST!r}, '--port', {str(int(port))!r}]\n"
        "runpy.run_path(os.path.join(src, 'script', 'run_backend.py'), run_name='__main__')\n"
    )


def start_backend(client: CrayotterClient | None = None, timeout: float = 60.0) -> tuple[bool, str]:
    client = client or CrayotterClient()
    if client.health():
        return True, "Crayotter 后端已经运行。"
    ensure_runtime_layout()
    seed_config_from_environment()
    env = os.environ.copy()
    env["CRAYOTTER_RUNTIME_ROOT"] = str(RUNTIME_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    startup_source = build_backend_startup_source(client.port)
    BACKEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = BACKEND_LOG.open("ab")
    try:
        process = subprocess.Popen(
            [sys.executable or "python", "-c", startup_source],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            env=env,
            start_new_session=True,
        )
    except Exception as exc:
        log_handle.close()
        return False, f"后端启动失败：{exc}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_handle.close()
            return False, "后端启动后退出：\n" + read_backend_log(40)
        if client.health():
            BACKEND_META.write_text(
                json.dumps(
                    {"pid": process.pid, "host": client.host, "port": client.port, "started_at": time.time()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            log_handle.close()
            return True, f"Crayotter 后端已启动（PID {process.pid}）。"
        time.sleep(1.0)
    log_handle.close()
    return False, "后端启动超时：\n" + read_backend_log(40)


def stop_backend() -> tuple[bool, str]:
    meta = _load_meta()
    pid = meta.get("pid")
    if not _pid_alive(pid):
        BACKEND_META.unlink(missing_ok=True)
        return True, "Crayotter 后端当前未运行。"
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return False, f"停止后端失败：{exc}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.25)
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError as exc:
            return False, f"强制停止后端失败：{exc}"
    BACKEND_META.unlink(missing_ok=True)
    return True, "Crayotter 后端已停止。"


def read_backend_log(lines: int = 100) -> str:
    if not BACKEND_LOG.exists():
        return "尚无后端日志。"
    return "\n".join(
        BACKEND_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    )


def runtime_diagnostics() -> dict[str, Any]:
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in ("langgraph", "openai", "dashscope", "moviepy", "cv2", "yt_dlp")
    }
    return {
        "python": sys.version.split()[0],
        "ffmpeg": shutil.which("ffmpeg") or "",
        "runtime_root": str(RUNTIME_ROOT),
        "modules": modules,
    }
