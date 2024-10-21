import json


class RequestType:
    Login = 0
    Exit = 1
    Single = 2
    Multi = 3
    All = 4
    Key = 5


class ResponseType:
    Refused = 0
    Server = 1
    Client = 2
    Broadcast = 3
    Multicast = 4
    File = 5
    Warn = 6
    PubKey = 7


class RequestMessage:
    def __init__(self, packet: str):
        # print(packet)
        packet_json = json.loads(packet)
        self.type = packet_json["type"]
        self.from_id = packet_json["from"]
        
        if self.type in [RequestType.Single, RequestType.Multi, RequestType.All]:
            self.to_ids = packet_json["to"]
            self.msg = packet_json["msg"]
            self.name = ""
        
        if self.type == RequestType.Login:
            self.to_ids = []
            self.msg = ""
            self.name = packet_json["name"]


class ResponseMessage:
    def __init__(self, type: ResponseType, from_id: int, msg: str, from_name: str = ""):
        self.type = type
        self.from_id = from_id
        self.msg = msg
        self.from_name = from_name

    @staticmethod
    def make_server_message(msg: str):
        return ResponseMessage(ResponseMessage.Server, -1, msg, "")
    
    @staticmethod
    def make_refused_message(msg: str):
        return ResponseMessage(ResponseMessage.Refused, -1, "", "")
    
    @staticmethod
    def make_post_message(type: ResponseType, from_id: int, msg: str, from_name: str):
        # Include Client, Broadcast and Multicast
        return ResponseMessage(type, from_id, msg, from_name)
    
    @staticmethod
    def make_warn_message(msg: str):
        return ResponseMessage(ResponseMessage.Server, -1, msg, "")

    def to_json_str(self):
        info = json.json()
        info["type"] = self.type
        if self.type != ResponseType.Refused:
            info["msg"] = self.msg
        
        if self.type in [ResponseType.Client, ResponseType.Broadcast, ResponseType.Multicast]:
            info["from"] = self.from_id
            info["from_name"] = self.from_name
        
        return json.dumps(info)