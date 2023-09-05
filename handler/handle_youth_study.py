import requests
from bs4 import BeautifulSoup
from datetime import datetime

from config import config
from utils.redis_utils import RedisConnection
from utils.send_message_with_log import reply_with_log

now = datetime.now().timestamp()


def update():
    # 尝试从Redis中获取答案
    redis_conn = RedisConnection().get_connection()
    cached_answer = redis_conn.get('youth_study')
    if cached_answer:
        return {'status': True, 'data': cached_answer.decode('utf-8')}

    req = requests.get('https://qcsh.h5yunban.com/youth-learning/cgi-bin/common-api/course/current')
    req.raise_for_status()  # 如果请求失败，这将引发HTTPError
    info = req.json()
    end_time = datetime.strptime(info['result']['endTime'], '%Y-%m-%d %H:%M:%S').timestamp()

    if now < end_time:
        page = requests.get(info['result']['uri'].replace('index.html', 'm.html'))
        soup = BeautifulSoup(page.text, 'html.parser')
        current = soup.select_one('.section0')
        a = []

        while current is not None and current.name == 'div':
            ans = ''
            options = current.select('.option')
            if options:
                w21_element = current.select_one('.w21')
                multiple = w21_element is not None and w21_element.get('data-a')
                for i, e in enumerate(current.select('div[data-a]')):
                    if not multiple or (multiple and e.get('data-c') == '1'):
                        if e.get('data-a') == '1':
                            ans += chr(65 + i)
            a.append(ans)
            current = current.find_next_sibling()

        a = a[2:]  # 修改此行，从索引 2 开始
        content = info['result']['title'].strip()
        card = ','.join(a[:a.index('')])
        exercise = ','.join(a[a.index('') + 1:])
        content += '\n知识卡片：' + card if card else ''
        content += '\n课后习题：' + exercise if exercise else ''
        # 将答案保存到Redis中
        redis_conn = RedisConnection().get_connection()
        ttl = config['youth_study']['success_ttl']  # 成功时的TTL
        redis_conn.setex('youth_study', ttl, content)
        return {'status': True, 'info': info, 'data': content}

    # 如果当前时间大于或等于end_time，则认为没有可用的青年大学习信息
    redis_conn = RedisConnection().get_connection()
    ttl = config['youth_study']['failure_ttl']  # 失败时的TTL
    redis_conn.setex('youth_study', ttl, "当前没有可用的青年大学习信息")
    return {'status': False}


async def handle_youth_study(client, message):
    result = update()
    if result['status']:
        output_text = result['data']
    else:
        output_text = result.get('error', "当前没有可用的青年大学习信息")
    await reply_with_log(message, output_text)  # 发送响应
