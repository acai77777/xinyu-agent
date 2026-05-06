"""分析评测失败原因"""
import json
from collections import Counter, defaultdict

with open(r"H:\AI\心理学agent\server\evaluation\results\results_google_gemini-3.1-flash-lite-preview_20260314_110258.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 按模块统计失败原因
module_failures = defaultdict(list)

for pr in data["pipeline"]:
    for mr in pr["modules"]:
        if not mr["passed"]:
            module_failures[mr["module"]].append({
                "case_id": pr["case_id"],
                "details": mr["details"],
                "expected": mr["expected"],
                "actual": mr["actual"],
            })

for module, failures in module_failures.items():
    print(f"\n{'='*60}")
    print(f"  {module} 失败项 ({len(failures)}个)")
    print(f"{'='*60}")
    for f in failures:
        print(f"\n  [{f['case_id']}] {f['details']}")
        if module == "emotion":
            exp_e = f["expected"].get("primary_emotion", "")
            act_e = f["actual"].get("primary_emotion", "")
            exp_v = f["expected"].get("valence", "")
            act_v = f["actual"].get("valence", "")
            exp_i = f["expected"].get("intensity_range", [])
            act_i = f["actual"].get("intensity", "")
            print(f"    期望: {exp_e}({exp_i}) {exp_v}")
            print(f"    实际: {act_e}({act_i}) {act_v}")
            sec = f["actual"].get("secondary_emotions", [])
            if sec:
                print(f"    次要情绪: {sec}")
        elif module == "crisis":
            print(f"    期望: level={f['expected'].get('level')}, keywords={f['expected'].get('should_match_keywords')}")
            print(f"    实际: level={f['actual'].get('level')}, keywords={f['actual'].get('matched_keywords')}, semantic={f['actual'].get('semantic_confirmed')}")
        elif module == "strategy":
            print(f"    期望: approach={f['expected'].get('primary_approach')}, techniques={f['expected'].get('should_include_techniques')}")
            print(f"    实际: approach={f['actual'].get('primary_approach')}, techniques={f['actual'].get('recommended_techniques')}")
        elif module == "distortion":
            print(f"    期望: detect={f['expected'].get('should_detect')}, types={f['expected'].get('types')}")
            act_types = f["actual"].get("types", [])
            print(f"    实际: detect={f['actual'].get('detected')}, types={act_types}")

# 策略独立评测
print(f"\n{'='*60}")
print(f"  strategy_standalone 失败项")
print(f"{'='*60}")
for sr in data.get("strategy_standalone", []):
    if not sr["passed"]:
        print(f"\n  [{sr['case_id']}] {sr['details']}")
        print(f"    期望: {sr['expected']}")
        print(f"    实际: {sr['actual']}")

# 对话评测摘要
print(f"\n{'='*60}")
print(f"  对话评测摘要")
print(f"{'='*60}")
for cr in data.get("conversation", []):
    scores = cr["scores"]
    avg = sum(scores.values()) / len(scores) if scores else 0
    print(f"\n  [{cr['case_id']}] {cr['scenario']} ({cr['turn_count']}轮) 平均={avg:.1f}")
    for dim, score in scores.items():
        print(f"    {dim}: {score}/5")
    if cr.get("red_flags_found"):
        print(f"    RED FLAGS: {cr['red_flags_found']}")
    if cr.get("improvement_suggestions"):
        print(f"    改进建议: {cr['improvement_suggestions'][:2]}")
