"""
中英文统一映射表
解决模块输出与期望输出之间的中英文不一致问题
"""

# ── 情绪近义词映射（标准情绪分类表：消极9 + 积极7 + 中性3 = 19类）──
# 每个 key 为标准情绪，set 包含该情绪的近义词和英文表达
EMOTION_SYNONYMS: dict[str, set[str]] = {
    # ── 消极 ──
    "悲伤": {"悲伤", "难过", "伤心", "哀伤", "心痛", "悲痛", "痛苦", "苦痛", "煎熬", "折磨",
             "沮丧", "消沉", "低落", "颓废", "失望", "落空", "灰心", "挫败", "挫折", "失败感",
             "困扰", "烦恼", "苦恼",
             "sad", "sadness", "grief", "sorrow", "pain", "painful", "suffering", "anguish", "agony",
             "depressed", "dejected", "down", "discouraged", "disappointed", "disappointment",
             "defeated", "frustrated", "frustration", "failure", "troubled", "bothered", "distressed"},
    "焦虑": {"焦虑", "紧张", "不安", "担忧", "忧虑", "担心", "矛盾", "纠结", "犹豫", "左右为难",
             "anxiety", "anxious", "nervous", "worried", "worry", "concerned", "uneasy",
             "conflicted", "ambivalent", "torn"},
    "愤怒": {"愤怒", "生气", "恼怒", "气愤", "暴怒", "烦躁", "烦", "不耐烦", "烦闷", "郁闷", "厌烦",
             "嫉妒", "羡慕", "妒忌", "不甘",
             "anger", "angry", "rage", "furious",
             "irritated", "annoyed", "restless", "jealous", "jealousy", "envy"},
    "恐惧": {"恐惧", "害怕", "惊恐", "畏惧", "fear", "afraid", "scared", "terrified"},
    "厌恶": {"厌恶", "反感", "恶心", "鄙视", "disgust", "disgusted", "repulsed", "aversion"},
    "羞耻": {"羞耻", "丢脸", "尴尬", "羞愧", "难堪", "shame", "ashamed", "embarrassed"},
    "内疚": {"内疚", "自责", "愧疚", "后悔", "懊悔", "悔恨", "遗憾",
             "guilt", "guilty", "regret", "remorse", "regretful"},
    "孤独": {"孤独", "寂寞", "疏离", "被忽视", "空虚", "空洞", "虚无", "麻木", "冷漠", "无感", "淡漠",
             "lonely", "loneliness", "isolated", "empty", "emptiness", "void", "numb", "indifferent", "apathetic"},
    "无助": {"无助", "无力", "绝望", "无望", "无力感", "helpless", "hopeless", "powerless", "desperate"},
    # ── 积极 ──
    "快乐": {"快乐", "开心", "高兴", "喜悦", "欣喜", "兴奋", "愉悦", "愉快", "舒畅", "畅快",
             "joy", "happy", "happiness", "excited", "pleasant", "pleased", "cheerful"},
    "感恩": {"感恩", "感激", "感谢", "grateful", "gratitude", "thankful"},
    "希望": {"希望", "期待", "期望", "盼望", "hope", "hopeful", "expectation"},
    "自豪": {"自豪", "骄傲", "自信", "成就感", "proud", "pride", "confident"},
    "平静": {"平静", "宁静", "安详", "释然", "淡然", "轻松", "放松",
             "calm", "peaceful", "serene", "tranquil", "relaxed", "relieved", "at ease"},
    "好奇": {"好奇", "兴趣", "求知", "curious", "curiosity", "interested"},
    "爱":   {"爱", "温暖", "温馨", "感动", "暖心", "关爱", "疼爱",
             "love", "warm", "warmth", "touched", "moved", "affection"},
    # ── 中性 ──
    "困惑": {"困惑", "迷茫", "迷惘", "不确定", "茫然", "confused", "confusion", "uncertain", "lost"},
    "无聊": {"无聊", "乏味", "无趣", "bored", "boredom", "tedious"},
    "疲惫": {"疲惫", "疲劳", "累", "倦怠", "精疲力竭", "exhausted", "tired", "fatigue"},
}


def emotion_matches(expected: str, actual: str) -> bool:
    """判断两个情绪名是否匹配（允许近义词）"""
    if expected == actual:
        return True
    # 在所有同义词组中查找
    for group in EMOTION_SYNONYMS.values():
        if expected in group and actual in group:
            return True
    # 单向查找
    synonyms = EMOTION_SYNONYMS.get(expected, {expected})
    return actual in synonyms


# ── 认知扭曲映射（英文key ↔ 中文名 ↔ 同义词）──
DISTORTION_MAP: dict[str, dict] = {
    "all_or_nothing":         {"cn": "全或无思维",   "en": "All-or-Nothing Thinking",     "aliases": {"非黑即白", "二分法思维"}},
    "overgeneralization":     {"cn": "过度概括",     "en": "Overgeneralization",           "aliases": {"以偏概全"}},
    "catastrophizing":        {"cn": "灾难化",       "en": "Catastrophizing",              "aliases": {"灾难化思维"}},
    "mind_reading":           {"cn": "读心术",       "en": "Mind Reading",                 "aliases": {"揣测他人想法"}},
    "fortune_telling":        {"cn": "预言家谬误",   "en": "Fortune Telling",              "aliases": {"算命", "预测未来"}},
    "should_statements":      {"cn": "应该陈述",     "en": "Should Statements",            "aliases": {"应该思维"}},
    "labeling":               {"cn": "贴标签",       "en": "Labeling",                     "aliases": {"标签化"}},
    "personalization":        {"cn": "个人化",       "en": "Personalization",              "aliases": {"个人归因"}},
    "emotional_reasoning":    {"cn": "情绪推理",     "en": "Emotional Reasoning",          "aliases": set()},
    "mental_filter":          {"cn": "心理过滤",     "en": "Mental Filter",                "aliases": {"选择性注意"}},
    "disqualifying_positive": {"cn": "否定正面",     "en": "Disqualifying the Positive",   "aliases": {"否定积极", "忽略正面"}},
    "minimization":           {"cn": "最小化",       "en": "Minimization",                 "aliases": set()},
    "control_fallacy":        {"cn": "控制谬误",     "en": "Control Fallacy",              "aliases": set()},
    "fairness_fallacy":       {"cn": "公平谬误",     "en": "Fallacy of Fairness",          "aliases": set()},
    "blaming":                {"cn": "指责",         "en": "Blaming",                      "aliases": {"外部归因"}},
}

# 构建统一查找表：任意名称 → 标准中文名
_DISTORTION_LOOKUP: dict[str, str] = {}
for key, info in DISTORTION_MAP.items():
    cn = info["cn"]
    _DISTORTION_LOOKUP[key] = cn                    # 英文key
    _DISTORTION_LOOKUP[cn] = cn                     # 中文名
    _DISTORTION_LOOKUP[info["en"]] = cn             # 英文全名
    _DISTORTION_LOOKUP[info["en"].lower()] = cn     # 英文全名小写
    for alias in info["aliases"]:
        _DISTORTION_LOOKUP[alias] = cn


def normalize_distortion(name: str) -> str:
    """将任意形式的扭曲类型名转为标准中文名"""
    return _DISTORTION_LOOKUP.get(name, _DISTORTION_LOOKUP.get(name.lower(), name))


def distortion_matches(expected: str, actual: str) -> bool:
    """判断两个认知扭曲类型是否匹配"""
    return normalize_distortion(expected) == normalize_distortion(actual)


# ── 风险等级映射（中↔英）──
RISK_LEVEL_MAP = {
    # 英文
    "critical": "critical", "high": "high", "medium": "medium", "low": "low",
    # 中文
    "危急": "critical", "严重": "critical",
    "高": "high", "高风险": "high",
    "中": "medium", "中等": "medium",
    "低": "low", "低风险": "low",
}


def normalize_risk_level(level: str) -> str:
    """将任意形式的风险等级转为标准英文小写"""
    return RISK_LEVEL_MAP.get(level, RISK_LEVEL_MAP.get(level.lower(), level.lower()))


# ── 策略方向映射（中↔英）──
APPROACH_MAP = {
    # 英文
    "cbt": "cbt",
    "positive_psychology": "positive_psychology",
    "safety": "safety",
    "active_listening": "active_listening",
    # 中文
    "认知行为疗法": "cbt", "认知行为": "cbt", "CBT": "cbt",
    "积极心理学": "positive_psychology",
    "安全协议": "safety", "安全守护": "safety", "危机干预": "safety",
    "积极倾听": "active_listening", "主动倾听": "active_listening", "倾听": "active_listening",
}


def normalize_approach(approach: str) -> str:
    """将任意形式的策略方向转为标准英文"""
    return APPROACH_MAP.get(approach, APPROACH_MAP.get(approach.lower(), approach.lower()))


# ── 技术名称映射（中↔英）──
TECHNIQUE_MAP: dict[str, set[str]] = {
    "认知重构":       {"cognitive_restructuring", "认知重构", "认知重建"},
    "苏格拉底式提问": {"socratic_questioning", "苏格拉底式提问"},
    "行为激活":       {"behavioral_activation", "行为激活"},
    "放松训练":       {"relaxation", "放松训练", "放松"},
    "危机响应":       {"crisis_response", "危机响应"},
    "感恩练习":       {"gratitude", "感恩", "感恩练习"},
    "优势发现":       {"strength_spotting", "优势发现"},
    "心流":           {"flow", "心流", "心流探索"},
    "意义探索":       {"meaning_exploration", "意义探索"},
    "品味":           {"savoring", "品味"},
    "最佳可能自我":   {"best_possible_self", "最佳可能自我"},
    "反映式倾听":     {"reflective_listening", "反映式倾听"},
    "情绪验证":       {"emotional_validation", "情绪验证"},
    "开放探索":       {"open_exploration", "开放探索"},
}


# 反向映射：英文→中文显示名
APPROACH_CN = {
    "cbt": "认知行为疗法",
    "positive_psychology": "积极心理学",
    "safety": "安全协议",
    "active_listening": "积极倾听",
}


def approach_to_cn(approach: str) -> str:
    """将策略方向英文转为中文显示名"""
    normalized = normalize_approach(approach)
    return APPROACH_CN.get(normalized, approach)


# 反向查找表：任意技术名 → 标准中文名
_TECHNIQUE_LOOKUP: dict[str, str] = {}
for _cn_name, _aliases in TECHNIQUE_MAP.items():
    for _alias in _aliases:
        _TECHNIQUE_LOOKUP[_alias] = _cn_name


def technique_to_cn(name: str) -> str:
    """将任意形式的技术名转为标准中文"""
    return _TECHNIQUE_LOOKUP.get(name, name)


def techniques_to_cn(names: list[str]) -> list[str]:
    """将技术名列表批量转为中文"""
    return [technique_to_cn(n) for n in names]


def technique_matches(expected: str, actual_list: list[str]) -> bool:
    """判断期望的技术是否在实际技术列表中"""
    # 查找期望技术的所有合法名称
    valid_names = set()
    for group in TECHNIQUE_MAP.values():
        if expected in group:
            valid_names = group
            break
    if not valid_names:
        valid_names = {expected}
    return bool(valid_names & set(actual_list))


# ── valence 映射 ──
VALENCE_MAP = {
    "positive": "positive", "negative": "negative", "neutral": "neutral",
    "积极": "positive", "正面": "positive",
    "消极": "negative", "负面": "negative",
    "中性": "neutral",
}


def normalize_valence(valence: str) -> str:
    """将任意形式的效价转为标准英文"""
    return VALENCE_MAP.get(valence, VALENCE_MAP.get(valence.lower(), valence.lower()))


_VALENCE_CN = {"positive": "积极", "negative": "消极", "neutral": "中性"}


def valence_to_cn(valence: str) -> str:
    """将效价转为中文显示名"""
    normalized = normalize_valence(valence)
    return _VALENCE_CN.get(normalized, valence)
