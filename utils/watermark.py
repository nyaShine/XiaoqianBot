import base64
import os

from PIL import Image, ImageDraw, ImageFont


class Watermark:
    def __init__(self):
        self.font_path = os.path.join("resource", "fonts", "SourceHanSansCN-Regular.otf")
        self.font = ImageFont.truetype(self.font_path, 30)

    def add_watermark_to_image(self, image_path, watermark_text, dense=False):
        watermark_text_encoded = base64.b64encode(watermark_text.encode()).decode()  # 将水印文本编码为base64

        image_dir, image_name = os.path.split(image_path)
        new_image_name = f"{image_name.split('.')[0]}_{('dense_' if dense else '')}watermarked_{watermark_text_encoded}.jpg"
        new_image_path = os.path.join(image_dir, new_image_name)

        # 如果已经存在加水印的图片，直接返回其路径
        if os.path.exists(new_image_path):
            return new_image_path

        img = Image.open(image_path).convert('RGBA')
        width, height = img.size

        # 设置最小间距
        min_distance = 125

        if dense:
            text_width, text_height = self.font.getsize(watermark_text)

            # 创建一个旋转45度的水印文本图像
            txt_img = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((0, 0), watermark_text, font=self.font, fill=(128, 128, 128, 128))
            txt_img = txt_img.rotate(45, expand=True)

            # 计算旋转后的文本图像的尺寸，如果小于最小间距，就使用最小间距
            rotated_width, rotated_height = txt_img.size
            rotated_width = max(rotated_width, min_distance)
            rotated_height = max(rotated_height, min_distance)

            for x in range(-rotated_width, width, rotated_width):
                for y in range(-rotated_height, height, rotated_height):
                    img.paste(txt_img, (x, y), txt_img)
        else:
            draw = ImageDraw.Draw(img)
            text_width, text_height = self.font.getsize(watermark_text)
            x = width - text_width - 10
            y = height - text_height - 10

            # 绘制黑色边框
            border_color = (0, 0, 0)
            for i in range(-2, 3):
                for j in range(-2, 3):
                    draw.text((x + i, y + j), watermark_text, font=self.font, fill=border_color)

            # 绘制白色字体
            text_color = (255, 255, 255)
            draw.text((x, y), watermark_text, font=self.font, fill=text_color)

        # 保存图片到一个新的文件
        img.convert('RGB').save(new_image_path)  # 将图片模式转换为'RGB'并保存

        return new_image_path


watermark = Watermark()
