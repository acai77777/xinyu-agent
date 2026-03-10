"""
心理教育材料——Agent 内部参考的知识库
提供去专业化语言的心理学概念解释，供 Agent 在对话中自然地传达给用户
"""


# === 认知扭曲的通俗解释（对齐 distortion.py 的 15 种类型） ===

COGNITIVE_DISTORTIONS = {
    "all_or_nothing": {
        "name": "全或无思维",
        "plain_language": "用非黑即白的方式看事情，觉得要么完美要么就是失败，没有中间地带。",
        "example": "比如考试没拿满分就觉得'我什么都不会'，或者一次表现不好就觉得'我彻底完蛋了'。",
        "gentle_reframe": "其实很多事情并不是只有两种极端，大多数时候我们处在中间某个位置——这本身就是正常的。",
    },
    "overgeneralization": {
        "name": "过度概括",
        "plain_language": "因为一件事不顺利，就觉得所有事情都会不顺利。",
        "example": "比如一次面试没通过就觉得'我永远找不到工作'。",
        "gentle_reframe": "一次经历并不能代表所有情况，每次机会其实都是独立的。",
    },
    "catastrophizing": {
        "name": "灾难化",
        "plain_language": "总是往最坏的方向想，把事情的后果想象得很严重。",
        "example": "比如迟到了五分钟就觉得'完了，领导一定要开除我'。",
        "gentle_reframe": "我们可以一起看看，除了最坏的情况，还有哪些其他可能性？",
    },
    "mind_reading": {
        "name": "读心术",
        "plain_language": "不经确认就认为自己知道别人在想什么，而且通常觉得别人在对自己做负面评价。",
        "example": "比如'他没回我消息，一定是讨厌我了'。",
        "gentle_reframe": "其实我们很难真的知道别人在想什么，也许对方只是在忙呢？",
    },
    "fortune_telling": {
        "name": "预言家谬误",
        "plain_language": "觉得自己能预知未来，而且预测的结果总是消极的。",
        "example": "比如'这次一定会失败的，没必要尝试了'。",
        "gentle_reframe": "未来还没发生，我们其实没办法确定结果。不试试的话，怎么知道呢？",
    },
    "should_statements": {
        "name": "应该陈述",
        "plain_language": "用'应该''必须'的标准来要求自己或别人，达不到就自责或生气。",
        "example": "比如'我不应该犯这种错误'或者'他应该理解我'。",
        "gentle_reframe": "'应该'有时候会变成一种无形的压力。如果换成'我希望''如果能……就更好了'，是不是感觉轻松一些？",
    },
    "labeling": {
        "name": "贴标签",
        "plain_language": "因为一件事就给自己或别人贴上一个固定的标签。",
        "example": "比如做错一件事就说'我是个废物'，而不是'我在这件事上犯了个错'。",
        "gentle_reframe": "一个行为并不能定义一个人。犯错只是说明这件事没做好，不代表你这个人不好。",
    },
    "personalization": {
        "name": "个人化",
        "plain_language": "把不是自己的责任揽到自己身上，觉得所有不好的事都跟自己有关。",
        "example": "比如朋友心情不好就觉得'一定是我惹他生气了'。",
        "gentle_reframe": "很多事情的发生是多种原因造成的，不一定都跟你有关系。",
    },
    "emotional_reasoning": {
        "name": "情绪推理",
        "plain_language": "用感受来当作事实的证据——'我感觉是这样，所以一定是这样'。",
        "example": "比如'我觉得自己很没用，所以我一定是个没用的人'。",
        "gentle_reframe": "感受是真实的，但感受不等于事实。心情低落的时候，我们容易把感觉当成现实。",
    },
    "mental_filter": {
        "name": "心理过滤",
        "plain_language": "像一个只能过滤出坏消息的筛子，只关注负面的部分，忽略了正面的信息。",
        "example": "比如收到10条好评和1条差评，却只记住那条差评。",
        "gentle_reframe": "试着完整地看待一件事——好的和不好的都包括在内。",
    },
    "disqualifying_positive": {
        "name": "否定正面",
        "plain_language": "即使有好事发生，也会找理由把它否定掉，觉得'不算数'。",
        "example": "比如别人夸你做得好，你却想'他只是客气而已'。",
        "gentle_reframe": "别人的认可是真实的。试着接受这份正面反馈，让自己开心一下也没关系。",
    },
    "minimization": {
        "name": "最小化",
        "plain_language": "把自己的成就和优点缩小，觉得没什么了不起的。",
        "example": "比如完成了一个很有挑战的项目却说'这没什么，谁都能做到'。",
        "gentle_reframe": "你做到的事情是有价值的。如果换作你的好朋友做到了同样的事，你会怎么评价？",
    },
    "control_fallacy": {
        "name": "控制谬误",
        "plain_language": "要么觉得自己对所有事情都无能为力，要么觉得所有事情都是自己造成的。",
        "example": "比如'我什么都改变不了'或者'家人不开心都是因为我'。",
        "gentle_reframe": "有些事我们能影响，有些事不在我们的控制范围内。分清哪些能改变、哪些不能，会让我们更有力量。",
    },
    "fairness_fallacy": {
        "name": "公平谬误",
        "plain_language": "强烈地觉得事情应该按照'公平'的标准来，当现实不符合预期时就感到愤怒或委屈。",
        "example": "比如'我付出这么多，他却不领情，太不公平了'。",
        "gentle_reframe": "每个人对'公平'的理解不同。关注自己能控制的行动，可能比等待别人的回应更让你自在。",
    },
    "blaming": {
        "name": "指责",
        "plain_language": "把问题的原因完全归咎于别人或外部环境，或者完全归咎于自己。",
        "example": "比如'都怪他我才会这样'或者'一切都是我的错'。",
        "gentle_reframe": "大多数问题是多方面因素造成的。与其追究谁的错，不如想想有什么是我们现在可以做的。",
    },
}


# === CBT 基本原理（去专业化表达） ===

CBT_CONCEPTS = {
    "cognitive_model": {
        "title": "想法、情绪和行为的关系",
        "explanation": "我们的感受很大程度上来自我们怎么想。同一件事情，用不同的方式去看，感受就会很不同。这不是说你的感受不对，而是说如果我们能看到更多角度，感受也会多一些选择。",
        "metaphor": "就像戴了一副有色眼镜——透过灰色镜片看世界，一切都是灰暗的。但如果我们知道自己戴着眼镜，就可以试着把它摘下来看看。",
    },
    "automatic_thoughts": {
        "title": "自动冒出来的想法",
        "explanation": "有时候一些想法会自动蹦出来，速度很快，我们甚至没意识到就已经在影响心情了。注意到这些想法是第一步——不需要评判它们，只是注意到就好。",
        "metaphor": "像弹幕一样飘过脑海——它们自动出现，但你不一定要认同每一条。",
    },
    "cognitive_restructuring": {
        "title": "换个角度看问题",
        "explanation": "不是说你的想法是'错'的，而是一起来看看有没有其他同样合理的看法。有时候我们会在烦恼时只看到一面，如果能多看几面，心情往往会好一些。",
        "metaphor": "就像从不同的窗户看同一条街——每扇窗看到的景象不完全相同。",
    },
    "behavioral_activation": {
        "title": "用行动改善心情",
        "explanation": "当我们情绪低落时，往往不想做任何事，但不做事又会让心情更差，形成恶性循环。即使不想动，做一些小事——哪怕只是散个步、整理一下桌面——都可能帮助打破这个循环。",
        "metaphor": "不需要等心情好了才行动，有时候先行动起来，心情自然会跟上来。",
    },
    "thought_record": {
        "title": "思维记录",
        "explanation": "把脑海中的想法写下来，看看它们是什么样子，有没有遗漏什么信息。写下来之后再看，常常会发现事情没有想象中那么绝对。",
        "metaphor": "像把一团乱麻理出来——当想法在脑子里转的时候很混乱，写出来就清楚多了。",
    },
}


# === 积极心理学核心概念 ===

POSITIVE_PSYCHOLOGY = {
    "perma": {
        "title": "幸福的五个支柱",
        "explanation": "心理学家Seligman提出幸福有五个维度：积极情绪（开心的时刻）、投入（全身心做喜欢的事）、关系（和他人的联结）、意义（觉得生活有目标）、成就（完成目标的满足感）。幸福不是只有一种样子，每个人可以在不同的维度找到自己的幸福。",
    },
    "gratitude": {
        "title": "感恩的力量",
        "explanation": "研究发现，有意识地关注生活中值得感恩的事，可以提升幸福感、改善睡眠、增强人际关系。感恩不是忽视困难，而是在困难中也能看到生活中好的一面。",
    },
    "character_strengths": {
        "title": "性格优势",
        "explanation": "每个人都有自己独特的性格优势——比如好奇心、善良、坚持、幽默等。发现并运用这些优势，不仅能让你更快乐，也能帮助你更好地应对困难。优势不是天赋，而是你最自然、最有能量的行为方式。",
    },
    "growth_mindset": {
        "title": "成长思维",
        "explanation": "相信能力可以通过努力和学习来提高，而不是觉得一切都是天生注定的。遇到困难的时候，成长思维会让你更愿意去尝试和坚持。",
    },
    "flow": {
        "title": "心流体验",
        "explanation": "你有没有做某件事时完全忘记了时间？那种全身心投入、挑战和能力刚好匹配的状态就叫'心流'。经常进入心流状态的人往往更有满足感和幸福感。",
    },
    "resilience": {
        "title": "心理韧性",
        "explanation": "心理韧性不是说不会受伤或不会难过，而是能在经历困难之后恢复过来、甚至成长。它可以通过练习来增强——保持社会联结、照顾好身体、接受变化是生活的一部分。",
    },
    "savoring": {
        "title": "品味美好",
        "explanation": "刻意放慢脚步，去注意和享受生活中美好的瞬间——一杯热茶、一个温暖的阳光、朋友的一句关心。研究表明，学会品味积极体验可以延长快乐的持续时间。",
    },
}


# === 情绪调节基础知识 ===

EMOTION_REGULATION = {
    "emotion_basics": {
        "title": "情绪是什么",
        "explanation": "情绪是身体对事情的自然反应，没有'好'或'坏'之分。难过、生气、害怕都是正常的情绪，它们在提醒我们一些重要的事情。不需要消除负面情绪，而是学会和它们相处。",
    },
    "window_of_tolerance": {
        "title": "情绪承受窗口",
        "explanation": "每个人都有一个'窗口'——在这个范围内，我们能正常思考和应对。当情绪太强烈，超出了这个窗口，我们就可能会感到崩溃或者变得麻木。好消息是，这个窗口可以通过练习慢慢扩大。",
    },
    "grounding": {
        "title": "接地技术",
        "explanation": "当情绪让你感到快要崩溃时，可以用身体的感觉把自己拉回来——感受脚踩在地上的感觉、注意周围能看到的5样东西、听到的3种声音。这些简单的方法能帮助你在强烈的情绪中稳住自己。",
    },
    "self_compassion": {
        "title": "自我关怀",
        "explanation": "像对待自己最好的朋友一样对待自己。当你犯错或者遇到困难时，不是责备自己，而是对自己说'没关系，每个人都会遇到困难的'。自我关怀不是放纵，而是给自己继续前进的力量。",
    },
}


def get_psychoeducation(topic: str) -> dict | None:
    """
    按主题获取心理教育内容。

    topic 支持两种格式：
    - 直接类别: "cognitive_model", "gratitude", "emotion_basics"
    - 带前缀: "distortion:all_or_nothing", "cbt:thought_record"

    返回包含 title / explanation 的字典，未找到返回 None。
    """
    # 带前缀格式
    if ":" in topic:
        prefix, key = topic.split(":", 1)
        source = {
            "distortion": COGNITIVE_DISTORTIONS,
            "cbt": CBT_CONCEPTS,
            "positive": POSITIVE_PSYCHOLOGY,
            "emotion": EMOTION_REGULATION,
        }.get(prefix)
        if source and key in source:
            return source[key]
        return None

    # 在所有知识库中查找
    for source in [COGNITIVE_DISTORTIONS, CBT_CONCEPTS, POSITIVE_PSYCHOLOGY, EMOTION_REGULATION]:
        if topic in source:
            return source[topic]

    return None


def get_distortion_explanation(distortion_type: str) -> dict | None:
    """
    获取认知扭曲的通俗解释。
    distortion_type: KEYWORD_PATTERNS 的 key，如 "all_or_nothing"
    """
    return COGNITIVE_DISTORTIONS.get(distortion_type)


def list_topics() -> dict[str, list[str]]:
    """列出所有可用的教育主题，按类别分组。"""
    return {
        "distortion": list(COGNITIVE_DISTORTIONS.keys()),
        "cbt": list(CBT_CONCEPTS.keys()),
        "positive": list(POSITIVE_PSYCHOLOGY.keys()),
        "emotion": list(EMOTION_REGULATION.keys()),
    }
