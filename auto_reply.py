# 自动回复模块：检测到【特定消息】就回复
def auto_reply(pure_text: str) -> str | None:
    reply_text = None

    # 匹配：? ？ 单独出现
    text = pure_text.strip()
    if text == "?" or text == "？":
        reply_text = "就你想表达什么呢喵~"  # 你可以改成任何内容
    elif text == "上号":
        reply_text = "喊别人上号前自己先上号行吗喵~"
    return reply_text