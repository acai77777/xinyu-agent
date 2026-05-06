"""
语音转文字——通过 LLM 多模态能力实现
心理咨询场景中，语音比文字更能传递情绪（语调、停顿、哽咽）
使用主模型（Gemini Flash 等）通过 OpenRouter 处理音频输入
"""
import base64
import json
import logging

import httpx

logger = logging.getLogger(__name__)


async def transcribe(audio_source: str) -> str:
    """
    将音频文件转为文字

    参数：audio_source 可以是本地路径或 URL
    返回：转写文本
    """
    result = await transcribe_with_emotion_hints(audio_source)
    return result["text"]


async def transcribe_with_emotion_hints(audio_source: str) -> dict:
    """
    增强版转写——同时提取语音情绪线索

    通过 LLM 多模态能力一次性完成转写+情绪分析：
    - 转写语音内容
    - 从语调、语速、停顿等线索推断情绪状态

    返回：{"text": str, "emotion_hints": list[str], "duration_seconds": 0}
    """
    from llm_client import get_async_client, get_model

    client = get_async_client()
    model = get_model()
    audio_data = await _load_audio(audio_source)

    prompt = (
        "你是一位心理咨询助手的语音分析模块。请完成以下任务：\n\n"
        "1. 将这段音频精确转写为文字\n"
        "2. 从语音特征中分析情绪线索（语调、语速、停顿、颤抖、哽咽等）\n\n"
        "返回严格的 JSON 格式，不要包含其他内容：\n"
        '{"text": "转写的完整文字", "emotion_hints": ["情绪线索1", "情绪线索2"]}\n\n'
        "注意：\n"
        "- text 必须是完整准确的转写\n"
        "- emotion_hints 是字符串数组，每条描述一个观察到的语音情绪特征\n"
        "- 如果没有明显的情绪线索，emotion_hints 返回空数组\n"
        "- 用描述性语言，不要下诊断结论"
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_data["base64"],
                            "format": audio_data["format"],
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw_text = response.choices[0].message.content or ""
        parsed = _parse_json_safe(raw_text)
        return {
            "text": parsed.get("text", ""),
            "emotion_hints": parsed.get("emotion_hints", []),
            "duration_seconds": 0,
        }
    except Exception as e:
        logger.error(f"[STT] LLM transcribe failed: {e}")
        return {"text": "", "emotion_hints": [], "duration_seconds": 0}


async def _load_audio(source: str) -> dict:
    """加载音频并转为 base64"""
    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(source)
            data = resp.content
    else:
        with open(source, "rb") as f:
            data = f.read()

    ext = source.rsplit(".", 1)[-1].lower()
    fmt = {
        "mp3": "mp3",
        "wav": "wav",
        "m4a": "m4a",
        "ogg": "ogg",
        "flac": "flac",
        "webm": "webm",
    }.get(ext, "mp3")

    return {
        "base64": base64.standard_b64encode(data).decode("utf-8"),
        "format": fmt,
    }


def _parse_json_safe(text: str) -> dict:
    """安全解析 JSON，处理 markdown 代码块包裹"""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return {"text": text, "emotion_hints": []}
