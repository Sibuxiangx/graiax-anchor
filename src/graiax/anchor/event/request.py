"""请求事件: 好友添加请求与加群请求"""

from __future__ import annotations

from . import OneBotEvent


class RequestEvent(OneBotEvent):
    """所有请求事件的基类.

    Attributes:
        request_type: 请求类型, ``friend`` 或 ``group``.
        user_id: 发送请求的用户 QQ 号.
        comment: 验证信息.
        flag: 请求标识, 用于处理请求时传入.
    """

    post_type: str = "request"
    request_type: str = ""
    user_id: int = 0
    comment: str = ""
    flag: str = ""


class FriendRequestEvent(RequestEvent):
    """好友添加请求事件.

    通过 ``Anchor.set_friend_add_request()`` 处理此请求.
    """

    request_type: str = "friend"


class GroupRequestEvent(RequestEvent):
    """加群请求 / 邀请事件.

    通过 ``Anchor.set_group_add_request()`` 处理此请求.

    Attributes:
        sub_type: 子类型, ``add`` (主动加群) 或 ``invite`` (被邀请).
        group_id: 群号.
    """

    request_type: str = "group"
    sub_type: str = ""
    group_id: int = 0
