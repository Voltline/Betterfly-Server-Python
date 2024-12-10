import datetime
import os

import pymysql as sql
from dbutils.pooled_db import PooledDB

from Database.db_setting import DBSetting
from Utils.color_logger import get_logger

logger = get_logger(__name__)

root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config_dir = os.path.join(root_dir, "Config")
config_fp = os.path.join(config_dir, 'database_config.json')


class DBOperator:
    """数据库操作类，基于连接池实现"""

    __setting = DBSetting(config_fp)
    __pool = PooledDB(
        creator=sql,
        maxconnections=16,  # 最大连接数
        mincached=4,       # 初始化时创建的连接数
        maxcached=16,       # 连接池中最多可用连接数
        blocking=True,     # 无可用连接时是否阻塞等待
        ping=1,            # 检查连接可用性
        host=__setting.ip,
        port=__setting.port,
        user=__setting.user,
        password=__setting.password,
        database=__setting.database,
        charset=__setting.charset,
    )

    def __init__(self):
        # 从连接池中获取连接
        self.__db = self.__pool.connection()
        self.__cur = self.__db.cursor()

    def __del__(self):
        self.close()

    def close(self):
        """关闭当前连接（将其归还到连接池）"""
        if self.__cur:
            self.__cur.close()
        if self.__db:
            self.__db.close()

    def execute(self, sql_stmt: str, all: bool = True, *args) -> tuple:
        """
        执行SQL语句
        :param sql_stmt: 待执行SQL语句
        :param all: 是否获取所有结果
        :param args: 参数
        :return: 查询结果元组
        """
        try:
            self.__cur.execute(sql_stmt, args)
            self.__db.commit()
            if all:
                return self.__cur.fetchall()
            else:
                res = self.__cur.fetchone()
                return (None,) if res is None else res
        except sql.err.InterfaceError as e:
            logger.error(f"SQL执行错误: {sql_stmt}, 参数: {args}\n{e}", exc_info=True)
            self.__db.rollback()
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}", exc_info=True)
            self.__db.rollback()
            raise

    # 以下为原有方法，使用实例化的execute
    def login(self, user_id: int, user_name: str, last_login: str | datetime.datetime) -> str:
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
        self.execute(stmt, True, user_id, user_name, last_login)
        return ''

    def queryUser(self, user_id: int) -> str:
        """
        通过user_id查询user信息
        :return: 用户昵称.用户头像
        """
        stmt = 'CALL query_user(%s);'
        user = self.execute(stmt, False, user_id)
        if user[0] is None:
            return '.'
        user_name = '' if user[0] is None else user[0]
        user_avatar = '' if user[1] is None else user[1]
        return user_name + '.' + user_avatar

    def queryUserName(self, user_id: int) -> str:
        """
        通过user_id查询user昵称
        :return: 用户昵称
        """
        stmt = 'CALL query_user_name(%s);'
        user_name = self.execute(stmt, False, user_id)[0]
        return '' if user_name is None else user_name

    def insertContact(self, user_id1: int, user_id2: int):
        """
        增加联系人
        """
        stmt = 'CALL insert_contact(%s, %s);'
        self.execute(stmt, False, user_id1, user_id2)

    def queryGroup(self, group_id: int) -> str:
        """
        通过group_id请求group信息
        :return: 群组名称.群头像
        """
        stmt = 'CALL query_group(%s);'
        group = self.execute(stmt, False, group_id)
        if group[0] is None:
            return '.'
        group_name = '' if group[0] is None else group[0]
        group_avatar = '' if group[1] is None else group[1]
        return group_name + '.' + group_avatar

    def insertGroup(self, group_id: int, group_name: str):
        """插入一个新group"""
        stmt = 'CALL insert_group(%s, %s);'
        self.execute(stmt, False, group_id, group_name)

    def insertGroupUser(self, group_id: int, user_id: int):
        """向group里添加user"""
        stmt = 'CALL insert_group_user(%s, %s);'
        self.execute(stmt, False, group_id, user_id)

    def insertMessage(self, from_user_id: int, to_id: int, timestamp: datetime.datetime | str, text: str, type: str, is_group: bool):
        """保存消息到服务器数据库"""
        stmt = 'CALL insert_message(%s, %s, %s, %s, %s, %s);'
        self.execute(stmt, False, from_user_id, to_id, timestamp, text, type, is_group)

    def queryFile(self, file_hash: str, file_suffix: str):
        """查询文件是否存在"""
        stmt = 'CALL query_file(%s, %s);'
        f_hash = self.execute(stmt, False, file_hash, file_suffix)
        return False if f_hash[0] is None else True

    def insertFile(self, file_hash: str, file_suffix: str):
        """向数据库中插入文件信息"""
        stmt = 'CALL insert_file(%s, %s);'
        self.execute(stmt, False, file_hash, file_suffix)

    def querySyncMessage(self, user_id: int, last_login: datetime.datetime | str):
        """查询未登录期间收到的消息"""
        stmt = 'CALL query_sync_message(%s, %s);'
        return self.execute(stmt, True, user_id, last_login)

    def queryGroupUser(self, group_id: int):
        """查询一个群聊的所有成员id"""
        stmt = 'CALL query_group_user(%s);'
        user_ids = self.execute(stmt, True, group_id)
        return (user_id for user_id_tuple in user_ids for user_id in user_id_tuple)

    def insertUserAPNsToken(self, from_user_id: int, user_apns_token: str):
        """保存用户的APNs Token"""
        stmt = 'CALL insert_user_apns_token(%s, %s);'
        self.execute(stmt, False, from_user_id, user_apns_token)

    def queryUserAPNsTokens(self, from_user_id: int):
        """查询用户的所有APNs Token"""
        stmt = 'CALL query_user_apns_tokens(%s);'
        return self.execute(stmt, True, from_user_id)

    def deleteUserAPNsToken(self, from_user_id: int, user_apns_token: str):
        """删除用户无效的APNs Token"""
        stmt = 'CALL delete_user_apns_token(%s, %s);'
        self.execute(stmt, False, from_user_id, user_apns_token)

    def updateUserAvatar(self, id: int, avatar: str):
        stmt = 'CALL update_user_avatar(%s, %s);'
        self.execute(stmt, False, id, avatar)

    def updateGroupAvatar(self, id: int, avatar: str):
        stmt = 'CALL update_group_avatar(%s, %s);'
        self.execute(stmt, False, id, avatar)
