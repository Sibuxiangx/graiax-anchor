"""Anchor 数据模型基础工具"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AnchorBaseModel(BaseModel):
    """graiax.anchor 所有数据模型的基类.

    基于 Pydantic v2, 配置了:

    - ``populate_by_name``: 支持字段名和别名同时赋值
    - ``from_attributes``: 支持从 ORM 对象构建
    - ``extra="allow"``: 允许额外字段 (兼容 OneBot 实现端的扩展字段)
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """序列化为字典.

        Returns:
            dict[str, Any]: 模型字典.
        """
        return self.model_dump(**kwargs)

    def to_json(self, **kwargs: Any) -> str:
        """序列化为 JSON 字符串.

        Returns:
            str: JSON 字符串.
        """
        return self.model_dump_json(**kwargs)
