"""
生成科技风Logo和头像
使用Python PIL生成简约科技风格的PNG图标
"""
from PIL import Image, ImageDraw, ImageFont
import os
import math


def create_tech_logo(size=256):
    """
    创建科技风格Logo
    
    设计元素：
    - 深蓝色渐变背景
    - 发光效果的六边形边框
    - 简约的CT字母标识
    - 科技感的光效
    """
    # 创建透明背景图像
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 中心坐标
    cx, cy = size // 2, size // 2
    
    # 绘制外发光效果
    for i in range(20, 0, -2):
        alpha = int(10 + (20 - i) * 0.5)
        glow_color = (0, 212, 255, alpha)
        draw.ellipse([cx - size//2 + i, cy - size//2 + i, 
                     cx + size//2 - i, cy + size//2 - i], 
                    outline=glow_color, width=1)
    
    # 绘制六边形外框
    hex_size = size // 2 - 20
    hex_points = []
    for i in range(6):
        angle = math.pi / 6 + i * math.pi / 3
        x = cx + hex_size * math.cos(angle)
        y = cy + hex_size * math.sin(angle)
        hex_points.append((x, y))
    
    # 填充六边形背景
    draw.polygon(hex_points, fill=(26, 31, 58, 255))
    
    # 绘制六边形边框
    draw.polygon(hex_points, outline=(0, 212, 255, 255), width=3)
    
    # 绘制内部六边形
    inner_size = hex_size * 0.7
    inner_points = []
    for i in range(6):
        angle = math.pi / 6 + i * math.pi / 3
        x = cx + inner_size * math.cos(angle)
        y = cy + inner_size * math.sin(angle)
        inner_points.append((x, y))
    
    draw.polygon(inner_points, outline=(0, 255, 213, 200), width=2)
    
    # 绘制中心点
    center_size = 8
    draw.ellipse([cx - center_size, cy - center_size, 
                 cx + center_size, cy + center_size], 
                fill=(0, 212, 255, 255))
    
    # 尝试加载字体绘制CT
    try:
        # 尝试加载Orbitron或其他科技感字体
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size=int(size * 0.25))
                break
        
        if font is None:
            font = ImageFont.load_default()
        
        # 绘制CT字母
        text = "CT"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = cx - text_width // 2
        text_y = cy - text_height // 2 - 20
        
        # 文字发光效果
        draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 212, 255, 100))
        draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 212, 255, 180))
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
        
    except Exception as e:
        print(f"字体加载失败: {e}")
        # 备用方案：绘制几何图形
        draw.rectangle([cx - 20, cy - 40, cx + 20, cy + 40], outline=(0, 212, 255, 255), width=3)
    
    # 绘制装饰线条
    line_length = size // 3
    line_width = 2
    line_color = (0, 212, 255, 150)
    
    # 左上到右下的线
    draw.line([cx - line_length, cy - line_length//2, cx - hex_size - 10, cy - hex_size - 10], 
              fill=line_color, width=line_width)
    draw.line([cx + line_length, cy + line_length//2, cx + hex_size + 10, cy + hex_size + 10], 
              fill=line_color, width=line_width)
    
    return img


def create_user_avatar(size=128):
    """
    创建用户头像
    
    设计：
    - 圆形科技感头像
    - 渐变背景
    - 发光边框
    - 首字母
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = size // 2, size // 2
    radius = size // 2 - 4
    
    # 绘制外发光
    for i in range(15, 0, -1):
        alpha = int(5 + (15 - i) * 1)
        draw.ellipse([cx - radius - i, cy - radius - i, 
                     cx + radius + i, cy + radius + i], 
                    outline=(0, 212, 255, alpha), width=1)
    
    # 绘制渐变背景圆
    for i in range(radius, 0, -1):
        ratio = i / radius
        r = int(0 + ratio * 26)
        g = int(212 - ratio * 50)
        b = int(255 - ratio * 50)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(r, g, b, 255))
    
    # 绘制边框
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], 
                outline=(0, 212, 255, 255), width=3)
    
    # 绘制内部边框
    inner_radius = radius - 8
    draw.ellipse([cx - inner_radius, cy - inner_radius, 
                 cx + inner_radius, cy + inner_radius], 
                outline=(0, 255, 213, 150), width=1)
    
    # 尝试加载字体
    try:
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size=int(size * 0.4))
                break
        
        if font is None:
            font = ImageFont.load_default()
        
        # 绘制问号或默认字母
        text = "C"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = cx - text_width // 2
        text_y = cy - text_height // 2
        
        # 发光效果
        draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 212, 255, 150))
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
        
    except Exception as e:
        print(f"字体加载失败: {e}")
    
    return img


def main():
    """主函数：生成并保存Logo"""
    output_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(output_dir, "logo.png")
    avatar_path = os.path.join(output_dir, "avatar.png")
    
    print("=" * 50)
    print("🎨 生成科技风Logo和头像")
    print("=" * 50)
    
    # 生成Logo
    print("\n📦 正在生成Logo...")
    logo = create_tech_logo(512)
    logo.save(logo_path, "PNG")
    print(f"✅ Logo已保存: {logo_path}")
    
    # 生成头像
    print("\n👤 正在生成用户头像...")
    avatar = create_user_avatar(256)
    avatar.save(avatar_path, "PNG")
    print(f"✅ 头像已保存: {avatar_path}")
    
    print("\n" + "=" * 50)
    print("🎉 完成！请在Streamlit Cloud重新部署查看效果")
    print("=" * 50)


if __name__ == "__main__":
    main()
