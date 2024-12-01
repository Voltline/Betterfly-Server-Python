import jwt
import time
import httpx
import json
import os

from Utils.color_logger import get_logger
logger = get_logger(__name__)

root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config_dir = os.path.join(root_dir, "Config")
config_fp = os.path.join(config_dir, 'AuthKey_8UZN8NKG46.p8')


class APNsClient:
    def __init__(self, use_sandbox: bool = True):
        """
        初始化 APNs 客户端。

        :param team_id: Apple Developer Team ID
        :param key_id: APNs 密钥的 Key ID
        :param bundle_id: 应用的 Bundle ID
        :param key_path: 本地 .p8 文件的路径
        :param use_sandbox: 是否使用沙盒环境（默认 True，生产环境为 False）
        """
        self.team_id = "BYMJC965BC"
        self.key_id = "8UZN8NKG46"
        self.bundle_id = "com.betterfly.betterflyclient"
        self.key_path = config_fp
        self.apns_url = "https://api.sandbox.push.apple.com" if use_sandbox else "https://api.push.apple.com"

    def _generate_jwt(self) -> str:
        """
        生成用于 APNs 请求的 JWT。

        :return: JWT 字符串
        """
        with open(self.key_path, "r") as f:
            private_key = f.read()

        token = jwt.encode(
            {"iss": self.team_id, "iat": int(time.time())},
            private_key,
            algorithm="ES256",
            headers={"alg": "ES256", "kid": self.key_id}
        )
        return token

    def send_notification(self, device_token: str, payload: dict) -> bool:
        """
        向指定设备发送推送通知。

        :param device_token: 目标设备的 Token
        :param payload: 推送通知的 JSON 数据
        :return: APNs 响应
        """
        headers = {
            "Authorization": f"bearer {self._generate_jwt()}",
            "apns-topic": self.bundle_id,
        }
        client = httpx.Client(http2=True)
        url = f"{self.apns_url}/3/device/{device_token}"
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()  # 如果状态码非200，抛出异常
            logger.info({"status": response.status_code, "data": response.json() if response.text else {}})
            return True
        except httpx.HTTPStatusError as e:
            logger.error({"status": e.response.status_code, "error": e.response.text})
            return False
        except Exception as e:
            logger.error({"status": "unknown_error", "error": str(e)})
            return False


def make_notification_payload(user_name: str, msg: str) -> dict:
    info = {"aps": {"alert": {}, "sound": "default", "badge": 1}}
    info["aps"]["alert"]["title"] = user_name
    info["aps"]["alert"]["body"] = msg
    info["aps"]["alert"]["sound"] = "default"
    return info
