"""
讯飞星火 Spark Lite API 封装
用于邮件内容润色、改写、优化
"""
import json
import hashlib
import base64
import hmac
import time
import os
from datetime import datetime
from urllib.parse import urlparse, urlencode
import websocket  # websocket-client

# ===== 讯飞星火配置 =====
SPARK_APP_ID = os.environ.get("SPARK_APP_ID", "a1ff432b")
SPARK_API_SECRET = os.environ.get("SPARK_API_SECRET", "OTBjMmY5ZmUxZTI1MjAwMjMwM2ZjMTU4")
SPARK_API_KEY = os.environ.get("SPARK_API_KEY", "309bcffee01285f0b319e2e7a72a0dca")

# Spark Lite 模型
SPARK_LITE_URL = "wss://spark-api.xf-yun.com/v1.1/chat"
SPARK_LITE_DOMAIN = "general"


def _get_auth_url(api_secret: str, api_key: str, url: str) -> str:
    """生成讯飞 WebSocket 鉴权 URL"""
    parsed = urlparse(url)
    now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    signature_origin = (
        f"host: {parsed.hostname}\n"
        f"date: {now}\n"
        f"GET {parsed.path} HTTP/1.1"
    )
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    params = {"authorization": authorization, "date": now, "host": parsed.hostname}
    return f"{url}?{urlencode(params)}"


def spark_chat(prompt: str, user_input: str, max_tokens: int = 2000) -> str:
    """
    调用讯飞星火 Spark Lite 对话接口

    Args:
        prompt: 系统提示词（角色设定）
        user_input: 用户输入文本
        max_tokens: 最大输出长度

    Returns:
        星火回复的完整文本
    """
    auth_url = _get_auth_url(SPARK_API_SECRET, SPARK_API_KEY, SPARK_LITE_URL)

    payload = {
        "header": {"app_id": SPARK_APP_ID},
        "parameter": {
            "chat": {"domain": SPARK_LITE_DOMAIN, "max_tokens": max_tokens, "temperature": 0.7}
        },
        "payload": {
            "message": {
                "text": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ]
            }
        },
    }

    result_text = []
    ws = websocket.create_connection(auth_url, timeout=30)
    ws.send(json.dumps(payload))

    while True:
        try:
            resp = ws.recv()
            data = json.loads(resp)
            code = data.get("header", {}).get("code", -1)
            if code != 0:
                ws.close()
                return f"[星火错误 code={code}] {data.get('header', {}).get('message', '')}"
            resp_text = (
                data.get("payload", {})
                .get("choices", {})
                .get("text", [{}])[0]
                .get("content", "")
            )
            result_text.append(resp_text)
            status = data.get("header", {}).get("status", 0)
            if status == 2:  # 2 = 结束
                break
        except websocket.WebSocketException:
            break

    ws.close()
    return "".join(result_text)


def polish_email(body: str, tone: str = "商务正式") -> str:
    """
    用星火润色邮件正文

    Args:
        body: 原始邮件正文
        tone: 语气风格（商务正式 / 亲切友好 / 简洁高效）

    Returns:
        润色后的邮件正文
    """
    prompt = (
        f"你是一位专业的商务邮件写作助手。请将以下邮件正文进行润色优化，"
        f"使其更加{tone}、通顺、得体。保持原意不变，保留所有变量占位符"
        f"（如 {{{{姓氏}}}} 、 {{{{姓名}}}} 等双大括号包裹的变量，以及 [客户姓名/老师] 等方括号占位符）不变。"
        f"直接输出润色后的邮件正文，不要加解释。"
    )
    return spark_chat(prompt, body)


def generate_email_subject(topic: str, recipient_name: str = "") -> str:
    """用星火生成邮件主题建议"""
    prompt = (
        "你是一位商务邮件主题生成助手。请根据以下信息生成3个简洁专业的邮件主题选项，"
        "每行一个，不要加序号或解释。"
    )
    info = f"邮件内容/主题：{topic}"
    if recipient_name:
        info += f"\n收件人：{recipient_name}"
    return spark_chat(prompt, info)


def rewrite_email(body: str, instruction: str) -> str:
    """
    根据用户指令改写邮件正文

    Args:
        body: 原始正文
        instruction: 改写指令（如"更简短"、"更正式"等）

    Returns:
        改写后的正文
    """
    prompt = (
        "你是一位邮件改写助手。请根据以下指令对邮件正文进行改写。"
        "保留所有变量占位符（双大括号 {{xxx}} 和方括号 [xxx] 格式）不变。"
        "直接输出改写后的正文，不要加解释。"
    )
    user_msg = f"改写指令：{instruction}\n\n原文：\n{body}"
    return spark_chat(prompt, user_msg)
