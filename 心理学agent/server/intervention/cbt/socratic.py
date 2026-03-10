"""
苏格拉底式提问模板
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


def get_socratic_guidance(distortion_type: str) -> list[str]:
    """根据认知扭曲类型，返回最适合的提问策略名称列表"""
    strategy_map = {
        "全或无思维": ["evidence_seeking", "alternative_perspective"],
        "过度概括": ["evidence_seeking", "clarification"],
        "读心术": ["assumption_probing", "evidence_seeking"],
        "灾难化": ["consequence_exploration", "evidence_seeking"],
        "应该陈述": ["clarification", "alternative_perspective"],
        "贴标签": ["clarification", "evidence_seeking"],
        "个人化": ["assumption_probing", "alternative_perspective"],
    }
    return strategy_map.get(distortion_type, ["evidence_seeking"])
