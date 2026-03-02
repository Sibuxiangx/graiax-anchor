"""OneBot 11 HTTP 客户端

所有 OneBot 11 API 调用均为 POST 请求, 请求体为 JSON 格式.
"""

from __future__ import annotations

from typing import Any

import aiohttp
from loguru import logger

from .config import OneBotConfig
from .util import validate_response


class HttpClient:
    """异步 HTTP 客户端, 用于与 OneBot 11 HTTP API 端点通信."""

    def __init__(self, config: OneBotConfig) -> None:
        """初始化 HTTP 客户端.

        Args:
            config (OneBotConfig): 连接配置.
        """
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 会话; 若会话已关闭则自动重建."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.config.http_headers)
        return self._session

    async def close(self) -> None:
        """关闭 HTTP 会话."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _url(self, endpoint: str) -> str:
        """拼接完整的 API URL."""
        base = self.config.http_url.rstrip("/")
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{base}{endpoint}"

    async def call(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """向 OneBot 11 端点发送 POST 请求并返回经过校验的数据.

        Args:
            endpoint (str): API 路径, 如 ``"send_group_msg"``.
            params (Optional[dict[str, Any]], optional): JSON 请求体参数.

        Raises:
            OneBotApiError: API 返回错误时抛出.
            aiohttp.ClientError: 网络层错误.

        Returns:
            Any: 响应中的 ``data`` 字段.
        """
        url = self._url(endpoint)
        body = params or {}
        logger.debug(f"HTTP POST {url}")
        try:
            async with self.session.post(url, json=body) as resp:
                resp.raise_for_status()
                raw = await resp.json()
                return validate_response(raw)
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling {endpoint}: {e}")
            raise

    async def call_raw(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """向 OneBot 11 端点发送 POST 请求并返回原始 JSON 响应 (不经过校验).

        Args:
            endpoint (str): API 路径.
            params (Optional[dict[str, Any]], optional): JSON 请求体参数.

        Returns:
            dict[str, Any]: 原始 JSON 响应.
        """
        url = self._url(endpoint)
        async with self.session.post(url, json=params or {}) as resp:
            resp.raise_for_status()
            return await resp.json()
