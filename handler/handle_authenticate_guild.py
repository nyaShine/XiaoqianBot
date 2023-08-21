import pymysql
import re

from botpy import get_logger
from botpy.errors import ForbiddenError
from botpy.message import Message

from config import config
from utils.guild_utils import get_guild_name_from_redis, check_guild_authenticity
from utils.mysql_utils import get_mysql_conn
from utils.send_message_with_log import reply_with_log


_log = get_logger()


def extract_id(content: str):
    # 去除空格，并将小写i和d替换为大写，以便后续正则匹配
    content = re.sub(r"[^\S\n]+", "", content.replace('i', 'I').replace('d', 'D'))
    match = re.search(r"ID[:：]([0-9]+)", content, re.IGNORECASE)

    if match:
        # 返回匹配到的数字内容
        return match.group(1)
    else:
        return None


def insert_authenticated_guild(guild_id: str):
    # 建立数据库连接
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 插入数据的SQL语句
            query = "INSERT INTO `authenticated_guilds` (`guild_id`) VALUES (%s)"
            cursor.execute(query, (guild_id,))
        conn.commit()
    except pymysql.err.IntegrityError:
        _log.error(f"频道ID {guild_id} 已经被认证过了。")
    except Exception as e:
        _log.error(f"尝试认证频道ID {guild_id} 时发生错误：{e}")
    finally:
        conn.close()


async def handle_authenticate_guild(client, message: Message):
    # 检查发消息的人是否是机器人的所有者
    if message.author.id != str(config['bot_owner_id']):
        await reply_with_log(message, content="只有机器人拥有者可以使用该指令")
        return
    # 获取引用的消息ID
    referenced_message_id = message.message_reference.message_id

    if referenced_message_id is None:
        await reply_with_log(message, content="你没有引用任何消息。")
        return

    try:
        # 使用API获取引用的消息
        referenced_message = await client.api.get_message(channel_id=message.channel_id,
                                                          message_id=referenced_message_id)
    except Exception as e:
        await reply_with_log(message, content="获取引用消息时失败。")
        _log.error(f"获取引用消息时失败: {e}")
        return
    guild_id_from_reference = extract_id(referenced_message['message']['content'])
    if guild_id_from_reference is not None:
        # 检查频道是否已经被认证过
        if check_guild_authenticity(guild_id_from_reference):
            await reply_with_log(message, content=f"频道ID: {guild_id_from_reference} 已经被认证过了")
        else:
            try:
                # 检查机器人是否已经加入了频道
                try:
                    await client.api.get_guild(guild_id=guild_id_from_reference)
                except ForbiddenError:
                    await reply_with_log(message, content=f"机器人未加入频道ID: {guild_id_from_reference}")
                    return

                insert_authenticated_guild(guild_id_from_reference)
                guild_name = await get_guild_name_from_redis(client, guild_id_from_reference)
                await reply_with_log(message,
                                     content=f"频道{guild_name}（{guild_id_from_reference}）认证成功")
            except Exception as e:
                await reply_with_log(message, content=f"尝试认证频道时发生错误：{e}")
                _log.error(f"尝试认证频道时发生错误：{e}")
    else:
        await reply_with_log(message, content="无法从引用消息中找到ID")
