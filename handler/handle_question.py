import pymysql
import re
import os
import shutil
import requests

from botpy.logging import get_logger
from botpy.message import Message

from config import config
from utils.guild_utils import check_guild_authenticity
from utils.watermark import watermark
from utils.mysql_utils import get_mysql_conn
from utils.get_help import bot_features_dict
from utils.roles import is_question_answer_admin_from_message
from utils.send_message_with_log import reply_with_log

_log = get_logger()


class QASystem:
    # 初始化创建mysql connection
    def __init__(self):
        self.conn = get_mysql_conn()

    @staticmethod
    def split_keywords(keywords):
        keyword_list = [keyword.strip() for keyword in re.split('[,|]', keywords)]
        return keyword_list[:5]

    # 根据问题和答案搜索
    def search_questions(self, guild_id, keywords, smart_search=False):
        keywords_list = self.split_keywords(keywords)
        cursor = self.conn.cursor()
        try:
            query_conditions = " AND ".join(
                [f"(question LIKE '%%{keyword}%%' OR answer LIKE '%%{keyword}%%')" for keyword in keywords_list])

            cursor.execute(f"""
                SELECT qa.guild_question_id, qa.question, qa.answer, 
                GROUP_CONCAT('resource/question_answer/', qa.question_answer_id, '/image_seq-', qai.image_seq ORDER BY qai.image_seq) AS image_path
                FROM question_answer qa
                LEFT JOIN question_answer_image qai ON qa.question_answer_id = qai.question_answer_id
                WHERE {query_conditions} AND qa.guild_id = %s
                GROUP BY qa.guild_question_id, qa.question, qa.answer
            """, guild_id)

            results = cursor.fetchall()

        except pymysql.Error as e:
            _log.error(f"错误：{e}")

        # 对结果进行处理，合并具有相同问题的不同图像路径
        processed_results = []
        for result in results:
            # 使用os.path.join处理image_path
            if result['image_path']:
                result['image_path'] = os.path.join(*result['image_path'].split(','))
            else:
                result['image_path'] = []
            processed_results.append(result)

        if smart_search and len(processed_results) == 1:
            return processed_results[0]
        else:
            return processed_results

    def set_watermark(self, guild_id, watermark_text, dense):
        cursor = self.conn.cursor()
        try:
            if watermark_text == "":
                cursor.execute("""
                    DELETE FROM question_answer_watermark WHERE guild_id = %s;
                """, guild_id)
            else:
                cursor.execute("""
                    INSERT INTO question_answer_watermark (guild_id, watermark, is_dense)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE watermark = %s, is_dense = %s;
                """, (guild_id, watermark_text, dense, watermark_text, dense))
            self.conn.commit()
            return True
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return False

    def get_watermark_info(self, guild_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT watermark, is_dense
                FROM question_answer_watermark
                WHERE guild_id = %s;
            """, guild_id)
            result = cursor.fetchone()
            if result:
                return result['watermark'], bool(result['is_dense'])
            return None, False
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return None, False

    async def send_images_with_watermark(self, message, image_paths, id, guild_id):
        for image_path in image_paths:
            full_image_path = image_path  # 直接使用 image_path
            watermark_text, dense = self.get_watermark_info(guild_id)
            if watermark_text:
                new_image_path = watermark.add_watermark_to_image(full_image_path, watermark_text, dense)
                await reply_with_log(message, content="", quote=False, at=False, file_image=new_image_path)
            else:
                await reply_with_log(message, content="", quote=False, at=False, file_image=full_image_path)

    # 将问答添加到数据库
    def add_question_answer(self, guild_id, question, answer):
        cursor = self.conn.cursor()

        # 检查问题的长度是否超过最大长度
        max_question_length = config['question_answer_system']['max_question_length']
        if len(question) > max_question_length:
            return False, f"问题的长度不能超过{max_question_length}个字符。"

        # 检查问题是否已经存在
        cursor.execute("""
            SELECT COUNT(*) FROM question_answer WHERE question = %s and guild_id = %s;
        """, (question, guild_id))
        count = cursor.fetchone()['COUNT(*)']
        if count > 0:
            return False, "问题已存在。"

        # 检查每个频道的问题数量是否超过上限
        cursor.execute("""
            SELECT COUNT(*) FROM question_answer WHERE guild_id = %s;
        """, guild_id)
        count = cursor.fetchone()['COUNT(*)']
        max_qa_per_channel = config['question_answer_system']['max_qa_per_channel']
        if count >= max_qa_per_channel:
            return False, f"每个频道的问题数量不能超过{max_qa_per_channel}个。"

        try:
            # 查询当前guild_id下的最大guild_question_id
            cursor.execute("""
                SELECT MAX(guild_question_id) as max_id FROM question_answer WHERE guild_id = %s;
            """, guild_id)
            result = cursor.fetchone()
            max_guild_question_id = 0 if result['max_id'] is None else result['max_id']
            guild_question_id = max_guild_question_id + 1

            cursor.execute("""
                INSERT INTO question_answer (question, answer, guild_id, guild_question_id)
                VALUES (%s, %s, %s, %s)
            """, (question, answer, guild_id, guild_question_id))

            self.conn.commit()
            return True, "问题和答案已成功添加到数据库。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return False, "添加问题和答案时发生错误。"

    def add_question_with_image(self, guild_id, question, answer, attachments):
        success, message = self.add_question_answer(guild_id, question, answer)
        if not success:
            return False, message

        cursor = self.conn.cursor()

        try:
            # 获取刚刚插入的问题的ID
            cursor.execute("""
                SELECT question_answer_id FROM question_answer
                WHERE question = %s AND guild_id = %s;
            """, (question, guild_id))
            question_answer_id = cursor.fetchone()['question_answer_id']

            # 保存图片到本地
            image_dir = os.path.join("resource", "question_answer", str(question_answer_id))
            os.makedirs(image_dir, exist_ok=True)
            for index, attachment in enumerate(attachments):
                image_seq = index + 1
                image_url = attachment.url
                if "://" not in image_url:
                    image_url = "https://" + image_url
                response = requests.get(image_url, stream=True)
                if response.status_code == 200:
                    image_path = os.path.join(image_dir, f"image_seq-{image_seq}")
                    with open(image_path, 'wb') as f:
                        response.raw.decode_content = True
                        shutil.copyfileobj(response.raw, f)

                    # 将图片信息插入数据库
                    cursor.execute("""
                        INSERT INTO question_answer_image (question_answer_id, image_seq)
                        VALUES (%s, %s)
                    """, (question_answer_id, image_seq))

            self.conn.commit()
            return True, "问题和答案已成功添加到数据库，图片也已保存。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return False, "添加问题和答案时发生错误。"

    def modify_question(self, guild_id, guild_question_id, question_answer):
        cursor = self.conn.cursor()

        question, answer = question_answer.split(':', 1) if ':' in question_answer else (question_answer, '')

        if not guild_question_id.isdigit():
            return "错误: ID 必须是一个数字。"

        # 检查问题的长度是否超过最大长度
        max_question_length = config['question_answer_system']['max_question_length']
        if len(question) > max_question_length:
            return f"问题的长度不能超过{max_question_length}个字符。"

        cursor.execute("""
        SELECT COUNT(*) FROM question_answer WHERE guild_question_id = %s AND guild_id = %s;
        """, (guild_question_id, guild_id))

        result = cursor.fetchone()
        if result['COUNT(*)'] == 0:
            return "错误: 没有找到问题ID为 " + str(guild_question_id) + " 的问题。"

        # 检查是否已经存在相同的问题
        cursor.execute("""
        SELECT COUNT(*) FROM question_answer WHERE question = %s and guild_id = %s;
        """, (question, guild_id))
        count = cursor.fetchone()['COUNT(*)']
        if count > 0:
            return "错误: 问题已存在。"

        try:
            cursor.execute("""
            UPDATE question_answer q SET q.question = %s, q.answer = %s
            WHERE q.guild_question_id = %s AND q.guild_id = %s;
            """, (question, answer, guild_question_id, guild_id))

            cursor.execute("""
            DELETE FROM question_answer_error_messages 
            WHERE question_answer_id IN (
            SELECT question_answer_id FROM question_answer WHERE guild_id = %s AND guild_question_id = %s);
            """, (guild_id, guild_question_id))

            self.conn.commit()
            return f"已修改问题 {guild_question_id} ，当前问题为：{question}，答案为：{answer}。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return "修改问题时发生错误。"

    def delete_question(self, guild_id, guild_question_id):
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            # 事务开始
            cursor.execute("BEGIN;")

            # 通过 guild_question_id 查询出对应的 question_answer_id
            cursor.execute("""
                SELECT question_answer_id FROM question_answer WHERE guild_id = %s AND guild_question_id = %s;
            """, (guild_id, guild_question_id))
            result = cursor.fetchone()
            question_answer_id = result['question_answer_id']

            # 删除与问题相关的所有错误消息
            cursor.execute("""
                DELETE FROM question_answer_error_messages WHERE question_answer_id = %s;
            """, (question_answer_id,))

            # 删除与问题相关的所有图片
            cursor.execute("""
                DELETE FROM question_answer_image WHERE question_answer_id = %s;
            """, (question_answer_id,))

            # 删除问题
            cursor.execute("""
                DELETE FROM question_answer WHERE guild_id = %s AND guild_question_id = %s;
            """, (guild_id, guild_question_id))

            # 提交事务
            self.conn.commit()

            # 删除对应的resource/question_answer/{question_answer_id}文件夹里的所有文件
            image_dir = os.path.join("resource", "question_answer", str(question_answer_id))
            shutil.rmtree(image_dir, ignore_errors=True)

            return "问题已成功删除。"
        except pymysql.Error as e:
            # 回滚事务
            self.conn.rollback()
            _log.error(f"错误：{e}")
            return "删除问题时发生错误。"

    def delete_images(self, guild_id, guild_question_id):
        cursor = self.conn.cursor()

        # 检查是否存在对应图片
        cursor.execute("""
            SELECT question_answer_id FROM question_answer WHERE guild_id = %s AND guild_question_id = %s;
        """, (guild_id, guild_question_id))
        question_answer_id = cursor.fetchone()

        if not question_answer_id:
            return "没有找到与此问题相关联的图片。"

        try:
            question_answer_id = question_answer_id['question_answer_id']
            cursor.execute("""
                DELETE FROM question_answer_image WHERE question_answer_id = %s;
            """, (question_answer_id,))
            self.conn.commit()

            # 删除对应的resource/question_answer/{question_answer_id}文件夹里的所有文件
            image_dir = os.path.join("resource", "question_answer", str(question_answer_id))
            shutil.rmtree(image_dir, ignore_errors=True)

            return "图片已成功删除。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return "删除图片时发生错误。"

    def add_images(self, guild_id, guild_question_id, attachments):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT question_answer_id FROM question_answer WHERE guild_id = %s AND guild_question_id = %s;
            """, (guild_id, guild_question_id))
            result = cursor.fetchone()

            if not result:  # 如果没有找到相应的 guild_question_id 数据
                return "添加图片失败，未找到指定问题序号。"
            question_answer_id = result['question_answer_id']

            # 保存图片到本地
            image_dir = os.path.join("resource", "question_answer", str(question_answer_id))
            os.makedirs(image_dir, exist_ok=True)

            # 获取已有图片数量
            cursor.execute("""
                SELECT COUNT(*) FROM question_answer_image WHERE question_answer_id = %s;
            """, (question_answer_id,))
            existing_image_count = cursor.fetchone()['COUNT(*)']

            if existing_image_count + len(attachments) > 9:
                return "添加图片失败，附件的图片数量加上数据库里已有的图片数量不得超过9个。"

            for index, attachment in enumerate(attachments):
                image_seq = existing_image_count + index + 1
                image_url = attachment.url
                if "://" not in image_url:
                    image_url = "https://" + image_url
                response = requests.get(image_url, stream=True)
                if response.status_code == 200:
                    image_path = os.path.join(image_dir, f"image_seq-{image_seq}")
                    with open(image_path, 'wb') as f:
                        response.raw.decode_content = True
                        shutil.copyfileobj(response.raw, f)

                    # 将图片信息插入数据库
                    cursor.execute("""
                        INSERT INTO question_answer_image (question_answer_id, image_seq)
                        VALUES (%s, %s)
                    """, (question_answer_id, image_seq))

            self.conn.commit()
            return "图片已成功添加。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            return "添加图片时发生错误。"

    # 提交错误报告
    def report_error(self, guild_id, error_id, error_text):
        cursor = self.conn.cursor()
        if not error_id.isdigit():
            response = "错误: ID必须是一个数字。"
            return response
        error_id = int(error_id)
        try:
            cursor.execute("""
                   SELECT * FROM `question_answer` WHERE `guild_question_id` = %s and guild_id = %s
               """, (error_id, guild_id))
            res = cursor.fetchone()
            if res is None:
                response = "提交错误报告时发生错误：指定ID不存在。"
                return response
            try:
                cursor.execute("""
                       INSERT INTO `question_answer_error_messages` (`question_answer_id`, `error_message`) VALUES (%s, %s)
                   """, (res['question_answer_id'], error_text))
                self.conn.commit()
                response = "错误报告已提交，感谢您的反馈！"
            except pymysql.Error as e:
                _log.error(f"错误：{e}")
                response = "提交错误报告时发生错误。"
        except pymysql.Error as e:
            _log.error(f"错误：{e}")
            response = "提交错误报告时发生错误。"
        return response

    # 查询错误报告
    def retrieve_errors(self, guild_id, guild_question_id=None):
        cursor = self.conn.cursor()
        try:
            # 如果没有提供频道问题ID，则检索所有错误
            if guild_question_id is None:
                cursor.execute("""
                    SELECT question_answer.guild_question_id, question_answer.question, question_answer_error_messages.error_message 
                    FROM `question_answer_error_messages` 
                    INNER JOIN `question_answer` ON question_answer_error_messages.question_answer_id = question_answer.question_answer_id
                    WHERE question_answer.guild_id = %s
                """, guild_id)
            else:  # 检索特定错误
                cursor.execute("""
                    SELECT question_answer.guild_question_id, question_answer.question, question_answer_error_messages.error_message 
                    FROM `question_answer_error_messages` 
                    INNER JOIN `question_answer` ON question_answer_error_messages.question_answer_id = question_answer.question_answer_id
                    WHERE question_answer.guild_id = %s AND question_answer.guild_question_id = %s
                """, (guild_id, guild_question_id))

            results = cursor.fetchall()
            return results

        except pymysql.Error as e:
            _log.error(f"错误：{e}")

    def delete_error(self, guild_id, error_id):
        cursor = self.conn.cursor()

        if error_id == "全部":
            try:  # 尝试执行SQL查询：删除所有错误信息
                cursor.execute("""DELETE FROM question_answer_error_messages 
                WHERE question_answer_id IN (
                SELECT question_answer_id FROM question_answer WHERE guild_id = %s)
                """, guild_id)
                self.conn.commit()
                return "已删除全部报错信息。"
            except pymysql.Error as e:
                _log.error(f"错误：{e}")
                return "删除报错信息时发生错误。"
        else:
            if not error_id.isdigit():  # 如果错误ID不是数字，则返回错误信息
                return "错误: ID必须是一个数字。"
            try:  # 尝试执行SQL查询：删除具有特定错误ID的错误消息
                cursor.execute("""
                DELETE FROM question_answer_error_messages
                WHERE question_answer_id IN (
                SELECT question_answer_id FROM question_answer WHERE guild_id = %s AND guild_question_id = %s);
                """, (guild_id, error_id))
                self.conn.commit()
                return f"已删除问题 {error_id} 的报错信息。"
            except pymysql.Error as e:
                _log.error(f"错误：{e}")
                return "删除报错信息时发生错误。"

    # 实现多关键词匹配问题的智能搜索
    def smart_search(self, guild_id, keywords):
        result = self.search_questions(guild_id, keywords, smart_search=True)

        if isinstance(result, dict):  # 如果只找到一条结果
            id, question, answer = result['guild_question_id'], result['question'], result['answer']
            image_paths = result['image_path'].split(',') if result['image_path'] else []
            return id, question, answer, image_paths

        elif isinstance(result, list) and result:  # 找到多个结果，且结果列表不为空
            return result
        else:  # 找不到结果 or 结果列表为空
            return None

    def search_question_by_id(self, guild_id, guild_question_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"""
                SELECT qa.guild_question_id, qa.question, qa.answer, 
                GROUP_CONCAT('resource/question_answer/', qa.question_answer_id, '/image_seq-', qai.image_seq ORDER BY qai.image_seq) AS image_paths
                FROM question_answer qa
                LEFT JOIN question_answer_image qai ON qa.question_answer_id = qai.question_answer_id
                WHERE qa.guild_id = %s AND qa.guild_question_id = %s
                GROUP BY qa.guild_question_id
            """, (guild_id, guild_question_id))

            results = cursor.fetchall()

        except pymysql.Error as e:
            _log.error(f"错误：{e}")

        # 对结果进行处理，合并具有相同问题的不同图像路径
        if results:
            processed_result = results[0]
            # 将image_paths分割为列表
            image_paths = processed_result['image_paths'].split(',') if processed_result['image_paths'] else []
            return processed_result['guild_question_id'], processed_result['question'], processed_result[
                'answer'], image_paths
        else:
            return None

    async def on_command(self, client, message: Message):
        guild_id = message.guild_id
        if not check_guild_authenticity(guild_id):
            await reply_with_log(message, content="当前功能存在安全隐患，请在我的官方频道【小千校园助手】中认证后使用")
            return
        content = message.content.strip()
        command_parts = content.split()

        if len(command_parts) < 3:
            usage = bot_features_dict.get("问", {}).get("usage", "")
            response = "你可能在使用问命令的时候遗漏了一些内容，以下是此命令的完整使用方法: \n" + usage
            await reply_with_log(message, response)
            return

        action = command_parts[2]
        args = " ".join(command_parts[3:])

        if action == "添加":
            if not is_question_answer_admin_from_message(message):
                response = "只有问答管理才能使用该指令。"
            else:
                question_answer_parts = args.split(':', 1)
                if len(question_answer_parts) == 2:
                    question, answer = question_answer_parts

                    # 处理附件中的图片
                    attachments = message.attachments
                    if attachments:
                        success = self.add_question_with_image(guild_id, question, answer, attachments)
                    else:
                        success = self.add_question_answer(guild_id, question, answer)

                    if success:
                        response = "问题和答案已成功添加到数据库。"
                    else:
                        response = "添加问题和答案时发生错误。可能是问题已存在。"
                else:
                    response = "请使用正确的格式添加问题和答案：`/问 添加 <问题>:<答案>`。"

        elif action == "报错":
            # 从args中提取出error_id和error_text
            error_parts = args.split(' ', 1)
            if len(error_parts) == 2:
                error_id, error_text = error_parts
                response = self.report_error(guild_id, error_id, error_text)
            else:
                response = "你可能在使用报错命令的时候遗漏了一些内容。你应该这样使用：/问 报错 <错误ID> <错误描述>"
        elif action == "查错":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限使用查错功能。只有问答管理才能使用该指令。"
            elif not args:
                response = '不合法的查错命令。应当为 "/问 查错 全部" 或者 "/问 查错 <问题编号>"'
            elif args == "全部":
                errors = self.retrieve_errors(guild_id)
                if errors:  # 如果错误不是None或空
                    response_msgs = [
                        f"问题ID: {error['guild_question_id']}, 问题: {error['question']}, 错误信息: {error['error_message']}"
                        for error in errors]
                    response = '\n'.join(response_msgs)
                else:
                    response = "当前频道没有错误报告"
            elif args.isdigit():  # 检查参数是否为数字（即，guild_question_id）
                errors = self.retrieve_errors(guild_id, int(args))
                if errors:  # 如果错误不是None或空
                    response_msgs = [
                        f"问题ID: {error['guild_question_id']}, 问题: {error['question']}, 错误信息: {error['error_message']}"
                        for error in errors]
                    response = '\n'.join(response_msgs)
                else:
                    response = "当前问题没有错误报告"
            else:
                response = "不合法的查错命令。应当为 \"/问 查错 全部\" 或者 \"/问 查错 <问题编号>\""
        elif action == "删错":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                error_id = args
                response = self.delete_error(guild_id, error_id)
        elif action == "修改":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                question_answer_parts = args.split(' ', 1)
                if len(question_answer_parts) == 2:
                    question_answer_id, question_answer = question_answer_parts
                    # 检查修改后的问题是否为空
                    if question_answer.strip() == "":
                        response = "修改后的问题不能为空。"
                    else:
                        response = self.modify_question(guild_id, question_answer_id, question_answer)
                else:
                    response = "你可能在使用修改命令的时候遗漏了一些内容。你应该这样使用：'/问 修改 <问题ID> <问题>:<答案>'"
        elif action == "水印":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                if not args:
                    response = '使用方法: @机器人 /问 水印 <无或不超过15个字符的utf8文本> [稀|密]'
                else:
                    args_split = args.split()
                    if len(args_split) >= 1:
                        watermark_text = args_split[0]
                        if len(args_split) >= 2:
                            watermark_density = args_split[1].lower()
                            if watermark_density not in ["稀", "密"]:
                                response = '使用方法: @机器人 /问 水印 <无或不超过15个字符的utf8文本> [稀|密]'
                                await reply_with_log(message, response)
                                return
                            else:
                                dense = watermark_density == "密"
                        else:
                            dense = False

                        if watermark_text == "无":
                            watermark_text = ""

                        success = self.set_watermark(guild_id, watermark_text, dense)
                        if success:
                            response = f"水印已设置为：{args if args != '' else '无'}"
                        else:
                            response = "设置水印时发生错误。"
                    else:
                        response = '使用方法: @机器人 /问 水印 <无或不超过15个字符的utf8文本> [稀|密]'
        elif action == "删除":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                if not args:
                    response = '使用方法: @机器人 /问 删除 <问题序号（guild_question_id）>'
                elif not args.isdigit():
                    response = "错误: 问题序号必须是一个数字。"
                else:
                    guild_question_id = args
                    response = self.delete_question(guild_id, guild_question_id)
        elif action == "删图":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                if not args:
                    response = '使用方法: @机器人 /问 删图 <问题序号（guild_question_id）>'
                elif not args.isdigit():
                    response = "错误: 问题序号必须是一个数字。"
                else:
                    guild_question_id = args
                    response = self.delete_images(guild_id, guild_question_id)
        elif action == "加图":
            if not is_question_answer_admin_from_message(message):
                response = "你没有权限执行此操作。只有问答管理才能使用该指令。"
            else:
                if not args or not message.attachments:
                    response = '使用方法: @机器人 /问 加图 <问题序号（guild_question_id）>'
                elif not args.isdigit():
                    response = "错误: 问题序号必须是一个数字。"
                else:
                    guild_question_id = args
                    response = self.add_images(guild_id, guild_question_id, message.attachments)
        elif action.isdigit():
            guild_question_id = int(action)
            search_result = self.search_question_by_id(guild_id, guild_question_id)
            if search_result:
                id, question, answer, image_paths = search_result
                response = f"{id} - {question}\n\n{answer}"
                # 如果存在图片，分次发送图片
                if image_paths:
                    await self.send_images_with_watermark(message, image_paths, id, guild_id)
            else:
                response = f"抱歉，没有找到与您输入的ID匹配的问题。"
        else:
            search_result = self.smart_search(guild_id, action)
            if isinstance(search_result, tuple):  # 如果搜索结果是元组，解包它
                id, question, answer, image_paths = search_result
                response = f"{id} - {question}\n\n{answer}"
                # 如果存在图片，分次发送图片
                if image_paths:
                    await self.send_images_with_watermark(message, image_paths, id, guild_id)

            elif isinstance(search_result, list):  # 如果搜索结果是列表，从其项目创建响应
                response = "\n\n".join(
                    [f"{result['guild_question_id']} - {result['question']}" for result in
                     search_result])

            else:  # 如果搜索结果是None或空字符串，发送适当的响应
                response = f"抱歉，没有找到与您的搜索关键词匹配的结果。建议尝试其他关键词搜索。"

        await reply_with_log(message, response, encode_urls=True)  # 发送响应


qa = QASystem()
