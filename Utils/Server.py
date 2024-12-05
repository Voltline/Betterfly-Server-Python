import socket
import select
import errno
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as dt
from queue import Queue

import Utils.Message
import Utils.config
import Utils.RegexUtil
from Utils.apns import APNsClient, make_notification_payload
from Utils.Message import ResponseMessage, ResponseType, RequestMessage, RequestType, df
from Utils.color_logger import get_logger
from Utils.Encrypto import MessageDealer
from Utils.cos import cos_operator as cos
from Database.db_operator import DBOperator

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
        self.clients = {}  # {UserID: (Username, FileNo, socket)}
        self.fno_uid = {}  # {FileNo: UserID}
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

        # apns_send_queue 是一个保存推送请求的队列，保证线程安全
        self.apns_send_queue = Queue()

        # apns_send_thread 专门处理向Apple APNs推送的任务
        self.apns_send_thread = threading.Thread(target=self.apns_send_worker)
        self.apns_send_thread.start()

        # apns 用于专门处理苹果设备的推送请求
        self.apns = APNsClient(use_sandbox=False)

    def run(self):
        try:
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
                            if fileno in self.fno_uid:  # 已初始化用户发来的消息
                                self.executor.submit(self.receive_data, fileno)
                            elif fileno in self.temp_clients:  # 未初始化用户发来的消息
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

    def apns_send_worker(self):
        # 需要的消息：(apn_token, user_name, user_msg, user_id)
        while True:
            apns_token, user_name, user_msg, user_id = self.apns_send_queue.get()
            if apns_token is None:
                break
            result = self.apns.send_notification(apns_token, make_notification_payload(user_name, user_msg))
            if not result:  # 发送异常，删除APNs Token
                db = DBOperator()
                db.deleteUserAPNsToken(user_id, apns_token)

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
                all_dt = client_socket.recv(40960)
                if all_dt:
                    datum = MessageDealer.decode(all_dt)
                    has_correct_login_packet = False
                    for data in datum:
                        # 解析登录包
                        login_packet = Utils.Message.RequestMessage(data)
                        if login_packet.type == RequestType.Login:
                            has_correct_login_packet = True
                            user_id = login_packet.from_id
                            user_name = login_packet.name
                            last_login = login_packet.timestamp
                            if user_id:
                                self.clients[user_id] = (user_name, fileno, client_socket)
                                self.fno_uid[fileno] = user_id
                                self.temp_clients.pop(fileno)  # 从临时存储中删除
                                logger.info(f"User {user_id} - {user_name} connected with fileno {fileno}")
                                client_socket.send(ResponseMessage.make_server_message(
                                    f"Welcome to Betterfly, {user_name}!").to_json_encoded_bytes())
                                db = DBOperator()
                                db.login(user_id, user_name, last_login)
                                self.sync_message(user_id, last_login)
                            else:
                                logger.warning(f"Received empty user ID from fileno {fileno}")
                                self.disconnect_queue.put((fileno, False))
                    if not has_correct_login_packet:  # 未初始化用户发送非登录包，直接关闭连接
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
            all_dt = client_socket.recv(40960)
            if all_dt:
                datum = MessageDealer.decode(all_dt)
                for data in datum:
                    logger.info(f"Received data from user {user_id}: {data}")
                    task = Utils.Message.RequestMessage(data)
                    if task.type == RequestType.Exit:  # 执行退出操作
                        self.disconnect_queue.put((fileno, False))
                    elif task.type == RequestType.Post:  # 正常发消息
                        now = dt.now()
                        task.packet_json["timestamp"] = now.strftime(df)  # 重新授时
                        task.timestamp = now
                        to_id = task.to_id
                        is_group = task.is_group
                        db = DBOperator()
                        db.insertMessage(task.from_id, task.to_id, task.timestamp, task.msg, task.msg_type,
                                         task.is_group)

                        if is_group:
                            self.send_message(to_id, task, is_group=True, send_apns_push=True)
                        else:
                            self.send_message(user_id, task)  # 重授时后直接回显消息
                            if to_id != user_id:
                                self.send_message(to_id, task, send_apns_push=True)
                    elif task.type == RequestType.QueryUser:  # 从数据库请求用户信息
                        self.process_query_user(user_id, task)
                    elif task.type == RequestType.InsertContact:  # 增加联系人
                        self.process_insert_contact(task)
                    elif task.type == RequestType.QueryGroup:  # 从数据库请求群组信息
                        self.process_query_group(task)
                    elif task.type == RequestType.InsertGroup:  # 增加群组
                        self.process_insert_group(task)
                    elif task.type == RequestType.InsertGroupUser:  # 加入群组
                        self.process_insert_group_user(task)
                    elif task.type == RequestType.File:
                        self.process_file_operation(task)
                    elif task.type == RequestType.APNsToken:
                        self.process_user_apns_token(task)
                    elif task.type == RequestType.UpdateAvatar:  # 更新用户头像/群头像
                        self.process_update_avatar(task)

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
        db = DBOperator()
        query_user_name = db.queryUser(query_user_id)
        response = ResponseMessage.make_user_info_message(query_user_id, query_user_name)
        self.send_message(user_id, response)

    def process_insert_contact(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id  # 发起加好友的人的id
        o_user_id = task.to_id  # 要加好友的另一个人的id
        if o_user_id is None or user_id is None:
            logger.warning(f'In insert contact: user_id or o_user_id is None for task {task.to_json_str()}')
            return
        db = DBOperator()
        db.insertContact(user_id, o_user_id)

        response = ResponseMessage.make_hello_message(user_id, o_user_id, db.queryUser(user_id))
        self.send_message(user_id, response)
        self.send_message(o_user_id, response)

    def process_query_group(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        query_group_id = task.to_id
        during_add = task.msg != ''  # 是否是加群/建群之前的检查性查询
        db = DBOperator()
        query_group_name = db.queryGroup(query_group_id)
        response = ResponseMessage.make_group_info_message(query_group_id, query_group_name, during_add)
        self.send_message(user_id, response)

    def process_insert_group(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        group_id = task.to_id
        group_name = task.msg
        db = DBOperator()
        db.insertGroup(group_id, group_name)
        db.insertGroupUser(group_id, user_id)
        response = ResponseMessage.make_hello_message(0, group_id, group_name, True)
        self.send_message(group_id, response, is_group=True)

    def process_insert_group_user(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        group_id = task.to_id
        db = DBOperator()
        db.insertGroupUser(group_id, user_id)
        response = ResponseMessage.make_hello_message(user_id, group_id, '', True, "Hi")
        self.send_message(group_id, response, True)

    def process_file_operation(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        file_hash = task.file_hash
        file_suffix = task.file_suffix
        operation = task.file_operation
        db = DBOperator()
        file_exist = db.queryFile(file_hash, file_suffix)
        file_name = file_hash + "." + file_suffix
        content = ""
        response = ""
        if operation == "upload":
            if not file_exist:
                content = cos.get_presigned_upload_url("betterfly-1251588291", file_name)
                db.insertFile(file_hash, file_suffix)
            else:
                content = "Existed"
            response = ResponseMessage.make_upload_message(file_name, content)
        elif operation == "download":
            if not file_exist:
                content = "Not Exist"
            else:
                content = cos.get_presigned_download_url("betterfly-1251588291", file_name)
            response = ResponseMessage.make_download_message(file_name, content)
        self.send_message(user_id, response)

    def process_user_apns_token(self, task: Utils.Message.RequestMessage):
        user_id = task.from_id
        user_apns_token = task.apns_token
        db = DBOperator()
        db.insertUserAPNsToken(user_id, user_apns_token)  # 添加用户的APNs Token用于后续发送通知

    def process_update_avatar(self, task: Utils.Message.RequestMessage):
        id = task.from_id
        is_group = task.is_group
        avatar = task.msg
        db = DBOperator()
        if is_group:
            db.updateGroupAvatar(id, avatar)
            group_info = db.queryGroup(id)
            response = ResponseMessage.make_group_info_message(id, group_info)
            self.send_message(id, response, is_group=True)
        else:
            db.updateUserAvatar(id, avatar)
            user_info = db.queryUser(id)
            response = ResponseMessage.make_user_info_message(id, user_info)
            self.send_message(id, response)

    def sync_message(self, user_id: int, last_login: dt | str):
        """给客户端发送未登录期间收到的消息"""
        db = DBOperator()
        msg_list = db.querySyncMessage(user_id, last_login)
        for msg in msg_list:
            response = ResponseMessage(
                type=ResponseType.Post,
                from_id=msg[0],
                to_id=msg[1],
                timestamp=msg[2],
                msg=msg[3],
                msg_type=msg[4],
                # 数据库里的is_group字段是个整数1或0，ResponseMessage里用isinstance(x, bool)判断会丢失这个字段
                is_group=(msg[5] == 1)
            )
            # 开启同步转发时，关闭APNs推送
            self.send_message(user_id, response)

    def close_client(self, fileno, abnormal=False):
        user_id = self.fno_uid.get(fileno)

        if user_id is not None:
            try:
                client_socket = self.clients[user_id][2]
                logger.info(f"Connection closed from user {user_id}")
                if not abnormal:
                    client_socket.send(ResponseMessage.make_server_message("Goodbye!").to_json_encoded_bytes())
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
            self.disconnect_queue.put((None, None))
            self.initialize_queue.put(None)
            self.apns_send_queue.put((None, None, None, None))
            self.disconnect_thread.join()
            self.initialize_thread.join()
            self.apns_send_thread.join()
            self.epoll.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    def send_message(self, to_id: int, message: ResponseMessage | RequestMessage,
                     is_group=False, send_apns_push=False):
        # APNs 推送请求默认不发送
        from_id = message.from_id  # 把from_id的获取提前，方便某人同步全体消息时转发使用
        db = DBOperator()
        to_list = list()
        if is_group:
            if to_id == -1:  # 当转发全体消息时
                for uid, (uname, fno, sock) in self.clients.items():
                    sock.send(message.to_json_encoded_bytes())
                return  # 全体消息转发完毕，可以退出了
            to_list.extend(db.queryGroupUser(to_id))
        else:
            to_list.append(to_id)

        for user_id in to_list:
            if user_id != from_id:
                if send_apns_push:  # 仅当需要启用APNs推送时使用，消息同步的时候不进行这些操作
                    user_name = db.queryUser(from_id)
                    if message.msg_type == "file":  # 用于获取推送需要的body内容
                        user_msg = "[文件]"
                    elif message.msg_type == "gif":
                        user_msg = "[表情符号]"
                    elif message.msg_type == "image":
                        user_msg = "[图片]"
                    else:
                        if len(message.msg) > 30:  # 文本过长只显示您有一条新消息
                            user_msg = "您有一条新消息"
                        else:  # 否则显示文本内容
                            user_msg = message.msg

                    apns_list = db.queryUserAPNsTokens(user_id)  # 查询出用户所有的APNs Token
                    for apns_token in apns_list:  # 开始尝试向对应用户所有APNs Token发送
                        if apns_token[0] is not None:
                            # (apns_token, user_name, user_msg, user_id)
                            self.apns_send_queue.put((apns_token[0], user_name, user_msg, user_id))
            recv_info = self.clients.get(user_id)

            if recv_info is None:
                logger.warning(
                    f'Failed to get clients for user: {user_id}    While sending message: {message.to_json_str()}')
                continue
            recv_sock = recv_info[2]
            recv_sock.send(message.to_json_encoded_bytes())

            logger.info(f'Sent message to user {user_id}: {message.to_json_str()}')


if __name__ == "__main__":
    try:
        config_path = 'config.json'  # 配置文件路径
        server = EpollChatServer(config=config_path)
        server.run()
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}", exc_info=True)