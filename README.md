[![贡献者][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![问题][issues-shield]][issues-url]
[![MIT许可证][license-shield]][license-url]

<br />
<div align="center">
  <h3 align="center"><a href="https://qun.qq.com/qunpro/robot/share?robot_appid=102057268">小千校园助手</a></h3>

  <p align="center">
    提供自动化QQ校园频道管理和消息服务解决方案
    <br />
    <br />
    <a href="https://github.com/nyaShine/XiaoqianBot/issues">报告Bug</a>
    ·
    <a href="https://github.com/nyaShine/XiaoqianBot/issues">请求功能</a>
  </p>
</div>

## 关于项目
QQ频道内测已超过2年，随着校园频道用户数量的增加，频道管理和信息服务的需求也不断增加。为了提高频道管理效率和用户体验，我们[东华大学镜月湖畔](https://pd.qq.com/s/25z4gtfil) QQ 频道运营团队决定开发一款针对 QQ 校园频道的综合服务机器人[小千校园助手](https://qun.qq.com/qunpro/robot/share?robot_appid=102057268)。

我们的愿景是：为 QQ 校园频道提供一种简单快捷的机器人自动化解决方案，以提高用户在频道中的沟通效率和便利性、减少频道管理团队的管理和内容维护的工作量。我们希望通过“小千校园助手”，可以让频道管理员和用户都能从繁琐的频道管理工作中解脱出来，更多地专注于频道的核心活动。

目前，“小千校园助手”已经实现了包括自动回复、信息查询、RSS订阅、邮箱认证、管理 Minecraft 服务器、设置管理、查询身份组、生成随机数、查询频道详情和检查机器人的在线状态等功能。

我们将持续优化“小千校园助手”的功能和性能，以期满足更多的校园频道需求。我们也欢迎更多的开发者和用户加入到我们的项目中，共同打造一个更好的QQ校园频道生态。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

### 构建工具

这个项目主要使用了以下工具：

* [Python](https://www.python.org/)
* [MySQL](https://www.mysql.com/)
* [Redis](https://redis.io/)
* [HTML](https://developer.mozilla.org/zh-CN/docs/Web/HTML)

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 开始使用

这里是一些如何在本地设置项目的说明。

### 前提条件

这是一些使用软件所需的事项以及如何安装它们的说明。
* Python
  1. 下载并安装 [Python](https://www.python.org/downloads/)
  2. 检查Python是否安装成功
     ```sh
     python --version
     ```
* MySQL
  1. 下载并安装 [MySQL](https://dev.mysql.com/downloads/installer/)
  2. 检查MySQL是否安装成功
     ```sh
     mysql --version
     ```
* Redis
  1. 下载并安装 [Redis](https://redis.io/download)
  2. 检查Redis是否安装成功
     ```sh
     redis-server --version
     ```

### 安装

1. 克隆仓库
   ```sh
   git clone https://github.com/nyaShine/XiaoqianBot.git
   ```
2. 从`config.yaml.example`复制到`config.yaml`，并输入你的`appid`，`token`和`bot_owner_id`。
3. 设置环境变量`DB_USER`, `SQL_DB_PASS`, `REDIS_DB_PASS`, `FROM_EMAIL`, `EMAIL_PASSWORD`, `AES_KEY`。
请注意，your_aes_key应为16位字符
在Windows下，你可以使用以下命令来永久设置环境变量：

```cmd
setx DB_USER "your_db_user"
setx SQL_DB_PASS "your_db_password"
setx REDIS_DB_PASS "your_redis_password"
setx FROM_EMAIL "your_email"
setx EMAIL_PASSWORD "your_email_password"
setx AES_KEY "your_aes_key"
```

在Linux下，你可以在`~/.bashrc`或`~/.bash_profile`文件中添加以下行来永久设置环境变量：

```bash
export DB_USER=your_db_user
export SQL_DB_PASS=your_db_password
export REDIS_DB_PASS=your_redis_password
export FROM_EMAIL=your_email
export EMAIL_PASSWORD=your_email_password
export AES_KEY=your_aes_key
```

然后，运行以下命令使更改生效：

```bash
source ~/.bashrc
```

或

```bash
source ~/.bash_profile
```

4. 初始化数据库
运行 `initialize_database.py` 脚本来初始化数据库。
```sh
python initialize_database.py
```

5. 运行项目
在 Windows 上，你可以运行 `run.bat` 文件来启动项目：
```cmd
run.bat
```
在 Linux 或 MacOS 上，你可以运行 `run.sh` 文件来启动项目：
```sh
./run.sh
```

注意：`run.bat`和`run.sh`中不会强制变更已安装的Python库的版本，可能导致依赖版本不兼容问题，你也可以通过以下命令安装项目依赖并运行项目：
```sh
pip install -r requirements.txt
python3 main.py
```

如果出现`ModuleNotFoundError: No module named 'module name'`错误，你可以从`requirements.txt`中找到相应的模块并手动安装，例如，你可以将`~= `改为`==`来安装指定版本的模块：
```sh
pip install module_name==version
```

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 使用

这个项目提供了多种功能，下面是一些实用例子：

### 帮助

查询机器人功能。

```sh
@机器人 /帮助 <功能名称>
```

此命令用于查询机器人的各项功能的使用方法。如果不指定<功能名称>，则返回所有功能的列表。

示例：

1. 查询所有功能：
   ```sh
   @机器人 /帮助
   ```
2. 查询特定功能（如“问”）的使用方法：
   ```sh
   @机器人 /帮助 问
   ```

更多例子，请参考`config/botFeatures.json`。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 路线图

- [ ] 自定义订阅
- [ ] mc server增加基岩版支持

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 许可证

根据MIT许可证分发。有关更多信息，请查看`LICENSE.txt`。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 联系
添加机器人到你的频道-[小千校园助手](https://qun.qq.com/qunpro/robot/share?robot_appid=102057268)

我的官方QQ频道 -[小千校园助手](https://pd.qq.com/s/1c5kb9o9x)

项目链接：[https://github.com/nyaShine/XiaoqianBot](https://github.com/nyaShine/XiaoqianBot)

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 致谢
在创建这个项目的过程中，我使用了以下的开源资源和库，对此表示感谢：
* [botpy](https://github.com/tencent-connect/botpy) - MIT License
* [HuaXiaofangBot](https://github.com/nyaShine/HuaXiaofangBot) - MIT License
* [source-han-sans](https://github.com/adobe-fonts/source-han-sans) - SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template) - MIT License
* 有关更多信息，请查看`licenses`文件夹。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

[contributors-shield]: https://img.shields.io/github/contributors/nyaShine/XiaoqianBot.svg?style=for-the-badge
[contributors-url]: https://github.com/nyaShine/XiaoqianBot/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/nyaShine/XiaoqianBot.svg?style=for-the-badge
[forks-url]: https://github.com/nyaShine/XiaoqianBot/network/members
[stars-shield]: https://img.shields.io/github/stars/nyaShine/XiaoqianBot.svg?style=for-the-badge
[stars-url]: https://github.com/nyaShine/XiaoqianBot/stargazers
[issues-shield]: https://img.shields.io/github/issues/nyaShine/XiaoqianBot.svg?style=for-the-badge
[issues-url]: https://github.com/nyaShine/XiaoqianBot/issues
[license-shield]: https://img.shields.io/github/license/nyaShine/XiaoqianBot.svg?style=for-the-badge
[license-url]: https://github.com/nyaShine/XiaoqianBot/blob/main/LICENSE

## 建议

在`site-packages/botpy/client.py`文件中，为了确保更长的响应时间，建议将默认的超时时间从5秒修改为60秒。具体修改如下：

```python
# 原代码
# timeout: int = 5

# 建议修改为
timeout: int = 60