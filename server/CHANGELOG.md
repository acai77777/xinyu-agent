# Changelog

## 2026-03-16 上下文管理优化——压缩 + 结构化笔记 + 多 Agent 编排

### 背景
Agent 每次 LLM 调用需同时注入 6+ 层上下文（画像、叙事、知识库、策略等），20 轮对话后输入 token 持续膨胀，子任务（情绪评估、知识检索）共享主 Agent 全量上下文造成浪费。

### 1. 对话压缩器（Phase 4a）

**新建**：`server/context/compressor.py`

- **滑动窗口**：保留最近 6 轮原始对话，更早的消息用轻量 LLM 压缩为结构化摘要（<300 字）
- **安全消息钉住**：复用 `crisis_detector.CRISIS_KEYWORDS` 作为单一数据源，含安全关键词的消息永远保留原始内容，不参与压缩
- **增量压缩**：旧摘要 + 新消息 → 合并更新，最多 5 轮后全量重压缩，避免每轮都重新压缩全部历史
- **工具结果压缩**：识别情绪/扭曲/策略等 JSON 结构，提取关键字段，长输出截断
- **摘要持久化**：新建 `conversation_summaries` 表（`db.py`），WebSocket 断连重连后无需重新压缩

**涉及文件**：`context/compressor.py`（新建）、`config.py`（+3 配置项）、`db.py`（+建表）、`api/routes_chat.py`（摘要读写）、`agent/loop.py`（集成）

### 2. 结构化会话笔记（Phase 4b）

**新建**：`server/context/session_notes.py`

- **三层数据结构**：用户层（画像、关系、叙事）、会话层（议题、策略、关键时刻）、实时层（安全等级、情绪、扭曲）
- **冷暖启动切换**：
  - 冷启动（前 2-3 轮，信息不足）：回退到原有 6 层全量注入
  - 暖启动（有议题或老用户 ≥3 轮）：紧凑模式 `to_compact_prompt()`，~200 字替代 ~700 字
- **并行异步加载**：4 个数据源通过 `asyncio.gather` 并行加载，同步 DB 调用用 `asyncio.to_thread` 包装

**涉及文件**：`context/session_notes.py`（新建）、`agent/loop.py`（替代 6 层注入逻辑）

### 3. 多 Agent 编排（Phase 4c）

**新建**：`server/context/sub_agents.py`、`server/context/cache.py`

- **子 Agent 隔离上下文**：分析 Agent 只接收最近 6 轮 + 精简 prompt（~940 tok），知识 Agent 只接收查询 + 候选结果（~170 tok），不再共享主 Agent 全量上下文
- **并行分发**：`SubAgentOrchestrator.dispatch()` 通过 `asyncio.wait(timeout=5s)` 并行执行分析和知识检索
- **超时降级**：LRU 缓存（`SubAgentCache`，按 session 分区，最多 100 个 session），超时/异常时使用上一轮缓存结果
- **触发条件**：分析 Agent 要求消息 ≥5 字符，知识 Agent 要求有明确议题且消息 >8 字符

**涉及文件**：`context/sub_agents.py`（新建）、`context/cache.py`（新建）、`agent/loop.py`（替代 `_background_assess`）

### 4. Token 使用量度量结果（20 轮对话）

| 维度 | 旧方案 | 新方案 | 节省 |
|------|--------|--------|------|
| System Prompt | 3,184 tok | 2,437 tok | **-23%** |
| 对话历史 (40→12 条) | 2,508 tok | 926 tok | **-63%** |
| 单次主调用总计 | 5,692 tok | 3,363 tok | **-41%** |
| 子 Agent 上下文 | 11,384 tok | 1,115 tok | **-90%** |
| **总计（含子任务）** | **17,076 tok** | **4,478 tok** | **-74%** |

### 5. 测试覆盖

**新建**：`server/tests/test_context.py`（54 个用例全部通过）

| 模块 | 用例数 | 覆盖点 |
|------|--------|--------|
| Compressor | 19 | 安全检测/分区/窗口分割/阈值/增量vs全量 |
| ToolResult | 6 | 情绪/扭曲/策略 JSON 提取、截断、透传 |
| SessionNotes | 13 | 冷暖判断 5 种场景、紧凑输出 8 种字段组合 |
| Cache | 6 | get/put/LRU 驱逐/刷新/覆盖 |
| Orchestrator | 7 | analysis/knowledge 触发条件边界值 |
| Readable | 3 | 消息格式转换、截断、非字符串处理 |

### 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建 | `server/context/__init__.py` |
| 新建 | `server/context/compressor.py` |
| 新建 | `server/context/session_notes.py` |
| 新建 | `server/context/sub_agents.py` |
| 新建 | `server/context/cache.py` |
| 新建 | `server/tests/test_context.py` |
| 新建 | `server/tests/measure_tokens.py` |
| 修改 | `server/config.py`（+3 配置项） |
| 修改 | `server/db.py`（+conversation_summaries 表） |
| 修改 | `server/api/routes_chat.py`（摘要读写 + 传参） |
| 修改 | `server/agent/loop.py`（集成三大技术） |

---

## 2026-03-14 多模态流程打通 + 策略生成优化

### 1. 多模态流程打通（图片 + 语音接入主流程）

**之前的问题**：vision/stt 模块代码已实现，但未接入主流程。图片消息只加文本前缀 `[用户发送了一张图片]`，语音消息的情绪线索被丢弃。

**改进**：
- `routes_chat.py`：图片消息调用 `analyze_image()` 获取图片理解结果，语音消息调用 `transcribe_with_emotion_hints()` 获取转写 + 情绪线索
- `loop.py`：`run_agent()` 新增 `multimodal_context` 参数，分析结果注入 `context_hints` → system prompt，LLM 带着视觉/语音线索生成回复

**涉及文件**：`api/routes_chat.py`、`agent/loop.py`

---

### 2. STT 架构改造（Whisper API → OpenRouter LLM）

**之前的问题**：`stt.py` 直接调用 OpenAI Whisper API，需要 `openai_api_key`，而项目实际走的是 OpenRouter（Cloudflare AI Gateway），没有配 OpenAI Key。

**改进**：
- 全部重写 `stt.py`，改为通过 `get_async_client()` + `get_model()` 走 OpenRouter → Gemini Flash
- 音频 base64 编码后以 `input_audio` 格式发给 chat completions
- 一次调用同时完成转写 + 情绪分析（比原来 Whisper 纯转写 + 代码分析 segments 更直接）
- 同时支持本地路径和 URL 输入，签名不变，调用方零改动

**涉及文件**：`multimodal/stt.py`

---

### 3. Vision 模型修正（light_model → 主模型）

**之前的问题**：`vision.py` 用的是 `get_light_model()`（DeepSeek V3），而 DeepSeek V3 不支持视觉输入。

**改进**：改为 `get_model()`，走主模型（Gemini Flash），支持图片理解。

**涉及文件**：`multimodal/vision.py`

---

### 4. 策略生成 Prompt 增加 Few-shot 示例

**之前的问题**：策略生成 prompt 只有格式说明，没有示例，模型输出稳定性不够。

**改进**：加入一个完整的工作压力场景示例（含触发语境 + 标准 JSON 输出），提高模型输出的格式一致性和质量。

**涉及文件**：`agent/session_strategy.py`

---

### 5. 策略生成智能跳过

**之前的问题**：第 1 轮对话结束后硬触发策略生成。如果用户只说了"你好"，模型会硬挤出一个低质量策略，存入 DB 后污染后续 Agent 行为。

**改进**：
- Prompt 加前置规则：对话内容无心理议题时返回 `{"skip": true}`
- 解析逻辑处理 skip 标记：收到就 return None，不存 DB、不发前端
- 触发条件从 `len == 2` 改为每轮检查：无策略才尝试，有了就不再触发
- 闲聊阶段每轮仅消耗一次极轻量 LLM 调用（返回 `{"skip": true}` 很快），一旦用户聊到正事就生成策略，后续零成本

**涉及文件**：`agent/session_strategy.py`、`api/routes_chat.py`

---

### 6. 情绪识别模块适配多 Provider（Anthropic 硬编码 → 统一 LLM 客户端）

**之前的问题**：`emotion.py` 硬编码 `anthropic.Anthropic()` 调用 Haiku 模型，无法使用 OpenRouter/DeepSeek。

**改进**：
- 改为通过 `get_sync_client()` + `get_light_model()` 获取客户端和模型
- 根据 `_is_openai_compatible()` 分支处理 Anthropic 和 OpenAI 兼容格式的请求/响应
- 提取 `_parse_emotion_raw()` 统一解析 JSON 字符串，保留 `_parse_emotion_response()` 兼容旧接口

**涉及文件**：`assessment/emotion.py`

---

### 7. 认知扭曲检测模块适配多 Provider

**之前的问题**：`distortion.py` 的 `_llm_confirm_distortions()` 硬编码 `anthropic.Anthropic()` 调用 Haiku，无法使用 OpenRouter/DeepSeek。

**改进**：
- 改为通过 `get_sync_client()` + `get_light_model()` 获取客户端和模型
- 根据 `_is_openai_compatible()` 分支处理请求/响应格式
- 提取 `_parse_distortion_raw()` 统一解析 JSON 字符串，保留 `_parse_distortion_response()` 兼容旧接口

**涉及文件**：`assessment/distortion.py`

---

### 8. 危机检测模块适配多 Provider

**之前的问题**：`crisis_detector.py` 的 `_semantic_classify()` 硬编码 `anthropic.AsyncAnthropic()` 调用 Haiku，无法使用 OpenRouter/DeepSeek。

**改进**：
- 改为通过 `get_async_client()` + `get_light_model()` 获取客户端和模型
- 根据 `_is_openai_compatible()` 分支调用不同 API 格式
- 新增 `_parse_semantic_response_openai()` 处理 OpenAI 兼容格式响应
- 提取 `_parse_semantic_json()` 统一解析核心 JSON 逻辑

**涉及文件**：`safety/crisis_detector.py`

---

### 9. 叙事记忆模块适配多 Provider

**之前的问题**：`narrative.py` 的情感弧线摘要生成硬编码 `anthropic.AsyncAnthropic()` 调用 Haiku，无法使用 OpenRouter/DeepSeek。

**改进**：
- 改为通过 `get_async_client()` + `get_light_model()` 获取客户端和模型
- 根据 `_is_openai_compatible()` 分支处理请求/响应格式

**涉及文件**：`memory/narrative.py`

---

### 10. LLM Provider 切换至 OpenRouter（Cloudflare AI Gateway）

**之前的问题**：项目默认 Provider 为 `anthropic`，主模型 `claude-sonnet-4`，轻量模型 `claude-haiku-4`，成本较高。

**改进**：
- 默认 Provider 改为 `openrouter`
- 主模型改为 `google/gemini-3.1-flash-lite-preview`（通过 Cloudflare AI Gateway 代理）
- 轻量模型改为 `deepseek/deepseek-v3.2`
- `config.py` 新增 `openrouter_api_key`、`openrouter_base_url` 配置项
