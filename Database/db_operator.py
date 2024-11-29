import pymysql as sql
from pymysql.cursors import Cursor
from pymysql.connections import Connection
import os
import datetime
import time as t

from Database.db_setting import DBSetting
from Utils.color_logger import get_logger
logger = get_logger(__name__)

root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config_dir = os.path.join(root_dir, "Config")
config_fp = os.path.join(config_dir, 'database_config.json')


class DBOperator:
    """数据库操作相关方法"""

    __setting = DBSetting(config_fp)
    __db: Connection = None
    __cur: Cursor = None

    def __init__(self):
        self.connect()

    def __del__(self):
        self.disconnect()

    @staticmethod
    def connect():
        """连接到数据库"""
        DBOperator.__db = sql.connect(
            host=DBOperator.__setting.ip,
            port=DBOperator.__setting.port,
            user=DBOperator.__setting.user,
            password=DBOperator.__setting.password,
            database=DBOperator.__setting.database,
            charset=DBOperator.__setting.charset,
        )
        DBOperator.__cur = DBOperator.__db.cursor()

    @staticmethod
    def disconnect():
        """断开与数据库的连接"""
        DBOperator.__db.commit()
        DBOperator.__cur.close()
        DBOperator.__db.close()

    @staticmethod
    def execute(sql_stmt: str, all: bool = True, *args) -> tuple:
        """
        数据库内部执行语句
        :param sql_stmt: 待执行SQL语句
        :param all: 是否以fetchall形式获取所有结果
        :param args: 所有可接受参数
        :return: 获取到的结果元组
        """
        try:
            DBOperator.__cur.execute(sql_stmt, args)
            DBOperator.__db.commit()
            if all:
                return DBOperator.__cur.fetchall()
            else:
                res = DBOperator.__cur.fetchone()
                if res is None:
                    return (None,)
                return res
        except sql.err.InterfaceError as e:
            logger.error(f"Error while executing SQL\n{sql_stmt}, {args}\n{e}", exc_info=True)
            logger.info("尝试尝试连接...")
            DBOperator.__cur.close()
            DBOperator.__db.close()
            t.sleep(2)
            DBOperator.connect()

    @staticmethod
    def login(user_id: int, user_name: str, last_login: str | datetime.datetime) -> str:
        """
        用户登录
        :param user_id: 用户id
        :param user_name: 用户昵称
        :param last_login: 上次与服务器有连接的时间
        :return: 返回发生错误的错误信息，如果成功则返回空字符串
        """
        # TODO: 增加密码后要增加判断密码错误的逻辑
        if user_id < 1000:
            return 'user_id不得小于1000'
        stmt = 'CALL login(%s,%s,%s);'
        err = ''
        DBOperator.execute(stmt, True, user_id, user_name, last_login)
        return err

    @staticmethod
    def queryUser(user_id: int) -> str:
        """
        通过user_id查询user信息
        :return: 用户昵称，如果用户不存在则返回空字符串
        """
        stmt = 'CALL query_user(%s);'
        user_name = DBOperator.execute(stmt, False, user_id)[0]
        return '' if user_name is None else user_name

    @staticmethod
    def insertContact(user_id1: int, user_id2: int):
        """
        增加联系人
        """
        stmt = 'CALL insert_contact(%s, %s);'
        DBOperator.execute(stmt, False, user_id1, user_id2)

    @staticmethod
    def queryGroup(group_id: int) -> str:
        """
        通过group_id请求group信息
        :return: 群组名称，如果群组不存在则返回空字符串
        """
        stmt = 'CALL query_group(%s);'
        group_name = DBOperator.execute(stmt, False, group_id)[0]
        return '' if group_name is None else group_name

    @staticmethod
    def insertGroup(group_id: int, group_name: str):
        """插入一个新group"""
        stmt = 'CALL insert_group(%s, %s);'
        DBOperator.execute(stmt, False, group_id, group_name)

    @staticmethod
    def insertGroupUser(group_id: int, user_id: int):
        """向group里添加user"""
        stmt = 'CALL insert_group_user(%s, %s);'
        DBOperator.execute(stmt, False, group_id, user_id)

    @staticmethod
    def insertMessage(from_user_id: int, to_id: int, timestamp: datetime.datetime, text: str, type: str, is_group: bool):
        """保存消息到服务器数据库"""
        stmt = 'CALL insert_message(%s, %s, %s, %s, %s, %s);'
        DBOperator.execute(stmt, False, from_user_id, to_id, timestamp, text, type, is_group)

    @staticmethod
    def queryFile(file_hash: str, file_suffix: str):
        """查询文件是否存在"""
        stmt = 'CALL query_file(%s, %s);'
        f_hash = DBOperator.execute(stmt, False, file_hash, file_suffix)
        return False if f_hash[0] is None else True

    @staticmethod
    def insertFile(file_hash: str, file_suffix: str):
        """向数据库中插入文件信息"""
        stmt = 'CALL insert_file(%s, %s);'
        DBOperator.execute(stmt, False, file_hash, file_suffix)

    @staticmethod
    def querySyncMessage(user_id: int, last_login: datetime.datetime | str):
        """查询未登录期间收到的消息"""
        stmt = 'CALL query_sync_message(%s, %s);'
        msg_list = DBOperator.execute(stmt, True, user_id, last_login)
        return msg_list

    @staticmethod
    def queryGroupUser(group_id: int):
        """查询一个群聊的所有成员id"""
        stmt = 'CALL query_group_user(%s);'
        user_ids = DBOperator.execute(stmt, True, group_id)
        return user_ids

db_operator = DBOperator()
