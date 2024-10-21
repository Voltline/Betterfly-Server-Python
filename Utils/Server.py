import socket
import select
import errno
import logging
import Utils.config
import json
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import os
import threading
from Utils.Message import RequestMessage, ResponseMessage, RequestType, ResponseType


MAX_WORKER = 16
MAX_QUEUE = 256


class EpollChatServer:
    def __init__(self, config: str):
        # 加载配置
        self.config = Utils.config.Config(config)
        self.host = self.config.ip
        self.port = self.config.port

        # 设置日志配置
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # 创建一个 TCP/IP 套接字
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(MAX_QUEUE)
        self.server_socket.setblocking(False)

        # 创建 epoll 对象
        self.epoll = select.epoll()
        # 将服务器套接字注册到 epoll 中，用于读取新连接
        self.epoll.register(self.server_socket.fileno(), select.EPOLLIN)

        # 字典来保存客户端信息
        self.clients = {}       # {UserID: (Username, FileNo)}
        self.fno_uid = {}       # {FileNo: UserID}
        self.uninitialized_clients = set()  # 用于存储未初始化的客户端文件描述符

        # ThreadPoolExecutor 用于异步处理复杂任务
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER)

        # 全局消息队列，用于处理所有客户端的消息
        self.message_queue = Queue()

        # 启动一个后台线程来处理消息队列
        self.message_thread = threading.Thread(target=self.process_messages, daemon=True)
        self.message_thread.start()

    def run(self):
        try:
            while True:
                try:
                    # 等待事件发生
                    events = self.epoll.poll(timeout=1)
                    for fileno, event in events:
                        # 新的客户端连接
                        if fileno == self.server_socket.fileno():
                            self.accept_client()
                        # 客户端发来消息
                        elif event & select.EPOLLIN:
                            self.executor.submit(self.receive_data, fileno)
                        # 错误事件
                        elif event & (select.EPOLLHUP | select.EPOLLERR):
                            self.executor.submit(self.close_client, fileno)
                except Exception as e:
                    self.logger.error(f"Error in event loop: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Critical error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def accept_client(self):
        try:
            client_socket, client_address = self.server_socket.accept()
            client_socket.setblocking(False)
            # 将新的客户端 socket 注册到 epoll 中用于读取数据
            self.logger.info(f"{client_socket.fileno()} connect")
            self.epoll.register(client_socket.fileno(), select.EPOLLIN)
            self.uninitialized_clients.add(client_socket.fileno())  # 标记为未初始化的客户端
            self.logger.info(f"New connection from {client_address}")
        except Exception as e:
            self.logger.error(f"Error accepting new client: {e}", exc_info=True)

    def receive_data(self, fileno):
        try:
            data = os.read(fileno, 40960)
            if data:
                # 解析数据
                message = data.decode()
                parsed_data = RequestMessage(message)
                user_id = self.fno_uid.get(fileno)
                self.logger.info(f"{user_id}: {message}")

                if fileno in self.uninitialized_clients:
                    if parsed_data.type == RequestType.Login:
                        user_id = parsed_data.from_id
                        user_name = parsed_data.name
                        if user_id:
                            self.clients[user_id] = (user_name, fileno)
                            self.fno_uid[fileno] = user_id
                            self.uninitialized_clients.remove(fileno)  # 从未初始化集合中移除
                            self.logger.info(f"User {user_id} - {user_name} connected with fileno {fileno}")
                            # 发送欢迎消息
                            welcome_message = ResponseMessage.make_server_message(f"Welcome {user_name}!").to_json_str()
                            os.write(fileno, welcome_message.encode())
                    elif parsed_data.type == RequestType.Exit:
                        self.close_client(fileno)
                    else:
                        self.logger.info(f"Ignoring unsupported message type from uninitialized fileno {fileno}: {parsed_data.type}")
                else:
                    if parsed_data.type == RequestType.Exit:
                        self.close_client(fileno)
                    else:
                        # 将消息加入队列以供处理
                        self.message_queue.put({"user_id": user_id, "data": message})
            else:
                # 客户端已断开连接
                self.close_client(fileno)
        except OSError as e:
            if e.errno != errno.EAGAIN:
                self.logger.error(f"OS error while receiving data from fileno {fileno}: {e}", exc_info=True)
                self.close_client(fileno)
        except Exception as e:
            self.logger.error(f"Error receiving data from client: {e}", exc_info=True)
            self.close_client(fileno)

    def process_messages(self):
        while True:
            try:
                # 从消息队列中获取消息
                message = self.message_queue.get()
                if message:
                    user_id = message["user_id"]
                    data = message["data"]
                    # 解析消息并处理
                    self.logger.info(f"Processing message from user {user_id}: {data}")
                    parsed_data = RequestMessage(data)

                    if parsed_data.type == RequestType.All:
                        broadcast_message = ResponseMessage.make_post_message(ResponseType.Broadcast, user_id, parsed_data.msg, self.clients[user_id][0]).to_json_str()
                        self.broadcast_data(user_id, broadcast_message.encode())
                    else:
                        self.logger.info(f"Received unsupported message type from user {user_id}: {parsed_data.type}")
            except Exception as e:
                self.logger.error(f"Error processing message: {e}", exc_info=True)

    def broadcast_data(self, sender_user_id, data):
        for uid, (user_name, fno) in self.clients.items():
            if uid != sender_user_id and uid is not None:
                try:
                    os.write(fno, data)
                except (OSError, BrokenPipeError) as e:
                    self.logger.error(f"Error sending data to user {uid}: {e}", exc_info=True)
                    self.close_client(fno)
                except Exception as e:
                    self.logger.error(f"Unexpected error broadcasting data to user {uid}: {e}", exc_info=True)
                    self.close_client(fno)

    def close_client(self, fileno):
        user_id = self.fno_uid.get(fileno)

        if user_id is not None:
            try:
                self.logger.info(f"Connection closed for user {user_id}")
                self.epoll.unregister(fileno)
                os.close(fileno)
                self.clients.pop(user_id)
                self.fno_uid.pop(fileno)
            except Exception as e:
                self.logger.error(f"Error closing client connection for user {user_id}: {e}", exc_info=True)
        elif fileno in self.uninitialized_clients:
            # 如果 fileno 未找到对应用户且是未初始化的客户端
            try:
                self.logger.info(f"Connection closed for uninitialized fileno {fileno}")
                self.epoll.unregister(fileno)
                os.close(fileno)
                self.uninitialized_clients.remove(fileno)
            except Exception as e:
                self.logger.error(f"Error closing temporary client connection for fileno {fileno}: {e}", exc_info=True)
        else:
            # 如果 fileno 未找到对应用户
            try:
                self.logger.info(f"Connection closed for temporary fileno {fileno}")
                self.epoll.unregister(fileno)
                os.close(fileno)
            except Exception as e:
                self.logger.error(f"Error closing temporary client connection for fileno {fileno}: {e}", exc_info=True)

    def shutdown(self):
        try:
            # 发送服务器关闭消息给所有已连接用户
            for uid, (user_name, fno) in list(self.clients.items()):
                try:
                    shutdown_message = ResponseMessage.make_server_message("Server Close").to_json_str()
                    os.write(fno, shutdown_message.encode())
                except (OSError, BrokenPipeError) as e:
                    self.logger.error(f"Error sending shutdown message to user {uid}: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error sending shutdown message to user {uid}: {e}", exc_info=True)
                finally:
                    self.close_client(fno)

            # 检查服务器套接字是否有效，避免负数的文件描述符错误
            if self.server_socket.fileno() != -1:
                self.logger.info("Shutting down server...")
                self.epoll.unregister(self.server_socket.fileno())
                self.server_socket.close()
            # 关闭 epoll 对象
            self.epoll.close()
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        config_path = 'config.json'  # 配置文件路径
        server = EpollChatServer(config=config_path)
        server.run()
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}", exc_info=True)