"""Anchor 上下文变量

提供 ``anchor_ctx`` 和 ``event_ctx`` 两个上下文变量,
使事件处理器无需显式传参即可获取当前 Anchor 实例和正在处理的事件.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import Anchor
    from .event import OneBotEvent

anchor_ctx: ContextVar[Anchor] = ContextVar("anchor_ctx")
"""当前 Anchor 实例的上下文变量."""

event_ctx: ContextVar[OneBotEvent] = ContextVar("event_ctx")
"""当前正在处理的事件的上下文变量."""


@contextmanager
def enter_context(anchor: Anchor, event: OneBotEvent):
    """在事件处理期间设置上下文变量.

    Args:
        anchor (Anchor): 当前 Anchor 实例.
        event (OneBotEvent): 当前正在处理的事件.
    """
    t1 = anchor_ctx.set(anchor)
    t2 = event_ctx.set(event)
    try:
        yield
    finally:
        anchor_ctx.reset(t1)
        event_ctx.reset(t2)
