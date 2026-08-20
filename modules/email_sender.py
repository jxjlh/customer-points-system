import smtplib
import time
import ssl
import os
import io
import mimetypes
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from email import encoders
from typing import Any, Union, List, Tuple, Optional


def guess_smtp_config(email_address: str) -> tuple:
    domain = email_address.split("@")[-1].lower() if "@" in email_address else ""
    presets = {
        "qq.com": ("smtp.qq.com", 465, True),
        "vip.qq.com": ("smtp.qq.com", 465, True),
        "foxmail.com": ("smtp.qq.com", 465, True),
        "163.com": ("smtp.163.com", 465, True),
        "126.com": ("smtp.126.com", 465, True),
        "yeah.net": ("smtp.yeah.net", 465, True),
        "gmail.com": ("smtp.gmail.com", 465, True),
        "outlook.com": ("smtp-mail.outlook.com", 587, False),
        "icloud.com": ("smtp.mail.me.com", 587, False),
        "sina.com": ("smtp.sina.com", 465, True),
        "sina.cn": ("smtp.sina.cn", 465, True),
        "sohu.com": ("smtp.sohu.com", 465, True),
        "139.com": ("smtp.139.com", 465, True),
        "aliyun.com": ("smtp.aliyun.com", 465, True),
        "exmail.qq.com": ("smtp.exmail.qq.com", 465, True),
    }
    if domain in presets:
        return presets[domain]
    # 网易企业邮箱（自定义域名）：smtp.qiye.163.com
    # 腾讯企业邮箱（自定义域名）：smtp.exmail.qq.com
    # 阿里企业邮箱（自定义域名）：smtp.mxhichina.com
    # 已知客户域名硬编码映射
    known_corp_domains = {
        # 网易企业邮箱客户域名
        "ibiologistics.com": ("smtp.qiye.163.com", 465, True),
    }
    if domain in known_corp_domains:
        return known_corp_domains[domain]
    return (f"smtp.{domain}", 465, True)


def list_smtp_candidates(email_address: str) -> list:
    """返回常见企业邮箱候选列表，用于连接失败时逐一尝试或提示用户选择。"""
    domain = email_address.split("@")[-1].lower() if "@" in email_address else ""
    host, port, ssl = guess_smtp_config(email_address)
    candidates = [(host, port, ssl, "自动识别")]
    if domain not in {
        "qq.com", "vip.qq.com", "foxmail.com", "163.com", "126.com",
        "yeah.net", "gmail.com", "outlook.com", "icloud.com", "sina.com",
        "sina.cn", "sohu.com", "139.com", "aliyun.com", "exmail.qq.com",
        "ibiologistics.com",
    }:
        candidates.append(("smtp.qiye.163.com", 465, True, "网易企业邮箱"))
        candidates.append(("smtp.exmail.qq.com", 465, True, "腾讯企业邮箱"))
        candidates.append(("smtp.mxhichina.com", 465, True, "阿里企业邮箱"))
    return candidates


def test_smtp_connection(smtp_user, smtp_password, smtp_host=None, smtp_port=None):
    host, port, use_ssl = guess_smtp_config(smtp_user)
    if smtp_host:
        host = smtp_host
    if smtp_port:
        port = int(smtp_port)

    start = time.time()
    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.quit()
        elapsed = round(time.time() - start, 2)
        return {"status": "success", "smtp_host": host, "smtp_port": port, "use_ssl": use_ssl, "elapsed_seconds": elapsed}
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {"status": "error", "message": str(e), "smtp_host": host, "smtp_port": port, "elapsed_seconds": elapsed}


def _encode_filename(filename: str) -> str:
    """RFC 2231 规范编码附件文件名，兼容中文/特殊字符，避免被网关降级为 .bin。"""
    import urllib.parse
    safe = urllib.parse.quote(filename, safe="!#$&+-.^_`|~")
    return f"filename*=UTF-8''{safe}"


def _attach_one(msg: MIMEMultipart, att: Any, fallback_name: str = "") -> None:
    """把单个附件附加到 MIMEMultipart。

    支持的附件输入格式：
    1. str: 本地文件路径
    2. tuple(bytes | BytesIO, filename): 内存数据+文件名
    3. dict: {"name": 文件名, "data": bytes/BytesIO/路径, "content_type": 可选}
    4. bytes: 纯字节（fallback_name 须提供）
    5. BytesIO / file-like: 有 .name 属性则取之，否则用 fallback_name
    """
    data: bytes = b""
    filename: str = fallback_name or "attachment"
    content_type: Optional[str] = None

    if isinstance(att, str):
        if not os.path.isfile(att):
            return
        filename = os.path.basename(att)
        with open(att, "rb") as f:
            data = f.read()
        content_type, _ = mimetypes.guess_type(att)
    elif isinstance(att, (tuple, list)) and len(att) >= 2:
        payload, fn = att[0], att[1]
        filename = str(fn) if fn else (fallback_name or "attachment")
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        elif isinstance(payload, io.IOBase) or hasattr(payload, "read"):
            if hasattr(payload, "seek"):
                try: payload.seek(0)
                except Exception: pass
            data = payload.read()
        else:
            data = str(payload).encode("utf-8")
        content_type, _ = mimetypes.guess_type(filename)
        if len(att) >= 3 and att[2]:
            content_type = str(att[2])
    elif isinstance(att, dict):
        filename = str(att.get("name") or fallback_name or "attachment")
        payload = att.get("data", b"")
        if isinstance(payload, str) and os.path.isfile(payload):
            with open(payload, "rb") as f:
                data = f.read()
        elif isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        elif isinstance(payload, io.IOBase) or hasattr(payload, "read"):
            if hasattr(payload, "seek"):
                try: payload.seek(0)
                except Exception: pass
            data = payload.read()
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
        if att.get("content_type"):
            content_type = str(att["content_type"])
        else:
            content_type, _ = mimetypes.guess_type(filename)
    elif isinstance(att, (bytes, bytearray)):
        data = bytes(att)
        filename = fallback_name or "attachment"
        content_type, _ = mimetypes.guess_type(filename)
    elif isinstance(att, io.IOBase) or hasattr(att, "read"):
        name = getattr(att, "name", "") or fallback_name or "attachment"
        filename = os.path.basename(str(name)) or (fallback_name or "attachment")
        if hasattr(att, "seek"):
            try: att.seek(0)
            except Exception: pass
        data = att.read()
        content_type, _ = mimetypes.guess_type(filename)

    if not data:
        return

    # 按 MIME 选择附件类型
    main, sub = "application", "octet-stream"
    if content_type:
        parts = content_type.split("/", 1)
        if len(parts) == 2 and parts[0]:
            main, sub = parts[0].lower(), parts[1].lower() or "octet-stream"

    # 对 application/* 用 MIMEApplication（规范的 _subtype）
    if main == "application":
        part = MIMEApplication(data, _subtype=sub or "octet-stream")
    else:
        part = MIMEBase(main, sub)
        part.set_payload(data)
        encoders.encode_base64(part)

    # 规范的 Content-Disposition：同时写 filename 和 RFC 2231 filename*
    # 双写可兼容不支持 RFC 2231 的旧客户端，中文不会变 .bin
    safe_ascii = "".join(c if ord(c) < 128 and c not in ' \t"\\;:/<>*?' else "_" for c in filename)
    disposition = f'attachment; filename="{safe_ascii}"; {_encode_filename(filename)}'
    part["Content-Disposition"] = disposition
    msg.attach(part)


def send_single_email(
    smtp_user, smtp_password, to_addr, subject, body,
    smtp_host=None, smtp_port=None, sender_name="",
    cc_addrs=None, reply_to=None, attachments=None,
):
    host, port, use_ssl = guess_smtp_config(smtp_user)
    if smtp_host:
        host = smtp_host
    if smtp_port:
        port = int(smtp_port)

    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header(sender_name or smtp_user, "utf-8")), smtp_user))
    msg["To"] = to_addr
    msg["Subject"] = str(Header(subject, "utf-8"))
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachments:
        for i, att in enumerate(attachments):
            try:
                _attach_one(msg, att, fallback_name=f"attachment_{i+1}")
            except Exception:
                pass

    start = time.time()
    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        server.login(smtp_user, smtp_password)
        all_recipients = [to_addr]
        if cc_addrs:
            all_recipients.extend(cc_addrs)
        server.sendmail(smtp_user, all_recipients, msg.as_string())
        server.quit()
        elapsed = round(time.time() - start, 2)
        return {"status": "success", "elapsed_seconds": elapsed, "smtp_host": host, "smtp_port": port}
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {"status": "error", "message": str(e), "elapsed_seconds": elapsed}


def send_bulk_emails(
    smtp_user, smtp_password, email_list,
    smtp_host=None, smtp_port=None, sender_name="",
    delay_seconds=1.0, dry_run=True,
    global_attachments=None,
):
    """批量发送邮件。

    参数:
        global_attachments: 统一附加在每封邮件上的附件列表
            支持 str（路径）/ tuple(data,name) / dict / bytes / BytesIO
        email_list[i]:
            可自带 "attachments" 字段，作为该邮件独有的附件（与 global_attachments 合并）
    """
    results = []
    for i, item in enumerate(email_list):
        item = dict(item) if isinstance(item, dict) else {"email": str(item)}
        to_addr = item.get("email", "").strip()
        subject = item.get("subject", "")
        body = item.get("body", "")

        # 合并附件：每封邮件独有 + 全局公共附件
        per_attachs = item.get("attachments") or []
        combined: list = []
        if isinstance(per_attachs, list):
            combined.extend(per_attachs)
        else:
            combined.append(per_attachs)
        if global_attachments:
            if isinstance(global_attachments, list):
                combined.extend(global_attachments)
            else:
                combined.append(global_attachments)
        combined = [a for a in combined if a is not None] or None

        if not to_addr:
            results.append({"index": i + 1, "email": to_addr, "status": "error", "message": "邮箱地址为空"})
            continue

        if dry_run:
            results.append({
                "index": i + 1, "email": to_addr, "name": item.get("name", ""),
                "subject": subject, "status": "success",
                "message": "演练模式 - 未实际发送" + (f"（附件x{len(combined or [])}）" if combined else ""),
            })
            continue

        result = send_single_email(
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            to_addr=to_addr,
            subject=subject,
            body=body,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            sender_name=sender_name,
            attachments=combined,
        )
        results.append({
            "index": i + 1,
            "email": to_addr,
            "name": item.get("name", ""),
            "subject": subject,
            "status": result["status"],
            "message": "发送成功" if result["status"] == "success" else result.get("message", ""),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        })

        if not dry_run and i < len(email_list) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] != "success")

    return {
        "status": "success" if failed_count == 0 or dry_run else "partial",
        "total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
        "smtp_host": guess_smtp_config(smtp_user)[0],
        "smtp_port": guess_smtp_config(smtp_user)[1],
    }

