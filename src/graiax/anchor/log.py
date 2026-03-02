"""Anchor 日志系统

提供 ``LogConfig`` 类, 为各类事件定义格式化日志模板,
收发消息时自动打印可读的日志. 风格延续 Ariadne 的 ``[RECV]`` / ``[SEND]`` 标签设计.

同时提供 loguru 异常回调, 用于替换默认的 ``sys.excepthook`` 和 asyncio 异常处理器,
以便统一通过 loguru 输出所有异常信息.
"""

from __future__ import annotations

import functools
import sys
import traceback
from collections.abc import Awaitable, Callable
from typing import (
    TYPE_CHECKING,
    Any,
)

from graia.broadcast.exceptions import ExecutionStop, PropagationCancelled
from loguru import logger

if TYPE_CHECKING:
    from .app import Anchor
    from .event import OneBotEvent


class LogConfig(dict[type["OneBotEvent"], str | None]):
    """事件日志配置.

    为每种事件类型关联一个格式化模板, 事件触发时自动格式化并输出日志.
    模板中可使用 ``{event}`` 和 ``{anchor}`` 占位符.

    Usage::

        from graiax.anchor.log import LogConfig

        log_config = LogConfig()
        app = Anchor(broadcast=broadcast, config=config, log_config=log_config)

    自定义日志级别::

        log_config = LogConfig(log_level="DEBUG")

    禁用特定事件的日志::

        from graiax.anchor.event.notice import GroupRecallNotice
        log_config = LogConfig(extra={GroupRecallNotice: None})
    """

    def __init__(
        self,
        log_level: str | Callable[[OneBotEvent], str | None] = "INFO",
        extra: dict[type[OneBotEvent], str | None] | None = None,
    ) -> None:
        """初始化日志配置.

        Args:
            log_level: 日志级别, 可以是字符串 (如 ``"INFO"``) 或一个接收事件返回级别的函数.
            extra: 额外的事件日志格式覆盖, 值为 ``None`` 表示禁用该事件的日志.
        """
        from .event.message import GroupMessageEvent, MessageSentEvent, PrivateMessageEvent
        from .event.notice import (
            FriendAddNotice,
            FriendRecallNotice,
            GroupAdminNotice,
            GroupBanNotice,
            GroupDecreaseNotice,
            GroupEssenceNotice,
            GroupIncreaseNotice,
            GroupPokeNotice,
            GroupRecallNotice,
        )
        from .event.request import FriendRequestEvent, GroupRequestEvent

        super().__init__()

        self.log_level: Callable[[OneBotEvent], str | None] = (
            log_level if callable(log_level) else lambda _: log_level
        )

        self.update({
            GroupMessageEvent: (
                "{anchor.account}: [RECV][群:{event.group_id}] "
                "{event.sender.nickname}({event.sender.user_id}) -> "
                "{event.message_chain.safe_display}"
            ),
            PrivateMessageEvent: (
                "{anchor.account}: [RECV][私:{event.user_id}] "
                "{event.sender.nickname}({event.sender.user_id}) -> "
                "{event.message_chain.safe_display}"
            ),
            MessageSentEvent: (
                "{anchor.account}: [SEND][-> {event.target_id}] <- "
                "{event.message_chain.safe_display}"
            ),

            GroupIncreaseNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.user_id} 加入了群聊"
            ),
            GroupDecreaseNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.user_id} 离开了群聊 ({event.sub_type})"
            ),
            GroupRecallNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.operator_id} 撤回了 {event.user_id} 的消息 {event.message_id}"
            ),
            FriendRecallNotice: (
                "{anchor.account}: [通知] {event.user_id} 撤回了消息 {event.message_id}"
            ),
            GroupAdminNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.user_id} 被{event.sub_type}管理员"
            ),
            GroupBanNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.user_id} 被{event.sub_type} {event.duration}秒"
            ),
            FriendAddNotice: (
                "{anchor.account}: [通知] 新好友 {event.user_id}"
            ),
            GroupPokeNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "{event.user_id} 戳了 {event.target_id}"
            ),
            GroupEssenceNotice: (
                "{anchor.account}: [通知][群:{event.group_id}] "
                "精华消息 {event.sub_type}: {event.message_id}"
            ),

            FriendRequestEvent: (
                "{anchor.account}: [请求] 好友申请: {event.user_id} ({event.comment})"
            ),
            GroupRequestEvent: (
                "{anchor.account}: [请求] 加群申请: {event.user_id} -> 群 {event.group_id} ({event.comment})"
            ),
        })

        if extra:
            self.update(extra)

    def event_hook(self, anchor: Anchor) -> Callable[[OneBotEvent], Awaitable[None]]:
        """创建绑定到指定 Anchor 实例的事件回调.

        Args:
            anchor: Anchor 实例.

        Returns:
            事件回调函数.
        """
        return functools.partial(self.log, anchor)

    async def log(self, anchor: Anchor, event: OneBotEvent) -> None:
        """根据事件类型格式化并输出日志.

        Args:
            anchor: 当前 Anchor 实例.
            event: 触发的事件.
        """
        log_level = self.log_level(event)
        fmt = self.get(type(event))
        if log_level and fmt:
            try:
                logger.log(log_level, fmt.format(event=event, anchor=anchor))
            except (AttributeError, KeyError, IndexError):
                logger.log(log_level, f"{type(event).__name__}: {event.model_dump(exclude_defaults=True)}")

    def log_send(
        self,
        anchor: Anchor,
        target_type: str,
        target_id: int,
        chain_display: str,
    ) -> None:
        """记录主动发送消息的日志.

        Args:
            anchor: 当前 Anchor 实例.
            target_type: 目标类型, ``"群"`` 或 ``"私"``.
            target_id: 目标 ID.
            chain_display: 消息链的安全显示文本.
        """
        logger.info(f"{anchor.account}: [SEND][{target_type}:{target_id}] <- {chain_display}")


# ── 异常回调 ──────────────────────────────────────────────────────────────────


def loguru_exc_callback(
    cls: type[BaseException],
    val: BaseException,
    tb: Any,
    *_: Any,
    **__: Any,
) -> None:
    """loguru 同步异常回调, 用于替换 ``sys.excepthook``.

    过滤掉 graia-broadcast 的 ``ExecutionStop`` 和 ``PropagationCancelled``.
    """
    if not issubclass(cls, (ExecutionStop, PropagationCancelled)):
        logger.opt(exception=(cls, val, tb)).error("Exception:")


def loguru_exc_callback_async(loop: Any, context: dict) -> None:
    """loguru 异步异常回调, 用于替换 ``asyncio.loop.set_exception_handler``.

    过滤掉 graia-broadcast 相关的内部异常.
    """
    message = context.get("message", "Unhandled exception in event loop")
    exception = context.get("exception")
    if exception is None:
        exc_info: Any = False
    elif isinstance(exception, (ExecutionStop, PropagationCancelled)):
        return
    else:
        exc_info = (type(exception), exception, exception.__traceback__)

    log_lines = [message]
    for key in sorted(context):
        if key in {"message", "exception"}:
            continue
        log_lines.append(f"  {key}: {context[key]!r}")

    logger.opt(exception=exc_info).error("\n".join(log_lines))


def install_log_hooks() -> None:
    """安装 loguru 异常回调到 sys.excepthook 和 traceback.print_exception."""
    sys.excepthook = loguru_exc_callback  # type: ignore[assignment]
    traceback.print_exception = loguru_exc_callback  # type: ignore[assignment]


def install_richuru() -> None:
    """尝试安装 richuru 以获得更美观的日志输出.

    如果 richuru 未安装则静默跳过.
    """
    try:
        import richuru
        richuru.install()
    except ImportError:
        pass
