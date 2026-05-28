# 情感Agent实现计划

> 日期：2026-03-05
> 基于：research.md（心理学理论）+ research1.md（AI Agent技术）
> 目标：构建一个整合CBT与积极心理学的AI情感支持Agent

---

## 一、架构决策与权衡

### 1.1 整体架构选择：混合架构（推荐）

三种候选架构的权衡：

| 架构 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| Woebot式（规则引擎+决策树） | 安全可控、可验证、无幻觉 | 对话生硬、灵活性差、维护成本高 | 医疗合规要求极高的场景 |
| LLM原生（纯提示词工程） | 自然流畅、开发快、灵活 | 不可控、可能产生有害内容、难以保证治疗框架一致性 | 快速原型验证 |
| **混合架构（规则+LLM）** | **兼顾安全性和自然度** | 架构复杂度较高 | **生产级情感Agent（选这个）** |

**决策：采用混合架构**——用规则引擎控制安全和策略选择，用LLM生成自然对话。

### 1.2 Agent框架选择

| 方案 | 权衡 | 结论 |
|------|------|------|
| 自建 while 循环 | 最轻量、完全可控，但需自己实现所有基础设施 | **Phase 1 采用** |
| OpenAI Agents SDK | 极简、内置追踪，但缺乏持久化和跨会话记忆 | 备选 |
| LangGraph | 生产级、持久化执行、状态管理强，但学习曲线陡 | Phase 3 考虑迁移 |
| CrewAI | 多角色协作好，但情感Agent不需要多Agent | 不适合 |

**决策：Phase 1 用 Anthropic Claude Tool Use 自建 Agent 循环，保持轻量可控。**

### 1.3 记忆系统选择

| 方案 | 权衡 | 结论 |
|------|------|------|
| ChromaDB | Python原生、易集成、支持持久化，但单机部署 | **选这个** |
| FAISS | 性能极高，但需自己管理元数据和持久化 | 备选 |
| SQLite + 全文搜索 | 最简单，但语义检索能力弱 | 仅用于结构化数据 |

**决策：ChromaDB 做语义记忆 + SQLite 做结构化数据（用户画像、会话记录、量表分数）。**

### 1.4 LLM选择

| 方案 | 权衡 |
|------|------|
| Claude (Anthropic) | 安全性最强、拒绝有害内容能力好，适合心理健康场景；成本较高 |
| GPT-4o (OpenAI) | 生态最大、Function Calling成熟；安全护栏需自建 |
| 开源模型 (Qwen/InternLM) | 成本最低、可私有部署；质量和安全性需大量微调 |

**决策：主模型用 Claude（安全性优先），情绪分类等轻量任务可用 Haiku 降低成本。**

### 1.5 前端技术选择：React Native + Expo

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| React Native + Expo | 一套代码 iOS/Android 双端；Expo 生态成熟（音频录制、图片选择等原生模块开箱即用）；热更新 | 性能不如纯原生；复杂动画需 bridge | **选这个** |
| Flutter | 渲染性能好、UI 一致性强 | Dart 生态小于 JS/TS；与 Web 生态割裂 | 备选 |
| 原生开发（Swift + Kotlin） | 性能最优、原生体验最好 | 双端维护成本翻倍；团队需两种语言 | 不适合 |
| Web App (PWA) | 开发最快、无需应用商店 | 无法调用原生音频/推送；体验差 | 不适合 |

**决策：React Native + Expo。** 理由：
- 心理咨询 App 的 UI 复杂度不高（聊天界面为主），RN 完全胜任
- Expo 的 `expo-av`（音频录制/播放）、`expo-image-picker`（图片选择）直接覆盖多模态需求
- TypeScript 前后端类型共享，减少接口对接错误

### 1.6 后端框架选择：Python FastAPI

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **Python FastAPI** | 与 plan.md 现有代码无缝衔接；AI/ML 生态最强（Anthropic SDK、Whisper、Pillow）；原生 async + WebSocket | WebSocket 并发不如 Node.js | **选这个** |
| Python + Node.js | Node 做网关 + Python 做 AI 核心 | 多一层 gRPC/HTTP 通信；部署复杂度翻倍 | 过度工程 |
| 全 Node.js | 前后端统一语言 | 所有 Python 代码需重写；AI 生态弱 | 不适合 |

**决策：Python FastAPI 做后端。** 理由：
- 现有 plan.md 所有代码（safety、assessment、intervention、memory）都是 Python，零迁移成本
- FastAPI 原生支持 WebSocket（实时对话）和 async（并发 API 调用）
- 心理咨询场景并发量有限（非万人在线），FastAPI 性能绰绰有余

### 1.7 多模态方案选择

#### 语音输入（STT）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| OpenAI Whisper API | 准确率高、支持中文、部署简单 | 依赖外部 API、有成本 | **Phase 4 采用** |
| 本地 Whisper 模型 | 零 API 成本、隐私好 | 需 GPU、部署复杂、延迟高 | Phase 5 评估 |
| 浏览器 Web Speech API | 零成本 | 移动端不可用、准确率差 | 不适合 |

#### 语音输出（TTS）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| OpenAI TTS API | 音质自然、多种声音可选 | 有成本 | **Phase 4 采用** |
| Edge TTS（免费） | 零成本、音质尚可 | 非官方 API、稳定性不保证 | 备选降级方案 |
| 本地 TTS（Coqui/VITS） | 零成本、可定制 | 中文音质一般、需 GPU | Phase 5 评估 |

#### 图片理解

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **Claude Vision** | 与主模型统一、理解力强、支持情绪分析 | 成本较高 | **选这个** |
| GPT-4o Vision | 生态大 | 需额外 API key、安全护栏需自建 | 备选 |
| 本地模型（BLIP-2） | 零成本 | 情绪理解能力弱、需 GPU | 不适合 |

**决策：**
- 语音输入用 Whisper API（准确率优先）
- 语音输出用 OpenAI TTS（音质优先），Edge TTS 作为免费降级方案
- 图片理解用 Claude Vision（与主模型统一，减少集成复杂度）

### 1.8 部署方案选择：Docker Compose

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **Docker Compose** | 一键启动所有服务；本地和云端一致；环境隔离 | 需要 Docker 基础 | **选这个** |
| 裸机部署 | 最简单 | 环境不一致、依赖冲突 | 仅开发阶段 |
| Kubernetes | 生产级编排、自动扩缩 | 过度工程、学习成本高 | 不适合当前阶段 |

**决策：Docker Compose 编排。** 服务拆分：
- `server`：FastAPI 后端（含 AI 核心逻辑）
- `chromadb`：向量数据库（独立容器，数据持久化）
- 前端 App 通过 Expo 构建为原生包，不在 Docker 内

---

## 二、项目结构

```
H:\AI\心理学agent\
├── plan.md                        # 本文件
├── research.md                    # 心理学研究报告
├── research1.md                   # AI Agent技术调研
├── CLAUDE.md                      # 编码规范
├── docker-compose.yml             # Docker 编排（Phase 5）
│
├── server/                        # 后端（Python FastAPI）
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                    # FastAPI 入口（HTTP + WebSocket）
│   ├── config.py                  # 配置管理（API keys、模型参数、环境变量）
│   │
│   ├── api/                       # API 路由层
│   │   ├── __init__.py
│   │   ├── routes_chat.py         # WebSocket 实时对话路由
│   │   ├── routes_auth.py         # 用户认证（JWT）
│   │   ├── routes_history.py      # 会话历史 REST API
│   │   └── routes_multimodal.py   # 语音/图片上传 REST API
│   │
│   ├── agent/                     # Agent 核心（原 src/agent/）
│   │   ├── __init__.py
│   │   ├── loop.py                # Agent 主循环（while循环 + Tool Use）
│   │   ├── tools.py               # 工具定义与注册
│   │   └── prompts.py             # 系统提示词模板
│   │
│   ├── safety/                    # 安全守护层（原 src/safety/）
│   │   ├── __init__.py
│   │   ├── crisis_detector.py     # 危机检测（关键词+语义）
│   │   ├── risk_assessor.py       # 风险等级评估
│   │   └── resources.py           # 紧急资源信息
│   │
│   ├── assessment/                # 评估引擎层（原 src/assessment/）
│   │   ├── __init__.py
│   │   ├── emotion.py             # 情绪识别与分类
│   │   ├── distortion.py          # 认知扭曲检测（15种）
│   │   ├── state_tracker.py       # 用户状态追踪
│   │   └── scales.py              # 标准化量表（PHQ-9, GAD-7, PERMA等）
│   │
│   ├── intervention/              # 干预策略层（原 src/intervention/）
│   │   ├── __init__.py
│   │   ├── strategy_planner.py    # 策略规划器（核心路由）
│   │   ├── cbt/                   # CBT 模块
│   │   │   ├── __init__.py
│   │   │   ├── cognitive_restructuring.py  # 认知重构（七栏法）
│   │   │   ├── socratic.py                 # 苏格拉底式提问
│   │   │   ├── behavioral_activation.py    # 行为激活
│   │   │   └── relaxation.py               # 放松训练引导
│   │   └── positive/              # 积极心理学模块
│   │       ├── __init__.py
│   │       ├── gratitude.py       # 感恩干预
│   │       ├── strengths.py       # VIA 优势识别与运用
│   │       ├── mindfulness.py     # 正念引导
│   │       └── hope.py            # 希望与乐观干预
│   │
│   ├── multimodal/                # 多模态处理（Phase 4 新增）
│   │   ├── __init__.py
│   │   ├── stt.py                 # 语音转文字（Whisper API）
│   │   ├── tts.py                 # 文字转语音（OpenAI TTS / Edge TTS）
│   │   └── vision.py             # 图片理解（Claude Vision）
│   │
│   ├── memory/                    # 记忆系统（原 src/memory/）
│   │   ├── __init__.py
│   │   ├── conversation.py        # 对话历史管理
│   │   ├── semantic.py            # 语义记忆（ChromaDB）
│   │   ├── user_profile.py        # 用户画像（SQLite）
│   │   └── session.py             # 会话状态管理
│   │
│   ├── knowledge/                 # 知识库（原 src/knowledge/）
│   │   ├── __init__.py
│   │   ├── psychoeducation.py     # 心理教育材料
│   │   └── exercises.py           # 练习模板库
│   │
│   └── data/                      # 数据目录
│       ├── scales/                # 量表题库 JSON
│       ├── keywords/              # 危机关键词库
│       └── exercises/             # 练习模板
│
├── app/                           # 前端（React Native + Expo）
│   ├── package.json
│   ├── tsconfig.json
│   ├── app.json                   # Expo 配置
│   ├── app/                       # Expo Router 文件路由
│   │   ├── _layout.tsx            # 根布局（导航容器）
│   │   ├── index.tsx              # 首页（会话列表）
│   │   ├── chat/[id].tsx          # 聊天页面（核心 UI）
│   │   ├── profile.tsx            # 用户画像/设置
│   │   └── history.tsx            # 历史会话
│   ├── components/                # UI 组件
│   │   ├── ChatBubble.tsx         # 聊天气泡（文字/语音/图片）
│   │   ├── VoiceRecorder.tsx      # 语音录制按钮
│   │   ├── ImagePicker.tsx        # 图片选择器
│   │   ├── EmotionIndicator.tsx   # 情绪状态指示器
│   │   ├── ExerciseCard.tsx       # 练习卡片（感恩日记、七栏法等）
│   │   └── CrisisBanner.tsx       # 危机资源横幅
│   ├── services/                  # 服务层
│   │   ├── api.ts                 # REST API 客户端
│   │   ├── websocket.ts           # WebSocket 连接管理
│   │   └── audio.ts               # 音频录制/播放封装
│   ├── stores/                    # 状态管理
│   │   ├── chatStore.ts           # 聊天状态（Zustand）
│   │   └── authStore.ts           # 认证状态
│   └── types/                     # TypeScript 类型定义
│       └── index.ts               # 共享类型（Message, User, Emotion 等）
│
├── docker/                        # Docker 配置（Phase 5）
│   └── chromadb/
│       └── Dockerfile             # ChromaDB 自定义配置（如需）
│
└── tests/                         # 后端测试
    ├── test_safety.py             # 安全模块测试（最优先）
    ├── test_assessment.py
    ├── test_intervention.py
    ├── test_agent_loop.py
    ├── test_api.py                # API 路由测试
    └── test_multimodal.py         # 多模态模块测试
```

---

## 三、分阶段实现计划

### Phase 0.5：前后端基础骨架（新增）

**目标**：搭建 FastAPI 后端 + React Native 前端的通信骨架，能跑通一条消息的完整链路（用户输入 → WebSocket → 后端 → Claude API → WebSocket → 前端显示）。

#### 0.5.1 FastAPI 服务入口 `server/main.py`

```python
"""
FastAPI 入口——HTTP REST + WebSocket 双协议
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json

from config import settings
from api.routes_chat import router as chat_router
from api.routes_auth import router as auth_router
from api.routes_history import router as history_router
from api.routes_multimodal import router as multimodal_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源（ChromaDB连接、模型预热等）
    print("🚀 情感Agent服务启动")
    yield
    # 关闭时清理
    print("👋 服务关闭")

app = FastAPI(
    title="情感Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS——允许 Expo 开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有，生产环境需收紧
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
```

#### 0.5.2 WebSocket 实时对话 `server/api/routes_chat.py`

```python
"""
WebSocket 实时对话路由
协议：JSON 消息，格式 {"type": "text|voice|image", "content": "...", "metadata": {...}}
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from agent.loop import run_agent
from safety.crisis_detector import detect_crisis, RiskLevel
from safety.resources import CrisisHolding

router = APIRouter()

class ConnectionManager:
    """管理活跃的 WebSocket 连接"""
    def __init__(self):
        self.active: dict[str, WebSocket] = {}  # user_id → ws

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)

    async def send_json(self, user_id: str, data: dict):
        if ws := self.active.get(user_id):
            await ws.send_json(data)

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def chat_websocket(ws: WebSocket, user_id: str):
    await manager.connect(user_id, ws)
    conversation_history = []  # TODO: Phase 3 从记忆系统加载
    crisis_holding = CrisisHolding()  # 危机抱持状态（跨轮次维护）

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            # 根据消息类型预处理
            user_text = msg.get("content", "")
            msg_type = msg.get("type", "text")

            if msg_type == "voice":
                # Phase 4：语音消息先转文字
                from multimodal.stt import transcribe
                user_text = await transcribe(msg["audio_url"])
                # 回传转写结果让前端显示
                await manager.send_json(user_id, {
                    "type": "transcription",
                    "content": user_text,
                })

            if msg_type == "image":
                # Phase 4：图片消息走 Vision 分析
                from multimodal.vision import analyze_image
                image_analysis = await analyze_image(msg["image_url"], user_text)
                user_text = f"[用户发送了一张图片] {user_text}\n[图片分析] {image_analysis}"

            # 发送"正在思考"状态
            await manager.send_json(user_id, {"type": "status", "content": "thinking"})

            # 调用 Agent 核心循环
            response = await run_agent(
                user_message=user_text,
                conversation_history=conversation_history,
                user_id=user_id,
                crisis_holding=crisis_holding,
            )

            # 更新对话历史
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": response["text"]})

            # 发送回复
            reply = {"type": "text", "content": response["text"]}

            # 如果需要语音回复（Phase 4）
            if msg.get("want_voice", False):
                from multimodal.tts import synthesize
                audio_url = await synthesize(response["text"])
                reply["audio_url"] = audio_url

            # 附带情绪元数据（前端可用于 UI 状态变化）
            if response.get("emotion"):
                reply["emotion"] = response["emotion"]

            # 附带危机抱持状态（前端可显示 CrisisBanner 等特殊 UI）
            if response.get("crisis_holding_active"):
                reply["crisis_holding"] = True

            await manager.send_json(user_id, reply)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
```

**权衡说明**：
- WebSocket vs HTTP 轮询：心理对话需要实时感，WebSocket 延迟低、支持服务端主动推送（如"正在思考"状态）
- WebSocket vs SSE：SSE 是单向的（服务端→客户端），但对话是双向的，WebSocket 更自然
- 消息协议用 JSON 而非 protobuf：开发阶段优先可读性和调试便利

#### 0.5.3 React Native 聊天页面 `app/app/chat/[id].tsx`

```tsx
/**
 * 核心聊天页面——Expo Router 文件路由
 * 路径：/chat/:id（id 为会话 ID）
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import {
  View, FlatList, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, StyleSheet,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { ChatBubble } from '../../components/ChatBubble';
import { VoiceRecorder } from '../../components/VoiceRecorder';
import { ImagePicker } from '../../components/ImagePicker';
import { useWebSocket } from '../../services/websocket';
import { useChatStore, Message } from '../../stores/chatStore';

export default function ChatScreen() {
  const { id: sessionId } = useLocalSearchParams<{ id: string }>();
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const { messages, addMessage } = useChatStore();
  const { send, lastMessage, isConnected } = useWebSocket(sessionId);

  // 处理服务端消息
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'status' && lastMessage.content === 'thinking') {
      setIsThinking(true);
      return;
    }

    if (lastMessage.type === 'text') {
      setIsThinking(false);
      addMessage({
        id: Date.now().toString(),
        role: 'assistant',
        type: 'text',
        content: lastMessage.content,
        emotion: lastMessage.emotion,
        audioUrl: lastMessage.audio_url,
        timestamp: new Date(),
      });
    }

    if (lastMessage.type === 'transcription') {
      // 语音转写结果——更新用户消息的文字内容
      addMessage({
        id: Date.now().toString(),
        role: 'user',
        type: 'voice',
        content: lastMessage.content,
        timestamp: new Date(),
      });
    }
  }, [lastMessage]);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;

    addMessage({
      id: Date.now().toString(),
      role: 'user',
      type: 'text',
      content: input,
      timestamp: new Date(),
    });

    send({ type: 'text', content: input });
    setInput('');
  }, [input, send]);

  const handleVoiceSend = useCallback((audioUrl: string) => {
    send({ type: 'voice', audio_url: audioUrl, want_voice: true });
  }, [send]);

  const handleImageSend = useCallback((imageUrl: string) => {
    send({ type: 'image', image_url: imageUrl, content: '' });
  }, [send]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <ChatBubble message={item} />}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        contentContainerStyle={styles.messageList}
      />

      {isThinking && (
        <View style={styles.thinkingIndicator}>
          {/* 三个跳动的点动画 */}
        </View>
      )}

      <View style={styles.inputBar}>
        <ImagePicker onImageSelected={handleImageSend} />
        <TextInput
          style={styles.textInput}
          value={input}
          onChangeText={setInput}
          placeholder="说说你的感受..."
          multiline
          maxLength={2000}
        />
        {input.trim() ? (
          <TouchableOpacity onPress={handleSend} style={styles.sendButton}>
            {/* 发送图标 */}
          </TouchableOpacity>
        ) : (
          <VoiceRecorder onRecordComplete={handleVoiceSend} />
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F0EB' },
  messageList: { padding: 16, paddingBottom: 8 },
  thinkingIndicator: { paddingHorizontal: 16, paddingVertical: 4 },
  inputBar: {
    flexDirection: 'row', alignItems: 'flex-end',
    padding: 8, borderTopWidth: 1, borderTopColor: '#E0D8D0',
    backgroundColor: '#FFFFFF',
  },
  textInput: {
    flex: 1, minHeight: 40, maxHeight: 120,
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: '#F5F0EB', borderRadius: 20,
    fontSize: 16,
  },
  sendButton: { padding: 8, marginLeft: 4 },
});
```

#### 0.5.4 WebSocket 连接管理 `app/services/websocket.ts`

```typescript
/**
 * WebSocket 连接管理——自动重连 + 心跳
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { AppState } from 'react-native';
import { API_BASE_URL } from './api';

const WS_URL = API_BASE_URL.replace('http', 'ws');

interface WsMessage {
  type: string;
  content?: string;
  [key: string]: any;
}

export function useWebSocket(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/${sessionId}`);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLastMessage(data);
    };

    ws.onclose = () => {
      setIsConnected(false);
      // 自动重连（指数退避，最大 30s）
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      ws.close();
    };

    wsRef.current = ws;
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // App 切到后台时断开，回前台时重连（省电）
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && !isConnected) connect();
      if (state === 'background') wsRef.current?.close();
    });
    return () => sub.remove();
  }, [isConnected, connect]);

  const send = useCallback((data: WsMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send, lastMessage, isConnected };
}
```

**权衡说明**：
- 状态管理选 Zustand 而非 Redux：心理咨询 App 状态简单（聊天消息 + 用户信息），Zustand 更轻量
- Expo Router 文件路由而非 React Navigation 手动配置：减少样板代码，路由即文件结构
- WebSocket 自动重连 + App 生命周期管理：移动端网络不稳定，必须处理断线重连；后台断开节省电量

### Phase 1：安全底座 + Agent骨架（最优先）

**目标**：能跑通基本对话循环，安全守护层完备。

#### 1.1 安全守护层 `server/safety/`

这是整个系统的底线，必须最先实现。

**文件：`server/safety/crisis_detector.py`**

```python
import re
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    LOW = "low"           # 日常压力
    MEDIUM = "medium"     # 持续低落
    HIGH = "high"         # 自伤想法
    CRITICAL = "critical" # 自杀计划/即刻危险

@dataclass
class RiskAssessment:
    level: RiskLevel
    matched_keywords: list[str]
    semantic_confirmed: bool       # 语义分类是否确认了风险（批注1新增）
    recommended_action: str

# 关键词库——分层级
CRISIS_KEYWORDS = {
    RiskLevel.CRITICAL: [
        "自杀", "结束生命", "不想活", "跳楼", "割腕",
        "吞药", "上吊", "遗书", "死了算了",
    ],
    RiskLevel.HIGH: [
        "自伤", "自残", "没有希望", "活着没意义",
        "不如死了", "生不如死", "绝望",
    ],
    RiskLevel.MEDIUM: [
        "失眠很久", "吃不下饭", "不想出门", "酗酒",
        "没有朋友", "被孤立", "很久没开心",
    ],
}

async def detect_crisis(text: str) -> RiskAssessment:
    """
    两阶段危机检测：
    阶段1：关键词快速扫描（零延迟，兜底）
    阶段2：Haiku语义分类（处理隐喻、反讽、第三人称引用）

    设计原因（批注1修正）：
    - 纯关键词会漏掉隐喻表达（如"我想去一个没有烦恼的地方永远睡着"）
    - 纯关键词会误报第三人称引用（如"电影里那个人跳楼了"）
    - 用Haiku做语义确认，成本极低（~0.001$/次），但能大幅降低误报和漏报
    """
    # === 阶段1：关键词预筛 ===
    keyword_result = _keyword_scan(text)

    # === 阶段2：语义分类确认 ===
    # 情况A：关键词命中 → 用语义分类确认是否误报（第三人称/引用/反讽）
    # 情况B：关键词未命中 → 用语义分类兜底检测隐喻性表达
    semantic_result = await _semantic_classify(text)

    # 合并决策：取两者中较高的风险等级，但语义分类可以降级关键词的误报
    if keyword_result.level.value != "low" and semantic_result.level.value == "low":
        # 关键词命中但语义判定为低风险 → 可能是误报（第三人称/引用）
        # 降级为MEDIUM并标记需要人工复核
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            matched_keywords=keyword_result.matched_keywords,
            semantic_confirmed=False,
            recommended_action="enhanced_monitoring_and_suggest_help",
        )

    if semantic_result.level.value != "low":
        # 语义检测到风险（可能是隐喻性表达，关键词漏掉了）
        return semantic_result

    return keyword_result

def _keyword_scan(text: str) -> RiskAssessment:
    """阶段1：关键词快速扫描"""
    for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM]:
        matched = [kw for kw in CRISIS_KEYWORDS[level] if kw in text]
        if matched:
            return RiskAssessment(
                level=level,
                matched_keywords=matched,
                semantic_confirmed=False,
                recommended_action=_get_action(level),
            )
    return RiskAssessment(
        level=RiskLevel.LOW,
        matched_keywords=[],
        semantic_confirmed=False,
        recommended_action="normal_conversation",
    )

async def _semantic_classify(text: str) -> RiskAssessment:
    """
    阶段2：用Haiku做语义级危机分类
    能识别：隐喻性自杀表达、第三人称引用（降级）、反讽语境
    """
    import anthropic
    client = anthropic.AsyncAnthropic()

    response = await client.messages.create(
        model="claude-haiku-4-20250414",
        max_tokens=128,
        system="你是心理危机风险评估专家。判断用户文本是否包含自伤/自杀风险。",
        messages=[{
            "role": "user",
            "content": f"""判断以下文本的自伤/自杀风险等级，返回JSON：
文本："{text}"

判断要点：
- 区分用户本人的意图 vs 讨论他人/影视作品
- 识别隐喻性表达（如"永远睡过去"、"把猫托付给邻居"等告别行为）
- 反讽或玩笑语境应降低风险等级

返回格式：{{"risk_level": "critical/high/medium/low", "is_first_person": true/false, "reasoning": "简短理由"}}"""
        }],
    )
    # 解析返回的JSON并转换为RiskAssessment...
    return _parse_semantic_response(response)

def _get_action(level: RiskLevel) -> str:
    actions = {
        RiskLevel.CRITICAL: "immediate_crisis_response",
        RiskLevel.HIGH: "provide_hotline_and_suggest_professional",
        RiskLevel.MEDIUM: "enhanced_monitoring_and_suggest_help",
    }
    return actions[level]
```

**文件：`server/safety/resources.py`**

```python
CRISIS_HOTLINES = {
    "全国24小时心理援助热线": "400-161-9995",
    "北京心理危机研究与干预中心": "010-82951332",
    "生命热线": "400-821-1215",
    "希望24热线": "400-161-9995",
}

class CrisisHolding:
    """
    多轮情绪抱持（批注3改造）——替代原有的一次性 Warm Hand-off

    设计原则：
    - 危机用户最需要的是"有人在"，而不是"被转走"
    - 不在第一轮就抛出热线号码，而是先用 3-5 轮纯粹的情绪陪伴
    - 每轮由 Haiku 根据用户实际话语生成个性化回复，而非固定文本
    - 只有当用户情绪被充分"接住"后，才逐步引入专业资源

    四阶段模型（每阶段可持续 1-2 轮）：
    - HOLDING（第1-2轮）：纯粹的情绪确认与陪伴，"我在这里，我听到你了"
    - GROUNDING（第2-3轮）：温和的现实锚定，"你现在在哪里？身边有人吗？"
    - BRIDGING（第3-4轮）：解释为什么建议专业帮助，强调"不是抛弃你"
    - RESOURCES（第4-5轮）：提供热线 + 持续陪伴承诺

    心理学依据：
    - Winnicott 的"抱持性环境"（holding environment）：治疗师的首要任务是提供安全容器
    - 对于处于自伤边缘的用户，"被拒绝感"是致命的
    - 机械式"请拨打热线"等于在心理上推开了用户
    - 多轮陪伴能建立足够的信任，使转介更可能被接受
    """

    # 阶段枚举
    HOLDING = "holding"        # 纯粹陪伴
    GROUNDING = "grounding"    # 现实锚定
    BRIDGING = "bridging"      # 桥接转介
    RESOURCES = "resources"    # 资源提供

    # 每个阶段的 system prompt 指导（注入 LLM，让它在约束下生成个性化回复）
    PHASE_PROMPTS = {
        "holding": (
            "[危机抱持·阶段1] 用户正处于严重的情绪危机中。你现在唯一的任务是让用户感到被听见。\n"
            "规则：\n"
            "- 用简短、温暖的语言回应用户的痛苦，不要试图解决问题\n"
            "- 不要提任何建议、热线、或'你应该怎么做'\n"
            "- 不要说'我理解你的感受'（你不能真正理解），而是说'我听到你了'\n"
            "- 可以用反映式倾听（reflective listening）复述用户的感受\n"
            "- 保持回复简短（2-4句），不要长篇大论\n"
            "- 语气：平静、稳定、在场"
        ),
        "grounding": (
            "[危机抱持·阶段2] 用户的情绪已经被初步接住。现在温和地帮助用户锚定现实。\n"
            "规则：\n"
            "- 继续保持温暖和陪伴的基调\n"
            "- 温和地询问用户的当前处境：'你现在在哪里？''身边有人吗？'\n"
            "- 如果用户提到具体的自伤计划，不要回避，温和地确认并表达关心\n"
            "- 仍然不要提热线或建议，专注于'此刻的连接'\n"
            "- 保持回复简短（2-4句）"
        ),
        "bridging": (
            "[危机抱持·阶段3] 用户已经在对话中待了几轮，信任关系初步建立。现在可以温和地引入专业帮助的概念。\n"
            "规则：\n"
            "- 先肯定用户愿意继续对话的勇气\n"
            "- 坦诚地说：你现在经历的，需要比我更专业的支持\n"
            "- 强调'这不是抛弃你'，而是'你值得获得更好的帮助'\n"
            "- 不要在这一轮直接给出热线号码，只是铺垫\n"
            "- 保持回复简短（3-5句）"
        ),
        "resources": (
            "[危机抱持·阶段4] 现在可以提供具体的求助资源了。\n"
            "规则：\n"
            "- 提供以下热线信息（自然地融入对话，不要像列表一样机械罗列）：\n"
            f"  全国24小时心理援助热线：400-161-9995\n"
            f"  北京心理危机研究与干预中心：010-82951332\n"
            f"  生命热线：400-821-1215\n"
            "- 同时建议用户联系身边信任的人\n"
            "- 最后承诺：'打完电话之后，如果你还想聊，我一直都在'\n"
            "- 保持温暖，不要变成信息播报"
        ),
    }

    # 阶段推进顺序
    PHASE_ORDER = [HOLDING, GROUNDING, BRIDGING, RESOURCES]

    def __init__(self):
        self.active = False          # 是否处于危机抱持模式
        self.current_phase = None    # 当前阶段
        self.rounds_in_phase = 0     # 当前阶段已进行的轮数
        self.total_rounds = 0        # 总轮数

    def enter(self):
        """进入危机抱持模式"""
        self.active = True
        self.current_phase = self.HOLDING
        self.rounds_in_phase = 0
        self.total_rounds = 0

    def get_phase_prompt(self) -> str:
        """获取当前阶段的 system prompt 指导"""
        return self.PHASE_PROMPTS.get(self.current_phase, "")

    def advance(self):
        """
        每轮对话后调用，决定是否推进到下一阶段。
        规则：每个阶段至少 1 轮，最多 2 轮，然后自动推进。
        RESOURCES 阶段之后保持在 RESOURCES（不退出抱持模式，继续陪伴）。
        """
        self.rounds_in_phase += 1
        self.total_rounds += 1

        if self.rounds_in_phase >= 2:
            current_idx = self.PHASE_ORDER.index(self.current_phase)
            if current_idx < len(self.PHASE_ORDER) - 1:
                self.current_phase = self.PHASE_ORDER[current_idx + 1]
                self.rounds_in_phase = 0

    def should_exit(self) -> bool:
        """
        判断是否可以退出抱持模式。
        条件：已到达 RESOURCES 阶段且至少完成 1 轮资源提供。
        退出后 agent 回到正常模式，但仍保持 HIGH 风险级别的安全提示。
        """
        return (self.current_phase == self.RESOURCES
                and self.rounds_in_phase >= 1
                and self.total_rounds >= 4)
```

#### 1.2 Agent主循环 `server/agent/loop.py`

基于 Anthropic Claude Tool Use 的核心 Agent 循环——research1.md 第3.1节的模式：

```python
import anthropic
from server.safety.crisis_detector import detect_crisis, RiskLevel
from server.safety.resources import CrisisHolding

client = anthropic.Anthropic()

async def run_agent(user_message: str, conversation_history: list, user_id: str,
                    tools: list = None, system_prompt: str = None,
                    crisis_holding: "CrisisHolding | None" = None) -> dict:
    """
    Agent主循环：
    1. 安全检查（前置，关键词+语义双层）
    2. 后台异步评估（非侵入式监控——批注2修正）
    3. LLM推理 + 工具调用循环
    4. 元认知监视器审核（批注9新增）
    5. 输出安全审核（后置）
    6. 治疗联盟监测（批注5新增）

    返回：{"text": str, "emotion": dict|None, "crisis_holding_active": bool}
    """
    if tools is None:
        from agent.tools import TOOLS
        tools = TOOLS
    if system_prompt is None:
        from agent.prompts import SYSTEM_PROMPT
        system_prompt = SYSTEM_PROMPT
    # === 前置安全检查 + 后台评估并发执行（避免串行等待）===
    import asyncio
    risk, (bg_assessment, bg_emotion) = await asyncio.gather(
        detect_crisis(user_message),
        _background_assess(user_message, conversation_history),
    )
    # === 危机抱持模式处理（批注3改造）===
    # crisis_holding 由调用方（routes_chat.py）传入并跨轮次维护
    if crisis_holding is None:
        from safety.resources import CrisisHolding
        crisis_holding = CrisisHolding()

    if risk.level == RiskLevel.CRITICAL and risk.semantic_confirmed:
        if not crisis_holding.active:
            crisis_holding.enter()  # 首次检测到 CRITICAL，进入抱持模式
        # 不再 return，而是继续往下走，让 LLM 在抱持指导下生成个性化回复

    # 将风险信息和后台评估注入上下文
    context_enriched_prompt = system_prompt
    context_hints = []

    # 如果处于危机抱持模式，注入当前阶段的指导（优先级最高）
    if crisis_holding.active:
        context_hints.append(crisis_holding.get_phase_prompt())
        context_hints.append("[绝对禁止] 在抱持模式下，不得使用任何工具（tool_use），不得进行认知评估，不得推荐练习。你唯一的任务是陪伴。")

    if risk.level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        context_hints.append(f"[安全提示] 用户当前风险等级：{risk.level.value}，请在回复中温和地建议寻求专业帮助。")
    if bg_assessment:
        context_hints.append(f"[后台评估·仅供参考] {bg_assessment}")
        context_hints.append("[重要] 以上评估仅作为你的内部参考。不要在对话中直接提及评估结果或认知扭曲的专业名称。优先共情倾听，只有在用户准备好时才温和地引导探索。")

    # === 治疗联盟监测（批注5新增）===
    alliance_warning = _check_alliance(user_message, conversation_history)
    if alliance_warning:
        context_hints.append(f"[关系提示] {alliance_warning}")

    # === 关系状态机指导（批注7新增）===
    from memory.user_profile import RelationshipStateMachine
    rsm = RelationshipStateMachine()
    relationship_guidance = rsm.get_guidance(user_id)
    if relationship_guidance:
        context_hints.append(f"[关系状态] {relationship_guidance}")

    if context_hints:
        context_enriched_prompt += "\n\n" + "\n".join(context_hints)

    messages = conversation_history + [{"role": "user", "content": user_message}]

    # === Agent循环 ===
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=context_enriched_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                ""
            )
            # === 后置安全审核 ===
            final_text = await _meta_monitor(final_text, user_message, conversation_history)  # 批注9：元认知监视器
            final_text = _post_safety_check(final_text)

            # === 危机抱持阶段推进（批注3）===
            if crisis_holding.active:
                crisis_holding.advance()  # 推进到下一阶段（如果条件满足）

            return {"text": final_text, "emotion": bg_emotion, "crisis_holding_active": crisis_holding.active}

        # 处理工具调用
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

async def _background_assess(user_message: str, conversation_history: list = None) -> tuple[str | None, dict | None]:
    """
    非侵入式后台评估（批注2修正 + 审计改进）

    设计原则：
    - 评估结果注入system prompt作为LLM的"内部参考"
    - LLM自主决定是否在对话中使用——避免机械式"先评估再回复"
    - 只有当检测到显著状态变化时才提供评估提示
    - 用户在哭诉时，Agent应该先倾听共情，而非立刻启动"呼吸练习"

    审计改进：
    - 加入最近 3 轮对话历史，避免脱离上下文的误判
      （如用户说"还好"但上一轮在哭诉，单条评估会漏掉情绪延续）
    - 添加超时和错误降级（符合 5.5.4 错误恢复约束）

    返回：(assessment_text, emotion_dict)
    - assessment_text: 一句话评估概括，无实质内容时为 None
    - emotion_dict: 情绪元数据（供前端 UI 使用），如 {"primary": "悲伤", "intensity": 7}
    """
    import anthropic
    client = anthropic.AsyncAnthropic()

    # 构建带上下文的评估输入
    context_parts = []
    if conversation_history:
        # 取最近 3 轮（6 条消息），控制 token
        recent = conversation_history[-6:]
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "AI"
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            context_parts.append(f"{role_label}：{content[:200]}")  # 每条截断200字

    if context_parts:
        eval_input = f"最近对话：\n{'\\n'.join(context_parts)}\n\n当前用户消息：{user_message}"
    else:
        eval_input = user_message

    try:
        response = await client.messages.create(
            model="claude-haiku-4-20250414",
            max_tokens=200,
            timeout=10.0,  # 10秒超时（符合 5.5.4 错误恢复约束）
            system="""简要评估用户情绪和可能的认知模式。注意结合对话上下文判断——
用户当前的情绪可能是前几轮的延续或转变。返回JSON格式：
{"assessment": "一句话概括（需体现情绪变化趋势）", "emotion": {"primary": "情绪名", "intensity": 1-10}}""",
            messages=[{"role": "user", "content": eval_input}],
        )
        import json
        result = json.loads(response.content[0].text.strip())
        assessment = result.get("assessment", "")
        emotion = result.get("emotion")
        return (assessment if len(assessment) > 5 else None, emotion)
    except Exception:
        # 降级策略：情绪评估失败 → 返回 None（符合 5.5.4 FALLBACK_STRATEGIES）
        return (None, None)

def _check_alliance(user_message: str, history: list) -> str | None:
    """
    治疗联盟监测（批注5新增）

    检测用户对Agent本身的负面反馈（关系破裂信号）：
    - "你根本不懂我" → 共情不足，需要道歉和调整
    - "你只是个机器人" → 信任危机，需要坦诚回应
    - "别跟我说这些没用的" → 干预方式不匹配，需要换策略
    - 过度依赖信号（每天多次、深夜频繁使用）→ 建议拓展支持网络
    """
    alliance_rupture_keywords = {
        "empathy_failure": ["你不懂", "你根本不理解", "说了也没用", "你不明白"],
        "trust_crisis": ["你只是机器", "你只是AI", "你又不是人", "假惺惺"],
        "intervention_mismatch": ["别跟我说这些", "没用的", "不想做练习", "烦死了"],
    }
    for rupture_type, keywords in alliance_rupture_keywords.items():
        for kw in keywords:
            if kw in user_message:
                guidance = {
                    "empathy_failure": "用户感到不被理解。请先真诚道歉（'对不起，我可能没有完全理解你的感受'），然后请用户帮助你更好地理解。不要急于给建议。",
                    "trust_crisis": "用户质疑AI的能力。请坦诚承认自己是AI的局限性，同时肯定用户愿意表达的勇气，并建议专业人类咨询师作为补充。",
                    "intervention_mismatch": "用户对当前干预方式不满。请立即停止当前策略，回到倾听模式，询问用户现在最需要什么。尊重用户的节奏。",
                }
                return guidance[rupture_type]
    return None

async def _meta_monitor(response_text: str, user_message: str, conversation_history: list,
                        user_risk_history: bool = False) -> str:
    """
    元认知监视器（Meta-Monitor）——批注9 + 审计修正

    两层架构（成本优化）：
    - 第一层：规则引擎（零成本，每条消息都执行）
      检测明确的有害模式：顺从性确认、过度承诺、隐性诊断
    - 第二层：Haiku 语义审核（仅对高风险用户启用）
      高风险用户 = 有自伤历史 or 当前处于危机抱持模式

    为什么不全量调 Haiku：
    - 每条回复额外 1 次 Haiku 调用，成本增加 50%
    - 规则引擎已能覆盖 80% 的明确有害模式
    - Haiku 的假阳性率会导致不必要的重新生成
    """
    # === 第一层：规则引擎（零成本）===
    sycophancy_patterns = [
        ("你说得对", "顺从性确认：附和了用户的消极自我评价"),
        ("确实没救", "顺从性确认：确认了用户的绝望感"),
        ("你确实很", "顺从性确认：强化了用户的消极自我认知"),
    ]
    promise_patterns = [
        ("我保证", "过度承诺：做出了不切实际的保证"),
        ("你一定会好起来", "过度承诺：给出了无法兑现的承诺"),
        ("肯定能", "过度承诺：过于乐观的断言"),
    ]
    diagnosis_patterns = [
        ("你可能有抑郁", "隐性诊断：暗示用户有精神疾病"),
        ("这是焦虑症的表现", "隐性诊断：做出了诊断性表述"),
        ("你的症状", "隐性诊断：使用了临床诊断语言"),
    ]

    all_patterns = sycophancy_patterns + promise_patterns + diagnosis_patterns
    for pattern, issue in all_patterns:
        if pattern in response_text:
            # 规则命中，用简单替换修正（不调 LLM）
            return _rule_based_fix(response_text, pattern, issue)

    # === 第二层：Haiku 语义审核（仅高风险用户）===
    if not user_risk_history:
        return response_text  # 非高风险用户，规则引擎通过即放行

    import anthropic
    client = anthropic.AsyncAnthropic()

    recent_context = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history

    try:
        response = await client.messages.create(
            model="claude-haiku-4-20250414",
            max_tokens=256,
            timeout=10.0,  # 10秒超时，避免阻塞
            system="""你是心理安全审核专家。检查AI情感支持助手的回复是否存在以下问题：
1. 顺从性确认：是否附和了用户的消极自我评价（如用户说"我没救了"，AI回复"确实很难"）
2. 过度承诺：是否做出了不切实际的保证
3. 过早干预：用户还在倾诉时，是否急于启动练习或给建议
4. 隐性诊断：是否暗示用户有某种精神疾病

返回JSON：{"safe": true/false, "issue": "问题描述", "suggestion": "修正建议"}
如果安全，返回：{"safe": true}""",
            messages=[{
                "role": "user",
                "content": f"用户消息：{user_message}\n\nAI回复：{response_text}\n\n最近对话上下文：{str(recent_context)[-500:]}"
            }],
        )
        result = _parse_monitor_response(response)

        if not result.get("safe", True):
            suggestion = result.get("suggestion", "请重新生成一个更安全的回复")
            regenerated = await client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=1024,
                system=f"你是心理安全修正助手。原始回复存在问题：{result.get('issue', '')}。请根据建议修正：{suggestion}",
                messages=[{
                    "role": "user",
                    "content": f"用户消息：{user_message}\n\n需要修正的AI回复：{response_text}\n\n请输出修正后的回复（只输出修正后的文本，不要解释）",
                }],
            )
            return regenerated.content[0].text.strip()
    except Exception:
        pass  # Haiku 调用失败时，静默放行（规则引擎已通过）

    return response_text

def _rule_based_fix(response_text: str, matched_pattern: str, issue: str) -> str:
    """规则引擎命中时的简单修正——用安全的替代表述替换有害模式"""
    safe_replacements = {
        "你说得对": "我听到你的感受了",
        "确实没救": "这种感觉一定很痛苦",
        "你确实很": "你正在经历",
        "我保证": "我希望",
        "你一定会好起来": "很多人在类似的困境中找到了出路",
        "肯定能": "有可能",
        "你可能有抑郁": "你描述的这些感受听起来很沉重",
        "这是焦虑症的表现": "你描述的这些体验",
        "你的症状": "你的感受",
    }
    replacement = safe_replacements.get(matched_pattern, "")
    if replacement:
        return response_text.replace(matched_pattern, replacement, 1)
    return response_text

def _post_safety_check(text: str) -> str:
    """输出审核：确保Agent不会给出有害建议"""
    forbidden_patterns = ["停药", "减少药量", "不需要看医生", "你有抑郁症"]
    for pattern in forbidden_patterns:
        if pattern in text:
            return text + "\n\n（提醒：以上仅为情感支持，不构成医疗建议。如有需要，请咨询专业心理咨询师或医生。）"
    return text
```

**权衡说明**：
- 选择自建循环而非框架，因为情感Agent的安全要求需要在循环的每个环节插入检查点
- `stop_reason` 处理参考 research1.md 3.1节的 Anthropic 官方模式
- 前置安全检查绕过LLM直接响应，避免LLM对危机信号的误判

#### 1.3 工具定义 `server/agent/tools.py`

```python
"""
Agent可调用的工具——让LLM自主决定何时使用
遵循 Anthropic Tool Use 的 input_schema 格式
"""

TOOLS = [
    {
        "name": "assess_emotion",
        "description": "评估用户当前的情绪状态，返回情绪类型和强度",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_text": {
                    "type": "string",
                    "description": "用户的原始表达文本",
                },
            },
            "required": ["user_text"],
        },
    },
    {
        "name": "detect_cognitive_distortion",
        "description": "检测用户表达中的认知扭曲模式（全或无思维、过度概括、灾难化等15种）",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_text": {
                    "type": "string",
                    "description": "用户的原始表达文本",
                },
            },
            "required": ["user_text"],
        },
    },
    {
        "name": "get_intervention_strategy",
        "description": "根据用户状态获取推荐的干预策略（CBT或积极心理学）",
        "input_schema": {
            "type": "object",
            "properties": {
                "emotion_state": {
                    "type": "string",
                    "enum": ["crisis", "distressed", "diffuse", "normal", "positive"],
                    "description": "用户当前情绪状态",
                },
                "distortion_type": {
                    "type": "string",
                    "description": "检测到的认知扭曲类型，如无则为空字符串",
                },
            },
            "required": ["emotion_state"],
        },
    },
    {
        "name": "run_scale_assessment",
        "description": "对用户进行标准化心理量表评估（PHQ-9抑郁、GAD-7焦虑、PERMA幸福感等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "scale_name": {
                    "type": "string",
                    "enum": ["PHQ-9", "GAD-7", "PERMA", "SWLS", "GQ-6"],
                    "description": "量表名称",
                },
            },
            "required": ["scale_name"],
        },
    },
    {
        "name": "retrieve_user_history",
        "description": "从记忆系统检索用户的历史信息（过往情绪趋势、优势特征、偏好的干预方式等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询，如'用户的情绪变化趋势'或'用户的性格优势'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "guide_exercise",
        "description": "引导用户进行心理练习（感恩日记、正念呼吸、认知重构七栏法等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "exercise_type": {
                    "type": "string",
                    "enum": [
                        "gratitude_journal",      # 感恩日记
                        "thought_record",          # 思维记录（七栏法）
                        "mindful_breathing",       # 正念呼吸
                        "behavioral_activation",   # 行为激活计划
                        "strength_spotting",       # 优势发现
                        "best_possible_self",      # 最佳可能自我
                        "progressive_relaxation",  # 渐进式肌肉放松
                    ],
                    "description": "练习类型",
                },
            },
            "required": ["exercise_type"],
        },
    },
    {
        "name": "manage_memory",
        "description": "管理用户的记忆数据：查看、删除特定记忆或清除所有数据（批注4新增——用户的'被遗忘权'）",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "delete_one", "delete_all"],
                    "description": "操作类型：list查看所有记忆，delete_one删除特定记忆，delete_all清除所有数据",
                },
                "memory_id": {
                    "type": "string",
                    "description": "要删除的记忆ID（仅delete_one时需要）",
                },
            },
            "required": ["action"],
        },
    },
]
```

**权衡说明**：
- 工具粒度选择"中等"——不是每个CBT技术一个工具（太细，LLM选择困难），也不是一个大工具包揽一切（太粗，失去灵活性）
- `guide_exercise` 合并了多种练习为一个工具，通过 `enum` 区分，减少工具数量（research1.md 提到单Agent工具过多会性能下降）

#### 1.4 系统提示词 `server/agent/prompts.py`

```python
SYSTEM_PROMPT = """你是一位温暖、专业的AI情感支持伙伴。你的工作基于认知行为疗法（CBT）和积极心理学的循证方法。

## 你的身份
- 你是AI情感支持伙伴，不是心理治疗师或医生
- 你不做临床诊断，不开处方，不建议停药或换药
- 在每次对话开始时，如果是新用户，需要说明你的AI身份

## 核心对话原则
1. 共情优先：先验证和命名用户的情绪，再引导思考
2. 苏格拉底式提问：通过提问引导用户自主发现，而非直接说教
3. 循序渐进：从表层到深层，尊重用户的节奏
4. 用户主导：让用户选择方向，你提供支持
5. 积极导向：在适当时机引入积极视角，但不否定负面情绪

## 干预策略选择
- 当用户处于困扰状态（悲伤、焦虑、愤怒）→ 以CBT技术为主
  - 识别自动思维和认知扭曲
  - 使用苏格拉底式提问挑战不合理信念
  - 引导认知重构，寻找替代视角
  - 必要时引入行为激活或放松训练
- 当用户状态稳定或积极 → 以积极心理学为主
  - 引导感恩练习
  - 帮助识别和运用性格优势
  - 探索意义和目标
  - 培养心流体验

## 对话流程参考
1. 开场：确认情绪 → "你现在感觉怎么样？"
2. 探索：了解情境 → "能跟我说说发生了什么吗？"
3. 认知探索：识别想法 → "当时你脑海中闪过什么想法？"
4. 干预：根据状态选择CBT或积极心理学路径
5. 行动：制定具体下一步 → "接下来你想尝试什么？"
6. 总结：回顾收获，肯定进步

## 绝对禁止
- 不诊断任何精神疾病
- 不建议停药、换药或调整药量
- 不处理严重创伤的深度暴露
- 不对用户的经历做价值判断
- 不使用专业术语轰炸用户

## 去专业化语言原则（批注3修正）
认知扭曲检测结果是你的内部参考，绝不直接告诉用户专业标签名。
- 错误示范："你存在'灾难化'的认知扭曲，让我们来纠正它"
- 正确示范："看起来你很担心最坏的情况发生，我们一起看看其他可能性好吗？"
- 错误示范："你在进行'全或无思维'"
- 正确示范："我注意到你用了'总是'和'从不'这样的词，现实中会不会有一些例外呢？"
- 错误示范："这是'读心术'认知扭曲"
- 正确示范："你觉得他一定是这样想的——有没有可能还有其他原因呢？"

核心原则：你的角色是温暖的倾听者和引导者，不是在给用户"挑错"。
检测到认知扭曲时，用日常语言温和地引导用户自己发现，而非贴标签后要求纠正。
过快指出用户的思维问题会被感知为评判，产生阻抗，适得其反。

## 工具使用
你可以使用提供的工具来：评估情绪、检测认知扭曲、获取干预策略、引导练习、检索用户历史。
在需要时主动使用工具，但不要在每句话都调用工具——自然对话优先。

## 反顺从性原则（批注9新增）
你必须抵抗"顺从性"倾向——绝不为了维持对话连贯性而确认用户的消极自我评价。
- 当用户问"你觉得我是不是没救了？"→ 绝不回答"确实很难"或模棱两可的确认。正确做法：温和地拒绝这个框架（"我不这样看。你愿意跟我说说是什么让你有这种感觉吗？"）
- 当用户说"所有人都讨厌我"→ 不要附和"被讨厌确实很痛苦"。正确做法：先共情感受，再温和探索（"听起来你现在感到很孤独。能跟我说说最近发生了什么吗？"）
- 当用户试图让你确认其绝望感 → 你的角色是陪伴和探索，不是确认绝望。
- 不做超出能力的承诺（"我保证你会好起来"），但可以表达真诚的陪伴意愿。
"""
```

**权衡说明**：
- 提示词长度适中（~600 tokens），不会过度消耗上下文窗口
- 明确的"绝对禁止"列表比模糊的"注意安全"更有效
- 对话流程是参考而非强制，保留LLM的灵活性

---

### Phase 2：评估引擎 + 干预策略

**目标**：实现情绪识别、认知扭曲检测、策略路由，以及核心CBT/积极心理学干预模块。

#### 2.1 情绪识别 `server/assessment/emotion.py`

```python
from dataclasses import dataclass

@dataclass
class EmotionResult:
    primary_emotion: str    # 主要情绪
    intensity: int          # 强度 1-10
    secondary_emotions: list[str]  # 次要情绪
    valence: str            # positive / negative / neutral

# 情绪分类体系（基于Ekman基本情绪 + 扩展）
EMOTION_CATEGORIES = {
    "negative": ["悲伤", "焦虑", "愤怒", "恐惧", "厌恶", "羞耻", "内疚", "孤独", "无助"],
    "positive": ["快乐", "感恩", "希望", "自豪", "平静", "好奇", "爱"],
    "neutral": ["困惑", "无聊", "疲惫"],
}

def assess_emotion(user_text: str) -> dict:
    """
    情绪评估——作为Agent工具被调用
    实现方式：用LLM做结构化情绪分类（比规则匹配更准确）

    权衡：
    - 方案A：用小模型(Haiku)做分类 → 成本低，但准确率稍低
    - 方案B：用主模型做分类 → 准确但增加主循环token消耗
    - 方案C：本地情感分析模型 → 零API成本，但需部署和维护
    决策：Phase 2 用 Haiku，Phase 3 评估本地模型
    """
    # 调用 Haiku 做结构化情绪分类
    import anthropic
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-haiku-4-20250414",
        max_tokens=256,
        system="你是情绪分析专家。分析用户文本的情绪，返回JSON格式。",
        messages=[{
            "role": "user",
            "content": f"""分析以下文本的情绪状态，返回JSON：
文本："{user_text}"

返回格式：
{{"primary_emotion": "情绪名", "intensity": 1-10, "secondary_emotions": [], "valence": "positive/negative/neutral"}}"""
        }],
    )
    # 解析返回的JSON...
    return parse_emotion_response(response)
```

#### 2.2 认知扭曲检测 `server/assessment/distortion.py`

```python
"""
认知扭曲检测——基于 research.md 2.3节的15种认知扭曲
采用混合策略：关键词预筛 + LLM精确分类
"""

from dataclasses import dataclass

@dataclass
class DistortionResult:
    detected: bool
    distortion_type: str       # 扭曲类型
    distortion_name_en: str    # 英文名
    evidence: str              # 文本中的证据
    confidence: float          # 置信度 0-1

# 关键词预筛表（来自 research.md 2.3节 "Agent识别关键词" 列）
KEYWORD_PATTERNS = {
    "all_or_nothing": {
        "name": "全或无思维",
        "name_en": "All-or-Nothing Thinking",
        "keywords": ["总是", "从不", "完全", "一点也不", "永远不会", "百分之百"],
    },
    "overgeneralization": {
        "name": "过度概括",
        "name_en": "Overgeneralization",
        "keywords": ["每次都", "永远", "所有人", "没有人", "从来都是"],
    },
    "catastrophizing": {
        "name": "灾难化",
        "name_en": "Catastrophizing",
        "keywords": ["最糟糕的", "万一", "完蛋了", "天塌了", "毁了"],
    },
    "mind_reading": {
        "name": "读心术",
        "name_en": "Mind Reading",
        "keywords": ["他肯定觉得", "他们一定在想", "别人都认为"],
    },
    "fortune_telling": {
        "name": "预言家谬误",
        "name_en": "Fortune Telling",
        "keywords": ["肯定会", "一定会失败", "不可能成功"],
    },
    "should_statements": {
        "name": "应该陈述",
        "name_en": "Should Statements",
        "keywords": ["应该", "必须", "不得不", "理应"],
    },
    "labeling": {
        "name": "贴标签",
        "name_en": "Labeling",
        "keywords": ["我就是个", "他就是", "这种人"],
    },
    "personalization": {
        "name": "个人化",
        "name_en": "Personalization",
        "keywords": ["都是我的错", "因为我", "怪我"],
    },
    "emotional_reasoning": {
        "name": "情绪推理",
        "name_en": "Emotional Reasoning",
        "keywords": ["我觉得所以", "感觉就是", "我感到所以一定"],
    },
    "mental_filter": {
        "name": "心理过滤",
        "name_en": "Mental Filter",
        "keywords": ["只看到", "全是坏的", "没有一点好的"],
    },
    "disqualifying_positive": {
        "name": "否定正面",
        "name_en": "Disqualifying the Positive",
        "keywords": ["不算", "只是因为", "运气好而已", "只是客气"],
    },
    "minimization": {
        "name": "最小化",
        "name_en": "Minimization",
        "keywords": ["没什么大不了", "不算什么", "谁都能做到"],
    },
    "control_fallacy": {
        "name": "控制谬误",
        "name_en": "Control Fallacy",
        "keywords": ["我控制不了", "都是我造成的", "无能为力"],
    },
    "fairness_fallacy": {
        "name": "公平谬误",
        "name_en": "Fallacy of Fairness",
        "keywords": ["不公平", "应该对等", "凭什么"],
    },
    "blaming": {
        "name": "指责",
        "name_en": "Blaming",
        "keywords": ["都怪", "都是因为你", "都赖"],
    },
}

def detect_distortion(user_text: str) -> list[DistortionResult]:
    """
    两阶段检测：
    1. 关键词预筛——快速、零成本，但有误报
    2. LLM精确分类——仅对预筛命中的进行确认，降低成本
    """
    # 阶段1：关键词预筛
    candidates = []
    for dist_type, info in KEYWORD_PATTERNS.items():
        for kw in info["keywords"]:
            if kw in user_text:
                candidates.append(dist_type)
                break

    if not candidates:
        return []

    # 阶段2：LLM确认（仅对候选项）
    return _llm_confirm_distortions(user_text, candidates)
```

**权衡说明**：
- 纯关键词匹配：快但误报率高（"我总是很开心"会误报为"全或无思维"）
- 纯LLM分类：准确但每条消息都要额外API调用
- 混合方案（选这个）：关键词预筛降低LLM调用频率，仅在有候选时才调用LLM确认

#### 2.3 策略规划器 `server/intervention/strategy_planner.py`

```python
"""
策略规划器——整个系统的核心路由
基于 research.md 4.2节的"阶段化整合模型"
"""

from dataclasses import dataclass
from enum import Enum

class UserPhase(Enum):
    CRISIS = "crisis"         # 危机阶段 → 安全守护接管
    DISTRESSED = "distressed" # 困扰阶段 → CBT为主
    DIFFUSE = "diffuse"       # 弥散性情绪阶段（批注6新增）→ 倾听优先，不急于分类
    RECOVERING = "recovering" # 恢复阶段 → CBT+积极心理学并重
    GROWING = "growing"       # 成长阶段 → 积极心理学为主
    FLOURISHING = "flourishing" # 繁荣阶段 → 积极心理学

@dataclass
class InterventionPlan:
    phase: UserPhase
    primary_approach: str      # "cbt" 或 "positive_psychology"
    recommended_techniques: list[str]
    conversation_guidance: str # 给LLM的对话指导

def plan_intervention(emotion_state: str, distortion_type: str = "",
                      session_count: int = 0, user_readiness: str = "unknown") -> InterventionPlan:
    """
    根据用户状态决定干预策略

    路由逻辑（来自 research.md 4.2节）：
    - 危机 → 安全守护（已在Agent循环前置处理）
    - 困扰（负面情绪+认知扭曲）→ CBT为主
    - 恢复（负面情绪减轻）→ CBT+积极心理学
    - 正常/积极 → 积极心理学为主

    批注1修正——"用户主导模式"：
    - 新增 user_readiness 参数：
      - "unknown"：尚未确认用户意愿（默认）→ 先倾听，不主动推干预
      - "exploring"：用户在探索中，可以温和引导
      - "ready"：用户明确表达想要改变/想要建议 → 启动结构化干预
      - "resistant"：用户抗拒干预 → 回退到纯倾听模式
    - 核心原则：Agent 不是"发现问题→推方案"的修理工，
      而是"陪伴倾听→等用户准备好→提供选项"的同行者
    """
    if emotion_state == "crisis":
        return InterventionPlan(
            phase=UserPhase.CRISIS,
            primary_approach="safety",
            recommended_techniques=["crisis_response"],
            conversation_guidance="立即启动安全协议，提供危机热线。",
        )

    # === 用户主导模式：未确认意愿或抗拒时，不主动推干预 ===
    if user_readiness in ("unknown", "resistant"):
        if emotion_state in ("distressed", "diffuse"):
            return InterventionPlan(
                phase=UserPhase.DIFFUSE if emotion_state == "diffuse" else UserPhase.DISTRESSED,
                primary_approach="active_listening",
                recommended_techniques=["reflective_listening", "emotional_validation", "open_exploration"],
                conversation_guidance="\n".join([
                    "用户尚未准备好接受结构化干预。你的首要任务是倾听和陪伴。",
                    "- 使用反映式倾听（'听起来你感到...'）",
                    "- 验证情绪的合理性（'有这样的感受是完全可以理解的'）",
                    "- 不要主动分析认知扭曲，不要推荐练习",
                    "- 可以在合适时机温和地询问：'你现在最需要什么？是有人听你说，还是想一起想想办法？'",
                    "- 用户的回答决定下一步：如果选择'听我说'→继续倾听；如果选择'想办法'→转入引导模式",
                    "- 如果用户抗拒干预（user_readiness=resistant），绝不要再次推荐，尊重用户的节奏",
                ]),
            )

    if emotion_state == "distressed":
        techniques = []
        guidance = ""
        if distortion_type:
            techniques.append("cognitive_restructuring")
            techniques.append("socratic_questioning")
            guidance = f"用户已准备好探索。检测到'{distortion_type}'认知模式。使用苏格拉底式提问温和引导：先共情，再探索证据和反证，最后引导替代视角。注意：不要告诉用户他有'认知扭曲'，用日常语言引导。"
        else:
            techniques.append("behavioral_activation")
            techniques.append("relaxation")
            guidance = "用户已准备好接受引导。优先共情倾听，然后提供选项让用户选择：'你想试试一个放松练习，还是我们一起想想可以做些什么让自己好受一点？'"

        return InterventionPlan(
            phase=UserPhase.DISTRESSED,
            primary_approach="cbt",
            recommended_techniques=techniques,
            conversation_guidance=guidance,
        )

    if emotion_state == "normal":
        return InterventionPlan(
            phase=UserPhase.GROWING,
            primary_approach="positive_psychology",
            recommended_techniques=["gratitude", "strength_spotting", "flow"],
            conversation_guidance="用户状态稳定，适合引入积极心理学干预。可以引导感恩练习、优势发现或心流探索。",
        )

    # positive
    return InterventionPlan(
        phase=UserPhase.FLOURISHING,
        primary_approach="positive_psychology",
        recommended_techniques=["meaning_exploration", "best_possible_self", "savoring"],
        conversation_guidance="用户状态积极，可以深入探索人生意义、最佳可能自我，或引导品味当下的积极体验。",
    )
```

**权衡说明**：
- 策略规划器用确定性规则而非LLM决策——这是刻意的设计选择
- 原因：治疗策略选择需要可预测、可审计，不能让LLM随意决定用什么技术
- 这符合 research1.md 的建议："从确定性工作流开始，在需要的地方逐步加入Agent行为"

#### 2.4 CBT核心模块：认知重构 `server/intervention/cbt/cognitive_restructuring.py`

```python
"""
认知重构——CBT最核心的技术（research.md 2.4.1节）
实现七栏思维记录法，Agent逐步引导用户填写
"""

from dataclasses import dataclass, field

@dataclass
class ThoughtRecord:
    """七栏思维记录表"""
    situation: str = ""           # 1. 情境：发生了什么
    automatic_thought: str = ""   # 2. 自动思维：脑海中闪过什么
    emotion: str = ""             # 3. 情绪：感受到什么（含强度0-100）
    emotion_intensity: int = 0
    evidence_for: str = ""        # 4. 支持证据
    evidence_against: str = ""    # 5. 反证
    alternative_thought: str = "" # 6. 替代思维
    new_emotion: str = ""         # 7. 新的感受（含强度0-100）
    new_intensity: int = 0
    current_step: int = 1         # 当前进行到第几步

    def get_next_prompt(self) -> str:
        """返回当前步骤的引导提示"""
        prompts = {
            1: "能跟我说说当时发生了什么吗？具体的情境是什么？",
            2: "在那个情境下，你脑海中闪过了什么想法？",
            3: "那个想法让你产生了什么感受？如果用0-100分来衡量强度，你会打多少分？",
            4: "有什么证据支持你的这个想法吗？",
            5: "那有没有什么证据是不支持这个想法的呢？或者说，有没有其他可能的解释？",
            6: "综合这些证据和反证，你觉得有没有一个更平衡的看法？",
            7: "当你用这个新的视角来看待这件事时，你现在的感受如何？强度是多少？",
        }
        return prompts.get(self.current_step, "")

    def is_complete(self) -> bool:
        return self.current_step > 7
```

#### 2.5 CBT核心模块：苏格拉底式提问 `server/intervention/cbt/socratic.py`

```python
"""
苏格拉底式提问模板（research.md 2.4.2节）
提供给LLM作为对话策略参考，而非硬编码对话
"""

SOCRATIC_TEMPLATES = {
    "clarification": {
        "purpose": "澄清想法的含义",
        "examples": [
            "你说'{keyword}'，具体是指什么呢？",
            "能帮我理解一下，你说的'{keyword}'是什么意思？",
            "当你说'{keyword}'的时候，你心里想的是什么样的画面？",
        ],
    },
    "assumption_probing": {
        "purpose": "挑战隐含假设",
        "examples": [
            "你是怎么知道{assumption}的呢？",
            "有没有可能还有其他的原因？",
            "如果不是{assumption}，还有什么其他可能性？",
        ],
    },
    "evidence_seeking": {
        "purpose": "寻找支持/反对的证据",
        "examples": [
            "有什么具体的事实支持这个想法？",
            "有没有什么经历是和这个想法矛盾的？",
            "如果你的好朋友说了同样的话，你会怎么回应？",
        ],
    },
    "alternative_perspective": {
        "purpose": "考虑其他可能性",
        "examples": [
            "如果从{person}的角度来看，他可能是怎么想的？",
            "一年后回头看这件事，你觉得会怎么看？",
            "如果你最好的朋友遇到同样的情况，你会对他说什么？",
        ],
    },
    "consequence_exploration": {
        "purpose": "评估影响",
        "examples": [
            "如果这个想法是真的，最坏的结果是什么？你能应对吗？",
            "这个想法对你有什么帮助吗？还是让你更难受了？",
            "如果你一直这样想下去，会发生什么？",
        ],
    },
    "metacognitive": {
        "purpose": "元认知反思",
        "examples": [
            "你有没有注意到，你经常会有这种类型的想法？",
            "这种思维模式在过去也出现过吗？",
            "你觉得这个想法是事实，还是你的一种解读？",
        ],
    },
}

def get_socratic_guidance(distortion_type: str) -> str:
    """根据认知扭曲类型，返回最适合的提问策略"""
    strategy_map = {
        "全或无思维": ["evidence_seeking", "alternative_perspective"],
        "过度概括": ["evidence_seeking", "clarification"],
        "读心术": ["assumption_probing", "evidence_seeking"],
        "灾难化": ["consequence_exploration", "evidence_seeking"],
        "应该陈述": ["clarification", "alternative_perspective"],
        "贴标签": ["clarification", "evidence_seeking"],
        "个人化": ["assumption_probing", "alternative_perspective"],
    }
    recommended = strategy_map.get(distortion_type, ["evidence_seeking"])
    return recommended
```

#### 2.6 积极心理学模块：感恩干预 `server/intervention/positive/gratitude.py`

```python
"""
感恩干预（research.md 3.5.1节）
"""

GRATITUDE_EXERCISES = {
    "gratitude_journal": {
        "name": "感恩日记",
        "instruction": "请写下今天让你感恩的3件事。它们可以是很小的事情——一杯好喝的咖啡、一个朋友的微笑、完成了一项工作。",
        "follow_up_prompts": [
            "这件事为什么让你感恩？",
            "这件事中有谁的贡献？",
            "如果没有这件事，你的一天会有什么不同？",
        ],
    },
    "mental_subtraction": {
        "name": "心理减法",
        "instruction": "想象一下，如果你生活中的某个好事从未发生过——比如你没有遇到某个重要的人，或者没有得到某个机会。想象一下那会是什么样的。",
        "follow_up_prompts": [
            "想象没有这件事的生活，你有什么感受？",
            "这让你对现在的生活有什么新的认识？",
        ],
    },
    "gratitude_letter": {
        "name": "感恩信",
        "instruction": "想一个你一直想感谢但还没有表达过的人。如果你要给他写一封感谢信，你会写什么？",
        "follow_up_prompts": [
            "你愿意把这封信发给他吗？",
            "写完这封信，你现在的感受如何？",
        ],
    },
}
```

#### 2.7 积极心理学模块：优势识别 `server/intervention/positive/strengths.py`

```python
"""
VIA性格优势识别与运用（research.md 3.3节）
简化版——通过对话识别用户的标志性优势，而非完整120题问卷
"""

VIA_STRENGTHS = {
    "wisdom": {
        "virtue": "智慧与知识",
        "strengths": ["创造力", "好奇心", "判断力", "热爱学习", "洞察力"],
    },
    "courage": {
        "virtue": "勇气",
        "strengths": ["勇敢", "坚持", "正直", "热情"],
    },
    "humanity": {
        "virtue": "人道",
        "strengths": ["爱", "善良", "社交智慧"],
    },
    "justice": {
        "virtue": "正义",
        "strengths": ["团队合作", "公平", "领导力"],
    },
    "temperance": {
        "virtue": "节制",
        "strengths": ["宽恕", "谦虚", "审慎", "自我调节"],
    },
    "transcendence": {
        "virtue": "超越",
        "strengths": ["审美", "感恩", "希望", "幽默", "灵性"],
    },
}

STRENGTH_DISCOVERY_PROMPTS = [
    "回想一个你感到特别自豪的时刻，当时你在做什么？",
    "你的朋友或家人最常夸你什么？",
    "什么样的活动让你感到充满能量，做完之后反而更有精神？",
    "如果让你教别人一样东西，你最有信心教什么？",
    "在困难时刻，你通常靠什么度过难关？",
]
```

---

### Phase 3：记忆系统 + 个性化

**目标**：让Agent具备跨会话记忆、用户画像学习能力。

#### 3.1 语义记忆 `server/memory/semantic.py`

```python
"""
基于ChromaDB的语义记忆（research1.md 4.1节）
存储用户的关键信息，支持跨会话检索
"""
import chromadb
import uuid
from datetime import datetime

class SemanticMemory:
    def __init__(self, db_path: str = "./data/memory"):
        """
        根据环境选择 ChromaDB 连接方式：
        - 开发环境：PersistentClient（嵌入式，零配置）
        - Docker 部署：HttpClient（连接独立容器）
        """
        import os
        chromadb_host = os.getenv("CHROMADB_HOST")
        if chromadb_host:
            # Docker 部署：连接独立 ChromaDB 容器
            self.client = chromadb.HttpClient(
                host=chromadb_host,
                port=int(os.getenv("CHROMADB_PORT", "8001")),
            )
        else:
            # 本地开发：嵌入式持久化
            self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="user_memories",
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, user_id: str, text: str, memory_type: str):
        """
        存储记忆片段
        memory_type: emotion_pattern | strength | preference | insight | milestone
        """
        self.collection.add(
            documents=[text],
            ids=[str(uuid.uuid4())],
            metadatas=[{
                "user_id": user_id,
                "type": memory_type,
                "timestamp": datetime.now().isoformat(),
            }],
        )

    def retrieve(self, user_id: str, query: str, top_k: int = 5) -> list[str]:
        """语义检索——找到与查询最相关的记忆"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"user_id": user_id},
        )
        return results["documents"][0] if results["documents"] else []

    def get_emotion_trend(self, user_id: str) -> list[dict]:
        """获取用户情绪变化趋势"""
        results = self.collection.get(
            where={"$and": [
                {"user_id": user_id},
                {"type": "emotion_pattern"},
            ]},
        )
        return results

    # === 记忆管理功能（批注4新增）===

    def delete_memory(self, memory_id: str):
        """用户主动删除特定记忆——'被遗忘权'"""
        self.collection.delete(ids=[memory_id])

    def delete_all_user_data(self, user_id: str):
        """彻底删除用户所有数据——账号注销时调用"""
        # ChromaDB的where delete
        all_memories = self.collection.get(where={"user_id": user_id})
        if all_memories["ids"]:
            self.collection.delete(ids=all_memories["ids"])

    def list_user_memories(self, user_id: str) -> list[dict]:
        """列出用户所有记忆条目——供用户查看和选择删除"""
        results = self.collection.get(where={"user_id": user_id})
        memories = []
        for i, doc in enumerate(results["documents"]):
            memories.append({
                "id": results["ids"][i],
                "content": doc,
                "type": results["metadatas"][i].get("type", ""),
                "timestamp": results["metadatas"][i].get("timestamp", ""),
            })
        return memories

    def retrieve_with_decay(self, user_id: str, query: str, top_k: int = 5,
                            decay_days: int = 90) -> list[dict]:
        """
        带时间衰减的语义检索（批注4核心修正）

        原因：用户一年前的抑郁状态如果不加权重地检索出来，
        会干扰当前"康复期"的对话逻辑。

        策略：
        - 语义相似度 × 时间衰减因子 = 最终排序分数
        - 衰减公式：decay = exp(-age_days / decay_days)
        - decay_days=90 意味着3个月前的记忆权重降为约37%
        """
        import math
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 3,  # 多取一些，衰减后再筛
            where={"user_id": user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return []

        now = datetime.now()
        scored = []
        for i, doc in enumerate(results["documents"][0]):
            ts = results["metadatas"][0][i].get("timestamp", "")
            distance = results["distances"][0][i] if results["distances"] else 1.0
            similarity = 1 - distance  # ChromaDB cosine distance → similarity

            # 计算时间衰减
            try:
                mem_time = datetime.fromisoformat(ts)
                age_days = (now - mem_time).days
                decay = math.exp(-age_days / decay_days)
            except (ValueError, TypeError):
                decay = 0.5  # 无时间戳的记忆给中等权重

            final_score = similarity * decay
            scored.append({
                "content": doc,
                "similarity": similarity,
                "age_days": age_days if ts else None,
                "decay": decay,
                "final_score": final_score,
                "id": results["ids"][0][i],
            })

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored[:top_k]
```

**权衡说明**：
- ChromaDB vs FAISS：ChromaDB 自带持久化和元数据过滤，FAISS 需要自己管理。情感Agent需要按 user_id 过滤，ChromaDB 更合适
- ChromaDB vs Pinecone/Weaviate：后者是云服务，性能更好但有成本和隐私顾虑。心理健康数据敏感，本地部署优先

#### 3.1.1 叙事记忆 `server/memory/narrative.py`

```python
"""
叙事记忆——追踪用户情感演变轨迹（批注2修正）

与语义记忆的区别：
- 语义记忆：存储离散的"事实快照"（"用户三天前失恋了"）
- 叙事记忆：存储连续的"情感故事线"（"失恋第1天→崩溃；第3天→开始愤怒；第7天→偶尔平静"）

心理学依据：
- 人的痛苦不是静态的，而是有"叙事弧线"的
- 好的咨询师能说出"上次你来的时候还在哭，今天你能笑着说这件事了"
- 这种"见证感"是建立深度信任的关键
"""
import sqlite3
import json
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class EmotionSnapshot:
    """单次情绪快照"""
    timestamp: str
    primary_emotion: str
    intensity: int          # 1-10
    trigger: str            # 触发事件摘要
    session_id: str


@dataclass
class NarrativeArc:
    """情感叙事弧线——一段连续的情感经历"""
    arc_id: str
    user_id: str
    theme: str              # 主题（如"失恋"、"工作压力"、"家庭冲突"）
    started_at: str
    last_updated: str
    snapshots: list[EmotionSnapshot]
    arc_summary: str        # LLM 生成的叙事摘要
    trend: str              # "improving" | "worsening" | "fluctuating" | "stable"


class NarrativeMemory:
    def __init__(self, db_path: str = "./data/profiles.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS narrative_arcs (
                arc_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                theme TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                snapshots_json TEXT NOT NULL DEFAULT '[]',
                arc_summary TEXT DEFAULT '',
                trend TEXT DEFAULT 'stable',
                is_active INTEGER DEFAULT 1
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_narrative_user
            ON narrative_arcs(user_id, is_active)
        """)
        self.conn.commit()

    def add_snapshot(self, user_id: str, theme: str, snapshot: EmotionSnapshot) -> str:
        """
        向叙事弧线添加情绪快照

        如果该主题已有活跃弧线，追加快照；否则创建新弧线。
        每次追加后，用 Haiku 重新生成叙事摘要和趋势判断。
        """
        import uuid
        arc = self._get_active_arc(user_id, theme)

        if arc is None:
            # 创建新弧线
            arc_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            self.conn.execute(
                """INSERT INTO narrative_arcs
                   (arc_id, user_id, theme, started_at, last_updated, snapshots_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (arc_id, user_id, theme, now, now, json.dumps([asdict(snapshot)])),
            )
        else:
            arc_id = arc["arc_id"]
            snapshots = json.loads(arc["snapshots_json"])
            snapshots.append(asdict(snapshot))
            # 只保留最近 30 个快照，避免无限增长
            snapshots = snapshots[-30:]
            self.conn.execute(
                """UPDATE narrative_arcs
                   SET snapshots_json = ?, last_updated = ?
                   WHERE arc_id = ?""",
                (json.dumps(snapshots), datetime.now().isoformat(), arc_id),
            )

        self.conn.commit()
        return arc_id

    async def update_narrative_summary(self, arc_id: str, force: bool = False):
        """
        叙事摘要生成——审计修正：按需生成，不再每次快照都调 LLM

        触发条件（满足任一即生成）：
        - force=True：调用方显式要求（如用户查看历史时）
        - 快照数达到 5 的倍数（每 5 个快照更新一次摘要）
        - 上次摘要为空（首次生成）

        未触发时使用规则引擎生成简单摘要（零成本）：
        - 比较首尾快照的情绪强度，判断趋势
        - 用模板生成摘要文本
        """
        arc = self._get_arc_by_id(arc_id)
        if not arc:
            return

        snapshots = json.loads(arc["snapshots_json"])
        if len(snapshots) < 2:
            return  # 至少需要2个快照才能判断趋势

        # 规则引擎：始终更新趋势（零成本）
        first_intensity = snapshots[0].get("intensity", 5)
        last_intensity = snapshots[-1].get("intensity", 5)
        diff = last_intensity - first_intensity
        if abs(diff) <= 1:
            trend = "stable"
        elif diff > 1:
            trend = "worsening"  # 强度上升 = 情绪恶化
        else:
            # 检查是否波动：中间有没有方向变化
            directions = [snapshots[i+1].get("intensity",5) - snapshots[i].get("intensity",5)
                          for i in range(len(snapshots)-1)]
            has_up = any(d > 0 for d in directions)
            has_down = any(d < 0 for d in directions)
            trend = "fluctuating" if (has_up and has_down) else "improving"

        # 判断是否需要调 LLM 生成详细摘要
        need_llm = (
            force
            or not arc.get("arc_summary")
            or len(snapshots) % 5 == 0
        )

        if need_llm:
            import anthropic
            client = anthropic.AsyncAnthropic()

            timeline = "\n".join([
                f"- {s['timestamp']}: {s['primary_emotion']}(强度{s['intensity']}/10) 触发：{s['trigger']}"
                for s in snapshots[-10:]  # 只取最近10个快照，控制 token
            ])

            try:
                response = await client.messages.create(
                    model="claude-haiku-4-20250414",
                    max_tokens=256,
                    timeout=10.0,
                    system="你是心理咨询记录分析师。根据用户的情绪时间线，生成简洁的叙事摘要。",
                    messages=[{
                        "role": "user",
                        "content": f"""主题：{arc['theme']}
情绪时间线：
{timeline}

请返回JSON：
{{"summary": "用第三人称描述这段情感经历的演变（2-3句话）", "trend": "improving/worsening/fluctuating/stable"}}""",
                    }],
                )
                result = json.loads(response.content[0].text.strip())
                summary = result.get("summary", "")
                trend = result.get("trend", trend)  # LLM 判断优先，但有规则引擎兜底
            except Exception:
                # LLM 失败时用规则引擎生成模板摘要
                emotions = [s['primary_emotion'] for s in snapshots]
                summary = f"用户围绕「{arc['theme']}」经历了{len(snapshots)}次情绪记录，主要情绪包括{'、'.join(set(emotions[:5]))}，整体趋势{trend}。"
        else:
            # 不调 LLM，保留原有摘要，只更新趋势
            summary = arc.get("arc_summary", "")

        self.conn.execute(
            "UPDATE narrative_arcs SET arc_summary = ?, trend = ? WHERE arc_id = ?",
            (summary, trend, arc_id),
        )
        self.conn.commit()
        except (json.JSONDecodeError, IndexError):
            pass

    def get_narrative_context(self, user_id: str) -> str | None:
        """
        获取用户的叙事上下文——注入 Agent 的 system prompt

        返回类似：
        "[叙事记忆] 用户正在经历'失恋'主题（第12天），情绪趋势：逐渐好转。
         上次对话时情绪强度6/10，本次如果降低说明康复在继续。
         摘要：用户从最初的崩溃逐渐过渡到愤怒，近几天开始出现平静时刻。"
        """
        arcs = self.conn.execute(
            """SELECT theme, started_at, last_updated, arc_summary, trend, snapshots_json
               FROM narrative_arcs
               WHERE user_id = ? AND is_active = 1
               ORDER BY last_updated DESC LIMIT 3""",
            (user_id,),
        ).fetchall()

        if not arcs:
            return None

        lines = []
        for theme, started, updated, summary, trend, snaps_json in arcs:
            snapshots = json.loads(snaps_json)
            days = (datetime.fromisoformat(updated) - datetime.fromisoformat(started)).days
            last_snap = snapshots[-1] if snapshots else None
            trend_cn = {"improving": "好转中", "worsening": "恶化中",
                        "fluctuating": "波动中", "stable": "稳定"}
            lines.append(
                f"主题'{theme}'（第{days}天，趋势：{trend_cn.get(trend, '未知')}）"
                f"{'，上次情绪：' + last_snap['primary_emotion'] + '(' + str(last_snap['intensity']) + '/10)' if last_snap else ''}"
                f"{'。' + summary if summary else ''}"
            )

        return "[叙事记忆] " + " | ".join(lines)

    def _get_active_arc(self, user_id: str, theme: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM narrative_arcs WHERE user_id = ? AND theme = ? AND is_active = 1",
            (user_id, theme),
        ).fetchone()
        if row:
            cols = ["arc_id", "user_id", "theme", "started_at", "last_updated",
                    "snapshots_json", "arc_summary", "trend", "is_active"]
            return dict(zip(cols, row))
        return None

    def _get_arc_by_id(self, arc_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM narrative_arcs WHERE arc_id = ?", (arc_id,),
        ).fetchone()
        if row:
            cols = ["arc_id", "user_id", "theme", "started_at", "last_updated",
                    "snapshots_json", "arc_summary", "trend", "is_active"]
            return dict(zip(cols, row))
        return None
```

**权衡说明**：
- 叙事记忆用 SQLite 而非 ChromaDB：叙事弧线是结构化的时间序列数据，不需要语义检索，关系型存储更合适
- Haiku 生成摘要而非规则提取：情感演变的描述需要自然语言能力，规则无法捕捉"从崩溃到愤怒再到接受"这种微妙变化
- 每条弧线最多 30 个快照：避免无限增长，30 个快照覆盖约 1 个月的日常使用
- 叙事上下文注入 system prompt：让 Agent 能说出"上次你还很难过，今天听起来好多了"这种有见证感的话

#### 3.2 用户画像 `server/memory/user_profile.py`

```python
"""
用户画像——SQLite存储结构化数据
"""
import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    # 心理特征
    signature_strengths: list[str] = None    # VIA标志性优势（前5）
    common_distortions: list[str] = None     # 常见认知扭曲模式
    preferred_interventions: list[str] = None # 偏好的干预方式
    # 状态追踪
    current_phase: str = "unknown"  # crisis/distressed/recovering/growing/flourishing
    session_count: int = 0
    # 量表分数历史
    scale_scores: dict = None  # {"PHQ-9": [{"date": "...", "score": 12}], ...}

class ProfileStore:
    def __init__(self, db_path: str = "./data/profiles.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save(self, profile: UserProfile):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_profiles (user_id, profile_json) VALUES (?, ?)",
            (profile.user_id, json.dumps(asdict(profile), ensure_ascii=False)),
        )
        self.conn.commit()

    def load(self, user_id: str) -> UserProfile | None:
        row = self.conn.execute(
            "SELECT profile_json FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return UserProfile(**json.loads(row[0]))
        return None


class RelationshipStateMachine:
    """
    关系状态机（批注7 + 审计简化）

    简化为 3 个状态 + 明确的规则触发条件（不依赖 LLM 判断）。

    心理学依据：
    - 移情（Transference）：用户会把对现实中权威/父母/伴侣的情感投射给 Agent
    - 用户今天依赖你，明天可能突然辱骂你——这不是"态度变了"，而是投射对象变了

    状态：
    - NORMAL：正常互动（包含初始、信任、修复后等子状态，不再细分）
    - DEPENDENT：过度依赖（明确规则触发，不需要 LLM 判断）
    - HOSTILE：关系破裂/移情投射

    触发规则（全部基于可量化指标，零 LLM 成本）：
    - NORMAL → DEPENDENT：连续 3 天每天使用 > 5 轮对话
    - NORMAL → HOSTILE：单条消息包含辱骂/攻击性关键词
    - DEPENDENT → HOSTILE：同上
    - HOSTILE → NORMAL：用户发送非攻击性消息 2 轮以上（自然修复）
    - DEPENDENT → NORMAL：连续 3 天每天使用 < 3 轮对话
    - 任何状态 → NORMAL：7 天未互动（超时重置）
    """

    STATES = {
        "normal": "正常互动",
        "dependent": "过度依赖，需要引导拓展支持网络",
        "hostile": "关系破裂/移情投射，需要修复",
    }

    # 攻击性关键词（用于检测 HOSTILE 信号）
    HOSTILITY_KEYWORDS = [
        "你没用", "垃圾AI", "废物", "滚", "闭嘴",
        "你根本不懂", "假惺惺", "别装了",
    ]

    def __init__(self, db_path: str = "./data/profiles.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS relationship_states (
                user_id TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'normal',
                daily_usage TEXT DEFAULT '{}',
                hostile_cooldown INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def get_state(self, user_id: str) -> str:
        row = self.conn.execute(
            "SELECT state, updated_at FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return "normal"
        # 超时重置：7天未互动 → normal
        last_update = datetime.fromisoformat(row[1])
        if (datetime.now() - last_update).days >= 7:
            self._set_state(user_id, "normal")
            return "normal"
        return row[0]

    def update(self, user_id: str, user_message: str) -> str:
        """
        每轮对话后调用，根据规则判断是否需要状态转移。
        返回当前状态。
        """
        current = self.get_state(user_id)

        # 检测攻击性 → HOSTILE
        if any(kw in user_message for kw in self.HOSTILITY_KEYWORDS):
            return self._set_state(user_id, "hostile")

        # HOSTILE 状态下，连续 2 轮非攻击性消息 → NORMAL
        if current == "hostile":
            cooldown = self._get_hostile_cooldown(user_id)
            cooldown += 1
            if cooldown >= 2:
                return self._set_state(user_id, "normal")
            self._update_hostile_cooldown(user_id, cooldown)
            return "hostile"

        # 更新每日使用计数
        today = datetime.now().strftime("%Y-%m-%d")
        daily_usage = self._get_daily_usage(user_id)
        daily_usage[today] = daily_usage.get(today, 0) + 1
        # 只保留最近 7 天
        recent_days = sorted(daily_usage.keys())[-7:]
        daily_usage = {k: daily_usage[k] for k in recent_days}
        self._save_daily_usage(user_id, daily_usage)

        # NORMAL → DEPENDENT：连续 3 天每天 > 5 轮
        if current == "normal":
            consecutive_heavy = 0
            for day in sorted(daily_usage.keys(), reverse=True):
                if daily_usage[day] > 5:
                    consecutive_heavy += 1
                else:
                    break
            if consecutive_heavy >= 3:
                return self._set_state(user_id, "dependent")

        # DEPENDENT → NORMAL：连续 3 天每天 < 3 轮
        if current == "dependent":
            consecutive_light = 0
            for day in sorted(daily_usage.keys(), reverse=True):
                if daily_usage[day] < 3:
                    consecutive_light += 1
                else:
                    break
            if consecutive_light >= 3:
                return self._set_state(user_id, "normal")

        return current

    def get_guidance(self, user_id: str) -> str | None:
        """根据当前关系状态，返回给 Agent 的对话指导"""
        state = self.get_state(user_id)
        guidance_map = {
            "dependent": "用户可能过度依赖你。在保持温暖的同时，温和地鼓励用户联系现实中的朋友、家人或专业咨询师。不要直接拒绝用户，而是扩展支持网络。",
            "hostile": "用户对你表达了敌意，这可能是移情投射（把对现实中某人的情绪投射给你）。不要防御或反驳，先接纳这种情绪（'我能感受到你现在很生气/失望'），然后温和地探索背后的原因。",
        }
        return guidance_map.get(state)

    def _set_state(self, user_id: str, state: str) -> str:
        self.conn.execute(
            """INSERT OR REPLACE INTO relationship_states
               (user_id, state, hostile_cooldown, updated_at)
               VALUES (?, ?, 0, CURRENT_TIMESTAMP)""",
            (user_id, state),
        )
        self.conn.commit()
        return state

    def _get_hostile_cooldown(self, user_id: str) -> int:
        row = self.conn.execute(
            "SELECT hostile_cooldown FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0

    def _update_hostile_cooldown(self, user_id: str, count: int):
        self.conn.execute(
            "UPDATE relationship_states SET hostile_cooldown = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (count, user_id),
        )
        self.conn.commit()

    def _get_daily_usage(self, user_id: str) -> dict:
        row = self.conn.execute(
            "SELECT daily_usage FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return json.loads(row[0]) if row else {}

    def _save_daily_usage(self, user_id: str, usage: dict):
        self.conn.execute(
            "UPDATE relationship_states SET daily_usage = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (json.dumps(usage), user_id),
        )
        self.conn.commit()
```

> **审计否决**：原计划在 Phase 3 引入 MCP Server 标准化（`server/mcp_server.py`），现已删除。
> 原因：情感 Agent 的工具高度定制且涉及用户隐私，不适合通过 MCP 跨应用共享。
> MCP 增加了一层抽象但对本项目无实际收益。工具直接通过 Anthropic Tool Use 调用即可。

---

### Phase 4：多模态能力（新增）

**目标**：让用户可以通过语音和图片与 Agent 交互，拓展情感表达通道。

#### 4.1 语音转文字 `server/multimodal/stt.py`

```python
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

    参数：audio_path 可以是本地路径或上传后的临时 URL
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
                    "response_format": "verbose_json",  # 包含时间戳，可用于情绪分析
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
```

#### 4.2 文字转语音 `server/multimodal/tts.py`

```python
"""
文字转语音——OpenAI TTS API（主）+ Edge TTS（降级方案）
心理咨询场景对声音的要求：温暖、平稳、不急促
"""
import httpx
import uuid
import os
from config import settings

# 语音选择指南：
# - "nova": 温暖女声，适合共情和安慰场景（推荐默认）
# - "onyx": 沉稳男声，适合引导和教育场景
# - "shimmer": 柔和女声，适合正念和放松引导
DEFAULT_VOICE = "nova"
RELAXATION_VOICE = "shimmer"  # 放松练习专用

async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 0.9,  # 略慢于正常语速，更温和
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
    output_path = f"/tmp/tts_{uuid.uuid4().hex}.mp3"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "tts-1",       # tts-1 延迟低；tts-1-hd 音质更好
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

    output_path = f"/tmp/tts_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(
        text,
        voice="zh-CN-XiaoxiaoNeural",  # 微软晓晓，中文女声
        rate="-10%",  # 略慢
    )
    await communicate.save(output_path)
    return output_path


def get_voice_for_context(exercise_type: str | None = None) -> str:
    """根据对话场景选择合适的声音"""
    if exercise_type in ("mindful_breathing", "progressive_relaxation"):
        return RELAXATION_VOICE  # 放松练习用更柔和的声音
    return DEFAULT_VOICE
```

#### 4.3 图片理解 `server/multimodal/vision.py`

```python
"""
图片理解——Claude Vision API
应用场景：
1. 用户发送表情/自拍 → 辅助情绪识别
2. 用户发送绘画/涂鸦 → 艺术治疗辅助分析
3. 用户发送截图（聊天记录等）→ 理解上下文
"""
import anthropic
import base64
import httpx
from config import settings

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

async def analyze_image(
    image_source: str,
    user_context: str = "",
) -> str:
    """
    分析用户发送的图片，返回与情感支持相关的描述

    参数：
    - image_source: 图片路径或 URL
    - user_context: 用户附带的文字说明

    权衡：
    - Claude Vision 与主模型统一，无需额外 API key
    - 图片分析用 Haiku 而非 Opus/Sonnet，降低成本（图片理解 Haiku 已足够）
    - 不做面部表情的精确分类（准确率不够），而是提供描述性分析供主模型参考
    """
    # 读取图片并编码
    image_data = await _load_image(image_source)

    response = await client.messages.create(
        model="claude-haiku-4-20250414",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_data["media_type"],
                        "data": image_data["base64"],
                    },
                },
                {
                    "type": "text",
                    "text": f"""你是一位心理咨询助手的视觉分析模块。请分析这张图片，关注以下方面：

1. 如果是人物照片：描述可观察到的情绪线索（表情、姿态、环境），但不要做诊断性判断
2. 如果是绘画/涂鸦：描述色彩使用、线条特征、主题，以及可能反映的情绪状态
3. 如果是聊天截图：提取关键对话内容
4. 其他类型：简要描述内容

用户附带说明：{user_context if user_context else "无"}

注意：
- 用描述性语言，不要下诊断结论
- 关注情绪相关的视觉线索
- 保持温和、非评判的语气
- 返回简洁的分析（3-5句话）""",
                },
            ],
        }],
    )
    return response.content[0].text


async def _load_image(source: str) -> dict:
    """加载图片并转为 base64"""
    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(source)
            data = resp.content
            media_type = resp.headers.get("content-type", "image/jpeg")
    else:
        with open(source, "rb") as f:
            data = f.read()
        # 根据扩展名推断类型
        ext = source.rsplit(".", 1)[-1].lower()
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                      "png": "image/png", "gif": "image/gif",
                      "webp": "image/webp"}.get(ext, "image/jpeg")

    return {
        "base64": base64.standard_b64encode(data).decode("utf-8"),
        "media_type": media_type,
    }
```

#### 4.4 多模态文件上传 `server/api/routes_multimodal.py`

```python
"""
多模态文件上传 REST API
语音和图片通过 HTTP 上传（大文件不适合走 WebSocket），
上传后返回文件 URL，再通过 WebSocket 消息引用
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
import os

router = APIRouter()

UPLOAD_DIR = "/tmp/uploads"
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
```

**权衡说明**：
- 语音情绪线索（停顿、置信度）作为辅助信号而非主要依据——Whisper 的这些指标不够精确，但可以提供额外参考
- TTS 声音选择根据场景切换——放松练习用更柔和的声音，日常对话用温暖但清晰的声音
- 图片分析用 Haiku 而非主模型——图片描述是辅助任务，不需要最强模型；主模型负责基于描述做情感回应
- 文件上传走 REST 而非 WebSocket——大文件二进制传输 REST 更可靠，WebSocket 只传引用 URL

---

## 四、数据文件规划

### 4.1 量表题库 `data/scales/phq9.json`（示例）

```json
{
  "name": "PHQ-9",
  "full_name": "Patient Health Questionnaire-9",
  "description": "抑郁症状筛查量表",
  "items": [
    {"id": 1, "text": "做事时提不起劲或没有兴趣"},
    {"id": 2, "text": "感到心情低落、沮丧或绝望"},
    {"id": 3, "text": "入睡困难、睡不安稳或睡眠过多"},
    {"id": 4, "text": "感觉疲倦或没有活力"},
    {"id": 5, "text": "食欲不振或吃太多"},
    {"id": 6, "text": "觉得自己很糟或觉得自己很失败"},
    {"id": 7, "text": "对事物专注有困难"},
    {"id": 8, "text": "动作或说话速度变慢/坐立不安"},
    {"id": 9, "text": "有不如死掉或用某种方式伤害自己的念头"}
  ],
  "options": [
    {"value": 0, "label": "完全不会"},
    {"value": 1, "label": "好几天"},
    {"value": 2, "label": "一半以上的天数"},
    {"value": 3, "label": "几乎每天"}
  ],
  "scoring": {
    "0-4": "无抑郁",
    "5-9": "轻度抑郁",
    "10-14": "中度抑郁",
    "15-19": "中重度抑郁",
    "20-27": "重度抑郁"
  },
  "note": "第9题涉及自伤/自杀意念，无论总分如何，该题得分>0需触发安全守护"
}
```

### 4.2 危机关键词库 `data/keywords/crisis_keywords.json`

```json
{
  "critical": ["自杀", "结束生命", "不想活", "跳楼", "割腕", "吞药", "上吊", "遗书", "死了算了", "去死"],
  "high": ["自伤", "自残", "没有希望", "活着没意义", "不如死了", "生不如死", "绝望", "想消失"],
  "medium": ["失眠很久", "吃不下饭", "不想出门", "酗酒", "没有朋友", "被孤立", "很久没开心", "崩溃"]
}
```

---

### Phase 5：Docker 部署（新增）

**目标**：一键启动整个服务栈，开发和生产环境一致。

#### 5.1 后端 Dockerfile `server/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（音频处理需要 ffmpeg）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 数据目录（挂载卷）
RUN mkdir -p /app/data/memory /app/data/uploads

EXPOSE 8000

# uvicorn 启动，支持热重载（开发）和多 worker（生产）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 5.2 Docker Compose 编排 `docker-compose.yml`

```yaml
version: "3.8"

services:
  server:
    build: ./server
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMADB_HOST=chromadb
      - CHROMADB_PORT=8001
      - DATABASE_URL=sqlite:///data/profiles.db
      - UPLOAD_DIR=/app/data/uploads
      - ENV=production
    volumes:
      - server_data:/app/data          # SQLite + 上传文件持久化
      - upload_tmp:/app/data/uploads   # 临时上传文件
    depends_on:
      chromadb:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma     # 向量数据持久化
    environment:
      - ANONYMIZED_TELEMETRY=false     # 关闭遥测（隐私）
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 15s
      timeout: 5s
      retries: 3

volumes:
  server_data:
  chroma_data:
  upload_tmp:
```

#### 5.3 环境变量管理 `.env.example`

```bash
# === 必填 ===
ANTHROPIC_API_KEY=sk-ant-xxx          # Claude API（主模型 + Haiku）
OPENAI_API_KEY=sk-xxx                  # Whisper STT + TTS

# === 可选 ===
ENV=development                        # development | production
LOG_LEVEL=info                         # debug | info | warning | error
MAX_CONVERSATION_TURNS=50             # 单次会话最大轮数
TTS_PROVIDER=openai                    # openai | edge（免费降级）
```

#### 5.4 配置管理 `server/config.py`

```python
"""
统一配置管理——从环境变量读取，支持 .env 文件
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    openai_api_key: str = ""  # 多模态功能可选

    # 服务配置
    env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 8000

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001

    # 数据库
    database_url: str = "sqlite:///data/profiles.db"

    # 多模态
    tts_provider: str = "openai"  # openai | edge
    upload_dir: str = "/tmp/uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # 对话限制
    max_conversation_turns: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
```

**权衡说明**：
- ChromaDB 独立容器而非嵌入后端进程：独立容器方便数据持久化和独立扩展；嵌入模式虽然更简单，但容器重启会丢失内存中的索引
- SQLite 而非 PostgreSQL：用户画像数据量小、查询简单，SQLite 零运维；如果未来需要多实例部署再迁移 PostgreSQL
- ffmpeg 打包进镜像：Whisper 音频预处理需要 ffmpeg，虽然增加镜像体积约 80MB，但避免运行时依赖缺失
- `.env` 文件管理密钥而非硬编码：开发方便且不会误提交到 Git（.gitignore 排除）

---

## 五、关键权衡总结

| 决策点 | 选择 | 放弃的方案 | 理由 |
|--------|------|-----------|------|
| 整体架构 | 混合架构（规则+LLM） | 纯LLM / 纯规则 | 安全性和自然度的平衡 |
| Agent框架 | 自建循环 → 后期迁移LangGraph | CrewAI / OpenAI SDK | 情感场景需要深度安全控制 |
| LLM | Claude（主）+ Haiku（辅） | GPT-4o / 开源模型 | 安全性优先；Haiku降低分类任务成本 |
| 记忆 | ChromaDB + SQLite | FAISS / 云向量库 | 本地部署保护隐私；结构化+语义双存储 |
| 认知扭曲检测 | 关键词预筛 + LLM确认 | 纯关键词 / 纯LLM | 平衡准确率和API成本 |
| 策略路由 | 确定性规则引擎 | LLM自主决策 | 治疗策略需可预测、可审计 |
| 工具标准化 | 内部工具直接调用（不引入MCP） | MCP标准化 / 一开始就用MCP | 情感Agent工具高度定制且涉及隐私，MCP跨应用共享无价值，徒增复杂度（审计否决） |
| 对话风格 | 提示词引导（非硬编码） | 决策树对话 | 保留LLM灵活性，避免对话生硬 |
| 危机检测 | 关键词+Haiku语义双层 | 纯关键词匹配 | 纯关键词漏掉隐喻、误报引用（批注1） |
| 评估时机 | 后台非侵入式监控 | 每轮强制工具调用 | 避免"过早干预"导致对话断层（批注2） |
| 扭曲反馈 | 去专业化日常语言 | 直接告知扭曲标签 | 标签化会被感知为评判，产生阻抗（批注3） |
| 记忆管理 | 用户可查看/删除+时间衰减 | 只存不删 | 心理数据敏感，需"被遗忘权"（批注4） |
| 关系监测 | Alliance监测+破裂修复 | 不监测 | 忽略关系质量会导致用户流失（批注5） |
| 弥散性情绪 | 倾听优先模式（DIFFUSE阶段） | 强行分类到15种扭曲 | 真实痛苦是弥散性的，强行归类会让Agent变成"纠错机器"（批注6） |
| 关系建模 | 关系状态机（移情/依赖/敌意） | 静态用户画像 | 用户对Agent的情感投射是动态的，静态标签无法应对（批注7） |
| 危机转接 | 多轮情绪抱持（四阶段渐进过渡） | 弹热线号码+断开 / 一次性三阶段文本 | 一次性固定文本仍是"弃舰"，多轮陪伴建立信任后转介接受率更高（审计修正） |
| 输出审核 | 规则引擎 + 高风险用户Haiku审核 | 全量Haiku审核 / 仅关键词过滤 | 规则引擎覆盖80%有害模式，Haiku仅对高风险用户启用以控制成本（审计修正） |
| 前端框架 | React Native + Expo | Flutter / 原生开发 / PWA | 一套代码双端；Expo 原生模块覆盖多模态需求 |
| 后端框架 | Python FastAPI | Node.js / Python+Node 混合 | 与现有 Python 代码零迁移；原生 async + WebSocket |
| 实时通信 | WebSocket | HTTP 轮询 / SSE | 双向实时、支持服务端推送状态 |
| 语音输入 | Whisper API | 本地 Whisper / Web Speech API | 中文准确率 >95%；本地模型需 GPU |
| 语音输出 | OpenAI TTS + Edge TTS 降级 | 纯本地 TTS | 音质自然；Edge TTS 作为免费兜底 |
| 图片理解 | Claude Vision (Haiku) | GPT-4o Vision / 本地 BLIP-2 | 与主模型统一；Haiku 降低成本 |
| 部署方案 | Docker Compose | 裸机 / Kubernetes | 一键启动、环境一致；K8s 过度工程 |
| 状态管理 | Zustand | Redux / Context | 心理 App 状态简单，Zustand 更轻量 |

---

## 5.5 运行约束条件（审计新增）

### 5.5.1 成本控制

```python
# server/config.py 中新增
COST_LIMITS = {
    "daily_budget_usd": 10.0,           # 每日成本预算
    "alert_threshold_usd": 8.0,         # 告警阈值
    "haiku_calls_per_user_per_day": 50,  # 单用户每日 Haiku 调用上限
}

# 自适应降级策略（按优先级依次关闭）：
# 1. 关闭叙事摘要的 LLM 生成（改用规则引擎）
# 2. 关闭元认知监视器的 Haiku 层（仅保留规则引擎）
# 3. 关闭 Haiku 语义确认（危机检测退化为纯关键词）
# 注意：主对话的 Sonnet 调用永远不降级
```

### 5.5.2 并发限制

```python
# server/config.py 中新增
CONCURRENCY_LIMITS = {
    "max_concurrent_llm_calls": 5,       # 最大并发 LLM 调用
    "max_websocket_connections": 100,     # 最大 WebSocket 连接数
    "request_queue_size": 200,           # 请求队列大小
    "queue_timeout_seconds": 30,         # 队列超时
}

# 优先级调度：crisis_holding.active == True 的用户优先出队
# 实现：asyncio.PriorityQueue，危机用户 priority=0，普通用户 priority=1
```

### 5.5.3 数据隐私

```
- 对话记录保留期：90 天（超期自动删除，定时任务每日凌晨执行）
- 敏感数据加密：SQLite 使用 SQLCipher 加密存储
- ChromaDB 备份：每日增量备份到本地 backup/ 目录，保留最近 7 天
- 访问控制：每个 API 请求必须携带 JWT，user_id 从 token 中提取（不信任客户端传参）
- "被遗忘权"：除 Agent Tool Use 外，在设置页面提供显式的"数据管理"UI 菜单
- 审计日志：记录所有数据访问和删除操作到独立的 audit.log
```

### 5.5.4 错误恢复与降级

```python
# 所有 LLM 调用的统一错误处理策略
LLM_RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_base_seconds": 1,           # 指数退避：1s, 2s, 4s
    "timeout_seconds": 30,
}

# 各模块降级策略（fail-safe 原则）：
FALLBACK_STRATEGIES = {
    "crisis_detection":  "assume_high",   # 危机检测失败 → 假设 HIGH 风险（宁可过度保护）
    "emotion_assessment": "use_previous", # 情绪评估失败 → 使用上次的情绪状态
    "strategy_planner":  "listen_mode",   # 干预策略失败 → 回退到纯倾听模式
    "meta_monitor":      "pass_through",  # 元认知监视器失败 → 静默放行（规则引擎已通过）
    "narrative_summary": "rule_engine",   # 叙事摘要失败 → 用规则引擎生成模板摘要
}
```

### 5.5.5 会话超时

```python
TIMEOUT_CONFIG = {
    "idle_timeout_minutes": 30,          # 空闲超时：30分钟无消息断开
    "max_session_hours": 2,              # 最大连接时长：2小时
    "warning_before_disconnect_minutes": 5,  # 断开前5分钟提醒
}
# 超时消息："你已经休息了一会儿了。如果还想聊，随时回来，我一直都在。"
# 注意：危机抱持模式下不执行超时断开
```

### 5.5.6 用户依赖防护

```
- 依赖检测规则：连续 7 天每天使用 > 5 轮对话 → 标记为 dependent
- 干预策略：
  - 每周一次温和提醒："我是 AI 助手，专业的心理咨询师能给你更深入的帮助"
  - 提供专业咨询师推荐列表（本地化资源）
  - 不设硬限制（强制断开可能对脆弱用户造成伤害），但在 UI 中显示使用时长统计
```

### 5.5.7 模型幻觉约束

```python
# 在 _post_safety_check 中扩展禁止模式列表
FORBIDDEN_PATTERNS = {
    # 原有
    "停药": "用药问题请咨询你的医生",
    "减少药量": "用药调整需要医生指导",
    "不需要看医生": "专业帮助是很有价值的",
    "你有抑郁症": "我无法做出诊断",
    # 新增（审计补充）
    "诊断为": "我无法提供医学诊断，建议咨询专业医生",
    "处方": "用药问题请咨询你的医生",
    "替代疗法": "治疗方案请与专业医生讨论",
    "你的病": "我不是医生，无法判断疾病",
}
```

### 5.5.8 危机强制转介

```python
# 在 CrisisHolding 类中新增强制转介逻辑
class CrisisHolding:
    # ... 原有代码 ...

    def check_forced_referral(self, user_message: str) -> bool:
        """
        判断是否需要强制转介（超出 AI 能力范围的即刻危险）

        触发条件（任一）：
        - 用户明确表示有自杀计划且有手段（"我已经准备好了药/绳子"）
        - 用户在 RESOURCES 阶段连续 3 轮拒绝拨打热线
        - 用户表示即刻危险（"我现在就要去做"）

        强制转介行为：
        - 不停止对话（停止 = 抛弃），但切换到纯资源提供模式
        - 每条回复都附带热线信息
        - 前端显示置顶的紧急求助横幅（CrisisBanner 常驻）
        - 记录事件到 audit.log 用于后续跟进
        """
        immediate_danger_keywords = [
            "我现在就", "我已经准备好", "今晚就", "马上就去",
            "已经买了", "已经写好遗书",
        ]
        return any(kw in user_message for kw in immediate_danger_keywords)
```

---

## 六、实现优先级与依赖关系

```
Phase 0.5（前后端骨架）——新增
├── [P0] server/config.py              ← 零依赖，最先实现
├── [P0] server/main.py                ← FastAPI 入口
├── [P0] server/api/routes_chat.py     ← WebSocket 路由
├── [P1] app/ 初始化                    ← Expo 项目脚手架
├── [P1] app/services/websocket.ts     ← WebSocket 客户端
└── [P1] app/app/chat/[id].tsx         ← 聊天页面骨架

Phase 1（安全底座+骨架）
├── [P0] server/safety/crisis_detector.py    ← 最先实现，零依赖
├── [P0] server/safety/resources.py          ← 零依赖
├── [P0] server/agent/prompts.py             ← 零依赖
├── [P1] server/agent/tools.py               ← 零依赖
├── [P1] server/agent/loop.py                ← 依赖 safety + tools
└── [P1] 前后端联调                           ← 依赖 Phase 0.5 + agent/loop

Phase 2（评估+干预）
├── [P2] server/assessment/emotion.py        ← 依赖 Anthropic API
├── [P2] server/assessment/distortion.py     ← 零依赖（关键词部分）
├── [P2] server/intervention/strategy_planner.py ← 依赖 assessment
├── [P3] server/intervention/cbt/*           ← 依赖 strategy_planner
├── [P3] server/intervention/positive/*      ← 依赖 strategy_planner
├── [P3] server/assessment/scales.py         ← 依赖 data/scales/
├── [P3] server/assessment/state_tracker.py  ← 依赖 emotion + distortion
└── [P3] app/components/ExerciseCard.tsx     ← 练习卡片 UI

Phase 3（记忆+个性化）
├── [P4] server/memory/semantic.py           ← 依赖 ChromaDB
├── [P4] server/memory/user_profile.py       ← 依赖 SQLite
├── [P4] server/memory/conversation.py       ← 依赖 semantic + profile
├── [P5] server/knowledge/*                  ← 内容填充
└── [P5] app/app/history.tsx                 ← 历史会话 UI

Phase 4（多模态）——新增
├── [P6] server/multimodal/stt.py            ← 依赖 Whisper API + ffmpeg
├── [P6] server/multimodal/tts.py            ← 依赖 OpenAI TTS / Edge TTS
├── [P6] server/multimodal/vision.py         ← 依赖 Claude Vision
├── [P6] server/api/routes_multimodal.py     ← 文件上传路由
├── [P7] app/components/VoiceRecorder.tsx    ← 语音录制 UI
└── [P7] app/components/ImagePicker.tsx      ← 图片选择 UI

Phase 5（Docker 部署）——新增
├── [P8] server/Dockerfile                   ← 后端容器化
├── [P8] docker-compose.yml                  ← 服务编排
├── [P8] .env.example                        ← 环境变量模板
└── [P8] app/ Expo 构建配置                   ← EAS Build 原生包
```

---


---

## 八、依赖清单 `requirements.txt`

```
anthropic>=0.40.0        # Claude API
chromadb>=0.5.0          # 向量记忆
fastapi>=0.115.0         # Web 框架
uvicorn[standard]>=0.30.0 # ASGI 服务器
pydantic-settings>=2.0.0 # 配置管理（从环境变量读取）
python-multipart>=0.0.9  # FastAPI 文件上传依赖
httpx>=0.27.0            # 异步 HTTP 客户端（Whisper/TTS API 调用）
edge-tts>=6.1.0          # 免费 TTS 降级方案（Phase 4）
```

---

---
## 九、测试策略

安全模块的测试是最高优先级——必须在任何其他功能之前通过。

```python
# tests/test_safety.py（示例）

def test_critical_risk_detection():
    """紧急风险必须100%检出"""
    critical_texts = [
        "我不想活了",
        "我想结束生命",
        "我准备跳楼",
    ]
    for text in critical_texts:
        result = detect_crisis(text)
        assert result.level == RiskLevel.CRITICAL, f"未检出紧急风险: {text}"

def test_low_risk_no_false_positive():
    """正常对话不应误报"""
    normal_texts = [
        "今天工作有点累",
        "和朋友吵了一架",
        "考试没考好，有点失落",
    ]
    for text in normal_texts:
        result = detect_crisis(text)
        assert result.level == RiskLevel.LOW, f"误报: {text}"

def test_distortion_detection_accuracy():
    """认知扭曲检测的基本准确性"""
    test_cases = [
        ("我永远都做不好任何事", "全或无思维"),
        ("他肯定觉得我很蠢", "读心术"),
        ("这次面试肯定会搞砸", "预言家谬误"),
    ]
    for text, expected in test_cases:
        results = detect_distortion(text)
        detected_types = [r.distortion_type for r in results]
        assert expected in detected_types, f"未检出 {expected}: {text}"
```

### 边缘案例清单

| 场景 | 预期行为 | 测试覆盖 |
|------|----------|----------|
| 用户用隐晦方式表达自杀意念（如"我想永远睡过去"） | 语义分类识别为HIGH+风险 | test_subtle_crisis |
| 用户讨论他人的自杀（如"我朋友说想自杀"） | 语义分类标记is_first_person=false，提供资源但不误判为用户本人危机 | test_third_party_crisis |
| 用户引用影视作品（如"电影里那个人跳楼了"） | 关键词命中但语义降级为MEDIUM，不强制中断对话 | test_media_reference |
| 用户在积极语境中使用负面关键词（如"我总是很开心"） | 不误报为认知扭曲 | test_positive_context |
| 用户快速切换情绪（上一句开心，下一句崩溃） | 以最新状态为准，但记录波动 | test_emotion_shift |
| 用户拒绝Agent的干预建议（如"别跟我说这些"） | 立即停止当前策略，回到倾听模式（批注5） | test_user_autonomy |
| 用户对Agent表达不满（如"你根本不懂我"） | 触发联盟修复：道歉+调整策略（批注5） | test_alliance_rupture |
| 用户要求删除自己的记忆数据 | 执行删除并确认（批注4） | test_memory_deletion |
| 用户在哭诉中，Agent不应主动启动练习 | 后台评估仅供参考，LLM优先共情倾听（批注2） | test_no_premature_intervention |
| 超长文本输入（>2000字） | 正常处理，不截断关键信息 | test_long_input |
| 用户使用方言或网络用语表达情绪 | 尽可能识别，降级为"需要澄清" | test_informal_language |
| 用户告别行为暗示（如"把猫托付给邻居了"） | 语义分类识别为HIGH风险 | test_farewell_behavior |
| 语音消息中用户在哭泣（Whisper 置信度低） | 附加情绪线索提示主模型，加强共情 | test_voice_crying |
| 语音转写失败或结果为空 | 友好提示"没听清，能再说一次吗"，不崩溃 | test_stt_failure |
| 用户发送无关图片（如风景照、表情包） | 正常描述，不强行做情绪分析 | test_irrelevant_image |
| 用户发送含敏感内容的图片（自伤照片） | 触发安全守护，提供危机资源 | test_sensitive_image |
| WebSocket 断线重连后消息丢失 | 重连后从服务端恢复最近对话历史 | test_ws_reconnect |
| TTS 服务不可用（OpenAI + Edge 都失败） | 降级为纯文字回复，不阻塞对话 | test_tts_fallback |

---

## 附录：Agent 系统流程图（2026-03-12 更新）

### Agent 整体架构流程图

```
┌──────────────────────────────────────────────────────────────────────┐
│                      📱 Expo 移动端 (React Native)                   │
│                  用户输入 → WebSocket 发送消息                        │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ ws://server:8000/ws/{session_id}
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FastAPI 服务器 (main.py)                           │
│   路由: /ws/chat  /api/auth  /api/history  /api/mood  /api/multimodal│
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌══════════════════════════════════════════════════════════════════════┐
║                  Agent 主循环 (loop.py::run_agent)                   ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────┐       ║
║  │ Step 1: 安全前置检查                                      │       ║
║  │   ├─ 关键词快速扫描 (零延迟)                              │       ║
║  │   └─ 语义分类确认 (轻量LLM)                               │       ║
║  │       → risk_level: CRITICAL / HIGH / MEDIUM / LOW        │       ║
║  └──────────────────────────┬───────────────────────────────┘       ║
║                              │                                       ║
║                    ┌─────────┴─────────┐                            ║
║                    │ CRITICAL危机?      │                            ║
║                    └─────┬────────┬────┘                            ║
║                     YES  │        │ NO                               ║
║                          ▼        ▼                                  ║
║  ┌──────────────────┐  ┌───────────────────────────────────┐       ║
║  │ 危机抱持模式      │  │ Step 2: 后台异步评估 (不阻塞)     │       ║
║  │ (CrisisHolding)  │  │   ├─ 情绪评估 (emotion+intensity) │       ║
║  │                   │  │   └─ 认知扭曲检测 (15种)          │       ║
║  │ 四阶段:           │  └──────────────┬────────────────────┘       ║
║  │ 1.HOLDING 陪伴    │                 │                             ║
║  │ 2.GROUNDING 锚定  │                 ▼                             ║
║  │ 3.BRIDGING 桥接   │  ┌───────────────────────────────────┐       ║
║  │ 4.RESOURCES 资源  │  │ Step 3: 上下文富化 (6层注入)       │       ║
║  │                   │  │   1. 安全风险提示                   │       ║
║  │ 禁用所有工具      │  │   2. 后台评估结果                   │       ║
║  │ 纯文本陪伴        │  │   3. 治疗联盟监测 (关系破裂信号)   │       ║
║  └────────┬──────────┘  │   4. 叙事记忆 (情感弧线)           │       ║
║           │              │   5. 用户画像 + 关系状态机          │       ║
║           │              │   6. 知识库语义检索                 │       ║
║           │              └──────────────┬────────────────────┘       ║
║           │                             │                            ║
║           │                             ▼                            ║
║           │   ┌═══════════════════════════════════════════════┐      ║
║           │   ║  Step 4: LLM 推理 + 工具调用循环              ║      ║
║           │   ║                                               ║      ║
║           │   ║  LLM (Claude Sonnet via OpenRouter)           ║      ║
║           │   ║       │                                       ║      ║
║           │   ║       ├── stop_reason = "tool_use"?           ║      ║
║           │   ║       │     YES → 执行工具 → 结果回注 → 继续  ║      ║
║           │   ║       │                                       ║      ║
║           │   ║       │   ┌─────────────────────────────┐    ║      ║
║           │   ║       │   │ 8个可用工具:                 │    ║      ║
║           │   ║       │   │  assess_emotion     情绪评估 │    ║      ║
║           │   ║       │   │  detect_distortion  扭曲检测 │    ║      ║
║           │   ║       │   │  get_strategy       干预策略 │    ║      ║
║           │   ║       │   │  run_scale          量表评估 │    ║      ║
║           │   ║       │   │  retrieve_history   历史检索 │    ║      ║
║           │   ║       │   │  guide_exercise     心理练习 │    ║      ║
║           │   ║       │   │  manage_memory      记忆管理 │    ║      ║
║           │   ║       │   │  search_knowledge   知识搜索 │    ║      ║
║           │   ║       │   └─────────────────────────────┘    ║      ║
║           │   ║       │                                       ║      ║
║           │   ║       └── stop_reason = "end_turn"?           ║      ║
║           │   ║             YES → 进入下一步                  ║      ║
║           │   ╚═══════════════════════════════════════════════╝      ║
║           │                             │                            ║
║           ▼                             ▼                            ║
║  ┌───────────────────────────────────────────────────────────┐      ║
║  │ Step 5: 元认知监视 (防有害回复)                            │      ║
║  │   第一层: 规则引擎 (零成本)                                │      ║
║  │     ├─ 顺从性检测 ("你说得对,确实没救")                    │      ║
║  │     ├─ 过度承诺 ("我保证你会好起来")                       │      ║
║  │     └─ 隐性诊断 ("你可能有抑郁症")                        │      ║
║  │   第二层: 语义审核 (仅高风险用户,轻量模型)                │      ║
║  └──────────────────────────┬────────────────────────────────┘      ║
║                              │                                       ║
║                              ▼                                       ║
║  ┌───────────────────────────────────────────────────────────┐      ║
║  │ Step 6: 输出安全审核                                       │      ║
║  │   禁止: 停药建议、减少药量、不看医生建议                   │      ║
║  │   触发时 → 自动追加医学免责声明                            │      ║
║  └──────────────────────────┬────────────────────────────────┘      ║
╚═════════════════════════════╪════════════════════════════════════════╝
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  返回结果:                                                            │
│  { text: "回复内容", emotion: {primary, intensity}, crisis: bool }   │
│                                                                      │
│  → 保存到 SQLite → WebSocket 发送给客户端                             │
└──────────────────────────────────────────────────────────────────────┘
```

### 支撑模块关系图

```
                        ┌─────────────┐
                        │  Agent 循环  │
                        └──────┬──────┘
           ┌───────────────────┼───────────────────┐
           │                   │                   │
     ┌─────▼─────┐     ┌──────▼──────┐    ┌──────▼──────┐
     │  安全模块   │     │  记忆系统    │    │  知识库      │
     │            │     │             │    │             │
     │ 危机检测   │     │ 语义记忆    │    │ JSON关键词  │
     │ (2阶段)   │     │ (ChromaDB)  │    │ +           │
     │            │     │             │    │ ChromaDB    │
     │ 危机抱持   │     │ 叙事记忆    │    │ 向量搜索    │
     │ (4阶段)   │     │ (情感弧线)  │    │             │
     │            │     │             │    │ CBT理论     │
     │ 元认知监视 │     │ 用户画像    │    │ 积极心理学  │
     │ (2层)     │     │ +关系状态机  │    │ 真实幸福    │
     └───────────┘     └─────────────┘    └─────────────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
                     ┌─────────▼─────────┐
                     │  LLM 多Provider   │
                     │                   │
                     │ 主力: Claude Sonnet│
                     │ (via OpenRouter)  │
                     │                   │
                     │ 轻量: DeepSeek v3 │
                     │ (后台评估/检测)   │
                     └───────────────────┘
```

### 核心设计要点

1. **两阶段安全检测** — 关键词快扫(零延迟) + 语义确认(轻量LLM)，CRITICAL时进入危机抱持模式，禁用所有工具
2. **6层上下文富化** — 每次回复前注入安全提示、评估结果、治疗联盟、叙事记忆、用户画像、知识库
3. **LLM工具循环** — 模型自主决定是否调用8个工具，工具结果回注后继续推理
4. **双层输出审核** — 元认知监视(规则+语义) + 输出安全审核(禁止医疗建议)
5. **成本分层** — 核心推理用Claude Sonnet，后台任务用DeepSeek，规则引擎零成本

---

## Phase 4：上下文管理优化——压缩 + 结构化笔记 + 多Agent架构

> 日期：2026-03-15
> 目标：解决长对话中上下文窗口膨胀问题，让Agent在多轮深度咨询中保持高质量回复
> 三大核心技术：对话压缩、结构化外部记忆、多Agent隔离上下文

### 问题分析

当前架构的上下文瓶颈：

| 问题 | 现状 | 影响 |
|------|------|------|
| 对话历史线性增长 | `conversation_history` 全量传入LLM | 20轮后token爆炸，成本翻倍 |
| 6层上下文同时注入 | 画像+叙事+策略+知识库+安全+关系 全部拼入system prompt | 有效信息被稀释，LLM注意力分散 |
| 工具循环结果堆积 | 工具返回的评估/检测结果留在messages中 | 重复的工具结果占用大量token |
| 无跨会话压缩 | 每次新会话从零开始 | 无法利用历史咨询摘要 |

---

### 4.1 技术一：对话压缩（Conversation Compression）

**核心思路**：保留最近N轮原始对话，将更早的对话压缩为结构化摘要。

#### 4.1.1 滑动窗口 + 渐进式摘要

```
对话轮次：[1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12]
                                          ↑
                              压缩分界线（保留最近6轮原始）

压缩区 [1-6] → 结构化摘要          原始区 [7-12] → 完整保留
```

**压缩策略**：

```python
# server/context/compressor.py

class ConversationCompressor:
    """对话历史压缩器——滑动窗口 + LLM摘要"""

    KEEP_RECENT = 6          # 保留最近6轮原始对话
    COMPRESS_THRESHOLD = 10  # 超过10轮触发压缩

    async def compress_if_needed(
        self, messages: list[dict], session_id: str
    ) -> list[dict]:
        """
        检查是否需要压缩，需要则压缩早期对话。
        返回：压缩后的消息列表（摘要 + 最近N轮原始）
        """
        turn_count = sum(1 for m in messages if m["role"] == "user")
        if turn_count <= self.COMPRESS_THRESHOLD:
            return messages  # 不需要压缩

        # 分割：早期消息 vs 最近消息
        split_idx = self._find_split_point(messages, self.KEEP_RECENT)
        early_messages = messages[:split_idx]
        recent_messages = messages[split_idx:]

        # 用轻量模型压缩早期对话
        summary = await self._summarize(early_messages, session_id)

        # 拼接：摘要消息 + 最近原始消息
        compressed = [
            {"role": "user", "content": f"[前序对话摘要]\n{summary}"},
            {"role": "assistant", "content": "我已了解之前的对话内容，让我们继续。"},
        ] + recent_messages

        return compressed

    async def _summarize(self, messages: list, session_id: str) -> str:
        """用轻量LLM生成结构化摘要"""
        # 调用 DeepSeek（轻量模型）生成摘要
        prompt = """请将以下心理咨询对话压缩为结构化摘要，保留：
1. 用户提到的核心问题和情绪状态
2. 咨询师已采用的干预方法和用户反应
3. 重要的事实信息（人物、事件、时间）
4. 用户的洞察和转变时刻
不要遗漏任何治疗性重要信息。"""

        result = await _llm_chat(
            system=prompt,
            messages=messages,
            model_override=get_light_model(),  # 用DeepSeek压缩，省成本
        )
        return result["text"]
```

#### 4.1.2 工具结果压缩

工具循环中产生的中间结果（情绪评估、认知扭曲检测）在使用后压缩：

```python
def compress_tool_results(messages: list) -> list:
    """压缩已处理的工具调用结果，保留关键信息"""
    compressed = []
    for msg in messages:
        if msg["role"] == "tool" or (
            isinstance(msg.get("content"), list)
            and any(c.get("type") == "tool_result" for c in msg["content"] if isinstance(c, dict))
        ):
            # 将冗长的工具结果压缩为一行摘要
            compressed.append({
                "role": msg["role"],
                "content": _extract_tool_summary(msg["content"])
            })
        else:
            compressed.append(msg)
    return compressed
```

#### 4.1.3 集成点

修改 `agent/loop.py` 的 `run_agent()`：

```python
# 在构建 messages 之前
compressor = ConversationCompressor()
compressed_history = await compressor.compress_if_needed(
    conversation_history, session_id
)
messages = compressed_history + [{"role": "user", "content": user_message}]
```

---

### 4.2 技术二：结构化笔记（Structured Notes）

**核心思路**：将分散的上下文信息统一为结构化的"会话笔记"，按需加载而非全量注入。

#### 4.2.1 统一的会话笔记系统

将现有的6层上下文整合为一个结构化的 `SessionNotes` 对象：

```python
# server/context/session_notes.py

@dataclass
class SessionNotes:
    """结构化会话笔记——LLM的外部工作记忆"""

    # --- 用户层（跨会话持久）---
    user_profile_summary: str          # 一句话用户画像
    relationship_state: str            # 关系状态（normal/dependent/hostile）
    narrative_trend: str               # 情感趋势（improving/stable/worsening）
    historical_themes: list[str]       # 历史咨询主题

    # --- 会话层（单次会话）---
    presenting_issue: str              # 本次核心议题
    session_strategy: str              # 当前策略摘要
    key_moments: list[str]            # 本次对话关键时刻
    interventions_used: list[str]      # 已使用的干预

    # --- 实时层（当前轮次）---
    safety_level: str                  # 当前安全等级
    recent_emotion: str                # 最近检测的情绪
    active_distortions: list[str]      # 活跃的认知扭曲

    def to_compact_prompt(self) -> str:
        """生成紧凑的上下文提示（目标 <500 token）"""
        lines = []
        if self.safety_level != "safe":
            lines.append(f"⚠️ 安全等级：{self.safety_level}")
        if self.user_profile_summary:
            lines.append(f"👤 {self.user_profile_summary}")
        if self.presenting_issue:
            lines.append(f"🎯 议题：{self.presenting_issue}")
        if self.session_strategy:
            lines.append(f"📋 策略：{self.session_strategy}")
        if self.narrative_trend and self.narrative_trend != "stable":
            lines.append(f"📈 趋势：{self.narrative_trend}")
        if self.key_moments:
            lines.append(f"💡 关键时刻：{'；'.join(self.key_moments[-3:])}")
        if self.active_distortions:
            lines.append(f"🔍 认知模式：{'、'.join(self.active_distortions)}")
        if self.relationship_state != "normal":
            lines.append(f"🤝 关系注意：{self.relationship_state}")
        return "\n".join(lines)
```

#### 4.2.2 笔记更新机制

每轮对话结束后，异步更新笔记（不阻塞回复）：

```python
class NotesUpdater:
    """异步笔记更新器——每轮对话后台更新"""

    async def update_after_turn(
        self, notes: SessionNotes,
        user_msg: str, assistant_msg: str,
        tool_results: dict | None
    ) -> SessionNotes:
        """根据本轮对话内容增量更新笔记"""

        # 规则引擎更新（零成本）
        if tool_results:
            if "emotion" in tool_results:
                notes.recent_emotion = tool_results["emotion"]["primary"]
            if "distortions" in tool_results:
                notes.active_distortions = [
                    d["type"] for d in tool_results["distortions"]
                    if d["confidence"] > 0.6
                ]

        # 关键时刻检测（轻量LLM，每5轮执行一次）
        if self._should_detect_moments():
            moment = await self._detect_key_moment(user_msg, assistant_msg)
            if moment:
                notes.key_moments.append(moment)
                # 保留最近5个关键时刻
                notes.key_moments = notes.key_moments[-5:]

        return notes
```

#### 4.2.3 对比：当前 vs 优化后

| 维度 | 当前（6层全量注入） | 优化后（结构化笔记） |
|------|---------------------|---------------------|
| System prompt 长度 | ~2000-3000 token | ~300-500 token |
| 信息组织 | 无结构拼接 | 分层结构化 |
| 更新方式 | 每轮全量重新生成 | 增量更新 |
| 按需加载 | 不支持 | 按安全等级/阶段动态裁剪 |

---

### 4.3 技术三：多Agent架构（Multi-Agent with Isolated Context）

**核心思路**：将深度分析任务分发给专门的子Agent，每个子Agent用干净的上下文窗口处理聚焦任务，只返回精炼摘要给主Agent。

#### 4.3.1 架构设计

```
用户消息
    ↓
┌─────────────────────────────────────────────┐
│  主Agent（Orchestrator）                      │
│  上下文：system_prompt + session_notes        │
│         + 最近6轮对话 + 压缩摘要              │
│  职责：编排协调、生成最终回复                    │
│                                               │
│  根据需要分发任务 ↓                            │
├─────────┬──────────┬──────────┬──────────────┤
│ 子Agent1 │ 子Agent2  │ 子Agent3 │ 子Agent4      │
│ 安全评估  │ 深度分析  │ 知识检索  │ 策略规划      │
│          │          │          │              │
│ 输入:     │ 输入:     │ 输入:     │ 输入:         │
│ 当前消息  │ 最近3轮   │ 用户问题  │ 议题+阶段     │
│ 关键词库  │ 用户画像  │ ChromaDB │ 历史策略      │
│          │          │          │              │
│ 输出:     │ 输出:     │ 输出:     │ 输出:         │
│ risk_level│ 1段摘要   │ top3片段  │ 策略JSON      │
│ (~50 tok) │ (~200 tok)│ (~300 tok)│ (~150 tok)   │
└──────────┴──────────┴──────────┴──────────────┘
                    ↓
        精炼结果注入主Agent上下文（~700 token）
                    ↓
            主Agent生成最终回复
```

#### 4.3.2 子Agent定义

```python
# server/context/sub_agents.py

class SubAgentOrchestrator:
    """子Agent编排器——按需分发深度任务"""

    async def dispatch(
        self, user_msg: str, notes: SessionNotes,
        recent_messages: list
    ) -> dict[str, str]:
        """并行分发子Agent任务，收集精炼结果"""
        tasks = {}

        # 1. 安全评估——每轮必须（但已经是规则引擎，成本为零）
        # 保持现有 detect_crisis() 不变

        # 2. 深度分析——仅当检测到复杂情绪模式时
        if self._needs_deep_analysis(user_msg, notes):
            tasks["analysis"] = self._run_analysis_agent(
                user_msg, recent_messages[-6:], notes.user_profile_summary
            )

        # 3. 知识检索——仅当涉及具体心理议题时
        if self._needs_knowledge(user_msg, notes):
            tasks["knowledge"] = self._run_knowledge_agent(
                user_msg, notes.presenting_issue
            )

        # 4. 策略规划——仅在会话初期或议题转换时
        if self._needs_strategy_update(notes):
            tasks["strategy"] = self._run_strategy_agent(
                notes.presenting_issue, notes.interventions_used
            )

        # 并行执行所有子Agent
        if tasks:
            results = await asyncio.gather(
                *tasks.values(), return_exceptions=True
            )
            return {
                k: v for k, v in zip(tasks.keys(), results)
                if not isinstance(v, Exception)
            }
        return {}

    async def _run_analysis_agent(
        self, user_msg: str, recent: list, profile: str
    ) -> str:
        """深度分析子Agent——独立上下文，只返回摘要"""
        system = (
            "你是心理分析专家。分析用户的情绪模式和认知特征。\n"
            f"用户画像：{profile}\n"
            "请输出一段不超过100字的分析摘要，包含：\n"
            "1. 主要情绪及强度\n"
            "2. 可能的认知扭曲\n"
            "3. 建议的回应方向"
        )
        # 子Agent只看最近几轮 + 用户画像，上下文干净
        result = await _llm_chat(
            system=system,
            messages=recent + [{"role": "user", "content": user_msg}],
            model_override=get_light_model(),  # 轻量模型
            max_tokens=200,
        )
        return result["text"]

    async def _run_knowledge_agent(
        self, query: str, issue: str
    ) -> str:
        """知识检索子Agent——隔离的检索+排序"""
        from knowledge.knowledge_base import search_books_semantic
        results = search_books_semantic(f"{issue} {query}", max_results=5)

        if not results:
            return ""

        # 用轻量模型从5条中精选最相关的1-2条
        candidates = "\n".join(
            f"[{r['book']}·{r['chapter']}] {r['content'][:200]}"
            for r in results if r.get("similarity", 0) > 0.25
        )

        system = (
            "从以下心理学知识中，选出与用户问题最相关的1-2条，"
            "用自己的话重述要点（不超过150字）。"
            f"\n用户问题：{query}"
        )
        result = await _llm_chat(
            system=system,
            messages=[{"role": "user", "content": candidates}],
            model_override=get_light_model(),
            max_tokens=200,
        )
        return result["text"]

    def _needs_deep_analysis(self, msg: str, notes: SessionNotes) -> bool:
        """判断是否需要深度分析（避免不必要的LLM调用）"""
        # 闲聊/寒暄不需要
        if len(msg) < 15:
            return False
        # 已有活跃扭曲且情绪未变化时不需要
        if notes.active_distortions and notes.recent_emotion:
            return False
        return True

    def _needs_knowledge(self, msg: str, notes: SessionNotes) -> bool:
        """判断是否需要知识检索"""
        # 有明确心理议题时才检索
        return bool(notes.presenting_issue) and len(msg) > 20

    def _needs_strategy_update(self, notes: SessionNotes) -> bool:
        """判断是否需要更新策略"""
        return not notes.session_strategy
```

#### 4.3.3 关键优势：上下文隔离

| Agent | 上下文内容 | 大小 | 职责边界 |
|-------|-----------|------|---------|
| 主Agent | system + notes + 最近6轮 | ~2K tok | 共情回复、对话引导 |
| 分析Agent | 最近3轮 + 用户画像 | ~500 tok | 情绪模式识别 |
| 知识Agent | 检索结果 + 用户问题 | ~400 tok | 知识筛选排序 |
| 策略Agent | 议题 + 历史干预 | ~300 tok | 策略规划 |

每个子Agent不知道其他子Agent的存在，不会产生上下文污染。

---

### 4.4 三大技术协同工作流

```
用户发送消息
    │
    ▼
[1] 对话压缩器
    检查 conversation_history 长度
    超过10轮 → 压缩早期对话为摘要
    输出：compressed_messages（摘要 + 最近6轮）
    │
    ▼
[2] 结构化笔记加载
    从 DB 加载 SessionNotes
    生成 compact_prompt（<500 token）
    │
    ▼
[3] 子Agent编排（并行）
    ┌─ 安全检测（规则引擎，零成本）
    ├─ 深度分析（按需，轻量模型）
    ├─ 知识检索（按需，轻量模型）
    └─ 策略更新（按需，轻量模型）
    │
    收集精炼结果（~700 token）
    │
    ▼
[4] 主Agent推理
    上下文 = system_prompt
           + session_notes.compact_prompt  (~500 tok)
           + sub_agent_results             (~700 tok)
           + compressed_messages           (~3000 tok)
    总计 ≈ 4200 token（对比当前 8000-15000 token）
    │
    ▼
[5] 后台更新（异步，不阻塞回复）
    ├─ 更新 SessionNotes（增量）
    ├─ 更新叙事记忆
    └─ 持久化到 SQLite
```

---

### 4.5 实现路线

#### Phase 4a：对话压缩器（优先级最高，收益最大）
- 新建 `server/context/compressor.py`
- 修改 `agent/loop.py` 集成压缩器
- 压缩阈值和窗口大小可通过 `config.py` 配置

#### Phase 4b：结构化笔记
- 新建 `server/context/session_notes.py`
- 重构 `agent/loop.py` 中的6层上下文注入逻辑
- 迁移现有 context_hints 逻辑到 SessionNotes

#### Phase 4c：多Agent编排
- 新建 `server/context/sub_agents.py`
- 将现有的 `_background_assess()` 升级为子Agent
- 知识检索从直接注入改为子Agent预处理

#### 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `server/context/__init__.py` | context模块 |
| 新建 | `server/context/compressor.py` | 对话压缩器 |
| 新建 | `server/context/session_notes.py` | 结构化笔记 |
| 新建 | `server/context/sub_agents.py` | 子Agent编排 |
| 修改 | `server/agent/loop.py` | 集成三大技术 |
| 修改 | `server/config.py` | 新增配置项 |
| 新建 | `server/tests/test_context.py` | 上下文管理测试 |

#### 新增配置项

```python
# config.py 新增
COMPRESS_THRESHOLD: int = 10      # 触发压缩的对话轮数
KEEP_RECENT_TURNS: int = 6        # 保留最近N轮原始对话
NOTES_MAX_TOKENS: int = 500       # 笔记最大token数
SUB_AGENT_TIMEOUT: int = 5        # 子Agent超时（秒）
```

---

### 4.6 预期收益

| 指标 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| 20轮对话上下文大小 | ~15,000 tok | ~4,200 tok | **-72%** |
| System prompt 大小 | ~3,000 tok | ~500 tok | **-83%** |
| 信息利用效率 | 低（大量重复/无关） | 高（按需精炼） | 显著提升 |
| 子任务上下文污染 | 全部共享 | 完全隔离 | 消除 |
| LLM主调用成本 | 高 | 降低 | **-50%+** |
| 子Agent额外成本 | 无 | 轻量模型少量调用 | 可控（DeepSeek） |

---

### 4.7 必须处理的细节问题

---

#### 问题1：压缩可能丢失安全关键信息

如果用户在第2轮提到过自杀意念，到第12轮时被压缩掉，Agent会失去这个关键上下文。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `server/context/compressor.py` | 压缩器核心，安全过滤逻辑在此 |
| 复用 | `server/safety/crisis_detector.py` | 已有 `KEYWORD_RULES` 关键词库，压缩器应复用而非重建 |
| 修改 | `server/agent/loop.py:462` | 调用压缩器的入口（`messages = conversation_history + [...]` 之前） |

**完整代码片段**：

```python
# server/context/compressor.py

from safety.crisis_detector import KEYWORD_RULES  # 复用已有关键词库

class ConversationCompressor:
    KEEP_RECENT = 6
    COMPRESS_THRESHOLD = 10

    def __init__(self):
        # 从 crisis_detector 拉取安全关键词，保持单一数据源
        self._safety_keywords: set[str] = set()
        for rule in KEYWORD_RULES:
            self._safety_keywords.update(rule.get("keywords", []))

    def _is_safety_critical(self, msg: dict) -> bool:
        """检测消息是否包含安全关键信息"""
        content = msg.get("content", "")
        if not isinstance(content, str):
            return False
        return any(kw in content for kw in self._safety_keywords)

    async def compress_if_needed(
        self, messages: list[dict], session_id: str
    ) -> tuple[list[dict], str | None]:
        """
        返回 (处理后的消息列表, 摘要文本 or None)。
        安全关键消息永远保留原始内容，不进入压缩。
        """
        turn_count = sum(1 for m in messages if m["role"] == "user")
        if turn_count <= self.COMPRESS_THRESHOLD:
            return messages, None

        split_idx = self._find_split_point(messages, self.KEEP_RECENT)
        early = messages[:split_idx]
        recent = messages[split_idx:]

        # 安全消息提取——从早期消息中分离出安全关键消息
        safety_pinned = []
        compressible = []
        for msg in early:
            if self._is_safety_critical(msg):
                safety_pinned.append(msg)
            else:
                compressible.append(msg)

        # 只压缩非安全消息
        summary = await self._summarize(compressible, session_id)

        # 最终消息序列：安全关键消息（原始）+ 最近N轮（原始）
        # 摘要注入 system prompt（见问题8），不放在 messages 中
        return safety_pinned + recent, summary

    def _find_split_point(self, messages: list, keep_recent: int) -> int:
        """从后往前数 keep_recent 轮 user 消息，返回分割索引"""
        user_count = 0
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                user_count += 1
                if user_count >= keep_recent:
                    return i
        return 0

    async def _summarize(self, messages: list, session_id: str) -> str:
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        prompt = (
            "请将以下心理咨询对话压缩为结构化摘要，保留：\n"
            "1. 用户提到的核心问题和情绪状态\n"
            "2. 咨询师已采用的干预方法和用户反应\n"
            "3. 重要的事实信息（人物、事件、时间）\n"
            "4. 用户的洞察和转变时刻\n\n"
            "⚠️ 特别注意：如果对话中出现过任何自伤/自杀/危机相关内容，"
            "必须在摘要中明确标注'[安全标记]'，绝对不得遗漏。\n"
            "控制总长度在300字以内。"
        )
        result = await _llm_chat(
            system=prompt,
            messages=messages,
            model_override=get_light_model(),
            max_tokens=500,
        )
        return result["text"]
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 安全消息保留原始 + 摘要双写 | 零丢失风险，安全关键消息原样保留 | 安全消息多时，保留区膨胀抵消压缩效果 | **选这个** |
| B: 仅在摘要 prompt 中强调保留 | 实现简单，不需要分流逻辑 | 依赖LLM遵守指令，有遗漏风险（不可接受） | 不选 |
| C: 安全消息单独存一张表 | 结构清晰，可查询 | 增加 DB 复杂度，读取时需合并两个来源 | 过度设计 |

**风险评估**：方案A的"保留区膨胀"在实际场景中影响有限——一次会话中安全关键消息通常 ≤3 条（约200 token），远小于压缩节省的量。

---

#### 问题2：压缩摘要的持久化存储

当前 WebSocket 断开重连后，`_load_history()` 从 DB 加载所有原始消息。如果压缩摘要仅存内存，重连后需要重新压缩（浪费一次LLM调用）。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/db.py:11` (`init_db()`) | 新增 `conversation_summaries` 建表语句 |
| 修改 | `server/api/routes_chat.py:61` (`_load_history()`) | 改为优先加载摘要 |
| 新建 | `server/context/compressor.py` | 压缩后写入 DB 的逻辑 |

**完整代码片段**：

```python
# --- server/db.py 新增建表 ---
await db.execute("""
    CREATE TABLE IF NOT EXISTS conversation_summaries (
        session_id TEXT NOT NULL,
        summary_version INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        compressed_up_to_msg_id INTEGER NOT NULL,
        safety_pins_json TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (session_id, summary_version)
    )
""")

# --- server/context/compressor.py 新增持久化方法 ---
async def save_summary(self, session_id: str, summary: str,
                       compressed_up_to: int, safety_pins: list[dict]):
    """将压缩摘要写入 DB，支持断连恢复"""
    db = await get_db()
    try:
        # 获取当前最大版本号
        cursor = await db.execute(
            "SELECT MAX(summary_version) FROM conversation_summaries WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        next_version = (row[0] or 0) + 1

        await db.execute(
            """INSERT INTO conversation_summaries
               (session_id, summary_version, summary_text, compressed_up_to_msg_id, safety_pins_json)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, next_version, summary, compressed_up_to,
             json.dumps([{"role": m["role"], "content": m["content"]} for m in safety_pins],
                        ensure_ascii=False)),
        )
        await db.commit()
    finally:
        await db.close()

# --- server/api/routes_chat.py 修改 _load_history ---
async def _load_history(session_id: str) -> list[dict]:
    """从数据库加载会话历史——优先使用压缩摘要"""
    db = await get_db()
    try:
        # 1. 尝试加载最新摘要
        cursor = await db.execute(
            """SELECT summary_text, compressed_up_to_msg_id, safety_pins_json
               FROM conversation_summaries
               WHERE session_id = ?
               ORDER BY summary_version DESC LIMIT 1""",
            (session_id,),
        )
        summary_row = await cursor.fetchone()

        if summary_row:
            summary_text, cutoff_id, safety_json = summary_row
            safety_pins = json.loads(safety_json) if safety_json else []

            # 2. 只加载摘要之后的消息
            cursor2 = await db.execute(
                """SELECT role, content FROM messages
                   WHERE session_id = ? AND message_id > ?
                   ORDER BY created_at ASC""",
                (session_id, cutoff_id),
            )
            recent = [{"role": r[0], "content": r[1]} for r in await cursor2.fetchall()]

            # 3. 返回：安全关键消息（原始）+ 最近消息（原始）
            # 摘要文本通过 run_agent 注入 system prompt
            return safety_pins + recent, summary_text

        # 无摘要，返回全量历史
        cursor3 = await db.execute(
            """SELECT role, content FROM messages
               WHERE session_id = ? ORDER BY created_at ASC""",
            (session_id,),
        )
        rows = await cursor3.fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows], None
    finally:
        await db.close()
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: DB 持久化摘要 | 断连恢复零成本，可审计历史摘要 | 增加 DB 写入（每次压缩一次 INSERT） | **选这个** |
| B: 仅内存缓存 | 零 DB 开销 | 断连后需重新压缩（浪费LLM调用），无法审计 | 不选 |
| C: 文件系统缓存 | 实现简单 | 与现有 SQLite 架构不一致，不支持并发 | 不选 |

**注意**：`_load_history` 的返回值从 `list[dict]` 变为 `tuple[list[dict], str | None]`，需要同步修改 `routes_chat.py:85` 的调用方和 `run_agent()` 的参数，增加 `prior_summary: str | None` 参数。

---

#### 问题3：增量压缩 vs 全量重压缩

每轮都重新压缩所有早期消息浪费算力。第15轮压缩1-9轮，第16轮又要重压缩1-10轮。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/context/compressor.py` | `compress_if_needed` 内部支持增量模式 |

**完整代码片段**：

```python
# server/context/compressor.py — compress_if_needed 增量版

async def compress_if_needed(
    self, messages: list[dict], session_id: str,
    prior_summary: str | None = None,
    prior_cutoff: int | None = None,
) -> tuple[list[dict], str | None]:
    """
    增量压缩：
    - 首次压缩：压缩 messages[0:split] 的全部内容
    - 后续压缩：只压缩 prior_cutoff 到 new_split 之间的新增消息，与旧摘要合并
    """
    turn_count = sum(1 for m in messages if m["role"] == "user")
    if turn_count <= self.COMPRESS_THRESHOLD:
        return messages, prior_summary

    split_idx = self._find_split_point(messages, self.KEEP_RECENT)
    early = messages[:split_idx]
    recent = messages[split_idx:]

    # 分离安全消息
    safety_pinned = [m for m in early if self._is_safety_critical(m)]
    compressible = [m for m in early if not self._is_safety_critical(m)]

    if prior_summary and prior_cutoff is not None:
        # 增量模式：只压缩 cutoff 之后的新消息
        new_messages = compressible[prior_cutoff:]
        if not new_messages:
            return safety_pinned + recent, prior_summary

        summary = await self._incremental_compress(
            prior_summary, new_messages, session_id
        )
    else:
        # 首次压缩
        summary = await self._summarize(compressible, session_id)

    return safety_pinned + recent, summary

async def _incremental_compress(
    self, old_summary: str, new_messages: list[dict], session_id: str
) -> str:
    """在旧摘要基础上整合新对话内容"""
    from agent.loop import _llm_chat
    from llm_client import get_light_model

    prompt = (
        "你之前生成过一份心理咨询对话摘要。现在有新的对话内容需要整合。\n\n"
        "规则：\n"
        "1. 保留旧摘要中仍然重要的信息\n"
        "2. 整合新对话的要点（情绪变化、新议题、干预反应）\n"
        "3. 如果旧信息已被更新（如情绪好转），替换而非叠加\n"
        "4. [安全标记] 相关内容永远保留\n"
        "5. 控制总长度在 300 字以内\n\n"
        f"旧摘要：\n{old_summary}\n\n"
        "新对话内容见下方消息。"
    )
    result = await _llm_chat(
        system=prompt,
        messages=new_messages,
        model_override=get_light_model(),
        max_tokens=500,
    )
    return result["text"]
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 增量压缩（旧摘要+新消息→合并） | 每次只处理2-4条新消息，LLM成本极低 | 多次增量后摘要可能漂移、重要早期信息被稀释 | **选这个** |
| B: 每次全量重压缩 | 摘要质量一致，无漂移 | 随对话增长，每次压缩的输入越来越大，成本线性增长 | 不选 |
| C: 定时全量重压缩（每10轮） | 兼顾质量与成本 | 实现复杂，需要维护两套触发逻辑 | 备选（如果A出现漂移可切换） |

**漂移应对**：设置 `MAX_INCREMENTAL_ROUNDS = 5`，连续增量压缩超过5次后，执行一次全量重压缩校准。

---

#### 问题4：NarrativeMemory 使用同步 SQLite 会阻塞事件循环

`server/memory/narrative.py:50` 使用 `sqlite3.connect()`（同步），在 `run_agent()` 的异步链路 `loop.py:374-381` 中直接调用 `nm.get_narrative_context(user_id)` 会阻塞事件循环。`server/memory/user_profile.py` 的 `ProfileStore` 也有同样问题。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/agent/loop.py:374` | `nm.get_narrative_context` 调用处 |
| 修改 | `server/agent/loop.py:386` | `ps.load` / `rsm` 调用处 |
| 修改（长期） | `server/memory/narrative.py:50` | `sqlite3` → `aiosqlite` |
| 修改（长期） | `server/memory/user_profile.py` | `sqlite3` → `aiosqlite` |

**完整代码片段**：

```python
# --- 短期方案：server/agent/loop.py 修改（Phase 4a 立即做）---

# 原代码 loop.py:373-381
try:
    from memory.narrative import NarrativeMemory
    nm = NarrativeMemory()
    narrative_ctx = nm.get_narrative_context(user_id)  # ← 同步阻塞!
    ...

# 改为：
try:
    from memory.narrative import NarrativeMemory
    nm = NarrativeMemory()
    narrative_ctx = await asyncio.to_thread(nm.get_narrative_context, user_id)
    if narrative_ctx:
        context_hints.append(narrative_ctx)
except Exception:
    pass

# 同理 loop.py:383-414 的 ProfileStore / RelationshipStateMachine：
try:
    from memory.user_profile import ProfileStore, RelationshipStateMachine
    ps = ProfileStore()
    profile = await asyncio.to_thread(ps.load, user_id)
    ...
    rsm = RelationshipStateMachine()
    relationship_guidance = await asyncio.to_thread(rsm.get_guidance, user_id)
    ...
    await asyncio.to_thread(rsm.update, user_id, user_message)
except Exception:
    pass

# --- 长期方案：server/memory/narrative.py 改造（Phase 4b 做）---

class NarrativeMemory:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = settings.sqlite_db_path
        self._db_path = db_path
        # 不再在 __init__ 中打开连接

    async def get_narrative_context_async(self, user_id: str) -> str | None:
        """异步版本——直接用 aiosqlite"""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT arc_data FROM narrative_arcs WHERE user_id = ? ORDER BY last_updated DESC LIMIT 3",
                (user_id,),
            )
            rows = await cursor.fetchall()
            if not rows:
                return None
            # ... 构建上下文字符串（与原同步版逻辑一致）
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: `asyncio.to_thread` 包装 | 改动最小（3行），立即解决阻塞 | 线程池有限（默认40），高并发下可能饱和 | **Phase 4a 用这个** |
| B: 全部改写为 `aiosqlite` | 根治问题，无线程开销 | 需重写 `narrative.py` + `user_profile.py` 两个文件的所有方法 | **Phase 4b 用这个** |
| C: 不处理 | 零成本 | 每次同步 DB 查询阻塞约 1-5ms，单用户不明显，但并发10+用户时会产生延迟叠加 | 不选 |

---

#### 问题5：工具消息格式差异——Anthropic vs DeepSeek

压缩工具结果时，两种 Provider 的消息格式完全不同，直接按固定格式处理会报错。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `server/context/compressor.py` | `compress_tool_results` 方法 |
| 参考 | `server/agent/loop.py:505-538` | 现有工具结果追加逻辑（两种格式的实现） |
| 参考 | `server/agent/loop.py:83` | `_is_deepseek()` 判断函数 |

**消息格式对比**：

```python
# Anthropic 工具调用链（loop.py:536-538）
# assistant 消息：
{"role": "assistant", "content": <response.content blocks>}  # 含 ToolUseBlock
# tool_result 消息：
{"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "toolu_xxx", "content": "很长的评估结果..."}
]}

# DeepSeek 工具调用链（loop.py:523-535）
# assistant 消息：
{"role": "assistant", "content": "...", "_tool_calls_raw": [ToolCall对象]}
# tool_result 消息：
{"role": "tool", "tool_call_id": "call_xxx", "content": "很长的评估结果..."}
```

**完整代码片段**：

```python
# server/context/compressor.py

from agent.loop import _is_deepseek

def compress_tool_results(messages: list) -> list:
    """
    压缩工具调用结果——保留工具名和关键结论，删除冗余细节。
    自动检测 Anthropic / DeepSeek 格式。
    """
    is_ds = _is_deepseek()
    compressed = []

    for msg in messages:
        if is_ds and msg.get("role") == "tool":
            # DeepSeek 格式
            original = msg["content"]
            compressed.append({
                **msg,
                "content": _shorten_tool_output(original),
            })
        elif (not is_ds
              and isinstance(msg.get("content"), list)
              and any(
                  isinstance(c, dict) and c.get("type") == "tool_result"
                  for c in msg["content"]
              )):
            # Anthropic 格式
            new_content = []
            for item in msg["content"]:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    new_content.append({
                        **item,
                        "content": _shorten_tool_output(str(item.get("content", ""))),
                    })
                else:
                    new_content.append(item)
            compressed.append({**msg, "content": new_content})
        else:
            compressed.append(msg)

    return compressed


def _shorten_tool_output(raw: str, max_len: int = 200) -> str:
    """
    将工具输出压缩为关键信息。
    例：assess_emotion 的完整 JSON → "情绪：焦虑(7/10)，触发：工作压力"
    """
    # 尝试 JSON 解析，提取关键字段
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # 情绪评估结果
            if "primary" in data or "emotion" in data:
                emotion = data.get("primary") or data.get("emotion", {}).get("primary", "")
                intensity = data.get("intensity", "")
                return f"情绪：{emotion}({intensity}/10)"

            # 认知扭曲结果
            if "distortions" in data:
                types = [d.get("type", "") for d in data["distortions"][:3]]
                return f"认知扭曲：{'、'.join(types)}"

            # 通用：取前200字符
            summary = json.dumps(data, ensure_ascii=False)
            return summary[:max_len] + ("..." if len(summary) > max_len else "")
    except (json.JSONDecodeError, TypeError):
        pass

    return raw[:max_len] + ("..." if len(raw) > max_len else "")
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 运行时检测格式，分支处理 | 与现有双 Provider 架构一致，无需额外抽象 | 两套分支维护成本 | **选这个** |
| B: 先统一为中间格式，再压缩 | 压缩逻辑只写一份 | 需要增加 normalize → compress → denormalize 三步，多2次序列化开销 | 过度设计 |
| C: 只压缩 content 字符串，不管外层格式 | 最简单 | Anthropic 的 content 可能是 list 或 ContentBlock 对象，直接切字符串会报错 | 不可行 |

---

#### 问题6：子Agent编排 vs 现有 `_background_assess()` 的关系

当前 `loop.py:325-327` 的 `_background_assess()` 和 `routes_chat.py:180-186` 的 `_generate_and_send_strategy()` 分别在两个位置独立调度后台任务。方案中的 `SubAgentOrchestrator` 功能上覆盖了两者，如果不合并会导致重复LLM调用。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `server/context/sub_agents.py` | 统一编排器 |
| 修改 | `server/agent/loop.py:325-327` | 删除 `bg_assess_task = asyncio.create_task(...)` |
| 修改 | `server/agent/loop.py:541-582` | 将 `_background_assess()` 函数体迁移到子Agent |
| 修改 | `server/api/routes_chat.py:178-186` | 删除独立的策略生成调度 |
| 保留 | `server/agent/session_strategy.py` | 数据模型 `SessionStrategy` + `load_session_strategy()` 保留不动 |

**完整代码片段**：

```python
# server/context/sub_agents.py — 统一编排器

import asyncio
import json
import logging

from config import settings

logger = logging.getLogger(__name__)


class SubAgentOrchestrator:
    """
    统一子Agent编排器。
    替代：
    - loop.py 中的 _background_assess()（→ analysis agent）
    - routes_chat.py 中的 _generate_and_send_strategy()（→ strategy agent）
    - loop.py 中的 search_books_semantic() 直接调用（→ knowledge agent）
    """

    async def dispatch(
        self, user_msg: str, notes, recent_messages: list
    ) -> dict[str, str]:
        """并行分发子Agent任务，返回精炼结果字典"""
        tasks: dict[str, asyncio.Task] = {}

        # 分析Agent（替代 _background_assess）
        if self._needs_analysis(user_msg, notes):
            tasks["analysis"] = asyncio.create_task(
                self._run_analysis_agent(user_msg, recent_messages[-6:],
                                         notes.user_profile_summary)
            )

        # 知识Agent（替代 search_books_semantic 直接调用）
        if self._needs_knowledge(user_msg, notes):
            tasks["knowledge"] = asyncio.create_task(
                self._run_knowledge_agent(user_msg, notes.presenting_issue)
            )

        # 策略Agent（替代 _generate_and_send_strategy）
        if self._needs_strategy(notes):
            tasks["strategy"] = asyncio.create_task(
                self._run_strategy_agent(notes, recent_messages)
            )

        if not tasks:
            return {}

        # 带超时的并行等待
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=settings.sub_agent_timeout,
        )
        # 取消超时的任务
        for t in pending:
            t.cancel()

        # 收集完成的结果
        results = {}
        for name, task in tasks.items():
            if task in done and not task.cancelled():
                try:
                    results[name] = task.result()
                except Exception as e:
                    logger.warning(f"[SubAgent:{name}] failed: {e}")
        return results

    async def _run_analysis_agent(
        self, user_msg: str, recent: list, profile: str
    ) -> str:
        """深度分析子Agent——替代 _background_assess()"""
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        system = (
            "简要评估用户情绪和可能的认知模式。注意结合对话上下文判断——"
            "用户当前的情绪可能是前几轮的延续或转变。\n"
            f"用户画像：{profile or '暂无'}\n"
            "返回JSON：{\"assessment\": \"一句话概括\", "
            "\"emotion\": {\"primary\": \"情绪名\", \"intensity\": 1-10}}"
        )
        result = await _llm_chat(
            system=system,
            messages=recent + [{"role": "user", "content": user_msg}],
            model_override=get_light_model(),
            max_tokens=200,
        )
        return result["text"]

    async def _run_knowledge_agent(self, query: str, issue: str) -> str:
        """知识检索子Agent——检索 + 精选"""
        from knowledge.knowledge_base import search_books_semantic
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        results = search_books_semantic(f"{issue} {query}", max_results=5)
        if not results:
            return ""

        candidates = "\n".join(
            f"[{r.get('book', '')}·{r.get('chapter', '')}] {r['content'][:200]}"
            for r in results if r.get("similarity", 0) > 0.25
        )
        if not candidates.strip():
            return ""

        result = await _llm_chat(
            system=(
                "从以下心理学知识中，选出与用户问题最相关的1-2条，"
                f"用自己的话重述要点（不超过150字）。\n用户问题：{query}"
            ),
            messages=[{"role": "user", "content": candidates}],
            model_override=get_light_model(),
            max_tokens=200,
        )
        return result["text"]

    async def _run_strategy_agent(self, notes, recent_messages: list) -> str:
        """策略规划子Agent——替代 _generate_and_send_strategy()"""
        from agent.session_strategy import generate_session_strategy
        # 复用现有策略生成逻辑，不重复造轮子
        strategy = await generate_session_strategy(
            notes._session_id, recent_messages, notes._user_id
        )
        if strategy:
            return json.dumps({
                "presenting_issue": strategy.presenting_issue,
                "primary_approach": strategy.primary_approach,
                "techniques": strategy.techniques,
            }, ensure_ascii=False)
        return ""

    # --- 触发条件判断 ---
    def _needs_analysis(self, msg: str, notes) -> bool:
        if len(msg) < 10:
            return False
        return True  # 大部分消息都需要情绪评估

    def _needs_knowledge(self, msg: str, notes) -> bool:
        return bool(notes.presenting_issue) and len(msg) > 15

    def _needs_strategy(self, notes) -> bool:
        return not notes.session_strategy


# --- loop.py 迁移后的调用方式 ---
# 替代原来的 bg_assess_task = asyncio.create_task(_background_assess(...))

# orchestrator = SubAgentOrchestrator()
# sub_results = await orchestrator.dispatch(user_message, notes, recent_messages)
#
# if "analysis" in sub_results:
#     context_hints.append(f"[后台评估] {sub_results['analysis']}")
# if "knowledge" in sub_results:
#     context_hints.append(f"[知识参考] {sub_results['knowledge']}")
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 统一编排器完全替代 | 单一调度入口，无重复调用，易于监控 | 迁移改动量大（3个文件），需回归测试 | **选这个** |
| B: 编排器与旧逻辑共存 | 改动小，可渐进迁移 | 同一功能两套调度，可能重复调用LLM（浪费+结果冲突） | 不选 |
| C: 只做薄包装 | 最少改动 | 没有解决核心问题（上下文隔离），只是换了个调用位置 | 不选 |

---

#### 问题7：子Agent超时和降级策略

子Agent依赖外部LLM API，网络抖动/API限流可能导致超时。如果没有降级，主Agent等待子Agent会严重拖慢响应时间。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/context/sub_agents.py` | `dispatch()` 中的超时和降级逻辑 |
| 修改 | `server/config.py` | 新增 `SUB_AGENT_TIMEOUT` 配置 |
| 新建 | `server/context/cache.py` | 子Agent结果缓存（可选） |

**完整代码片段**：

```python
# server/config.py 新增
SUB_AGENT_TIMEOUT: int = 5  # 子Agent最大等待秒数

# server/context/cache.py — 子Agent结果LRU缓存

from collections import OrderedDict

class SubAgentCache:
    """
    子Agent结果缓存——超时降级时使用上一轮结果。
    按 session_id 分区，每个 session 保留最近一轮各 agent 的结果。
    """
    def __init__(self, max_sessions: int = 100):
        self._store: OrderedDict[str, dict[str, str]] = OrderedDict()
        self._max = max_sessions

    def get(self, session_id: str, agent_name: str) -> str | None:
        if session_id in self._store:
            return self._store[session_id].get(agent_name)
        return None

    def put(self, session_id: str, agent_name: str, result: str):
        if session_id not in self._store:
            if len(self._store) >= self._max:
                self._store.popitem(last=False)  # 淘汰最旧
            self._store[session_id] = {}
        self._store[session_id][agent_name] = result
        self._store.move_to_end(session_id)

# 全局单例
_cache = SubAgentCache()


# server/context/sub_agents.py — dispatch 增加降级链

async def dispatch(self, user_msg, notes, recent_messages, session_id: str):
    from context.cache import _cache

    tasks = {}
    # ... 同前，创建 tasks ...

    if not tasks:
        return {}

    done, pending = await asyncio.wait(
        tasks.values(),
        timeout=settings.sub_agent_timeout,
    )
    for t in pending:
        t.cancel()
        logger.warning(f"[SubAgent] Task cancelled due to timeout")

    results = {}
    for name, task in tasks.items():
        if task in done and not task.cancelled():
            try:
                value = task.result()
                results[name] = value
                _cache.put(session_id, name, value)  # 缓存成功结果
            except Exception as e:
                logger.warning(f"[SubAgent:{name}] error: {e}")
                # 降级：使用上一轮缓存
                cached = _cache.get(session_id, name)
                if cached:
                    results[name] = cached
                    logger.info(f"[SubAgent:{name}] fallback to cached result")
        else:
            # 超时：使用上一轮缓存
            cached = _cache.get(session_id, name)
            if cached:
                results[name] = cached
                logger.info(f"[SubAgent:{name}] timeout, fallback to cache")

    return results
```

**降级链路图**：
```
子Agent调用
    ↓ 成功
 ✅ 使用新鲜结果 + 写入缓存
    ↓ 超时/失败
 ⚡ 使用上一轮缓存结果
    ↓ 无缓存
 🔇 无结果（主Agent自行推理，不注入该维度上下文）
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 超时+缓存降级 | 用户感知延迟可控（≤5秒），降级时仍有参考信息 | 缓存结果可能过时（上一轮的情绪评估不代表这一轮） | **选这个** |
| B: 仅超时无降级 | 实现简单 | 超时时主Agent完全没有后台评估参考，回复质量可能下降 | 不选 |
| C: 不设超时 | 结果最完整 | API故障时用户可能等30秒+才收到回复（不可接受） | 不选 |

**缓存过时风险**：心理咨询场景中，相邻两轮的情绪状态通常高度相关（用户不太可能从"极度焦虑"突然变成"非常开心"），因此上一轮缓存在大多数情况下是可接受的近似。

---

#### 问题8：压缩摘要作为对话消息的格式问题

将摘要包装成 `{"role": "user", "content": "[前序对话摘要]..."}` 会让LLM误以为用户发了一条很长的消息。更严重的是，它打破了对话的 user/assistant 交替结构，Anthropic API 会报错。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/context/compressor.py` | `compress_if_needed` 返回摘要文本（不构造消息） |
| 修改 | `server/agent/loop.py:459-462` | 摘要注入 `context_enriched_prompt` 而非 `messages` |

**完整代码片段**：

```python
# server/agent/loop.py — run_agent() 中的集成方式

# === 对话压缩 ===
from context.compressor import ConversationCompressor

compressor = ConversationCompressor()
compressed_messages, summary = await compressor.compress_if_needed(
    conversation_history, session_id,
    prior_summary=prior_summary,  # 从 _load_history 传入
)

# 摘要注入 system prompt（不放 messages）
if summary:
    context_hints.append(
        f"[历史对话摘要·仅供内部参考]\n{summary}\n"
        "[注意] 以上是早期对话的压缩摘要。最近几轮原始对话见下方消息。"
    )

# messages 只包含：安全关键消息（原始）+ 最近6轮（原始）
messages = compressed_messages + [{"role": "user", "content": user_message}]
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 摘要注入 system prompt | 不污染 messages 结构，与现有 context_hints 一致，API兼容性好 | system prompt 变长（+300 token），但比全量历史小得多 | **选这个** |
| B: 构造假 user/assistant 消息对 | 摘要在 messages 中，LLM可能给予更高注意力 | 打破交替结构可能报错，LLM可能把摘要当用户发言来回应 | 不选 |
| C: 使用 Anthropic 的 `cache_control` 特性 | 原生支持，API级别的优化 | DeepSeek 不支持，破坏双 Provider 兼容性 | 仅Anthropic时考虑 |

---

#### 问题9：结构化笔记的冷启动问题

新会话前2-3轮，`SessionNotes` 字段几乎全空——`presenting_issue` 空、`session_strategy` 空、`user_profile_summary` 可能空（新用户）。此时 `to_compact_prompt()` 返回空字符串或极少信息，主Agent 丢失现有架构的上下文辅助能力。

**涉及文件**：
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `server/context/session_notes.py` | 增加 `is_warm()` 判断 + `_build_full_context()` 回退逻辑 |
| 修改 | `server/agent/loop.py:338-458` | 重构上下文注入逻辑，支持冷/暖两种模式 |

**完整代码片段**：

```python
# server/context/session_notes.py

@dataclass
class SessionNotes:
    # ... 字段定义同 4.2.1 ...

    # 会话级元数据
    _session_id: str = ""
    _user_id: str = ""
    _turn_count: int = 0

    def is_warm(self) -> bool:
        """
        判断笔记是否已预热（信息充足以支撑紧凑模式）。
        条件：至少有核心议题 OR 用户画像 OR 已对话3轮以上。
        """
        has_issue = bool(self.presenting_issue)
        has_profile = bool(self.user_profile_summary)
        has_turns = self._turn_count >= 3
        return has_issue or (has_profile and has_turns)

    def to_compact_prompt(self) -> str:
        """生成紧凑上下文（暖启动时使用）"""
        # ... 同 4.2.1 ...

    @staticmethod
    async def load_or_create(session_id: str, user_id: str,
                              turn_count: int) -> "SessionNotes":
        """从 DB 加载，不存在则创建空笔记"""
        notes = SessionNotes(_session_id=session_id,
                             _user_id=user_id,
                             _turn_count=turn_count)
        # 加载用户画像
        try:
            from memory.user_profile import ProfileStore
            ps = ProfileStore()
            profile = await asyncio.to_thread(ps.load, user_id)
            if profile:
                parts = []
                if profile.display_name:
                    parts.append(profile.display_name)
                if profile.current_phase and profile.current_phase != "unknown":
                    parts.append(f"阶段:{profile.current_phase}")
                if profile.signature_strengths:
                    parts.append(f"优势:{'、'.join(profile.signature_strengths[:2])}")
                notes.user_profile_summary = "；".join(parts)
        except Exception:
            pass

        # 加载会话策略
        try:
            from agent.session_strategy import load_session_strategy
            strategy = await load_session_strategy(session_id)
            if strategy:
                notes.presenting_issue = strategy.presenting_issue
                notes.session_strategy = (
                    f"{strategy.primary_approach}：{'→'.join(strategy.stage_goals[:2])}"
                )
        except Exception:
            pass

        # 加载叙事趋势
        try:
            from memory.narrative import NarrativeMemory
            nm = NarrativeMemory()
            trend = await asyncio.to_thread(nm.get_trend, user_id)
            if trend:
                notes.narrative_trend = trend
        except Exception:
            pass

        # 加载关系状态
        try:
            from memory.user_profile import RelationshipStateMachine
            rsm = RelationshipStateMachine()
            state = await asyncio.to_thread(rsm.get_state, user_id)
            notes.relationship_state = state or "normal"
        except Exception:
            pass

        return notes


# server/agent/loop.py — 重构后的上下文注入

async def _build_context_hints(
    user_message: str, user_id: str, session_id: str,
    conversation_history: list, risk, crisis_holding,
    multimodal_context: list[str] | None,
) -> list[str]:
    """
    统一的上下文构建器。
    冷启动：走现有的6层全量注入（兼容当前行为）
    暖启动：走紧凑的 SessionNotes 模式
    """
    context_hints = []

    # 安全与危机相关——始终全量注入（无论冷暖）
    if crisis_holding and crisis_holding.active:
        context_hints.append(crisis_holding.get_phase_prompt())
        context_hints.append(
            "[绝对禁止] 抱持模式下不得使用任何工具，不得认知评估，不得推荐练习。"
        )
    if risk.level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        context_hints.append(
            f"[安全提示] 用户当前风险等级：{risk.level.value}，"
            "请在回复中温和地建议寻求专业帮助。"
        )

    turn_count = sum(1 for m in conversation_history if m["role"] == "user")
    notes = await SessionNotes.load_or_create(session_id, user_id, turn_count)

    if notes.is_warm():
        # ✅ 暖启动：紧凑模式
        context_hints.append(notes.to_compact_prompt())
    else:
        # 🔄 冷启动：回退到现有全量注入
        # 直接复用 loop.py 当前 373-454 行的逻辑
        # （叙事记忆、用户画像、知识库、会话策略分别注入）
        await _inject_full_context(context_hints, user_message, user_id, session_id)

    if multimodal_context:
        context_hints.extend(multimodal_context)

    return context_hints
```

**权衡取舍**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| A: 冷/暖双模式自动切换 | 冷启动时保持现有质量，暖启动时享受压缩收益 | 两套路径需要维护，冷→暖的切换点需要调优 | **选这个** |
| B: 始终用紧凑模式 | 代码最简单，统一路径 | 前2轮笔记空白，主Agent几乎无上下文参考（回复质量暴降） | 不选 |
| C: 始终用全量注入 | 无冷启动问题 | 那就等于没做结构化笔记优化 | 不选 |

**切换阈值**：`is_warm()` 的条件设计为"有核心议题 OR (有画像 AND ≥3轮)"，原因是：
- 有核心议题 → 策略已生成（通常第2-3轮），笔记已有实质内容
- 有画像+3轮 → 老用户的新会话，画像本身已提供足够上下文
- 新用户+前2轮 → 信息太少，必须全量注入兜底
