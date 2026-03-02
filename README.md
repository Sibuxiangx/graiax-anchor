<div align="center">

# Anchor

_An elegant Python OneBot 11 framework, inspired by Graia Ariadne._

[![PyPI](https://img.shields.io/pypi/v/graiax-anchor)](https://pypi.org/project/graiax-anchor)
[![Python Version](https://img.shields.io/pypi/pyversions/graiax-anchor)](https://pypi.org/project/graiax-anchor)
[![License](https://img.shields.io/github/license/Sibuxiangx/graiax-anchor)](https://github.com/Sibuxiangx/graiax-anchor/blob/master/LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-30173d.svg)](https://docs.astral.sh/ruff/)

</div>

Anchor 是基于 [Graia Ariadne](https://github.com/GraiaProject/Ariadne) 设计重构的 **OneBot 11 协议框架**，保留了 Ariadne 优雅的 `MessageChain` 消息链设计和 `graia` 生态的核心组件（`graia-broadcast`、`launart`、`creart`）。

## 特性

- **扩展支持** — 表情回应、Markdown、群精华等
- **保留 MessageChain 设计** — 丰富的消息段类型与链式查询 API
- **graia 生态兼容** — 支持 `graia-broadcast`、`graia-saya`

## 安装

```bash
pip install graiax-anchor
```

推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv add graiax-anchor
```

## 快速开始

```python
from graia.broadcast import Broadcast
from graiax.anchor import Anchor, OneBotConfig
from graiax.anchor.event.message import GroupMessageEvent

broadcast = Broadcast()
app = Anchor(
    broadcast=broadcast,
    config=OneBotConfig(
        ws_url="ws://localhost:3001",
        access_token="your_token",
    ),
)


@broadcast.receiver(GroupMessageEvent)
async def on_group_message(event: GroupMessageEvent):
    chain = event.message_chain
    if chain.startswith("/hello"):
        await app.send_group_msg(event.group_id, "Hello, World!")


app.launch_blocking()
```

更多示例请参考 [demo.md](./demo.md)。

## 项目结构

```
graiax.anchor
├── app.py              # Anchor 主应用类, 80+ API 方法
├── log.py              # 日志系统 (LogConfig)
├── connection/         # HTTP / WebSocket 客户端与配置
├── event/              # OneBot 11 事件模型 (消息/通知/请求/元事件)
├── message/
│   ├── segment.py      # 消息段类型 (Text, Image, At, Reply, Forward, ...)
│   ├── chain.py        # MessageChain 消息链
│   └── parser/         # 消息解析器 (DetectPrefix, MatchRegex, ...)
├── model/              # 数据模型 (Friend, Group, Member, ...)
├── dispatcher.py       # graia-broadcast Dispatcher
├── service.py          # Launart 服务
└── util/               # 工具 (发送策略, 验证器, Saya 集成)
```

## 协议

本项目以 [`GNU AGPL-3.0`](https://choosealicense.com/licenses/agpl-3.0/) 作为开源协议。

## 致谢

- [Graia Ariadne](https://github.com/GraiaProject/Ariadne) — 框架设计灵感来源
- [NapCat](https://github.com/NapNeko/NapCatQQ) — OneBot 11 协议实现
- [graia-broadcast](https://github.com/GraiaProject/BroadcastControl) — 事件分发系统
- [launart](https://github.com/GraiaProject/launart) — 服务生命周期管理

**如果认为本项目有帮助, 欢迎点一个 Star.**
