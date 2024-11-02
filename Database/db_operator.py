import pymysql as sql
from pymysql.cursors import Cursor
from pymysql.connections import Connection
import os
import logging
import datetime
import time as t

from Database.db_setting import DBSetting

root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config_dir = os.path.join(root_dir, "Config")
config_fp = os.path.join(config_dir, 'database_config.json')
logger = logging.getLogger(__name__)


class DBOperator:
    """数据库操作相关方法"""

    __setting = DBSetting(config_fp)
    __db: Connection = None
    __cur: Cursor = None

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
            logger.error(e)
            logger.error("尝试尝试连接...")
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
        try:
            DBOperator.execute(stmt, True, user_id, user_name, last_login)
        except Exception as e:
            err = str(e)
            logger.error(e)
        return err


