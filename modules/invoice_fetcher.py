import email
import html
import imaplib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_CONFIG = {
    "imap_server": "imap.qiye.163.com",
    "imap_port": 993,
    "email": "",
    "password": "",
    "sender": "百旺金穗云dzfpfwpt@hnfapiao.com",
    "subject_filter": "开具的发票",
    "output_dir": r"C:\Users\Admin\Downloads\发票汇总",
    "days_back": 5,
    "base_url": "https://dzfpfwpt.hnfapiao.com",
    "state_file": "",
}

ILLEGAL_FILENAME_CHARS = r'\\/:*?"<>|'


def sanitize_filename(name: str, max_len: int = 60) -> str:
    if not name:
        return ""
    name = html.unescape(name).strip()
    for ch in ILLEGAL_FILENAME_CHARS:
        name = name.replace(ch, "_")
    name = re.sub(r"\s+", "", name)
    name = name.strip("._")
    return name[:max_len]


def decode_mime(s):
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def parse_email_date(msg) -> str:
    raw = msg.get("Date")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt is not None:
                try:
                    dt = dt.astimezone()
                except Exception:
                    pass
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return time.strftime("%Y-%m-%d")


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._cur_href = None
        self._cur_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            d = dict(attrs)
            self._cur_href = d.get("href")
            self._cur_text = []

    def handle_data(self, data):
        if self._cur_href is not None:
            self._cur_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._cur_href is not None:
            self.links.append((self._cur_href, "".join(self._cur_text)))
            self._cur_href = None
            self._cur_text = []


def find_pdf_link(html_body: str, base_url: str):
    if not html_body:
        return None

    m = re.search(r'(?:href|HREF)\s*=\s*["\']([^"\']*exportDzfpwjEwm[^"\']*Wjgs=PDF[^"\']*)["\']',
                  html_body, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:href|HREF)\s*=\s*["\']([^"\']*Wjgs=PDF[^"\']*)["\']', html_body, re.I)
    if m:
        return m.group(1).strip()

    parser = LinkExtractor()
    try:
        parser.feed(html_body)
    except Exception:
        return None

    candidates = []
    for href, text in parser.links:
        if not href:
            continue
        t = (text or "").lower()
        h = href.lower()
        score = 0
        if "下载" in text or "download" in t:
            score += 2
        if "pdf" in t or ".pdf" in h or "pdf" in h:
            score += 3
        if "invoice" in h or "fp" in h or "dzfp" in h:
            score += 1
        if score >= 2:
            candidates.append((score, href))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]
    return urllib.parse.urljoin(base_url, best)


def html_to_text(html_body: str) -> str:
    if not html_body:
        return ""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return html.unescape(body)


def extract_field(text: str, patterns):
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return ""


BUYER_PATTERNS = [
    r"购方名称[：:]\s*([^\s,，。；;]{2,40})",
    r"购买方名称[：:]\s*([^\s,，。；;]{2,40})",
    r"抬头[：:]\s*([^\s,，。；;]{2,40})",
    r"名称[：:]\s*([^\s,，。；;]{2,40})",
]

AMOUNT_PATTERNS = [
    r"金额合计[：:]\s*([-+]?[0-9][0-9,]*\.?[0-9]*\s*元?)",
    r"价税合计[：:]\s*([-+]?[0-9][0-9,]*\.?[0-9]*\s*元?)",
    r"合计金额[：:]\s*([-+]?[0-9][0-9,]*\.?[0-9]*\s*元?)",
    r"金额[：:]\s*([-+]?[0-9][0-9,]*\.?[0-9]*\s*元?)",
]


def build_amount(amount_raw: str, has_yuan: bool) -> str:
    if not amount_raw:
        return ""
    s = amount_raw.replace(",", "").strip()
    sign = "-" if s.startswith("-") else ("+" if s.startswith("+") else "")
    digits = re.sub(r"[^\d.]", "", s)
    if not digits:
        return ""
    try:
        float((sign + digits) if sign else digits)
    except ValueError:
        return ""
    return (sign + digits) + ("元" if has_yuan else "")


def download_pdf(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36",
            "Accept": "application/pdf,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data


def is_pdf(data: bytes) -> bool:
    return data[:5].upper() == b"%PDF-"


def load_state(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(path: Path, state: dict):
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_one(msg_bytes: bytes, cfg: dict, base_url: str):
    msg = email.message_from_bytes(msg_bytes)
    subject = decode_mime(msg.get("Subject", ""))
    date_str = parse_email_date(msg)
    html_body = None
    plain_text = ""
    attachment = None
    attachment_name = None

    for part in msg.walk():
        ctype = part.get_content_type()
        disp = (part.get("Content-Disposition") or "").lower()
        if ctype == "text/html" and html_body is None:
            payload = part.get_payload(decode=True) or b""
            html_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        elif ctype == "text/plain" and not plain_text:
            payload = part.get_payload(decode=True) or b""
            plain_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if "attachment" in disp or part.get_filename():
            fname = part.get_filename()
            if fname and fname.lower().endswith(".pdf"):
                attachment = part.get_payload(decode=True)
                attachment_name = fname

    text_for_parse = html_to_text(html_body) if html_body else plain_text

    if attachment and is_pdf(attachment):
        buyer = extract_field(text_for_parse, BUYER_PATTERNS)
        am = extract_field(text_for_parse, AMOUNT_PATTERNS)
        has_yuan = "元" in am
        amount = build_amount(am, has_yuan)
        return attachment, buyer, amount, subject, date_str, "attachment"

    url = find_pdf_link(html_body, base_url)
    if url:
        try:
            data = download_pdf(url)
        except Exception as e:
            return None, f"下载失败 {url}: {e}"
        if is_pdf(data):
            buyer = extract_field(text_for_parse, BUYER_PATTERNS)
            am = extract_field(text_for_parse, AMOUNT_PATTERNS)
            has_yuan = "元" in am
            amount = build_amount(am, has_yuan)
            return data, buyer, amount, subject, date_str, "link"
        else:
            return None, "链接返回内容不是 PDF"
    return None, "未找到 PDF 链接"


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def imap_since_date(days_back: int) -> str:
    import datetime
    d = datetime.date.today() - datetime.timedelta(days=max(0, days_back))
    return f"{d.strftime('%d-')}{MONTHS[d.month - 1]}{d.strftime('-%Y')}"


class InvoiceFetcher:
    def __init__(self, config=None, db_manager=None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self._db = db_manager

    def fetch_invoices(self, days=None, dry_run=False):
        server = self.config["imap_server"]
        port = int(self.config.get("imap_port", 993))
        results = []

        try:
            imap = imaplib.IMAP4_SSL(server, port)
            imap.login(self.config["email"], self.config["password"])
        except Exception as e:
            return None, f"登录失败: {str(e)}"

        try:
            ok, raw_folders = imap.list()
            folder_names = []
            if ok == "OK" and raw_folders:
                for f in raw_folders:
                    raw = f if isinstance(f, str) else f.decode(errors="replace")
                    m = re.findall(r'"([^"]*)"', raw)
                    if m:
                        folder_names.append(m[-1])
            if not folder_names:
                folder_names = ["INBOX"]

            out_dir = Path(self.config["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)

            state_path = Path(self.config.get("state_file") or (Path(__file__).parent.parent / "database" / "invoice_state.json"))
            state = load_state(state_path)
            processed_set = set(state.get("processed", []))

            # 新增：从数据库加载已处理 UID（优先）
            if self._db and hasattr(self._db, 'get_processed_invoice_uids'):
                try:
                    db_uids = self._db.get_processed_invoice_uids()
                    processed_set = processed_set | db_uids
                except Exception:
                    pass

            total_new = 0
            failed_count = 0

            for folder in folder_names:
                try:
                    imap.select(folder, readonly=True)
                except Exception:
                    continue

                search_days = days if days is not None else int(self.config.get("days_back", 5))
                typ, data = imap.search(None, "SINCE", imap_since_date(search_days))
                if typ != "OK":
                    continue

                uids = data[0].split() if data and data[0] else []
                if not uids:
                    continue

                subject_filter = (self.config.get("subject_filter") or "").strip()
                sender_filter = (self.config.get("sender") or "").strip()

                for uid in uids:
                    ukey = f"{folder}:{uid.decode() if isinstance(uid, bytes) else str(uid)}"
                    if ukey in processed_set:
                        continue

                    try:
                        ok2, msg_data = imap.fetch(uid, "(RFC822)")
                    except Exception:
                        ok2, msg_data = None, None

                    if not ok2 or not msg_data:
                        continue

                    raw = None
                    for block in msg_data:
                        if isinstance(block, tuple):
                            raw = block[1]

                    if not raw:
                        continue

                    probe = email.message_from_bytes(raw)
                    subj = decode_mime(probe.get("Subject", ""))
                    frm = probe.get("From", "")

                    is_invoice = (subject_filter and subject_filter in subj) or \
                                 (sender_filter and sender_filter in frm)

                    if not is_invoice:
                        continue

                    result = fetch_one(raw, self.config, self.config.get("base_url", ""))
                    if result[0] is None:
                        processed_set.add(ukey)
                        failed_count += 1
                        fail_record = {
                            "status": "failed",
                            "subject": subj,
                            "date": parse_email_date(probe),
                            "folder": folder,
                            "reason": result[1] if len(result) > 1 else "未找到可下载的 PDF",
                            "email_uid": ukey,
                        }
                        results.append(fail_record)
                        # 新增：失败记录也保存到数据库
                        if self._db and not dry_run:
                            try:
                                self._db.add_invoice_record(fail_record)
                            except Exception:
                                pass
                        continue

                    pdf_bytes, buyer, amount, subject, date_str, src = result
                    buyer_s = sanitize_filename(buyer) or "未知购方"
                    amount_s = sanitize_filename(amount)
                    fname = f"{date_str}_电子发票{buyer_s}{amount_s}.pdf"

                    target = out_dir / fname
                    n = 1
                    while target.exists():
                        fname = f"{date_str}_电子发票{buyer_s}{amount_s}_{n}.pdf"
                        target = out_dir / fname
                        n += 1

                    if not dry_run:
                        target.write_bytes(pdf_bytes)

                    processed_set.add(ukey)
                    total_new += 1

                    success_record = {
                        "status": "success",
                        "subject": subject,
                        "date": date_str,
                        "buyer": buyer or "未知购方",
                        "amount": amount,
                        "filename": fname,
                        "filepath": str(target),
                        "source": src,
                        "folder": folder,
                        "email_uid": ukey,
                    }
                    results.append(success_record)

                    # 新增：成功记录保存到数据库
                    if self._db and not dry_run:
                        try:
                            self._db.add_invoice_record(success_record)
                        except Exception:
                            pass

            state["processed"] = list(processed_set)
            if not dry_run:
                save_state(state_path, state)

            summary = {
                "total_processed": total_new + failed_count,
                "success_count": total_new,
                "failed_count": failed_count,
                "output_dir": str(out_dir)
            }

            return results, summary

        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def validate_config(self):
        errors = []
        if not self.config.get("email"):
            errors.append("邮箱地址不能为空")
        if not self.config.get("password"):
            errors.append("客户端授权码不能为空")
        if not self.config.get("imap_server"):
            errors.append("IMAP服务器地址不能为空")
        return errors

    def get_state_path(self):
        return str(Path(self.config.get("state_file") or (Path(__file__).parent.parent / "database" / "invoice_state.json")))
