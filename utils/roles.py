import json

from botpy import get_logger

from utils.mysql_utils import get_mysql_conn
from utils.redis_utils import RedisConnection

_log = get_logger()

# 创建一个redis连接
redis_conn = RedisConnection().get_connection()


def is_creator(user_roles):
    return '4' in user_roles


def is_creator_from_message(message):
    user_roles = message.member.roles  # 从 Message 对象获取用户的身份组 ID 列表
    return is_creator(user_roles)


def is_creator_or_super_admin(user_roles):
    return '4' in user_roles or '2' in user_roles


def is_creator_or_super_admin_from_message(message):
    user_roles = message.member.roles  # 从 Message 对象获取用户的身份组 ID 列表
    return is_creator_or_super_admin(user_roles)


async def get_guild_roles_ids(client, guild_id):
    try:
        # 获取频道身份组列表
        response = await client.api.get_guild_roles(guild_id=guild_id)
        return [role['id'] for role in response['roles']]
    except Exception as err:
        _log.error(f"调用 get_guild_roles, err = {err}")
        return None


def is_bot_admin(user_roles, guild_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 查询所有的机器人管理员身份组
            sql = "SELECT role FROM management_roles WHERE guild_id = %s"
            cursor.execute(sql, (guild_id,))
            bot_admin_roles = cursor.fetchall()

            # 检查用户的身份组是否包含任何机器人管理员身份组
            for role in bot_admin_roles:
                admin_role = role['role']
                if admin_role in user_roles:
                    return True
    except Exception as e:
        _log.error(f"检查机器人管理身份组时失败:{e}")
    finally:
        conn.close()

    return False


def is_bot_admin_from_message(message):
    user_roles = message.member.roles  # 从 Message 对象获取用户的身份组 ID 列表
    return (is_creator_or_super_admin(user_roles) or
            is_management_role(user_roles, message.guild_id, "机器人管理"))


def is_specific_admin_from_message(message, role_type):
    user_roles = message.member.roles  # 从 Message 对象获取用户的身份组 ID 列表
    return is_creator_or_super_admin(user_roles) or is_management_role(user_roles, message.guild_id, role_type)


def is_question_answer_admin_from_message(message):
    return is_specific_admin_from_message(message, "问答管理")


def is_minecraft_server_admin_from_message(message):
    return is_specific_admin_from_message(message, "mc管理")


def is_rss_subscription_admin_from_message(message):
    return is_specific_admin_from_message(message, "rss订阅管理")


def is_email_verification_admin_from_message(message):
    return is_specific_admin_from_message(message, "邮箱认证管理")


def is_management_role(user_roles, guild_id, role_type):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 查询特定类型的管理员身份组
            sql = "SELECT role FROM management_roles WHERE guild_id = %s AND role_type = %s"
            cursor.execute(sql, (guild_id, role_type))
            management_roles = cursor.fetchall()

            # 检查用户的身份组是否包含任何管理身份组
            for role in management_roles:
                management_role = role['role']
                if management_role in user_roles:
                    return True
    except Exception as e:
        _log.error(f"检查管理身份组时失败：{e}")
    finally:
        conn.close()

    return False


async def get_guild_roles(client, guild_id):
    try:
        # 尝试从redis获取数据
        roles_data = redis_conn.get(f"guild_roles:{guild_id}")

        # 如果redis中存在数据，则直接返回
        if roles_data is not None:
            roles = json.loads(roles_data)
        else:
            # 如果redis中不存在数据，则发送请求获取数据
            response = await client.api.get_guild_roles(guild_id=guild_id)
            roles = response['roles']

            # 将获取的数据存入redis，设置过期时间为3分钟
            redis_conn.setex(f"guild_roles:{guild_id}", 180, json.dumps(roles))

        return roles
    except Exception as e:
        _log.error(f"获取频道身份组时错误：{e}")
        return None
