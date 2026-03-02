"""Anchor 内置 Dispatcher

提供一组 graia-broadcast Dispatcher, 用于向事件监听器自动注入常用对象,
如 Anchor 实例、当前事件、消息链、发送者信息、群组信息等.
"""

from __future__ import annotations

from typing import Any

from graia.broadcast.interfaces.dispatcher import DispatcherInterface

from .context import anchor_ctx, event_ctx
from .event import OneBotEvent
from .event.message import GroupMessageEvent, MessageEvent
from .message.chain import MessageChain
from .message.segment import Reply
from .model.relationship import FriendSender, Group, GroupSender


class AnchorDispatcher:
    """注入当前 Anchor 实例.

    当监听器参数类型标注为 ``Anchor`` 时, 自动注入当前上下文中的 Anchor 实例.
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        from .app import Anchor

        if interface.annotation is Anchor:
            return anchor_ctx.get(None)
        return None


class EventDispatcher:
    """注入当前 OneBotEvent 实例.

    当监听器参数类型标注为 ``OneBotEvent`` 或其子类时, 自动注入当前正在处理的事件.
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        event = event_ctx.get(None)
        if event is None:
            return None
        if interface.annotation is OneBotEvent or (
            isinstance(interface.annotation, type) and isinstance(event, interface.annotation)
        ):
            return event
        return None


class MessageChainDispatcher:
    """注入消息链.

    当监听器参数类型标注为 ``MessageChain`` 时,
    从当前 ``MessageEvent`` 中提取并注入消息链.
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        if interface.annotation is MessageChain:
            event = event_ctx.get(None)
            if isinstance(event, MessageEvent):
                return event.message_chain
        return None


class SenderDispatcher:
    """注入消息发送者信息.

    当监听器参数类型标注为 ``GroupSender`` 或 ``FriendSender`` 时,
    从当前消息事件中提取并注入对应的发送者对象.
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        event = event_ctx.get(None)
        if not isinstance(event, MessageEvent):
            return None
        if interface.annotation in (GroupSender, FriendSender):
            if isinstance(event.sender, interface.annotation):
                return event.sender
        return None


class GroupDispatcher:
    """注入群组信息.

    当监听器参数类型标注为 ``Group`` 或参数名为 ``group_id`` 且类型为 ``int`` 时,
    从当前 ``GroupMessageEvent`` 中提取并注入群组对象或群号.
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        if interface.annotation is Group or interface.annotation is int and interface.name == "group_id":
            event = event_ctx.get(None)
            if isinstance(event, GroupMessageEvent):
                if interface.annotation is int:
                    return event.group_id
                return Group(group_id=event.group_id)
        return None


class ReplyDispatcher:
    """注入回复段.

    当监听器参数类型标注为 ``Reply`` 时,
    从当前消息事件的消息链中提取并注入回复段 (如果存在).
    """

    @staticmethod
    async def catch(interface: DispatcherInterface) -> Any | None:
        if interface.annotation is Reply:
            event = event_ctx.get(None)
            if isinstance(event, MessageEvent):
                return event.message_chain.reply
        return None
