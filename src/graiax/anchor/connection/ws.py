"""OneBot 11 WebSocket 客户端

正向 WebSocket 连接: 主动连接到 OneBot 实现端的 WS 端点,
接收事件推送, 同时支持通过 WebSocket 发送 API 调用.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
from loguru import logger

from ..event import OneBotEvent
from .config import OneBotConfig
from .util import build_event, validate_response


class WebSocketClient:
    """OneBot 11 正向 WebSocket 客户端.

    连接到 OneBot WS 端点, 接收事件推送并支持通过 WebSocket 发送 API 调用.
    API 调用使用 ``echo`` 字段进行请求-响应关联.
    """

    def __init__(
        self,
        config: OneBotConfig,
        event_callback: Callable[[OneBotEvent], Awaitable[Any]],
    ) -> None:
        """初始化 WebSocket 客户端.

        Args:
            config (OneBotConfig): 连接配置.
            event_callback: 事件回调, 收到事件时调用.
        """
        self.config = config
        self._event_callback = event_callback
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._running = False
        self._recv_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        """WebSocket 是否处于连接状态."""
        return self._ws is not None and not self._ws.closed

    async def connect(self) -> None:
        """建立 WebSocket 连接并启动接收循环.

        Raises:
            ValueError: ``ws_url`` 未配置.
        """
        if not self.config.ws_url:
            raise ValueError("ws_url is not configured")
        headers: dict[str, str] = {}
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.config.ws_url, headers=headers)
        self._running = True
        self._recv_task = asyncio.create_task(self._receive_loop())
        logger.info(f"WebSocket connected to {self.config.ws_url}")

    async def close(self) -> None:
        """关闭 WebSocket 连接并清理所有待处理的 Future."""
        self._running = False
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def _receive_loop(self) -> None:
        """WebSocket 消息接收循环.

        区分两类消息:
        - 带 ``echo`` 字段的为 API 响应, 与对应的 Future 关联
        - 带 ``post_type`` 字段的为事件推送, 交由事件回调处理
        """
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from WS: {msg.data[:200]}")
                        continue

                    echo = data.get("echo")
                    if echo and echo in self._pending:
                        fut = self._pending.pop(echo)
                        if not fut.done():
                            fut.set_result(data)
                        continue

                    if "post_type" in data:
                        try:
                            event = build_event(data)
                            await self._event_callback(event)
                        except Exception:
                            logger.exception("Error processing WS event")
                    else:
                        logger.debug(f"Unknown WS message: {str(data)[:200]}")

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("WebSocket receive loop error")
        finally:
            self._running = False

    async def call(self, action: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        """通过 WebSocket 发送 API 调用并等待响应.

        Args:
            action (str): OneBot API 动作名, 如 ``"send_group_msg"``.
            params (Optional[dict[str, Any]], optional): 动作参数.
            timeout (float, optional): 等待响应的超时秒数, 默认为 30.0.

        Raises:
            RuntimeError: WebSocket 未连接.
            TimeoutError: 等待响应超时.
            OneBotApiError: API 返回错误.

        Returns:
            Any: 响应中的 ``data`` 字段.
        """
        if not self.connected:
            raise RuntimeError("WebSocket is not connected")
        echo = str(uuid.uuid4())
        payload = {"action": action, "params": params or {}, "echo": echo}
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[echo] = fut
        await self._ws.send_json(payload)  # type: ignore[union-attr]
        try:
            raw = await asyncio.wait_for(fut, timeout=timeout)
            return validate_response(raw)
        except asyncio.TimeoutError:
            self._pending.pop(echo, None)
            raise TimeoutError(f"WebSocket API call {action} timed out after {timeout}s")
