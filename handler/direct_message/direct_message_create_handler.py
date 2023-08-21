from botpy import logging
from botpy.message import DirectMessage

from handler.handle_email_verification import handle_email_verification_direct_message
from utils.send_message_with_log import post_dms_with_log

_log = logging.get_logger()


async def direct_message_create_handler(client, message: DirectMessage):
    _log.info(
        f"收到私信消。Author ID: {message.author.id}, Author Username: {message.author.username}, Content: {message.content}, Timestamp: {message.timestamp}")
    content = message.content
    COMMANDS = {
        "/邮箱认证": handle_email_verification_direct_message
    }

    if content.startswith("/"):
        command = content.split()[0]  # 假设命令是消息中的第一个词
        handler = COMMANDS.get(command)

        if handler:
            await handler(client, message)
        else:
            await post_dms_with_log(client, message, content="无法识别的命令，请检查您的输入。")
    else:
        await post_dms_with_log(client, message, content="消息格式错误，请使用正确的命令格式。")
