from botpy.message import Message

from utils.send_message_with_log import reply_with_log


async def handle_ping(client, message: Message):
    await reply_with_log(message, content="pong")
