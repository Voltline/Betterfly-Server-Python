import socket
import sys
import json
import time


class RequestType:
    Login = 0
    Exit = 1
    Single = 2
    Multi = 3
    All = 4
    Key = 5


class SimpleTCPClient:
    def __init__(self, host: str, port: int, user_id: int, username: str):
        self.server_address = (host, port)
        self.user_id = user_id
        self.username = username
        self.client_socket = None
        self.connected = False
        self.connect()
        self.initialize_user_id()
        time.sleep(1)  # 给服务器时间处理登录请求

    def connect(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect(self.server_address)
            self.connected = True
            print(f"Connected to server at {self.server_address[0]}:{self.server_address[1]}")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            sys.exit(1)

    def initialize_user_id(self):
        # 发送登录请求以进行初始化
        if self.connected:
            try:
                login_message = self.create_message(RequestType.Login, {"from": self.user_id, "name": self.username})
                self.client_socket.sendall(login_message.encode())
                print(f"Sent login message: {login_message}")
                # 等待服务器确认
                self.receive_message()
            except (socket.error, BrokenPipeError) as e:
                print(f"Error sending login message: {e}")
                self.handle_disconnection()

    def send_message(self, msg_type: int, content: dict):
        if not self.connected:
            print("Not connected to server. Cannot send message.")
            return

        message = self.create_message(msg_type, content)
        try:
            self.client_socket.sendall(message.encode())
            print(f"Sent: {message}")
        except (socket.error, BrokenPipeError) as e:
            print(f"Error sending message: {e}")
            self.handle_disconnection()

    def receive_message(self):
        if not self.connected:
            print("Not connected to server. Cannot receive message.")
            return

        try:
            data = self.client_socket.recv(4096)
            if data:
                print(f"Received: {data.decode()}")
        except socket.error as e:
            print(f"Error receiving message: {e}")
            self.handle_disconnection()

    def handle_disconnection(self):
        if not self.connected:
            return

        print("Handling disconnection... Reconnecting...")
        self.close()
        time.sleep(2)  # 等待两秒后尝试重新连接
        self.connect()
        self.initialize_user_id()  # 重新连接后重新发送用户ID

    @staticmethod
    def create_message(msg_type: int, content: dict) -> str:
        return json.dumps({
            "type": msg_type,
            **content
        })

    def close(self):
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                print(f"Error during shutdown: {e}")
            self.client_socket.close()
            self.connected = False
            print("Connection closed.")


if __name__ == "__main__":
    host = '127.0.0.1'  # 服务器的 IP 地址
    port = 54342  # 服务器的端口
    user_id = 44248193  # 用户ID，用于在连接时进行初始化
    username = 'Voltline'  # 用户名

    client = SimpleTCPClient(host, port, user_id, username)
    try:
        # 等待服务器处理登录请求后再发送消息
        time.sleep(2)
        # 测试发送广播消息
        client.send_message(RequestType.All, {"from": user_id, "msg": "Hello, everyone!"})
        time.sleep(1)
        client.receive_message()
    finally:
        client.close()
