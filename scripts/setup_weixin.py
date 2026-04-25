#!/usr/bin/env python3
"""微信 iLink 扫码登录助手 — 获取二维码并轮询扫码状态."""
import base64
import json
import os
import struct
import sys
import time
import urllib.request

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
TOKEN_FILE = os.path.expanduser("~/.kiro/weixin_token.json")


def _get(url: str, timeout: int = 35) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    base = DEFAULT_BASE_URL.rstrip("/") + "/"

    print("📡 正在连接 iLink 服务器获取登录二维码...")
    qr_resp = _get(base + "ilink/bot/get_bot_qrcode?bot_type=3")
    qrcode_id = qr_resp.get("qrcode")
    qrcode_url = qr_resp.get("qrcode_img_content")

    if not qrcode_id or not qrcode_url:
        print("❌ 获取二维码失败，服务器返回:", qr_resp)
        return 1

    print("")
    print("=" * 50)
    print("📱 请用微信扫描下方二维码")
    print("=" * 50)
    print("")

    # 尝试显示 ASCII 二维码
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(qrcode_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print("(qrcode 库未安装，仅显示链接)")
    except Exception as e:
        print(f"(显示二维码失败: {e})")

    print("")
    print(f"或复制链接到浏览器: {qrcode_url}")
    print("")
    print("扫描后请在微信中点击「确认登录」...")
    print("")

    # 轮询扫码状态
    poll_url = base + f"ilink/bot/get_qrcode_status?qrcode={qrcode_id}"
    deadline = time.time() + 480
    headers = {"iLink-App-ClientVersion": "1"}

    while time.time() < deadline:
        try:
            req = urllib.request.Request(poll_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=40) as resp:
                status = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  [轮询错误] {e}")
            time.sleep(2)
            continue

        st = status.get("status", "wait")
        if st == "wait":
            print(".", end="", flush=True)
        elif st == "scaned":
            print("\n👀 已扫码，请在微信中点击确认...")
        elif st == "confirmed":
            bot_token = status.get("bot_token")
            base_url = status.get("baseurl", DEFAULT_BASE_URL)

            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, "w") as f:
                json.dump({"bot_token": bot_token, "base_url": base_url}, f)

            print(f"\n✅ 微信登录成功！")
            print(f"   Token: {bot_token[:20]}...")
            print(f"   已保存到: {TOKEN_FILE}")
            return 0
        elif st == "expired":
            print("\n❌ 二维码已过期，请重新运行 setup.sh")
            return 1

        time.sleep(1)

    print("\n❌ 登录超时（8分钟）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
