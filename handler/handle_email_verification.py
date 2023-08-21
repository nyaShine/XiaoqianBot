import base64
import os
import random
import re

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from botpy import get_logger
from botpy.message import DirectMessage

from config import config
from utils.get_help import get_help, bot_features_dict
from utils.guild_utils import get_guild_name_from_redis
from utils.mysql_utils import get_mysql_conn
from utils.redis_utils import RedisConnection
from utils.roles import get_guild_roles, is_email_verification_admin_from_message
from utils.send_email import send_email, EmailSendingError
from utils.send_message_with_log import reply_with_log, post_dms_with_log, post_dms_from_message_with_log

_log = get_logger()

# 从环境变量中获取AES加密密钥
AES_KEY = os.environ.get('AES_KEY').encode()

# 创建一个AES加密对象
cipher = AES.new(AES_KEY, AES.MODE_ECB)


def encrypt_email(email):
    # 对电子邮件地址进行AES加密
    email = email.encode()
    encrypted_email = base64.b64encode(cipher.encrypt(pad(email, AES.block_size))).decode('utf-8')
    return encrypted_email


def decrypt_email(encrypted_email):
    # 对电子邮件地址进行AES解密
    email = unpad(cipher.decrypt(base64.b64decode(encrypted_email)), AES.block_size).decode('utf-8')
    return email


def execute_sql_with_commit(conn, sql, params):
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()


def validate_email_domain(email_domain):
    email_domain = email_domain.lstrip('@')
    if not re.match(r"[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_domain):
        return False, "邮箱域名格式不正确。请确保它是一个有效的电子邮件域名。"
    if "edu" not in email_domain.split("."):
        return False, "非教育邮箱。请使用一个包含 'edu' 的电子邮件域名。"
    return True, ""


def add_email_domain(email_domain, guild_id):
    is_valid, message = validate_email_domain(email_domain)
    if not is_valid:
        return message

    # 确保域名以'@'开头
    if not email_domain.startswith('@'):
        email_domain = '@' + email_domain

    conn = get_mysql_conn()
    with conn.cursor() as cursor:
        sql = "SELECT COUNT(*) AS count FROM email_domains WHERE email_domain = %s AND guild_id = %s"
        cursor.execute(sql, (email_domain, guild_id))
        result = cursor.fetchone()
        if result['count'] > 0:
            return "此邮箱域名已存在。"

    with conn.cursor() as cursor:
        sql = "SELECT COUNT(*) AS count, MAX(guild_domain_id) AS max_id FROM email_domains WHERE guild_id = %s"
        cursor.execute(sql, (guild_id,))
        result = cursor.fetchone()
        max_domain_counts = config['email_verification']['max_domain_counts']
        if result['count'] >= max_domain_counts:
            return f"当前频道的邮箱域名已达上限（{max_domain_counts}个）。无法添加更多。"
        current_max_id = int(result['max_id']) if result['max_id'] is not None else 0

    sql = "INSERT INTO email_domains (email_domain, guild_id, guild_domain_id) VALUES (%s, %s, %s)"
    execute_sql_with_commit(conn, sql, (email_domain, guild_id, current_max_id + 1))

    return f"邮箱域名 {email_domain} 已成功添加。"


def delete_email_domain(email_domain, guild_id):
    # 确保域名以'@'开头'
    if not email_domain.startswith('@'):
        email_domain = '@' + email_domain

    conn = get_mysql_conn()
    with conn.cursor() as cursor:
        # 检查域名是否存在
        sql = "SELECT guild_domain_id FROM email_domains WHERE email_domain = %s AND guild_id = %s"
        cursor.execute(sql, (email_domain, guild_id))
        result = cursor.fetchone()
        if not result:
            return "此邮箱域名不存在。"
        guild_domain_id = result['guild_domain_id']

    try:
        with conn.cursor() as cursor:
            conn.begin()
            # 删除域名
            sql = "DELETE FROM email_domains WHERE email_domain = %s AND guild_id = %s"
            cursor.execute(sql, (email_domain, guild_id))

            # 更新其它域名的guild_domain_id
            sql = "UPDATE email_domains SET guild_domain_id = guild_domain_id - 1 WHERE guild_id = %s AND guild_domain_id > %s"
            cursor.execute(sql, (guild_id, guild_domain_id))
            conn.commit()
    except Exception as e:
        conn.rollback()
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()

    return f"邮箱域名 {email_domain} 已成功删除。"


def clear_email_domains(guild_id):
    sql = "DELETE FROM email_domains WHERE guild_id = %s"
    conn = get_mysql_conn()
    execute_sql_with_commit(conn, sql, (guild_id,))

    return "当前频道的所有邮箱域名已成功清空(未删除邮箱地址信息)。"


def get_email_domains(guild_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT guild_domain_id, email_domain FROM email_domains WHERE guild_id = %s ORDER BY guild_domain_id"
            cursor.execute(sql, (guild_id,))
            result = cursor.fetchall()
            return [(row['guild_domain_id'], row['email_domain']) for row in result]
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()


def add_or_update_email_verification_role(guild_id, role_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 检查角色是否存在
            sql = "SELECT COUNT(*) AS count FROM email_verification_roles WHERE guild_id = %s"
            cursor.execute(sql, (guild_id,))
            result = cursor.fetchone()
            if result['count'] > 0:
                # 更新角色
                sql = "UPDATE email_verification_roles SET role = %s WHERE guild_id = %s"
                cursor.execute(sql, (role_id, guild_id))
            else:
                # 插入角色
                sql = "INSERT INTO email_verification_roles (role, guild_id) VALUES (%s, %s)"
                cursor.execute(sql, (role_id, guild_id))
            conn.commit()
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()


def delete_email_verification_role(guild_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM email_verification_roles WHERE guild_id = %s"
            cursor.execute(sql, (guild_id,))
            conn.commit()
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()


async def handle_email_verification_at_message(client, message):
    content = message.content.strip()
    command_parts = content.split(' ')
    command = command_parts[2] if len(command_parts) > 2 else None
    param = command_parts[3] if len(command_parts) > 3 else None

    if command is None:
        help_text = get_help('邮箱认证')
        await reply_with_log(message, help_text)
        return

    if not is_email_verification_admin_from_message(message):
        await reply_with_log(message, "抱歉，您没有权限执行此操作。")
        return

    if command == '添加域名':
        if param is None:
            await reply_with_log(message, "请输入要添加的邮箱域名。")
        else:
            result = add_email_domain(param, message.guild_id)
            await reply_with_log(message, result)
    elif command == '删除域名':
        if param is None:
            await reply_with_log(message, "请输入要删除的邮箱域名。")
        else:
            result = delete_email_domain(param, message.guild_id)
            await reply_with_log(message, result)
    elif command == '清空域名':
        result = clear_email_domains(message.guild_id)
        await reply_with_log(message, result)
    elif command == '域名列表':
        domains = get_email_domains(message.guild_id)
        if not domains:
            await reply_with_log(message, "当前频道没有设置邮箱域名。")
        else:
            domains_str = '\n'.join([f"{domain_id}: {domain}" for domain_id, domain in domains])
            await reply_with_log(message, f"当前频道的邮箱域名列表:\n{domains_str}")
    elif command == '添加邮箱认证身份组':
        if param is None:
            await reply_with_log(message, "请输入要添加的邮箱认证身份组ID或'取消'。")
        elif param == '取消':
            delete_email_verification_role(message.guild_id)
            await reply_with_log(message, "邮箱认证身份组已成功取消。")
        elif param.isdigit():
            guild_roles = await get_guild_roles(client, message.guild_id)
            if guild_roles is None:
                await reply_with_log(message, "获取身份组信息时发生错误。")
            else:
                role_ids = [role['id'] for role in guild_roles]
                role_name = next((role_info['name'] for role_info in guild_roles if role_info['id'] == param), None)
                if param not in role_ids:
                    await reply_with_log(message, f"身份组 {role_name} 在当前频道中不存在，使用@机器人 /查询身份组，以查看频道身份组ID。")
                else:
                    add_or_update_email_verification_role(message.guild_id, param)
                    await reply_with_log(message, f"邮箱认证身份组 {role_name} 已成功添加。")
        else:
            await reply_with_log(message, "无法识别的命令，请检查您的输入。")
    elif re.match(r"查询<@!\d+>", command):
        param = re.search(r"<@!(\d+)>", command).group(1)
        if param is None:
            await reply_with_log(message, "请输入要查询的用户。")
        else:
            user_id = param
            email_address = get_email_address(message.guild_id, user_id)
            if email_address is not None:
                await post_dms_from_message_with_log(client, message, f"用户 {user_id} 的电子邮件地址是 {email_address}")
                await reply_with_log(message, "已通过私信发送用户的电子邮件地址，请注意查看私信。")
            else:
                await reply_with_log(message, f"未找到用户 {user_id} 的电子邮件地址。")
    else:
        await reply_with_log(message, "无法识别的命令，请检查您的输入。")


def generate_verification_code():
    chars = config['email_verification']['chars']
    code_length = config['email_verification']['code_length']
    return ''.join(random.choices(chars, k=code_length))


def save_verification_code_to_redis(email, guild_id, author_id, code):
    encrypted_email = encrypt_email(email)
    redis_conn = RedisConnection().get_connection()
    guild_key_pattern = config['email_verification']['redis']['guild_key_pattern']
    key = guild_key_pattern.format(guild_id=guild_id, author_id=author_id)
    redis_conn.hmset(key, {"email": encrypted_email, "code": code})
    if code == 'Failed':
        redis_conn.expire(key, config['email_verification']['redis']['failed_ttl'])
    else:
        redis_conn.expire(key, config['email_verification']['redis']['ttl'])


def get_verification_code_from_redis(guild_id, author_id):
    redis_conn = RedisConnection().get_connection()
    guild_key_pattern = config['email_verification']['redis']['guild_key_pattern']
    key = guild_key_pattern.format(guild_id=guild_id, author_id=author_id)
    encrypted_email = redis_conn.hget(key, "email")
    code = redis_conn.hget(key, "code")
    if encrypted_email is not None:
        encrypted_email = encrypted_email.decode('utf-8')
    if code is not None:
        code = code.decode('utf-8')
    return encrypted_email, code


def check_verification_code(email, guild_id, code):
    saved_code = get_verification_code_from_redis(email, guild_id)
    return saved_code is not None and saved_code.lower() == code.lower()


def add_email_address(email_address, guild_id, user_id):
    encrypted_email_address = encrypt_email(email_address)
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) AS count FROM email_addresses WHERE email_address = %s AND guild_id = %s"
            cursor.execute(sql, (encrypted_email_address, guild_id))
            result = cursor.fetchone()
            if result['count'] > 0:
                return "此电子邮件地址已被使用。"
        sql = "INSERT INTO email_addresses (email_address, guild_id, user_id) VALUES (%s, %s, %s)"
        execute_sql_with_commit(conn, sql, (encrypted_email_address, guild_id, user_id))
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")


def get_email_address(guild_id, user_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT email_address FROM email_addresses WHERE guild_id = %s AND user_id = %s"
            cursor.execute(sql, (guild_id, user_id))
            result = cursor.fetchone()
            # 对电子邮件地址进行AES解密
            email_address = decrypt_email(result['email_address']) if result else None
            return email_address
    except Exception as e:
        _log.error(f"发生了一个错误: {e}")
    finally:
        conn.close()


async def handle_email_verification_direct_message(client, message: DirectMessage):
    src_guild_id = message.src_guild_id
    author_id = message.author.id

    # 检查用户是否已经进行过邮箱认证
    email_address = get_email_address(src_guild_id, author_id)
    if email_address is not None:
        await post_dms_with_log(client, message, content="您已经完成了邮箱认证，无需重复认证。")
        return

    content = message.content.strip()
    command_parts = content.split(' ')
    command = command_parts[1] if len(command_parts) > 1 else None

    if command is None:
        usage = bot_features_dict.get("邮箱认证", {}).get("usage", "")
        domains = get_email_domains(src_guild_id)
        domains_str = '\n'.join([f"{domain_id}: {domain}" for domain_id, domain in domains])
        await post_dms_with_log(client, message, content=f"指令格式错误。正确格式为：\n{usage}\n你可以使用的邮箱域名有：\n{domains_str}")
    elif command == "开始认证":
        username = command_parts[2] if len(command_parts) > 2 else None
        domain_id = command_parts[3] if len(command_parts) > 3 else None
        if username is None or domain_id is None:
            usage = bot_features_dict.get("邮箱认证", {}).get("usage", "")
            domains = get_email_domains(src_guild_id)
            domains_str = '\n'.join([f"{domain_id}: {domain}" for domain_id, domain in domains])
            await post_dms_with_log(client, message, content=f"指令格式错误。正确格式为：\n{usage}\n你可以使用的邮箱域名有：\n{domains_str}")
        else:
            domains = get_email_domains(src_guild_id)
            email_domain = next((domain for domain_id, domain in domains if domain_id == domain_id), None)
            if email_domain is None:
                await post_dms_with_log(client, message, content="无法识别的域名ID，请检查您的输入。")
            else:
                email = f"{username}{email_domain}"
                encrypted_email, verification_code = get_verification_code_from_redis(src_guild_id, author_id)
                ttl = RedisConnection().get_connection().ttl(f"guild_id:{src_guild_id}-author_id:{author_id}")
                if verification_code == 'Failed':
                    await post_dms_with_log(client, message, content=f"发送失败，请{ttl}秒后重试。")
                elif verification_code:
                    await post_dms_with_log(client, message, content="验证码已发送到您的邮箱，请查看邮箱。如果长时间未收到邮件请检查垃圾邮件箱或者重新尝试。")
                else:
                    verification_code = generate_verification_code()
                    guild_name = await get_guild_name_from_redis(client, src_guild_id)
                    subject = f'【{guild_name}】QQ频道校园邮箱验证'
                    body = f'您的验证码是：{verification_code}\n\n您收到这封邮件，是因为有人在【{guild_name}】QQ频道上使用了此邮箱地址进行教育邮箱验证。如果这不是您本人的操作，或者您没有进行此操作，请忽视此邮件。同时，如果此邮件给您带来了困扰，我们深感抱歉并诚挚地向您道歉。'
                    try:
                        send_email(email, subject, body)
                        save_verification_code_to_redis(email, src_guild_id, author_id, verification_code)
                        await post_dms_with_log(client, message,
                                                content="验证码已发送到您的邮箱。请输入验证码。例如：/邮箱认证 验证码 你的验证码")
                    except EmailSendingError:
                        save_verification_code_to_redis(email, src_guild_id, author_id, 'Failed')
                        await post_dms_with_log(client, message, content="验证码发送失败，请稍后重试。")
    elif command == "验证码":
        verification_code = command_parts[2] if len(command_parts) > 2 else None
        if verification_code is None:
            await post_dms_with_log(client, message, content="请输入验证码。例如：/邮箱认证 验证码 你的验证码")
        else:
            encrypted_email_address, saved_code = get_verification_code_from_redis(src_guild_id, author_id)
            if saved_code is None:
                await post_dms_with_log(client, message,
                                        content="请先发送验证码。例如：/邮箱认证 开始认证 邮箱用户名 邮箱域名id\n如果你已经发送过验证码，可能是验证码已过期。")
            else:
                email_address = decrypt_email(encrypted_email_address)
                if saved_code == verification_code.upper():
                    conn = get_mysql_conn()
                    with conn.cursor() as cursor:
                        sql = "SELECT role FROM email_verification_roles WHERE guild_id = %s"
                        cursor.execute(sql, (src_guild_id,))
                        result = cursor.fetchone()

                    if result is None:
                        await post_dms_with_log(client, message, content="当前频道没有设置邮箱认证身份组，请联系频道管理员。")
                    else:
                        role_id = result['role']
                        try:
                            await client.api.create_guild_role_member(
                                guild_id=src_guild_id,
                                role_id=role_id,
                                user_id=author_id,
                            )
                            result = add_email_address(email_address, src_guild_id, author_id)
                            if result is not None:
                                await post_dms_with_log(client, message, content=result)
                            else:
                                await post_dms_with_log(client, message, content="身份组添加成功！")
                        except Exception as e:
                            _log.error(f"发生了一个错误: {e}")
                            await post_dms_with_log(client, message, content="身份组添加失败，请稍后重试。")
                else:
                    await post_dms_with_log(client, message, content="验证码错误，请检查您的输入。")
    else:
        await post_dms_with_log(client, message, content="无法识别的命令，请检查您的输入。")
