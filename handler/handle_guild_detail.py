from botpy.message import Message

from utils.guild_utils import get_guild_detail_from_redis
from utils.roles import is_bot_admin_from_message
from utils.send_message_with_log import reply_with_log


async def handle_guild_detail(client, message: Message):
    if not is_bot_admin_from_message(message):
        await reply_with_log(message, "只有机器人管理才能使用该指令。")
        return

    guild_id = message.guild_id
    guild_detail = await get_guild_detail_from_redis(client, guild_id)
    if guild_detail:
        message_content = f"频道详细信息:\n" \
                          f"ID: {guild_detail['id']}\n" \
                          f"名称: {guild_detail['name']}\n" \
                          f"成员数: {guild_detail['member_count']}\n" \
                          f"最大成员数: {guild_detail['max_members']}\n" \
                          f"描述: {guild_detail['description']}"
    else:
        message_content = "频道详情失败。"
    await reply_with_log(message, content=message_content)
