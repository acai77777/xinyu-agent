"""
文字转语音——OpenAI TTS API（主）+ Edge TTS（降级方案）
心理咨询场景对声音的要求：温暖、平稳、不急促
"""
import tempfile
import uuid

import httpx
from config import settings

# 语音选择指南：
# - "nova": 温暖女声，适合共情和安慰场景（推荐默认）
# - "onyx": 沉稳男声，适合引导和教育场景
# - "shimmer": 柔和女声，适合正念和放松引导
DEFAULT_VOICE = "nova"
RELAXATION_VOICE = "shimmer"


async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 0.9,
) -> str:
    """
    文字转语音，返回音频文件路径

    权衡：
    - OpenAI TTS：$15/1M chars，音质最自然
    - Edge TTS：免费，音质尚可，但非官方 API
    - 决策：默认用 OpenAI TTS，API 失败时降级到 Edge TTS
    """
    try:
        return await _openai_tts(text, voice, speed)
    except Exception as e:
        print(f"OpenAI TTS 失败，降级到 Edge TTS: {e}")
        return await _edge_tts_fallback(text)


async def _openai_tts(text: str, voice: str, speed: float) -> str:
    """OpenAI TTS API"""
    tmp_dir = tempfile.gettempdir()
    output_path = f"{tmp_dir}/tts_{uuid.uuid4().hex}.mp3"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "speed": speed,
                "response_format": "mp3",
            },
        )
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path


async def _edge_tts_fallback(text: str) -> str:
    """Edge TTS 免费降级方案"""
    import edge_tts

    tmp_dir = tempfile.gettempdir()
    output_path = f"{tmp_dir}/tts_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(
        text,
        voice="zh-CN-XiaoxiaoNeural",
        rate="-10%",
    )
    await communicate.save(output_path)
    return output_path


def get_voice_for_context(exercise_type: str | None = None) -> str:
    """根据对话场景选择合适的声音"""
    if exercise_type in ("mindful_breathing", "progressive_relaxation"):
        return RELAXATION_VOICE
    return DEFAULT_VOICE
