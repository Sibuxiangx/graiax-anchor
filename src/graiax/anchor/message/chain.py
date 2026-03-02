"""消息链实现

保留 Ariadne 的富消息链 API 设计. ``MessageChain`` 是消息段的有序容器,
提供丰富的查询、操纵和序列化方法.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from copy import deepcopy
from typing import (
    Any,
    Literal,
    TypeVar,
    Union,
    overload,
)

from .segment import (
    File,
    Reply,
    Segment,
    Text,
)

Segment_T = TypeVar("Segment_T", bound=Segment)

MessageContainer = Union[str, Segment, Sequence[Any], "MessageChain"]
"""可作为 MessageChain 构造参数的类型联合."""


class MessageChain:
    """有序消息段容器, 模仿 Ariadne 的 MessageChain 设计.

    支持:

    - 从字符串、消息段、字典、嵌套容器构造
    - 基于类型的查询: ``chain[Text]``, ``chain.get(Image, 2)``
    - 切片、迭代、长度、布尔判断
    - 与 OneBot 11 线路格式 (``list[dict]``) 的互相序列化
    - 前缀/后缀移除、替换等字符串操作
    """

    __slots__ = ("_content",)

    # ── 构造 ──────────────────────────────────────────────────────────────

    @overload
    def __init__(self, __root__: Sequence[Segment], *, inline: Literal[True]) -> None: ...
    @overload
    def __init__(self, *elements: MessageContainer, inline: Literal[False] = False) -> None: ...

    def __init__(
        self,
        __root__: MessageContainer = (),
        *elements: MessageContainer,
        inline: bool = False,
    ) -> None:
        if inline:
            self._content: list[Segment] = list(__root__)  # type: ignore[arg-type]
        else:
            self._content = self.build_chain((__root__, *elements) if elements else __root__)

    @property
    def content(self) -> list[Segment]:
        """获取内部消息段列表."""
        return self._content

    # ── 从原始数据构建 ────────────────────────────────────────────────────

    @staticmethod
    def build_chain(obj: MessageContainer) -> list[Segment]:
        """从各种输入类型递归构建扁平的消息段列表.

        Args:
            obj (MessageContainer): 输入数据, 可为字符串、消息段、字典列表等.

        Returns:
            list[Segment]: 构建出的消息段列表.
        """
        if isinstance(obj, MessageChain):
            return deepcopy(obj._content)
        if isinstance(obj, Segment):
            return [obj]
        if isinstance(obj, str):
            return [Text(obj)]
        result: list[Segment] = []
        for item in obj:  # type: ignore[union-attr]
            if isinstance(item, dict):
                result.append(Segment.from_dict(item))
            elif isinstance(item, Segment):
                result.append(item)
            elif isinstance(item, str):
                result.append(Text(item))
            elif isinstance(item, (list, tuple)):
                result.extend(MessageChain.build_chain(item))
            else:
                result.append(Text(str(item)))
        return result

    @classmethod
    def from_onebot(cls, data: list[dict[str, Any]]) -> MessageChain:
        """从 OneBot 11 线路格式 (消息段字典列表) 解析.

        Args:
            data (list[dict[str, Any]]): OneBot 消息段列表.

        Returns:
            MessageChain: 解析后的消息链.
        """
        return cls(data)

    @classmethod
    def model_validate(cls, obj: Any) -> MessageChain:
        """Pydantic v2 兼容的验证方法.

        Args:
            obj: 待验证的对象.

        Returns:
            MessageChain: 验证后的消息链.
        """
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, list):
            return cls(obj)
        return cls(str(obj))

    # ── 序列化 ────────────────────────────────────────────────────────────

    def to_onebot(self) -> list[dict[str, Any]]:
        """序列化为 OneBot 11 线路格式.

        Returns:
            list[dict[str, Any]]: 消息段字典列表.
        """
        return [seg.to_dict() for seg in self._content]

    def model_dump(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Pydantic v2 兼容的序列化方法."""
        return self.to_onebot()

    # ── 显示 ──────────────────────────────────────────────────────────────

    @property
    def display(self) -> str:
        """获取消息链的可读文本表示."""
        return "".join(seg.display for seg in self._content)

    @property
    def safe_display(self) -> str:
        """获取转义后的安全显示文本."""
        return repr(self.display)[1:-1]

    def __str__(self) -> str:
        return self.display

    def __repr__(self) -> str:
        return f"MessageChain({self._content!r})"

    # ── 集合协议 ──────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._content)

    def __bool__(self) -> bool:
        return bool(self._content)

    def __iter__(self) -> Iterator[Segment]:
        return iter(self._content)

    def __contains__(self, item: type[Segment] | Segment | str) -> bool:
        if isinstance(item, type) and issubclass(item, Segment):
            return any(isinstance(seg, item) for seg in self._content)
        if isinstance(item, str):
            return item in self.display
        return item in self._content

    # ── 索引 ──────────────────────────────────────────────────────────────

    @overload
    def __getitem__(self, item: type[Segment_T]) -> list[Segment_T]: ...
    @overload
    def __getitem__(self, item: tuple[type[Segment_T], int]) -> list[Segment_T]: ...
    @overload
    def __getitem__(self, item: int) -> Segment: ...
    @overload
    def __getitem__(self, item: slice) -> MessageChain: ...

    def __getitem__(self, item: Any) -> Any:
        """支持多种索引方式.

        - ``chain[Text]``: 获取所有 Text 段
        - ``chain[Text, 2]``: 获取前 2 个 Text 段
        - ``chain[0]``: 按位置索引
        - ``chain[1:3]``: 切片
        """
        if isinstance(item, type) and issubclass(item, Segment):
            return self.get(item)
        if isinstance(item, tuple) and len(item) == 2:
            return self.get(item[0], item[1])
        if isinstance(item, int):
            return self._content[item]
        if isinstance(item, slice):
            return MessageChain(self._content[item], inline=True)
        raise TypeError(f"Invalid index type: {type(item)}")

    # ── 查询方法 ──────────────────────────────────────────────────────────

    def get(self, seg_type: type[Segment_T], count: int = -1) -> list[Segment_T]:
        """获取指定类型的所有 (或前 *count* 个) 消息段.

        Args:
            seg_type (type[Segment_T]): 目标消息段类型.
            count (int, optional): 最大获取数量, -1 为全部.

        Returns:
            list[Segment_T]: 匹配的消息段列表.
        """
        result: list[Segment_T] = []
        for seg in self._content:
            if isinstance(seg, seg_type):
                result.append(seg)
                if count > 0 and len(result) >= count:
                    break
        return result

    def get_first(self, seg_type: type[Segment_T]) -> Segment_T | None:
        """获取指定类型的第一个消息段.

        Args:
            seg_type (type[Segment_T]): 目标消息段类型.

        Returns:
            Segment_T | None: 找到的消息段, 未找到返回 ``None``.
        """
        for seg in self._content:
            if isinstance(seg, seg_type):
                return seg
        return None

    def has(self, seg_type: type[Segment]) -> bool:
        """检查消息链中是否包含指定类型的消息段.

        Args:
            seg_type (type[Segment]): 目标消息段类型.

        Returns:
            bool: 是否包含.
        """
        return any(isinstance(seg, seg_type) for seg in self._content)

    def count(self, seg_type: type[Segment]) -> int:
        """统计指定类型的消息段数量.

        Args:
            seg_type (type[Segment]): 目标消息段类型.

        Returns:
            int: 数量.
        """
        return sum(1 for seg in self._content if isinstance(seg, seg_type))

    def only(self, *seg_types: type[Segment]) -> bool:
        """检查消息链是否仅包含指定类型的消息段.

        Args:
            *seg_types (type[Segment]): 允许的消息段类型.

        Returns:
            bool: 是否仅包含指定类型.
        """
        return all(isinstance(seg, seg_types) for seg in self._content)

    # ── 回复提取 ──────────────────────────────────────────────────────────

    @property
    def reply(self) -> Reply | None:
        """提取回复段 (如果存在); 通常为消息链的第一个元素."""
        return self.get_first(Reply)

    def without_reply(self) -> MessageChain:
        """返回去除回复段后的副本."""
        return self.exclude(Reply)

    # ── 文本提取 ──────────────────────────────────────────────────────────

    @property
    def pure_text(self) -> str:
        """将所有 Text 段拼接为单个字符串."""
        return "".join(seg.text for seg in self._content if isinstance(seg, Text))

    # ── 过滤 ──────────────────────────────────────────────────────────────

    def include(self, *seg_types: type[Segment]) -> MessageChain:
        """返回仅包含指定类型消息段的新消息链.

        Args:
            *seg_types (type[Segment]): 要保留的消息段类型.

        Returns:
            MessageChain: 过滤后的新消息链.
        """
        return MessageChain(
            [seg for seg in self._content if isinstance(seg, seg_types)],
            inline=True,
        )

    def exclude(self, *seg_types: type[Segment]) -> MessageChain:
        """返回排除指定类型消息段的新消息链.

        Args:
            *seg_types (type[Segment]): 要排除的消息段类型.

        Returns:
            MessageChain: 过滤后的新消息链.
        """
        return MessageChain(
            [seg for seg in self._content if not isinstance(seg, seg_types)],
            inline=True,
        )

    def as_sendable(self) -> MessageChain:
        """返回可发送的副本 (去除 File 等不可直接发送的段)."""
        return self.exclude(File)

    # ── 变换辅助 (返回新消息链) ───────────────────────────────────────────

    def append(self, item: Segment | str) -> MessageChain:
        """返回在末尾追加元素后的新消息链.

        Args:
            item (Union[Segment, str]): 要追加的消息段或文本.

        Returns:
            MessageChain: 新消息链.
        """
        seg = Text(item) if isinstance(item, str) else item
        return MessageChain(self._content + [seg], inline=True)

    def prepend(self, item: Segment | str) -> MessageChain:
        """返回在开头插入元素后的新消息链.

        Args:
            item (Union[Segment, str]): 要插入的消息段或文本.

        Returns:
            MessageChain: 新消息链.
        """
        seg = Text(item) if isinstance(item, str) else item
        return MessageChain([seg] + self._content, inline=True)

    def extend(self, items: MessageChain | Iterable[Segment]) -> MessageChain:
        """返回追加多个元素后的新消息链.

        Args:
            items (Union[MessageChain, Iterable[Segment]]): 要追加的消息段.

        Returns:
            MessageChain: 新消息链.
        """
        if isinstance(items, MessageChain):
            items = items._content
        return MessageChain(self._content + list(items), inline=True)

    def copy(self) -> MessageChain:
        """返回消息链的深拷贝."""
        return MessageChain(deepcopy(self._content), inline=True)

    # ── 字符串操作 ────────────────────────────────────────────────────────

    def removeprefix(self, prefix: str, *, copy: bool = True) -> MessageChain:
        """移除消息链开头的文本前缀.

        Args:
            prefix (str): 要移除的前缀.
            copy (bool, optional): 是否在副本上操作, 默认为 True.

        Returns:
            MessageChain: 处理后的消息链.
        """
        elements = deepcopy(self._content) if copy else self._content
        for i, seg in enumerate(elements):
            if isinstance(seg, Text):
                if seg.text.startswith(prefix):
                    elements[i] = Text(seg.text[len(prefix) :])
                break
            if not isinstance(seg, Reply):
                break
        return MessageChain(elements, inline=True)

    def removesuffix(self, suffix: str, *, copy: bool = True) -> MessageChain:
        """移除消息链末尾的文本后缀.

        Args:
            suffix (str): 要移除的后缀.
            copy (bool, optional): 是否在副本上操作, 默认为 True.

        Returns:
            MessageChain: 处理后的消息链.
        """
        elements = deepcopy(self._content) if copy else self._content
        for i in range(len(elements) - 1, -1, -1):
            seg = elements[i]
            if isinstance(seg, Text):
                if seg.text.endswith(suffix):
                    elements[i] = Text(seg.text[: -len(suffix)])
                break
        return MessageChain(elements, inline=True)

    def replace(self, old: MessageContainer, new: MessageContainer) -> MessageChain:
        """替换消息链中的内容.

        当 ``old`` 和 ``new`` 均为字符串时, 对 Text 段做文本替换;
        否则基于 display 文本进行替换.

        Args:
            old (MessageContainer): 要替换的内容.
            new (MessageContainer): 替换为的内容.

        Returns:
            MessageChain: 替换后的新消息链.
        """
        if isinstance(old, str) and isinstance(new, str):
            result: list[Segment] = []
            for seg in self._content:
                if isinstance(seg, Text):
                    result.append(Text(seg.text.replace(old, new)))
                else:
                    result.append(seg)
            return MessageChain(result, inline=True)
        if not isinstance(old, MessageChain):
            old = MessageChain(old)
        if not isinstance(new, MessageChain):
            new = MessageChain(new)
        display = self.display
        old_display = old.display
        if old_display not in display:
            return self.copy()
        new_display = new.display
        return MessageChain(display.replace(old_display, new_display))

    def startswith(self, prefix: str) -> bool:
        """检查消息链纯文本是否以指定前缀开头.

        Args:
            prefix (str): 要检查的前缀.

        Returns:
            bool: 是否匹配.
        """
        return self.pure_text.lstrip().startswith(prefix)

    def endswith(self, suffix: str) -> bool:
        """检查消息链纯文本是否以指定后缀结尾.

        Args:
            suffix (str): 要检查的后缀.

        Returns:
            bool: 是否匹配.
        """
        return self.pure_text.rstrip().endswith(suffix)

    # ── 索引辅助 ──────────────────────────────────────────────────────────

    def index_sub(self, sub: MessageChain) -> list[int]:
        """在消息链的文本表示中查找子串的所有起始位置.

        Args:
            sub (MessageChain): 要查找的子消息链.

        Returns:
            list[int]: 所有匹配的起始索引.
        """
        text = self.display
        sub_text = sub.display
        indices: list[int] = []
        start = 0
        while True:
            idx = text.find(sub_text, start)
            if idx == -1:
                break
            indices.append(idx)
            start = idx + 1
        return indices

    # ── 运算符 ────────────────────────────────────────────────────────────

    def __add__(self, other: MessageChain | Segment | str) -> MessageChain:
        if isinstance(other, str):
            other = Text(other)
        if isinstance(other, Segment):
            return MessageChain(self._content + [other], inline=True)
        if isinstance(other, MessageChain):
            return MessageChain(self._content + other._content, inline=True)
        return NotImplemented

    def __radd__(self, other: MessageChain | Segment | str) -> MessageChain:
        if isinstance(other, str):
            other = Text(other)
        if isinstance(other, Segment):
            return MessageChain([other] + self._content, inline=True)
        if isinstance(other, MessageChain):
            return MessageChain(other._content + self._content, inline=True)
        return NotImplemented

    def __mul__(self, count: int) -> MessageChain:
        result: list[Segment] = []
        for _ in range(count):
            result.extend(deepcopy(self._content))
        return MessageChain(result, inline=True)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MessageChain):
            return self._content == other._content
        if isinstance(other, list):
            return self._content == other
        return NotImplemented

    def __hash__(self) -> int:
        return id(self)

    # ── 二进制下载辅助 ───────────────────────────────────────────────────

    async def download_binary(self) -> MessageChain:
        """下载消息链中所有媒体段的二进制数据.

        Returns:
            MessageChain: 自身 (下载完成后).
        """
        from .segment import MediaSegment

        for seg in self._content:
            if isinstance(seg, MediaSegment):
                await seg.get_bytes()
        return self
