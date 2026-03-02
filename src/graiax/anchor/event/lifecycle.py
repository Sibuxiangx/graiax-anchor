"""元事件: 心跳与生命周期"""

from __future__ import annotations

from pydantic import Field

from ..model.util import AnchorBaseModel
from . import OneBotEvent


class HeartbeatStatus(AnchorBaseModel):
    """心跳事件中的状态信息.

    Attributes:
        online: 是否在线.
        good: 状态是否正常.
    """

    online: bool | None = None
    good: bool = True


class HeartbeatEvent(OneBotEvent):
    """OneBot 实现端周期性发送的心跳事件.

    Attributes:
        status: 心跳状态.
        interval: 心跳间隔 (毫秒).
    """

    post_type: str = "meta_event"
    meta_event_type: str = "heartbeat"
    status: HeartbeatStatus = Field(default_factory=HeartbeatStatus)
    interval: int = 0


class LifecycleEvent(OneBotEvent):
    """生命周期事件.

    Attributes:
        sub_type: 子类型, 取值为 ``enable`` / ``disable`` / ``connect``.
    """

    post_type: str = "meta_event"
    meta_event_type: str = "lifecycle"
    sub_type: str = ""
