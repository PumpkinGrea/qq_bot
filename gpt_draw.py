# GPT 生图模块
# 调用中转站的图片生成接口（OpenAI 兼容格式）：文字描述 → 生成图 → 下载转 base64 → CQ码。
# key 从 config_secret.py 读取（该文件已被 .gitignore 忽略，不入库）。
import requests
import base64
import time
import threading
from io import BytesIO
from PIL import Image

try:
    from config_secret import DRAW_API_KEY
except ImportError:
    DRAW_API_KEY = ""

# ===================== 配置区 =====================
DRAW_BASE_URL = "https://www.right.codes/draw"
DRAW_MODEL = "gpt-image-2"
DRAW_SIZE = "1024x1024"
DRAW_TIMEOUT = 120          # 生图较慢，给足超时
DRAW_COOLDOWN = 5           # 两次生图最小间隔（秒），防刷烧钱
# ==================================================

_draw_lock = threading.Lock()
_last_draw_time = [0.0]     # 用列表包装以便在锁内修改


def get_gpt_draw(prompt: str) -> tuple[str | None, str | None]:
    """
    根据文字描述生成图片。
    返回 (CQ码, 错误提示)：成功时 (cq, None)，失败时 (None, 提示文案)。
    """
    if not prompt or not prompt.strip():
        return None, "要画什么呀？@我 画图 + 描述，比如『画图 一只戴帽子的猫』喵~"

    if not DRAW_API_KEY or DRAW_API_KEY == "在这里填入你的key":
        return None, "画图功能还没配置好key喵，等主人填一下~"

    with _draw_lock:
        # 简单限流：距上次生图太近则拒绝
        elapsed = time.time() - _last_draw_time[0]
        if elapsed < DRAW_COOLDOWN:
            return None, f"画得太快啦，{DRAW_COOLDOWN - int(elapsed)}秒后再来喵~"
        _last_draw_time[0] = time.time()

    url = f"{DRAW_BASE_URL}/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {DRAW_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": DRAW_MODEL,
        "prompt": prompt.strip(),
        "image": [],
        "size": DRAW_SIZE,
        "response_format": "url",
    }

    try:
        resp = requests.post(url, json=data, headers=headers, timeout=DRAW_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()

        img_url = result["data"][0]["url"]

        # 下载生成的图片并转 JPEG base64（与随机图一致，保证 QQ 显示且压缩体积）
        img_resp = requests.get(img_url, timeout=30)
        img_resp.raise_for_status()
        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=90)

        base64_img = base64.b64encode(output_buffer.getvalue()).decode()
        return f"[CQ:image,file=base64://{base64_img}]", None

    except Exception as e:
        print(f"[生图] 失败: {e}")
        return None, "画图失败了喵，可能是太忙或描述有问题，待会再试试~"
