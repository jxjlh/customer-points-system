"""企业微信登录模块 - 占位实现

如果需要启用企业微信登录，请在此模块中实现完整功能。
"""


def get_wecom_config(config):
    """从配置中获取企业微信配置。"""
    wecom_cfg = config.get("wecom", {})
    # 确保有默认值
    if "enabled" not in wecom_cfg:
        wecom_cfg["enabled"] = False
    return wecom_cfg


def is_configured(wecom_cfg):
    """检查企业微信配置是否完整。"""
    if not wecom_cfg.get("enabled", False):
        return False
    required_fields = ["corp_id", "agent_id", "secret"]
    return all(wecom_cfg.get(field) for field in required_fields)


def build_oauth_url_prefix(wecom_cfg):
    """构建企业微信 OAuth 授权 URL 前缀。"""
    corp_id = wecom_cfg.get("corp_id", "")
    return f"https://open.weixin.qq.com/connect/oauth2/authorize?appid={corp_id}"


def exchange_auth_code(wecom_cfg, auth_code):
    """用授权码换取用户信息。

    返回: (userid, error_message)
    成功时 error_message 为 None，失败时 userid 为 None。
    """
    # 占位实现 - 实际使用时需要调用企业微信 API
    return None, "企业微信登录功能未实现"


def match_local_user(config, wecom_userid):
    """根据企业微信 userid 匹配本地用户。

    返回: 匹配到的用户名，没匹配到返回 None。
    """
    usernames = config.get("credentials", {}).get("usernames", {})
    for username, user_info in usernames.items():
        if user_info.get("wecom_userid") == wecom_userid:
            return username
    return None
