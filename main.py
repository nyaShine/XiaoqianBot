import asyncio

from botpy.logging import get_logger
from botpy.message import Message, DirectMessage
from botpy.forum import OpenThread
import botpy

from config import config
from handler.direct_message.direct_message_create_handler import direct_message_create_handler
from handler.handle_rss_subscription import RSSCrawler
from handler.open_forum_event.open_forum_thread_create_handler import open_forum_thread_create_handler
from handler.public_guild_messages.at_message_create_handler import at_message_create_handler

_log = get_logger()


class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")

    # 当收到@机器人的消息时
    async def on_at_message_create(self, message: Message):
        await at_message_create_handler(self, message)

    # 当收到用户发给机器人的私信消息时
    async def on_direct_message_create(self, message: DirectMessage):
        await direct_message_create_handler(self, message)

    # 当收到用户创建主题时
    async def on_open_forum_thread_create(self, open_forum_thread: OpenThread):
        await open_forum_thread_create_handler(self, open_forum_thread)


async def main():
    # 订阅所有事件
    intents = botpy.Intents(public_guild_messages=True,
                            direct_message=True,
                            open_forum_event=True)
    client = MyClient(intents=intents)

    # 启动QQ机器人
    client_task = asyncio.create_task(client.start(config["appid"], config["token"]))

    # 启动RSSCrawler
    async with RSSCrawler(client) as crawler:
        await asyncio.gather(client_task, crawler.crawler())

if __name__ == "__main__":
    asyncio.run(main())
