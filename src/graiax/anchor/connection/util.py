"""连接工具: 响应校验与事件构建"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ..event import OneBotEvent
from ..event.lifecycle import HeartbeatEvent, LifecycleEvent
from ..event.message import (
    GroupMessageEvent,
    MessageSentEvent,
    PrivateMessageEvent,
)
from ..event.notice import (
    BotOfflineNotice,
    FriendAddNotice,
    FriendPokeNotice,
    FriendRecallNotice,
    GroupAdminNotice,
    GroupBanNotice,
    GroupCardNotice,
    GroupDecreaseNotice,
    GroupEssenceNotice,
    GroupGrayTipNotice,
    GroupIncreaseNotice,
    GroupMsgEmojiLikeNotice,
    GroupNameNotice,
    GroupPokeNotice,
    GroupRecallNotice,
    GroupTitleNotice,
    GroupUploadNotice,
    HonorNotice,
    InputStatusNotice,
    LuckyKingNotice,
    PokeNotice,
    ProfileLikeNotice,
)
from ..event.request import FriendRequestEvent, GroupRequestEvent
from ..exception import (
    BadRequestError,
    NotFoundError,
    OneBotApiError,
    UnauthorizedError,
)


def validate_response(data: dict[str, Any]) -> Any:
    """校验 OneBot 11 API 响应并提取 data 字段.

    Args:
        data (dict[str, Any]): 原始 API 响应.

    Raises:
        BadRequestError: 错误码 1400.
        UnauthorizedError: 错误码 1401.
        NotFoundError: 错误码 1404.
        OneBotApiError: 其他错误码.

    Returns:
        Any: 响应中的 ``data`` 字段.
    """
    status = data.get("status", "")
    retcode = data.get("retcode", 0)

    if status == "ok" or retcode == 0:
        return data.get("data")

    message = data.get("message", "")
    wording = data.get("wording", "")

    exc_map: dict[int, type[OneBotApiError]] = {
        1400: BadRequestError,
        1401: UnauthorizedError,
        1404: NotFoundError,
    }
    exc_cls = exc_map.get(retcode, OneBotApiError)
    raise exc_cls(retcode, message, wording, data)


# ── 通知事件分发表 ────────────────────────────────────────────────────────────

_NOTICE_TYPE_MAP: dict[str, type[OneBotEvent]] = {
    "friend_add": FriendAddNotice,
    "friend_recall": FriendRecallNotice,
    "group_recall": GroupRecallNotice,
    "group_increase": GroupIncreaseNotice,
    "group_decrease": GroupDecreaseNotice,
    "group_admin": GroupAdminNotice,
    "group_ban": GroupBanNotice,
    "group_upload": GroupUploadNotice,
    "group_card": GroupCardNotice,
    "essence": GroupEssenceNotice,
    "group_msg_emoji_like": GroupMsgEmojiLikeNotice,
    "bot_offline": BotOfflineNotice,
}

_NOTIFY_SUBTYPE_MAP: dict[str, type[OneBotEvent]] = {
    "poke": PokeNotice,
    "profile_like": ProfileLikeNotice,
    "input_status": InputStatusNotice,
    "group_name": GroupNameNotice,
    "title": GroupTitleNotice,
    "gray_tip": GroupGrayTipNotice,
    "lucky_king": LuckyKingNotice,
    "honor": HonorNotice,
}


def _resolve_poke(data: dict[str, Any]) -> type[OneBotEvent]:
    """根据是否存在 group_id 区分群戳一戳和好友戳一戳."""
    if data.get("group_id"):
        return GroupPokeNotice
    return FriendPokeNotice


def build_event(data: dict[str, Any]) -> OneBotEvent:
    """从原始 JSON 字典构建类型化的 OneBotEvent.

    分发逻辑:

    1. ``post_type`` → 大分类
    2. ``message``: ``message_type`` → ``PrivateMessageEvent`` / ``GroupMessageEvent``
    3. ``notice``: ``notice_type`` → 具体通知; ``notify`` 进一步按 ``sub_type`` 分发
    4. ``request``: ``request_type`` → ``FriendRequestEvent`` / ``GroupRequestEvent``
    5. ``meta_event``: ``meta_event_type`` → ``HeartbeatEvent`` / ``LifecycleEvent``

    Args:
        data (dict[str, Any]): 原始事件 JSON 数据.

    Returns:
        OneBotEvent: 类型化的事件实例.
    """
    post_type = data.get("post_type", "")

    # ── message ──────────────────────────────────────────────────────────
    if post_type in ("message", "message_sent"):
        msg_type = data.get("message_type", "")
        if post_type == "message_sent":
            return MessageSentEvent.model_validate(data)
        if msg_type == "private":
            return PrivateMessageEvent.model_validate(data)
        if msg_type == "group":
            return GroupMessageEvent.model_validate(data)
        logger.warning(f"Unknown message_type: {msg_type}")
        return OneBotEvent.model_validate(data)

    # ── notice ───────────────────────────────────────────────────────────
    if post_type == "notice":
        notice_type = data.get("notice_type", "")
        if notice_type == "notify":
            sub_type = data.get("sub_type", "")
            if sub_type == "poke":
                cls = _resolve_poke(data)
            else:
                cls = _NOTIFY_SUBTYPE_MAP.get(sub_type, OneBotEvent)
            return cls.model_validate(data)
        cls = _NOTICE_TYPE_MAP.get(notice_type, OneBotEvent)
        return cls.model_validate(data)

    # ── request ──────────────────────────────────────────────────────────
    if post_type == "request":
        req_type = data.get("request_type", "")
        if req_type == "friend":
            return FriendRequestEvent.model_validate(data)
        if req_type == "group":
            return GroupRequestEvent.model_validate(data)
        logger.warning(f"Unknown request_type: {req_type}")
        return OneBotEvent.model_validate(data)

    # ── meta_event ───────────────────────────────────────────────────────
    if post_type == "meta_event":
        meta_type = data.get("meta_event_type", "")
        if meta_type == "heartbeat":
            return HeartbeatEvent.model_validate(data)
        if meta_type == "lifecycle":
            return LifecycleEvent.model_validate(data)
        return OneBotEvent.model_validate(data)

    logger.warning(f"Unknown post_type: {post_type}")
    return OneBotEvent.model_validate(data)
