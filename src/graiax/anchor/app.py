"""Anchor 实例"""

from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Iterable
from typing import (
    Any,
    ClassVar,
)

from graia.broadcast import Broadcast
from launart import Launart
from loguru import logger

from .connection.config import OneBotConfig
from .context import enter_context
from .event import OneBotEvent
from .event.message import GroupMessageEvent, MessageEvent, PrivateMessageEvent
from .log import LogConfig, install_log_hooks, install_richuru, loguru_exc_callback_async
from .message.chain import MessageChain, MessageContainer
from .message.segment import ForwardNode
from .model.relationship import (
    EssenceMessage,
    Friend,
    Group,
    GroupHonorInfo,
    GroupNotice,
    GroupRootFiles,
    LoginInfo,
    Member,
    StatusInfo,
    Stranger,
    VersionInfo,
)
from .service import AnchorService


class Anchor:
    """Anchor, 一个优雅且协议完备的 Python OneBot 11 框架.

    Usage::

        from graia.broadcast import Broadcast
        from graiax.anchor import Anchor
        from graiax.anchor.connection import OneBotConfig

        broadcast = Broadcast()
        app = Anchor(
            broadcast=broadcast,
            config=OneBotConfig(
                ws_url="ws://localhost:3001",
                access_token="your_token",
            ),
        )
        app.launch_blocking()
    """

    instances: ClassVar[dict[int, Anchor]] = {}
    launch_manager: ClassVar[Launart] = None  # type: ignore[assignment]
    _log_installed: ClassVar[bool] = False

    broadcast: Broadcast
    config: OneBotConfig
    service: AnchorService
    log_config: LogConfig
    account: int

    def __init__(
        self,
        broadcast: Broadcast,
        config: OneBotConfig,
        *,
        launch_manager: Launart | None = None,
        log_config: LogConfig | None = None,
        install_log: bool = True,
    ) -> None:
        """初始化 Anchor 实例.

        Args:
            broadcast (Broadcast): 事件系统实例.
            config (OneBotConfig): OneBot 连接配置, 至少需要提供 ws_url 或 http_url.
            launch_manager (Optional[Launart], optional): 启动管理器, 未提供时自动创建.
            log_config (Optional[LogConfig], optional): 日志配置, 未提供时使用默认配置.
            install_log (bool, optional): 是否安装 loguru 异常回调与 richuru, 默认为 True.
        """
        if install_log and not Anchor._log_installed:
            install_log_hooks()
            install_richuru()
            Anchor._log_installed = True

        self.broadcast = broadcast
        self.config = config
        self.log_config = log_config or LogConfig()
        if launch_manager:
            Anchor.launch_manager = launch_manager
        if Anchor.launch_manager is None:
            Anchor.launch_manager = Launart()
        self.service = AnchorService(broadcast, config)
        self.service.add_event_callback(self.log_config.event_hook(self))
        self.service.add_event_callback(self._event_hook)
        self.account = config.account
        if self.account:
            Anchor.instances[self.account] = self

    async def _event_hook(self, event: OneBotEvent) -> None:
        if not self.account and hasattr(event, "self_id") and event.self_id:
            self.account = event.self_id
            Anchor.instances[self.account] = self
            logger.info(f"账号自动识别: {self.account}")
        with enter_context(self, event):
            sys.audit("AnchorPostRemoteEvent", event)

    @classmethod
    def current(cls, account: int | None = None) -> Anchor:
        """获取 Anchor 的当前实例.

        Args:
            account (Optional[int], optional): 指定账号; 不提供时从上下文或唯一实例推断.

        Raises:
            ValueError: 存在多个实例且无法确定目标时抛出.

        Returns:
            Anchor: 当前实例.
        """
        if account and account in cls.instances:
            return cls.instances[account]
        from .context import anchor_ctx

        if ctx := anchor_ctx.get(None):
            return ctx
        if len(cls.instances) == 1:
            return next(iter(cls.instances.values()))
        raise ValueError("Ambiguous Anchor reference; specify account or use within event context")

    def _patch_launch_manager(self) -> None:
        mgr = Anchor.launch_manager
        if self.service.id not in {s.id for s in mgr._service_bind.values()}:
            mgr.add_service(self.service)

    def launch_blocking(self, stop_signals: Iterable[signal.Signals] = (signal.SIGINT,)) -> None:
        """以阻塞方式启动 Anchor.

        Args:
            stop_signals (Iterable[signal.Signals], optional): 要监听的停止信号, 默认为 ``(signal.SIGINT,)``.
        """
        self._patch_launch_manager()
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(loguru_exc_callback_async)
        try:
            Anchor.launch_manager.launch_blocking(stop_signal=stop_signals)
        except asyncio.CancelledError:
            logger.info("Anchor exited.")

    @classmethod
    def stop(cls) -> None:
        """计划停止 Anchor."""
        mgr = cls.launch_manager
        if mgr:
            mgr.status.exiting = True
            if mgr.task_group is not None:
                mgr.task_group.stop = True
                task = mgr.task_group.blocking_task
                if task and not task.done():
                    task.cancel()

    async def call_api(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """调用任意 OneBot 11 API 端点.

        Args:
            endpoint (str): API 端点名称, 如 ``"send_group_msg"``.
            params (Optional[dict[str, Any]], optional): 请求参数.

        Returns:
            Any: API 返回的 data 字段.
        """
        return await self.service.call_api(endpoint, params)

    # ══════════════════════════════════════════════════════════════════════
    #  消息接口
    # ══════════════════════════════════════════════════════════════════════

    async def send_private_msg(
        self,
        user_id: int,
        message: MessageContainer,
        *,
        auto_escape: bool = False,
    ) -> dict[str, Any]:
        """发送私聊消息.

        Args:
            user_id (int): 目标 QQ 号.
            message (MessageContainer): 要发送的消息内容.
            auto_escape (bool, optional): 消息内容是否作为纯文本发送, 默认为 False.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        chain = MessageChain(message) if not isinstance(message, MessageChain) else message
        self.log_config.log_send(self, "私", user_id, chain.safe_display)
        result = await self.call_api("send_private_msg", {
            "user_id": user_id,
            "message": chain.to_onebot(),
            "auto_escape": auto_escape,
        })
        return result

    async def send_group_msg(
        self,
        group_id: int,
        message: MessageContainer,
        *,
        auto_escape: bool = False,
    ) -> dict[str, Any]:
        """发送群聊消息.

        Args:
            group_id (int): 目标群号.
            message (MessageContainer): 要发送的消息内容.
            auto_escape (bool, optional): 消息内容是否作为纯文本发送, 默认为 False.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        chain = MessageChain(message) if not isinstance(message, MessageChain) else message
        self.log_config.log_send(self, "群", group_id, chain.safe_display)
        result = await self.call_api("send_group_msg", {
            "group_id": group_id,
            "message": chain.to_onebot(),
            "auto_escape": auto_escape,
        })
        return result

    async def send_msg(
        self,
        message: MessageContainer,
        *,
        message_type: str | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
        auto_escape: bool = False,
    ) -> dict[str, Any]:
        """发送消息; 根据提供的参数自动判断消息类型.

        当 ``message_type`` 未指定时, 将根据 ``user_id`` 和 ``group_id`` 推断发送目标.

        Args:
            message (MessageContainer): 要发送的消息内容.
            message_type (Optional[str], optional): 消息类型, ``"private"`` 或 ``"group"``.
            user_id (Optional[int], optional): 目标 QQ 号 (私聊时必填).
            group_id (Optional[int], optional): 目标群号 (群聊时必填).
            auto_escape (bool, optional): 消息内容是否作为纯文本发送, 默认为 False.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        chain = MessageChain(message) if not isinstance(message, MessageChain) else message
        target_label = "群" if (message_type == "group" or group_id) else "私"
        target_id = group_id or user_id or 0
        self.log_config.log_send(self, target_label, target_id, chain.safe_display)
        params: dict[str, Any] = {
            "message": chain.to_onebot(),
            "auto_escape": auto_escape,
        }
        if message_type:
            params["message_type"] = message_type
        if user_id is not None:
            params["user_id"] = user_id
        if group_id is not None:
            params["group_id"] = group_id
        return await self.call_api("send_msg", params)

    async def send_message(
        self,
        target: MessageEvent | Group | Friend | Member | int,
        message: MessageContainer,
        *,
        quote: int | None = None,
    ) -> dict[str, Any]:
        """依据传入的 ``target`` 自动发送消息.

        可接受消息事件、群组、好友、成员实例或 QQ 号作为发送目标;
        传入群消息事件时将回复到对应群组, 传入私聊事件时将回复到私聊.

        Args:
            target (Union[MessageEvent, Group, Friend, Member, int]): 消息发送目标.
            message (MessageContainer): 要发送的消息内容.
            quote (Optional[int], optional): 需要回复的消息 ID, 默认为 None.

        Raises:
            TypeError: 无法判断消息发送目标的类型.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        chain = MessageChain(message) if not isinstance(message, MessageChain) else message
        from .message.segment import Reply

        if quote:
            chain = MessageChain([Reply(quote)] + list(chain.content), inline=True)

        if isinstance(target, GroupMessageEvent):
            return await self.send_group_msg(target.group_id, chain)
        if isinstance(target, PrivateMessageEvent):
            return await self.send_private_msg(target.user_id, chain)
        if isinstance(target, MessageEvent):
            return await self.send_private_msg(target.user_id, chain)
        if isinstance(target, Group):
            return await self.send_group_msg(target.group_id, chain)
        if isinstance(target, (Friend, Stranger)):
            return await self.send_private_msg(target.user_id, chain)
        if isinstance(target, Member):
            return await self.send_private_msg(target.user_id, chain)
        if isinstance(target, int):
            return await self.send_private_msg(target, chain)
        raise TypeError(f"Cannot determine target type: {type(target)}")

    async def delete_msg(self, message_id: int) -> None:
        """撤回指定消息.

        Args:
            message_id (int): 需要撤回的消息 ID.
        """
        await self.call_api("delete_msg", {"message_id": message_id})

    async def get_msg(self, message_id: int) -> dict[str, Any]:
        """获取消息详情.

        Args:
            message_id (int): 消息 ID.

        Returns:
            dict[str, Any]: 消息详情, 包含发送者、消息内容等信息.
        """
        return await self.call_api("get_msg", {"message_id": message_id})

    async def get_forward_msg(self, message_id: str) -> Any:
        """获取合并转发消息的内容.

        Args:
            message_id (str): 合并转发消息的 ID.

        Returns:
            Any: 合并转发的消息列表.
        """
        return await self.call_api("get_forward_msg", {"message_id": message_id})

    async def send_forward_msg(
        self,
        messages: list[ForwardNode],
        *,
        group_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """发送合并转发消息.

        ``group_id`` 和 ``user_id`` 至少提供一个以确定发送目标.

        Args:
            messages (list[ForwardNode]): 转发消息节点列表.
            group_id (Optional[int], optional): 目标群号.
            user_id (Optional[int], optional): 目标 QQ 号.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        nodes = [{"type": "node", "data": n.data} for n in messages]
        params: dict[str, Any] = {"messages": nodes}
        if group_id is not None:
            params["group_id"] = group_id
        if user_id is not None:
            params["user_id"] = user_id
        return await self.call_api("send_forward_msg", params)

    async def send_group_forward_msg(
        self, group_id: int, messages: list[ForwardNode]
    ) -> dict[str, Any]:
        """发送群聊合并转发消息.

        Args:
            group_id (int): 目标群号.
            messages (list[ForwardNode]): 转发消息节点列表.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        nodes = [{"type": "node", "data": n.data} for n in messages]
        return await self.call_api("send_group_forward_msg", {
            "group_id": group_id,
            "messages": nodes,
        })

    async def send_private_forward_msg(
        self, user_id: int, messages: list[ForwardNode]
    ) -> dict[str, Any]:
        """发送私聊合并转发消息.

        Args:
            user_id (int): 目标 QQ 号.
            messages (list[ForwardNode]): 转发消息节点列表.

        Returns:
            dict[str, Any]: 包含 ``message_id`` 的返回结果.
        """
        nodes = [{"type": "node", "data": n.data} for n in messages]
        return await self.call_api("send_private_forward_msg", {
            "user_id": user_id,
            "messages": nodes,
        })

    async def forward_friend_single_msg(
        self, message_id: int, user_id: int
    ) -> None:
        """转发单条消息到好友.

        Args:
            message_id (int): 要转发的消息 ID.
            user_id (int): 目标好友 QQ 号.
        """
        await self.call_api("forward_friend_single_msg", {
            "message_id": message_id,
            "user_id": user_id,
        })

    async def forward_group_single_msg(
        self, message_id: int, group_id: int
    ) -> None:
        """转发单条消息到群组.

        Args:
            message_id (int): 要转发的消息 ID.
            group_id (int): 目标群号.
        """
        await self.call_api("forward_group_single_msg", {
            "message_id": message_id,
            "group_id": group_id,
        })

    async def get_group_msg_history(
        self,
        group_id: int,
        *,
        message_seq: int | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """获取群消息历史记录.

        Args:
            group_id (int): 群号.
            message_seq (Optional[int], optional): 起始消息序号, 默认为最新.
            count (int, optional): 获取数量, 默认为 20.

        Returns:
            list[dict[str, Any]]: 消息列表.
        """
        params: dict[str, Any] = {"group_id": group_id, "count": count}
        if message_seq is not None:
            params["message_seq"] = message_seq
        result = await self.call_api("get_group_msg_history", params)
        return result.get("messages", []) if isinstance(result, dict) else result or []

    async def get_friend_msg_history(
        self,
        user_id: int,
        *,
        message_seq: int | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """获取好友消息历史记录.

        Args:
            user_id (int): 好友 QQ 号.
            message_seq (Optional[int], optional): 起始消息序号, 默认为最新.
            count (int, optional): 获取数量, 默认为 20.

        Returns:
            list[dict[str, Any]]: 消息列表.
        """
        params: dict[str, Any] = {"user_id": user_id, "count": count}
        if message_seq is not None:
            params["message_seq"] = message_seq
        result = await self.call_api("get_friend_msg_history", params)
        return result.get("messages", []) if isinstance(result, dict) else result or []

    async def mark_msg_as_read(self, message_id: int) -> None:
        """标记消息为已读.

        Args:
            message_id (int): 消息 ID.
        """
        await self.call_api("mark_msg_as_read", {"message_id": message_id})

    async def mark_private_msg_as_read(self, user_id: int) -> None:
        """标记私聊消息为已读.

        Args:
            user_id (int): 好友 QQ 号.
        """
        await self.call_api("mark_private_msg_as_read", {"user_id": user_id})

    async def mark_group_msg_as_read(self, group_id: int) -> None:
        """标记群聊消息为已读.

        Args:
            group_id (int): 群号.
        """
        await self.call_api("mark_group_msg_as_read", {"group_id": group_id})

    async def set_msg_emoji_like(
        self, message_id: int, emoji_id: str, *, set: bool = True
    ) -> None:
        """对消息贴表情回应.

        Args:
            message_id (int): 消息 ID.
            emoji_id (str): 表情 ID.
            set (bool, optional): 是否设置 (False 为取消), 默认为 True.
        """
        await self.call_api("set_msg_emoji_like", {
            "message_id": message_id,
            "emoji_id": emoji_id,
            "set": set,
        })

    # ══════════════════════════════════════════════════════════════════════
    #  好友 / 用户接口
    # ══════════════════════════════════════════════════════════════════════

    async def get_login_info(self) -> LoginInfo:
        """获取当前登录账号的信息.

        首次调用时会自动填充 ``self.account``.

        Returns:
            LoginInfo: 登录账号信息, 包含 ``user_id`` 和 ``nickname``.
        """
        data = await self.call_api("get_login_info")
        info = LoginInfo.model_validate(data)
        if not self.account and info.user_id:
            self.account = info.user_id
            Anchor.instances[self.account] = self
        return info

    async def get_friend_list(self) -> list[Friend]:
        """获取好友列表.

        Returns:
            list[Friend]: 好友列表.
        """
        data = await self.call_api("get_friend_list")
        return [Friend.model_validate(f) for f in (data or [])]

    async def get_friends_with_category(self) -> list[dict[str, Any]]:
        """获取带分组信息的好友列表.

        Returns:
            list[dict[str, Any]]: 分组好友列表.
        """
        return await self.call_api("get_friends_with_category") or []

    async def get_stranger_info(self, user_id: int, *, no_cache: bool = False) -> Stranger:
        """获取陌生人信息.

        Args:
            user_id (int): 目标 QQ 号.
            no_cache (bool, optional): 是否不使用缓存, 默认为 False.

        Returns:
            Stranger: 陌生人信息.
        """
        data = await self.call_api("get_stranger_info", {
            "user_id": user_id,
            "no_cache": no_cache,
        })
        return Stranger.model_validate(data)

    async def delete_friend(self, user_id: int) -> None:
        """删除好友.

        Args:
            user_id (int): 要删除的好友 QQ 号.
        """
        await self.call_api("delete_friend", {"user_id": user_id})

    async def set_friend_remark(self, user_id: int, remark: str) -> None:
        """设置好友备注.

        Args:
            user_id (int): 好友 QQ 号.
            remark (str): 新的备注名.
        """
        await self.call_api("set_friend_remark", {
            "user_id": user_id,
            "remark": remark,
        })

    async def set_friend_add_request(
        self, flag: str, approve: bool = True, *, remark: str = ""
    ) -> None:
        """处理好友添加请求.

        Args:
            flag (str): 请求标识 (从 ``FriendRequestEvent`` 获取).
            approve (bool, optional): 是否同意, 默认为 True.
            remark (str, optional): 添加后的好友备注 (仅在同意时有效).
        """
        await self.call_api("set_friend_add_request", {
            "flag": flag,
            "approve": approve,
            "remark": remark,
        })

    async def send_like(self, user_id: int, times: int = 1) -> None:
        """给好友点赞.

        Args:
            user_id (int): 好友 QQ 号.
            times (int, optional): 点赞次数, 每个好友每天最多 10 次, 默认为 1.
        """
        await self.call_api("send_like", {"user_id": user_id, "times": times})

    # ══════════════════════════════════════════════════════════════════════
    #  群组接口
    # ══════════════════════════════════════════════════════════════════════

    async def get_group_list(self, *, no_cache: bool = False) -> list[Group]:
        """获取群列表.

        Args:
            no_cache (bool, optional): 是否不使用缓存, 默认为 False.

        Returns:
            list[Group]: 群列表.
        """
        data = await self.call_api("get_group_list", {"no_cache": no_cache})
        return [Group.model_validate(g) for g in (data or [])]

    async def get_group_info(self, group_id: int, *, no_cache: bool = False) -> Group:
        """获取群信息.

        Args:
            group_id (int): 群号.
            no_cache (bool, optional): 是否不使用缓存, 默认为 False.

        Returns:
            Group: 群信息.
        """
        data = await self.call_api("get_group_info", {
            "group_id": group_id,
            "no_cache": no_cache,
        })
        return Group.model_validate(data)

    async def get_group_info_ex(self, group_id: int) -> dict[str, Any]:
        """获取群详细信息 (NapCat 扩展).

        Args:
            group_id (int): 群号.

        Returns:
            dict[str, Any]: 群详细信息.
        """
        return await self.call_api("get_group_info_ex", {"group_id": group_id})

    async def get_group_member_list(
        self, group_id: int, *, no_cache: bool = False
    ) -> list[Member]:
        """获取群成员列表.

        Args:
            group_id (int): 群号.
            no_cache (bool, optional): 是否不使用缓存, 默认为 False.

        Returns:
            list[Member]: 群成员列表.
        """
        data = await self.call_api("get_group_member_list", {
            "group_id": group_id,
            "no_cache": no_cache,
        })
        return [Member.model_validate(m) for m in (data or [])]

    async def get_group_member_info(
        self, group_id: int, user_id: int, *, no_cache: bool = False
    ) -> Member:
        """获取群成员信息.

        Args:
            group_id (int): 群号.
            user_id (int): 群成员 QQ 号.
            no_cache (bool, optional): 是否不使用缓存, 默认为 False.

        Returns:
            Member: 群成员信息.
        """
        data = await self.call_api("get_group_member_info", {
            "group_id": group_id,
            "user_id": user_id,
            "no_cache": no_cache,
        })
        return Member.model_validate(data)

    async def set_group_kick(
        self, group_id: int, user_id: int, *, reject_add_request: bool = False
    ) -> None:
        """将指定群成员踢出群组; 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            user_id (int): 要踢出的群成员 QQ 号.
            reject_add_request (bool, optional): 是否拒绝此人的加群请求, 默认为 False.
        """
        await self.call_api("set_group_kick", {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": reject_add_request,
        })

    async def set_group_ban(
        self, group_id: int, user_id: int, *, duration: int = 1800
    ) -> None:
        """在指定群组禁言指定群成员; 需要有相应权限(管理员/群主).

        ``duration`` 为 ``0`` 时表示取消禁言.

        Args:
            group_id (int): 群号.
            user_id (int): 要禁言的群成员 QQ 号.
            duration (int, optional): 禁言时长 (秒), 默认为 1800 (30 分钟).
        """
        await self.call_api("set_group_ban", {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration,
        })

    async def set_group_whole_ban(self, group_id: int, *, enable: bool = True) -> None:
        """设置全体禁言; 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            enable (bool, optional): 是否开启全体禁言, 默认为 True.
        """
        await self.call_api("set_group_whole_ban", {
            "group_id": group_id,
            "enable": enable,
        })

    async def set_group_admin(
        self, group_id: int, user_id: int, *, enable: bool = True
    ) -> None:
        """设置/取消群管理员; 需要群主权限.

        Args:
            group_id (int): 群号.
            user_id (int): 目标群成员 QQ 号.
            enable (bool, optional): 是否设置为管理员, 默认为 True.
        """
        await self.call_api("set_group_admin", {
            "group_id": group_id,
            "user_id": user_id,
            "enable": enable,
        })

    async def set_group_name(self, group_id: int, group_name: str) -> None:
        """修改群名; 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            group_name (str): 新群名.
        """
        await self.call_api("set_group_name", {
            "group_id": group_id,
            "group_name": group_name,
        })

    async def set_group_card(
        self, group_id: int, user_id: int, *, card: str = ""
    ) -> None:
        """修改群成员名片; 需要有相应权限(管理员/群主).

        ``card`` 为空字符串时表示删除群名片.

        Args:
            group_id (int): 群号.
            user_id (int): 目标群成员 QQ 号.
            card (str, optional): 新名片内容, 默认为空(删除名片).
        """
        await self.call_api("set_group_card", {
            "group_id": group_id,
            "user_id": user_id,
            "card": card,
        })

    async def set_group_leave(self, group_id: int, *, is_dismiss: bool = False) -> None:
        """退出群组; 若为群主且 ``is_dismiss`` 为 True 则解散群.

        Args:
            group_id (int): 群号.
            is_dismiss (bool, optional): 是否解散群 (仅群主生效), 默认为 False.
        """
        await self.call_api("set_group_leave", {
            "group_id": group_id,
            "is_dismiss": is_dismiss,
        })

    async def set_group_add_request(
        self,
        flag: str,
        sub_type: str,
        approve: bool = True,
        *,
        reason: str = "",
    ) -> None:
        """处理加群请求/邀请.

        Args:
            flag (str): 请求标识 (从 ``GroupRequestEvent`` 获取).
            sub_type (str): 请求子类型, ``"add"`` 或 ``"invite"``.
            approve (bool, optional): 是否同意, 默认为 True.
            reason (str, optional): 拒绝理由 (仅在拒绝时有效).
        """
        await self.call_api("set_group_add_request", {
            "flag": flag,
            "sub_type": sub_type,
            "approve": approve,
            "reason": reason,
        })

    async def get_group_honor_info(
        self, group_id: int, type: str = "all"
    ) -> GroupHonorInfo:
        """获取群荣誉信息.

        Args:
            group_id (int): 群号.
            type (str, optional): 荣誉类型, 可选 ``"talkative"`` / ``"performer"`` / \
                ``"legend"`` / ``"strong_newbie"`` / ``"emotion"`` / ``"all"``, 默认为 ``"all"``.

        Returns:
            GroupHonorInfo: 群荣誉信息.
        """
        data = await self.call_api("get_group_honor_info", {
            "group_id": group_id,
            "type": type,
        })
        return GroupHonorInfo.model_validate(data)

    async def get_essence_msg_list(self, group_id: int) -> list[EssenceMessage]:
        """获取群精华消息列表.

        Args:
            group_id (int): 群号.

        Returns:
            list[EssenceMessage]: 精华消息列表.
        """
        data = await self.call_api("get_essence_msg_list", {"group_id": group_id})
        return [EssenceMessage.model_validate(e) for e in (data or [])]

    async def set_essence_msg(self, message_id: int) -> None:
        """设置精华消息; 需要有相应权限(管理员/群主).

        Args:
            message_id (int): 消息 ID.
        """
        await self.call_api("set_essence_msg", {"message_id": message_id})

    async def delete_essence_msg(self, message_id: int) -> None:
        """移除精华消息; 需要有相应权限(管理员/群主).

        Args:
            message_id (int): 消息 ID.
        """
        await self.call_api("delete_essence_msg", {"message_id": message_id})

    async def send_group_notice(
        self, group_id: int, content: str, *, image: str = ""
    ) -> None:
        """发布群公告; 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            content (str): 公告内容.
            image (str, optional): 公告图片, 支持 URL 或 ``base64://`` 格式.
        """
        params: dict[str, Any] = {"group_id": group_id, "content": content}
        if image:
            params["image"] = image
        await self.call_api("_send_group_notice", params)

    async def get_group_notice(self, group_id: int) -> list[GroupNotice]:
        """获取群公告列表.

        Args:
            group_id (int): 群号.

        Returns:
            list[GroupNotice]: 群公告列表.
        """
        data = await self.call_api("_get_group_notice", {"group_id": group_id})
        return [GroupNotice.model_validate(n) for n in (data or [])]

    async def get_group_at_all_remain(self, group_id: int) -> dict[str, Any]:
        """获取群 @全体成员 剩余次数.

        Args:
            group_id (int): 群号.

        Returns:
            dict[str, Any]: 包含 ``can_at_all`` 等字段的信息.
        """
        return await self.call_api("get_group_at_all_remain", {"group_id": group_id})

    async def set_group_sign(self, group_id: int) -> None:
        """群打卡.

        Args:
            group_id (int): 群号.
        """
        await self.call_api("set_group_sign", {"group_id": group_id})

    async def send_group_sign(self, group_id: int) -> None:
        """发送群打卡 (别名).

        Args:
            group_id (int): 群号.
        """
        await self.call_api("send_group_sign", {"group_id": group_id})

    async def get_group_ignored_notifies(self, group_id: int) -> dict[str, Any]:
        """获取群内被过滤的系统通知.

        Args:
            group_id (int): 群号.

        Returns:
            dict[str, Any]: 被过滤的通知信息.
        """
        return await self.call_api("get_group_ignored_notifies", {"group_id": group_id})

    async def set_group_remark(self, group_id: int, remark: str) -> None:
        """设置群备注.

        Args:
            group_id (int): 群号.
            remark (str): 新的群备注.
        """
        await self.call_api("set_group_remark", {
            "group_id": group_id,
            "remark": remark,
        })

    # ── 群文件操作 ─────────────────────────────────────────────────────────

    async def get_group_root_files(self, group_id: int) -> GroupRootFiles:
        """获取群根目录文件列表.

        Args:
            group_id (int): 群号.

        Returns:
            GroupRootFiles: 群根目录下的文件和文件夹.
        """
        data = await self.call_api("get_group_root_files", {"group_id": group_id})
        return GroupRootFiles.model_validate(data)

    async def upload_group_file(
        self,
        group_id: int,
        file: str,
        name: str,
        *,
        folder: str = "",
    ) -> None:
        """上传群文件.

        Args:
            group_id (int): 群号.
            file (str): 文件路径或 URL.
            name (str): 上传后的文件名.
            folder (str, optional): 上传目录 ID, 默认为根目录.
        """
        await self.call_api("upload_group_file", {
            "group_id": group_id,
            "file": file,
            "name": name,
            "folder": folder,
        })

    async def move_group_file(
        self,
        group_id: int,
        file_id: str,
        parent_directory: str,
    ) -> None:
        """移动群文件.

        Args:
            group_id (int): 群号.
            file_id (str): 文件 ID.
            parent_directory (str): 目标文件夹 ID.
        """
        await self.call_api("move_group_file", {
            "group_id": group_id,
            "file_id": file_id,
            "parent_directory": parent_directory,
        })

    async def rename_group_file(
        self,
        group_id: int,
        file_id: str,
        new_name: str,
    ) -> None:
        """重命名群文件.

        Args:
            group_id (int): 群号.
            file_id (str): 文件 ID.
            new_name (str): 新文件名.
        """
        await self.call_api("rename_group_file", {
            "group_id": group_id,
            "file_id": file_id,
            "new_name": new_name,
        })

    async def trans_group_file(
        self,
        group_id: int,
        file_id: str,
    ) -> None:
        """转存群文件到自己的网盘.

        Args:
            group_id (int): 群号.
            file_id (str): 文件 ID.
        """
        await self.call_api("trans_group_file", {
            "group_id": group_id,
            "file_id": file_id,
        })

    # ── 群相册操作 (NapCat 扩展) ──────────────────────────────────────────

    async def get_qun_album_list(self, group_id: int) -> list[dict[str, Any]]:
        """获取群相册列表 (NapCat 扩展).

        Args:
            group_id (int): 群号.

        Returns:
            list[dict[str, Any]]: 群相册列表.
        """
        return await self.call_api("get_qun_album_list", {"group_id": group_id}) or []

    async def get_group_album_media_list(
        self, group_id: int, album_id: str, *, count: int = 20
    ) -> list[dict[str, Any]]:
        """获取群相册内的媒体文件列表 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            album_id (str): 相册 ID.
            count (int, optional): 获取数量, 默认为 20.

        Returns:
            list[dict[str, Any]]: 媒体文件列表.
        """
        return await self.call_api("get_group_album_media_list", {
            "group_id": group_id,
            "album_id": album_id,
            "count": count,
        }) or []

    async def upload_image_to_qun_album(
        self, group_id: int, image: str
    ) -> dict[str, Any]:
        """上传图片到群相册 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            image (str): 图片路径或 URL.

        Returns:
            dict[str, Any]: 上传结果.
        """
        return await self.call_api("upload_image_to_qun_album", {
            "group_id": group_id,
            "image": image,
        })

    async def del_group_album_media(
        self, group_id: int, album_id: str, media_id: str
    ) -> None:
        """删除群相册内的媒体文件 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            album_id (str): 相册 ID.
            media_id (str): 媒体文件 ID.
        """
        await self.call_api("del_group_album_media", {
            "group_id": group_id,
            "album_id": album_id,
            "media_id": media_id,
        })

    async def set_group_album_media_like(
        self, group_id: int, album_id: str, media_id: str
    ) -> None:
        """为群相册媒体文件点赞 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            album_id (str): 相册 ID.
            media_id (str): 媒体文件 ID.
        """
        await self.call_api("set_group_album_media_like", {
            "group_id": group_id,
            "album_id": album_id,
            "media_id": media_id,
        })

    async def do_group_album_comment(
        self, group_id: int, album_id: str, media_id: str, content: str
    ) -> None:
        """评论群相册媒体文件 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            album_id (str): 相册 ID.
            media_id (str): 媒体文件 ID.
            content (str): 评论内容.
        """
        await self.call_api("do_group_album_comment", {
            "group_id": group_id,
            "album_id": album_id,
            "media_id": media_id,
            "content": content,
        })

    # ══════════════════════════════════════════════════════════════════════
    #  系统接口
    # ══════════════════════════════════════════════════════════════════════

    async def get_status(self) -> StatusInfo:
        """获取运行状态.

        Returns:
            StatusInfo: 包含 ``online`` 和 ``good`` 等状态信息.
        """
        data = await self.call_api("get_status")
        return StatusInfo.model_validate(data)

    async def get_version_info(self) -> VersionInfo:
        """获取版本信息.

        Returns:
            VersionInfo: 包含 ``app_name``、``app_version``、``protocol_version`` 等信息.
        """
        data = await self.call_api("get_version_info")
        return VersionInfo.model_validate(data)

    async def get_cookies(self, *, domain: str = "") -> dict[str, Any]:
        """获取 Cookies.

        Args:
            domain (str, optional): 需要获取 cookies 的域名.

        Returns:
            dict[str, Any]: 包含 cookies 的结果.
        """
        return await self.call_api("get_cookies", {"domain": domain})

    async def can_send_image(self) -> bool:
        """检查是否可以发送图片.

        Returns:
            bool: 是否可以发送图片.
        """
        data = await self.call_api("can_send_image")
        return data.get("yes", False) if isinstance(data, dict) else bool(data)

    async def can_send_record(self) -> bool:
        """检查是否可以发送语音.

        Returns:
            bool: 是否可以发送语音.
        """
        data = await self.call_api("can_send_record")
        return data.get("yes", False) if isinstance(data, dict) else bool(data)

    async def set_online_status(
        self, status: int, ext_status: int = 0, battery_status: int = 0
    ) -> None:
        """设置在线状态 (NapCat 扩展).

        Args:
            status (int): 在线状态码.
            ext_status (int, optional): 扩展在线状态码, 默认为 0.
            battery_status (int, optional): 电量状态, 默认为 0.
        """
        await self.call_api("set_online_status", {
            "status": status,
            "ext_status": ext_status,
            "battery_status": battery_status,
        })

    async def get_online_clients(self) -> list[dict[str, Any]]:
        """获取在线客户端列表.

        Returns:
            list[dict[str, Any]]: 当前在线的客户端列表.
        """
        data = await self.call_api("get_online_clients")
        if isinstance(data, dict):
            return data.get("clients", [])
        return data or []

    async def get_robot_uin_range(self) -> list[dict[str, Any]]:
        """获取机器人 QQ 号段 (NapCat 扩展).

        Returns:
            list[dict[str, Any]]: QQ 号段列表.
        """
        return await self.call_api("get_robot_uin_range") or []

    async def get_clientkey(self) -> str:
        """获取 ClientKey (NapCat 扩展).

        Returns:
            str: ClientKey.
        """
        data = await self.call_api("get_clientkey")
        if isinstance(data, dict):
            return data.get("clientkey", "")
        return str(data) if data else ""

    async def get_rkey(self) -> list[dict[str, Any]]:
        """获取 RKey 列表 (NapCat 扩展).

        Returns:
            list[dict[str, Any]]: RKey 列表.
        """
        return await self.call_api("get_rkey") or []

    # ══════════════════════════════════════════════════════════════════════
    #  文件接口
    # ══════════════════════════════════════════════════════════════════════

    async def get_image(self, file: str) -> dict[str, Any]:
        """获取图片信息.

        Args:
            file (str): 图片缓存文件名.

        Returns:
            dict[str, Any]: 包含 ``file`` 路径等信息.
        """
        return await self.call_api("get_image", {"file": file})

    async def get_record(self, file: str, *, out_format: str = "mp3") -> dict[str, Any]:
        """获取语音文件信息.

        Args:
            file (str): 语音缓存文件名.
            out_format (str, optional): 输出格式, 默认为 ``"mp3"``.

        Returns:
            dict[str, Any]: 包含 ``file`` 路径等信息.
        """
        return await self.call_api("get_record", {
            "file": file,
            "out_format": out_format,
        })

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """获取文件信息 (NapCat 扩展).

        Args:
            file_id (str): 文件 ID.

        Returns:
            dict[str, Any]: 文件详细信息.
        """
        return await self.call_api("get_file", {"file_id": file_id})

    async def download_file(
        self,
        url: str,
        *,
        thread_count: int = 1,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """下载文件到缓存目录.

        Args:
            url (str): 文件 URL.
            thread_count (int, optional): 下载线程数, 默认为 1.
            headers (Optional[dict[str, str]], optional): 自定义请求头.

        Returns:
            dict[str, Any]: 包含 ``file`` 路径的结果.
        """
        params: dict[str, Any] = {"url": url, "thread_count": thread_count}
        if headers:
            params["headers"] = headers
        return await self.call_api("download_file", params)

    # ══════════════════════════════════════════════════════════════════════
    #  扩展 / NapCat 接口
    # ══════════════════════════════════════════════════════════════════════

    async def set_qq_profile(
        self,
        nickname: str,
        *,
        company: str = "",
        email: str = "",
        college: str = "",
        personal_note: str = "",
    ) -> None:
        """设置 QQ 个人资料.

        Args:
            nickname (str): 昵称.
            company (str, optional): 公司.
            email (str, optional): 邮箱.
            college (str, optional): 学校.
            personal_note (str, optional): 个性签名.
        """
        await self.call_api("set_qq_profile", {
            "nickname": nickname,
            "company": company,
            "email": email,
            "college": college,
            "personal_note": personal_note,
        })

    async def set_qq_avatar(self, file: str) -> None:
        """设置 QQ 头像 (NapCat 扩展).

        Args:
            file (str): 图片文件路径或 URL.
        """
        await self.call_api("set_qq_avatar", {"file": file})

    async def set_self_longnick(self, long_nick: str) -> None:
        """设置个人签名 (NapCat 扩展).

        Args:
            long_nick (str): 新的个性签名内容.
        """
        await self.call_api("set_self_longnick", {"long_nick": long_nick})

    async def ocr_image(self, image: str) -> dict[str, Any]:
        """OCR 图片识别.

        Args:
            image (str): 图片文件路径、URL 或收到的图片 ``file`` 字段.

        Returns:
            dict[str, Any]: OCR 识别结果.
        """
        return await self.call_api("ocr_image", {"image": image})

    async def translate_en2zh(self, words: list[str]) -> list[str]:
        """英译中 (NapCat 扩展).

        Args:
            words (list[str]): 需要翻译的英文单词/短语列表.

        Returns:
            list[str]: 对应的中文翻译结果.
        """
        data = await self.call_api("translate_en2zh", {"words": words})
        return data if isinstance(data, list) else []

    async def check_url_safely(self, url: str) -> dict[str, Any]:
        """检查链接安全性.

        Args:
            url (str): 需要检查的 URL.

        Returns:
            dict[str, Any]: 安全性检查结果.
        """
        return await self.call_api("check_url_safely", {"url": url})

    async def create_collection(
        self, raw_data: str, brief: str
    ) -> None:
        """创建收藏 (NapCat 扩展).

        Args:
            raw_data (str): 收藏原始数据.
            brief (str): 收藏摘要.
        """
        await self.call_api("create_collection", {
            "rawData": raw_data,
            "brief": brief,
        })

    async def send_group_ark_share(
        self, group_id: int, url: str
    ) -> dict[str, Any]:
        """发送群 Ark 卡片分享 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            url (str): 分享的 URL.

        Returns:
            dict[str, Any]: 发送结果.
        """
        return await self.call_api("send_group_ark_share", {
            "group_id": group_id,
            "url": url,
        })

    async def send_ark_share(
        self, user_id: int, url: str
    ) -> dict[str, Any]:
        """发送私聊 Ark 卡片分享 (NapCat 扩展).

        Args:
            user_id (int): 目标 QQ 号.
            url (str): 分享的 URL.

        Returns:
            dict[str, Any]: 发送结果.
        """
        return await self.call_api("send_ark_share", {
            "user_id": user_id,
            "url": url,
        })

    async def ark_share_group(
        self, group_id: int, url: str
    ) -> dict[str, Any]:
        """Ark 分享到群 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            url (str): 分享的 URL.

        Returns:
            dict[str, Any]: 发送结果.
        """
        return await self.call_api("ArkShareGroup", {
            "group_id": group_id,
            "url": url,
        })

    async def ark_share_peer(
        self, user_id: int, url: str
    ) -> dict[str, Any]:
        """Ark 分享到好友 (NapCat 扩展).

        Args:
            user_id (int): 目标 QQ 号.
            url (str): 分享的 URL.

        Returns:
            dict[str, Any]: 发送结果.
        """
        return await self.call_api("ArkSharePeer", {
            "user_id": user_id,
            "url": url,
        })

    async def get_guild_list(self) -> list[dict[str, Any]]:
        """获取频道列表.

        Returns:
            list[dict[str, Any]]: 频道列表.
        """
        return await self.call_api("get_guild_list") or []

    # ── 流式传输接口 (NapCat 扩展) ────────────────────────────────────────

    async def upload_file_stream(self, file: str, name: str) -> dict[str, Any]:
        """流式上传文件 (NapCat 扩展).

        Args:
            file (str): 文件路径.
            name (str): 文件名.

        Returns:
            dict[str, Any]: 上传结果.
        """
        return await self.call_api("upload_file_stream", {"file": file, "name": name})

    async def download_file_stream(self, file_id: str) -> dict[str, Any]:
        """流式下载文件 (NapCat 扩展).

        Args:
            file_id (str): 文件 ID.

        Returns:
            dict[str, Any]: 下载结果.
        """
        return await self.call_api("download_file_stream", {"file_id": file_id})

    async def clean_stream_temp_file(self) -> None:
        """清理流式传输临时文件 (NapCat 扩展)."""
        await self.call_api("clean_stream_temp_file")

    # ── 群组扩展接口 ──────────────────────────────────────────────────────

    async def set_group_kick_members(
        self,
        group_id: int,
        user_ids: list[int],
        *,
        reject_add_request: bool = False,
    ) -> None:
        """批量踢出群成员 (NapCat 扩展); 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            user_ids (list[int]): 要踢出的群成员 QQ 号列表.
            reject_add_request (bool, optional): 是否拒绝此人的加群请求, 默认为 False.
        """
        await self.call_api("set_group_kick_members", {
            "group_id": group_id,
            "user_ids": user_ids,
            "reject_add_request": reject_add_request,
        })

    async def set_group_todo(
        self,
        group_id: int,
        message_id: int,
    ) -> None:
        """设置群待办 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            message_id (int): 要设为待办的消息 ID.
        """
        await self.call_api("set_group_todo", {
            "group_id": group_id,
            "message_id": message_id,
        })

    async def set_group_search(self, group_id: int, keyword: str) -> dict[str, Any]:
        """群内搜索 (NapCat 扩展).

        Args:
            group_id (int): 群号.
            keyword (str): 搜索关键词.

        Returns:
            dict[str, Any]: 搜索结果.
        """
        return await self.call_api("set_group_search", {
            "group_id": group_id,
            "keyword": keyword,
        })

    async def set_group_add_option(
        self, group_id: int, option: int
    ) -> None:
        """设置加群方式 (NapCat 扩展); 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            option (int): 加群方式选项.
        """
        await self.call_api("set_group_add_option", {
            "group_id": group_id,
            "option": option,
        })

    async def set_group_robot_add_option(
        self, group_id: int, option: int
    ) -> None:
        """设置群机器人添加方式 (NapCat 扩展); 需要有相应权限(管理员/群主).

        Args:
            group_id (int): 群号.
            option (int): 机器人添加方式选项.
        """
        await self.call_api("set_group_robot_add_option", {
            "group_id": group_id,
            "option": option,
        })

    # ── 可疑好友请求 (NapCat 扩展) ────────────────────────────────────────

    async def get_doubt_friends_add_request(self) -> list[dict[str, Any]]:
        """获取可疑的好友添加请求列表 (NapCat 扩展).

        Returns:
            list[dict[str, Any]]: 可疑好友请求列表.
        """
        return await self.call_api("get_doubt_friends_add_request") or []

    async def set_doubt_friends_add_request(
        self, flag: str, approve: bool = True
    ) -> None:
        """处理可疑的好友添加请求 (NapCat 扩展).

        Args:
            flag (str): 请求标识.
            approve (bool, optional): 是否同意, 默认为 True.
        """
        await self.call_api("set_doubt_friends_add_request", {
            "flag": flag,
            "approve": approve,
        })

    # ── 表情回应 (NapCat 扩展) ────────────────────────────────────────────

    async def get_emoji_likes(self, message_id: int) -> list[dict[str, Any]]:
        """获取消息的表情回应列表 (NapCat 扩展).

        Args:
            message_id (int): 消息 ID.

        Returns:
            list[dict[str, Any]]: 表情回应列表.
        """
        return await self.call_api("get_emoji_likes", {"message_id": message_id}) or []

    async def fetch_emoji_like(
        self,
        message_id: int,
        emoji_id: str,
        emoji_type: str = "",
    ) -> dict[str, Any]:
        """获取消息的特定表情回应详情 (NapCat 扩展).

        Args:
            message_id (int): 消息 ID.
            emoji_id (str): 表情 ID.
            emoji_type (str, optional): 表情类型.

        Returns:
            dict[str, Any]: 表情回应详情.
        """
        return await self.call_api("fetch_emoji_like", {
            "message_id": message_id,
            "emoji_id": emoji_id,
            "emoji_type": emoji_type,
        })
