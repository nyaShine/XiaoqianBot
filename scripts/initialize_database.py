import getpass
import os
import subprocess

from mysql.connector import connect, Error


# 警告用户并提供退出选项
print("警告：这个脚本是用来初始化数据库的，不是在正常的生产环境中使用。运行这个脚本会创建一个新的数据库并删除同名的现有数据库。")
proceed = input("你确定要继续吗？输入'yes'继续，输入任何其他内容退出。")
if proceed.lower() != 'yes':
    print("退出脚本。")
    exit(0)

# 检查MySQL是否已安装
if subprocess.call('which mysql', shell=True):
    print("MySQL未安装。请先安装MySQL再试。")
    exit(1)

# 从用户处获取MySQL用户名和密码
username = input("请输入你的MySQL用户名: ")
password = getpass.getpass("请输入你的MySQL密码: ")

# 连接到MySQL
try:
    with connect(
        host="localhost",
        user=username,
        password=password,
    ) as connection:
        print("成功连接到MySQL")

        # 创建新数据库
        create_database_query = "CREATE DATABASE xiaoqianbot"
        with connection.cursor() as cursor:
            cursor.execute(create_database_query)

        # 导入.sql文件
        os.system(f'mysql -u {username} -p{password} xiaoqianbot < xiaoqianbot.sql')

        # 创建数据库配置文件
        with open('db_config.py', 'w') as f:
            f.write(f"""# 数据库配置
host="localhost"
user="{username}"
password="{password}"
database="xiaoqianbot"
""")

        print("数据库已成功设置")

except Error as e:
    print(e)
