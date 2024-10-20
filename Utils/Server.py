import socket
import select
import errno
import logging
import Utils.Message
import Utils.config
import json


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
        self.server_socket.listen(100)
        self.server_socket.setblocking(False)

        # 创建 epoll 对象
        self.epoll = select.epoll()
        # 将服务器套接字注册到 epoll 中，用于读取新连接
        self.epoll.register(self.server_socket.fileno(), select.EPOLLIN)

        # 字典来保存用户ID，文件描述符和套接字对象的映射关系
        self.clients = {}       # {UserID: (Username, FileNo, socket)}
        self.fno_uid = {}       # {FileNo: UserID}
        self.temp_clients = {}  # 用于临时存储未分配用户ID的连接 {FileNo: socket}

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
                            if fileno in self.fno_uid:          # 收到已初始化用户的消息
                                self.receive_data(fileno)
                            elif fileno in self.temp_clients:   # 收到未初始化用户的消息
                                self.initialize_client(fileno)
                            else:
                                self.logger.warning(f"Received event for unknown fileno {fileno}, ignoring.")
                                self.epoll.unregister(fileno)
                        # 错误事件
                        elif event & (select.EPOLLHUP | select.EPOLLERR):
                            self.close_client(fileno)
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
            # 将新的客户端 socket 注册到 epoll 中，用于读取数据
            self.epoll.register(client_socket.fileno(), select.EPOLLIN)
            # 暂时将文件描述符与 socket 对象关联，等待接收用户ID
            self.temp_clients[client_socket.fileno()] = client_socket
            self.logger.info(f"New connection from {client_address}")
        except Exception as e:
            self.logger.error(f"Error accepting new client: {e}", exc_info=True)

    def initialize_client(self, fileno):
        try:
            client_socket = self.temp_clients[fileno]
            data = client_socket.recv(40960)
            if data:
                # 接收RequestMessage.Login包
                login_packet = Utils.Message.RequestMessage(data.decode())
                user_id = login_packet.from_id
                user_name = login_packet.name
                if user_id:
                    self.clients[user_id] = (user_name, fileno, client_socket)
                    self.fno_uid[fileno] = user_id
                    self.temp_clients.pop(fileno); # 从临时存储中删除
                    self.logger.info(f"User {user_id} - {user_name} connected with fileno {fileno}")     
                else:
                    self.logger.warning(f"Received empty user ID from fileno {fileno}")
                    self.close_client(fileno)
            else:
                # 客户端已断开连接
                self.close_client(fileno)
        except socket.error as e:
            if e.errno != errno.EAGAIN:
                # 处理异常并关闭连接
                self.logger.error(f"Socket error while initializing client for fileno {fileno}: {e}", exc_info=True)
                self.close_client(fileno)
        except Exception as e:
            # 对于初始化失败的情况，直接关闭连接
            self.logger.error(f"Error initializing client: {e}", exc_info=True)
            self.close_client(fileno)
            self.temp_clients.pop(fileno) # 从临时客户端目录中丢掉连接信息

    def receive_data(self, fileno):
        client_socket = None
        user_id = self.fno_uid.get(fileno)
        if user_id != None:
            client_socket = self.clients.get(user_id)[2]

        if client_socket is None:
            self.logger.error(f"Client socket for fileno {fileno} not found")
            return

        try:
            data = client_socket.recv(40960)
            if data:
                # TODO: 在此开始处理各种类型的消息
                # 处理正常消息
                self.logger.info(f"Received data from user {user_id}: {data.decode()} from {client_socket.getpeername()}")
            else:
                # 客户端已断开连接
                self.close_client(fileno)
        except socket.error as e:
            if e.errno != errno.EAGAIN:
                # 处理异常并关闭连接
                self.logger.error(f"Socket error while receiving data from fileno {fileno}: {e}", exc_info=True)
                self.close_client(fileno)
        except Exception as e:
            self.logger.error(f"Error receiving data from client: {e}", exc_info=True)
            self.close_client(fileno)

    def broadcast_data(self, sender_user_id, data):
        for uid, (user_name, fno, sock) in self.clients.items():
            if uid != sender_user_id and uid is not None:
                try:
                    sock.send(data)
                except (socket.error, BrokenPipeError) as e:
                    self.logger.error(f"Error sending data to user {uid}: {e}", exc_info=True)
                    self.close_client(fno)
                except Exception as e:
                    self.logger.error(f"Unexpected error broadcasting data to user {uid}: {e}", exc_info=True)
                    self.close_client(fno)

    def close_client(self, fileno):
        user_id = self.fno_uid.get(fileno)

        if user_id is not None:
            try:
                client_socket = self.clients[user_id][2]
                self.logger.info(f"Connection closed from {client_socket.getpeername()} for user {user_id}")
                self.epoll.unregister(fileno)
                client_socket.close()
                self.clients.pop(user_id)
                self.fno_uid.pop(fileno)
            except Exception as e:
                self.logger.error(f"Error closing client connection for user {user_id}: {e}", exc_info=True)
        elif fileno in self.temp_clients:
            # 如果 fileno 存在于临时客户端中
            try:
                client_socket = self.temp_clients[fileno]
                self.logger.info(f"Connection closed from {client_socket.getpeername()} for temporary fileno {fileno}")
                self.epoll.unregister(fileno)
                client_socket.close()
                self.temp_clients.pop(fileno)
            except Exception as e:
                self.logger.error(f"Error closing temporary client connection for fileno {fileno}: {e}", exc_info=True)

    def shutdown(self):
        try:
            # 发送服务器关闭消息给所有已连接用户
            for uid, (user_name, fno, sock) in list(self.clients.items()):
                try:
                    shutdown_message = json.dumps({"type": "server", "content": {"message": "Server Close"}})
                    sock.send(shutdown_message.encode())
                except (socket.error, BrokenPipeError) as e:
                    self.logger.error(f"Error sending shutdown message to user {uid}: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error sending shutdown message to user {uid}: {e}", exc_info=True)
                finally:
                    self.close_client(fno)

            # 关闭所有未完成的临时客户端连接
            for fileno, sock in list(self.temp_clients.items()):
                self.close_client(fileno)

            # 检查服务器套接字是否有效，避免文件描述符为负数的错误
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
