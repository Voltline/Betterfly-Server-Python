import datetime
import socket
import select
import errno
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as dt
from queue import Queue

import Utils.Message
import Utils.config
from Utils.Message import ResponseMessage, ResponseType, RequestMessage, RequestType, df
from Database.db_operator import db_operator as db
from Utils.cos import COS as cos
from Utils.color_logger import get_logger
logger = get_logger(__name__)

MAX_WORKER = 16
MAX_QUEUE = 200


class EpollChatServer:
    def __init__(self, config: str):
        # 加载配置
        self.config = Utils.config.Config(config)
        self.host = self.config.ip
        self.port = self.config.port

        # 设置日志配置
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.clients = {}       # {UserID: (Username, FileNo, socket)}
        self.fno_uid = {}       # {FileNo: UserID}
        self.temp_clients = {}  # 用于临时存储未分配用户ID的连接 {FileNo: socket}

        # ThreadPoolExecutor 用于异步处理复杂任务
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER)

        # disconnect_queue 是一个保存需要关闭的fd的队列，保证线程安全
        self.disconnect_queue = Queue()

        # initialize_queue 是一个保存需要连接初始化的fd的队列，保证线程安全
        self.initialize_queue = Queue()

        # disconnect_thread 专门处理关闭连接的任务
        self.disconnect_thread = threading.Thread(target=self.close_worker)
        self.disconnect_thread.start()
        # initialize_thread 专门处理连接初始化的任务
        self.initialize_thread = threading.Thread(target=self.initialize_worker)
        self.initialize_thread.start()

    def run(self):
        try:
            db.connect()
            logger.info('Server started successfully')
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
                            if fileno in self.fno_uid:          # 已初始化用户发来的消息
                                self.executor.submit(self.receive_data, fileno)
                            elif fileno in self.temp_clients:   # 未初始化用户发来的消息
                                self.initialize_queue.put(fileno)
                            else:
                                logger.warning(f"Received event for unknown fileno {fileno}, ignoring.")
                                self.epoll.unregister(fileno)
                        # 错误事件
                        elif event & (select.EPOLLHUP | select.EPOLLERR):
                            self.disconnect_queue.put((fileno, True))
                except Exception as e:
                    logger.error(f"Error in event loop: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Critical error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def close_worker(self):
        while True:
            fileno, abnormal = self.disconnect_queue.get()
            if fileno is None:
                break
            self.close_client(fileno, abnormal)

    def initialize_worker(self):
        while True:
            fileno = self.initialize_queue.get()
            if fileno is None:
                break
            self.initialize_client(fileno)

    def accept_client(self):
        try:
            client_socket, client_address = self.server_socket.accept()
            client_socket.setblocking(False)
            # 将新的客户端 socket 注册到 epoll 中用于读取数据
            self.epoll.register(client_socket.fileno(), select.EPOLLIN)
            # 暂时将套接字存储起来，等待分配用户ID
            self.temp_clients[client_socket.fileno()] = client_socket
            logger.info(f"New connection from {client_address}")
        except Exception as e:
            logger.error(f"Error accepting new client: {e}", exc_info=True)

    def initialize_client(self, fileno):
        logger.info(f"Initializing client {fileno}")
        try:
            client_socket = self.temp_clients.get(fileno)
            if client_socket is not None:
                data = client_socket.recv(40960)
                if data:
                    # 解析登录包
                    login_packet = Utils.Message.RequestMessage(data.decode())
                    if login_packet.type == RequestType.Login:
                        user_id = login_packet.from_id
                        user_name = login_packet.name
                        last_login = login_packet.timestamp
                        if user_id:
                            self.clients[user_id] = (user_name, fileno, client_socket)
                            self.fno_uid[fileno] = user_id
                            self.temp_clients.pop(fileno)  # 从临时存储中删除
                            logger.info(f"User {user_id} - {user_name} connected with fileno {fileno}")
                            client_socket.send(ResponseMessage.make_server_message(
                                f"Welcome to Betterfly, {user_name}!").to_json_str().encode())
                            db.login(user_id, user_name, last_login)
                        else:
                            logger.warning(f"Received empty user ID from fileno {fileno}")
                            self.disconnect_queue.put((fileno, False))
                    else:  # 未初始化用户发送非登录包，直接关闭连接
                        logger.warning(f"Received invalid request from fileno {fileno}")
                        self.disconnect_queue.put((fileno, False))
                else:
                    # 客户端已断开连接
                    self.disconnect_queue.put((fileno, True))
        except socket.error as e:
            if e.errno != errno.EAGAIN:
                logger.error(f"Socket error while initializing client for fileno {fileno}: {e}", exc_info=True)
                self.disconnect_queue.put((fileno, True))
        except Exception as e:
            logger.error(f"Error initializing client: {e}", exc_info=True)
            self.disconnect_queue.put((fileno, False))
            self.temp_clients.pop(fileno, None)  # 如果存在则从临时存储中删除

    def receive_data(self, fileno):
        client_socket = None
        user_id = self.fno_uid.get(fileno)
        if user_id is not None:
            client_socket = self.clients.get(user_id)[2]

        if client_socket is None:
            logger.error(f"Client socket for fileno {fileno} not found")
            return

        try:
            data = client_socket.recv(40960)
            logger.info(f"Received data from user {user_id}: {data.decode()}")
            if data:
                task = Utils.Message.RequestMessage(data.decode())
                if task.type == RequestType.Exit:  # 执行退出操作
                    self.disconnect_queue.put((fileno, False))
                elif task.type == RequestType.Post:  # 正常发消息
                    now = dt.now()
                    task.packet_json["timestamp"] = now.strftime(df)  # 重新授时
                    task.timestamp = now
                    to_id = task.to_id
                    is_group = task.is_group
                    db.insertMessage(task.from_id, task.to_id, task.timestamp, task.msg, task.msg_type, task.is_group)
                    self.send_message(user_id, task)  # 重授时后直接回显消息
                    if to_id == -1:
                        for uid, (uname, fno, sock) in self.clients.items():
                            if uid != user_id:
                                sock.send(task.to_json_str().encode())
                    else:
                        if to_id != user_id:
                            to_info = self.clients.get(to_id)
                            if to_info is not None:
                                uname, fno, sock = to_info
                                sock.send(task.to_json_str().encode())
                elif task.type == RequestType.QueryUser:  # 从数据库请求用户信息
                    self.process_query_user(user_id, task)
                elif task.type == RequestType.InsertContact:  # 增加联系人
                    self.process_insert_contact(task)
                elif task.type == RequestType.QueryGroup:  # 从数据库请求群组信息
                    self.process_query_group(task)
                elif task.type == RequestType.InsertGroup:  # 增加群组
                    self.process_insert_group(task)

            else:
                # 客户端已断开连接
                self.disconnect_queue.put((fileno, True))
        except socket.error as e:
            if e.errno != errno.EAGAIN:
                logger.error(f"Socket error while receiving data from fileno {fileno}: {e}", exc_info=True)
                self.disconnect_queue.put((fileno, True))
        except Exception as e:
            logger.error(f"Error receiving data from client: {e}", exc_info=True)
            self.disconnect_queue.put((fileno, True))

    def process_query_user(self, user_id: int, task: Utils.Message.RequestMessage):
        """
        :param user_id: 发起请求的用户id
        :param task: 请求内容
        """
        query_user_id = task.to_id
        query_user_name = db.queryUser(query_user_id)
        response = ResponseMessage.make_user_info_message(query_user_id, query_user_name)
        self.send_message(user_id, response)

    def process_insert_contact(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id  # 发起加好友的人的id
        o_user_id = task.to_id  # 要加好友的另一个人的id
        if o_user_id is None or user_id is None:
            logger.warning(f'In insert contact: user_id or o_user_id is None for task {task.to_json_str()}')
            return
        db.insertContact(user_id, o_user_id)

        response = ResponseMessage.make_hello_message(user_id, o_user_id, db.queryUser(user_id))
        self.send_message(user_id, response)
        self.send_message(o_user_id, response)

    def process_query_group(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        query_group_id = task.to_id
        during_add = task.msg != ''  # 是否是加群/建群之前的检查性查询
        query_group_name = db.queryGroup(query_group_id)
        response = ResponseMessage.make_group_info_message(query_group_id, query_group_name, during_add)
        self.send_message(user_id, response)

    def process_insert_group(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        group_id = task.to_id
        group_name = task.msg
        db.insertGroup(group_id, group_name)  # TODO: 数据库插入时的错误消息处理
        db.insertGroupUser(group_id, user_id)
        response = ResponseMessage.make_hello_message(0, group_id, group_name, True)
        self.send_message(user_id, response)

    def process_insert_group_user(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        group_id = task.to_id
        db.insertGroupUser(group_id, user_id)
        response = ResponseMessage.make_hello_message(user_id, group_id, '', True, "Hi")
        self.send_message(user_id, response)

    def close_client(self, fileno, abnormal = False):
        user_id = self.fno_uid.get(fileno)

        if user_id is not None:
            try:
                client_socket = self.clients[user_id][2]
                logger.info(f"Connection closed from user {user_id}")
                if not abnormal:
                    client_socket.send(ResponseMessage.make_server_message("Goodbye!").to_json_str().encode())
                    self.epoll.unregister(fileno)
                client_socket.close()
                self.clients.pop(user_id)
                self.fno_uid.pop(fileno)
            except Exception as e:
                logger.error(f"Error closing client connection for user {user_id}: {e}", exc_info=True)
        elif fileno in self.temp_clients:
            # 如果 fileno 存在于临时客户端中
            try:
                client_socket = self.temp_clients[fileno]
                logger.info(f"Connection closed from temporary fileno {fileno}")
                if not abnormal:
                    self.epoll.unregister(fileno)
                client_socket.close()
                self.temp_clients.pop(fileno)
            except Exception as e:
                logger.error(f"Error closing temporary client connection for fileno {fileno}: {e}", exc_info=True)

    def shutdown(self):
        try:
            # 发送服务器关闭消息给所有已连接用户
            for uid, (user_name, fno, sock) in list(self.clients.items()):
                self.disconnect_queue.put((fno, False))

            # 关闭所有未完成的临时客户端连接
            for fno, sock in list(self.temp_clients.items()):
                self.disconnect_queue.put((fno, False))

            # 检查服务器套接字是否有效，避免负数的文件描述符错误
            if self.server_socket.fileno() != -1:
                logger.info("Shutting down server...")
                self.epoll.unregister(self.server_socket.fileno())
                self.server_socket.close()
            # 关闭 epoll 对象
            self.disconnect_thread.join()
            self.initialize_thread.join()
            self.epoll.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    def send_message(self, user_id: int, message: ResponseMessage | RequestMessage):
        recv_info = self.clients.get(user_id)
        if recv_info is None:
            logger.warning(f'Failed to get clients for user: {user_id}')
            logger.warning(f'While sending message: {message.to_json_str()}')
            return
        recv_sock = recv_info[2]
        recv_sock.send(message.to_json_str().encode())


if __name__ == "__main__":
    try:
        config_path = 'config.json'  # 配置文件路径
        server = EpollChatServer(config=config_path)
        server.run()
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}", exc_info=True)