"""Anchor 工具模块"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import TypeVar

T = TypeVar("T")


def camel_to_snake(name: str) -> str:
    """将驼峰命名转换为蛇形命名.

    Args:
        name (str): 驼峰命名字符串.

    Returns:
        str: 蛇形命名字符串.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def gen_subclass(cls: type) -> Iterator[type]:
    """递归获取指定类的所有子类.

    Args:
        cls (type): 目标类.

    Yields:
        type: 子类.
    """
    for sub in cls.__subclasses__():
        yield sub
        yield from gen_subclass(sub)
