"""
书籍导入脚本——将心理学书籍按章节分块存入 ChromaDB
支持三本书：
  1. 《真实的幸福》— 纯文本TXT
  2. 《积极心理学》— OCR提取后的TXT
  3. 《认知行为疗法入门》— OCR提取后的TXT（按小节分块）
"""
import os
import re
import uuid
from pathlib import Path

import chromadb

from config import settings

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# 每个 chunk 的最大字符数（约 500-800 字为宜，保持语义完整）
MAX_CHUNK_SIZE = 800
OVERLAP_SIZE = 100  # 相邻 chunk 重叠字符数


def _get_chroma_client():
    """复用 memory/semantic.py 的连接模式"""
    chromadb_host = os.getenv("CHROMADB_HOST")
    if chromadb_host:
        return chromadb.HttpClient(
            host=chromadb_host,
            port=int(os.getenv("CHROMADB_PORT", "8001")),
        )
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def _get_collection():
    """获取或创建 book_knowledge collection"""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="book_knowledge",
        metadata={"hnsw:space": "cosine"},
    )


def _split_text_to_chunks(text: str, max_size: int = MAX_CHUNK_SIZE,
                          overlap: int = OVERLAP_SIZE) -> list[str]:
    """
    按段落边界将文本分成 chunks。
    优先在段落（空行）处分割；段落过长则在句号处分割。
    """
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= max_size:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            # 段落本身太长，按句号切分
            if len(para) > max_size:
                sentences = re.split(r'(?<=[。！？])', para)
                current = ""
                for sent in sentences:
                    if not sent.strip():
                        continue
                    if len(current) + len(sent) <= max_size:
                        current += sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current:
        chunks.append(current)

    # 添加重叠
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(prev_tail + "\n" + chunks[i])
        chunks = overlapped

    return chunks


# ============================================================
# 《真实的幸福》TXT 解析
# ============================================================

# 章节结构：(章节标记, 部分名, 章名, 第一个子标题)
_AUTHENTIC_HAPPINESS_CHAPTERS = [
    ("引言", None, "引言　积极心理学：增加幸福，而不是减少痛苦", "引言"),
    ("第1章", "第一部分　什么是幸福", "第1章　为什么要幸福", "有幸福感的人更长寿吗"),
    ("第2章", "第一部分　什么是幸福", "第2章　幸福的心理学", "我的幸福之路"),
    ("第3章", "第一部分　什么是幸福", "第3章　幸福的误区", "进化排斥积极情绪吗"),
    ("第4章", "第一部分　什么是幸福", "第4章　怎样才能永远幸福", "H：幸福的持久度"),
    ("第5章", "第一部分　什么是幸福", "第5章　塞式幸福法则1：过去的就让它过去", "测一测你的生活满意度"),
    ("第6章", "第一部分　什么是幸福", "第6章　塞式幸福法则2：未来不全如你想象", "测一测自己的乐观程度"),
    ("第7章", "第一部分　什么是幸福", "第7章　塞式幸福法则3：抓住现在的幸福", "愉悦"),
    ("第8章", "第二部分　幸福在哪里", "第8章　拉近幸福的六种美德", "天生坏，还是环境坏"),
    ("第9章", "第二部分　幸福在哪里", "第9章　获得幸福的24个优势", "天赋与优势"),
    ("第10章", "第三部分　用幸福斟满人生", "第10章　在职场中寻找幸福", "工作的三个阶梯"),
    ("第11章", "第三部分　用幸福斟满人生", "第11章　结了婚的人最幸福", "爱与被爱的能力"),
    ("第12章", "第三部分　用幸福斟满人生", "第12章　别让孩子输在幸福感上", "孩子的幸福感"),
]


def _find_chapter_boundaries(lines: list[str]) -> list[tuple[int, str, str, str]]:
    """
    在正文中定位各章起始行号。
    返回 [(start_line, chapter_id, part_name, chapter_name), ...]
    """
    boundaries = []
    for ch_id, part, ch_name, first_heading in _AUTHENTIC_HAPPINESS_CHAPTERS:
        for i, line in enumerate(lines):
            if i < 500:  # 跳过目录区
                continue
            if line.strip() == first_heading or (
                ch_id == "引言" and line.strip() == "引言"
                and i > 500  # 正文区的引言
            ):
                boundaries.append((i, ch_id, part or "", ch_name))
                break
    return boundaries


def ingest_authentic_happiness():
    """导入《真实的幸福》到 ChromaDB"""
    txt_path = _PROJECT_ROOT / "真实的幸福.txt"
    if not txt_path.exists():
        print(f"文件不存在: {txt_path}")
        return

    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    boundaries = _find_chapter_boundaries(lines)
    if not boundaries:
        print("未找到章节边界！")
        return

    print(f"找到 {len(boundaries)} 个章节")

    collection = _get_collection()
    total_chunks = 0

    for idx, (start, ch_id, part, ch_name) in enumerate(boundaries):
        # 确定章节结束位置
        if idx + 1 < len(boundaries):
            end = boundaries[idx + 1][0]
        else:
            end = len(lines)

        chapter_text = "".join(lines[start:end]).strip()
        chunks = _split_text_to_chunks(chapter_text)

        for ci, chunk in enumerate(chunks):
            doc_id = f"ah_{ch_id}_{ci}"
            collection.upsert(
                ids=[doc_id],
                documents=[chunk],
                metadatas=[{
                    "book": "真实的幸福",
                    "author": "Martin Seligman",
                    "part": part,
                    "chapter": ch_name,
                    "chapter_id": ch_id,
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                }],
            )

        total_chunks += len(chunks)
        print(f"  {ch_name}: {len(chunks)} chunks")

    print(f"\n《真实的幸福》导入完成: {total_chunks} chunks")
    return total_chunks


# ============================================================
# 《积极心理学》OCR文本解析
# ============================================================

def _parse_positive_psychology_chapters(text: str) -> list[tuple[str, str, str]]:
    """
    从OCR文本中解析章节结构。
    OCR文本以 '=== 第 N 页 ===' 分页。
    返回 [(chapter_id, chapter_name, chapter_text), ...]
    """
    lines = text.split("\n")

    # 中文数字映射
    cn_nums = {
        "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
        "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
        "十一": "11", "十二": "12",
    }

    # 章节标题（OCR后可能有噪声，取正文中出现的）
    chapter_titles = {
        "1": "积极心理学概述",
        "2": "幸福感",
        "3": "积极思维：乐观、归因与希望",
        "4": "幸福感的含义",
        "5": "认知心理学与乐观",
        "6": "性格力量与美德",
        "7": "价值观",
        "8": "兴趣、能力和成就",
        "9": "健康心理学",
        "10": "积极的社会关系",
        "11": "授权机构",
        "12": "积极心理学的未来",
    }

    # 查找正文中的章节起始（跳过目录区，大约前400行）
    chapter_pattern = re.compile(r'^第([一二三四五六七八九十]+|\d+)章')
    chapter_starts = []

    for i, line in enumerate(lines):
        if i < 400:  # 跳过前面的目录和版权页
            continue
        m = chapter_pattern.match(line.strip())
        if m:
            ch_cn = m.group(1)
            ch_num = cn_nums.get(ch_cn, ch_cn)
            # 排除参考文献/注释中重复出现的章节引用（通常很短的行）
            if i + 1 < len(lines) and len(lines[i].strip()) < 20:
                # 检查后续几行是否也是章节标题（目录区的特征）
                next_lines = [l.strip() for l in lines[i+1:i+5] if l.strip()]
                has_next_chapter = any(chapter_pattern.match(l) for l in next_lines)
                if has_next_chapter and len(next_lines) > 0:
                    continue  # 跳过目录/索引中的重复
            chapter_starts.append((i, ch_num))

    # 去重：只保留每个章节号第一次出现
    seen = set()
    unique_starts = []
    for line_no, ch_num in chapter_starts:
        if ch_num not in seen:
            seen.add(ch_num)
            unique_starts.append((line_no, ch_num))

    if not unique_starts:
        return [("全书", "积极心理学", text)]

    chapters = []
    for idx, (start, ch_num) in enumerate(unique_starts):
        ch_title = chapter_titles.get(ch_num, f"第{ch_num}章")
        ch_id = f"第{ch_num}章"
        ch_name = f"第{ch_num}章 {ch_title}"
        end = unique_starts[idx + 1][0] if idx + 1 < len(unique_starts) else len(lines)
        ch_text = "\n".join(lines[start:end])
        chapters.append((ch_id, ch_name, ch_text))

    return chapters


def ingest_positive_psychology():
    """导入《积极心理学》OCR文本到 ChromaDB"""
    ocr_path = _DATA_DIR / "积极心理学_raw.txt"
    if not ocr_path.exists():
        print(f"OCR文件不存在: {ocr_path}")
        print("请先运行 ocr_extract.py 提取PDF文字")
        return

    with open(ocr_path, "r", encoding="utf-8") as f:
        text = f.read()

    chapters = _parse_positive_psychology_chapters(text)
    if not chapters:
        print("未找到章节结构！")
        return

    print(f"找到 {len(chapters)} 个章节")

    collection = _get_collection()
    total_chunks = 0

    for ch_id, ch_name, ch_text in chapters:
        chunks = _split_text_to_chunks(ch_text)

        for ci, chunk in enumerate(chunks):
            doc_id = f"pp_{ch_id}_{ci}"
            collection.upsert(
                ids=[doc_id],
                documents=[chunk],
                metadatas=[{
                    "book": "积极心理学",
                    "author": "Christopher Peterson",
                    "part": "",
                    "chapter": ch_name,
                    "chapter_id": ch_id,
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                }],
            )

        total_chunks += len(chunks)
        print(f"  {ch_name}: {len(chunks)} chunks")

    print(f"\n《积极心理学》导入完成: {total_chunks} chunks")
    return total_chunks


# ============================================================
# 《认知行为疗法入门》OCR文本解析（按小节 X.X 分块）
# ============================================================

# 全书10章的章节标题
_CBT_CHAPTER_TITLES = {
    "1": "心理学基础",
    "2": "认知行为疗法基础",
    "3": "咨询过程",
    "4": "评估性会谈",
    "5": "自动思维",
    "6": "咨询性会谈",
    "7": "中间信念",
    "8": "核心信念",
    "9": "健康人格",
    "10": "结束会谈",
}


def _parse_cbt_sections(text: str) -> list[dict]:
    """
    按小节（X.X 级别）解析OCR文本。
    返回 [{"chapter": "第5章 自动思维",
            "section": "5.2 自动思维的基础知识",
            "text": "..."}, ...]
    """
    lines = text.split("\n")

    # 去掉页码标记
    content_lines = []
    for line in lines:
        if re.match(r'^===\s*第\s*\d+\s*页\s*===$', line.strip()):
            continue
        content_lines.append(line)

    full_text = "\n".join(content_lines)

    # 匹配小节标题：X.X 或 X.X.X 后跟中文标题
    # 例如: "5.2 自动思维的基础知识" 或 "5.2.1 自动思维的定义"
    # OCR可能在数字和点之间有空格: "5. 2" 或 "5 .2"
    section_pattern = re.compile(
        r'^(\d{1,2})\s*[.．]\s*(\d{1,2})\s*(?:[.．]\s*(\d{1,2}))?\s+'
        r'([\u4e00-\u9fff][\u4e00-\u9fff\w，、：（）""''\u00b7\u002d\u2014]+)',
        re.MULTILINE,
    )

    matches = list(section_pattern.finditer(full_text))

    if not matches:
        # 回退：整体按段落分块
        return [{"chapter": "认知行为疗法入门", "section": "全书",
                 "text": full_text}]

    sections = []
    for i, m in enumerate(matches):
        ch_num = m.group(1)
        sec_num = m.group(2)
        subsec_num = m.group(3)  # 可能为 None
        title = m.group(4).strip()

        ch_title = _CBT_CHAPTER_TITLES.get(ch_num, f"第{ch_num}章")
        chapter = f"第{ch_num}章 {ch_title}"

        if subsec_num:
            section_id = f"{ch_num}.{sec_num}.{subsec_num}"
        else:
            section_id = f"{ch_num}.{sec_num}"
        section = f"{section_id} {title}"

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        sec_text = full_text[start:end].strip()

        sections.append({
            "chapter": chapter,
            "chapter_num": ch_num,
            "section": section,
            "section_id": section_id,
            "text": sec_text,
        })

    # 去重：同一个 section_id 可能在目录区和正文区各出现一次，
    # 保留内容最长的那个（正文区的内容远长于目录条目）
    best_by_id: dict[str, dict] = {}
    for sec in sections:
        sid = sec["section_id"]
        if sid not in best_by_id or len(sec["text"]) > len(best_by_id[sid]["text"]):
            best_by_id[sid] = sec
    sections = list(best_by_id.values())

    # 过滤掉内容过短的条目（< 200字符通常是目录残留或只有标题的stub）
    sections = [s for s in sections if len(s["text"]) >= 200]

    return sections


def ingest_cbt_primer():
    """导入《认知行为疗法入门》OCR文本到 ChromaDB（按小节分块）"""
    ocr_path = _DATA_DIR / "认知行为疗法入门_raw.txt"
    if not ocr_path.exists():
        print(f"OCR文件不存在: {ocr_path}")
        print("请先运行 ocr_extract.py cbt 提取PDF文字")
        return

    with open(ocr_path, "r", encoding="utf-8") as f:
        text = f.read()

    sections = _parse_cbt_sections(text)
    if not sections:
        print("未找到小节结构！")
        return

    print(f"找到 {len(sections)} 个小节")

    collection = _get_collection()
    total_chunks = 0

    for sec in sections:
        chunks = _split_text_to_chunks(sec["text"])

        for ci, chunk in enumerate(chunks):
            doc_id = f"cbt_{sec['section_id']}_{ci}"
            collection.upsert(
                ids=[doc_id],
                documents=[chunk],
                metadatas=[{
                    "book": "认知行为疗法入门",
                    "author": "郭召良",
                    "part": "",
                    "chapter": sec["chapter"],
                    "chapter_id": f"第{sec['chapter_num']}章",
                    "section": sec["section"],
                    "section_id": sec["section_id"],
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                }],
            )

        total_chunks += len(chunks)
        print(f"  {sec['section']}: {len(chunks)} chunks")

    print(f"\n《认知行为疗法入门》导入完成: {total_chunks} chunks ({len(sections)} 小节)")
    return total_chunks


def search_test(query: str = "感恩", n_results: int = 3):
    """测试语义搜索"""
    collection = _get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )
    print(f"\n搜索 '{query}' 的结果：")
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i]
        print(f"\n--- 结果 {i+1} (距离: {dist:.4f}) ---")
        print(f"书: {meta['book']} | 章: {meta['chapter']}")
        print(f"内容: {doc[:200]}...")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python book_ingestion.py authentic   # 导入《真实的幸福》")
        print("  python book_ingestion.py positive    # 导入《积极心理学》")
        print("  python book_ingestion.py cbt         # 导入《认知行为疗法入门》")
        print("  python book_ingestion.py all         # 导入全部")
        print("  python book_ingestion.py search 感恩 # 测试搜索")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd in ("authentic", "all"):
        ingest_authentic_happiness()
    if cmd in ("positive", "all"):
        ingest_positive_psychology()
    if cmd in ("cbt", "all"):
        ingest_cbt_primer()
    if cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "感恩"
        search_test(query)
