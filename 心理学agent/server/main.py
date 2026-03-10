"""
FastAPI 入口——HTTP REST + WebSocket 双协议
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from db import init_db
from api.routes_chat import router as chat_router
from api.routes_auth import router as auth_router
from api.routes_history import router as history_router
from api.routes_multimodal import router as multimodal_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("情感Agent服务启动")
    yield
    print("服务关闭")


app = FastAPI(
    title="情感Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS——允许 Expo 开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST 路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(history_router, prefix="/api/history", tags=["历史"])
app.include_router(multimodal_router, prefix="/api/multimodal", tags=["多模态"])

# WebSocket 路由（聊天核心）
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
