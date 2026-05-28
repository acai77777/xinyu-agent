# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 协作规则（MAOMAO 个人偏好，必须遵守）

1. 以后都用中文解释
2. 每次回复前都必须使用 MAOMAO 作为称呼
3. 不能写兼容性代码，除非 MAOMAO 主动要求
4. 在编写任何代码前，先描述你的方法并等待批准
5. 如果需求模糊，请在编写代码前提出澄清问题
6. 完成任何代码编写后，列出边缘案例并建议覆盖它们的测试用例
7. 如果任务需要修改超过 3 个文件，先停止并将其拆分成更小的任务
8. 出现 bug 时，先编写能重现该 bug 的测试，再修复直到测试通过
9. 每次我纠正你时，反思你做错了什么，并制定永不再犯的计划
10. 部署方法见 `deploy.md`

## 项目概述

心语 XinYu — 基于 LLM 的 AI 心理健康伴侣，融合 CBT（认知行为疗法）与积极心理学。后端 FastAPI（REST + WebSocket），前端 Expo RN（iOS/Android/Web 同一份代码），LLM 走 OpenRouter（主对话 Gemini Flash + 评估 DeepSeek 双模型）。

## 常用命令

### 本地后端
```bash
cd server
pip install -r requirements.txt
cp .env.example .env   # 填入 OPENROUTER_API_KEY
uvicorn main:app --reload --port 8000
# 健康检查: curl http://localhost:8000/health
# API 文档: http://localhost:8000/docs
```

### 本地前端
```bash
cd app
npm install
npx expo start         # 选 w 走 Web，i/a 走 iOS/Android
```

### 测试
```bash
cd server
python -m pytest tests/                          # 全量
python -m pytest tests/test_safety.py            # 单文件
python -m pytest tests/test_safety.py::test_xxx  # 单用例
python -m pytest -k "crisis" -v                  # 按关键字过滤
```
`tests/conftest.py` 会用 `tempfile` 起独立 SQLite 并设 dummy API key，所以测试不依赖真实 `.env`。

### Docker Compose（生产形态）
```bash
docker compose up -d           # 起 server + chromadb 两个容器
docker compose logs -f server  # 看日志
docker compose build server && docker compose up -d server   # 仅重建后端
```

### 部署到远端服务器
见 `deploy.md`。核心：`scp` 改动文件到 `root@43.138.164.41:/opt/xinyu-agent/`，远端 `docker compose build server && up -d server`。Git 推送的根目录是 `H:\AI` 不是 `H:\AI\心理学agent`。

### 跨会话记忆 e2e
```bash
python tools/e2e_test_cross_session.py           # 验证 ChromaDB 跨会话记忆
python tools/run_server_no_kb.py                 # 无 ChromaDB 也能起服务（启用 NO_KB 路径）
```

## 代码架构

### 后端整体分层（`server/`）

```
api/                  REST + WebSocket 入口
  ├─ routes_chat.py   ←—— WebSocket 主通道，唯一的对话入口
  ├─ routes_auth.py   ←—— JWT 登录/注册
  └─ routes_{history,mood,multimodal}.py

agent/loop.py         主循环：双 Provider 抽象（Anthropic / OpenAI-Compatible），
                      统一返回 {text, tool_calls, stop_reason}；
                      每次调用追加写 data/llm_calls.jsonl 便于排障
agent/tools.py        工具定义 + 执行分发
agent/prompts.py      系统 prompt
agent/session_strategy.py  会话开场策略（冷/暖启动）

safety/               两阶段危机检测：关键词扫描（零延迟）→ LLM 语义确认
  ├─ crisis_detector.py  RiskLevel: SAFE / LOW / MEDIUM / HIGH / CRITICAL
  └─ resources.py        四阶段抱持性环境 HOLDING→GROUNDING→BRIDGING→RESOURCES

assessment/           情绪 19 类 + 认知扭曲 15 种 + 标准化量表（PHQ-9/GAD-7/PERMA/SWLS/GQ-6）
intervention/         CBT（苏格拉底对话、认知重构）+ 积极心理学（感恩、优势）+ 结构化练习

memory/               三层记忆——别混淆
  ├─ semantic.py      ChromaDB 向量库，90 天指数衰减
  ├─ narrative.py     按主题的快照序列 + 趋势检测 + LLM 摘要
  ├─ user_profile.py  3 态状态机：NORMAL / DEPENDENT / HOSTILE
  └─ writer.py        ←—— 写入入口（之前有过"跨会话失忆"bug，所有持久化必须走这里）

context/              对话压缩：>compress_threshold(8) 轮触发，保留最近 N + LLM 摘要
  ├─ compressor.py    主压缩逻辑
  ├─ sub_agents.py    子 Agent 编排（独立上下文窗口）
  ├─ cache.py         LRU 缓存降级
  └─ session_notes.py 结构化笔记

knowledge/            混合检索（关键词 + 向量）
multimodal/           语音（TTS：OpenAI / Edge）+ 图片
evaluation/           评测框架，eval_*.py / eval_report*.html 是产物
config.py             pydantic-settings 单例 settings（环境变量 + 默认值）
db.py                 aiosqlite 异步连接（注意：之前修过 sqlite 线程隔离 bug）
main.py               FastAPI 入口 + lifespan(init_db) + CORS + /uploads 静态
```

### 前端整体分层（`app/`）

- **Expo Router** 文件路由：`app/app/{index,login,chat/[id],history,mood-trend,profile}.tsx`
- **Zustand** 单 store：`stores/chatStore.ts` 管会话列表 + 当前消息流
- **服务层**：`services/{api.ts,websocket.ts,audio.ts}`，WebSocket 是聊天唯一通道，REST 走鉴权/历史/打卡/多模态
- **组件**：`components/ChatBubble.tsx` 等

### 关键数据流（对话）

```
RN 前端 → WS /ws/chat?session_id=... → ConnectionManager
  → agent.loop.run_agent
     ├─ safety.crisis_detector 关键词扫
     ├─ memory 三层注入上下文
     ├─ context.compressor 必要时压缩
     ├─ _llm_chat（流式回调 stream_cb 推 chunk 回 WS）
     ├─ tool_calls → agent.tools.execute_tool
     └─ 输出后审核
  → _save_message 持久化 → WS 推送给前端
```

## 关键约定 / 易踩坑

- **改协议必须所有端一起改**：WebSocket/HTTP/RPC 任何协议字段调整，server + app 必须同时上线，不能服务端先改留尾巴（曾因此踩坑）。
- **清调试 print 时保留三条状态日志**：接收 / 出错 / 送达。全清掉会导致线上失明。
- **流式回调里的异常用 `logger.error(..., exc_info=True)`**，不要静默吞掉。
- **修 bug 先写复现测试**（规则 8）。`tools/repro_*.mjs` 是历史复现脚本，新 bug 也按这个命名放进去。
- **不要提交**：`server/data/agent.db`、`server/data/psyqa_*.json`、`server/.env`、`backstage-data/`（生产快照）。
- **LLM Provider 切换**：通过 `LLM_PROVIDER=anthropic|deepseek|openrouter` 环境变量，`agent/loop.py::_llm_chat` 统一封装，加新 provider 时改这一处即可。
- **对话压缩参数**在 `config.py`：`compress_threshold=8` / `compress_keep_recent=3`（已从 6 降到 3 以减风格污染），调之前先理解为什么。
- **危机消息固定**：含自杀关键词的消息在上下文压缩中永不删除，这是安全红线。
- **测试别 mock 数据库**：`conftest.py` 已配好临时真实 SQLite，集成测试要打真库。
