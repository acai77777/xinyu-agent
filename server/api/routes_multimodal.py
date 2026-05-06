"""
多模态文件上传 REST API
语音和图片通过 HTTP 上传（大文件不适合走 WebSocket），
上传后返回文件路径，再通过 WebSocket 消息引用
"""
import os
import tempfile
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "agent_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".webm"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload/audio")
async def upload_audio(file: UploadFile = File(...)):
    """上传语音文件，返回文件路径"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(400, f"不支持的音频格式: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件过大（最大 10MB）")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    return {"audio_url": filepath}


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """上传图片文件，返回文件路径"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE:
        raise HTTPException(400, f"不支持的图片格式: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件过大（最大 10MB）")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    return {"image_url": filepath}
