"""OneBot 11 消息段类型

每个消息段遵循 OneBot 11 格式: ``{"type": "<seg_type>", "data": {...}}``.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from io import BytesIO
from json import dumps as j_dump
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import Field

if TYPE_CHECKING:
    from .chain import MessageChain

from ..model.util import AnchorBaseModel


class Segment(AnchorBaseModel):
    """所有 OneBot 11 消息段的基类.

    线路格式: ``{"type": "<seg_type>", "data": {...}}``
    """

    type: str = "unknown"

    def __hash__(self) -> int:
        return hash((self.__class__,) + tuple(self.__dict__.values()))

    @property
    def display(self) -> str:
        """获取消息段的可读文本表示."""
        return str(self)

    def __str__(self) -> str:
        return ""

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """序列化为 OneBot 线路格式字典.

        Returns:
            dict[str, Any]: ``{"type": ..., "data": {...}}`` 格式的字典.
        """
        data = {}
        for k, v in self.model_dump(exclude={"type"}, exclude_none=True).items():
            data[k] = v
        return {"type": self.type, "data": data}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        """从 OneBot 线路格式字典反序列化为消息段实例.

        Args:
            data (dict[str, Any]): OneBot 消息段字典.

        Returns:
            Segment: 对应类型的消息段实例.
        """
        seg_type = data.get("type", "unknown")
        seg_data = data.get("data", {})
        seg_cls = SEGMENT_REGISTRY.get(seg_type, Segment)
        return seg_cls.model_validate({"type": seg_type, **seg_data})

    def __add__(self, other: MessageChain | list[Segment] | Segment | str) -> MessageChain:
        from .chain import MessageChain

        if isinstance(other, str):
            other = Text(other)
        if isinstance(other, Segment):
            other = [other]
        if isinstance(other, MessageChain):
            other = list(other.content)
        return MessageChain([self] + other, inline=True)

    def __radd__(self, other: MessageChain | list[Segment] | Segment | str) -> MessageChain:
        from .chain import MessageChain

        if isinstance(other, str):
            other = Text(other)
        if isinstance(other, Segment):
            other = [other]
        if isinstance(other, MessageChain):
            other = list(other.content)
        return MessageChain(other + [self], inline=True)


# ─── 文本消息段 ──────────────────────────────────────────────────────────────


class Text(Segment):
    """纯文本消息段.

    Attributes:
        text: 文本内容.
    """

    type: str = "text"
    text: str = ""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(text=text, **kwargs)

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Text) and self.text == other.text

    def __hash__(self) -> int:
        return hash(("text", self.text))


class At(Segment):
    """@ 提及消息段.

    使用 ``qq="all"`` 表示 @全体成员.

    Attributes:
        qq: 目标 QQ 号或 ``"all"``.
    """

    type: str = "at"
    qq: str = ""

    def __init__(self, qq: int | str = "", **kwargs: Any) -> None:
        super().__init__(qq=str(qq), **kwargs)

    @property
    def target(self) -> int | None:
        """获取目标 QQ 号; @全体成员时返回 ``None``."""
        if self.qq == "all":
            return None
        return int(self.qq)

    @property
    def is_all(self) -> bool:
        """是否为 @全体成员."""
        return self.qq == "all"

    def __str__(self) -> str:
        return "@全体成员" if self.is_all else f"@{self.qq}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, At) and self.qq == other.qq

    def __hash__(self) -> int:
        return hash(("at", self.qq))


class Reply(Segment):
    """回复 (引用) 消息段.

    Attributes:
        id: 被回复的消息 ID.
    """

    type: str = "reply"
    id: str = ""

    def __init__(self, id: int | str = "", **kwargs: Any) -> None:
        super().__init__(id=str(id), **kwargs)

    @property
    def message_id(self) -> int:
        """获取被回复的消息 ID."""
        return int(self.id)

    def __str__(self) -> str:
        return f"[回复:{self.id}]"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Reply) and self.id == other.id

    def __hash__(self) -> int:
        return hash(("reply", self.id))


# ─── 表情消息段 ──────────────────────────────────────────────────────────────


class Face(Segment):
    """QQ 内置表情消息段.

    Attributes:
        id: 表情 ID.
    """

    type: str = "face"
    id: str = ""
    raw: Any | None = None
    result_id: str | None = Field(None, alias="resultId")
    chain_count: int | None = Field(None, alias="chainCount")

    def __init__(self, id: int | str = "", **kwargs: Any) -> None:
        super().__init__(id=str(id), **kwargs)

    def __str__(self) -> str:
        return f"[表情:{self.id}]"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Face) and self.id == other.id

    def __hash__(self) -> int:
        return hash(("face", self.id))


class MFace(Segment):
    """QQ 商城表情消息段.

    Attributes:
        emoji_id: 表情 ID.
        emoji_package_id: 表情包 ID.
        key: 密钥.
        summary: 表情描述文本.
    """

    type: str = "mface"
    emoji_id: str = ""
    emoji_package_id: str = ""
    key: str | None = None
    summary: str | None = None

    def __str__(self) -> str:
        return f"[商城表情:{self.summary or self.emoji_id}]"


class Dice(Segment):
    """骰子消息段.

    Attributes:
        result: 骰子结果 (1-6).
    """

    type: str = "dice"
    result: str | None = None

    def __str__(self) -> str:
        return f"[骰子:{self.result}]" if self.result else "[骰子]"


class RPS(Segment):
    """猜拳消息段.

    Attributes:
        result: 猜拳结果.
    """

    type: str = "rps"
    result: str | None = None

    def __str__(self) -> str:
        return f"[猜拳:{self.result}]" if self.result else "[猜拳]"


class Poke(Segment):
    """戳一戳消息段.

    Attributes:
        poke_type: 戳一戳类型.
        id: 戳一戳 ID.
    """

    type: str = "poke"
    poke_type: str = Field("", alias="type")
    id: str = ""

    def __init__(self, poke_type: str = "", id: str = "", **kwargs: Any) -> None:
        super().__init__(type="poke", poke_type=poke_type, id=id, **kwargs)

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "poke", "data": {"type": self.poke_type, "id": self.id}}

    def __str__(self) -> str:
        return f"[戳一戳:{self.poke_type}]"


# ─── 媒体消息段 ──────────────────────────────────────────────────────────────


class MediaSegment(Segment):
    """媒体消息段基类, 携带文件引用.

    支持多种方式指定文件内容: 文件路径、URL、Base64 编码、原始字节.

    Attributes:
        file: 文件标识 (URL / ``base64://`` / 文件名).
        url: 文件下载 URL.
        file_size: 文件大小 (字节).
    """

    file: str = ""
    url: str | None = None
    file_size: int | None = None

    def __init__(
        self,
        file: str = "",
        *,
        url: str | None = None,
        path: Path | str | None = None,
        base64: str | None = None,
        data_bytes: bytes | BytesIO | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化媒体消息段.

        Args:
            file (str): 文件标识.
            url (Optional[str]): 文件 URL.
            path (Optional[Union[Path, str]]): 本地文件路径, 将自动读取并编码为 Base64.
            base64 (Optional[str]): Base64 编码的文件内容.
            data_bytes (Optional[Union[bytes, BytesIO]]): 原始字节数据.
        """
        if path:
            p = Path(path) if isinstance(path, str) else path
            file = "base64://" + b64encode(p.read_bytes()).decode()
        elif base64:
            file = f"base64://{base64}"
        elif data_bytes:
            raw = data_bytes.read() if isinstance(data_bytes, BytesIO) else data_bytes
            file = "base64://" + b64encode(raw).decode()
        elif url and not file:
            file = url
        super().__init__(file=file, url=url, **kwargs)

    async def get_bytes(self) -> bytes:
        """下载媒体内容并返回原始字节.

        Raises:
            ValueError: 没有可用的 URL 或 Base64 数据.

        Returns:
            bytes: 媒体文件的原始字节数据.
        """
        if self.file.startswith("base64://"):
            return b64decode(self.file[9:])
        if self.url:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as resp:
                    resp.raise_for_status()
                    return await resp.read()
        raise ValueError("No URL or base64 data available for download.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        if self.file and self.file == other.file:
            return True
        if self.url and self.url == other.url:
            return True
        return False

    def __hash__(self) -> int:
        return hash((self.type, self.file or self.url))


class Image(MediaSegment):
    """图片消息段.

    Attributes:
        summary: 图片描述 (如来自表情包的描述).
        sub_type: 图片子类型.
    """

    type: str = "image"
    summary: str | None = None
    sub_type: int | None = None
    key: str | None = None
    emoji_id: str | None = None
    emoji_package_id: str | None = None

    def __str__(self) -> str:
        return f"[图片:{self.summary}]" if self.summary else "[图片]"


class Record(MediaSegment):
    """语音消息段."""

    type: str = "record"
    path: str | None = None

    def __str__(self) -> str:
        return "[语音]"


class Video(MediaSegment):
    """视频消息段.

    Attributes:
        thumb: 视频封面 URL.
    """

    type: str = "video"
    thumb: str | None = None

    def __str__(self) -> str:
        return "[视频]"


class File(MediaSegment):
    """文件消息段.

    Attributes:
        name: 文件名.
        file_id: 文件 ID.
    """

    type: str = "file"
    name: str | None = None
    file_id: str | None = None

    def __str__(self) -> str:
        return f"[文件:{self.name or self.file}]"


# ─── 富媒体消息段 ────────────────────────────────────────────────────────────


class Json(Segment):
    """JSON 卡片消息段.

    Attributes:
        data: JSON 字符串.
    """

    type: str = "json"
    data: str = ""

    def __init__(self, data: str | dict | list = "", **kwargs: Any) -> None:
        """初始化 JSON 消息段.

        Args:
            data (Union[str, dict, list]): JSON 数据, 可传入字典或列表, 将自动序列化.
        """
        if isinstance(data, (dict, list)):
            data = j_dump(data, ensure_ascii=False)
        super().__init__(data=data, **kwargs)

    def to_dict(self, **_: Any) -> dict[str, Any]:
        return {"type": "json", "data": {"data": self.data}}

    def __str__(self) -> str:
        return "[JSON消息]"


class Xml(Segment):
    """XML 消息段.

    Attributes:
        data: XML 字符串.
    """

    type: str = "xml"
    data: str = ""

    def __init__(self, data: str = "", **kwargs: Any) -> None:
        super().__init__(data=data, **kwargs)

    def to_dict(self, **_: Any) -> dict[str, Any]:
        return {"type": "xml", "data": {"data": self.data}}

    def __str__(self) -> str:
        return "[XML消息]"


class Music(Segment):
    """音乐分享消息段 (仅发送; 接收时为 JSON 卡片).

    Attributes:
        music_type: 音乐来源类型, 如 ``qq`` / ``163`` / ``custom``.
        id: 歌曲 ID.
        url: 歌曲链接.
        image: 封面图片 URL.
        singer: 歌手名.
        title: 歌曲标题.
        content: 歌曲描述.
    """

    type: str = "music"
    music_type: str = Field("", alias="type")
    id: str | None = None
    url: str | None = None
    image: str | None = None
    singer: str | None = None
    title: str | None = None
    content: str | None = None

    def __init__(self, music_type: str = "", **kwargs: Any) -> None:
        super().__init__(type="music", music_type=music_type, **kwargs)

    def to_dict(self, **_: Any) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.music_type}
        for k in ("id", "url", "image", "singer", "title", "content"):
            v = getattr(self, k)
            if v is not None:
                data[k] = v
        return {"type": "music", "data": data}

    def __str__(self) -> str:
        return f"[音乐分享:{self.title or self.music_type}]"


class Forward(Segment):
    """合并转发消息段.

    Attributes:
        id: 转发消息 ID.
        content: 转发内容 (展开时的消息列表).
    """

    type: str = "forward"
    id: str = ""
    content: list[dict[str, Any]] | None = None

    def __str__(self) -> str:
        if self.content:
            return f"[合并转发:共{len(self.content)}条]"
        return f"[合并转发:{self.id}]"


class ForwardNode(AnchorBaseModel):
    """合并转发中的单条消息节点.

    可通过 ``custom()`` 自定义内容, 或通过 ``reference()`` 引用已有消息.
    """

    type: str = "node"
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def custom(
        cls,
        user_id: int,
        nickname: str,
        content: list[dict[str, Any]],
    ) -> ForwardNode:
        """创建自定义内容的转发节点.

        Args:
            user_id (int): 发送者 QQ 号 (可伪造).
            nickname (str): 发送者昵称 (可伪造).
            content (list[dict[str, Any]]): 消息内容 (OneBot 格式的消息段列表).

        Returns:
            ForwardNode: 转发节点.
        """
        return cls(
            data={
                "user_id": str(user_id),
                "nickname": nickname,
                "content": content,
            }
        )

    @classmethod
    def reference(cls, message_id: int) -> ForwardNode:
        """创建引用已有消息的转发节点.

        Args:
            message_id (int): 要引用的消息 ID.

        Returns:
            ForwardNode: 转发节点.
        """
        return cls(data={"id": str(message_id)})


class Contact(Segment):
    """推荐联系人卡片消息段.

    Attributes:
        contact_type: 联系人类型, ``qq`` (好友) 或 ``group`` (群).
        id: 联系人 QQ 号或群号.
    """

    type: str = "contact"
    contact_type: str = Field("", alias="type")
    id: str = ""

    def __init__(self, contact_type: str = "", id: int | str = "", **kwargs: Any) -> None:
        super().__init__(type="contact", contact_type=contact_type, id=str(id), **kwargs)

    def to_dict(self, **_: Any) -> dict[str, Any]:
        return {"type": "contact", "data": {"type": self.contact_type, "id": self.id}}

    def __str__(self) -> str:
        return f"[联系人:{self.contact_type}/{self.id}]"


class Location(Segment):
    """位置消息段.

    Attributes:
        lat: 纬度.
        lon: 经度.
        title: 位置标题.
        content: 位置描述.
    """

    type: str = "location"
    lat: str = ""
    lon: str = ""
    title: str | None = None
    content: str | None = None

    def __str__(self) -> str:
        return f"[位置:{self.title or f'{self.lat},{self.lon}'}]"


class Markdown(Segment):
    """Markdown 消息段 (NapCat 扩展).

    Attributes:
        content: Markdown 文本内容.
    """

    type: str = "markdown"
    content: str = ""

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(content=content, **kwargs)

    def __str__(self) -> str:
        return "[Markdown消息]"


class MiniApp(Segment):
    """小程序消息段 (NapCat 扩展).

    Attributes:
        data: 小程序数据.
    """

    type: str = "miniapp"
    data: str = ""

    def __str__(self) -> str:
        return "[小程序]"


# ─── 消息段注册表 ────────────────────────────────────────────────────────────

SEGMENT_REGISTRY: dict[str, type[Segment]] = {}
"""消息段类型注册表, 用于将 OneBot 线路格式中的 type 字段映射到对应的消息段类."""


def _build_registry() -> None:
    """扫描当前模块, 将所有 Segment 子类注册到 SEGMENT_REGISTRY."""
    import inspect
    import sys

    module = sys.modules[__name__]
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, Segment) and obj is not Segment and obj is not MediaSegment:
            try:
                seg_type = obj.model_fields["type"].default
                if seg_type and seg_type != "unknown":
                    SEGMENT_REGISTRY[seg_type] = obj
            except Exception:
                pass


_build_registry()
