import json

from botpy import get_logger

from config import config
from utils.mysql_utils import get_mysql_conn
from utils.redis_utils import RedisConnection

_log = get_logger()


async def get_guild_name_from_redis(client, guild_id):
    guild_detail = await get_guild_detail_from_redis(client, guild_id)
    return guild_detail['name'] if guild_detail else None


async def save_guild_detail_to_redis(client, guild_id):
    guild_detail = await client.api.get_guild(guild_id=guild_id)
    redis_conn = RedisConnection().get_connection()
    redis_conn.set(f"guild_detail:{guild_id}", json.dumps(guild_detail), ex=config['guild_detail_expiry_time'])


async def get_guild_detail_from_redis(client, guild_id):
    redis_conn = RedisConnection().get_connection()
    guild_detail_json = redis_conn.get(f"guild_detail:{guild_id}")
    if guild_detail_json is not None:
        return json.loads(guild_detail_json.decode('utf-8'))
    else:
        await save_guild_detail_to_redis(client, guild_id)
        guild_detail_json = redis_conn.get(f"guild_detail:{guild_id}")
        return json.loads(guild_detail_json.decode('utf-8')) if guild_detail_json else None


def check_guild_authenticity(guild_id: str) -> bool:
    # 建立数据库连接
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 查询数据的SQL语句
            query = "SELECT `guild_id` FROM `authenticated_guilds` WHERE `guild_id` = %s"
            cursor.execute(query, (guild_id,))
            result = cursor.fetchone()
            if result is not None:
                return True
            else:
                return False
    except Exception as e:
        _log.error(f"尝试检查频道ID {guild_id} 是否已认证时发生错误：{e}")
    finally:
        conn.close()
