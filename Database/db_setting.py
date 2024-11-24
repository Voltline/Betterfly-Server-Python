import json


class DBSetting():
    """数据库的设置信息"""

    def __init__(self, config: str | dict):
        """
        初始化
        :param info:可以是json文件的路径或是json字典
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                config = json.load(f)

        self.user = config["user"]
        self.password = config["password"]
        self.ip = config["ip"]
        self.port = config["port"]
        self.database = config["db"]
        self.charset = config["charset"]

