"""
草稿箱存储模块
支持保存/加载/删除/定时发送草稿
"""
import json
import os
import tempfile
from datetime import datetime

_DRAFT_DIR = None


def _get_draft_dir() -> str:
    global _DRAFT_DIR
    if _DRAFT_DIR is None:
        base = os.environ.get("CRAYOTTER_WRITABLE_DIR")
        if not base:
            base = tempfile.gettempdir()
        _DRAFT_DIR = os.path.join(base, "email_drafts")
    os.makedirs(_DRAFT_DIR, exist_ok=True)
    return _DRAFT_DIR


def _draft_path(draft_id: str) -> str:
    safe_id = draft_id.replace("/", "_").replace(" ", "_")
    return os.path.join(_get_draft_dir(), f"{safe_id}.json")


def save_draft(draft_data: dict) -> str:
    """
    保存草稿

    Args:
        draft_data: 草稿内容 dict，包含：
            - id: 草稿ID（可选，不传则自动生成）
            - name: 草稿名称
            - subject_template: 主题模板
            - body_template: 正文模板
            - sender_email: 发件邮箱
            - sender_password: 授权码
            - sender_name: 发件人名称
            - smtp_host / smtp_port / smtp_ssl: SMTP配置
            - cc: 抄送
            - bcc: 密抄
            - recipients: 收件人列表 [{name, email, ...}]
            - attachments_info: 附件信息（文件名列表）
            - scheduled_time: 定时发送时间（ISO格式字符串）
            - batch_size: 分批大小
            - batch_interval: 分批间隔分钟
            - font_size / font_color / bg_color / font_family / use_html
            - created_at: 创建时间
            - updated_at: 更新时间
            - status: draft / scheduled / sent

    Returns:
        草稿ID
    """
    draft_id = draft_data.get("id") or f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    draft_data["id"] = draft_id
    draft_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "created_at" not in draft_data:
        draft_data["created_at"] = draft_data["updated_at"]

    path = _draft_path(draft_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, ensure_ascii=False, indent=2)
    return draft_id


def load_draft(draft_id: str) -> dict:
    """加载单个草稿"""
    path = _draft_path(draft_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_drafts() -> list:
    """列出所有草稿，按更新时间倒序"""
    d = _get_draft_dir()
    drafts = []
    for fname in os.listdir(d):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    drafts.append(data)
            except (json.JSONDecodeError, IOError):
                continue
    drafts.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return drafts


def delete_draft(draft_id: str) -> bool:
    """删除草稿"""
    path = _draft_path(draft_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def update_draft_status(draft_id: str, status: str) -> bool:
    """更新草稿状态"""
    data = load_draft(draft_id)
    if data is None:
        return False
    data["status"] = status
    save_draft(data)
    return True
