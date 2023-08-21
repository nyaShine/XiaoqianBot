from utils.redis_utils import RedisConnection


async def save_channel_name_to_redis(client, guild_id, channel_id):
    channel = await client.api.get_channel(channel_id=channel_id)
    channel_name = channel["name"]
    redis_conn = RedisConnection().get_connection()
    redis_conn.set(f"channel_name:{guild_id}:{channel_id}", channel_name, ex=86400)  # 存储1天


async def get_channel_name_from_redis(client, guild_id, channel_id):
    redis_conn = RedisConnection().get_connection()
    channel_name_bytes = redis_conn.get(f"channel_name:{guild_id}:{channel_id}")
    if channel_name_bytes is not None:
        return channel_name_bytes.decode('utf-8')
    else:
        await save_channel_name_to_redis(client, guild_id, channel_id)
        channel_name_bytes = redis_conn.get(f"channel_name:{guild_id}:{channel_id}")
        return channel_name_bytes.decode('utf-8') if channel_name_bytes else None
