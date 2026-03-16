"""
Token 使用量对比度量——优化前 vs 优化后

度量方法：用字符数 / 1.5 估算中文 token 数（中文平均 1 字 ≈ 1.5 token）
对比维度：
  1. System prompt 大小（冷启动 vs 暖启动）
  2. 20 轮对话的 messages 大小（无压缩 vs 有压缩）
  3. 子 Agent 上下文隔离效果
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, patch, MagicMock
from context.compressor import ConversationCompressor
from context.session_notes import SessionNotes
from agent.prompts import SYSTEM_PROMPT


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文 1 字 ≈ 1.5 token，英文 1 word ≈ 1 token）"""
    return int(len(text) * 1.5)


def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        total += 10  # role/metadata 开销
    return total


def make_realistic_messages(turns: int) -> list[dict]:
    """生成模拟的真实心理咨询对话"""
    templates_user = [
        "最近工作压力特别大，老板总是在deadline前临时加需求，我感觉喘不过气来。",
        "我试了你说的方法记录想法，但是发现自己脑子里全是消极的东西，根本停不下来。",
        "嗯，我昨天和同事吵了一架，她说我效率低，我觉得她说得对，我确实不行。",
        "有时候我会想，是不是我不适合这份工作，要不要辞职算了。",
        "我父母也一直对我的工作选择不满意，觉得我应该考公务员。",
        "上周有一天我心情还不错，完成了一个小项目，同事还夸我了。",
        "但好心情也没持续多久，周末又开始焦虑下周的工作了。",
        "我试了深呼吸放松，好像有一点用，但是效果不太持久。",
        "最近失眠也很严重，晚上翻来覆去睡不着，脑子里全是工作的事。",
        "我觉得自己像个陀螺一样，不停地转，但不知道在转什么。",
        "其实我小时候成绩很好的，不知道为什么长大后总觉得自己不够好。",
        "谢谢你听我说这些，平时我都不太敢跟别人讲这些。",
        "我今天心情好了一点，想聊聊怎么改善睡眠的问题。",
        "我注意到一个规律，每次周日晚上焦虑最严重。",
        "如果周末做了些开心的事情，周一的状态会好很多。",
        "我在想要不要尝试培养一个新爱好来转移注意力。",
        "之前你提到过感恩日记，我试了三天，感觉还不错。",
        "我发现自己总是在用'必须'和'应该'来要求自己，这样活得好累。",
        "今天和朋友聊了聊，她也有类似的焦虑，我突然觉得不那么孤单了。",
        "我想给自己定一个小目标，每天至少做一件让自己开心的事情。",
    ]
    templates_assistant = [
        "我能感受到你现在承受的压力。你说'喘不过气来'，这个描述很生动。能告诉我，通常这种感觉在什么时候最强烈吗？",
        "记录想法是很棒的第一步。发现脑子里都是消极内容，这本身就是一个重要的觉察。我们可以一起看看这些想法，找到更平衡的视角。",
        "你提到觉得同事说得对，你'确实不行'。我想问一下，如果你的好朋友遇到同样的情况，你也会对她说同样的话吗？",
        "辞职的念头出现时，通常是在什么情境下？有没有过不想辞职、甚至觉得工作还行的时刻？",
        "听起来你面临着来自不同方向的期望。你自己内心对工作最看重的是什么？",
        "完成项目被夸奖时的那种感觉，你还记得吗？那一刻你对自己是怎么看的？",
        "你观察到好心情不持久，这个觉察很有价值。焦虑似乎有一个'预期'的特点——它总在事情还没发生时就出现。",
        "深呼吸有用是好消息。效果不持久很正常，我们可以试试把它变成一个更固定的习惯，比如每天设定两个固定时间。",
        "失眠常常和白天的焦虑有关。你有没有注意到，哪些天晚上睡得比较好，那天发生了什么不同的事？",
        "这个比喻很形象。我们一起想想，你希望往哪个方向转。如果能暂停一下这个陀螺，你最想做什么？",
        "'小时候成绩好'和'现在觉得不够好'之间，是否有什么经历改变了你对自己的看法？",
        "你愿意分享这些需要勇气，感谢你的信任。接下来你最想先处理哪个方面的困扰？",
        "很高兴听到你心情有好转。睡眠确实是一个我们可以用具体方法改善的领域，你想从哪里开始？",
        "发现周日晚上最焦虑，这是一个很好的自我观察。你觉得周日晚上的焦虑主要在担心什么？",
        "你已经在建立因果联系了：周末开心→周一状态好。这说明积极活动确实对你有效。",
        "培养新爱好是个好想法。你之前有没有什么一直想尝试但还没开始的事情？",
        "坚持了三天感恩日记，这很棒！你在记的时候，有没有发现什么以前忽略的积极面？",
        "你发现了'必须'和'应该'这个模式——这是很深的自我觉察。我们可以试试把这些词换成'我希望'或'最好能'，感受一下有什么不同。",
        "和朋友聊天让你感到不孤单，这说明社会连接对你很重要。你平时和朋友见面的频率怎样？",
        "每天做一件开心的事，这个目标很具体也很可行。你已经想好今天要做什么了吗？",
    ]
    msgs = []
    for i in range(turns):
        msgs.append({"role": "user", "content": templates_user[i % len(templates_user)]})
        msgs.append({"role": "assistant", "content": templates_assistant[i % len(templates_assistant)]})
    return msgs


def simulate_old_full_context() -> str:
    """模拟旧的 6 层全量注入"""
    hints = []

    # 叙事记忆
    hints.append(
        "[叙事背景] 用户经历了持续的工作压力，从最初的焦虑逐渐发展为自我怀疑。"
        "第一个弧线'工作压力焦虑'仍在持续，情绪趋势为波动中。"
        "近期出现了一些积极变化——用户开始尝试自我照顾。"
    )

    # 用户画像
    hints.append(
        "[用户画像] 称呼：小明；性格优势：坚持、好奇心、善良；"
        "常见认知扭曲：灾难化、非黑即白思维、读心术；"
        "偏好干预方式：认知重构、行为激活；当前阶段：困扰期"
    )

    # 关系状态
    hints.append(
        "[关系状态] 当前关系健康。用户信任度良好，愿意分享深层感受。"
        "建议：保持稳定的支持性回应节奏。"
    )

    # 知识库检索（3 条）
    hints.append(
        "[知识库参考] 以下是与用户话题相关的心理学知识，仅供你内部参考，"
        "不要直接照搬或引用书名，而是自然地融入对话中：\n"
        "【认知行为疗法入门·第三章】CBT 的核心假设是：我们的情绪和行为不是由事件本身决定的，"
        "而是由我们对事件的解释（认知）决定的。自动思维（automatic thoughts）是指在特定情境下"
        "自动浮现的想法，往往带有消极色彩和认知偏差。识别这些自动思维是改变的第一步。\n"
        "【积极心理学·第五章】感恩练习已被大量研究证实可以提升幸福感。每天记录三件感恩的事，"
        "持续两周以上就能产生显著效果。重要的是关注具体细节而非笼统概括。\n"
        "【认知行为疗法入门·第七章】睡眠卫生是改善失眠的基础方法。包括固定作息、"
        "限制咖啡因、创建舒适的睡眠环境、睡前放松程序等。"
    )

    # 会话策略
    hints.append(
        "[会话策略·第2版]\n"
        "核心议题：工作压力导致的焦虑和自我怀疑\n"
        "阶段目标：识别消极自动思维→建立认知重构习惯\n"
        "主要方法：认知行为疗法\n"
        "推荐技术：思维记录表、苏格拉底式提问、行为激活\n"
        "注意事项：避免过早引入深层信念挑战、注意用户的节奏\n"
        "[重要] 以上策略是你的内部工作计划，不要直接告诉用户。按此策略自然引导对话。"
    )

    return "\n\n".join(hints)


def simulate_warm_compact() -> str:
    """模拟 SessionNotes 暖启动紧凑模式"""
    notes = SessionNotes(
        user_profile_summary="小明；阶段:困扰期；优势:坚持、好奇心；认知扭曲:灾难化、非黑即白",
        presenting_issue="工作压力导致的焦虑和自我怀疑",
        session_strategy="认知行为疗法：识别消极思维→认知重构（思维记录、苏格拉底提问、行为激活）",
        narrative_trend="fluctuating",
        narrative_context="[叙事背景] 工作压力弧线持续中，近期有积极变化",
        relationship_state="normal",
        recent_emotion="焦虑，强度 6/10",
        active_distortions=["灾难化"],
        key_moments=["意识到'必须/应该'模式", "感恩日记坚持3天"],
    )
    return notes.to_compact_prompt()


async def measure_compression(turns: int):
    """度量压缩效果"""
    msgs = make_realistic_messages(turns)
    comp = ConversationCompressor(compress_threshold=5, keep_recent=6)

    with patch.object(comp, "_summarize", new_callable=AsyncMock) as mock:
        mock.return_value = (
            "用户因工作压力产生焦虑和自我怀疑，老板频繁加需求，与同事发生冲突。"
            "尝试了想法记录和深呼吸，有一定效果但不持久。存在'必须/应该'思维模式。"
            "近期积极变化：完成项目获夸奖、感恩日记坚持三天、与朋友倾诉感到不孤单。"
            "失眠问题待处理。周日晚上焦虑最严重，周末活动对周一状态有积极影响。"
        )
        compressed_msgs, summary = await comp.compress_if_needed(msgs, "test")

    return msgs, compressed_msgs, summary


async def main():
    print("=" * 70)
    print("         Token 使用量对比度量：优化前 vs 优化后")
    print("=" * 70)

    # ── 1. System Prompt 对比 ──
    print("\n" + "─" * 70)
    print("1. System Prompt 大小对比")
    print("─" * 70)

    base_tokens = estimate_tokens(SYSTEM_PROMPT)
    old_context = simulate_old_full_context()
    warm_context = simulate_warm_compact()

    old_total = base_tokens + estimate_tokens(old_context)
    warm_total = base_tokens + estimate_tokens(warm_context)

    print(f"  基础 prompt:           {base_tokens:>5} token")
    print(f"  旧 6层全量注入:        {estimate_tokens(old_context):>5} token  ({len(old_context)} 字符)")
    print(f"  新 暖启动紧凑模式:     {estimate_tokens(warm_context):>5} token  ({len(warm_context)} 字符)")
    print()
    print(f"  旧 system prompt 总计: {old_total:>5} token")
    print(f"  新 system prompt 总计: {warm_total:>5} token")
    print(f"  节省:                  {old_total - warm_total:>5} token  ({(old_total - warm_total)/old_total*100:.0f}%)")

    # ── 2. 对话历史对比 ──
    print("\n" + "─" * 70)
    print("2. 对话历史大小对比（20 轮对话）")
    print("─" * 70)

    raw_msgs, compressed_msgs, summary = await measure_compression(20)
    raw_tokens = estimate_messages_tokens(raw_msgs)
    compressed_tokens = estimate_messages_tokens(compressed_msgs)
    summary_tokens = estimate_tokens(summary) if summary else 0

    print(f"  原始消息数:            {len(raw_msgs):>5} 条")
    print(f"  压缩后消息数:          {len(compressed_msgs):>5} 条")
    print()
    print(f"  原始消息 token:        {raw_tokens:>5} token")
    print(f"  压缩后消息 token:      {compressed_tokens:>5} token")
    print(f"  摘要 token:            {summary_tokens:>5} token（注入 system prompt）")
    print(f"  压缩后总计:            {compressed_tokens + summary_tokens:>5} token")
    print(f"  节省:                  {raw_tokens - compressed_tokens - summary_tokens:>5} token  ({(raw_tokens - compressed_tokens - summary_tokens)/raw_tokens*100:.0f}%)")

    # ── 3. 总计对比 ──
    print("\n" + "─" * 70)
    print("3. 单次 LLM 调用总 token 对比（20 轮对话）")
    print("─" * 70)

    old_call = old_total + raw_tokens
    new_call = warm_total + compressed_tokens + summary_tokens

    print(f"  旧方案（全量注入 + 原始历史）:   {old_call:>6} token")
    print(f"  新方案（紧凑笔记 + 压缩历史）:   {new_call:>6} token")
    print(f"  节省:                             {old_call - new_call:>6} token  ({(old_call - new_call)/old_call*100:.0f}%)")

    # ── 4. 子 Agent 隔离效果 ──
    print("\n" + "─" * 70)
    print("4. 子 Agent 上下文隔离效果")
    print("─" * 70)

    # 分析 agent 只接收最近 6 轮 + 精简 system prompt
    analysis_system = (
        "简要评估用户情绪和可能的认知模式。注意结合对话上下文判断——"
        "用户当前的情绪可能是前几轮的延续或转变。"
        "用户画像：小明；阶段:困扰期"
        '\n返回JSON格式：\n'
        '{"assessment": "一句话概括", "emotion": {"primary": "情绪名", "intensity": 1-10}}'
    )
    analysis_msgs = raw_msgs[-12:]  # 最近 6 轮
    analysis_tokens = estimate_tokens(analysis_system) + estimate_messages_tokens(analysis_msgs)

    # 知识 agent 只接收查询 + 候选结果
    knowledge_input = "工作压力导致的焦虑和自我怀疑 我最近工作压力很大"
    knowledge_candidates = (
        "【认知行为疗法入门·第三章】CBT核心假设...(200字)\n"
        "【积极心理学·第五章】感恩练习已被大量研究证实...(200字)\n"
        "【认知行为疗法入门·第七章】睡眠卫生...(200字)"
    )
    knowledge_tokens = estimate_tokens(knowledge_input) + estimate_tokens(knowledge_candidates)

    print(f"  旧方案：子任务共享主 Agent 全部上下文")
    print(f"    分析评估上下文:     {old_call:>6} token（=主调用全量）")
    print(f"    知识检索上下文:     {old_call:>6} token（=主调用全量）")
    print()
    print(f"  新方案：子 Agent 隔离上下文")
    print(f"    分析 Agent 上下文:  {analysis_tokens:>6} token（仅最近6轮 + 精简 prompt）")
    print(f"    知识 Agent 上下文:  {knowledge_tokens:>6} token（仅查询 + 候选结果）")
    print(f"    子 Agent 总计:      {analysis_tokens + knowledge_tokens:>6} token")
    print()
    sub_agent_saved = (old_call * 2) - (analysis_tokens + knowledge_tokens)
    print(f"  子 Agent 上下文节省:  {sub_agent_saved:>6} token  "
          f"({sub_agent_saved/(old_call*2)*100:.0f}%)")

    # ── 5. 总结 ──
    print("\n" + "=" * 70)
    print("                         总结")
    print("=" * 70)

    total_old = old_call + old_call * 2  # 主调用 + 2个子任务共享上下文
    total_new = new_call + analysis_tokens + knowledge_tokens

    print(f"  20轮对话总输入 token（含子任务）:")
    print(f"    旧方案: {total_old:>6} token")
    print(f"    新方案: {total_new:>6} token")
    print(f"    节省:   {total_old - total_new:>6} token  ({(total_old - total_new)/total_old*100:.0f}%)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
