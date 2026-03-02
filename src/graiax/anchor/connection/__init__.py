"""OneBot 11 连接层

提供 HTTP 和 WebSocket 客户端, 用于与 OneBot 实现端通信.
"""

from .config import OneBotConfig as OneBotConfig
from .http import HttpClient as HttpClient
from .util import build_event as build_event
from .util import validate_response as validate_response
from .ws import WebSocketClient as WebSocketClient
