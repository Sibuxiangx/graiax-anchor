"""消息链解析器 / 装饰器

作为 graia-broadcast 的 Decorator / Derive 目标使用,
类似 Ariadne 的 DetectPrefix, DetectSuffix, MatchRegex 等.
"""

from __future__ import annotations

import abc
import difflib
import re
from collections.abc import Iterable

from graia.broadcast.builtin.derive import Derive
from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.decorator import DecoratorInterface
from graia.broadcast.interfaces.dispatcher import DispatcherInterface

from ..chain import MessageChain
from ..segment import At, Text


class ChainDecorator(abc.ABC, Decorator, Derive[MessageChain]):
    """消息链装饰器的抽象基类.

    子类需实现 ``__call__`` 方法: 接收消息链, 返回处理后的消息链或抛出 ``ExecutionStop``.
    """

    pre = True

    @abc.abstractmethod
    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain | None:
        ...

    async def target(self, interface: DecoratorInterface):
        return await self(
            await interface.dispatcher_interface.lookup_param("message_chain", MessageChain, None),
            interface.dispatcher_interface,
        )


class DetectPrefix(ChainDecorator):
    """前缀检测装饰器.

    当消息链不以给定前缀之一开头时中止执行; 匹配成功时返回去除前缀后的消息链.

    Args:
        prefix (Union[str, Iterable[str]]): 一个或多个前缀字符串.
    """

    def __init__(self, prefix: str | Iterable[str]) -> None:
        self.prefix: list[str] = [prefix] if isinstance(prefix, str) else list(prefix)

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        for prefix in self.prefix:
            if chain.startswith(prefix):
                return chain.removeprefix(prefix).removeprefix(" ")
        raise ExecutionStop


class DetectSuffix(ChainDecorator):
    """后缀检测装饰器.

    当消息链不以给定后缀之一结尾时中止执行; 匹配成功时返回去除后缀后的消息链.

    Args:
        suffix (Union[str, Iterable[str]]): 一个或多个后缀字符串.
    """

    def __init__(self, suffix: str | Iterable[str]) -> None:
        self.suffix: list[str] = [suffix] if isinstance(suffix, str) else list(suffix)

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        for suffix in self.suffix:
            if chain.endswith(suffix):
                return chain.removesuffix(suffix).removesuffix(" ")
        raise ExecutionStop


class MentionMe(ChainDecorator):
    """提及机器人检测装饰器.

    当消息未 @机器人 时中止执行; 匹配成功时返回去除 @段后的消息链.

    Args:
        name (Union[bool, str]): 为 True 时自动获取机器人昵称进行匹配;
            为字符串时使用指定名称匹配.
    """

    def __init__(self, name: bool | str = True) -> None:
        self.name = name

    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain | None:
        from ...app import Anchor

        app = Anchor.current()
        if not chain:
            raise ExecutionStop

        first = chain[0]
        if isinstance(first, At):
            if first.target == app.account:
                return chain[1:].removeprefix(" ")

        if isinstance(self.name, str):
            name = self.name
        elif self.name is True:
            info = await app.get_login_info()
            name = info.nickname
        else:
            raise ExecutionStop

        if isinstance(first, Text) and first.text.lstrip().startswith(name):
            return chain.removeprefix(name).removeprefix(" ")

        raise ExecutionStop


class Mention(ChainDecorator):
    """特定用户提及检测装饰器.

    当消息链未提及指定用户时中止执行.

    Args:
        target (Union[int, str]): 目标用户 QQ 号 (匹配 At 段) 或昵称 (匹配 Text 段前缀).
    """

    def __init__(self, target: int | str) -> None:
        self.person = target

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        if not chain:
            raise ExecutionStop
        first = chain[0]
        if isinstance(first, Text) and isinstance(self.person, str) and first.text.startswith(self.person):
            return chain.removeprefix(self.person).removeprefix(" ")
        if isinstance(first, At) and isinstance(self.person, int) and first.target == self.person:
            return chain[1:].removeprefix(" ")
        raise ExecutionStop


class ContainKeyword(ChainDecorator):
    """关键词包含检测装饰器.

    当消息链中不包含指定关键词时中止执行.

    Args:
        keyword (str): 要检测的关键词.
    """

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        if self.keyword not in chain:
            raise ExecutionStop
        return chain


class MatchContent(ChainDecorator):
    """精确内容匹配装饰器.

    当消息链内容与给定内容不完全一致时中止执行.

    Args:
        content (Union[str, MessageChain]): 要匹配的内容.
    """

    def __init__(self, content: str | MessageChain) -> None:
        self.content = content

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        if isinstance(self.content, str) and chain.display != self.content:
            raise ExecutionStop
        if isinstance(self.content, MessageChain) and chain != self.content:
            raise ExecutionStop
        return chain


class MatchRegex(ChainDecorator, BaseDispatcher):
    """正则表达式匹配装饰器.

    当消息链文本不匹配正则时中止执行; 匹配成功后可通过 ``re.Match`` 类型注入匹配结果.

    Args:
        regex (str): 正则表达式.
        flags (re.RegexFlag, optional): 正则标志.
        full (bool, optional): 是否使用 ``fullmatch``, 默认为 True.
    """

    def __init__(self, regex: str, flags: re.RegexFlag = re.RegexFlag(0), full: bool = True) -> None:
        self.pattern = re.compile(regex, flags)
        self.match_func = self.pattern.fullmatch if full else self.pattern.match

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        if not self.match_func(chain.display):
            raise ExecutionStop
        return chain

    async def beforeExecution(self, interface: DispatcherInterface):
        chain: MessageChain = await interface.lookup_param("message_chain", MessageChain, None)
        if res := self.match_func(chain.display):
            interface.local_storage["__regex_match__"] = res
        else:
            raise ExecutionStop

    async def catch(self, interface: DispatcherInterface):
        if interface.annotation is re.Match:
            return interface.local_storage.get("__regex_match__")


class FuzzyMatch(ChainDecorator):
    """模糊匹配装饰器.

    当消息文本与模板的相似度低于阈值时中止执行.

    Args:
        template (str): 匹配模板.
        min_rate (float, optional): 最低相似度, 默认为 0.6.
    """

    def __init__(self, template: str, min_rate: float = 0.6) -> None:
        self.template = template
        self.min_rate = min_rate

    async def __call__(self, chain: MessageChain, _) -> MessageChain | None:
        text = chain.display
        matcher = difflib.SequenceMatcher(a=text, b=self.template)
        if matcher.real_quick_ratio() < self.min_rate:
            raise ExecutionStop
        if matcher.quick_ratio() < self.min_rate:
            raise ExecutionStop
        if matcher.ratio() < self.min_rate:
            raise ExecutionStop
        return chain


StartsWith = DetectPrefix
"""``DetectPrefix`` 的别名."""

EndsWith = DetectSuffix
"""``DetectSuffix`` 的别名."""
