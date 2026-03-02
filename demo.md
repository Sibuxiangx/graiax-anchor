# 示例

## 私聊回复

```python
from graiax.anchor.event.message import PrivateMessageEvent


@broadcast.receiver(PrivateMessageEvent)
async def on_private_message(event: PrivateMessageEvent):
    chain = event.message_chain
    await app.send_private_msg(event.user_id, f"你说了: {chain.pure_text}")
```

## 使用消息段

```python
from graiax.anchor.message.segment import At, Image, Text


@broadcast.receiver(GroupMessageEvent)
async def on_group_message(event: GroupMessageEvent):
    chain = event.message_chain
    if chain.startswith("/pic"):
        await app.send_group_msg(
            event.group_id,
            [At(event.user_id), Text(" 这是你要的图片: "), Image(url="https://example.com/image.png")],
        )
```

## MessageChain 查询

```python
from graiax.anchor.message.segment import At, Image, Text

chain = event.message_chain

# 按类型索引
images = chain[Image]           # 获取所有图片段
first_at = chain.get_first(At)  # 获取第一个 @

# 检查与计数
chain.has(At)                   # 是否包含 @
chain.count(Text)               # Text 段数量
chain.only(Text, Image)         # 是否仅包含文本和图片

# 文本提取
chain.pure_text                 # 所有 Text 段拼接
chain.display                   # 可读文本表示

# 过滤
chain.include(Text, Image)      # 仅保留文本和图片
chain.exclude(At)               # 排除 @
chain.without_reply()           # 去除回复段

# 前后缀
chain.startswith("/cmd")
chain.removeprefix("/cmd")
chain.removesuffix("。")

# 回复
chain.reply                     # 获取回复段 (Reply | None)
```

## 消息解析器

```python
from graiax.anchor.message.parser import DetectPrefix, DetectSuffix, MatchRegex, MentionMe, ContainKeyword


# 前缀检测 — chain 自动去除前缀
@broadcast.receiver(GroupMessageEvent, decorators=[DetectPrefix("/cmd")])
async def on_command(event: GroupMessageEvent, chain: MessageChain):
    await app.send_group_msg(event.group_id, f"收到命令参数: {chain.pure_text}")


# @机器人 检测
@broadcast.receiver(GroupMessageEvent, decorators=[MentionMe()])
async def on_mention(event: GroupMessageEvent, chain: MessageChain):
    await app.send_group_msg(event.group_id, "你叫我？")


# 正则匹配
@broadcast.receiver(GroupMessageEvent, decorators=[MatchRegex(r"天气\s+(\S+)")])
async def on_weather(event: GroupMessageEvent, chain: MessageChain):
    await app.send_group_msg(event.group_id, "查询天气中...")


# 关键词包含
@broadcast.receiver(GroupMessageEvent, decorators=[ContainKeyword("早安")])
async def on_morning(event: GroupMessageEvent, chain: MessageChain):
    await app.send_group_msg(event.group_id, "早安！")
```

## 群管理操作

```python
# 全群禁言
await app.set_group_whole_ban(group_id, enable=True)

# 禁言指定成员 600 秒
await app.set_group_ban(group_id, user_id, duration=600)

# 踢出成员
await app.set_group_kick(group_id, user_id)

# 设置群名片
await app.set_group_card(group_id, user_id, card="新名片")

# 设置群名
await app.set_group_name(group_id, "新群名")

# 撤回消息
await app.delete_msg(message_id)
```

## 合并转发

```python
from graiax.anchor.message.segment import ForwardNode
from graiax.anchor.message.chain import MessageChain

nodes = [
    ForwardNode.custom(10001, "Alice", MessageChain("第一条消息").to_onebot()),
    ForwardNode.custom(10002, "Bob", MessageChain("第二条消息").to_onebot()),
    ForwardNode.reference(existing_message_id),  # 引用已有消息
]
await app.send_group_forward_msg(group_id, nodes)
```

## 通知事件处理

```python
from graiax.anchor.event.notice import (
    FriendAddNotice,
    GroupIncreaseNotice,
    GroupPokeNotice,
    GroupRecallNotice,
)


@broadcast.receiver(GroupIncreaseNotice)
async def on_member_join(event: GroupIncreaseNotice):
    await app.send_group_msg(event.group_id, [At(event.user_id), Text(" 欢迎!")])


@broadcast.receiver(GroupPokeNotice)
async def on_poke(event: GroupPokeNotice):
    if event.target_id == event.self_id:
        await app.send_group_msg(event.group_id, "别戳我!")


@broadcast.receiver(FriendAddNotice)
async def on_friend_add(event: FriendAddNotice):
    await app.send_private_msg(event.user_id, "你好, 我们成为好友了!")
```

## 请求处理

```python
from graiax.anchor.event.request import FriendRequestEvent, GroupRequestEvent


# 自动同意好友请求
@broadcast.receiver(FriendRequestEvent)
async def on_friend_request(event: FriendRequestEvent):
    await app.set_friend_add_request(flag=event.flag, approve=True)


# 加群请求 (需手动审核时可记录日志)
@broadcast.receiver(GroupRequestEvent)
async def on_group_request(event: GroupRequestEvent):
    await app.set_group_add_request(flag=event.flag, sub_type=event.sub_type, approve=True)
```

## 事件过滤器

```python
from graiax.anchor.util.validator import GroupValidator, UserValidator, CustomValidator


# 仅在指定群生效
@broadcast.receiver(GroupMessageEvent, decorators=[GroupValidator(123456, 789012)])
async def only_these_groups(event: GroupMessageEvent):
    ...


# 仅响应指定用户
@broadcast.receiver(GroupMessageEvent, decorators=[UserValidator(10001)])
async def only_this_user(event: GroupMessageEvent):
    ...


# 自定义条件
@broadcast.receiver(GroupMessageEvent, decorators=[CustomValidator(lambda e: e.group_id > 100000)])
async def custom_filter(event: GroupMessageEvent):
    ...
```

## 日志配置

```python
from graiax.anchor import Anchor, OneBotConfig
from graiax.anchor.log import LogConfig

# 默认 — 自动输出 [RECV] / [SEND] / [通知] / [请求] 日志
app = Anchor(broadcast=broadcast, config=config)

# 自定义日志级别
app = Anchor(broadcast=broadcast, config=config, log_config=LogConfig(log_level="DEBUG"))

# 禁用特定事件日志
from graiax.anchor.event.notice import GroupRecallNotice

app = Anchor(
    broadcast=broadcast,
    config=config,
    log_config=LogConfig(extra={GroupRecallNotice: None}),
)

# 禁用日志安装 (不替换 sys.excepthook, 不安装 richuru)
app = Anchor(broadcast=broadcast, config=config, install_log=False)
```
