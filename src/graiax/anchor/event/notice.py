"""通知事件: 群通知与好友通知"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..model.util import AnchorBaseModel
from . import OneBotEvent

# ── 基类 ──────────────────────────────────────────────────────────────────────


class NoticeEvent(OneBotEvent):
    """所有通知事件的基类.

    Attributes:
        notice_type: 通知类型.
    """

    post_type: str = "notice"
    notice_type: str = ""


class GroupNoticeEvent(NoticeEvent):
    """群相关通知事件的基类.

    Attributes:
        group_id: 群号.
        user_id: 相关用户 QQ 号.
    """

    group_id: int = 0
    user_id: int = 0


# ── 好友通知 ──────────────────────────────────────────────────────────────────


class FriendAddNotice(NoticeEvent):
    """好友添加成功通知.

    Attributes:
        user_id: 新好友 QQ 号.
    """

    notice_type: str = "friend_add"
    user_id: int = 0


class FriendRecallNotice(NoticeEvent):
    """好友消息撤回通知.

    Attributes:
        user_id: 撤回消息的用户 QQ 号.
        message_id: 被撤回的消息 ID.
    """

    notice_type: str = "friend_recall"
    user_id: int = 0
    message_id: int = 0


# ── 群通知 ────────────────────────────────────────────────────────────────────


class GroupRecallNotice(GroupNoticeEvent):
    """群消息撤回通知.

    Attributes:
        operator_id: 操作者 QQ 号 (撤回他人消息时为管理员).
        message_id: 被撤回的消息 ID.
    """

    notice_type: str = "group_recall"
    operator_id: int = 0
    message_id: int = 0


class GroupIncreaseNotice(GroupNoticeEvent):
    """群成员增加通知.

    Attributes:
        sub_type: 子类型, ``approve`` (管理员同意) 或 ``invite`` (被邀请).
        operator_id: 操作者 QQ 号.
    """

    notice_type: str = "group_increase"
    sub_type: str = ""
    operator_id: int = 0


class GroupDecreaseNotice(GroupNoticeEvent):
    """群成员减少通知.

    Attributes:
        sub_type: 子类型, ``leave`` (主动退群) / ``kick`` (被踢) / \
            ``kick_me`` (登录号被踢) / ``disband`` (群解散).
        operator_id: 操作者 QQ 号.
    """

    notice_type: str = "group_decrease"
    sub_type: str = ""
    operator_id: int = 0


class GroupAdminNotice(GroupNoticeEvent):
    """群管理员变动通知.

    Attributes:
        sub_type: 子类型, ``set`` (设置管理员) 或 ``unset`` (取消管理员).
    """

    notice_type: str = "group_admin"
    sub_type: str = ""


class GroupBanNotice(GroupNoticeEvent):
    """群禁言通知.

    Attributes:
        sub_type: 子类型, ``ban`` (禁言) 或 ``lift_ban`` (解除禁言).
        operator_id: 操作者 QQ 号.
        duration: 禁言时长 (秒); 解除禁言时为 0.
    """

    notice_type: str = "group_ban"
    sub_type: str = ""
    operator_id: int = 0
    duration: int = 0


class GroupUploadFile(AnchorBaseModel):
    """群文件上传中的文件信息.

    Attributes:
        id: 文件 ID.
        name: 文件名.
        size: 文件大小 (字节).
        busid: 业务 ID.
    """

    id: str = ""
    name: str = ""
    size: int = 0
    busid: int = 0


class GroupUploadNotice(GroupNoticeEvent):
    """群文件上传通知.

    Attributes:
        file: 上传的文件信息.
    """

    notice_type: str = "group_upload"
    file: GroupUploadFile = Field(default_factory=GroupUploadFile)


class GroupCardNotice(GroupNoticeEvent):
    """群成员名片变更通知.

    Attributes:
        card_new: 新名片.
        card_old: 旧名片.
    """

    notice_type: str = "group_card"
    card_new: str = ""
    card_old: str = ""


class GroupEssenceNotice(GroupNoticeEvent):
    """群精华消息变动通知.

    Attributes:
        sub_type: 子类型, ``add`` (设为精华) 或 ``delete`` (移除精华).
        message_id: 消息 ID.
        sender_id: 消息发送者 QQ 号.
        operator_id: 操作者 QQ 号.
    """

    notice_type: str = "essence"
    sub_type: str = ""
    message_id: int = 0
    sender_id: int = 0
    operator_id: int = 0


class GroupMsgEmojiLikeNotice(GroupNoticeEvent):
    """群消息表情回应通知.

    Attributes:
        message_id: 消息 ID.
        likes: 表情回应列表.
    """

    notice_type: str = "group_msg_emoji_like"
    message_id: int = 0
    likes: list[dict[str, Any]] = Field(default_factory=list)


# ── notify 子类型事件 (notice_type='notify') ─────────────────────────────────


class NotifyEvent(NoticeEvent):
    """``notice_type='notify'`` 的基类, 进一步按 ``sub_type`` 分发.

    Attributes:
        sub_type: 通知子类型.
    """

    notice_type: str = "notify"
    sub_type: str = ""


class PokeNotice(NotifyEvent):
    """戳一戳事件.

    Attributes:
        user_id: 发起戳一戳的用户 QQ 号.
        target_id: 被戳的用户 QQ 号.
        group_id: 群号 (群内戳一戳时有值).
        sender_id: 发送者 QQ 号 (NapCat 扩展字段).
    """

    sub_type: str = "poke"
    user_id: int = 0
    target_id: int = 0
    group_id: int = 0
    raw_info: Any | None = None
    sender_id: int = 0


class FriendPokeNotice(PokeNotice):
    """好友间的戳一戳事件."""

    pass


class GroupPokeNotice(PokeNotice):
    """群内的戳一戳事件."""

    pass


class ProfileLikeNotice(NotifyEvent):
    """个人资料被点赞通知 (NapCat 扩展).

    Attributes:
        operator_id: 点赞者 QQ 号.
        operator_nick: 点赞者昵称.
        times: 点赞次数.
    """

    sub_type: str = "profile_like"
    operator_id: int = 0
    operator_nick: str = ""
    times: int = 0


class InputStatusNotice(NotifyEvent):
    """用户输入状态变更通知 (NapCat 扩展).

    Attributes:
        status_text: 状态文本.
        event_type: 事件类型码.
        user_id: 用户 QQ 号.
        group_id: 群号 (如适用).
    """

    sub_type: str = "input_status"
    status_text: str = ""
    event_type: int = 0
    user_id: int = 0
    group_id: int = 0


class GroupNameNotice(NotifyEvent):
    """群名称变更通知 (NapCat 扩展).

    Attributes:
        group_id: 群号.
        user_id: 修改者 QQ 号.
        name_new: 新群名.
    """

    sub_type: str = "group_name"
    group_id: int = 0
    user_id: int = 0
    name_new: str = ""


class GroupTitleNotice(NotifyEvent):
    """群成员头衔变更通知.

    Attributes:
        group_id: 群号.
        user_id: 被授予头衔的成员 QQ 号.
        title: 新头衔.
    """

    sub_type: str = "title"
    group_id: int = 0
    user_id: int = 0
    title: str = ""


class GroupGrayTipNotice(NotifyEvent):
    """群灰色提示消息 (NapCat 扩展).

    Attributes:
        group_id: 群号.
        user_id: 相关用户 QQ 号.
        message_id: 消息 ID.
        busi_id: 业务 ID.
        content: 提示内容.
    """

    sub_type: str = "gray_tip"
    group_id: int = 0
    user_id: int = 0
    message_id: int = 0
    busi_id: str = ""
    content: str = ""
    raw_info: Any | None = None


class LuckyKingNotice(NotifyEvent):
    """群红包运气王通知.

    Attributes:
        group_id: 群号.
        user_id: 发红包的用户 QQ 号.
        target_id: 运气王 QQ 号.
    """

    sub_type: str = "lucky_king"
    group_id: int = 0
    user_id: int = 0
    target_id: int = 0


class HonorNotice(NotifyEvent):
    """群荣誉变更通知.

    Attributes:
        group_id: 群号.
        user_id: 获得荣誉的用户 QQ 号.
        honor_type: 荣誉类型.
    """

    sub_type: str = "honor"
    group_id: int = 0
    user_id: int = 0
    honor_type: str = ""


# ── 机器人离线 ────────────────────────────────────────────────────────────────


class BotOfflineNotice(NoticeEvent):
    """机器人离线通知 (NapCat 扩展).

    Attributes:
        user_id: 机器人 QQ 号.
        tag: 离线标签.
        message: 离线原因描述.
    """

    notice_type: str = "bot_offline"
    user_id: int = 0
    tag: str = ""
    message: str = ""
