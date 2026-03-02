"""Anchor 服务

基于 Launart 的服务实现, 管理 OneBot 11 连接的完整生命周期,
包括 HTTP 客户端和 WebSocket 客户端的创建、事件分发与连接清理.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from graia.broadcast import Broadcast
from launart import ExportInterface, Launart, Service
from loguru import logger

from .connection.config import OneBotConfig
from .connection.http import HttpClient
from .connection.ws import WebSocketClient
from .event import OneBotEvent
from .event.lifecycle import HeartbeatEvent


class AnchorInterface(ExportInterface["AnchorService"]):
    """AnchorService 的导出接口, 供其他 Launart 组件访问 API 调用能力."""

    def __init__(self, service: AnchorService) -> None:
        self.service = service

    async def call_api(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """通过服务调用 OneBot API.

        Args:
            endpoint (str): API 端点名称.
            params (Optional[dict[str, Any]], optional): 请求参数.

        Returns:
            Any: API 返回的 data 字段.
        """
        return await self.service.call_api(endpoint, params)


class AnchorService(Service):
    """管理 OneBot 连接的 Launart 服务.

    生命周期:

    1. **preparing**: 创建 HTTP / WebSocket 客户端
    2. **blocking**: 保持 WebSocket 连接, 将事件分发至 Broadcast
    3. **cleanup**: 关闭所有连接
    """

    id = "anchor.service"
    supported_interface_types = {AnchorInterface}

    broadcast: Broadcast
    config: OneBotConfig
    http: HttpClient | None
    ws: WebSocketClient | None

    _event_callbacks: list[Any]

    def __init__(self, broadcast: Broadcast, config: OneBotConfig) -> None:
        """初始化服务.

        Args:
            broadcast (Broadcast): 事件系统实例.
            config (OneBotConfig): OneBot 连接配置.
        """
        self.broadcast = broadcast
        self.config = config
        self.http = None
        self.ws = None
        self._event_callbacks = []
        super().__init__()

    @property
    def required(self) -> set[str | type[ExportInterface]]:
        return set()

    @property
    def stages(self) -> set[Literal["preparing", "blocking", "cleanup"]]:
        return {"preparing", "blocking", "cleanup"}

    def get_interface(self, interface_type: type[AnchorInterface]) -> AnchorInterface:
        return AnchorInterface(self)

    def add_event_callback(self, cb: Any) -> None:
        """注册事件回调.

        Args:
            cb: 异步回调函数, 签名为 ``async def cb(event: OneBotEvent) -> None``.
        """
        self._event_callbacks.append(cb)

    async def _dispatch_event(self, event: OneBotEvent) -> None:
        """分发事件到所有回调和 Broadcast; 心跳事件会被静默忽略."""
        if isinstance(event, HeartbeatEvent):
            return
        for cb in self._event_callbacks:
            try:
                await cb(event)
            except Exception:
                logger.exception("Error in event callback")
        self.broadcast.postEvent(event)

    async def launch(self, manager: Launart) -> None:
        """服务启动入口, 由 Launart 调用."""
        async with self.stage("preparing"):
            if self.config.http_url:
                self.http = HttpClient(self.config)
                logger.info(f"HTTP client ready: {self.config.http_url}")
            if self.config.ws_url:
                self.ws = WebSocketClient(self.config, self._dispatch_event)
                await self.ws.connect()

        async with self.stage("blocking"):
            if self.ws:
                while self.ws.connected:
                    await asyncio.sleep(1)
                logger.warning("WebSocket disconnected")
            else:
                await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            if self.ws:
                await self.ws.close()
            if self.http:
                await self.http.close()
            logger.info("AnchorService shut down")

    async def call_api(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """调用 OneBot API 端点; 优先使用 WebSocket, 不可用时回退到 HTTP.

        Args:
            endpoint (str): API 端点名称.
            params (Optional[dict[str, Any]], optional): 请求参数.

        Raises:
            RuntimeError: WebSocket 和 HTTP 均不可用.

        Returns:
            Any: API 返回的 data 字段.
        """
        if self.ws and self.ws.connected:
            return await self.ws.call(endpoint, params)
        if self.http:
            return await self.http.call(endpoint, params)
        raise RuntimeError("No connection available (neither WS nor HTTP)")
