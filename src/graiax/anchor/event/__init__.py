"""OneBot 11 事件系统

所有事件均继承自 ``OneBotEvent``. 事件分发基于 ``post_type`` 及其子类型字段,
而非 mirai-api-http 中的单一 ``type`` 字段.
"""

from __future__ import annotations

from typing import Any

from graia.broadcast import Dispatchable

from ..model.util import AnchorBaseModel


class OneBotEvent(AnchorBaseModel, Dispatchable):
    """所有 OneBot 11 事件的基类.

    每个事件都携带以下字段:

    Attributes:
        time: Unix 时间戳 (秒).
        self_id: 接收事件的机器人 QQ 号.
        post_type: 事件大类, 取值为 ``message`` / ``message_sent`` / \
            ``notice`` / ``request`` / ``meta_event``.
    """

    time: int = 0
    self_id: int = 0
    post_type: str = ""

    class Dispatcher:
        """默认事件 Dispatcher; 子类可覆盖以注入特定参数."""

        @staticmethod
        async def catch(interface: Any) -> Any | None:
            pass
