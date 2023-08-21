import os

import pymysql
from DBUtils.PooledDB import PooledDB

from config import config

# 创建连接池
pool = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    maxshared=3,
    blocking=True,
    setsession=[],
    ping=0,
    host=config['mysql']['host'],
    port=config['mysql']['port'],
    user=os.environ.get('DB_USER'),
    password=os.environ.get('SQL_DB_PASS'),
    database=config['mysql']['database'],
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)


def get_mysql_conn():
    conn = pool.connection()
    return conn
