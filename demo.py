"""graiax-anchor 演示 Bot

展示框架的核心功能: 消息收发、消息链操作、群管理、请求处理等.
连接到本地 NapCat 实例, 通过 WebSocket 通信.

使用方式:
    uv run python demo.py
"""

from __future__ import annotations

import os

from graia.broadcast import Broadcast

from graiax.anchor import Anchor, OneBotConfig
from graiax.anchor.event.message import GroupMessageEvent, PrivateMessageEvent
from graiax.anchor.event.notice import (
    FriendAddNotice,
    GroupIncreaseNotice,
    GroupPokeNotice,
    GroupRecallNotice,
)
from graiax.anchor.event.request import FriendRequestEvent, GroupRequestEvent
from graiax.anchor.message.chain import MessageChain
from graiax.anchor.message.segment import At, ForwardNode, Text

# ── 配置 ──────────────────────────────────────────────────────────────────────

WS_URL = os.environ.get("ANCHOR_WS_URL", "ws://localhost:3001")
ACCESS_TOKEN = os.environ.get("ANCHOR_ACCESS_TOKEN", "")

# ── 初始化 ────────────────────────────────────────────────────────────────────

broadcast = Broadcast()
app = Anchor(
    broadcast=broadcast,
    config=OneBotConfig(
        ws_url=WS_URL,
        access_token=ACCESS_TOKEN,
    ),
)

# ══════════════════════════════════════════════════════════════════════════════
#  消息处理
# ══════════════════════════════════════════════════════════════════════════════


@broadcast.receiver(GroupMessageEvent)
async def on_group_message(event: GroupMessageEvent):
    chain = event.message_chain
    text = chain.pure_text.strip()
    group_id = event.group_id
    sender = event.sender

    # /ping — 存活检测
    if text == "/ping":
        await app.send_group_msg(group_id, "pong!")
        return

    # /info — 查看 Bot 信息
    if text == "/info":
        login = await app.get_login_info()
        version = await app.get_version_info()
        await app.send_group_msg(
            group_id,
            f"Bot: {login.nickname}({login.user_id})\n"
            f"实现: {version.app_name} {version.app_version}",
        )
        return

    # /echo <内容> — 复读
    if text.startswith("/echo "):
        content = chain.removeprefix("/echo ")
        await app.send_group_msg(group_id, content)
        return

    # /at — 回复并 @ 发送者
    if text == "/at":
        await app.send_group_msg(
            group_id,
            [At(sender.user_id), Text(" 你好!")],
        )
        return

    # /members — 群成员数
    if text == "/members":
        members = await app.get_group_member_list(group_id)
        await app.send_group_msg(group_id, f"本群共 {len(members)} 位成员")
        return

    # /chain — 演示 MessageChain 操作
    if text == "/chain":
        demo = MessageChain([Text("Hello "), At(sender.user_id), Text(" World")])
        lines = [
            f"display: {demo.display}",
            f"pure_text: {demo.pure_text}",
            f"has(At): {demo.has(At)}",
            f"count(Text): {demo.count(Text)}",
            f"len: {len(demo)}",
            f"include(Text): {demo.include(Text).display}",
        ]
        await app.send_group_msg(group_id, "\n".join(lines))
        return

    # /forward — 合并转发示例
    if text == "/forward":
        login = await app.get_login_info()
        nodes = [
            ForwardNode.custom(
                login.user_id,
                login.nickname,
                MessageChain("第一条: 你好").to_onebot(),
            ),
            ForwardNode.custom(
                login.user_id,
                login.nickname,
                MessageChain([Text("第二条: "), At(sender.user_id)]).to_onebot(),
            ),
            ForwardNode.custom(
                login.user_id,
                login.nickname,
                MessageChain("第三条: 这是合并转发演示").to_onebot(),
            ),
        ]
        await app.send_group_forward_msg(group_id, nodes)
        return

    # /help — 帮助
    if text == "/help":
        await app.send_group_msg(
            group_id,
            "可用命令:\n"
            "/ping - 存活检测\n"
            "/info - Bot 信息\n"
            "/echo <内容> - 复读\n"
            "/at - @ 你\n"
            "/members - 群成员数\n"
            "/chain - MessageChain 演示\n"
            "/forward - 合并转发演示\n"
            "/help - 显示帮助",
        )
        return


@broadcast.receiver(PrivateMessageEvent)
async def on_private_message(event: PrivateMessageEvent):
    chain = event.message_chain
    text = chain.pure_text.strip()

    if text == "/ping":
        await app.send_private_msg(event.user_id, "pong!")
        return

    # 私聊默认复读
    await app.send_private_msg(event.user_id, f"你说了: {chain.display}")


# ══════════════════════════════════════════════════════════════════════════════
#  通知处理
# ══════════════════════════════════════════════════════════════════════════════


@broadcast.receiver(GroupIncreaseNotice)
async def on_member_join(event: GroupIncreaseNotice):
    await app.send_group_msg(
        event.group_id,
        [At(event.user_id), Text(" 欢迎加入本群!")],
    )


@broadcast.receiver(GroupRecallNotice)
async def on_group_recall(event: GroupRecallNotice):
    pass


@broadcast.receiver(GroupPokeNotice)
async def on_poke(event: GroupPokeNotice):
    if event.target_id == event.self_id:
        await app.send_group_msg(event.group_id, "别戳我!")


@broadcast.receiver(FriendAddNotice)
async def on_friend_add(event: FriendAddNotice):
    await app.send_private_msg(event.user_id, "你好, 我们成为好友了!")


# ══════════════════════════════════════════════════════════════════════════════
#  请求处理
# ══════════════════════════════════════════════════════════════════════════════


@broadcast.receiver(FriendRequestEvent)
async def on_friend_request(event: FriendRequestEvent):
    await app.set_friend_add_request(flag=event.flag, approve=True)


@broadcast.receiver(GroupRequestEvent)
async def on_group_request(event: GroupRequestEvent):
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.launch_blocking()
