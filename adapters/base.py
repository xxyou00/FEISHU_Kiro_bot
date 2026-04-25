#!/usr/bin/env python3
"""PlatformAdapter 抽象基类与统一消息模型."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class IncomingMessage:
    platform: str
    raw_user_id: str
    unified_user_id: str
    message_id: str
    text: str
    chat_type: str = "private"
    is_at_me: bool = False
    context_token: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class OutgoingPayload:
    text: str
    images: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def platform(self) -> str:
        """平台标识，如 'feishu' 或 'weixin'."""

    @abstractmethod
    def start(self) -> None:
        """启动监听（阻塞或后台线程）."""

    @abstractmethod
    def send_text(self, raw_user_id: str, text: str, context_token: str | None = None) -> None:
        """主动推送文本消息."""

    @abstractmethod
    def reply(self, incoming: IncomingMessage, payload: OutgoingPayload) -> None:
        """回复某条 incoming 消息."""

    @abstractmethod
    def upload_image(self, path: str) -> str | None:
        """上传图片，返回平台特定的 media_key."""

    @abstractmethod
    def upload_file(self, path: str) -> str | None:
        """上传文件，返回平台特定的 file_key."""
