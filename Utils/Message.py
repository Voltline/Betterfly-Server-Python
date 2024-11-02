import json
from datetime import datetime as dt


df = "%Y-%m-%d %H:%M:%S"

class RequestType:
    Login = 0
    Exit = 1
    Post = 2
    Key = 3


class ResponseType:
    Refused = 0
    Server = 1
    Post = 2
    File = 3
    Warn = 4
    PubKey = 5


class RequestMessage:
    def __init__(self, packet: str):
        self.packet_json = json.loads(packet)
        self.type = self.packet_json["type"]
        self.from_id = self.packet_json["from"]
        
        if self.type == RequestType.Post:
            self.from_user_id = self.packet_json["from"]
            self.from_user_name = self.packet_json["name"]
            self.is_group = self.packet_json["is_group"]
            self.to_id = self.packet_json["to"]
            self.msg = self.packet_json["msg"]
            self.msg_type = self.packet_json["msg_type"]
            self.timestamp = dt.now()
            self.name = ""
        
        if self.type == RequestType.Login:
            self.to_id = 0
            self.msg = ""
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

    def to_json_str(self):
        info = json.loads("{}")
        info["type"] = self.type
        if self.type != ResponseType.Refused:
            info["msg"] = self.msg
        
        return json.dumps(info)