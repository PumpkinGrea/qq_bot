# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 NapCat (OneBot v11) 的 QQ 群聊机器人。通过 WebSocket 长连接接收 QQ 消息，支持自动回复、AI 对话识图、图片镜像、幻影坦克生成等功能。

## 运行与依赖

```bash
# 安装依赖（项目无 requirements.txt，需手动安装）
pip install aiohttp requests pillow

# 启动机器人（需先启动 NapCat 并监听 ws://127.0.0.1:3001）
python bot_main.py
```

无测试、构建或 lint 配置。调试通过控制台日志（每条消息都会打印群号/用户/内容/是否艾特）。

## 架构

消息流向：NapCat → WebSocket → [bot_main.py](bot_main.py) `connect()` → `handle_msg()` → 各功能模块。

[bot_main.py](bot_main.py) 是唯一入口和总调度。`handle_msg()` 是核心：所有 QQ 消息都进入此函数，按固定优先级顺序匹配回复逻辑，命中后写入 `reply_text`，最后统一发送。理解这个函数的匹配顺序是修改回复行为的关键。

四个功能模块被 `handle_msg()` 调用，各自独立、无共享状态：

- [auto_reply.py](auto_reply.py) `auto_reply()` — 纯文本关键词匹配，群聊**未艾特**时触发。
- [pic_handle.py](pic_handle.py) — 图片处理。`get_reply_img()` 做左右镜像（支持 GIF 逐帧）；`get_phantom_tank()` 做幻影坦克（需 ≥2 张图，强制灰度区间分离避免失效）。返回 CQ 码（base64 内嵌图片）。
- [ai_module.py](ai_module.py) `ai_response()` — 智谱 GLM 兜底回复，仅在群聊**艾特**且无其它命中时调用。文本走 `glm-4.5-air`，带图走视觉模型 `glm-4.6v`。

## 关键约定

- **回复优先级**：`handle_msg()` 中 AI 是兜底，仅当 `reply_text is None and image_reply is None` 且被艾特时才调用。新增功能时注意插入位置，避免被前面的分支拦截或拦截掉 AI。
- **图片功能的 reply_text 占位**：图片处理成功后会强制给 `reply_text` 赋一个占位字符串（如 "镜像图片"），目的是绕过末尾 `if not reply_text: return` 的拦截；实际发送的是 `image_reply`。
- **AI 上下文记忆**：`chat_memory` 是进程内字典，按 `group_id` 隔离，每群独立对话历史。重启即丢失。`global_lock` + `COOLDOWN` 串行化所有 AI 请求做限流。识图请求不写入图片到历史，只存文字。
- **消息解析**：`extract_text_from_message()` 只提取纯文本和图片 URL，忽略其它消息段类型。
- **WebSocket 请求-响应配对**：主动调用 OneBot API（如 `get_group_list`）时需带唯一 `echo` 字段，并循环 `ws.receive()` 直到匹配的 `echo` 返回（跳过心跳和事件包）。见 `send_startup_broadcast()`。
- **防风控**：发送前 `REPLY_DELAY` 延迟，群发公告每条间隔 `asyncio.sleep(0.8)`。

## 配置位置（硬编码）

- NapCat WebSocket 地址与 Token：[bot_main.py](bot_main.py) 顶部 `WS_URL` 及 `connect()` 中的 `Authorization` header。
- 智谱 API Key 与模型名：[ai_module.py](ai_module.py) 顶部配置区。
- 主人 QQ 号：`handle_msg()` 中硬编码（`sender_qq == 3554647781`）。

注意：`guild1.db*` 是数据库文件，但当前代码中未被任何模块引用。
