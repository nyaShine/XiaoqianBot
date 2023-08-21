from botpy.message import Message

from utils.send_message_with_log import reply_with_log


async def handle_subscription(client, message: Message):
    await reply_with_log(message, content="这是一个饼，还没做")
