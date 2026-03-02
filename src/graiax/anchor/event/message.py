"""消息事件: 私聊消息、群消息、机器人自身发送的消息"""

from __future__ import annotations

from typing import Any

from ..message.chain import MessageChain
from ..model.relationship import FriendSender, GroupSender
from . import OneBotEvent


class MessageEvent(OneBotEvent):
    """所有消息事件的基类.

    Attributes:
        message_type: 消息类型, ``private`` 或 ``group``.
        sub_type: 消息子类型, 如 ``friend`` / ``normal`` / ``anonymous`` 等.
        message_id: 消息 ID.
        user_id: 发送者 QQ 号.
        sender: 发送者信息.
        message: 原始 OneBot 消息段列表.
        raw_message: 原始消息文本.
        font: 字体.
    """

    post_type: str = "message"
    message_type: str = ""
    sub_type: str = ""
    message_id: int = 0
    user_id: int = 0
    sender: FriendSender | GroupSender = FriendSender()
    message: list[dict[str, Any]] = []
    raw_message: str = ""
    font: int = 0

    _chain: MessageChain | None = None

    @property
    def message_chain(self) -> MessageChain:
        """获取解析后的消息链; 首次访问时从 ``message`` 字段懒加载构建."""
        if self._chain is None:
            object.__setattr__(self, "_chain", MessageChain.from_onebot(self.message))
        return self._chain  # type: ignore[return-value]

    @property
    def id(self) -> int:
        """消息 ID 的便捷访问."""
        return self.message_id

    def __int__(self) -> int:
        return self.message_id


class PrivateMessageEvent(MessageEvent):
    """私聊 (好友/临时) 消息事件.

    Attributes:
        sender: 发送者信息.
        target_id: 接收者 QQ 号 (仅 NapCat 提供).
        temp_source: 临时会话来源群号 (如适用).
    """

    message_type: str = "private"
    sender: FriendSender = FriendSender()
    target_id: int | None = None
    temp_source: int | None = None


class GroupMessageEvent(MessageEvent):
    """群消息事件.

    Attributes:
        group_id: 群号.
        anonymous: 匿名信息 (如果是匿名消息).
        sender: 发送者信息.
    """

    message_type: str = "group"
    group_id: int = 0
    anonymous: dict[str, Any] | None = None
    sender: GroupSender = GroupSender()


class MessageSentEvent(MessageEvent):
    """机器人自身发送的消息事件 (``post_type='message_sent'``).

    Attributes:
        target_id: 发送目标 QQ 号.
        sender: 发送者信息.
        group_id: 群号 (群消息时有值).
    """

    post_type: str = "message_sent"
    target_id: int = 0
    sender: FriendSender | GroupSender = FriendSender()
    group_id: int = 0
