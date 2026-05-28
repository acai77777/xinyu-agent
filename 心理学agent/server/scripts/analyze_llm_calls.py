"""分析 llm_calls.jsonl:验证"上下文越长 → 输出越长"假设。

读 /app/data/llm_calls.jsonl,对每条记录计算:
- messages 总字符数 (= 上下文长度)
- response_text 字数 (= AI 输出长度)
- 是否包含新 prompt 标志 ("硬约束,违反即视为失败回复")

分桶统计:按 messages 长度分 4 档,看每档的 response 字数分布。
"""
import json
import sys
from pathlib import Path

LOG = Path("/app/data/llm_calls.jsonl")
NEW_PROMPT_MARKER = "硬约束,违反即视为失败回复"


def msg_chars(messages):
    n = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            n += len(c)
        elif isinstance(c, list):
            for item in c:
                if isinstance(item, dict):
                    n += len(json.dumps(item, ensure_ascii=False))
                else:
                    n += len(str(item))
        else:
            n += len(str(c))
    return n


def main():
    records = []
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            system = r.get("system") or ""
            messages = r.get("messages") or []
            resp = r.get("response_text") or ""
            if not resp:
                continue
            records.append({
                "ctx_len": msg_chars(messages),
                "sys_len": len(system),
                "resp_len": len(resp),
                "new_prompt": NEW_PROMPT_MARKER in system,
                "stop": r.get("stop_reason"),
            })

    print(f"总记录: {len(records)}")
    new_recs = [r for r in records if r["new_prompt"]]
    old_recs = [r for r in records if not r["new_prompt"]]
    print(f"新 prompt: {len(new_recs)} 条")
    print(f"旧 prompt: {len(old_recs)} 条")
    print()

    def stats(recs, label):
        if not recs:
            print(f"=== {label} === (无数据)")
            return
        recs_end = [r for r in recs if r["stop"] == "end_turn"]
        print(f"=== {label} (end_turn only,排除 tool_use 中间步骤) ===")
        print(f"样本数: {len(recs_end)}")
        if not recs_end:
            return

        # 按 ctx_len 分桶
        recs_end.sort(key=lambda x: x["ctx_len"])
        n = len(recs_end)
        buckets = [
            ("Q1(最短)", recs_end[: n // 4 or 1]),
            ("Q2", recs_end[n // 4: n // 2 or 1]),
            ("Q3", recs_end[n // 2: 3 * n // 4 or 1]),
            ("Q4(最长)", recs_end[3 * n // 4:]),
        ]
        print(f"{'桶':<10} {'样本':<6} {'ctx均':<8} {'resp均':<8} {'resp中位':<10} {'resp最大':<8}")
        for name, b in buckets:
            if not b:
                continue
            avg_ctx = sum(r["ctx_len"] for r in b) / len(b)
            resps = sorted(r["resp_len"] for r in b)
            avg_resp = sum(resps) / len(resps)
            med_resp = resps[len(resps) // 2]
            max_resp = resps[-1]
            print(f"{name:<10} {len(b):<6} {avg_ctx:<8.0f} {avg_resp:<8.0f} {med_resp:<10} {max_resp:<8}")
        print()

        # 整体过 300 字的比例
        over_300 = [r for r in recs_end if r["resp_len"] > 300]
        over_500 = [r for r in recs_end if r["resp_len"] > 500]
        print(f"超 300 字: {len(over_300)}/{len(recs_end)} ({100*len(over_300)/len(recs_end):.1f}%)")
        print(f"超 500 字: {len(over_500)}/{len(recs_end)} ({100*len(over_500)/len(recs_end):.1f}%)")
        print()

        # 长上下文(Q4)的具体例子
        if buckets[3][1]:
            print(f"--- Q4 最长上下文样本 (前 5) ---")
            for r in buckets[3][1][:5]:
                print(f"  ctx={r['ctx_len']:>6} resp={r['resp_len']:>4}")
        print()

    stats(old_recs, "旧 prompt")
    stats(new_recs, "新 prompt")


if __name__ == "__main__":
    main()
