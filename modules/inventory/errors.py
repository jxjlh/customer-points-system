class InventoryError(Exception):
    """库存模块可安全展示给用户的业务错误。"""


class ValidationError(InventoryError):
    """输入内容不符合库存业务规则。"""


class DuplicateItemCodeError(InventoryError):
    """库存编号已经存在。"""


class InsufficientStockError(InventoryError):
    """出库数量超过当前库存。"""


class ItemNotFoundError(InventoryError):
    """库存物品不存在。"""


class ItemArchivedError(InventoryError):
    """库存物品已归档，不能继续出入库。"""


class DeleteRestrictedError(InventoryError):
    """库存物品存在历史记录，不能彻底删除。"""
