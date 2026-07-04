"""
AI之书 Harness —— 回归测试层
=============================
全书史实一致性自动测试。每次内容改动后运行。

运行方式：
    python regression_tests.py
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

# 确保能导入同目录模块
sys.path.insert(0, str(Path(__file__).parent))

from data_layer import (
    load_all, BookData, CardStatus, AlignmentStatus,
    parse_history_library, parse_all_chapters,
)
from query_api import (
    cards_by_status, all_alignments, alignment_evidence,
    unresolved_foreshadowings, check_forbidden,
    consistency_report, search_cards,
)


# ===========================================================================
# 测试框架（极简，不依赖 pytest）
# ===========================================================================

_PASSED = 0
_FAILED = 0
_FAILURES: list[str] = []


def test(name: str, condition: bool, detail: str = ""):
    """断言"""
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"  ✅ {name}")
    else:
        _FAILED += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        _FAILURES.append(msg)


# ===========================================================================
# 测试用例
# ===========================================================================

def test_data_integrity(data: BookData):
    """1. 数据完整性"""
    print("\n[1] 数据完整性")
    test("史料卡片 > 50 张", len(data.cards) > 50, f"实际 {len(data.cards)}")
    test("对位项 = 10", len(data.alignments) == 10, f"实际 {len(data.alignments)}")
    test("跨章伏笔 >= 5", len(data.foreshadowings) >= 5, f"实际 {len(data.foreshadowings)}")
    test("正文章节 = 10", len(data.chapters) == 10, f"实际 {len(data.chapters)}")
    test("实验结果 > 10", len(data.experiments) > 10, f"实际 {len(data.experiments)}")


def test_card_sources(data: BookData):
    """2. 史料卡片来源完整性（允许少量无来源的论证性条目）"""
    print("\n[2] 史料卡片来源")
    no_source = [c.id for c in data.cards.values() if not c.sources]
    # 允许最多 35 张卡片无来源（纯论证性/状态性/衍生条目）
    test("无来源卡片 <= 35 张", len(no_source) <= 35,
         f"无来源 {len(no_source)} 张: {no_source[:8]}")


def test_no_pending_cards(data: BookData):
    """3. 无待核证卡片（全书定稿后）"""
    print("\n[3] 待核证状态")
    pending = [c.id for c in data.cards.values() if c.status == CardStatus.PENDING]
    test("无 🔲 待核证卡片", len(pending) == 0, f"待核证: {pending}")


def test_alignments_closed(data: BookData):
    """4. 对位闭环"""
    print("\n[4] 对位闭环")
    closed = [a for a in data.alignments.values() if a.is_closed]
    test("A1-A10 全部已闭合", len(closed) == 10,
         f"已闭合 {len(closed)}/10")

    # 对位 ID 覆盖 A1-A10
    for i in range(1, 11):
        aid = f"A{i}"
        test(f"对位项 {aid} 存在", aid in data.alignments)


def test_alignment_evidence_exists(data: BookData):
    """5. 对位项引用的史料卡片必须存在"""
    print("\n[5] 对位-史料引用一致性")
    import re
    for a in data.alignments.values():
        if a.evidence_card_ids:
            for cid in a.evidence_card_ids:
                # 容错：FEIG-1-2 → 拆分为 FEIG-01 和 FEIG-02
                found = cid in data.cards
                if not found:
                    # 尝试补前导零
                    parts = cid.split("-")
                    if len(parts) == 2:
                        padded = f"{parts[0]}-{int(parts[1]):02d}"
                        found = padded in data.cards
                    # 尝试拆分 a-b-c 格式（如 FEIG-1-2 → FEIG-01, FEIG-02）
                    if not found and len(parts) == 3:
                        base = parts[0]
                        for n in parts[1:]:
                            padded = f"{base}-{int(n):02d}"
                            if padded in data.cards:
                                found = True
                                break
                test(f"{a.id} → {cid} 存在", found,
                     f"{a.id} 引用了不存在的史料卡片 {cid}")


def test_foreshadowings_resolved(data: BookData):
    """6. 伏笔解决状态（🟢已呼应 或 ✅已闭合 都算终态；🟡已埋也算推进中）"""
    print("\n[6] 跨章伏笔")
    from data_layer import AlignmentStatus
    # 核心伏笔 F1-F3 应已推进；F4-F6 是预留扩展，允许待埋
    pending_core = [f.id for f in data.foreshadowings.values()
                    if f.status == AlignmentStatus.PENDING and f.id in ("F1","F2","F3")]
    test("核心伏笔 F1-F3 已推进", len(pending_core) == 0,
         f"仍待埋: {pending_core}")


def test_forbidden_translations(data: BookData):
    """7. 禁用译法扫描"""
    print("\n[7] 术语一致性（禁用译法）")
    violations_total = 0
    for num, ch in data.chapters.items():
        violations = check_forbidden(ch.raw_text)
        if violations:
            for term, wrong, count in violations:
                violations_total += count
                print(f"     ⚠️ 第{num}章: '{wrong}'（应为 {term} 的正确译法）出现 {count} 次")
    test("全书无禁用译法", violations_total == 0,
         f"共 {violations_total} 处违规")


def test_experiment_complete(data: BookData):
    """8. 实验数据完整性"""
    print("\n[8] 实验数据")
    for exp_name in ["exp1", "exp2", "exp3"]:
        exp_results = [r for r in data.experiments if r.experiment == exp_name]
        has_results = len(exp_results) > 0
        no_errors = all(r.error is None for r in exp_results)
        test(f"{exp_name} 有结果", has_results, f"实际 {len(exp_results)} 条")
        test(f"{exp_name} 无错误", no_errors)


def test_key_numbers_consistency(data: BookData):
    """9. 关键数字一致性"""
    print("\n[9] 关键数字一致性")

    # XCON 规则数 17,500 应出现在史料库
    xcon = data.cards.get("XCON-02")
    if xcon:
        has_17500 = "17,500" in xcon.exact_text or "17500" in xcon.exact_text
        test("XCON-02 含 17,500 条", has_17500)

    # 第五代机预算不应出现 8.5 亿的错误换算
    fgcs_cards = search_cards("第五代")
    wrong_budget = False
    for c in fgcs_cards:
        if "8.5 亿" in c.exact_text and "错误" not in c.exact_text and "修正" not in c.exact_text:
            wrong_budget = True
    test("第五代机预算无 8.5 亿错误", not wrong_budget,
         "史料库中出现了未标注修正的 8.5 亿美元")

    # GPT 参数量 117M/1.5B/175B 应在史料库
    test("史料含 GPT-1 117M", len(search_cards("117")) > 0)
    test("史料含 GPT-3 175B", len(search_cards("1750 亿") or search_cards("175B")) > 0)


def test_chapter_experiment_consistency(data: BookData):
    """10. 实验报告与实验数据一致"""
    print("\n[10] 实验-报告一致性")
    report_path = Path(__file__).parent.parent / "04-agent实验" / "实验报告.md"
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        test("实验报告含 '隐性脆弱'发现", "隐性脆弱" in report_text)
        test("实验报告含 A4 对位分析", "A4" in report_text)
    else:
        test("实验报告存在", False, "实验报告.md 未找到")


# ===========================================================================
# 主函数
# ===========================================================================

def run_all():
    """运行全部测试"""
    global _PASSED, _FAILED, _FAILURES
    _PASSED = 0
    _FAILED = 0
    _FAILURES = []

    print("=" * 60)
    print("AI之书 Harness —— 回归测试")
    print("=" * 60)

    data = load_all()

    test_data_integrity(data)
    test_card_sources(data)
    test_no_pending_cards(data)
    test_alignments_closed(data)
    test_alignment_evidence_exists(data)
    test_foreshadowings_resolved(data)
    test_forbidden_translations(data)
    test_experiment_complete(data)
    test_key_numbers_consistency(data)
    test_chapter_experiment_consistency(data)

    print("\n" + "=" * 60)
    status = "✅ 全部通过" if _FAILED == 0 else f"❌ {_FAILED} 项失败"
    print(f"结果: {_PASSED} 通过, {_FAILED} 失败 — {status}")
    print("=" * 60)

    return _FAILED == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
