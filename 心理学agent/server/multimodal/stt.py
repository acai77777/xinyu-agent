"""
语音转文字——Whisper API
心理咨询场景中，语音比文字更能传递情绪（语调、停顿、哽咽）
Phase 4 先用 API，Phase 5 评估本地 Whisper 模型
"""
import httpx
from config import settings


async def transcribe(audio_path: str) -> str:
    """
    将音频文件转为文字

    参数：audio_path 可以是本地路径或上传后的临时路径
    返回：转写文本

    权衡：
    - Whisper large-v3 准确率最高，但 API 成本 $0.006/min
    - 心理对话通常单条语音 < 60s，成本可控
    - 中文识别准确率 > 95%，满足需求
    """
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": ("audio.m4a", f, "audio/m4a")},
                data={
                    "model": "whisper-1",
                    "language": "zh",
                    "response_format": "verbose_json",
                },
            )
    result = response.json()
    return result.get("text", "")


async def transcribe_with_emotion_hints(audio_path: str) -> dict:
    """
    增强版转写——提取语音情绪线索

    Whisper verbose_json 返回 segments 包含：
    - no_speech_prob：静默概率（高值可能表示犹豫、哽咽）
    - avg_logprob：识别置信度（低值可能表示含糊不清、哭泣）

    这些信号可以辅助情绪评估，但不作为主要依据
    """
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": ("audio.m4a", f, "audio/m4a")},
                data={
                    "model": "whisper-1",
                    "language": "zh",
                    "response_format": "verbose_json",
                },
            )
    result = response.json()

    # 提取语音情绪线索
    segments = result.get("segments", [])
    long_pauses = sum(1 for s in segments if s.get("no_speech_prob", 0) > 0.5)
    low_confidence = sum(1 for s in segments if s.get("avg_logprob", 0) < -0.8)

    emotion_hints = []
    if long_pauses > 2:
        emotion_hints.append("语音中有较多停顿，用户可能在犹豫或情绪波动")
    if low_confidence > 1:
        emotion_hints.append("部分语音识别置信度低，用户可能在哭泣或声音颤抖")

    return {
        "text": result.get("text", ""),
        "emotion_hints": emotion_hints,
        "duration_seconds": result.get("duration", 0),
    }
