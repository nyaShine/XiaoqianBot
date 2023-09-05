import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import html
import pymysql

import aiohttp
import feedparser
from botpy import get_logger
from botpy.message import Message
from bs4 import BeautifulSoup

from config import config
from utils.channel_utils import get_channel_name_from_redis
from utils.get_help import bot_features_dict
from utils.guild_utils import check_guild_authenticity
from utils.mysql_utils import get_mysql_conn
from utils.parse_date import parse_date
from utils.redis_utils import RedisConnection
from utils.roles import is_rss_subscription_admin_from_message
from utils.send_message_with_log import reply_with_log, post_with_log
from utils.time_utils import is_time_range_valid


_log = get_logger()


class RSSCrawler:
    def __init__(self, client):
        self.client = client
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession()

        # 从配置文件中获取rss_subscription部分的配置
        self.config = config['rss_subscription']

        # 应用配置项
        self.crawler_sleep_time = self.config['crawler_sleep_time']
        self.message_length_limit = self.config['message_length_limit']
        self.rss_fetch_timeout = self.config['rss_fetch_timeout']
        self.rss_parse_max_workers = self.config['rss_parse_max_workers']
        self.rss_truncate_length = self.config['rss_truncate_length']
        self.time_range_start, self.time_range_end = self.config['time_range'].split('-')
        self.message_limit_seconds = config['message_limit_seconds']

        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.rss_parse_max_workers)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        if self.session:
            await self.session.close()
            self.session = None

    async def close(self):
        await self.session.close()

    @staticmethod
    def truncate_string(s, length):
        return (s[:length] + '..') if len(s) > length else s

    @staticmethod
    def clean_html(raw_html):
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text()

    async def fetch_rss(self, session, url: str):
        _log.info(f"正在从{url}获取RSS...")
        try:
            async with session.get(url, timeout=self.rss_fetch_timeout) as response:  # 设置超时
                return await response.text()
        except (asyncio.TimeoutError, Exception) as e:
            _log.error(f"由于{str(e)}，从{url}获取RSS失败。")
            return None

    async def parse_rss(self, rss_text: str):
        return await self.loop.run_in_executor(self.executor, feedparser.parse, rss_text)

    async def send_rss_item(self, client, rss_item, subscriptions):
        if not is_time_range_valid(self.time_range_start, self.time_range_end):
            _log.info("由于时间限制，跳过发送rss项目。")
            return False
        title = html.unescape(rss_item['title'])
        link = rss_item['link']
        description = self.clean_html(html.unescape(rss_item['description']))

        # 如果description过长，只发送前半部分字符，并注明截断
        if len(description) > self.message_length_limit:
            description = description[:self.message_length_limit] + "... (内容过长，已截断，详情请点击链接查看)"

        for subscription in subscriptions:
            channel_id = subscription['channel_id']
            custom_name = subscription['custom_name']
            published_date = rss_item['published_date']
            if published_date:
                title = f"{title} ({published_date.strftime('%Y-%m-%d %H:%M:%S')})"
            message = f"{custom_name}：\n{title}：\n链接：{link}\n描述：{description}"

            # 创建Redis连接
            redis_conn = RedisConnection()
            conn = redis_conn.get_connection()

            # 检查频道是否已经达到消息发送上限
            key = f"msg_daily_limit:{channel_id}"
            if not conn.exists(key):
                try:
                    await post_with_log(client, channel_id, message, encode_urls=True)
                except Exception as e:
                    if 'push channel message reach limit' in str(e):
                        _log.error(f"消息发送达到上限：{e}")
                        # 设置过期时间为当日23:59
                        expire_seconds = (datetime.now().replace(hour=23, minute=59, second=59)
                                          - datetime.now()).seconds
                        # 如果过期时间超过config中预设的过期时间上限，则设为上限时间
                        if expire_seconds > self.message_limit_seconds:
                            expire_seconds = self.message_limit_seconds
                        conn.set(key, 1, ex=expire_seconds)
                        return False
                    return True
        return True

    async def crawler(self):
        await asyncio.sleep(10)  # 等待10秒以确保QQ机器人已启动
        while True:
            _log.info("爬虫正在运行...")
            if not is_time_range_valid(self.time_range_start, self.time_range_end):
                await asyncio.sleep(self.crawler_sleep_time)
                continue

            conn = None
            try:
                conn = get_mysql_conn()
                with conn.cursor() as cursor:
                    # 获取需要更新的RSS源
                    sql = "SELECT * FROM rss_feed WHERE ADDDATE(last_updated, INTERVAL current_interval MINUTE) <= NOW() AND (block_duration IS NULL OR last_blocked IS NULL OR ADDDATE(last_blocked, INTERVAL block_duration DAY) < NOW())"
                    cursor.execute(sql)
                    feeds = cursor.fetchall()

                    for feed in feeds:
                        rss_feed_id = feed['rss_feed_id']
                        url = feed['url']

                        # 更新last_updated字段
                        sql = "UPDATE rss_feed SET last_updated = NOW() WHERE rss_feed_id = %s"
                        cursor.execute(sql, (rss_feed_id,))
                        conn.commit()  # 提交事务

                        # 获取RSS源
                        try:
                            rss_text = await self.fetch_rss(self.session, url)
                            try:
                                rss_data = await self.loop.run_in_executor(self.executor, feedparser.parse, rss_text)
                            except Exception as e:
                                _log.error(f"解析RSS源时发生错误：{e}")
                                # 访问被屏蔽，更新block_count和last_blocked
                                sql = "UPDATE rss_feed SET block_count = block_count + 1, last_blocked = NOW() WHERE rss_feed_id = %s"
                                cursor.execute(sql, (rss_feed_id,))
                                conn.commit()  # 提交事务
                                continue

                            # 访问成功，重置block_count和last_blocked
                            sql = "UPDATE rss_feed SET block_count = 0, last_blocked = NULL WHERE rss_feed_id = %s"
                            cursor.execute(sql, (rss_feed_id,))
                            conn.commit()  # 提交事务

                            # 保存新的RSS项
                            for rss_item in rss_data.entries:
                                link = rss_item['link']
                                sql = "SELECT * FROM rss_item WHERE link = %s"
                                cursor.execute(sql, (link,))
                                result = cursor.fetchone()
                                if not result:
                                    published_date_str = rss_item.get('published', None)
                                    published_date = None  # 默认为None
                                    if published_date_str:
                                        try:
                                            published_date = parse_date(published_date_str)
                                        except ValueError as e:
                                            _log.error(f"解析日期时间时发生错误：{e}")
                                    title = self.truncate_string(rss_item['title'], self.rss_truncate_length)
                                    link = self.truncate_string(rss_item['link'], self.rss_truncate_length)

                                    sql = "INSERT INTO rss_item (rss_feed_id, title, link, description, published_date) VALUES (%s, %s, %s, %s, %s)"
                                    cursor.execute(sql, (
                                        rss_feed_id, title, link, rss_item.get('description', ''), published_date))
                                    conn.commit()  # 提交事务

                        except Exception as e:
                            _log.error(f"获取RSS源时发生错误：{e}")
                            # 访问被屏蔽，更新block_count和last_blocked
                            sql = "UPDATE rss_feed SET block_count = block_count + 1, last_blocked = NOW() WHERE rss_feed_id = %s"
                            cursor.execute(sql, (rss_feed_id,))
                            conn.commit()  # 提交事务
                            continue

                        # 获取RSS源的订阅
                        sql = "SELECT * FROM rss_subscription WHERE rss_feed_id = %s"
                        cursor.execute(sql, (rss_feed_id,))
                        subscriptions = cursor.fetchall()

                        # 发送新的RSS项
                        sql = "SELECT * FROM rss_item WHERE rss_feed_id = %s AND rss_item_id NOT IN (SELECT rss_item_id FROM rss_item_delivery WHERE channel_id = %s) AND DATE_ADD(published_date, INTERVAL %s DAY) >= NOW()"
                        for subscription in subscriptions:
                            cursor.execute(sql, (rss_feed_id, subscription['channel_id'], subscription['max_age']))
                            rss_items = cursor.fetchall()
                            for rss_item in rss_items:
                                sql = "SELECT rss_item_id FROM rss_item WHERE rss_item_id = %s"
                                cursor.execute(sql, (rss_item['rss_item_id'],))
                                if cursor.fetchone() is None:
                                    _log.error("rss_item_id does not exist in rss_item table.")
                                    continue
                                if await self.send_rss_item(self.client, rss_item, subscriptions):
                                    sql = "INSERT INTO rss_item_delivery (rss_item_id, guild_id, channel_id) VALUES (%s, %s, %s)"
                                    cursor.execute(sql, (
                                        rss_item['rss_item_id'], subscription['guild_id'], subscription['channel_id']))
                                    conn.commit()  # 提交事务

            finally:
                if conn:
                    conn.close()
                _log.info("爬虫运行结束")
                await asyncio.sleep(self.crawler_sleep_time)


class RSSSystem:
    def __init__(self):
        self.conn = get_mysql_conn()
        # 从配置文件中获取rss_subscription部分的配置
        self.config = config['rss_subscription']
        self.rss_item_max_age = self.config['rss_item_max_age']
        self.max_feeds_per_channel = self.config['max_feeds_per_channel']
        self.max_channels_per_guild = self.config['max_channels_per_guild']
        self.min_feed_interval = self.config['min_feed_interval']

    async def add_feed(self, client, message: Message, url: str, name: str, interval: str):
        # 检查 interval 是否为数字
        if not interval.isdigit():
            await reply_with_log(message, "更新间隔必须为数字。")
            return

        interval = int(interval)

        # 检查当前频道的 RSS 源数量是否已达到上限
        try:
            with self.conn.cursor() as cursor:
                sql = "SELECT COUNT(*) AS count FROM rss_subscription WHERE guild_id = %s"
                cursor.execute(sql, (message.guild_id,))
                result = cursor.fetchone()
                if result['count'] >= self.max_feeds_per_channel:
                    await reply_with_log(message, f"当前频道的 RSS 源数量已达到上限（{self.max_feeds_per_channel}个）。")
                    return
        except Exception as e:
            _log.error(f"检查 RSS 源数量时发生错误：{e}")
            await reply_with_log(message, "检查 RSS 源数量时发生错误。")
            return

        # 检查当前频道的子频道数量是否已达到上限
        try:
            with self.conn.cursor() as cursor:
                sql = "SELECT channel_id FROM rss_subscription WHERE guild_id = %s GROUP BY channel_id"
                cursor.execute(sql, (message.guild_id,))
                channels = cursor.fetchall()
                channel_ids = [channel['channel_id'] for channel in channels]
                if len(channel_ids) >= self.max_channels_per_guild and message.channel_id not in channel_ids:
                    channel_names = ", ".join(
                        [await get_channel_name_from_redis(client, message.guild_id, channel_id) for channel_id in
                         channel_ids])
                    await reply_with_log(message,
                                         f"当前频道的子频道数量已达到上限（{self.max_channels_per_guild}个）。请在机器人-管理-机器人推送设置中添加{channel_names}三个子频道，否则推送将无法正常发送。")
                    return
        except Exception as e:
            _log.error(f"检查子频道数量时发生错误：{e}")
            await reply_with_log(message, "检查子频道数量时发生错误。")
            return

        # 解码HTML实体
        url = html.unescape(url)
        # 检查URL是否有效
        try:
            timeout = aiohttp.ClientTimeout(total=config["rss_subscription"]["rss_fetch_timeout"])  # 设置超时时间
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        await reply_with_log(message, "无法访问RSS源，请检查URL是否正确。")
                        return
        except Exception as e:
            _log.error(f"无法访问RSS源，错误信息：{e}")
            await reply_with_log(message, "无法访问RSS源。")
            return

        # 将RSS源添加到数据库
        try:
            # 开始事务
            with self.conn.cursor() as cursor:
                self.conn.begin()
                sql = "SELECT rss_feed_id, system_min_interval FROM rss_feed WHERE url = %s"
                cursor.execute(sql, (url,))
                result = cursor.fetchone()
                if result:
                    rss_feed_id = result['rss_feed_id']
                    system_min_interval = result['system_min_interval']
                else:
                    sql = "INSERT INTO rss_feed (url, system_min_interval, current_interval) VALUES (%s, %s, %s)"
                    system_min_interval = self.min_feed_interval
                    cursor.execute(sql, (url, system_min_interval, interval))
                    rss_feed_id = cursor.lastrowid

                if interval < system_min_interval:
                    interval = system_min_interval
                    interval_message = f"，但该RSS源的最低更新间隔为{system_min_interval}分钟，已将你的RSS源更新间隔设置为{interval}分钟"
                else:
                    interval_message = ""

                # 获取当前guild_id下最大的guild_rss_subscription_id
                sql = "SELECT MAX(guild_rss_subscription_id) AS max_id FROM rss_subscription WHERE guild_id = %s"
                cursor.execute(sql, (message.guild_id,))
                result = cursor.fetchone()
                if result['max_id']:
                    guild_rss_subscription_id = result['max_id'] + 1
                else:
                    guild_rss_subscription_id = 1

                sql = "INSERT INTO rss_subscription (guild_id, channel_id, rss_feed_id, custom_name, user_min_interval, guild_rss_subscription_id) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (
                    message.guild_id, message.channel_id, rss_feed_id, name, interval, guild_rss_subscription_id))

                # 更新rss_feed的current_interval为当前rss_feed的user_min_interval的最小值
                sql = "UPDATE rss_feed SET current_interval = (SELECT MIN(user_min_interval) FROM rss_subscription WHERE rss_feed_id = %s) WHERE rss_feed_id = %s"
                cursor.execute(sql, (rss_feed_id, rss_feed_id))

                self.conn.commit()
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:  # 重复的RSS源
                await reply_with_log(message, f"RSS源：{name} 已经在当前频道订阅过了。")
                return
            else:
                raise
        except Exception as e:
            self.conn.rollback()
            _log.error(f"添加RSS源时发生错误：{e}")
            await reply_with_log(message, "添加RSS源时发生错误。")
            return

        await reply_with_log(message, f"成功添加RSS源：{name}{interval_message}。建议在机器人-管理-机器人推送设置中设置单个子频道推送上限为99条每天")

    async def remove_feed(self, client, message: Message, guild_rss_subscription_id: str):
        # 检查输入是否为正整数
        if not guild_rss_subscription_id.isdigit() or int(guild_rss_subscription_id) <= 0:
            await reply_with_log(message, "输入错误，RSS源编号应为正整数。")
            return

        guild_rss_subscription_id = int(guild_rss_subscription_id)

        # 从数据库中删除RSS源
        try:
            with self.conn.cursor() as cursor:
                # 先判断是否存在该guild_rss_subscription_id
                sql = "SELECT custom_name FROM rss_subscription WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (guild_rss_subscription_id, message.guild_id))
                result = cursor.fetchone()
                if not result:
                    await reply_with_log(message, f"RSS源编号：{guild_rss_subscription_id} 在当前频道未找到。")
                    return
                custom_name = result['custom_name']

                # 删除rss_subscription
                sql = "DELETE FROM rss_subscription WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (guild_rss_subscription_id, message.guild_id))

                # 更新所有guild_rss_subscription_id大于被删除项的rss_subscription的guild_rss_subscription_id，将其减1
                sql = "UPDATE rss_subscription SET guild_rss_subscription_id = guild_rss_subscription_id - 1 WHERE guild_id = %s AND guild_rss_subscription_id > %s"
                cursor.execute(sql, (message.guild_id, guild_rss_subscription_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            _log.error(f"删除RSS源时发生错误：{e}")
            await reply_with_log(message, "删除RSS源时发生错误。")
            return

        await reply_with_log(message, f"成功删除RSS源：{custom_name}")

    async def list_feeds(self, client, message: Message):
        # 从数据库中获取当前频道订阅的所有RSS源并发送给用户
        try:
            with self.conn.cursor() as cursor:
                sql = """SELECT rss_subscription.guild_rss_subscription_id, rss_subscription.custom_name, rss_feed.url, rss_subscription.user_min_interval, rss_subscription.max_age, rss_subscription.channel_id 
                         FROM rss_subscription 
                         LEFT JOIN rss_feed ON rss_subscription.rss_feed_id = rss_feed.rss_feed_id 
                         WHERE rss_subscription.guild_id = %s"""
                cursor.execute(sql, (message.guild_id,))
                feeds = cursor.fetchall()
        except Exception as e:
            _log.error(f"获取RSS源列表时发生错误：{e}")
            await reply_with_log(message, "获取RSS源列表时发生错误。")
            return

        if feeds:
            reply = "当前订阅的RSS源：\n"
            for feed in feeds:
                channel_name = await get_channel_name_from_redis(client, message.guild_id, feed['channel_id'])
                reply += f"- 序号：{feed['guild_rss_subscription_id']}, 名称：{feed['custom_name']}, URL：{feed['url']}。更新间隔：{feed['user_min_interval']}分钟, 过期时间：{feed['max_age']}天, 子频道：{channel_name}\n"
        else:
            reply = "当前没有订阅任何RSS源。"

        await reply_with_log(message, reply, encode_urls=True)

    async def update_feed_interval(self, client, message: Message, guild_rss_subscription_id: str, new_interval: str):
        # 检查输入是否为正整数
        if not guild_rss_subscription_id.isdigit() or int(
                guild_rss_subscription_id) <= 0 or not new_interval.isdigit() or int(new_interval) < 0:
            await reply_with_log(message, "输入错误，RSS源编号和新的更新间隔应为正整数。")
            return

        guild_rss_subscription_id = int(guild_rss_subscription_id)
        new_interval = int(new_interval)

        # 更新数据库中的user_min_interval
        try:
            with self.conn.cursor() as cursor:
                # 先判断是否存在该guild_rss_subscription_id
                sql = "SELECT rss_feed_id, custom_name FROM rss_subscription WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (guild_rss_subscription_id, message.guild_id))
                result = cursor.fetchone()
                if not result:
                    await reply_with_log(message, f"RSS源编号：{guild_rss_subscription_id} 在当前频道未找到。")
                    return
                custom_name = result['custom_name']
                rss_feed_id = result['rss_feed_id']

                sql = "SELECT system_min_interval FROM rss_feed WHERE rss_feed_id = %s"
                cursor.execute(sql, (rss_feed_id,))
                result = cursor.fetchone()
                system_min_interval = result['system_min_interval']

                if new_interval < system_min_interval:
                    new_interval = system_min_interval
                    interval_message = f"，但该RSS源的最低更新间隔为{system_min_interval}分钟，已将你的RSS源更新间隔设置为{new_interval}分钟"
                else:
                    interval_message = ""

                sql = "UPDATE rss_subscription SET user_min_interval = %s WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (new_interval, guild_rss_subscription_id, message.guild_id))

                # 更新rss_feed的current_interval为当前rss_feed的user_min_interval的最小值
                sql = "UPDATE rss_feed SET current_interval = (SELECT MIN(user_min_interval) FROM rss_subscription WHERE rss_feed_id = %s) WHERE rss_feed_id = %s"
                cursor.execute(sql, (rss_feed_id, rss_feed_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            _log.error(f"更新RSS源更新间隔时发生错误：{e}")
            await reply_with_log(message, "更新RSS源更新间隔时发生错误。")
            return

        await reply_with_log(message, f"成功更新RSS源：{custom_name} 的更新间隔为 {new_interval}分钟{interval_message}")

    async def update_feed_expiration(self, client, message: Message, guild_rss_subscription_id: str,
                                     new_expiration: str):
        # 检查输入是否为正整数
        if (not guild_rss_subscription_id.isdigit() or
                int(guild_rss_subscription_id) <= 0 or
                not new_expiration.isdigit() or
                int(new_expiration) < 0 or
                int(new_expiration) > self.rss_item_max_age):
            await reply_with_log(message, "输入错误，RSS源编号应为正整数，新的过期时间应为0到max_age之间的整数。")
            return

        guild_rss_subscription_id = int(guild_rss_subscription_id)
        new_expiration = int(new_expiration)

        # 更新数据库中的max_age
        try:
            with self.conn.cursor() as cursor:
                # 先判断是否存在该guild_rss_subscription_id
                sql = "SELECT custom_name FROM rss_subscription WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (guild_rss_subscription_id, message.guild_id))
                result = cursor.fetchone()
                if not result:
                    await reply_with_log(message, f"RSS源编号：{guild_rss_subscription_id} 在当前频道未找到。")
                    return
                custom_name = result['custom_name']

                sql = "UPDATE rss_subscription SET max_age = %s WHERE guild_rss_subscription_id = %s AND guild_id = %s"
                cursor.execute(sql, (new_expiration, guild_rss_subscription_id, message.guild_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            _log.error(f"更新RSS源过期时间时发生错误：{e}")
            await reply_with_log(message, "更新RSS源过期时间时发生错误。")
            return

        await reply_with_log(message, f"成功更新RSS源：{custom_name} 的过期时间为 {new_expiration}天")

    async def on_command(self, client, message: Message):
        guild_id = message.guild_id
        if not check_guild_authenticity(guild_id):
            await reply_with_log(message, content="当前功能存在安全隐患，请在我的官方频道【小千校园助手】中认证后使用")
            return
        if not is_rss_subscription_admin_from_message(message):
            await reply_with_log(message, "只有rss订阅管理才能使用该指令。")
            return

        content = message.content.strip()
        command_parts = content.split()
        if len(command_parts) < 3:
            usage = bot_features_dict.get("rss订阅", {}).get("usage", "")
            await reply_with_log(message, f"请提供指令。使用方法：\n{usage}")
            return

        action = command_parts[2]
        if action == "添加":
            if len(command_parts) != 6:
                await reply_with_log(message, "添加RSS源的指令格式应为：添加 [URL] [自定义名称] [更新间隔]")
                return
            await self.add_feed(client, message, command_parts[3], command_parts[4], command_parts[5])
        elif action == "删除":
            if len(command_parts) != 4:
                await reply_with_log(message, "删除RSS源的指令格式应为：删除 [RSS源序号]")
                return
            await self.remove_feed(client, message, command_parts[3])
        elif action == "列表":
            if len(command_parts) != 3:
                await reply_with_log(message, "查看RSS源列表的指令格式应为：列表")
                return
            await self.list_feeds(client, message)
        elif action == "修改更新间隔":
            if len(command_parts) != 5:
                await reply_with_log(message, "修改更新间隔的指令格式应为：修改更新间隔 [RSS源序号] [新的更新间隔]")
                return
            await self.update_feed_interval(client, message, command_parts[3], command_parts[4])
        elif action == "修改过期时间":
            if len(command_parts) != 5:
                await reply_with_log(message, "修改过期时间的指令格式应为：修改过期时间 [RSS源序号] [新的过期时间]")
                return
            await self.update_feed_expiration(client, message, command_parts[3], command_parts[4])
        else:
            await reply_with_log(message, "无效的指令，可用的指令为：添加、删除、列表")


rss = RSSSystem()
