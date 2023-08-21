import os

import redis

from config import config


class RedisConnection:
    def __init__(self, host=None, port=None, db=None, password=None,
                 max_connections=None, socket_timeout=None, socket_connect_timeout=None):
        self.host = host or config['redis']['host']
        self.port = port or config['redis']['port']
        self.db = db or config['redis']['db']
        self.password = password or os.environ.get('REDIS_DB_PASS')
        self.max_connections = max_connections or config['redis']['max_connections']
        self.socket_timeout = socket_timeout or config['redis']['socket_timeout']
        self.socket_connect_timeout = socket_connect_timeout or config['redis']['socket_connect_timeout']

        self.pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
        )

    def get_connection(self):
        return redis.Redis(connection_pool=self.pool)
