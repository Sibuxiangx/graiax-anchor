"""Anchor 异常定义"""


class AnchorException(Exception):
    """graiax.anchor 基础异常."""


class AnchorConfigurationError(AnchorException):
    """Anchor 配置错误."""


class OneBotApiError(AnchorException):
    """OneBot API 返回错误时抛出.

    Attributes:
        retcode (int): OneBot 错误码.
        message (str): 错误信息.
        wording (str): 错误描述.
        data (dict | None): 原始返回数据.
    """

    def __init__(self, retcode: int, message: str = "", wording: str = "", data: dict | None = None):
        self.retcode = retcode
        self.message = message
        self.wording = wording
        self.data = data
        super().__init__(f"OneBot API error {retcode}: {message} ({wording})")


class BadRequestError(OneBotApiError):
    """错误码 1400: 请求格式错误或业务逻辑失败."""


class UnauthorizedError(OneBotApiError):
    """错误码 1401: 权限不足."""


class NotFoundError(OneBotApiError):
    """错误码 1404: 请求的资源不存在."""


class InvalidArgumentError(AnchorException):
    """提供了无效的参数."""


class AccountNotFoundError(AnchorException):
    """找不到指定的账号."""


class MessageTooLongError(AnchorException):
    """消息过长, 无法发送."""
