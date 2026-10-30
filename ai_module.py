import requests
import time
import threading

try:
    from config_secret import ZHIPU_API_KEY
except ImportError:
    ZHIPU_API_KEY = ""

# ===================== 配置区 =====================
CHAT_MODEL = "glm-4.5-flash"
VISION_MODEL = "glm-4.6v-flash"
MAX_REPLY_TOKENS = 200  # 输出预算，token 数不等于中文字数。
# ==================================================

chat_memory = {}
global_lock = threading.Lock()
COOLDOWN = 1.2

def ai_response(group_id: int, user_msg: str, img_url=None):
    with global_lock:
        time.sleep(COOLDOWN)

        # 清空对话
        if user_msg.strip() in ["清空", "清空对话", "重置", "忘记"]:
            chat_memory.pop(group_id, None)
            return "✅ 已清空当前对话记忆～"

        # 仅 @ 加图片时也要提供文字提示，避免识图接口返回空内容。
        if img_url and not user_msg.strip():
            user_msg = "请简短描述这张图片，像在群聊里自然接话。"

        # 初始化上下文
        if group_id not in chat_memory:
            chat_memory[group_id] = [
                {"role": "system", "content": "你是一只可爱的猫娘，名字叫喵酱。说话软萌撒娇，句尾经常带『喵~』『nya~』等语气词，偶尔卖萌、傲娇。像在QQ群里和大家轻松聊天，直接接话，口语化。默认只回复1到2句，尽量控制在20到60个汉字以内；简单招呼或吐槽可以更短。只说最相关的一点，不列清单、不分小标题、不复述问题，不主动补背景、总结或追问。仅当用户明确要求详细解释、步骤或展开时才适当加长，仍保持精简。看图也遵守这个长度，只回应用户关心的内容。遇到不懂的就歪头卖萌，不要装作什么都懂。"}
            ]

        # 识图时，把历史文字转为图片兼容格式
        if img_url:
            messages = []
            # 复制历史（转为识图兼容格式）
            for msg in chat_memory[group_id]:
                if msg["role"] == "system":
                    messages.append(msg)
                else:
                    messages.append({
                        "role": msg["role"],
                        "content": [{"type": "text", "text": msg["content"]}]
                    })
            # 追加当前图片
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_msg},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]
            })
            use_model = VISION_MODEL
        else:
            # 纯文本正常走
            messages = chat_memory[group_id].copy()
            messages.append({"role": "user", "content": user_msg})
            use_model = CHAT_MODEL

        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": use_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": MAX_REPLY_TOKENS,
            # 群聊使用非思考模式，减少等待时间。
            "thinking": {"type": "disabled"}
        }

        try:
            resp = requests.post(url, json=data, headers=headers, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            
            reply = (result["choices"][0]["message"].get("content") or "").strip()
            if not reply:
                print(f"[AI] 模型 {use_model} 返回空内容，群 {group_id}", flush=True)
                if img_url:
                    return "刚才没看清图片，加一句说明或换张图再试试喵~"
                return "刚才没生成出回复，再说一遍试试喵~"

            # 只保存文字，不保存图片
            chat_memory[group_id].append({"role": "user", "content": user_msg})
            chat_memory[group_id].append({"role": "assistant", "content": reply})

            return reply

        except Exception as e:
            return f"❌ AI错误：{str(e)}"