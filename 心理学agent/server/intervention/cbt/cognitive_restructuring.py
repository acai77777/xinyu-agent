"""
认知重构——CBT最核心的技术
实现七栏思维记录法，Agent逐步引导用户填写
"""
from dataclasses import dataclass


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
