from __future__ import annotations

import json
import os
import smtplib
import time
import mimetypes
import base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Any

from ._shared import *


def _guess_smtp_config(email_address: str) -> tuple[str, int, bool]:
    """根据邮箱地址猜测常见SMTP服务器配置。

    Returns (host, port, use_ssl)
    """
    domain = email_address.split("@")[-1].lower() if "@" in email_address else ""
    presets: dict[str, tuple[str, int, bool]] = {
        "qq.com": ("smtp.qq.com", 465, True),
        "vip.qq.com": ("smtp.qq.com", 465, True),
        "foxmail.com": ("smtp.qq.com", 465, True),
        "163.com": ("smtp.163.com", 465, True),
        "126.com": ("smtp.126.com", 465, True),
        "yeah.net": ("smtp.yeah.net", 465, True),
        "vip.163.com": ("smtp.vip.163.com", 465, True),
        "gmail.com": ("smtp.gmail.com", 465, True),
        "outlook.com": ("smtp-mail.outlook.com", 587, False),
        "hotmail.com": ("smtp-mail.outlook.com", 587, False),
        "live.com": ("smtp-mail.outlook.com", 587, False),
        "icloud.com": ("smtp.mail.me.com", 587, False),
        "sina.com": ("smtp.sina.com", 465, True),
        "sina.cn": ("smtp.sina.cn", 465, True),
        "sohu.com": ("smtp.sohu.com", 465, True),
        "21cn.com": ("smtp.21cn.com", 465, True),
        "189.cn": ("smtp.189.cn", 465, True),
        "139.com": ("smtp.139.com", 465, True),
        "aliyun.com": ("smtp.aliyun.com", 465, True),
        "exmail.qq.com": ("smtp.exmail.qq.com", 465, True),
        "mxhichina.com": ("smtp.mxhichina.com", 465, True),
    }
    if domain in presets:
        return presets[domain]
    # 企业邮箱/未知域名，返回通用默认值
    return (f"smtp.{domain}", 465, True)


@tool
def test_smtp_connection(
    smtp_user: str,
    smtp_password: str,
    smtp_host: str = "",
    smtp_port: int = 0,
    use_ssl: bool | str = "auto",
    sender_name: str = "",
) -> str:
    """测试SMTP邮箱登录连接是否成功。

    支持QQ邮箱、163邮箱、Gmail、Outlook等常见邮箱，大部分需要使用「授权码」而非登录密码。

    Args:
        smtp_user: 完整邮箱地址，例如 "yourname@qq.com"。
        smtp_password: SMTP授权码（不是邮箱登录密码，需要在邮箱设置中开启SMTP并生成授权码）。
        smtp_host: SMTP服务器地址，留空则根据邮箱自动猜测。
        smtp_port: SMTP端口，留空则根据邮箱自动猜测（通常SSL=465, STARTTLS=587）。
        use_ssl: 是否使用SSL加密，"auto"/true/false。默认"auto"按猜测配置。
        sender_name: 发件人显示名称，可选。

    Returns:
        JSON字符串，包含连接测试结果和检测到的SMTP配置。
    """
    try:
        smtp_user = smtp_user.strip()
        if not smtp_user or "@" not in smtp_user:
            return json.dumps({
                "status": "error",
                "message": "邮箱地址格式错误",
            }, ensure_ascii=False)

        guessed_host, guessed_port, guessed_ssl = _guess_smtp_config(smtp_user)
        host = smtp_host.strip() or guessed_host
        port = int(smtp_port) if smtp_port else guessed_port
        if isinstance(use_ssl, bool):
            ssl_enabled = use_ssl
        else:
            us = str(use_ssl).strip().lower()
            ssl_enabled = guessed_ssl if us in ("auto", "", "none") else us not in ("0", "false", "no", "off")

        if not host:
            return json.dumps({
                "status": "error",
                "message": "无法猜测SMTP服务器，请手动指定 smtp_host",
            }, ensure_ascii=False)

        start = time.time()
        if ssl_enabled:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        try:
            server.login(smtp_user, smtp_password)
        finally:
            try:
                server.quit()
            except Exception:
                pass

        elapsed = round(time.time() - start, 2)
        display_sender = formataddr((str(Header(sender_name or smtp_user.split("@")[0], "utf-8")), smtp_user))
        logger.info("📧 SMTP连接成功: %s via %s:%d (SSL=%s) 耗时%.2fs",
                    smtp_user, host, port, ssl_enabled, elapsed)
        return json.dumps({
            "status": "success",
            "message": "SMTP登录成功，可以发送邮件",
            "smtp_user": smtp_user,
            "smtp_host": host,
            "smtp_port": port,
            "use_ssl": ssl_enabled,
            "sender_display": display_sender,
            "elapsed_seconds": elapsed,
        }, ensure_ascii=False, indent=2)
    except smtplib.SMTPAuthenticationError as e:
        return json.dumps({
            "status": "error",
            "message": f"SMTP认证失败: {e}. 请确认是否使用邮箱的「授权码」而非登录密码，且已在邮箱设置中开启SMTP服务。",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("SMTP连接测试失败")
        return json.dumps({
            "status": "error",
            "message": f"SMTP连接出错: {e}",
        }, ensure_ascii=False)


def _attach_files(msg: MIMEMultipart, attachments: list[str]) -> list[str]:
    """为邮件消息添加附件，返回处理的附件文件名列表。"""
    attached: list[str] = []
    for raw_path in attachments or []:
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.exists() or not path.is_file():
            continue
        ctype, _ = mimetypes.guess_type(str(path))
        if ctype is None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(path, "rb") as f:
            payload = f.read()
        part = MIMEBase(maintype, subtype)
        part.set_payload(payload)
        part.add_header("Content-Transfer-Encoding", "base64")
        try:
            filename_encoded = path.name.encode("utf-8")
            filename_header = "=?utf-8?b?" + base64.b64encode(filename_encoded).decode("ascii") + "?="
        except Exception:
            filename_header = path.name
        part.add_header("Content-Disposition", "attachment", filename=filename_header)
        msg.attach(part)
        attached.append(str(path))
    return attached


@tool
def send_single_email(
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    subject: str,
    body: str,
    smtp_host: str = "",
    smtp_port: int = 0,
    use_ssl: bool | str = "auto",
    sender_name: str = "",
    body_format: str = "plain",
    cc_email: str = "",
    bcc_email: str = "",
    reply_to: str = "",
    attachments_json: str = "[]",
) -> str:
    """发送单封邮件。

    Args:
        smtp_user: 完整发件邮箱地址。
        smtp_password: SMTP授权码。
        to_email: 收件人邮箱地址，多个用逗号分隔。
        subject: 邮件主题。
        body: 邮件正文。
        smtp_host: SMTP服务器，留空自动猜测。
        smtp_port: SMTP端口，留空自动猜测。
        use_ssl: 是否使用SSL，"auto"/true/false。
        sender_name: 发件人显示名称。
        body_format: 正文格式 "plain" 或 "html"。
        cc_email: 抄送邮箱，多个用逗号分隔。
        bcc_email: 密送邮箱，多个用逗号分隔。
        reply_to: 回复地址。
        attachments_json: 附件路径列表的JSON字符串，例如 '["/path/a.pdf"]'。

    Returns:
        JSON字符串，发送结果。
    """
    try:
        smtp_user = smtp_user.strip()
        to_emails = [e.strip() for e in (to_email or "").split(",") if e.strip()]
        cc_emails = [e.strip() for e in (cc_email or "").split(",") if e.strip()]
        bcc_emails = [e.strip() for e in (bcc_email or "").split(",") if e.strip()]
        all_rcpts = to_emails + cc_emails + bcc_emails

        if not smtp_user or "@" not in smtp_user:
            return json.dumps({"status": "error", "message": "发件邮箱格式错误"}, ensure_ascii=False)
        if not to_emails or any("@" not in e for e in to_emails):
            return json.dumps({"status": "error", "message": "收件邮箱格式错误"}, ensure_ascii=False)

        guessed_host, guessed_port, guessed_ssl = _guess_smtp_config(smtp_user)
        host = smtp_host.strip() or guessed_host
        port = int(smtp_port) if smtp_port else guessed_port
        if isinstance(use_ssl, bool):
            ssl_enabled = use_ssl
        else:
            us = str(use_ssl).strip().lower()
            ssl_enabled = guessed_ssl if us in ("auto", "", "none") else us not in ("0", "false", "no", "off")

        if body_format and str(body_format).lower() == "html":
            mime_subtype = "html"
        else:
            mime_subtype = "plain"

        try:
            attachment_paths: list[str] = json.loads(attachments_json) if attachments_json else []
        except Exception:
            attachment_paths = []

        has_attachments = bool(attachment_paths)
        if has_attachments:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body or "", mime_subtype, "utf-8"))
        else:
            msg = MIMEText(body or "", mime_subtype, "utf-8")

        msg["From"] = formataddr((str(Header(sender_name or smtp_user.split("@")[0], "utf-8")), smtp_user))
        msg["To"] = ", ".join(to_emails)
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg["Subject"] = Header(subject or "(无主题)", "utf-8")
        if reply_to and "@" in reply_to:
            msg["Reply-To"] = reply_to

        attached_files: list[str] = []
        if has_attachments:
            attached_files = _attach_files(msg, attachment_paths)  # type: ignore[arg-type]

        start = time.time()
        if ssl_enabled:
            server = smtplib.SMTP_SSL(host, port, timeout=60)
        else:
            server = smtplib.SMTP(host, port, timeout=60)
            server.starttls()
        try:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, all_rcpts, msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass

        elapsed = round(time.time() - start, 2)
        logger.info("📧 邮件已发送: %s -> %s [主题: %s] 附件:%d 耗时%.2fs",
                    smtp_user, to_emails[0], subject[:30], len(attached_files), elapsed)
        return json.dumps({
            "status": "success",
            "message": "邮件发送成功",
            "from": smtp_user,
            "to": to_emails,
            "cc": cc_emails,
            "bcc_count": len(bcc_emails),
            "subject": subject,
            "attachments": attached_files,
            "elapsed_seconds": elapsed,
        }, ensure_ascii=False, indent=2)
    except smtplib.SMTPAuthenticationError as e:
        return json.dumps({
            "status": "error",
            "message": f"SMTP认证失败: {e}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("发送单封邮件失败")
        return json.dumps({
            "status": "error",
            "message": f"发送邮件出错: {e}",
        }, ensure_ascii=False)


@tool
def send_bulk_emails(
    smtp_user: str,
    smtp_password: str,
    rendered_emails_json: str,
    smtp_host: str = "",
    smtp_port: int = 0,
    use_ssl: bool | str = "auto",
    sender_name: str = "",
    cc_email: str = "",
    bcc_email: str = "",
    reply_to: str = "",
    delay_seconds: float = 1.0,
    stop_on_error: bool = False,
    dry_run: bool = False,
) -> str:
    """批量发送邮件，输入为 render_email_template 输出的 rendered_emails JSON列表。

    每封邮件之间会有间隔以避免被邮件服务商限流。

    Args:
        smtp_user: 完整发件邮箱地址。
        smtp_password: SMTP授权码。
        rendered_emails_json: render_email_template 返回的 rendered_emails 列表 JSON。
        smtp_host: SMTP服务器，留空自动猜测。
        smtp_port: SMTP端口，留空自动猜测。
        use_ssl: 是否使用SSL，"auto"/true/false。
        sender_name: 发件人显示名称。
        cc_email: 每封邮件统一的抄送邮箱。
        bcc_email: 每封邮件统一的密送邮箱。
        reply_to: 每封邮件统一的回复地址。
        delay_seconds: 每封邮件之间的间隔秒数，默认1秒。
        stop_on_error: 遇到错误时是否立即停止，默认false继续下一封。
        dry_run: 是否为演练模式（不实际发送，仅验证流程），默认false。

    Returns:
        JSON字符串，包含 success_count、failed_count、results 详细列表。
    """
    try:
        parsed = json.loads(rendered_emails_json) if isinstance(rendered_emails_json, str) else rendered_emails_json
        emails: list[dict[str, Any]]
        if isinstance(parsed, list):
            emails = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("rendered_emails"), list):
            emails = parsed["rendered_emails"]
        else:
            return json.dumps({
                "status": "error",
                "message": "rendered_emails_json 格式错误，应为列表或包含 rendered_emails 字段的对象",
            }, ensure_ascii=False)

        if not emails:
            return json.dumps({
                "status": "error",
                "message": "待发送邮件列表为空",
            }, ensure_ascii=False)

        smtp_user = smtp_user.strip()
        if not smtp_user or "@" not in smtp_user:
            return json.dumps({"status": "error", "message": "发件邮箱格式错误"}, ensure_ascii=False)

        guessed_host, guessed_port, guessed_ssl = _guess_smtp_config(smtp_user)
        host = smtp_host.strip() or guessed_host
        port = int(smtp_port) if smtp_port else guessed_port
        if isinstance(use_ssl, bool):
            ssl_enabled = use_ssl
        else:
            us = str(use_ssl).strip().lower()
            ssl_enabled = guessed_ssl if us in ("auto", "", "none") else us not in ("0", "false", "no", "off")

        results: list[dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        server = None
        login_done = False

        total = len(emails)
        logger.info("📧 开始批量发送邮件: 共%d封, 间隔%.1fs, 演练模式=%s",
                    total, delay_seconds, dry_run)

        try:
            if not dry_run:
                if ssl_enabled:
                    server = smtplib.SMTP_SSL(host, port, timeout=60)
                else:
                    server = smtplib.SMTP(host, port, timeout=60)
                    server.starttls()
                server.login(smtp_user, smtp_password)
                login_done = True

            for idx, item in enumerate(emails, start=1):
                to_email = str(item.get("email", "")).strip()
                subject = str(item.get("subject", "(无主题)"))
                body = str(item.get("body", ""))
                body_format = str(item.get("body_format") or "plain").lower()
                extra_attachments = item.get("attachments") or []
                if isinstance(extra_attachments, str):
                    try:
                        extra_attachments = json.loads(extra_attachments)
                    except Exception:
                        extra_attachments = []

                item_result: dict[str, Any] = {
                    "index": idx,
                    "email": to_email,
                    "name": item.get("name", ""),
                    "subject": subject,
                }

                if not to_email or "@" not in to_email:
                    failed_count += 1
                    item_result["status"] = "error"
                    item_result["message"] = "收件邮箱格式错误或缺失"
                    results.append(item_result)
                    if stop_on_error:
                        break
                    continue

                try:
                    if dry_run:
                        item_result["status"] = "success"
                        item_result["message"] = "演练模式：未实际发送"
                        success_count += 1
                    else:
                        to_emails = [to_email]
                        cc_emails = [e.strip() for e in (cc_email or "").split(",") if e.strip()]
                        bcc_emails = [e.strip() for e in (bcc_email or "").split(",") if e.strip()]
                        all_rcpts = to_emails + cc_emails + bcc_emails

                        has_attachments = bool(extra_attachments)
                        if has_attachments:
                            msg = MIMEMultipart()
                            msg.attach(MIMEText(body, "html" if body_format == "html" else "plain", "utf-8"))
                        else:
                            msg = MIMEText(body, "html" if body_format == "html" else "plain", "utf-8")

                        msg["From"] = formataddr((
                            str(Header(sender_name or smtp_user.split("@")[0], "utf-8")),
                            smtp_user,
                        ))
                        msg["To"] = ", ".join(to_emails)
                        if cc_emails:
                            msg["Cc"] = ", ".join(cc_emails)
                        msg["Subject"] = Header(subject, "utf-8")
                        if reply_to and "@" in reply_to:
                            msg["Reply-To"] = reply_to

                        attached_files = _attach_files(msg, extra_attachments) if has_attachments else []  # type: ignore[arg-type]

                        assert server is not None
                        server.sendmail(smtp_user, all_rcpts, msg.as_string())

                        item_result["status"] = "success"
                        item_result["message"] = "发送成功"
                        item_result["attachments"] = attached_files
                        success_count += 1

                    logger.info("  [%d/%d] %s -> %s  %s",
                                idx, total, "✓" if item_result["status"] == "success" else "✗",
                                to_email, subject[:40])
                except Exception as mail_err:
                    failed_count += 1
                    item_result["status"] = "error"
                    item_result["message"] = str(mail_err)
                    results.append(item_result)
                    logger.warning("  [%d/%d] ✗ 发送失败: %s -> %s", idx, total, to_email, mail_err)
                    if stop_on_error:
                        break
                    results.append(item_result)
                    if delay_seconds > 0 and idx < total:
                        time.sleep(delay_seconds)
                    continue

                results.append(item_result)
                if delay_seconds > 0 and idx < total and not (stop_on_error and failed_count > 0):
                    time.sleep(delay_seconds)
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

        logger.info("📧 批量发送完成: 成功%d, 失败%d / 共%d", success_count, failed_count, total)
        return json.dumps({
            "status": "success" if success_count > 0 else ("error" if failed_count == total else "partial"),
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "smtp_host": host,
            "smtp_port": port,
            "use_ssl": ssl_enabled,
            "login_ok": login_done or dry_run,
            "dry_run": dry_run,
            "results": results,
        }, ensure_ascii=False, indent=2)
    except smtplib.SMTPAuthenticationError as e:
        return json.dumps({
            "status": "error",
            "message": f"SMTP认证失败: {e}",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("批量发送邮件失败")
        return json.dumps({
            "status": "error",
            "message": f"批量发送出错: {e}",
            "total": len(parsed) if "parsed" in locals() else 0,
            "success_count": 0,
            "failed_count": 0,
        }, ensure_ascii=False)
