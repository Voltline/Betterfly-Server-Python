import json
from datetime import datetime as dt
from enum import IntEnum

from Database.db_operator import DBOperator
from Utils.Encrypto import MessageDealer

df = "%Y-%m-%d %H:%M:%S"


class RequestType(IntEnum):
    Login = 0  # 与服务建立连接
    Exit = 1  # 关闭与服务器的连接
    Post = 2  # 正常发信
    Key = 3  # 本地发送对称密钥
    QueryUser = 4  # 通过id请求用户信息
    InsertContact = 5  # 添加联系人
    QueryGroup = 6  # 通过id请求群组信息
    InsertGroup = 7  # 添加群组
    InsertGroupUser = 8  # 向群组中添加用户
    File = 9  # 文件上传/下载请求
    APNsToken = 10  # 用户APNs Token
    UpdateAvatar = 11  # 上传用户头像或群头像


class ResponseType(IntEnum):
    Refused = 0
    Server = 1  # 服务器消息
    Post = 2  # 正常发信
    File = 3  # 文件下载/上传链接/已存在通知
    Warn = 4  # 警告信息
    PubKey = 5  # RSA公钥响应信息
    UserInfo = 6  # 告知被查询的用户信息
    GroupInfo = 7  # 告知被查询的群组信息


class RequestMessage:
    def __init__(self, packet: str):
        self.packet_json = json.loads(packet)
        self.type: int = self.packet_json["type"] if 'type' in self.packet_json else -1
        self.from_id: int = self.packet_json["from"] if "from" in self.packet_json else 0
        self.to_id: int = self.packet_json["to"] if 'to' in self.packet_json else 0
        self.timestamp: dt = dt.strptime(self.packet_json["timestamp"], df) if self.packet_json.get(
            "timestamp") else dt.now()
        self.msg: str = self.packet_json["msg"] if 'msg' in self.packet_json else ''
        self.is_group = self.packet_json["is_group"] if 'is_group' in self.packet_json else False

        if self.type == RequestType.Post:
            self.name = self.packet_json["name"]
            self.msg_type = self.packet_json["msg_type"]
            self.name = ""

        elif self.type == RequestType.Login:
            self.to_id = 0
            self.name = self.packet_json["name"]
            self.user_apn_token = self.packet_json["user_apn_token"] if 'user_apn_token' in self.packet_json else ''

        elif self.type == RequestType.File:
            self.file_hash = self.packet_json["file_hash"]
            self.file_suffix = self.packet_json["file_suffix"]
            self.file_operation = self.packet_json["operation"]

        elif self.type == RequestType.APNsToken:
            self.apns_token = self.packet_json["apns_token"]

    def to_json_str(self):
        return json.dumps(self.packet_json)

    def to_json_encoded_bytes(self) -> bytes:
        return MessageDealer.encode(self.to_json_str())


class ResponseMessage:
    def __init__(self, type: ResponseType, from_id: int, msg: str, from_name: str = "",
                 to_id: int = 0, is_group: bool = None, content: str = "",
                 timestamp: dt | str = None, msg_type: str = None, file_op: str = None):
        self.type = type
        self.from_id = from_id
        self.msg = msg
        self.from_name = from_name
        self.to_id = to_id
        self.is_group = is_group
        self.content = content
        self.timestamp = timestamp
        self.msg_type = msg_type
        self.file_op = file_op

    @staticmethod
    def make_server_message(msg: str):
        return ResponseMessage(ResponseType.Server, -1, msg, "")

    @staticmethod
    def make_refused_message(msg: str):
        return ResponseMessage(ResponseType.Refused, -1, "", "")

    @staticmethod
    def make_upload_message(file_full_name: str, content: str):
        return ResponseMessage(ResponseType.File, 0, file_full_name, content=content, file_op="upload")

    @staticmethod
    def make_download_message(file_full_name: str, content: str):
        return ResponseMessage(ResponseType.File, 0, file_full_name, content=content, file_op="download")

    @staticmethod
    def make_warn_message(msg: str):
        return ResponseMessage(ResponseType.Server, -1, msg, "")

    @staticmethod
    def make_user_info_message(user_id: int, user_info: str):
        return ResponseMessage(ResponseType.UserInfo, 0, user_info, "", user_id)

    @staticmethod
    def make_group_info_message(group_id: int, group_info: str, during_add: bool = False):
        from_id = -1 if during_add else 0
        return ResponseMessage(ResponseType.GroupInfo, from_id, group_info, "", group_id)

    @staticmethod
    def make_hello_message(from_user_id: int, to_id: int, from_user_name: str = '',
                           is_group: bool = False, msg: str = "Hello"):
        """此消息会在创建时录入数据库"""
        response = ResponseMessage(ResponseType.Post, from_user_id, msg, from_user_name, to_id, is_group,
                                   timestamp=dt.now().strftime(df), msg_type="text")
        db = DBOperator()
        db.insertMessage(response.from_id, response.to_id, response.timestamp, response.msg, "text", response.is_group)
        return response

    def to_json_str(self):
        info = json.loads("{}")
        info["type"] = self.type
        info['timestamp'] = datetime_str(self.timestamp)
        if self.type != ResponseType.Refused:
            info["msg"] = self.msg
        if self.from_id is not None:
            info['from'] = self.from_id
        if self.to_id is not None:
            info['to'] = self.to_id
        if isinstance(self.is_group, bool):
            info['is_group'] = self.is_group
        if self.from_name:
            info["name"] = self.from_name
        if self.content:
            info['content'] = self.content
        if self.msg_type:
            info['msg_type'] = self.msg_type
        if self.file_op:
            info['file_op'] = self.file_op

        return json.dumps(info)

    def to_json_encoded_bytes(self) -> bytes:
        return MessageDealer.encode(self.to_json_str())


def datetime_str(t: dt = None) -> str:
    """
    :param t: 不传入则获取当前服务器时间的字符串，传入则获取传入时间对应的字符串
    """
    if t is None:
        t = dt.now()
    return t.strftime(df)
