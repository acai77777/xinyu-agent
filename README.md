# 心语 XinYu — AI 心理健康伴侣

<div align="center">

**一个 24/7 在线的 AI 心理咨询助手，融合认知行为疗法（CBT）与积极心理学**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Expo 55](https://img.shields.io/badge/Expo-55-000.svg?logo=expo)](https://expo.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)

</div>

## 项目简介

心语（XinYu）是一款基于大语言模型的 AI 心理健康伴侣应用。它融合了**认知行为疗法（CBT）**和**积极心理学**两大理论框架，通过自然对话的形式为用户提供情绪支持、心理评估和结构化干预。

> ⚠️ **重要提示**：心语是一个实验性项目，不能替代专业心理咨询或医疗诊断。如果你正处于危机状态，请立即拨打当地心理援助热线。

## 核心功能

### 智能对话
- 基于 LLM 的深度共情对话，理解用户情绪状态
- 支持文字、语音、图片多模态输入
- 语音合成回复（TTS），支持语音交互

### 安全体系
- **两阶段危机检测**：关键词扫描（零延迟）+ LLM 语义分类确认
- **四阶段"抱持性环境"模型**：HOLDING → GROUNDING → BRIDGING → RESOURCES
- **输出审核**：语境感知规则引擎 + 有害内容替换 + 语义审核
- **安全消息固定**：含自杀关键词的消息在上下文压缩中永不删除

### 评估引擎
- **情绪分类**：19 类精细情绪识别
- **认知扭曲检测**：15 种 CBT 认知扭曲类型
- **标准化量表**：PHQ-9（抑郁）、GAD-7（焦虑）、PERMA（幸福感）、SWLS（生活满意度）、GQ-6（感恩）

### 干预工具
- **CBT 模块**：苏格拉底式对话、认知重构
- **积极心理学模块**：感恩练习、优势发掘
- **结构化练习指导**：正念呼吸、渐进放松、行为激活、最佳可能自我

### 记忆系统
- **语义记忆**：ChromaDB 向量数据库，支持 90 天指数衰减
- **叙事记忆**：按主题的快照序列 + 趋势检测 + LLM 摘要
- **用户画像**：3 态关系状态机（NORMAL / DEPENDENT / HOSTILE）

### 上下文管理
- **对话压缩**：超过 10 轮时自动压缩，保留最近 6 轮 + LLM 摘要（Token 使用量 **-74%**）
- **结构化笔记**：冷/暖启动模式的三层数据结构
- **子 Agent 编排**：独立上下文窗口，节省 90% Token，5 秒超时 + LRU 缓存降级

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    客户端 (Expo RN)                      │
│         iOS / Android / Web  |  WebSocket + REST        │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    后端 (FastAPI)                        │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │  API 层   │ │ Agent 层  │ │ 安全层  │ │  评估层    │  │
│  │ REST+WS  │ │ 工具调用  │ │ 危机检测│ │ 情绪/扭曲  │  │
│  └──────────┘ └──────────┘ └─────────┘ └────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │ 干预层   │ │ 记忆层   │ │ 知识库  │ │  上下文    │  │
│  │ CBT+积极 │ │ 三层记忆 │ │ 混合检索│ │ 压缩管理   │  │
│  └──────────┘ └──────────┘ └─────────┘ └────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    数据 & 模型                            │
│  SQLite + ChromaDB  |  OpenRouter / DeepSeek / Anthropic │
└─────────────────────────────────────────────────────────┘
```

| 层级 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + WebSocket |
| 前端框架 | Expo 55 + React Native 0.83 |
| 状态管理 | Zustand |
| 主对话模型 | Gemini Flash (OpenRouter) |
| 轻量评估模型 | DeepSeek V3.2 |
| 向量数据库 | ChromaDB (ONNX 嵌入) |
| 关系数据库 | SQLite (aiosqlite 异步) |
| 认证 | JWT + bcrypt |
| 语音合成 | OpenAI TTS + Edge TTS |
| 部署 | Docker Compose |

## 快速开始

### 前置条件
- Docker & Docker Compose
- OpenRouter API Key（[免费注册](https://openrouter.ai/)）

### 部署

```bash
# 1. 克隆仓库
git clone https://github.com/acai77777/xinyu-agent.git
cd xinyu-agent

# 2. 配置环境变量
cp server/.env.example server/.env
# 编辑 server/.env，填入你的 OPENROUTER_API_KEY

# 3. 启动服务
docker compose up -d

# 4. 访问
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 本地开发

```bash
# 后端
cd server
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端
cd app
npm install
npx expo start
```

## 项目结构

```
xinyu-agent/
├── server/                    # Python FastAPI 后端
│   ├── agent/                 # Agent 核心循环 + 工具 + Prompt
│   ├── api/                   # REST + WebSocket 路由
│   ├── safety/                # 危机检测 + 抱持性环境
│   ├── assessment/            # 情绪/认知扭曲/量表评估
│   ├── intervention/          # CBT + 积极心理学干预
│   ├── memory/                # 三层记忆系统
│   ├── knowledge/             # 知识库 + 混合检索
│   ├── context/               # 上下文压缩管理
│   ├── multimodal/            # 语音/图片处理
│   ├── evaluation/            # 评测框架
│   ├── tests/                 # 单元测试 (131 个用例)
│   └── data/                  # 练习模板/关键词/心理量表
├── app/                       # Expo React Native 前端
│   ├── app/                   # 页面路由 (Expo Router)
│   ├── components/            # UI 组件
│   ├── services/              # API + WebSocket 客户端
│   └── stores/                # Zustand 状态管理
├── prototype/                 # HTML 原型
├── docker-compose.yml         # 部署配置
└── research.md                # 心理学研究文档 (56KB)
```

## 心理学理论基础

### 认知行为疗法 (CBT)
基于 Aaron Beck 的认知模型，帮助用户识别和重构 **15 种认知扭曲**，包括：
全或无思维、过度概括、心理过滤、否定正面、妄下结论、夸大/缩小、情绪推理、"应该"陈述、标签化、个人化等。

### 积极心理学
基于 Martin Seligman 的 **PERMA 幸福感模型**：
- **P**ositive Emotion（积极情绪）
- **E**ngagement（投入）
- **R**elationships（关系）
- **M**eaning（意义）
- **A**ccomplishment（成就）

## 安全评测

| 指标 | 得分 |
|------|------|
| 综合准确率 | **91.4%** |
| CRITICAL Recall | **70%** |
| HIGH Recall | **100%** |
| 致命漏检 | **0** |
| 红队测试 | **7/7** 通过 |
| 鲁棒性 | **11/11** 通过 |

## 贡献

欢迎提交 Issue 和 Pull Request！在提交 PR 前请：
1. 确保现有测试通过：`cd server && python -m pytest tests/`
2. 为新功能添加测试覆盖
3. 遵循项目现有的代码风格

## 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

<div align="center">
  <sub>如果你正在经历困难，请记住你并不孤单。寻求帮助是勇敢的表现。</sub>
</div>
