"""消息发送行为 (Action)

定义了 ``Anchor.send_message()`` 使用的错误处理策略.
可在 ``graiax.anchor.util.send`` 中查看所有内置 Action.
"""

from __future__ import annotations

from typing import Any


class Strict:
    """严格模式: 遇到异常直接抛出."""

    @staticmethod
    async def param(data: dict[str, Any]) -> dict[str, Any]:
        """预处理发送参数."""
        return data

    @staticmethod
    async def result(result: Any) -> Any:
        """处理发送结果."""
        return result

    @staticmethod
    async def exception(exc: Exception) -> Any:
        """处理发送异常; 严格模式下直接重新抛出."""
        raise exc


class Bypass:
    """透传模式: 异常不抛出, 而是作为返回值返回."""

    @staticmethod
    async def param(data: dict[str, Any]) -> dict[str, Any]:
        return data

    @staticmethod
    async def result(result: Any) -> Any:
        return result

    @staticmethod
    async def exception(exc: Exception) -> Exception:
        """处理发送异常; 透传模式下返回异常对象."""
        return exc


class Ignore:
    """忽略模式: 异常不抛出, 返回 ``None``."""

    @staticmethod
    async def param(data: dict[str, Any]) -> dict[str, Any]:
        return data

    @staticmethod
    async def result(result: Any) -> Any:
        return result

    @staticmethod
    async def exception(_: Exception) -> None:
        """处理发送异常; 忽略模式下返回 ``None``."""
        return None


class Safe:
    """安全模式: 发送失败时可选择忽略异常.

    未来可扩展为: 逐步将富媒体段降级为文本并重试发送.

    Args:
        ignore (bool): 为 True 时忽略异常返回 ``None``; 为 False 时抛出原始异常.
    """

    def __init__(self, ignore: bool = False) -> None:
        self.ignore = ignore

    async def param(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def result(self, result: Any) -> Any:
        return result

    async def exception(self, exc: Exception) -> Any:
        """处理发送异常; 根据 ``ignore`` 参数决定是否抛出."""
        if self.ignore:
            return None
        raise exc
