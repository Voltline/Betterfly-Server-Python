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


class COSConfig:
    """ COS配置文件JSON：
    {
      "secret_id": "",
      "secret_key": "",
      "region": "ap-shanghai"
    }
    """
    def __init__(self, path: str):
        """
        :param path: 配置COS配置文件路径
        """
        self.path = path
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.secret_id = data["secret_id"]
            self.secret_key = data["secret_key"]
            self.region = data["region"]