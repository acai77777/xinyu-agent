"""
图片理解——Claude Vision API
应用场景：
1. 用户发送表情/自拍 → 辅助情绪识别
2. 用户发送绘画/涂鸦 → 艺术治疗辅助分析
3. 用户发送截图（聊天记录等）→ 理解上下文
"""
import base64

import httpx


async def analyze_image(
    image_source: str,
    user_context: str = "",
) -> str:
    """
    分析用户发送的图片，返回与情感支持相关的描述

    参数：
    - image_source: 图片路径或 URL
    - user_context: 用户附带的文字说明

    权衡：
    - Claude Vision 与主模型统一，无需额外 API key
    - 图片分析用 Haiku 而非 Sonnet，降低成本
    - 不做面部表情的精确分类（准确率不够），而是提供描述性分析供主模型参考
    """
    import anthropic
    from config import settings

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    image_data = await _load_image(image_source)

    response = await client.messages.create(
        model=settings.light_model,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_data["media_type"],
                        "data": image_data["base64"],
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "你是一位心理咨询助手的视觉分析模块。请分析这张图片，关注以下方面：\n\n"
                        "1. 如果是人物照片：描述可观察到的情绪线索（表情、姿态、环境），但不要做诊断性判断\n"
                        "2. 如果是绘画/涂鸦：描述色彩使用、线条特征、主题，以及可能反映的情绪状态\n"
                        "3. 如果是聊天截图：提取关键对话内容\n"
                        "4. 其他类型：简要描述内容\n\n"
                        f"用户附带说明：{user_context if user_context else '无'}\n\n"
                        "注意：\n"
                        "- 用描述性语言，不要下诊断结论\n"
                        "- 关注情绪相关的视觉线索\n"
                        "- 保持温和、非评判的语气\n"
                        "- 返回简洁的分析（3-5句话）"
                    ),
                },
            ],
        }],
    )
    return response.content[0].text


async def _load_image(source: str) -> dict:
    """加载图片并转为 base64"""
    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(source)
            data = resp.content
            media_type = resp.headers.get("content-type", "image/jpeg")
    else:
        with open(source, "rb") as f:
            data = f.read()
        ext = source.rsplit(".", 1)[-1].lower()
        media_type = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "image/jpeg")

    return {
        "base64": base64.standard_b64encode(data).decode("utf-8"),
        "media_type": media_type,
    }
