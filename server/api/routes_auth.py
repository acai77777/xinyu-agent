"""
用户认证路由——JWT 注册 / 登录 / 令牌验证
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
from jose import jwt, JWTError

from config import settings
from db import get_db

router = APIRouter()

# Bearer token 提取
security = HTTPBearer()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# === 请求/响应模型 ===

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str


# === JWT 工具函数 ===

def _create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> str:
    """解码 JWT，返回 user_id。无效则抛 HTTPException。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效令牌")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="令牌已过期或无效")


# === 依赖注入：获取当前用户 ===

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    从 Authorization header 提取 JWT 并验证。
    返回 user_id，供其他路由使用。
    """
    return _decode_token(credentials.credentials)


# === 路由 ===

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """注册新用户"""
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6个字符")

    db = await get_db()
    try:
        # 检查用户名是否已存在
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE username = ?", (req.username,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="用户名已存在")

        user_id = uuid.uuid4().hex
        password_hash = _hash_password(req.password)
        display_name = req.display_name or req.username

        await db.execute(
            "INSERT INTO users (user_id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
            (user_id, req.username, password_hash, display_name),
        )
        await db.commit()

        token = _create_token(user_id)
        return TokenResponse(
            access_token=token,
            user_id=user_id,
            display_name=display_name,
        )
    finally:
        await db.close()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """用户登录"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT user_id, password_hash, display_name FROM users WHERE username = ?",
            (req.username,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        user_id, password_hash, display_name = row
        if not _verify_password(req.password, password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = _create_token(user_id)
        return TokenResponse(
            access_token=token,
            user_id=user_id,
            display_name=display_name or req.username,
        )
    finally:
        await db.close()


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    """获取当前用户信息"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT username, display_name, created_at FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {
            "user_id": user_id,
            "username": row[0],
            "display_name": row[1],
            "created_at": row[2],
        }
    finally:
        await db.close()
