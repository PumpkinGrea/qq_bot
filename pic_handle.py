
import requests
from io import BytesIO
from PIL import Image
import base64

# ==============================================
# 消息回复模块：处理文本+图片逻辑 → 返回处理后的图片消息
# 主程序调用：from msg_reply import get_reply_text
# ==============================================
def get_reply_img(pure_text: str, img_url_list: list[str]) -> str | None:
    if not img_url_list:
        return None

    img_url = img_url_list[0]

    try:
        # 1. 下载图片
        response = requests.get(img_url, timeout=10)
        image_data = response.content
        img = Image.open(BytesIO(image_data))
        
        # ======================
        # 核心：支持 GIF 多帧镜像
        # ======================
        if img.format == "GIF" and img.n_frames > 1:
            # ==========================================
            # GIF 动图处理：逐帧镜像 → 合成新动画
            # ==========================================
            frames = []
            durations = []  # 保存每帧延时（动画速度）
            
            for i in range(img.n_frames):
                img.seek(i)  # 切换到第 i 帧
                frame = img.convert("RGBA")  # 保留透明背景
                width, height = frame.size
                
                # 左右镜像（和你原来逻辑一样）
                left_half = frame.crop((0, 0, width // 2, height))
                right_half = left_half.transpose(Image.FLIP_LEFT_RIGHT)
                new_frame = Image.new('RGBA', (width, height))
                new_frame.paste(left_half, (0, 0))
                new_frame.paste(right_half, (width // 2, 0))
                
                frames.append(new_frame)
                durations.append(img.info.get("duration", 100))  # 原动画速度
            
            # 保存 GIF 动图（保留循环+延时）
            output_buffer = BytesIO()
            frames[0].save(
                output_buffer,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,  # 无限循环
                disposal=2
            )
            
        else:
            # ==========================================
            # 静态图片（JPG/PNG）处理（原逻辑）
            # ==========================================
            img = img.convert("RGB")
            width, height = img.size
            left_half = img.crop((0, 0, width // 2, height))
            right_half = left_half.transpose(Image.FLIP_LEFT_RIGHT)
            new_img = Image.new('RGB', (width, height))
            new_img.paste(left_half, (0, 0))
            new_img.paste(right_half, (width // 2, 0))
            
            output_buffer = BytesIO()
            new_img.save(output_buffer, format="JPEG")

        # 2. 生成 CQ 码
        processed_image_data = output_buffer.getvalue()
        base64_img = base64.b64encode(processed_image_data).decode()
        cq_image = f"[CQ:image,file=base64://{base64_img}]"

        return cq_image

    except Exception as e:
        print(f"图片处理失败: {e}")
        return None

# ==============================================
# 优化版幻影坦克图片处理函数（100% 无失效）
# 输入：纯文本 + 图片URL列表（必须至少2张图）
# 效果：白色背景显示第一张图，黑色背景显示第二张图
# 优化：强制灰度区间分离，彻底解决表层比里层暗导致的失效问题
# ==============================================
def get_phantom_tank(pure_text: str, img_url_list: list[str]) -> str | None:
    if len(img_url_list) < 2:
        print("幻影坦克需要至少2张图片！")
        return None

    try:
        # 1. 下载两张图片
        response1 = requests.get(img_url_list[0], timeout=10)
        img1 = Image.open(BytesIO(response1.content)).convert("L")  # 表层（白背景）
        response2 = requests.get(img_url_list[1], timeout=10)
        img2 = Image.open(BytesIO(response2.content)).convert("L")  # 里层（黑背景）

        # 2. 统一尺寸
        width, height = img1.size
        img2 = img2.resize((width, height), Image.Resampling.LANCZOS)

        # ==========================================
        # ✅ 核心优化：强制灰度区间分离
        # ==========================================
        pixels1 = img1.load()
        pixels2 = img2.load()

        for y in range(height):
            for x in range(width):
                # 表层压缩到 128-255（亮区）
                old1 = pixels1[x, y]
                pixels1[x, y] = int(128 + (old1 / 255) * 127)
                
                # 里层压缩到 0-127（暗区）
                old2 = pixels2[x, y]
                pixels2[x, y] = int((old2 / 255) * 127)

        # 3. 幻影坦克核心算法（现在永远不会进入else分支）
        phantom_img = Image.new("RGBA", (width, height))
        phantom_pixels = phantom_img.load()

        for y in range(height):
            for x in range(width):
                light = pixels1[x, y]  # 128-255
                dark = pixels2[x, y]   # 0-127

                # 现在永远满足 light > dark，直接计算
                alpha = 255 - (light - dark)
                alpha = max(alpha, 1)
                rgb = int((dark * 255) / alpha)

                phantom_pixels[x, y] = (rgb, rgb, rgb, alpha)

        # 4. 保存为PNG并生成CQ码
        output_buffer = BytesIO()
        phantom_img.save(output_buffer, format="PNG")
        base64_img = base64.b64encode(output_buffer.getvalue()).decode()
        return f"[CQ:image,file=base64://{base64_img}]"

    except Exception as e:
        print(f"幻影坦克生成失败: {e}")
        return None