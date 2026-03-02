"""Anchor 内置 Dispatcher

提供一组 graia-broadcast Dispatcher, 用于向事件监听器自动注入常用对象,
如 Anchor 实例、当前事件、消息链、发送者信息、群组信息等.

所有 Dispatcher 均继承 ``BaseDispatcher``, 注册到 ``Broadcast.finale_dispatchers``
作为最终兜底的参数解析器.
"""

from __future__ import annotations

from typing import Any

from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface

from .event import OneBotEvent
from .event.message import GroupMessageEvent, MessageEvent
from .message.chain import MessageChain
from .message.segment import Reply
from .model.relationship import FriendSender, Group, GroupSender


class AnchorDispatcher(BaseDispatcher):
    """注入当前 Anchor 实例.

    当监听器参数类型标注为 ``Anchor`` 时, 通过 ``Anchor.current()`` 注入实例.
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        from .app import Anchor

        if interface.annotation is Anchor:
            try:
                return Anchor.current()
            except ValueError:
                return None
        return None


class EventDispatcher(BaseDispatcher):
    """注入当前 OneBotEvent 实例.

    当监听器参数类型标注为 ``OneBotEvent`` 或其子类时, 自动注入当前正在处理的事件.
    通过 ``interface.event`` 获取 graia-broadcast 上下文中的事件.
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        event = interface.event
        if interface.annotation is OneBotEvent or (
            isinstance(interface.annotation, type) and isinstance(event, interface.annotation)
        ):
            return event
        return None


class MessageChainDispatcher(BaseDispatcher):
    """注入消息链.

    当监听器参数类型标注为 ``MessageChain`` 时,
    从当前 ``MessageEvent`` 中提取并注入消息链.
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        if interface.annotation is MessageChain:
            event = interface.event
            if isinstance(event, MessageEvent):
                return event.message_chain
        return None


class SenderDispatcher(BaseDispatcher):
    """注入消息发送者信息.

    当监听器参数类型标注为 ``GroupSender`` 或 ``FriendSender`` 时,
    从当前消息事件中提取并注入对应的发送者对象.
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        event = interface.event
        if not isinstance(event, MessageEvent):
            return None
        if interface.annotation in (GroupSender, FriendSender):
            if isinstance(event.sender, interface.annotation):
                return event.sender
        return None


class GroupDispatcher(BaseDispatcher):
    """注入群组信息.

    当监听器参数类型标注为 ``Group`` 或参数名为 ``group_id`` 且类型为 ``int`` 时,
    从当前 ``GroupMessageEvent`` 中提取并注入群组对象或群号.
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        if interface.annotation is Group or (interface.annotation is int and interface.name == "group_id"):
            event = interface.event
            if isinstance(event, GroupMessageEvent):
                if interface.annotation is int:
                    return event.group_id
                return Group(group_id=event.group_id)
        return None


class ReplyDispatcher(BaseDispatcher):
    """注入回复段.

    当监听器参数类型标注为 ``Reply`` 时,
    从当前消息事件的消息链中提取并注入回复段 (如果存在).
    """

    mixin = []

    async def catch(self, interface: DispatcherInterface) -> Any:
        if interface.annotation is Reply:
            event = interface.event
            if isinstance(event, MessageEvent):
                return event.message_chain.reply
        return None
