"""
价格库数据规范化公共函数

供 PriceService 和 PgDatabaseManager 共用，避免循环依赖。
"""
import json
import os


# 默认配置（当配置文件不可用时使用）
_DEFAULT_SEX_MAPPING = {
    "M": ["M", "Male", "male", "公", "雄", "男"],
    "F": ["F", "Female", "female", "母", "雌", "女"],
}


def _load_mapping_config() -> dict:
    """加载 excel_mapping.json 配置"""
    config_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
    )
    mapping_path = os.path.join(config_dir, "excel_mapping.json")
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def normalize_sex(sex: str) -> str:
    """
    规范化性别字段

    Args:
        sex: 原始性别值（M/Male/公/雄 等）

    Returns:
        标准化后的性别（M 或 F）
    """
    if not sex:
        return ""
    sex = str(sex).strip().upper()
    config = _load_mapping_config()
    sex_mapping = config.get("sex_mapping", _DEFAULT_SEX_MAPPING)

    for standard, aliases in sex_mapping.items():
        if sex in [a.upper() for a in aliases]:
            return standard

    return sex


def normalize_age(age: str) -> str:
    """
    规范化周龄字段

    Args:
        age: 原始周龄值（"6", "6w", "6周" 等）

    Returns:
        标准化后的周龄（纯数字字符串）
    """
    if not age:
        return ""
    age = str(age).strip()
    if age.isdigit():
        return age
    # 去除 "w" 或 "周" 后缀
    if age.endswith("w") or age.endswith("周"):
        return age[:-1].strip()
    return age
