# 随机二次元图片模块
# 方式A（稳妥版）：自己下载图片 → 用 Pillow 统一转 PNG → base64 内嵌 CQ 码发送。
# 不依赖 NapCat 能否访问图源域名；统一转码避免 webp 在部分 QQ 客户端不显示。
import requests
import base64
from io import BytesIO
from PIL import Image

# 图源接口（按顺序尝试，前一个失败自动用下一个兜底）。均为全年龄横版动漫图。
_API_SOURCES = [
    "https://t.alcy.cc/moe",        # 栗次元
    "https://www.dmoe.cc/random.php",  # 樱花二次元
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_acg_pic() -> str | None:
    """获取一张随机二次元图，返回可直接发送的 CQ 码；全部失败返回 None。"""
    for api_url in _API_SOURCES:
        try:
            resp = requests.get(api_url, headers=_HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            # 校验确实拿到的是图片
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type:
                print(f"[随机图] {api_url} 返回非图片: {content_type}")
                continue

            # 统一转 JPEG（兼容 webp/png/gif 等），压缩体积、保证 QQ 正常显示
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            output_buffer = BytesIO()
            img.save(output_buffer, format="JPEG", quality=88)

            base64_img = base64.b64encode(output_buffer.getvalue()).decode()
            return f"[CQ:image,file=base64://{base64_img}]"

        except Exception as e:
            print(f"[随机图] {api_url} 获取失败: {e}")
            continue

    return None
