"""Saya 集成工具

提供与 graia-saya 配合使用的便捷装饰器.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def listen(*events: type[Any]) -> Callable:
    """注册 Saya 事件监听器的装饰器.

    Usage::

        from graiax.anchor.util.saya import listen
        from graiax.anchor.event.message import GroupMessageEvent

        channel = Channel.current()

        @listen(GroupMessageEvent)
        async def handler(event: GroupMessageEvent):
            ...

    Args:
        *events (Type[Any]): 要监听的事件类型.

    Returns:
        Callable: 装饰器.
    """

    def decorator(func: Callable) -> Callable:
        from graia.saya import Channel

        channel = Channel.current()
        from graia.saya.builtins.broadcast import ListenerSchema

        channel.use(ListenerSchema(listening_events=list(events)))(func)
        return func

    return decorator
