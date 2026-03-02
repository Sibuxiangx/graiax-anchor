"""OneBot 11 关系模型: 好友、群、群成员、陌生人等"""

from __future__ import annotations

import functools
from enum import Enum
from typing import Any

from pydantic import Field

from .util import AnchorBaseModel

_MEMBER_ROLE_LV: dict[str, int] = {
    "member": 1,
    "admin": 2,
    "owner": 3,
}

_MEMBER_ROLE_REPR: dict[str, str] = {
    "member": "<普通成员>",
    "admin": "<管理员>",
    "owner": "<群主>",
}


@functools.total_ordering
class MemberRole(str, Enum):
    """群成员角色.

    支持比较运算: ``Member < Admin < Owner``.
    """

    Member = "member"
    """普通成员"""
    Admin = "admin"
    """管理员"""
    Owner = "owner"
    """群主"""

    def __lt__(self, other: MemberRole) -> bool:
        return _MEMBER_ROLE_LV[self.value] < _MEMBER_ROLE_LV[other.value]

    def __repr__(self) -> str:
        return _MEMBER_ROLE_REPR.get(self.value, self.value)

    def __str__(self) -> str:
        return self.value


class Sex(str, Enum):
    """用户性别."""

    Male = "male"
    Female = "female"
    Unknown = "unknown"


class User(AnchorBaseModel):
    """OneBot 11 用户基类.

    Attributes:
        user_id: QQ 号.
        nickname: 昵称.
    """

    user_id: int
    nickname: str = ""

    def __int__(self) -> int:
        return self.user_id

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, User) and self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)

    def __str__(self) -> str:
        return f"{self.nickname}({self.user_id})"


class Friend(User):
    """好友.

    Attributes:
        remark: 好友备注.
    """

    remark: str = ""

    def __str__(self) -> str:
        display = self.remark or self.nickname
        return f"{display}({self.user_id})"


class Stranger(User):
    """陌生人.

    Attributes:
        sex: 性别.
        age: 年龄.
        qid: QID.
        level: 等级.
        login_days: 连续登录天数.
    """

    sex: Sex = Sex.Unknown
    age: int = 0
    qid: str = ""
    level: int = 0
    login_days: int = Field(0, alias="login_days")


class FriendWithCategory(Friend):
    """带分组信息的好友.

    Attributes:
        category_id: 分组 ID.
        category_name: 分组名称.
    """

    category_id: int = Field(0, alias="categoryId")
    category_name: str = Field("", alias="categoryName")


class Group(AnchorBaseModel):
    """QQ 群.

    Attributes:
        group_id: 群号.
        group_name: 群名.
        member_count: 当前成员数.
        max_member_count: 最大成员数.
    """

    group_id: int
    group_name: str = ""
    member_count: int = 0
    max_member_count: int = 0

    def __int__(self) -> int:
        return self.group_id

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Group) and self.group_id == other.group_id

    def __hash__(self) -> int:
        return hash(self.group_id)

    def __str__(self) -> str:
        return f"{self.group_name}({self.group_id})"


class GroupSender(AnchorBaseModel):
    """群消息事件中的发送者信息.

    Attributes:
        user_id: QQ 号.
        nickname: 昵称.
        card: 群名片.
        sex: 性别.
        age: 年龄.
        area: 地区.
        level: 等级.
        role: 群角色.
        title: 专属头衔.
    """

    user_id: int = 0
    nickname: str = ""
    card: str = ""
    sex: Sex = Sex.Unknown
    age: int = 0
    area: str = ""
    level: str = ""
    role: MemberRole = MemberRole.Member
    title: str = ""

    def __int__(self) -> int:
        return self.user_id


class FriendSender(AnchorBaseModel):
    """私聊消息事件中的发送者信息.

    Attributes:
        user_id: QQ 号.
        nickname: 昵称.
        sex: 性别.
        age: 年龄.
    """

    user_id: int = 0
    nickname: str = ""
    sex: Sex = Sex.Unknown
    age: int = 0

    def __int__(self) -> int:
        return self.user_id


class Member(AnchorBaseModel):
    """群成员.

    Attributes:
        group_id: 群号.
        user_id: QQ 号.
        nickname: 昵称.
        card: 群名片.
        sex: 性别.
        age: 年龄.
        area: 地区.
        join_time: 入群时间 (Unix 时间戳).
        last_sent_time: 最后发言时间 (Unix 时间戳).
        level: 等级.
        role: 群角色.
        unfriendly: 是否不良记录成员.
        title: 专属头衔.
        title_expire_time: 头衔过期时间 (Unix 时间戳).
        card_changeable: 是否允许修改群名片.
        shut_up_timestamp: 禁言到期时间 (Unix 时间戳).
    """

    group_id: int = 0
    user_id: int = 0
    nickname: str = ""
    card: str = ""
    sex: Sex = Sex.Unknown
    age: int = 0
    area: str = ""
    join_time: int = 0
    last_sent_time: int = 0
    level: str = "0"
    role: MemberRole = MemberRole.Member
    unfriendly: bool = False
    title: str = ""
    title_expire_time: int = 0
    card_changeable: bool = False
    shut_up_timestamp: int = 0

    @property
    def display_name(self) -> str:
        """获取显示名称; 优先使用群名片, 其次为昵称."""
        return self.card or self.nickname

    def __int__(self) -> int:
        return self.user_id

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, (Member, User)) and self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)

    def __str__(self) -> str:
        return f"{self.display_name}({self.user_id} @ {self.group_id})"


class GroupHonorInfo(AnchorBaseModel):
    """群荣誉信息.

    Attributes:
        group_id: 群号.
        current_talkative: 当前龙王.
        talkative_list: 历史龙王列表.
        performer_list: 群聊之火列表.
        legend_list: 群聊炽焰列表.
        strong_newbie_list: 冒尖小春笋列表.
        emotion_list: 快乐之源列表.
    """

    group_id: int = 0
    current_talkative: dict | None = None
    talkative_list: list[dict] = Field(default_factory=list)
    performer_list: list[dict] = Field(default_factory=list)
    legend_list: list[dict] = Field(default_factory=list)
    strong_newbie_list: list[dict] = Field(default_factory=list)
    emotion_list: list[dict] = Field(default_factory=list)


class EssenceMessage(AnchorBaseModel):
    """精华消息.

    Attributes:
        sender_id: 消息发送者 QQ 号.
        sender_nick: 发送者昵称.
        sender_time: 消息发送时间.
        operator_id: 设精操作者 QQ 号.
        operator_nick: 操作者昵称.
        operator_time: 设精时间.
        message_id: 消息 ID.
    """

    sender_id: int = 0
    sender_nick: str = ""
    sender_time: int = 0
    operator_id: int = 0
    operator_nick: str = ""
    operator_time: int = 0
    message_id: int = 0


class GroupNotice(AnchorBaseModel):
    """群公告.

    Attributes:
        sender_id: 发布者 QQ 号.
        publish_time: 发布时间 (Unix 时间戳).
        message: 公告内容.
    """

    sender_id: int = 0
    publish_time: int = 0
    message: dict = Field(default_factory=dict)


class GroupFileInfo(AnchorBaseModel):
    """群文件信息.

    Attributes:
        group_id: 群号.
        file_id: 文件 ID.
        file_name: 文件名.
        busid: 业务 ID.
        file_size: 文件大小 (字节).
        upload_time: 上传时间.
        dead_time: 过期时间.
        modify_time: 修改时间.
        download_times: 下载次数.
        uploader: 上传者 QQ 号.
        uploader_name: 上传者昵称.
    """

    group_id: int = 0
    file_id: str = ""
    file_name: str = ""
    busid: int = 0
    file_size: int = 0
    upload_time: int = 0
    dead_time: int = 0
    modify_time: int = 0
    download_times: int = 0
    uploader: int = 0
    uploader_name: str = ""


class GroupFolderInfo(AnchorBaseModel):
    """群文件夹信息.

    Attributes:
        group_id: 群号.
        folder_id: 文件夹 ID.
        folder_name: 文件夹名称.
        create_time: 创建时间.
        creator: 创建者 QQ 号.
        creator_name: 创建者昵称.
        total_file_count: 文件总数.
    """

    group_id: int = 0
    folder_id: str = ""
    folder_name: str = ""
    create_time: int = 0
    creator: int = 0
    creator_name: str = ""
    total_file_count: int = 0


class GroupRootFiles(AnchorBaseModel):
    """群根目录文件与文件夹.

    Attributes:
        files: 文件列表.
        folders: 文件夹列表.
    """

    files: list[GroupFileInfo] = Field(default_factory=list)
    folders: list[GroupFolderInfo] = Field(default_factory=list)


class LoginInfo(AnchorBaseModel):
    """当前登录信息.

    Attributes:
        user_id: 机器人 QQ 号.
        nickname: 机器人昵称.
    """

    user_id: int = 0
    nickname: str = ""


class VersionInfo(AnchorBaseModel):
    """OneBot 实现端版本信息.

    Attributes:
        app_name: 应用名称.
        app_version: 应用版本.
        protocol_version: 协议版本.
        app_full_name: 应用全名 (NapCat 扩展).
        runtime_os: 运行系统 (NapCat 扩展).
        runtime_arch: 运行架构 (NapCat 扩展).
        version: 版本字符串 (NapCat 扩展).
    """

    app_name: str = ""
    app_version: str = ""
    protocol_version: str = ""

    app_full_name: str | None = None
    runtime_os: str | None = None
    runtime_arch: str | None = None
    version: str | None = None


class OnlineStatus(AnchorBaseModel):
    """在线状态.

    Attributes:
        online: 是否在线.
        good: 状态是否正常.
    """

    online: bool = False
    good: bool = False


class StatusInfo(AnchorBaseModel):
    """完整运行状态信息.

    Attributes:
        app_initialized: 应用是否已初始化.
        app_enabled: 应用是否已启用.
        app_good: 应用状态是否正常.
        online: 是否在线.
        good: 状态是否正常.
    """

    app_initialized: bool = Field(False, alias="app_initialized")
    app_enabled: bool = Field(False, alias="app_enabled")
    app_good: bool = Field(False, alias="app_good")
    online: bool = False
    good: bool = False
