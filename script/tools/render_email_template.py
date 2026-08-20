from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ._shared import *


def _render_template(template: str, variables: dict[str, Any]) -> tuple[str, list[str]]:
    """使用变量字典渲染模板字符串，返回渲染结果和缺失的变量名列表。

    支持两种占位符语法:
    - {{变量名}}          直接替换
    - {{姓氏}} / {{姓}}   特殊别名，映射到 surname
    - {{名字}} / {{名}}   特殊别名，映射到 given_name
    - {{姓名}}           特殊别名，映射到 name
    - {{邮箱}}           特殊别名，映射到 email
    """
    alias_map = {
        "姓氏": "surname",
        "姓": "surname",
        "名字": "given_name",
        "名": "given_name",
        "姓名": "name",
        "邮箱": "email",
    }
    resolved_vars: dict[str, Any] = {}
    for k, v in variables.items():
        resolved_vars[str(k)] = "" if v is None else str(v)
    for alias, real_key in alias_map.items():
        if alias not in resolved_vars and real_key in resolved_vars:
            resolved_vars[alias] = resolved_vars[real_key]

    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        real_key = alias_map.get(key, key)
        if real_key in resolved_vars:
            return resolved_vars[real_key]
        if key in resolved_vars:
            return resolved_vars[key]
        missing.append(key)
        return match.group(0)

    pattern = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
    rendered = pattern.sub(replace, template)
    return rendered, sorted(set(missing))


@tool
def render_email_template(
    subject_template: str,
    body_template: str,
    recipients_json: str,
    body_format: str = "plain",
) -> str:
    """根据收件人列表批量渲染邮件主题和正文模板。

    模板中使用 {{变量名}} 作为占位符，例如：
      - 主题: "{{姓氏}}您好，关于您的订单通知"
      - 正文: "尊敬的{{姓名}}：\n\n感谢您的支持..."

    内置变量别名：{{姓氏}}={{姓}}=surname, {{名字}}={{名}}=given_name,
                 {{姓名}}=name, {{邮箱}}=email

    Args:
        subject_template: 邮件主题模板字符串，支持 {{变量}} 占位符。
        body_template: 邮件正文模板字符串，支持 {{变量}} 占位符。
        recipients_json: read_email_excel 返回的 recipients 列表的 JSON 字符串，
            或直接传入单个收件人 dict 的 JSON。
        body_format: 正文格式，"plain"（纯文本）或 "html"。默认 "plain"。

    Returns:
        JSON字符串，包含 rendered_emails 列表，每条包含：
        - name, email, surname, given_name
        - subject: 渲染后的主题
        - body: 渲染后的正文
        - missing_vars: 该收件人模板中缺失的变量列表
        + 其他原始字段
    """
    try:
        parsed: Any = json.loads(recipients_json) if isinstance(recipients_json, str) else recipients_json
        recipients: list[dict[str, Any]]
        if isinstance(parsed, list):
            recipients = parsed
        elif isinstance(parsed, dict):
            if "recipients" in parsed and isinstance(parsed["recipients"], list):
                recipients = parsed["recipients"]
            else:
                recipients = [parsed]
        else:
            return json.dumps({
                "status": "error",
                "message": "recipients_json 格式错误，应为列表或包含 recipients 的对象",
            }, ensure_ascii=False)

        if not recipients:
            return json.dumps({
                "status": "error",
                "message": "收件人列表为空",
            }, ensure_ascii=False)

        rendered_emails: list[dict[str, Any]] = []
        all_missing: set[str] = set()
        for rec in recipients:
            if not isinstance(rec, dict):
                continue
            subject, missing_subj = _render_template(subject_template or "", rec)
            body, missing_body = _render_template(body_template or "", rec)
            missing = sorted(set(missing_subj) | set(missing_body))
            all_missing.update(missing)
            item: dict[str, Any] = {
                **rec,
                "subject": subject,
                "body": body,
                "body_format": body_format,
                "missing_vars": missing,
            }
            rendered_emails.append(item)

        logger.info(
            "📧 模板渲染: %d封邮件, 缺失变量: %s",
            len(rendered_emails),
            sorted(all_missing) or "无",
        )
        return json.dumps({
            "status": "success",
            "count": len(rendered_emails),
            "all_missing_vars": sorted(all_missing),
            "rendered_emails": rendered_emails,
        }, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({
            "status": "error",
            "message": f"recipients_json JSON解析失败: {e}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("模板渲染失败")
        return json.dumps({
            "status": "error",
            "message": f"模板渲染出错: {e}",
        }, ensure_ascii=False)


@tool
def load_email_template_file(template_path: str) -> str:
    """从文件加载邮件主题和正文模板。

    支持两种格式：
    1. 纯文本模板文件 (.txt / .md / .html)：第一行为主题（可选，以"主题:"或"Subject:"开头），
       其余为正文；若无主题行，则整个文件为正文。
    2. JSON模板文件 (.json)：包含 "subject" 和 "body" 字段，可选 "body_format"。

    Args:
        template_path: 模板文件路径，例如 "/Users/xxx/template.txt"。

    Returns:
        JSON字符串，包含 subject, body, body_format。
    """
    try:
        resolved = Path(template_path).resolve(strict=False)
        if not resolved.exists():
            return json.dumps({
                "status": "error",
                "message": f"模板文件不存在: {template_path}",
            }, ensure_ascii=False)

        suffix = resolved.suffix.lower()
        content = resolved.read_text(encoding="utf-8")

        subject = ""
        body = content
        body_format = "html" if suffix in (".html", ".htm") else "plain"

        if suffix == ".json":
            data = json.loads(content)
            subject = str(data.get("subject", "") or "")
            body = str(data.get("body", "") or "")
            if "body_format" in data:
                body_format = str(data["body_format"]).lower()
        else:
            lines = content.splitlines()
            if lines:
                first = lines[0].strip()
                for prefix in ("主题：", "主题:", "Subject：", "Subject:", "SUBJECT：", "SUBJECT:"):
                    if first.startswith(prefix):
                        subject = first[len(prefix):].strip()
                        body = "\n".join(lines[1:]).lstrip("\n")
                        break

        logger.info("📧 加载模板: %s (主题长度:%d, 正文长度:%d, 格式:%s)",
                    str(resolved), len(subject), len(body), body_format)
        return json.dumps({
            "status": "success",
            "path": str(resolved),
            "subject": subject,
            "body": body,
            "body_format": body_format,
        }, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({
            "status": "error",
            "message": f"JSON模板解析失败: {e}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("加载模板失败")
        return json.dumps({
            "status": "error",
            "message": f"加载模板出错: {e}",
        }, ensure_ascii=False)
