"""
企业微信登录：OAuth2 网页授权（自建应用扫码登录）

流程：
1. 点击"企业微信登录" -> 浏览器跳转企业微信授权页（扫码/确认）
2. 企业微信回调本应用 URL，携带 auth_code
3. 应用服务端用 auth_code 换取成员 userid，再匹配本地系统用户完成登录

依赖 config.yaml 中的 wecom 配置段：
    wecom:
      enabled: true
      corp_id: "企业ID"
      agent_id: "自建应用AgentId"
      secret: "自建应用Secret"
      # 可选：授权回调可信域名需在企业微信后台"网页授权及JS-SDK"中配置
"""
import time

import requests

OAUTH_URL = "https://login.work.weixin.qq.com/wwlogin/sso/login"
TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
USERINFO_URL = "https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo"

_token_cache = {"token": None, "expires_at": 0.0}


def get_wecom_config(config: dict) -> dict:
    wecom = config.get("wecom") or {}
    return {
        "enabled": bool(wecom.get("enabled", False)),
        "corp_id": str(wecom.get("corp_id", "")).strip(),
        "agent_id": str(wecom.get("agent_id", "")).strip(),
        "secret": str(wecom.get("secret", "")).strip(),
    }


def is_configured(wecom_cfg: dict) -> bool:
    return bool(wecom_cfg["corp_id"] and wecom_cfg["agent_id"] and wecom_cfg["secret"])


def build_oauth_url_prefix(wecom_cfg: dict) -> str:
    """构造授权 URL 前缀；redirect_uri 只能由浏览器端拼接，因此在 JS 中补全。"""
    return (
        f"{OAUTH_URL}?login_type=CorpApp"
        f"&appid={wecom_cfg['corp_id']}"
        f"&agentid={wecom_cfg['agent_id']}"
        f"&redirect_uri="
    )


def _get_access_token(corp_id: str, secret: str) -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    resp = requests.get(
        TOKEN_URL,
        params={"corpid": corp_id, "corpsecret": secret},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"获取 access_token 失败：{data.get('errmsg')}")
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 7200)) - 300
    return data["access_token"]


def exchange_auth_code(wecom_cfg: dict, auth_code: str):
    """用授权码换取成员身份，返回 (userid, error_message)。"""
    try:
        token = _get_access_token(wecom_cfg["corp_id"], wecom_cfg["secret"])
        resp = requests.get(
            USERINFO_URL,
            params={"access_token": token, "code": auth_code},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            return None, f"企业微信授权失败：{data.get('errmsg')}"
        userid = data.get("userid")
        if not userid:
            return None, "当前扫码身份非企业成员，无法登录"
        return userid, None
    except requests.RequestException as exc:
        return None, f"企业微信接口请求失败：{exc}"
    except RuntimeError as exc:
        return None, str(exc)


def match_local_user(config: dict, wecom_userid: str):
    """把企业微信 userid 匹配到本地系统用户：用户名相同，或用户配置了 wecom_userid 字段。"""
    usernames = config.get("credentials", {}).get("usernames", {})
    if wecom_userid in usernames:
        return wecom_userid
    for uname, info in usernames.items():
        if isinstance(info, dict) and info.get("wecom_userid") == wecom_userid:
            return uname
    return None
