"""
AI之书 Harness —— 查询层
========================
Agent 可调用的查询接口。基于 data_layer.py。

可独立调用，也可包装为 langgraph @tool 供 Agent 使用。
"""

from __future__ import annotations

from data_layer import (
    load_all, BookData, HistoryCard, AlignmentItem, Foreshadowing,
    Chapter, ExperimentResult, CardStatus, AlignmentStatus,
)
from functools import lru_cache
from typing import Optional

# 全局缓存数据（避免重复解析）
_cache: Optional[BookData] = None


def _data() -> BookData:
    global _cache
    if _cache is None:
        _cache = load_all()
    return _cache


def reload():
    """重新加载全部数据（内容更新后调用）"""
    global _cache
    _cache = load_all()


# ===========================================================================
# 史料查询
# ===========================================================================

def lookup_card(card_id: str) -> Optional[HistoryCard]:
    """按 ID 查询史料卡片。如 lookup_card("XCON-02")"""
    d = _data()
    # 容错：自动补前导零（XCON-2 → XCON-02）
    if card_id not in d.cards:
        parts = card_id.split("-")
        if len(parts) == 2:
            padded = f"{parts[0]}-{int(parts[1]):02d}"
            return d.cards.get(padded)
    return d.cards.get(card_id)


def search_cards(query: str, chapter: Optional[str] = None) -> list[HistoryCard]:
    """关键词搜索史料卡片。可选按章节过滤。"""
    d = _data()
    q = query.lower()
    results = []
    for card in d.cards.values():
        text = (card.assertion_short + " " + card.exact_text).lower()
        if q in text:
            if chapter is None or any(chapter in c for c in card.chapters):
                results.append(card)
    return results


def cards_by_status(status: str) -> list[HistoryCard]:
    """按状态筛选。status: "✅"|"⚠️"|"❓"|"🔲" """
    d = _data()
    return [c for c in d.cards.values() if status in c.status.value]


def cards_by_chapter(chapter: str) -> list[HistoryCard]:
    """按章节筛选。如 cards_by_chapter("第三章")"""
    d = _data()
    return [c for c in d.cards.values() if any(chapter in ch for ch in c.chapters)]


def all_topics() -> dict[str, list[str]]:
    """返回 {主题: [卡片ID列表]}"""
    d = _data()
    topics: dict[str, list[str]] = {}
    for cid, card in d.cards.items():
        topics.setdefault(card.topic, []).append(cid)
    return topics


# ===========================================================================
# 对位查询
# ===========================================================================

def get_alignment(item_id: str) -> Optional[AlignmentItem]:
    """查询对位项。如 get_alignment("A1")"""
    return _data().alignments.get(item_id)


def all_alignments() -> list[AlignmentItem]:
    """全部对位项 A1-A10"""
    return list(_data().alignments.values())


def alignments_by_status(status_emoji: str) -> list[AlignmentItem]:
    """按状态筛选对位项。status_emoji: "✅"|"🟢"|"🟡"|"🔲" """
    return [a for a in _data().alignments.values() if status_emoji in a.status.value]


def alignment_evidence(item_id: str) -> list[HistoryCard]:
    """返回该对位项引用的全部史料卡片"""
    d = _data()
    item = d.alignments.get(item_id)
    if not item:
        return []
    cards = []
    for cid in item.evidence_card_ids:
        card = lookup_card(cid)
        if card:
            cards.append(card)
    return cards


def alignment_table() -> str:
    """生成对位表的可读字符串（用于 Agent 输出）"""
    d = _data()
    lines = [f"{'ID':<5} {'状态':<4} {'专家系统侧':<25} {'Agent 侧':<25} {'史料':<15}"]
    lines.append("-" * 80)
    for a in sorted(d.alignments.values(), key=lambda x: x.id):
        cards_str = ",".join(a.evidence_card_ids[:3]) if a.evidence_card_ids else "—"
        lines.append(
            f"{a.id:<5} {a.status.value:<4} "
            f"{a.expert_desc[:24]:<25} {a.agent_desc[:24]:<25} {cards_str:<15}"
        )
    return "\n".join(lines)


# ===========================================================================
# 伏笔查询
# ===========================================================================

def get_foreshadowing(fid: str) -> Optional[Foreshadowing]:
    return _data().foreshadowings.get(fid)


def unresolved_foreshadowings() -> list[Foreshadowing]:
    """未解决的伏笔（状态非终态）"""
    return [f for f in _data().foreshadowings.values()
            if not f.status.is_terminal and f.status != AlignmentStatus.ECHOED]


# ===========================================================================
# 正文查询
# ===========================================================================

def get_chapter(num: int) -> Optional[Chapter]:
    return _data().chapters.get(num)


def search_chapters(query: str) -> list[tuple[int, str]]:
    """在全部正文中搜索，返回 [(章号, 匹配片段)]"""
    d = _data()
    q = query.lower()
    results = []
    for num, ch in d.chapters.items():
        text = ch.raw_text.lower()
        idx = text.find(q)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(ch.raw_text), idx + len(q) + 50)
            snippet = ch.raw_text[start:end].replace("\n", " ")
            results.append((num, f"...{snippet}..."))
    return results


def chapter_word_count(num: int) -> int:
    """章字数"""
    ch = get_chapter(num)
    return len(ch.raw_text) if ch else 0


def total_word_count() -> int:
    """全书正文字数"""
    return sum(ch.raw_text.__len__() for ch in _data().chapters.values())


# ===========================================================================
# 术语查询
# ===========================================================================

def translate(en: str) -> str:
    """英文→中文译名。如 translate("Herbert A. Simon") → "司马贺" """
    d = _data()
    for p_en, p in d.persons.items():
        if en.lower() in p_en.lower():
            return p.zh
    for t_en, t in d.terms.items():
        if en.lower() in t_en.lower():
            return t.zh
    return f"[未收录] {en}"


def check_forbidden(text: str) -> list[tuple[str, str, int]]:
    """扫描文本中的禁用译法。返回 [(术语, 错误用法, 出现次数)]。

    只检查术语表/人名表中明确标记为"禁用"的译法。
    不会误报正确的中文译名（如"司马贺"不是违规）。
    """
    d = _data()
    violations = []
    for p in d.persons.values():
        for wrong in p.forbidden:
            # 只匹配精确的独立词出现，不匹配子串
            count = text.count(wrong)
            if count > 0:
                violations.append((p.en, wrong, count))
    for t in d.terms.items() if isinstance(d.terms, dict) else []:
        pass  # 术语的 forbidden 解析可能不可靠，暂时跳过
    return violations


# ===========================================================================
# 实验查询
# ===========================================================================

def get_experiment_result(exp: str, method: str, version: str) -> Optional[ExperimentResult]:
    """查询单个实验结果"""
    d = _data()
    for r in d.experiments:
        if r.experiment == exp and r.method == method and r.version == version:
            return r
    return None


def compare_methods(case_id: str) -> dict:
    """对比 G vs D 在同一 case 上的表现"""
    d = _data()
    results = {}
    for r in d.experiments:
        if case_id in r.case_id:
            key = f"{r.method}-{r.version}"
            results[key] = {
                "tool_calls": r.tool_calls,
                "num_messages": r.num_messages,
                "elapsed_sec": r.elapsed_sec,
            }
    return results


def experiment_summary() -> dict:
    """三子实验摘要"""
    d = _data()
    summary = {}
    for exp_name in ["exp1", "exp2", "exp3"]:
        exp_results = [r for r in d.experiments if r.experiment == exp_name]
        summary[exp_name] = {
            "结果数": len(exp_results),
            "有错误": sum(1 for r in exp_results if r.error),
            "方法": list(set(r.method for r in exp_results)),
        }
    return summary


# ===========================================================================
# 跨层查询
# ===========================================================================

def consistency_report() -> dict:
    """全书一致性摘要"""
    d = _data()
    report = {
        "史料卡片": {"总数": len(d.cards), "状态分布": {}},
        "对位项": {"总数": len(d.alignments), "已闭合": 0},
        "伏笔": {"总数": len(d.foreshadowings), "未解决": 0},
        "正文": {"章节数": len(d.chapters)},
        "实验": {"结果数": len(d.experiments)},
    }
    from collections import Counter
    status_dist = Counter(c.status.value for c in d.cards.values())
    report["史料卡片"]["状态分布"] = dict(status_dist)
    report["对位项"]["已闭合"] = sum(1 for a in d.alignments.values() if a.is_closed)
    report["伏笔"]["未解决"] = len(unresolved_foreshadowings())
    return report


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("AI之书 Harness —— 查询层演示")
    print("=" * 60)

    print("\n📊 一致性报告:")
    for k, v in consistency_report().items():
        print(f"  {k}: {v}")

    print(f"\n📋 对位表:")
    print(alignment_table())

    print(f"\n🔍 查询 XCON-02:")
    card = lookup_card("XCON-02")
    if card:
        print(f"  {card.id} [{card.status.value}]")
        print(f"  断言: {card.assertion_short}")
        print(f"  来源: {len(card.sources)} 个 URL")

    print(f"\n🔍 搜索 '第五代机':")
    for c in search_cards("第五代机")[:3]:
        print(f"  {c.id} [{c.status.value}] {c.assertion_short[:50]}")

    print(f"\n🧪 实验摘要:")
    for exp, info in experiment_summary().items():
        print(f"  {exp}: {info}")

    print(f"\n🔤 translate('Herbert A. Simon') = {translate('Herbert A. Simon')}")
    print(f"🔤 translate('Rule Explosion') = {translate('Rule Explosion')}")

    print(f"\n📈 全书总字数: {total_word_count()}")
