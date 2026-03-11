"""
Agent 主循环——支持 Anthropic / DeepSeek (OpenAI 兼容) 双 Provider
安全检查 → 后台评估 → LLM推理+工具调用 → 元认知监视 → 后置审核
"""
import asyncio
import json

from config import settings
from llm_client import get_async_client, get_model, get_light_model, _is_openai_compatible
from safety.crisis_detector import detect_crisis, RiskLevel
from safety.resources import CrisisHolding
from agent.tools import TOOLS, execute_tool
from agent.prompts import SYSTEM_PROMPT


# ============================================================
# LLM 调用抽象层——屏蔽 Anthropic / DeepSeek 差异
# ============================================================

def _is_deepseek() -> bool:
    return _is_openai_compatible()


async def _llm_chat(
    system: str,
    messages: list,
    tools: list | None = None,
    max_tokens: int | None = None,
    model_override: str | None = None,
) -> dict:
    """
    统一 LLM 调用接口。

    返回标准化格式：
    {
        "text": str | None,
        "tool_calls": [{"id": str, "name": str, "input": dict}, ...],
        "stop_reason": "end_turn" | "tool_use",
        "raw": <原始响应>,
    }
    """
    if max_tokens is None:
        max_tokens = settings.max_tokens

    if _is_deepseek():
        return await _deepseek_chat(system, messages, tools, max_tokens, model_override)
    else:
        return await _anthropic_chat(system, messages, tools, max_tokens, model_override)


async def _anthropic_chat(system, messages, tools, max_tokens, model_override):
    import anthropic
    client = get_async_client()

    model = get_model(model_override)

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    if tools:
        kwargs["tools"] = tools

    response = await client.messages.create(**kwargs)

    text = next((b.text for b in response.content if hasattr(b, "text")), None)
    tool_calls = [
        {"id": b.id, "name": b.name, "input": b.input}
        for b in response.content if b.type == "tool_use"
    ]

    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": "tool_use" if response.stop_reason == "tool_use" else "end_turn",
        "raw": response,
    }


def _tools_to_openai_format(tools: list) -> list:
    """将 Anthropic tool 格式转为 OpenAI function calling 格式"""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return result


def _messages_to_openai_format(system: str, messages: list) -> list:
    """将消息列表转为 OpenAI 格式（处理 Anthropic 原生格式和 DeepSeek 循环格式）"""
    oai_msgs = [{"role": "system", "content": system}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # DeepSeek 工具循环中的 tool 消息（已经是 OpenAI 格式）
        if role == "tool":
            oai_msgs.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": str(msg.get("content", "")),
            })
            continue

        # DeepSeek 工具循环中的 assistant 消息（带 _tool_calls_raw）
        if role == "assistant" and "_tool_calls_raw" in msg:
            assistant_msg: dict = {"role": "assistant", "content": msg.get("content") or None}
            tc_raw = msg["_tool_calls_raw"]
            if tc_raw:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tc_raw
                ]
            oai_msgs.append(assistant_msg)
            continue

        # Anthropic tool_result 列表 -> OpenAI tool message
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    oai_msgs.append({
                        "role": "tool",
                        "tool_call_id": item.get("tool_use_id", ""),
                        "content": str(item.get("content", "")),
                    })
            continue

        # Anthropic assistant with tool_use blocks (原始 Anthropic response.content)
        if role == "assistant" and not isinstance(content, str):
            text_parts = []
            tool_calls_oai = []
            for block in content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                elif hasattr(block, "type") and block.type == "tool_use":
                    tool_calls_oai.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input, ensure_ascii=False),
                        },
                    })

            assistant_msg2: dict = {"role": "assistant"}
            if text_parts:
                assistant_msg2["content"] = "\n".join(text_parts)
            else:
                assistant_msg2["content"] = None
            if tool_calls_oai:
                assistant_msg2["tool_calls"] = tool_calls_oai
            oai_msgs.append(assistant_msg2)
            continue

        oai_msgs.append({"role": role, "content": str(content)})

    return oai_msgs


async def _deepseek_chat(system, messages, tools, max_tokens, model_override):
    from openai import AsyncOpenAI

    client = get_async_client()
    model = get_model(model_override)

    oai_messages = _messages_to_openai_format(system, messages)

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        messages=oai_messages,
    )
    if tools:
        kwargs["tools"] = _tools_to_openai_format(tools)

    response = await client.chat.completions.create(**kwargs)

    choice = response.choices[0]
    text = choice.message.content
    tool_calls = []

    if choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })

    has_tools = len(tool_calls) > 0
    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": "tool_use" if has_tools else "end_turn",
        "raw": response,
    }


# ============================================================
# Agent 主循环
# ============================================================

async def run_agent(
    user_message: str,
    conversation_history: list,
    user_id: str,
    tools: list | None = None,
    system_prompt: str | None = None,
    crisis_holding: CrisisHolding | None = None,
) -> dict:
    """
    Agent主循环：
    1. 安全检查（前置，关键词+语义双层）
    2. 后台异步评估（非侵入式监控）
    3. LLM推理 + 工具调用循环
    4. 元认知监视器审核
    5. 输出安全审核（后置）
    6. 治疗联盟监测

    返回：{"text": str, "emotion": dict|None, "crisis_holding_active": bool}
    """
    if tools is None:
        tools = TOOLS
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    # === 前置安全检查 + 后台评估并发执行（避免串行等待）===
    risk, (bg_assessment, bg_emotion) = await asyncio.gather(
        detect_crisis(user_message),
        _background_assess(user_message, conversation_history),
    )

    # === 危机抱持模式处理 ===
    if crisis_holding is None:
        crisis_holding = CrisisHolding()

    if risk.level == RiskLevel.CRITICAL and risk.semantic_confirmed:
        if not crisis_holding.active:
            crisis_holding.enter()

    # 将风险信息和后台评估注入上下文
    context_enriched_prompt = system_prompt
    context_hints: list[str] = []

    if crisis_holding.active:
        context_hints.append(crisis_holding.get_phase_prompt())
        context_hints.append(
            "[绝对禁止] 在抱持模式下，不得使用任何工具（tool_use），"
            "不得进行认知评估，不得推荐练习。你唯一的任务是陪伴。"
        )

    if risk.level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        context_hints.append(
            f"[安全提示] 用户当前风险等级：{risk.level.value}，"
            f"请在回复中温和地建议寻求专业帮助。"
        )

    if bg_assessment:
        context_hints.append(f"[后台评估·仅供参考] {bg_assessment}")
        context_hints.append(
            "[重要] 以上评估仅作为你的内部参考。不要在对话中直接提及评估结果"
            "或认知扭曲的专业名称。优先共情倾听，只有在用户准备好时才温和地引导探索。"
        )

    alliance_warning = _check_alliance(user_message, conversation_history)
    if alliance_warning:
        context_hints.append(f"[关系提示] {alliance_warning}")

    try:
        from memory.user_profile import RelationshipStateMachine
        rsm = RelationshipStateMachine()
        relationship_guidance = rsm.get_guidance(user_id)
        if relationship_guidance:
            context_hints.append(f"[关系状态] {relationship_guidance}")
    except ImportError:
        pass

    if context_hints:
        context_enriched_prompt += "\n\n" + "\n".join(context_hints)

    messages = conversation_history + [{"role": "user", "content": user_message}]

    # 危机抱持模式下禁用工具
    active_tools = [] if crisis_holding.active else tools

    # === Agent 循环 ===
    while True:
        result = await _llm_chat(
            system=context_enriched_prompt,
            messages=messages,
            tools=active_tools or None,
            max_tokens=settings.max_tokens,
        )

        if result["stop_reason"] != "tool_use":
            final_text = result["text"] or ""

            final_text = await _meta_monitor(
                final_text, user_message, conversation_history
            )
            final_text = _post_safety_check(final_text)

            if crisis_holding.active:
                crisis_holding.advance()

            return {
                "text": final_text,
                "emotion": bg_emotion,
                "crisis_holding_active": crisis_holding.active,
            }

        # 处理工具调用
        tool_context = {
            "user_id": user_id,
            "user_messages": [
                msg["content"] for msg in conversation_history
                if msg["role"] == "user" and isinstance(msg["content"], str)
            ] + [user_message],
        }
        tool_results = []
        for tc in result["tool_calls"]:
            tool_output = execute_tool(tc["name"], tc["input"], context=tool_context)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": str(tool_output),
            })

        # 追加 assistant 消息和 tool_result
        if _is_deepseek():
            # OpenAI 格式：assistant message with tool_calls + 每个 tool 单独 message
            assistant_content = result["text"] or ""
            raw_choice = result["raw"].choices[0]
            # 存储原始 assistant message 用于后续转换
            messages.append({"role": "assistant", "content": assistant_content,
                             "_tool_calls_raw": raw_choice.message.tool_calls})
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_use_id"],
                    "content": tr["content"],
                })
        else:
            messages.append({"role": "assistant", "content": result["raw"].content})
            messages.append({"role": "user", "content": tool_results})


async def _background_assess(
    user_message: str,
    conversation_history: list | None = None,
) -> tuple[str | None, dict | None]:
    """
    非侵入式后台评估——用轻量模型做情绪/认知模式扫描。
    结果注入system prompt作为LLM的"内部参考"。
    """
    context_parts = []
    if conversation_history:
        recent = conversation_history[-6:]
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "AI"
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            context_parts.append(f"{role_label}：{content[:200]}")

    if context_parts:
        context_text = "\n".join(context_parts)
        eval_input = f"最近对话：\n{context_text}\n\n当前用户消息：{user_message}"
    else:
        eval_input = user_message

    try:
        # 后台评估用轻量模型
        light_model = get_light_model()
        result = await _llm_chat(
            system=(
                "简要评估用户情绪和可能的认知模式。注意结合对话上下文判断——"
                "用户当前的情绪可能是前几轮的延续或转变。返回JSON格式：\n"
                '{"assessment": "一句话概括（需体现情绪变化趋势）", '
                '"emotion": {"primary": "情绪名", "intensity": 1-10}}'
            ),
            messages=[{"role": "user", "content": eval_input}],
            max_tokens=200,
            model_override=light_model,
        )
        parsed = json.loads(result["text"].strip())
        assessment = parsed.get("assessment", "")
        emotion = parsed.get("emotion")
        return (assessment if len(assessment) > 5 else None, emotion)
    except Exception:
        return (None, None)


def _check_alliance(user_message: str, history: list) -> str | None:
    """治疗联盟监测——检测用户对Agent本身的负面反馈（关系破裂信号）。"""
    alliance_rupture_keywords = {
        "empathy_failure": ["你不懂", "你根本不理解", "说了也没用", "你不明白"],
        "trust_crisis": ["你只是机器", "你只是AI", "你又不是人", "假惺惺"],
        "intervention_mismatch": ["别跟我说这些", "没用的", "不想做练习", "烦死了"],
    }
    guidance_map = {
        "empathy_failure": (
            "用户感到不被理解。请先真诚道歉（'对不起，我可能没有完全理解你的感受'），"
            "然后请用户帮助你更好地理解。不要急于给建议。"
        ),
        "trust_crisis": (
            "用户质疑AI的能力。请坦诚承认自己是AI的局限性，同时肯定用户愿意表达的勇气，"
            "并建议专业人类咨询师作为补充。"
        ),
        "intervention_mismatch": (
            "用户对当前干预方式不满。请立即停止当前策略，回到倾听模式，"
            "询问用户现在最需要什么。尊重用户的节奏。"
        ),
    }

    for rupture_type, keywords in alliance_rupture_keywords.items():
        for kw in keywords:
            if kw in user_message:
                return guidance_map[rupture_type]
    return None


async def _meta_monitor(
    response_text: str,
    user_message: str,
    conversation_history: list,
    user_risk_history: bool = False,
) -> str:
    """
    元认知监视器（Meta-Monitor）
    - 第一层：规则引擎（零成本）
    - 第二层：语义审核（仅高风险用户）
    """
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
            return _rule_based_fix(response_text, pattern, issue)

    if not user_risk_history:
        return response_text

    try:
        light_model = get_light_model()
        result = await _llm_chat(
            system=(
                "你是心理安全审核专家。检查AI情感支持助手的回复是否存在以下问题：\n"
                "1. 顺从性确认：是否附和了用户的消极自我评价\n"
                "2. 过度承诺：是否做出了不切实际的保证\n"
                "3. 过早干预：用户还在倾诉时，是否急于启动练习或给建议\n"
                "4. 隐性诊断：是否暗示用户有某种精神疾病\n\n"
                '返回JSON：{"safe": true/false, "issue": "问题描述", "suggestion": "修正建议"}\n'
                '如果安全，返回：{"safe": true}'
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"用户消息：{user_message}\n\n"
                    f"AI回复：{response_text}\n\n"
                    f"最近对话上下文：{str(conversation_history[-6:])[-500:]}"
                ),
            }],
            max_tokens=256,
            model_override=light_model,
        )
        parsed = _parse_json_safe(result["text"] or "")

        if not parsed.get("safe", True):
            suggestion = parsed.get("suggestion", "请重新生成一个更安全的回复")
            regen = await _llm_chat(
                system=(
                    f"你是心理安全修正助手。原始回复存在问题：{parsed.get('issue', '')}。"
                    f"请根据建议修正：{suggestion}"
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"用户消息：{user_message}\n\n"
                        f"需要修正的AI回复：{response_text}\n\n"
                        f"请输出修正后的回复（只输出修正后的文本，不要解释）"
                    ),
                }],
                max_tokens=1024,
                model_override=light_model,
            )
            return (regen["text"] or response_text).strip()
    except Exception:
        pass

    return response_text


def _rule_based_fix(response_text: str, matched_pattern: str, issue: str) -> str:
    """规则引擎命中时的简单修正"""
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


def _parse_json_safe(text: str) -> dict:
    """安全解析 JSON，处理 markdown 代码块包裹"""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return {"safe": True}
