import asyncio
import re
from botpy import logging
from botpy.message import Message

from handler.handle_authenticate_guild import handle_authenticate_guild
from handler.handle_channel_list import handle_channel_list
from handler.handle_dice_random import dice_random
from handler.handle_guild_detail import handle_guild_detail
from handler.handle_role import handle_admin
from handler.handle_email_verification import handle_email_verification_at_message
from handler.handle_help import handle_help
from handler.handle_role import handle_query_identity_group
from handler.handle_minecraft_server import handle_minecraft_server
from handler.handle_ping import handle_ping
from handler.handle_question import qa
from handler.handle_rss_subscription import rss
from handler.handle_youth_study import handle_youth_study
from utils.send_message_with_log import reply_with_log

_log = logging.get_logger()


async def at_message_create_handler(client, message: Message):
    timestamp = message.timestamp
    channel_id = message.channel_id
    member = message.member
    nick = member.nick
    content = message.content

    message_info = f"{timestamp} {channel_id} {nick}: {content}"
    _log.info(message_info)

    # Match any command starting with /
    match = re.search(r"(/\w+)", content)

    COMMANDS = {
        "/帮助": handle_help,
        "/菜单": handle_help,
        "/问": qa.on_command,
        "/rss订阅": rss.on_command,
        "/邮箱认证": handle_email_verification_at_message,
        "/mc": handle_minecraft_server,
        "/随机": dice_random.on_command,
        "/设置管理": handle_admin,
        "/查询身份组": handle_query_identity_group,
        "/查询子频道": handle_channel_list,
        "/查询频道详情": handle_guild_detail,
        "/ping": handle_ping,
        "/频道认证": handle_authenticate_guild,
        "/青年大学习": handle_youth_study
    }

    if match:
        command = match.group(1)
        handler = COMMANDS.get(command)

        if handler:
            asyncio.create_task(handler(client, message))
        else:
            await reply_with_log(message, "无法识别的命令，请检查您的输入。")
    else:
        await reply_with_log(message, "消息格式错误，请使用正确的命令格式。")
