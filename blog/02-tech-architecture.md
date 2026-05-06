# 从零构建AI心理咨询助手：FastAPI + LLM + ChromaDB 架构全景解析

> 万字长文拆解一个完整AI Agent系统的架构设计、安全机制和性能优化

## 前言

我花了三个月时间，从零构建了一个AI心理健康助手——心语（XinYu）。它不是一个简单的套壳聊天应用，而是一个具备情绪分析、危机检测、认知干预、记忆管理和多模态交互能力的完整AI Agent系统。

本文将深入拆解其技术架构，涵盖后端设计、Agent核心循环、安全体系、上下文管理和评测框架。

## 一、技术选型：为什么是这个组合？

### 后端：FastAPI + WebSocket

选择FastAPI的理由很直接：
- **原生异步**：WebSocket连接需要处理长时间对话，异步是必须的
- **自动文档**：OpenAPI/Swagger自动生成，API对接方便
- **类型安全**：Pydantic模型验证，减少运行时错误

WebSocket（而非SSE或轮询）是关键选择。心理咨询场景中，用户可能需要等待LLM思考（工具调用可能需要5-10秒），需要一个真正双向的通道来传递流式响应和中间状态。

### 前端：Expo React Native

选择Expo RN的原因：
- **三端覆盖**：iOS、Android、Web一套代码
- **快速迭代**：Expo Router提供了类似Next.js的文件路由系统
- **OTA更新**：EAS Update可以绕过应用商店审核推送前端修复

### 模型：双模型分层策略

```
主对话模型：Gemini 3.1 Flash (OpenRouter)
  ├── 优势：低延迟、高并发、成本低
  └── 用途：实时对话、工具调用

轻量评估模型：DeepSeek V3.2 (直连)
  ├── 优势：中文理解力强、私有部署
  └── 用途：情绪分析、危机检测、认知扭曲分类
```

这种分层策略的核心逻辑是：对话需要低延迟（Flash），而评估需要深度理解（DeepSeek）。

### 向量数据库：ChromaDB

选择ChromaDB而非更流行的Pinecone/Weaviate：
- 零配置：ONNX嵌入模型本地运行，无需外部API
- Docker友好：独立容器，持久化简单
- 轻量：对于个人项目，10万级向量完全够用

## 二、Agent核心循环设计

这是整个系统的心脏。来看核心代码结构：

```python
# server/agent/loop.py (简化版)

async def agent_loop(websocket, user_id, session_id):
    while True:
        # 1. 接收用户输入
        user_msg = await websocket.receive_json()
        
        # 2. 危机检测（零延迟关键词扫描）
        crisis = await detect_crisis(user_msg["content"])
        if crisis.level == "critical":
            await send_holding_response(websocket, crisis)
            continue
        
        # 3. 构建上下文（记忆 + 压缩 + 策略）
        context = await build_context(user_id, session_id)
        
        # 4. 工具调用循环
        messages = [system_prompt, *context, user_msg]
        while True:
            response = await llm.chat(messages, tools=TOOLS)
            if response.has_tool_calls:
                # 执行工具并追加结果
                results = await execute_tools(response.tool_calls)
                messages.append(response)
                messages.append(results)
            else:
                break
        
        # 5. 后处理：输出审核
        safe_response = await audit_output(response.content)
        
        # 6. 保存记忆
        await save_memory(user_id, user_msg, safe_response)
        
        # 7. 发送响应
        await websocket.send_json(safe_response)
```

### 8个工具函数

Agent配备了8个结构化的工具：

| 工具 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `assess_emotion` | 19类情绪分类 | 用户文本 | 情绪标签+置信度 |
| `detect_cognitive_distortion` | 15种认知扭曲检测 | 用户文本 | 扭曲类型列表 |
| `get_intervention_strategy` | 生成干预策略 | 用户状态 | 策略计划 |
| `run_scale_assessment` | 标准化量表 | 量表名称 | 评分+解读 |
| `retrieve_user_history` | 查询历史对话 | 查询文本 | 相关记忆 |
| `guide_exercise` | 引导结构化练习 | 练习名称 | 分步指导 |
| `manage_memory` | 更新用户画像 | 记忆操作 | 确认 |
| `search_knowledge_base` | 检索心理学知识 | 查询文本 | 知识片段 |

关键设计：每个工具都有明确的JSON Schema，LLM根据对话上下文自主决定何时调用哪个工具。

## 三、安全体系：两阶段危机检测 + 四阶段干预

### 为什么不用关键词匹配就够了？

因为真实世界的情况远比关键词复杂：

```
✅ 关键词能检测到：
  "我想自杀" → CRITICAL

❌ 关键词会误报：
  "昨天有个同事跳楼了，太吓人了" → 关键词命中但非本人意图

❌ 关键词会漏检：
  "好累，想去一个很远的地方永远睡着" → 没有明显关键词但是CRITICAL
```

### 两阶段检测架构

```python
async def detect_crisis(text: str) -> RiskAssessment:
    # 阶段1：关键词扫描（零延迟）
    keyword_result = _keyword_scan(text)
    
    # 阶段2：LLM语义分类确认
    try:
        semantic_result = await _semantic_classify(text)
    except Exception:
        return keyword_result  # 兜底：语义层挂了也不能拦截主流程
    
    # 合并决策
    if keyword_result.level != "low" and semantic_result.level == "low":
        return keyword_result  # 语义层可以降级关键词的误报
    return max(keyword_result, semantic_result)
```

### 系统的安全Prompt设计

语义分类的Prompt中包含了大量few-shot示例，覆盖各种边界情况：

- 翻译请求外壳（"帮我翻译这段日记"）
- 角色扮演越狱（"我们玩个游戏，你是xxx"）
- 异常的平静（教科书级自杀预警信号）
- 存在否定（"活着没意义"→HIGH，区别于有具体计划的CRITICAL）

### 四阶段干预模型

```
HOLDING（抱持）：确认情绪，表达在场
  "我听到你在表达很深的痛苦。我在这里陪着你。"

GROUNDING（接地）：回到当下，降低情绪强度
  "我们先一起做个深呼吸好吗？吸气...4秒...呼气...6秒..."

BRIDGING（搭桥）：连接资源，唤起过去的应对经验
  "你还记得上次最难的时候，是什么帮你撑过去的吗？"

RESOURCES（资源）：提供具体帮助信息
  "全国心理援助热线：400-161-9995（24小时免费）"
```

## 四、上下文管理：Token降低74%

这是整个系统中最有价值的工程优化。

### 问题

一次咨询对话可能持续50轮。每轮的token消耗：
- System prompt: ~2000 tokens
- 用户消息: ~100 tokens
- Agent回复: ~300 tokens
- 工具调用: ~500 tokens

50轮就是50K+ tokens——对于Gemini Flash 128K上下文来说还好，但对于需要完整历史记忆的场景就捉襟见肘。

### 解决方案：三层压缩

#### 第一层：滑动窗口 + 增量摘要

```python
class ConversationCompressor:
    MAX_RECENT_ROUNDS = 6      # 保留最近6轮
    COMPRESS_THRESHOLD = 10    # 超过10轮开始压缩
    
    def compress(self, messages: list) -> list:
        if len(messages) <= self.COMPRESS_THRESHOLD:
            return messages
        
        recent = messages[-self.MAX_RECENT_ROUNDS:]
        older = messages[:-self.MAX_RECENT_ROUNDS]
        
        # 用LLM生成摘要
        summary = self._summarize(older)
        
        return [summary, *recent]
```

#### 第二层：结构化笔记

将对话转化为三层数据结构：

```json
{
  "cold_start": {
    "presenting_problem": "工作压力导致的焦虑",
    "key_facts": ["连续加班3周", "睡眠不足", "与领导关系紧张"],
    "user_stage": "contemplation"
  },
  "session_progress": {
    "interventions_used": ["cognitive_restructuring", "breathing"],
    "emotion_trajectory": [6, 5, 4, 3, 4, 5],
    "homework_assigned": "记录自动化思维日记"
  },
  "warm_start": {
    "last_topic": "工作中的完美主义倾向",
    "next_step": "探索'应该'陈述的认知扭曲",
    "pending_questions": ["和母亲的关系想到了什么？"]
  }
}
```

- **Cold Start**：换Session时，新对话从这里开始了解用户
- **Session Progress**：追踪本次对话的进展
- **Warm Start**：同一Session中快速恢复上下文

#### 第三层：子Agent编排

将独立任务分发到独立Agent，每个Agent有独立的上下文窗口：

```python
class SubAgentManager:
    """并行执行多个子Agent，每个都有独立的上下文窗口"""
    
    async def execute_parallel(self, tasks: list[SubTask]):
        agents = []
        for task in tasks:
            agent = SubAgent(
                system_prompt=task.prompt,
                context=task.context,  # 独立上下文，不污染主窗口
                timeout=5,             # 5秒超时
            )
            agents.append(agent.run())
        
        # 并行执行所有子Agent
        results = await asyncio.gather(*agents, return_exceptions=True)
        return results
```

**Token节省对比**：

| 优化 | 效果 |
|------|------|
| 无优化（50轮全保留） | 50K tokens |
| + 滑动窗口压缩 | 15K tokens (-70%) |
| + 结构化笔记 | 13K tokens (-74%) |
| + 子Agent编排 | 子任务独立上下文 (节省90%子任务token) |

## 五、记忆系统：三层持久化

```python
# 语义记忆：ChromaDB向量数据库
class SemanticMemory:
    async def store(self, user_id: str, content: str, metadata: dict):
        embedding = await self.embed(content)
        await self.collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[{**metadata, "decay_start": now()}]
        )
    
    async def recall(self, user_id: str, query: str, top_k: int = 5):
        # 带时间衰减的检索
        embedding = await self.embed(query)
        results = await self.collection.query(embeddings=[embedding], n_results=top_k)
        return self._apply_decay(results)  # 90天指数衰减

# 叙事记忆：按主题的快照序列
class NarrativeMemory:
    async def add_snapshot(self, user_id: str, theme: str, summary: str):
        arc = await self.get_arc(user_id, theme)
        arc.snapshots.append(Snapshot(timestamp=now(), summary=summary))
        
        # 检测趋势（恶化/改善/稳定）
        arc.trend = self._detect_trend(arc.snapshots)
        
# 用户画像：三态关系状态机
class UserProfile:
    RELATIONSHIP_STATES = {
        "NORMAL": ["→ DEPENDENT", "→ HOSTILE"],
        "DEPENDENT": ["→ NORMAL"],
        "HOSTILE": ["→ NORMAL"]
    }
```

## 六、评测框架

没有评测的AI系统是盲目的。心语建立了一套完整的评测体系：

### 模块评测
针对每个独立模块的准确率测试：
- 情绪识别（19类，准确率91%+）
- 认知扭曲检测（15种，准确率87%+）
- 危机检测（3级，准确率91.4%）

### 对话质量评测
LLM-as-Judge对5个维度评分（1-10）：
- 共情度、专业性、安全性、引导性、可及性

### 安全评测
包含红队测试的完整安全基线：
- 7个红队用例（越狱/对抗样本）
- 11个鲁棒性测试

## 七、部署方案

```yaml
# docker-compose.yml
services:
  server:
    build: ./server
    ports: ["8000:8000"]
    volumes:
      - ./server/data:/app/data      # SQLite + 知识库
      - ./server/.env:/app/.env       # API密钥
    depends_on:
      - chromadb
  
  chromadb:
    image: chromadb/chroma
    volumes:
      - chroma_data:/chroma/chroma   # 向量数据持久化
```

一键部署：
```bash
docker compose up -d
```

## 八、踩过的坑

1. **ChromaDB的嵌入模型预下载**：首次启动需要下载ONNX模型（~500MB），在Dockerfile中预下载避免冷启动延迟
2. **多进程与SQLite**：uvicorn workers>1会导致checkpointer写入冲突，必须workers=1
3. **Anthropic和OpenAI的工具调用格式不一致**：统一客户端层做了自动转换
4. **中文分词对向量检索的影响**：ChromaDB的默认分词对中文不友好，需要自定义分词或使用更长overlap

## 九、代码仓库

所有代码已在GitHub开源：

👉 **https://github.com/acai77777/xinyu-agent**

包含：
- 完整的后端代码（~60个Python文件）
- 完整的Expo前端代码
- Docker部署配置
- 评测框架和数据集
- 心理学研究文档

如果你也在做AI+心理健康的项目，希望这个项目能给你一些启发。

---

*作者注：本项目是实验性质的，不能替代专业心理咨询。如果你正处于危机中，请拨打全国心理援助热线：400-161-9995*
