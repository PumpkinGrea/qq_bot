# 导入异步核心库
import asyncio
# 导入异步WebSocket网络库，用于和NapCat通信
import aiohttp
# 随机数生成模块
import random
# 图片处理逻辑
from pic_handle import get_reply_img
from pic_handle import get_phantom_tank
# 自动检测回复逻辑
from auto_reply import auto_reply
# 导入api调用模块
from ai_module import ai_response


import json
import uuid

# -------------------------- 基础配置区 --------------------------
# 连接NapCat的WebSocket地址，和你NapCat配置保持一致
WS_URL = "ws://127.0.0.1:3001/onebot/v11/ws"

# 打字延迟，防止秒回风控（单位：秒）
REPLY_DELAY = 0.8
# ----------------------------------------------------------------


# ============================
# 【机器人启动后自动发全群公告】
# ============================
async def send_startup_broadcast(ws):
    try:
        print("🔍 正在获取群列表...")
        
        # ✅ 核心修复1：添加唯一 echo 标识（必须！）
        # 用来区分哪个响应对应哪个请求
        request_echo = str(uuid.uuid4())
        
        await ws.send_json({
            "action": "get_group_list",
            "params": {},
            "echo": request_echo  # 必须加这个字段！
        })

        # ✅ 核心修复2：循环接收，直到找到匹配 echo 的响应
        # 忽略所有心跳包、事件消息
        group_data = None
        timeout = 10  # 最多等10秒
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            response = await ws.receive()
            
            # 跳过非文本响应
            if response.type != 1:  # 1 = TEXT
                continue
                
            try:
                data = json.loads(response.data)
                # 检查是否是我们刚才请求的响应
                if data.get("echo") == request_echo:
                    group_data = data
                    break
            except json.JSONDecodeError:
                continue

        if not group_data:
            print("❌ 获取群列表超时，跳过公告发送")
            return

        group_list = group_data.get("data", [])
        
        if not group_list:
            print("⚠️ 未找到任何群聊，跳过公告发送")
            return

        print(f"✅ 成功获取到 {len(group_list)} 个群聊")

        # 2. 公告内容
        broadcast_msg = """📢 机器人已更新重启！
✅ 模型：glm-4.5-air
✅ 新增功能：glm‑4.6v（可分析图片），发送图片即可分析
✅ 支持上下文对话 + 各群独立记忆
💡 使用方法：@机器人 + 文字/图片 即可聊天识图
    发送@机器人 清空对话 重置记忆
    详情请发送"菜单"查询"""

        # 3. 遍历所有群发送公告
        success_count = 0
        fail_count = 0
        
        for group in group_list:
            group_id = group.get("group_id")
            if not group_id:
                continue
                
            try:
                await ws.send_json({
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": broadcast_msg
                    }
                })
                print(f"✅ 已发送公告到群: {group_id}")
                success_count += 1
            except Exception as e:
                print(f"❌ 群 {group_id} 发送失败: {str(e)}")
                fail_count += 1
                
            await asyncio.sleep(0.8)  # 防风控，不要改太小

        print(f"\n🎉 全群公告发送完成！成功: {success_count} 个，失败: {fail_count} 个")

    except Exception as e:
        print(f"❌ 公告发送异常: {str(e)}")
        import traceback
        traceback.print_exc()

def extract_text_from_message(message):
    """
    只提取：纯文本 + 图片URL列表
    返回：(纯文本字符串, 图片url列表)
    """
    # 普通字符串消息
    if isinstance(message, str):
        return message.strip(), []

    # 数组格式消息：遍历只拿 text 和 image
    elif isinstance(message, list):
        text_content = []
        image_urls = []

        for segment in message:
            seg_type = segment.get("type")
            data = segment.get("data", {})

            # 提取文本
            if seg_type == "text":
                text_content.append(data.get("text", ""))
            # 提取图片url
            elif seg_type == "image":
                img_url = data.get("url", "")
                if img_url:
                    image_urls.append(img_url)

        full_text = "".join(text_content).strip()

        # test
        # print(f"【提取结果】文本: {full_text} | 图片URL: {image_urls}")

        return full_text, image_urls

    # 未知格式
    else:
        return "", []


def check_is_at_robot(data):
    """
    工具函数：检测本条群聊消息 是否 艾特了本机器人
    :param data: 完整消息数据包
    :return: True=被艾特  False=没有艾特
    """
    try:
        # 获取当前机器人的QQ账号
        robot_qq = str(data.get("self_id"))
        # 获取消息片段列表（艾特、图片、文字都在这里）
        msg_segments = data.get("message", [])

        # 遍历所有消息片段
        for seg in msg_segments:
            # 判断片段类型是否为【艾特】
            if seg.get("type") == "at":
                # 获取被艾特的QQ号
                target_qq = str(seg.get("data", {}).get("qq", ""))
                # 如果艾特的QQ = 机器人QQ → 命中
                if target_qq == robot_qq:
                    return True
    except Exception:
        # 报错直接判定为未艾特
        pass
    return False


async def connect():
    """
    主连接函数：
    1. 建立和NapCat的长连接
    2. 持续监听QQ推送的所有消息
    """
    # 创建异步网络会话
    session = aiohttp.ClientSession()
    try:
        # 长效连接NapCat的WebSocket服务 + 携带Token认证
        async with session.ws_connect(
            WS_URL,
            headers={"Authorization": "Bearer yds3554647781"}
        ) as ws:
            print("✅ QQ全自动机器人已启动，开始监听消息！")
            # 发布更新公告
            #await send_startup_broadcast(ws)
            # 无限循环：持续等待接收QQ消息
            async for msg in ws:
                # 只处理文本类型的消息数据包
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # 交给消息处理函数
                    await handle_msg(ws, msg.json())
    finally:
        # 程序关闭时，自动关闭网络连接，消除警告
        await session.close()


# ==============================================================================
# ======================== QQ机器人 CQ码 发送格式大全 ==========================
# ==============================================================================
# 说明：
# 1. 直接把下面的内容赋值给 reply_text 即可发送
# 2. 可自由组合：文字 + 表情 + 图片 + 艾特
# 3. 群聊/私聊通用
# ==============================================================================

# ---------------------- 1. QQ官方表情（最常用） ----------------------
# [CQ:face,id=数字]
# 常用ID：
# 106 = 可爱    108 = 笑哭    109 = 呲牙
# 110 = 偷笑    111 = 害羞    112 = 调皮
# 113 = 得意    114 = 吐舌    115 = 闭眼
# 例子：reply_text = "[CQ:face,id=106] 你好喵~"

# ---------------------- 2. 发送本地图片（必须绝对路径） ----------------------
# 路径规则：
# 1. 用 / 不要用 \
# 2. 不能有中文、空格、特殊字符
# 3. 前面加 file:///
# 例子：reply_text = "[CQ:image,file=file:///D:/robot/pic/1.jpg]"

# ---------------------- 3. 发送网络图片 ----------------------
# 直接放图片URL
# 例子：reply_text = "[CQ:image,file=https://xxx.com/123.jpg]"

# ---------------------- 4. 艾特某人（群聊专用） ----------------------
# 例子：reply_text = "[CQ:at,qq=12345678] 你好！"

# ---------------------- 5. 组合消息（最强！） ----------------------
# 表情 + 文字 + 图片
# 例子：reply_text = "[CQ:face,id=106] 看这张图～[CQ:image,file=file:///D:/1.jpg]"

# ---------------------- 6. 发送语音 ----------------------
# 例子：reply_text = "[CQ:record,file=file:///D:/voice/hello.mp3]"

# ---------------------- 7. 发送随机运势（带表情） ----------------------
# num = random.randint(1,100)
# reply_text = f"[CQ:face,id=106] 今日运势：{num}分喵~"

# ==============================================================================

# ====================== ✅ 核心：消息处理函数 ======================
async def handle_msg(ws, data):
    """
    所有QQ消息都会进入这里处理
    你只需要看懂下面的变量，就能写任何回复逻辑
    """
    # 只拦截「普通消息事件」，过滤无关系统通知
    if data.get("post_type") != "message":
        return

    # ====================== ✅ 已经拆好的万能参数（最重要） ======================
    pure_text, img_url_list = extract_text_from_message(data["message"])   # 纯文本+图片url列表 
    sender_qq = data["user_id"]                             # 发送者【QQ号】
    group_qq = data.get("group_id")                         # 群号（私聊=None）
    is_group = group_qq is not None                        # 是否【群聊】
    is_private = not is_group                              # 是否【私聊】
    at_me = check_is_at_robot(data)                        # 群里是否【艾特我】

    # 控制台打印日志（方便调试）
    if is_group:
        print(f"[群聊] 群:{group_qq}  用户:{sender_qq}  内容:{pure_text}  艾特我:{at_me}")
    else:
        print(f"[私聊] 用户:{sender_qq}  内容:{pure_text}")

    # ====================== ✅【万能自定义回复模块】你只改这里！======================
    # 回复内容初始为空
    reply_text = None

    # ==========================================
    # 群聊 自动检测触发回复（非艾特生效）
    # ==========================================
    if is_group and not at_me:
        reply_text = auto_reply(pure_text)

    # ----------------------  群聊特殊回复逻辑（必须艾特才生效） ----------------------

    if is_group and at_me and sender_qq == 3554647781 and pure_text == "说话":
        reply_text = "主人你好喵~"
    elif is_group and at_me and pure_text == "今日运势":
        num = random.randint(1, 100)
        reply_text = "今日运势指数为" + str(num) + "喵~"
    # 新增：艾特机器人 + 发【菜单】，就回复菜单
    elif is_group and at_me and pure_text == "菜单":
        reply_text = """📋 机器人功能菜单
        1. 镜像 → 生成左右对称图片
        2. 幻影坦克 → 黑白背景显示不同图片
        3. 今日运势 → 查看今日运势
        4. AI对话 → 艾特机器人直接聊天，支持上下文，支持发送图片识图
        💡 使用方法：@机器人 + 关键词/内容 + 图片（按需）
        💡 发送「清空对话」可重置当前群AI记忆"""

    # ----------------------  私聊回复逻辑 ----------------------
    # for test
    if is_private:
        if "在吗" in pure_text:
            reply_text = "在的哦～"
        elif "你好" in pure_text:
            reply_text = "你好呀！"

    # ----------------------  图片处理逻辑 ----------------------

    image_reply = None

    if is_group and "镜像" in pure_text and img_url_list:
        print("处理中")
        image_reply = get_reply_img(pure_text, img_url_list)
        # 有图片处理结果，强制让 reply_text 不为空，防止被 return 拦截
        if image_reply:
            reply_text = "镜像图片"

    if "幻影坦克" in pure_text and len(img_url_list) >= 2:
        print("生成幻影坦克中...")
        image_reply = get_phantom_tank(pure_text, img_url_list)
        if image_reply:
            reply_text = "幻影坦克"   

    # ====================== AI 兜底回复（不冲突！） ======================
    if is_group and at_me and reply_text is None and image_reply is None:
        # 有图片就传第一张，支持 glm-4.6v 识图
        img = img_url_list[0] if len(img_url_list) > 0 else None
        reply_text = ai_response(group_qq, pure_text, img)


    # =================================================================================

    # 没有需要回复的内容，直接退出
    if not reply_text:
        return

    # 模拟人工打字延迟
    await asyncio.sleep(REPLY_DELAY)

    # 发送消息
    if is_group:
        # CQ标准艾特格式：自动拼接 @发送者
        at_user = f"[CQ:at,qq={sender_qq}] "

        if image_reply:
            # 图片处理 → 发处理后的图片
            send_content = at_user + image_reply
        else:
            # 没图片 → 正常发文字
            send_content = at_user + reply_text

        # 发送群消息
        await ws.send_json({
            "action": "send_group_msg",
            "params": {"group_id": group_qq, "message": send_content}
        })
        print(f"✅ 群聊已回复并艾特用户：{reply_text}")
    else:
        # 私聊直接发文字，不需要艾特
        await ws.send_json({
            "action": "send_private_msg",
            "params": {"user_id": sender_qq, "message": reply_text}
        })
        print(f"✅ 私聊已回复：{reply_text}")



# 程序入口
if __name__ == "__main__":
    asyncio.run(connect())