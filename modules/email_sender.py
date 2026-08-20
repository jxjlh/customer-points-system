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


def _encode_filename_rfc2231(filename: str) -> str:
    """RFC 2231 规范编码文件名（用于 filename*）。"""
    import urllib.parse
    safe = urllib.parse.quote(filename, safe="!#$&+-.^_`|~")
    return f"UTF-8''{safe}"


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

    # ======================
    # 附件文件名双写（兼容所有主流客户端）
    # ======================
    # 1) filename: RFC 2047 encoded-word (Base64)
    #    —— 网易企业邮箱、QQ 邮箱、Foxmail、Windows 旧版 Outlook、国内手机邮件客户端都优先识别
    # 2) filename*: RFC 2231 percent-encoded
    #    —— Gmail / Outlook 365 / iOS 邮件 / Apple Mail 等新标准客户端优先
    # 只设置一条 Content-Disposition 头（避免重复头造成客户端选错）。
    has_non_ascii = any(ord(ch) > 127 for ch in filename)
    if has_non_ascii:
        # 强制 RFC 2047 Base64 编码（不要依赖 Header 自动选择，它有时直接回退为明文中文）
        # Header(...).encode() 保证形如 =?utf-8?b?xxxx?=
        hdr_rfc2047 = Header(filename, "utf-8", header_name="content-disposition")
        filename_rfc2047 = hdr_rfc2047.encode()  # 注意：不用 str()，强制触发 encode() 输出 =?...?=
        filename_star_rfc2231 = _encode_filename_rfc2231(filename)
        disp_value = (
            'attachment; '
            f'filename="{filename_rfc2047}"; '
            f'filename*={filename_star_rfc2231}'
        )
    else:
        safe_ascii = filename.replace('"', '\\"')
        disp_value = f'attachment; filename="{safe_ascii}"'
    if "Content-Disposition" in part:
        part.replace_header("Content-Disposition", disp_value)
    else:
        part["Content-Disposition"] = disp_value
    msg.attach(part)


def _normalize_addrs(value) -> List[str]:
    """把 逗号/换行/空格 分隔的邮箱字符串或列表，规范为纯净邮箱列表（去重、去空、保留顺序）。"""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p for p in __import__("re").split(r"[,;\s，；]+", value.strip()) if p]
    else:
        try:
            iter(value)
        except TypeError:
            return []
        parts = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                parts.extend(p for p in __import__("re").split(r"[,;\s，；]+", item.strip()) if p)
            else:
                parts.append(str(item))
    seen = set()
    result = []
    for a in parts:
        a = a.strip().strip("<>").strip()
        if not a or "@" not in a:
            continue
        low = a.lower()
        if low in seen:
            continue
        seen.add(low)
        result.append(a)
    return result


def send_single_email(
    smtp_user, smtp_password, to_addr, subject, body,
    smtp_host=None, smtp_port=None, sender_name="",
    cc_addrs=None, bcc_addrs=None, reply_to=None, attachments=None,
    max_retries=3, base_backoff_seconds=2.0,
    is_html=False, scheduled_send_time=None,
):
    """发送单封邮件，带自动重试与指数退避（防止网易企业邮箱长时间批量断开连接）。

    max_retries: 最大尝试次数（>=1），默认 3 次
    base_backoff_seconds: 重试 2 次等待 base 秒；重试 3 次等待 base*2 秒…（指数退避）
    is_html: True 时邮件体作为 HTML 发送（支持字体大小/颜色/排版）
    scheduled_send_time: datetime 对象，如果指定，函数会等待到该时间再发送
    """
    host, port, use_ssl = guess_smtp_config(smtp_user)
    if smtp_host:
        host = smtp_host
    if smtp_port:
        port = int(smtp_port)

    if max_retries < 1:
        max_retries = 1

    to_list = _normalize_addrs(to_addr)
    cc_list = _normalize_addrs(cc_addrs)
    bcc_list = _normalize_addrs(bcc_addrs)

    # 定时发送：如果指定了时间，等待到该时刻再发
    if scheduled_send_time is not None:
        from datetime import datetime as _dt
        now = _dt.now()
        if hasattr(scheduled_send_time, "timestamp"):
            wait_seconds = (scheduled_send_time - now).total_seconds()
        else:
            wait_seconds = float(scheduled_send_time)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header(sender_name or smtp_user, "utf-8")), smtp_user))
    if to_list:
        msg["To"] = ", ".join(to_list)
    msg["Subject"] = str(Header(subject, "utf-8"))
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    # 注意：Bcc 不能写在 msg 头部，否则会被收件人看到。只把 Bcc 放入 SMTP sendmail 实际收件人列表。
    if reply_to:
        msg["Reply-To"] = reply_to

    # 根据是否 HTML 选择邮件体类型
    body_subtype = "html" if is_html else "plain"
    msg.attach(MIMEText(body, body_subtype, "utf-8"))

    if attachments:
        for i, att in enumerate(attachments):
            try:
                _attach_one(msg, att, fallback_name=f"attachment_{i+1}")
            except Exception:
                pass

    # SMTP 层的所有实际收件人：To + Cc + Bcc（Bcc 不会出现在头里）
    all_recipients_raw: List[str] = list(to_list)
    all_recipients_raw.extend(cc_list)
    all_recipients_raw.extend(bcc_list)
    seen = set()
    unique_recipients = []
    for addr in all_recipients_raw:
        low = addr.lower()
        if low in seen:
            continue
        seen.add(low)
        unique_recipients.append(addr)

    if not unique_recipients:
        return {"status": "error", "message": "没有可送达的收件人地址（To/Cc/Bcc 均为空或非法）",
                "elapsed_seconds": 0,
                "to_count": len(to_list), "cc_count": len(cc_list), "bcc_count": len(bcc_list)}

    msg_text = msg.as_string()  # 提前生成一次，每次重试复用（含附件，防止重复编码）

    last_err = None
    start = time.time()
    for attempt in range(1, max_retries + 1):
        server = None
        try:
            # 每一次尝试：新连接 + 新登录，避免网易服务器因连接过长踢下线
            if use_ssl:
                ctx = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=60)
            else:
                server = smtplib.SMTP(host, port, timeout=60)
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, unique_recipients, msg_text)
            try:
                server.quit()
            except Exception:
                pass
            elapsed = round(time.time() - start, 2)
            return {
                "status": "success", "elapsed_seconds": elapsed,
                "smtp_host": host, "smtp_port": port,
                "to_count": len(to_list), "cc_count": len(cc_list), "bcc_count": len(bcc_list),
                "recipients": unique_recipients,
                "attempts": attempt,
            }
        except Exception as e:
            last_err = e
            # 尝试关闭遗留连接，避免半开连接累积
            if server is not None:
                try:
                    server.close()
                except Exception:
                    pass
            # 指数退避，最后一次不再等待
            if attempt < max_retries:
                sleep_s = base_backoff_seconds * (2 ** (attempt - 1))  # 2s -> 4s -> 8s ...
                # 常见"频控/稍后再试"类响应码再额外加一点缓冲
                msg_str = str(e).lower()
                if any(k in msg_str for k in ("421", "450", "452", "too many", "rate", "limit", "busy", "稍后")):
                    sleep_s += 3.0
                time.sleep(sleep_s)

    elapsed = round(time.time() - start, 2)
    return {"status": "error",
            "message": f"{str(last_err)}（已重试 {max_retries} 次）" if last_err else "未知错误",
            "elapsed_seconds": elapsed,
            "to_count": len(to_list), "cc_count": len(cc_list), "bcc_count": len(bcc_list),
            "attempts": max_retries}


def send_bulk_emails(
    smtp_user, smtp_password, email_list,
    smtp_host=None, smtp_port=None, sender_name="",
    delay_seconds=1.0, dry_run=True,
    global_attachments=None, global_cc=None, global_bcc=None,
    is_html=False, scheduled_send_time=None,
):
    """批量发送邮件。

    参数:
        global_attachments: 统一附加在每封邮件上的附件列表
        global_cc: 每封邮件统一抄送给这些邮箱（出现在 Cc 头）
        global_bcc: 每封邮件统一密抄送给这些邮箱（不出现在邮件头，仅 SMTP 层送达）
        is_html: True 时邮件体作为 HTML 发送（支持字体大小/颜色/排版）
        scheduled_send_time: datetime 对象，如果指定，第一封会等待到该时间再开始发送
        email_list[i]:
            可自带 "attachments" / "cc" / "bcc" / "is_html" 字段（对应字段会与全局字段合并、去重）
    """
    g_cc = _normalize_addrs(global_cc)
    g_bcc = _normalize_addrs(global_bcc)

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

        # 合并 Cc / Bcc：每封邮件独有 + 全局
        per_cc = _normalize_addrs(item.get("cc"))
        per_bcc = _normalize_addrs(item.get("bcc"))
        merged_cc = list(dict.fromkeys([*g_cc, *per_cc]))
        merged_bcc = list(dict.fromkeys([*g_bcc, *per_bcc]))

        if not to_addr and not merged_cc and not merged_bcc:
            results.append({"index": i + 1, "email": to_addr, "status": "error", "message": "收件人地址为空"})
            continue

        if dry_run:
            extra = []
            if combined: extra.append(f"附件x{len(combined)}")
            if merged_cc: extra.append(f"Cc×{len(merged_cc)}")
            if merged_bcc: extra.append(f"Bcc×{len(merged_bcc)}")
            msg_suffix = "（" + "，".join(extra) + "）" if extra else ""
            results.append({
                "index": i + 1, "email": to_addr, "name": item.get("name", ""),
                "subject": subject, "status": "success",
                "message": f"演练模式 - 未实际发送{msg_suffix}",
                "cc": merged_cc, "bcc": merged_bcc,
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
            cc_addrs=merged_cc,
            bcc_addrs=merged_bcc,
            attachments=combined,
            is_html=item.get("is_html", is_html) if isinstance(item.get("is_html"), bool) else is_html,
            scheduled_send_time=scheduled_send_time if i == 0 else None,
        )
        results.append({
            "index": i + 1,
            "email": to_addr,
            "name": item.get("name", ""),
            "subject": subject,
            "status": result["status"],
            "message": "发送成功" if result["status"] == "success" else result.get("message", ""),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "to_count": result.get("to_count", 0),
            "cc_count": result.get("cc_count", 0),
            "bcc_count": result.get("bcc_count", 0),
            "cc": merged_cc, "bcc": merged_bcc,
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
        "global_cc": g_cc,
        "global_bcc": g_bcc,
    }

