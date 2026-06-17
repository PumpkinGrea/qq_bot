import requests
import time
import threading

# ===================== 配置区 =====================
ZHIPU_API_KEY = "sk-0785ff2a4988465d87c7ef5eb4eaf5e4.FJj67FzCANSdYwpP"
CHAT_MODEL = "glm-5.1"
VISION_MODEL = "glm-4.6v"
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

        # 初始化上下文
        if group_id not in chat_memory:
            chat_memory[group_id] = [
                {"role": "system", "content": "你是QQ群智能助手，回答简短、可爱、口语化、不啰嗦"}
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
            "temperature": 0.7
        }

        try:
            resp = requests.post(url, json=data, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            
            # ✅ 关键修复：加上 message 层
            reply = result["choices"][0]["message"]["content"].strip()

            # 只保存文字，不保存图片
            chat_memory[group_id].append({"role": "user", "content": user_msg})
            chat_memory[group_id].append({"role": "assistant", "content": reply})

            return reply

        except Exception as e:
            return f"❌ AI错误：{str(e)}"