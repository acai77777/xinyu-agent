"""
SQLite 数据库初始化与连接管理
"""
import aiosqlite
import sqlite3
from pathlib import Path

from config import settings


async def init_db():
    """
    创建所有必需的表。在应用启动时调用一次。
    使用 aiosqlite 异步执行，避免阻塞事件循环。
    """
    db_path = settings.sqlite_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # 用户表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 会话表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 消息表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                msg_type TEXT DEFAULT 'text',
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES conversations(session_id)
            )
        """)

        # 用户画像表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 危机抱持状态表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crisis_holding_states (
                user_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL DEFAULT 0,
                current_phase TEXT,
                rounds_in_phase INTEGER DEFAULT 0,
                total_rounds INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 关系状态表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS relationship_states (
                user_id TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'normal',
                daily_usage TEXT DEFAULT '{}',
                hostile_cooldown INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 叙事弧线表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS narrative_arcs (
                arc_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                theme TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                snapshots_json TEXT NOT NULL DEFAULT '[]',
                arc_summary TEXT DEFAULT '',
                trend TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1
            )
        """)

        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接（调用方需要自己关闭）"""
    return await aiosqlite.connect(settings.sqlite_db_path)
