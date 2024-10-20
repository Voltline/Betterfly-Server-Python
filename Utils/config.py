import json


class Config:
    def __init__(self, path: str):
        """
        :param path: 配置文件路径
        """
        self.path = path
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.ip = data['ip']
            self.port = data['port']