import random
import re

from botpy import logging
from botpy.message import Message

from config import config
from utils.send_message_with_log import reply_with_log, post_dms_from_message_with_log

_log = logging.get_logger()


class DiceRandom:
    def __init__(self):
        self.default_sides = config['dice_random']['default_sides']
        self.max_expression_length = config['dice_random']['max_expression_length']
        self.max_dice_times = config['dice_random']['max_dice_times']
        self.max_dice_sides = config['dice_random']['max_dice_sides']
        self.dice_pattern = re.compile(r"^([\+-]?\s*\d*(d\d+)?\s*([\+-]\s*\d*(d\d+)?\s*)*)$")
        self.command_pattern = re.compile(r"/随机(?:\s+((?:\d*d\d+|[\d+|-])+))?(?:\s+暗骰)?", re.I)

    async def on_command(self, client, message: Message):
        content = message.content
        # 解析输入
        match = self.command_pattern.search(content)
        if match:
            dice_expression = match.group(1) or f"1d{self.default_sides}"
            dice_expression = dice_expression.replace("D", "d")
            is_secret = "暗骰" in content
            dice_expression = dice_expression.replace("暗骰", "").strip()
            if len(dice_expression) > self.max_expression_length:
                await reply_with_log(message, "输入的表达式过长，请重新输入。")
                return
            if '.' in dice_expression:  # 检查是否包含小数点
                await reply_with_log(message, "输入的表达式包含小数，我们不支持小数，请重新输入。")
                return
            if dice_expression.isdigit():
                dice_expression = f"1d{dice_expression}"
            if not self.dice_pattern.match(dice_expression):
                await reply_with_log(message, "输入的表达式无效，请重新输入。")
                return
            result, steps, error_message = self.calculate_dice_expression(dice_expression)
            if error_message:
                await reply_with_log(message, error_message)
                return
            response = f"{steps}={result}"
            if is_secret:
                await post_dms_from_message_with_log(client, message, response)
                await reply_with_log(message, "结果已发送到私信，请注意查收。")
            else:
                await reply_with_log(message, response)
        else:
            await reply_with_log(message, "无法识别的命令，请检查您的输入。")

    def calculate_dice(self, dice_expression):
        if 'd' in dice_expression:
            times, sides = dice_expression.split('d')
            if not times or not sides:  # 如果没有明确的骰子数量或面数，跳过处理
                return None, None, None, "输入的表达式无效，请重新输入。"
            times = int(times)
            sides = int(sides)
            if times > self.max_dice_times:
                return None, None, None, f"骰子数量超过最大限制{self.max_dice_times}。"
            if sides > self.max_dice_sides:
                return None, None, None, f"骰子面数超过最大限制{self.max_dice_sides}。"
            dice_results = random.choices(range(1, sides + 1), k=times)
            dice_results_str = '+'.join(map(str, dice_results))
            return dice_expression, dice_results_str, sum(dice_results), None
        else:
            return None, None, None, "输入的表达式无效，请重新输入。"

    def calculate_dice_expression(self, expression):
        # 计算骰子表达式的结果
        parts = iter(re.split(r"(\+|-)", expression))
        result = 0
        dice_exp = []
        dice_res = []
        is_negative = False
        for part in parts:
            if part.strip() == '':
                continue
            if 'd' in part:
                dice_expression, dice_step, dice_result, error_message = self.calculate_dice(part)
                if error_message:
                    return None, None, error_message
                result += (-1 if is_negative else 1) * dice_result
                dice_exp.append(f"{'-' if is_negative else ''}" + dice_expression)
                dice_res.append(f"{'-' if is_negative else ''}" + f"({dice_step})")
                is_negative = False
            elif part.isdigit():
                number = int(part)
                result += (-1 if is_negative else 1) * number
                dice_exp.append(f"{'-' if is_negative else ''}" + part)
                dice_res.append(f"{'-' if is_negative else ''}" + part)
                is_negative = False
            elif part == '-':
                is_negative = True
            elif part == '+':
                next_part = next(parts)
                if next_part.strip() == '':
                    continue
                if 'd' in next_part:
                    dice_expression, dice_step, dice_result, error_message = self.calculate_dice(next_part)
                    if error_message:
                        return None, None, error_message
                    result += dice_result
                    dice_exp.append('+' + dice_expression)
                    dice_res.append('+' + f"({dice_step})")
                else:
                    number = int(next_part)
                    result += number
                    dice_exp.append('+' + next_part)
                    dice_res.append('+' + next_part)

        dice_exp_str = ''.join(dice_exp)
        dice_res_str = ''.join(dice_res)

        # 如果存在，移除开头的'+'
        if dice_exp_str[0] == '+':
            dice_exp_str = dice_exp_str[1:]
        if dice_res_str[0] == '+':
            dice_res_str = dice_res_str[1:]

        return result, f"{dice_exp_str}={dice_res_str}", None


dice_random = DiceRandom()
