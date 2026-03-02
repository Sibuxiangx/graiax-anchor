"""事件监听器验证器

提供基于群号、用户 QQ 号或自定义谓词的事件过滤装饰器,
作为 graia-broadcast Decorator 使用.
"""

from __future__ import annotations

from collections.abc import Callable

from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.decorator import DecoratorInterface


class GroupValidator(Decorator):
    """群过滤器: 仅允许来自指定群的事件通过.

    Args:
        *group_ids (int): 允许的群号列表.
    """

    pre = True

    def __init__(self, *group_ids: int) -> None:
        self.group_ids = set(group_ids)

    async def target(self, interface: DecoratorInterface):
        event = interface.dispatcher_interface.event
        gid = getattr(event, "group_id", None)
        if gid is None or gid not in self.group_ids:
            raise ExecutionStop
        return event


class UserValidator(Decorator):
    """用户过滤器: 仅允许来自指定用户的事件通过.

    Args:
        *user_ids (int): 允许的用户 QQ 号列表.
    """

    pre = True

    def __init__(self, *user_ids: int) -> None:
        self.user_ids = set(user_ids)

    async def target(self, interface: DecoratorInterface):
        event = interface.dispatcher_interface.event
        uid = getattr(event, "user_id", None)
        if uid is None or uid not in self.user_ids:
            raise ExecutionStop
        return event


class CustomValidator(Decorator):
    """自定义谓词验证器.

    Args:
        predicate (Callable[..., bool]): 接收事件对象, 返回 ``True`` 放行, ``False`` 中止.
    """

    pre = True

    def __init__(self, predicate: Callable[..., bool]) -> None:
        self.predicate = predicate

    async def target(self, interface: DecoratorInterface):
        event = interface.dispatcher_interface.event
        if not self.predicate(event):
            raise ExecutionStop
        return event
