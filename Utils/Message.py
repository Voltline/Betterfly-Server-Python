import json
from enum import IntEnum
from datetime import datetime as dt


df = "%Y-%m-%d %H:%M:%S"


class RequestType(IntEnum):
    Login = 0
    Exit = 1
    Post = 2
    Key = 3
    QueryUser = 4


class ResponseType(IntEnum):
    Refused = 0
    Server = 1
    Post = 2
    File = 3
    Warn = 4
    PubKey = 5
    UserInfo = 6


class RequestMessage:
    def __init__(self, packet: str):
        self.packet_json = json.loads(packet)
        self.type = self.packet_json["type"]
        self.from_id = self.packet_json["from"]
        self.timestamp = dt.strptime(self.packet_json["timestamp"], df) if 'timestamp' in self.packet_json else dt.now()
        self.msg = self.packet_json["msg"] if 'msg' in self.packet_json else ''

        if self.type == RequestType.Post:
            self.from_user_id = self.packet_json["from"]
            self.from_user_name = self.packet_json["name"]
            self.is_group = self.packet_json["is_group"]
            self.to_id = self.packet_json["to"]
            self.msg_type = self.packet_json["msg_type"]
            self.name = ""
        
        elif self.type == RequestType.Login:
            self.to_id = 0
            self.name = self.packet_json["name"]



    def to_json_str(self):
        return json.dumps(self.packet_json)


class ResponseMessage:
    def __init__(self, type: ResponseType, from_id: int, msg: str, from_name: str = ""):
        self.type = type
        self.from_id = from_id
        self.msg = msg
        self.from_name = from_name

    @staticmethod
    def make_server_message(msg: str):
        return ResponseMessage(ResponseType.Server, -1, msg, "")
    
    @staticmethod
    def make_refused_message(msg: str):
        return ResponseMessage(ResponseType.Refused, -1, "", "")
    
    @staticmethod
    def make_warn_message(msg: str):
        return ResponseMessage(ResponseType.Server, -1, msg, "")

    @staticmethod
    def make_user_info_message(user_name: str):
        return ResponseMessage(ResponseType.UserInfo, 0, user_name, "")

    def to_json_str(self):
        info = json.loads("{}")
        info["type"] = self.type
        if self.type != ResponseType.Refused:
            info["msg"] = self.msg
        info['timestamp'] = datetime_str()
        
        return json.dumps(info)


def datetime_str(t: dt = None) -> str:
    """
    :param t: 不传入则获取当前服务器时间的字符串，传入则获取传入时间对应的字符串
    """
    if t is None:
        t = dt.now()
    return t.strftime(df)
