"""Anchor 类型定义"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


class Sentinel:
    """标记值, 用于区分「未传入参数」和 ``None``."""


@runtime_checkable
class SendMessageActionProtocol(Protocol[T]):
    """消息发送行为协议.

    定义了消息发送过程中的三个阶段: 参数预处理、结果处理、异常处理.
    可在 ``graiax.anchor.util.send`` 中查看内置实现.
    """

    async def param(self, data: dict[str, Any]) -> dict[str, Any]:
        """预处理发送参数."""
        ...

    async def result(self, result: Any) -> T:
        """处理发送结果."""
        ...

    async def exception(self, exc: Exception) -> T:
        """处理发送异常."""
        ...


def generic_issubclass(cls: type, classinfo: type | tuple) -> bool:
    """安全的 ``issubclass`` 包装, 支持泛型类型.

    Args:
        cls (type): 要检查的类.
        classinfo (Union[type, tuple]): 目标类或类元组.

    Returns:
        bool: 是否为子类.
    """
    try:
        return issubclass(cls, classinfo)
    except TypeError:
        origin = getattr(classinfo, "__origin__", None)
        if origin:
            return issubclass(cls, origin)
        return False
