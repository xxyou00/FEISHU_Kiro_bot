#!/usr/bin/env python3
import pytest
from adapters.weixin import WeixinAdapter, _headers, _split_text


def test_headers_without_token():
    h = _headers()
    assert h["Content-Type"] == "application/json"
    assert h["AuthorizationType"] == "ilink_bot_token"
    assert "Authorization" not in h
    assert "X-WECHAT-UIN" in h


def test_headers_with_token():
    h = _headers("abc123")
    assert h["Authorization"] == "Bearer abc123"


def test_split_text_short():
    assert _split_text("hello", 2000) == ["hello"]


def test_split_text_long():
    text = "a" * 2500
    chunks = _split_text(text, 2000)
    assert len(chunks) == 2
    assert len(chunks[0]) <= 2000


class TestWeixinAdapter:
    def test_handle_incoming_text(self):
        received = []
        adapter = WeixinAdapter(bot_token="fake", on_message=lambda m: received.append(m))
        adapter._context_tokens = {}
        msg = {
            "message_type": 1,
            "from_user_id": "wxid_abc@im.wechat",
            "context_token": "ctx_123",
            "client_id": "msg_001",
            "item_list": [{"type": 1, "text_item": {"text": "  hello  "}}],
        }
        adapter._handle_incoming(msg)
        assert len(received) == 1
        assert received[0].platform == "weixin"
        assert received[0].raw_user_id == "wxid_abc@im.wechat"
        assert received[0].text == "hello"
        assert adapter._context_tokens["wxid_abc@im.wechat"] == "ctx_123"

    def test_send_text_without_context_token_logs_error(self, caplog):
        import logging
        adapter = WeixinAdapter(bot_token="fake", on_message=lambda m: None)
        with caplog.at_level(logging.ERROR):
            adapter.send_text("wxid_abc", "hi")
        assert "缺少 context_token" in caplog.text
