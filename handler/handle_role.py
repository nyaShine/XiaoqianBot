from botpy.logging import get_logger
from botpy.message import Message

from config import config
from utils.get_help import bot_features_dict
from utils.mysql_utils import get_mysql_conn
from utils.roles import is_creator_or_super_admin_from_message, get_guild_roles
from utils.send_message_with_log import reply_with_log


_log = get_logger()


def add_management_role(role, guild_id, role_type):
    conn = get_mysql_conn()

    # 检查是否试图添加固定的管理员身份组
    if role in ['2', '4']:
        return "不能将创建者或超级管理员身份组添加到机器人管理员身份组。"

    try:
        with conn.cursor() as cursor:
            # 如果要添加的管理员身份组是机器人管理员
            if role_type == "机器人管理":
                # 检查该身份组是否已经是其他类型的管理员
                check_sql = "SELECT * FROM management_roles WHERE role = %s AND guild_id = %s AND role_type != '机器人管理'"
                cursor.execute(check_sql, (role, guild_id))
                if cursor.fetchone() is not None:
                    # 如果已经是其他类型的管理员，那么删除其作为其他类型管理员的记录
                    delete_sql = "DELETE FROM management_roles WHERE role = %s AND guild_id = %s AND role_type != '机器人管理'"
                    cursor.execute(delete_sql, (role, guild_id))
            else:
                # 如果要添加的不是机器人管理，而该身份组已经是机器人管理
                check_sql = "SELECT * FROM management_roles WHERE role = %s AND guild_id = %s AND role_type = '机器人管理'"
                cursor.execute(check_sql, (role, guild_id))
                if cursor.fetchone() is not None:
                    # 不允许添加
                    return f"{role} 已经是机器人管理，不能设置为其他类型的管理。"

            # 首先检查管理员身份组是否已经存在
            check_sql = "SELECT * FROM management_roles WHERE role = %s AND guild_id = %s AND role_type = %s"
            cursor.execute(check_sql, (role, guild_id, role_type))
            # 如果已存在（查询操作返回的结果不为空），则直接返回False
            if cursor.fetchone() is not None:
                return f"{role} 已经是 {role_type}，无需再次设置。"

            # 如果要添加的管理员身份组不存在，则执行添加操作
            sql = """INSERT INTO management_roles (role, guild_id, role_type) 
                     VALUES (%s, %s, %s)"""
            cursor.execute(sql, (role, guild_id, role_type))

        conn.commit()
    except Exception as e:
        _log.error(f"添加管理身份组失败：{e}")
        conn.rollback()
        return f"添加 {role_type} 失败：{e}"
    finally:
        conn.close()

    return f"{role} 已成功设置为 {role_type}。"


def reset_management_roles(guild_id):
    conn = get_mysql_conn()

    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM management_roles WHERE guild_id = %s"
            cursor.execute(sql, (guild_id,))

        conn.commit()
    except Exception as e:
        _log.error(f"重置管理身份组失败：{e}")
        conn.rollback()
    finally:
        conn.close()


def remove_management_role(role, guild_id, role_type):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            # 查询要删除的管理员身份组是否存在
            check_sql = "SELECT * FROM management_roles WHERE role = %s AND guild_id = %s AND role_type = %s"
            cursor.execute(check_sql, (role, guild_id, role_type))
            if cursor.fetchone() is None:
                return False

            # 如果存在，则执行删除操作
            sql = """DELETE FROM management_roles WHERE role = %s AND guild_id = %s AND role_type = %s"""
            cursor.execute(sql, (role, guild_id, role_type))

        conn.commit()
    except Exception as e:
        _log.error(f"移除管理身份组失败：{e}")
        conn.rollback()
        return False
    finally:
        conn.close()

    return True


def get_all_management_roles(guild_id):
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT role, role_type FROM management_roles WHERE guild_id = %s"
            cursor.execute(sql, (guild_id,))
            rows = cursor.fetchall()

            roles_dict = {}
            for row in rows:
                role_type = row["role_type"]
                if role_type not in roles_dict:
                    roles_dict[role_type] = []
                roles_dict[role_type].append(row["role"])

            return roles_dict
    except Exception as e:
        _log.error(f"获取所有管理身份组失败：{e}")
        return None
    finally:
        conn.close()


async def handle_query_identity_group(client, message: Message):
    if not is_creator_or_super_admin_from_message(message):
        await reply_with_log(message, "只有频道创建者和超级管理员才能使用该指令。")
        return

    try:
        # 获取频道身份组列表
        roles = await get_guild_roles(client, message.guild_id)
        if roles is None:
            await reply_with_log(message, "获取身份组信息时发生错误。")
            return

        # 构建包含身份组名称和 ID 的消息
        roleListMsg = "身份组列表：\n"
        for role in roles:
            roleListMsg += f"ID: {role['id']}, 名称: {role['name']}, 人数: {role['number']}, 成员上限: {role['member_limit']}\n"

        await reply_with_log(message, roleListMsg)  # 发送响应
    except Exception as err:
        _log.error(f"调用 get_guild_roles, err = {err}")


async def handle_admin(client, message: Message):
    if not is_creator_or_super_admin_from_message(message):
        await reply_with_log(message, "只有频道创建者和超级管理员才能使用该指令。")
        return

    # 解析参数
    args = message.content.split()
    if len(args) < 3:
        usage = bot_features_dict.get("设置管理", {}).get("usage", "")
        await reply_with_log(message, f"指令格式错误。正确格式为：\n{usage}")
        return

    role = args[2]

    if role == "重置":
        reset_management_roles(message.guild_id)  # 删除指定频道的所有管理员记录
        await reply_with_log(message, "已成功重置机器人的管理员列表。")
        return

    if role == "列表":
        roles_dict = get_all_management_roles(message.guild_id)
        guild_roles = await get_guild_roles(client, message.guild_id)
        if guild_roles is None:
            await reply_with_log(message, "获取身份组信息时发生错误。")
            return
        role_names_dict = {role_info['id']: role_info['name'] for role_info in guild_roles}
        role_nums_dict = {role_info['id']: role_info['number'] for role_info in guild_roles}

        roles_list_msg = "管理员身份组列表：\n"
        for role_type, roles in roles_dict.items():
            roles_list_msg += f"{role_type}：\n"
            for role in roles:
                role_name = role_names_dict.get(role, "未知身份组")
                role_num = role_nums_dict.get(role, "未知")
                roles_list_msg += f"    {role_name}（{role}, {role_num}人）\n"
            roles_list_msg = roles_list_msg.rstrip("\n")
        await reply_with_log(message, roles_list_msg)
        return

    if len(args) < 4:
        usage = bot_features_dict.get("设置管理", {}).get("usage", "")
        await reply_with_log(message, f"指令格式错误。正确格式为：\n{usage}")
        return

    role_type = args[3]
    # 检查 role_type 是否有效
    valid_role_types = config['valid_role_types']
    if role_type not in valid_role_types:
        valid_roles_str = "、".join(valid_role_types)
        await reply_with_log(message, f"无效的管理类型。有效的管理类型包括：{valid_roles_str}。")
        return

    operation = args[4] if len(args) > 4 else None
    valid_operations = ["设置", "取消"]
    if operation not in valid_operations:
        valid_operations_str = "或".join(valid_operations)
        await reply_with_log(message, f"无效的操作。只能是 {valid_operations_str}。")
        return

    # 获取身份组列表
    guild_roles = await get_guild_roles(client, message.guild_id)
    if guild_roles is None:
        await reply_with_log(message, "获取身份组信息时发生错误。")
        return

    role_ids = [role['id'] for role in guild_roles]
    role_name = next((role_info['name'] for role_info in guild_roles if role_info['id'] == role), None)

    if role not in role_ids:
        await reply_with_log(message, f"身份组 {role_name} 在当前频道中不存在，使用@机器人 /查询身份组，以查看频道身份组ID。")
        return

    # 添加管理员
    if operation == "设置":
        result = add_management_role(role, message.guild_id, role_type)  # 添加一条管理员记录。若已存在，则返回False；否则返回True。
        if "已成功设置为" in result:
            await reply_with_log(message, f"{result}")
        else:
            await reply_with_log(message, f"{result}")

    # 取消管理员
    elif operation == "取消":
        removed = remove_management_role(role, message.guild_id, role_type)  # 移除管理员
        if removed:
            await reply_with_log(message, f"已取消 {role_name} 身份组的 {role_type} 身份。")
        else:
            await reply_with_log(message, f"{role_name} 身份组并未设置为 {role_type}，取消失败。")
