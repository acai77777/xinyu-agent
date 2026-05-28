"""
下载 PsyDial 和 CPsyCoun 数据集并抽样
PsyDial: HuggingFace datasets API
CPsyCoun: GitHub raw files

抽样策略：
- PsyDial: 抽 20 条长对话（平均 37.8 轮）
- CPsyCoun: 抽 30 条（覆盖不同主题）
"""
import json
import os
import random
import sys
import re
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path(__file__).parent / "data"
PSYDIAL_DIR = DATA_DIR / "psydial"
CPSYCOUN_DIR = DATA_DIR / "cpsycoun"


# ═══════════════════════════════════════════════════
# PsyDial — 从 HuggingFace datasets API 下载
# ═══════════════════════════════════════════════════

PSYDIAL_HF_URLS = [
    "https://hf-mirror.com/datasets/qiuhuachuan/PsyDial-D4/resolve/main/PsyDial-D4.json",
    "https://huggingface.co/datasets/qiuhuachuan/PsyDial-D4/resolve/main/PsyDial-D4.json",
]


def download_psydial(sample_size: int = 20):
    """下载 PsyDial-D4 并抽样"""
    PSYDIAL_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = PSYDIAL_DIR / "_raw_psydial_d4.json"

    if cache_path.exists():
        print(f"[PsyDial] 使用缓存: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print(f"[PsyDial] 从 HuggingFace 下载 PsyDial-D4...")
        # 先尝试 datasets API（parquet rows）
        data = _download_psydial_hf_api()
        if not data:
            # 降级：尝试直接下载 JSON
            data = _download_psydial_direct()
        if not data:
            print("[PsyDial] 下载失败，跳过")
            return
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[PsyDial] 已缓存原始数据: {len(data)} 条对话")

    # 抽样：按长度分层，覆盖短/中/长对话
    random.seed(42)
    short = [d for d in data if len(d.get("messages", [])) <= 40]
    medium = [d for d in data if 40 < len(d.get("messages", [])) <= 80]
    long_ = [d for d in data if len(d.get("messages", [])) > 80]

    sampled = []
    sampled.extend(random.sample(short, min(5, len(short))))
    sampled.extend(random.sample(medium, min(10, len(medium))))
    sampled.extend(random.sample(long_, min(5, len(long_))))

    # 标准化格式
    standardized = []
    for i, item in enumerate(sampled):
        dialogue = _standardize_psydial(item, i)
        if dialogue:
            standardized.append(dialogue)

    output_path = PSYDIAL_DIR / "sampled.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standardized, f, ensure_ascii=False, indent=2)
    print(f"[PsyDial] 抽样完成: {len(standardized)} 条 → {output_path}")


def _download_psydial_hf_api() -> list | None:
    """通过 HuggingFace datasets API 下载"""
    # 尝试 rows API（分页获取前 200 条）
    url = "https://datasets-server.huggingface.co/rows?dataset=qiuhuachuan/PsyDial-D4&config=default&split=train&offset=0&length=100"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            rows = result.get("rows", [])
            if rows:
                return [row.get("row", row) for row in rows]
    except Exception as e:
        print(f"[PsyDial] HF API 失败: {e}")
    return None


def _download_psydial_direct() -> list | None:
    """直接下载 JSON 文件（优先镜像，降级官方）"""
    for url in PSYDIAL_HF_URLS:
        try:
            print(f"[PsyDial] 尝试: {url[:60]}...")
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[PsyDial] 失败: {e}")
    return None


def _standardize_psydial(item: dict, idx: int) -> dict | None:
    """将 PsyDial 数据标准化为统一格式"""
    # PsyDial-D4 格式: {"messages": [{"role": "system/user/assistant", "content": "..."}]}
    raw_msgs = item.get("messages", item.get("dialogue", item.get("conversations", [])))
    if not raw_msgs:
        for key in item:
            if isinstance(item[key], list) and len(item[key]) > 0:
                first = item[key][0]
                if isinstance(first, dict) and ("role" in first or "content" in first):
                    raw_msgs = item[key]
                    break

    if not raw_msgs:
        return None

    messages = []
    for turn in raw_msgs:
        role = turn.get("role", "")
        content = turn.get("content", turn.get("text", ""))
        if not content or role == "system":
            continue
        # 统一角色名
        if role in ("user", "client", "来访者", "患者"):
            messages.append({"role": "client", "content": content})
        elif role in ("assistant", "counselor", "咨询师", "心理咨询师"):
            messages.append({"role": "counselor", "content": content})

    if len(messages) < 4:
        return None

    return {
        "id": f"psydial_{idx:03d}",
        "source": "PsyDial-D4",
        "turn_count": len(messages),
        "messages": messages,
    }


# ═══════════════════════════════════════════════════
# CPsyCoun — 从 GitHub raw 文件下载
# ═══════════════════════════════════════════════════

CPSYCOUN_RAW_BASE = "https://raw.githubusercontent.com/CAS-SIAT-XinHai/CPsyCoun/main/CPsyCounD/Data"


def download_cpsycoun(sample_size: int = 30):
    """下载 CPsyCoun 文本文件并抽样"""
    CPSYCOUN_DIR.mkdir(parents=True, exist_ok=True)

    # 随机抽样 case ID（总共约 1900 个）
    random.seed(42)
    total_cases = 1898
    sampled_ids = sorted(random.sample(range(total_cases), min(sample_size, total_cases)))

    standardized = []
    for case_id in sampled_ids:
        url = f"{CPSYCOUN_RAW_BASE}/case_{case_id}.txt"
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as resp:
                raw_bytes = resp.read()
                text = raw_bytes.decode("utf-8")

            dialogue = _parse_cpsycoun_text(text)
            if dialogue and len(dialogue) >= 4:
                standardized.append({
                    "id": f"cpsycoun_{case_id:04d}",
                    "source": "CPsyCounD",
                    "source_file": f"case_{case_id}.txt",
                    "turn_count": len(dialogue),
                    "messages": dialogue,
                })
                print(f"  [CPsyCoun] case_{case_id}: {len(dialogue)} 轮")
        except Exception as e:
            print(f"  [CPsyCoun] case_{case_id} 下载失败: {e}")

    output_path = CPSYCOUN_DIR / "sampled.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standardized, f, ensure_ascii=False, indent=2)
    print(f"[CPsyCoun] 抽样完成: {len(standardized)} 条 → {output_path}")


def _parse_cpsycoun_text(text: str) -> list[dict]:
    """
    解析 CPsyCoun 文本格式：
    来访者：...
    心理咨询师：...
    """
    messages = []
    # 按角色前缀分割
    pattern = r'(来访者|心理咨询师)：(.*?)(?=(?:来访者|心理咨询师)：|\Z)'
    matches = re.findall(pattern, text.strip(), re.DOTALL)

    for role_cn, content in matches:
        content = content.strip()
        if not content:
            continue
        role = "client" if role_cn == "来访者" else "counselor"
        messages.append({"role": role, "content": content})

    return messages


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def main():
    print("=" * 50)
    print("  心理学Agent评测 — 数据集下载")
    print("=" * 50)

    print("\n[1/2] 下载 PsyDial...")
    download_psydial(sample_size=20)

    print("\n[2/2] 下载 CPsyCoun...")
    download_cpsycoun(sample_size=30)

    # 清理临时文件
    test_file = DATA_DIR / "case_0_test.txt"
    if test_file.exists():
        test_file.unlink()

    print("\n" + "=" * 50)
    print("  下载完成！")
    print("=" * 50)

    # 显示统计
    for name, d in [("PsyDial", PSYDIAL_DIR), ("CPsyCoun", CPSYCOUN_DIR)]:
        sampled = d / "sampled.json"
        if sampled.exists():
            with open(sampled, "r", encoding="utf-8") as f:
                data = json.load(f)
            turns = [item["turn_count"] for item in data]
            print(f"  {name}: {len(data)} 条对话, "
                  f"平均 {sum(turns)/len(turns):.1f} 轮/对话, "
                  f"范围 [{min(turns)}-{max(turns)}]")


if __name__ == "__main__":
    main()
