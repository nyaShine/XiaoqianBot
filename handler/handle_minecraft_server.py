import ipaddress
import json
import re

from botpy import get_logger
from mcstatus import JavaServer

from config import config
from utils.get_help import get_help
from utils.mysql_utils import get_mysql_conn
from utils.redis_utils import RedisConnection
from utils.roles import is_minecraft_server_admin_from_message
from utils.send_message_with_log import reply_with_log


# 初始化一个Redis连接
redis_conn = RedisConnection()

# 创建一个日志记录器
_log = get_logger()


async def query_mc_server(server):
    # 获取一个Redis连接
    r = redis_conn.get_connection()

    # 尝试从Redis中获取服务器状态
    try:
        server_status = r.get(server["server_address"])
    except Exception as e:
        _log.error(f"从Redis中获取服务器状态失败，服务器地址：{server['server_address']}，错误信息：{str(e)}")
        return None

    if server_status is not None:
        # 如果在Redis中找到了服务器状态，就直接返回
        return json.loads(server_status)

    # 如果在Redis中没有找到服务器状态，就查询服务器，并将结果存入Redis
    mc_server = JavaServer.lookup(server["server_address"])
    try:
        status = await mc_server.async_status()
        latency = round(status.latency, 2)
        server_status = f"在线，玩家数：{status.players.online}/{status.players.max}，延迟：{latency} ms"
        status_query_timeout = config['minecraft_servers']['redis']['status_query_timeout']
        r.set(server["server_address"], json.dumps(server_status), ex=status_query_timeout)
    except Exception as e:
        server_status = f"离线，错误信息：{str(e)}"
        status_query_failed_ttl = config['minecraft_servers']['redis']['status_query_failed_ttl']
        r.set(server["server_address"], json.dumps(server_status), ex=status_query_failed_ttl)  # 设置失败状态的过期时间为1分钟
        _log.error(f"查询服务器状态失败，服务器地址：{server['server_address']}，错误信息：{str(e)}")

    return server_status


def is_valid_ip_address(address):
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False


def is_valid_domain_name(address):
    pattern = r"^((([0-9a-z.]+\.[a-z]+)|(([0-9]{1,3}\.){3}[0-9]{1,3})))$"
    return re.match(pattern, address, re.IGNORECASE) is not None


def is_valid_port(port):
    return 0 <= port <= 65535


def is_valid_server_address(server_address):
    # 移除"http://"或"https://"
    if server_address.startswith("http://"):
        server_address = server_address[7:]
    elif server_address.startswith("https://"):
        server_address = server_address[8:]

    # 移除末尾的斜线
    if server_address.endswith("/"):
        server_address = server_address[:-1]

    # 分离主机和端口
    if ':' in server_address:
        host, port_str = server_address.rsplit(':', 1)
        if not port_str.isdigit() or not is_valid_port(int(port_str)):
            return False
    else:
        host = server_address

    # 检查主机
    return is_valid_ip_address(host) or is_valid_domain_name(host)


async def show_servers(client, message):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT `server_address`, `server_name`, `server_description` FROM `minecraft_servers` WHERE `guild_id` = %s"
            cursor.execute(sql, (message.guild_id,))
            servers = cursor.fetchall()
    finally:
        conn.close()

    if not servers:
        help_msg = get_help('mc')  # 假设 'mc' 是你的 feature_name
        await reply_with_log(message, f"没有设置服务器。\n\n{help_msg}")
    else:
        server_info = "\n".join(
            [
                f"名称: {server['server_name']}\n"
                f"地址: {server['server_address']}\n"
                f"描述: {server['server_description']}\n"
                f"状态: {await query_mc_server(server)}\n"
                f"-----------------------------------"
                for server in servers
            ]
        )
        await reply_with_log(message, server_info)


async def add_server(client, message, server_address, server_name, server_description):
    if not is_valid_server_address(server_address):
        await reply_with_log(message, "服务器地址格式错误。")
        return

    # 限制服务器地址的长度
    max_server_address_length = config['minecraft_servers']['max_server_address_length']
    if len(server_address) > max_server_address_length:
        await reply_with_log(message, f"服务器地址过长。最大长度为{max_server_address_length}个字符。")
        return

    # 限制服务器名称的长度
    max_server_name_length = config['minecraft_servers']['max_server_name_length']
    if len(server_name) > max_server_name_length:
        await reply_with_log(message, f"服务器名称过长。最大长度为{max_server_name_length}个字符。")
        return

    max_server_description_length = config['minecraft_servers']['max_server_description_length']
    # 限制服务器描述的长度
    if len(server_description) > max_server_description_length:
        await reply_with_log(message, f"服务器描述过长。最大长度为{max_server_description_length}个字符。")
        return

    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 检查服务器是否已经存在
            sql = "SELECT COUNT(*) as count FROM `minecraft_servers` WHERE `server_address` = %s AND `guild_id` = %s"
            cursor.execute(sql, (server_address, message.guild_id))
            result = cursor.fetchone()
            if result['count'] > 0:
                await reply_with_log(message, "服务器已经存在。")
            else:
                sql = "INSERT INTO `minecraft_servers` (`server_address`, `server_name`, `server_description`, `guild_id`) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (server_address, server_name, server_description, message.guild_id))
                conn.commit()
                await reply_with_log(message, "服务器添加成功。")
    finally:
        conn.close()


async def delete_server(client, message, server_address):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 检查服务器是否存在
            sql = "SELECT COUNT(*) as count FROM `minecraft_servers` WHERE `server_address` = %s AND `guild_id` = %s"
            cursor.execute(sql, (server_address, message.guild_id))
            result = cursor.fetchone()
            if result['count'] > 0:
                sql = "DELETE FROM `minecraft_servers` WHERE `server_address` = %s AND `guild_id` = %s"
                cursor.execute(sql, (server_address, message.guild_id))
                conn.commit()
                await reply_with_log(message, "服务器删除成功。")
            else:
                await reply_with_log(message, "服务器不存在。")
    finally:
        conn.close()


async def handle_minecraft_server(client, message):
    content = message.content.strip()
    args = content.split(" ")

    if len(args) < 3:
        # 如果没有指定子命令，就显示所有服务器的信息
        await show_servers(client, message)
    else:
        subcommand = args[2]
        if subcommand == "添加":
            if not is_minecraft_server_admin_from_message(message):
                await reply_with_log(message, "对不起，你没有权限执行此操作。")
                return
            if len(args) < 6:
                await reply_with_log(message, "参数不足，正确的格式是：/mc 添加 服务器地址 服务器名称 服务器简介")
            else:
                await add_server(client, message, args[3], args[4], " ".join(args[5:]))
        elif subcommand == "删除":
            if not is_minecraft_server_admin_from_message(message):
                await reply_with_log(message, "对不起，你没有权限执行此操作。")
                return
            if len(args) < 4:
                await reply_with_log(message, "参数不足，正确的格式是：/mc 删除 服务器地址")
            else:
                await delete_server(client, message, args[3])
        else:
            await reply_with_log(message, "无法识别的命令，请检查您的输入。")
