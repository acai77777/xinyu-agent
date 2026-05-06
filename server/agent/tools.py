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
        "description": "管理用户的记忆数据：查看、删除特定记忆或清除所有数据（用户的'被遗忘权'）",
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
    {
        "name": "search_knowledge_base",
        "description": "在心理学知识库中搜索相关知识（同时使用关键词匹配和语义向量搜索），覆盖CBT理论、积极心理学、真实的幸福等书籍",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询，如'感恩练习'、'认知扭曲'、'心流体验'等",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数（默认5）",
                },
            },
            "required": ["query"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict, context: dict | None = None) -> str:
    """
    工具分发器——根据工具名调用对应的后端实现。

    context: 可选的对话上下文，包含 user_messages 等信息供工具使用。
    """
    handlers = {
        "assess_emotion": _handle_assess_emotion,
        "detect_cognitive_distortion": _handle_detect_distortion,
        "get_intervention_strategy": _handle_get_strategy,
        "run_scale_assessment": _handle_run_scale,
        "retrieve_user_history": _handle_retrieve_history,
        "guide_exercise": _handle_guide_exercise,
        "manage_memory": _handle_manage_memory,
        "search_knowledge_base": _handle_search_knowledge_base,
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return f"未知工具：{tool_name}"
    return handler(tool_input, context=context)


# === 工具实现 ===

def _handle_assess_emotion(inputs: dict, context: dict | None = None) -> str:
    import json
    from assessment.emotion import assess_emotion
    result = assess_emotion(inputs.get("user_text", ""))
    return json.dumps(result, ensure_ascii=False)


def _handle_detect_distortion(inputs: dict, context: dict | None = None) -> str:
    import json
    from assessment.distortion import detect_distortion
    results = detect_distortion(inputs.get("user_text", ""))
    return json.dumps(
        [{"type": r.distortion_type, "type_en": r.distortion_name_en,
          "evidence": r.evidence, "confidence": r.confidence}
         for r in results],
        ensure_ascii=False,
    )


def _handle_get_strategy(inputs: dict, context: dict | None = None) -> str:
    import json
    from intervention.strategy_planner import plan_intervention, detect_user_readiness

    # 从对话上下文中检测用户准备程度
    user_readiness = "unknown"
    if context and context.get("user_messages"):
        user_readiness = detect_user_readiness(context["user_messages"])

    plan = plan_intervention(
        emotion_state=inputs.get("emotion_state", "normal"),
        distortion_type=inputs.get("distortion_type", ""),
        user_readiness=user_readiness,
    )
    return json.dumps({
        "phase": plan.phase.value,
        "approach": plan.primary_approach,
        "techniques": plan.recommended_techniques,
        "guidance": plan.conversation_guidance,
        "user_readiness": user_readiness,
    }, ensure_ascii=False)


def _handle_run_scale(inputs: dict, context: dict | None = None) -> str:
    import json
    from assessment.scales import get_scale_intro
    scale_name = inputs.get("scale_name", "")
    try:
        intro = get_scale_intro(scale_name)
        return json.dumps(intro, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_retrieve_history(inputs: dict, context: dict | None = None) -> str:
    """从三个记忆源检索用户历史：语义记忆 + 叙事记忆 + 用户画像"""
    import json

    user_id = (context or {}).get("user_id", "")
    query = inputs.get("query", "")
    if not user_id:
        return '{"error": "缺少 user_id"}'

    results = {}

    # 1. 语义记忆（ChromaDB）
    try:
        from memory.semantic import SemanticMemory
        sm = SemanticMemory()
        memories = sm.retrieve_with_decay(user_id, query, top_k=5)
        results["semantic_memories"] = [
            {"content": m["content"], "score": round(m["final_score"], 3)}
            for m in memories
        ]
    except Exception:
        results["semantic_memories"] = []

    # 2. 叙事记忆（情感弧线）
    try:
        from memory.narrative import NarrativeMemory
        nm = NarrativeMemory()
        narrative_ctx = nm.get_narrative_context(user_id)
        results["narrative_context"] = narrative_ctx or ""
    except Exception:
        results["narrative_context"] = ""

    # 3. 用户画像
    try:
        from memory.user_profile import ProfileStore
        ps = ProfileStore()
        profile = ps.load(user_id)
        if profile:
            results["user_profile"] = {
                "strengths": profile.signature_strengths,
                "common_distortions": profile.common_distortions,
                "preferred_interventions": profile.preferred_interventions,
                "current_phase": profile.current_phase,
                "session_count": profile.session_count,
            }
    except Exception:
        pass

    return json.dumps(results, ensure_ascii=False)


def _load_exercise_from_json(exercise_type: str) -> dict | None:
    """从 data/exercises/ 目录加载练习 JSON 数据"""
    import json
    from pathlib import Path
    filepath = Path(__file__).resolve().parent.parent / "data" / "exercises" / f"{exercise_type}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _handle_guide_exercise(inputs: dict, context: dict | None = None) -> str:
    import json
    exercise_type = inputs.get("exercise_type", "")

    # 感恩练习库（含 gratitude_journal / mental_subtraction / gratitude_letter）
    from intervention.positive.gratitude import GRATITUDE_EXERCISES
    if exercise_type in GRATITUDE_EXERCISES:
        ex = GRATITUDE_EXERCISES[exercise_type]
        return json.dumps({
            "name": ex["name"],
            "instruction": ex["instruction"],
            "follow_up_prompts": ex["follow_up_prompts"],
        }, ensure_ascii=False)

    # 认知重构七栏法
    if exercise_type == "thought_record":
        from intervention.cbt.cognitive_restructuring import ThoughtRecord
        tr = ThoughtRecord()
        return json.dumps({
            "name": "思维记录（七栏法）",
            "instruction": tr.get_next_prompt(),
            "total_steps": 7,
        }, ensure_ascii=False)

    # 从 JSON 数据文件加载其余练习
    data = _load_exercise_from_json(exercise_type)
    if data:
        return json.dumps({
            "name": data["name"],
            "instruction": data["instruction"],
            "follow_up_prompts": data.get("follow_up_prompts", []),
        }, ensure_ascii=False)

    return json.dumps({"error": f"未知练习类型：{exercise_type}"}, ensure_ascii=False)


def _handle_manage_memory(inputs: dict, context: dict | None = None) -> str:
    """管理用户记忆：查看、删除特定记忆、清除全部（被遗忘权）"""
    import json

    user_id = (context or {}).get("user_id", "")
    action = inputs.get("action", "list")
    if not user_id:
        return '{"error": "缺少 user_id"}'

    try:
        from memory.semantic import SemanticMemory
        sm = SemanticMemory()
    except Exception as e:
        return json.dumps({"error": f"记忆系统不可用: {e}"}, ensure_ascii=False)

    if action == "list":
        memories = sm.list_user_memories(user_id)
        return json.dumps({
            "action": "list",
            "count": len(memories),
            "memories": memories,
        }, ensure_ascii=False)

    if action == "delete_one":
        memory_id = inputs.get("memory_id", "")
        if not memory_id:
            return '{"error": "delete_one 需要提供 memory_id"}'
        sm.delete_memory(memory_id)
        return json.dumps({
            "action": "delete_one",
            "deleted_id": memory_id,
            "result": "ok",
        }, ensure_ascii=False)

    if action == "delete_all":
        sm.delete_all_user_data(user_id)
        return json.dumps({
            "action": "delete_all",
            "user_id": user_id,
            "result": "ok",
        }, ensure_ascii=False)

    return json.dumps({"error": f"未知操作: {action}"}, ensure_ascii=False)


def _handle_search_knowledge_base(inputs: dict, context: dict | None = None) -> str:
    """同时使用关键词匹配和语义向量搜索知识库"""
    import json
    from knowledge.knowledge_base import search_knowledge, search_books_semantic

    query = inputs.get("query", "")
    max_results = inputs.get("max_results", 5)

    # 1. JSON 关键词匹配
    keyword_results = search_knowledge(query, max_results=max_results)

    # 2. ChromaDB 语义搜索
    semantic_results = search_books_semantic(query, max_results=max_results)

    return json.dumps({
        "keyword_matches": keyword_results,
        "semantic_matches": semantic_results,
    }, ensure_ascii=False)
