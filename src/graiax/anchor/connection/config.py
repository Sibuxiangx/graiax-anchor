"""OneBot 11 连接配置"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OneBotConfig:
    """OneBot 11 连接配置.

    至少需要提供 ``http_url`` 或 ``ws_url`` 之一.

    Attributes:
        http_url: HTTP API 基础 URL, 如 ``"http://localhost:3000"``.
        ws_url: WebSocket URL, 如 ``"ws://localhost:3001"``.
        access_token: Bearer 认证令牌.
        account: 机器人 QQ 号; 为 0 时会在首次调用 ``get_login_info`` 时自动填充.
    """

    http_url: str = ""
    ws_url: str = ""
    access_token: str = ""
    account: int = 0

    @property
    def http_headers(self) -> dict[str, str]:
        """构建 HTTP 请求头, 包含 Content-Type 和可选的 Authorization."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
