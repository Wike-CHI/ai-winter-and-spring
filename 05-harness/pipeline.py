"""
AI之书 Harness —— 写作流水线固化
=================================
把多智能体写作流水线固化为可复用的状态追踪框架。

不替代人工 LLM 编排——记录状态、检查闸门、生成检查清单。
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from data_layer import load_all, BookData


# ===========================================================================
# 流水线阶段
# ===========================================================================

class PipelineStage(Enum):
    """写作流水线的六个阶段"""
    RESEARCH = ("research", "史料核证", "Researcher 并行核证史料")
    DRAFT = ("draft", "起草", "Writer 基于已核证史料起草正文")
    FACT_CHECK = ("fact_check", "逐句核证", "Fact-Checker 逐句复核，产出核证附录")
    CONTINUITY = ("continuity", "连贯性审查", "Continuity Editor 查对位伏笔")
    STYLE = ("style", "文风审查", "Style Editor 查 AI 腔")
    FINALIZE = ("finalize", "定稿", "入库并更新台账")

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @property
    def desc(self) -> str:
        return self.value[2]


# 阶段顺序（闸门规则：必须按此顺序推进）
STAGE_ORDER = [
    PipelineStage.RESEARCH,
    PipelineStage.DRAFT,
    PipelineStage.FACT_CHECK,
    PipelineStage.CONTINUITY,
    PipelineStage.STYLE,
    PipelineStage.FINALIZE,
]


class ChapterStatus(Enum):
    """章节在流水线中的状态"""
    NOT_STARTED = "未启动"
    RESEARCHING = "史料核证中"
    DRAFTING = "起草中"
    IN_REVIEW = "质检中"
    FINALIZED = "已定稿"


# ===========================================================================
# 章节流水线记录
# ===========================================================================

@dataclass
class ChapterPipeline:
    """单章的流水线状态"""
    chapter_num: int
    chapter_title: str
    current_stage: PipelineStage
    stages_passed: list[PipelineStage]
    gates: dict[PipelineStage, bool]  # 每阶段闸门是否通过
    notes: dict[str, str]  # 阶段备注

    @property
    def status(self) -> ChapterStatus:
        if self.current_stage == PipelineStage.RESEARCH:
            return ChapterStatus.RESEARCHING
        elif self.current_stage == PipelineStage.DRAFT:
            return ChapterStatus.DRAFTING
        elif self.current_stage in (PipelineStage.FACT_CHECK,
                                     PipelineStage.CONTINUITY,
                                     PipelineStage.STYLE):
            return ChapterStatus.IN_REVIEW
        elif self.current_stage == PipelineStage.FINALIZE:
            return ChapterStatus.FINALIZED
        return ChapterStatus.NOT_STARTED

    @property
    def is_finalized(self) -> bool:
        return PipelineStage.FINALIZE in self.stages_passed

    def gate_check(self) -> dict[str, bool]:
        """检查当前阶段闸门是否通过"""
        results = {}
        if self.current_stage == PipelineStage.FACT_CHECK:
            # 闸门：无 ❌ 错误项
            results["无硬伤"] = self.gates.get(PipelineStage.FACT_CHECK, False)
        elif self.current_stage == PipelineStage.CONTINUITY:
            # 闸门：对位项全部已埋/已呼应
            results["对位一致"] = self.gates.get(PipelineStage.CONTINUITY, False)
        elif self.current_stage == PipelineStage.STYLE:
            # 闸门：无 AI 腔黑名单词
            results["无AI腔"] = self.gates.get(PipelineStage.STYLE, False)
        return results


# ===========================================================================
# 流水线管理器
# ===========================================================================

class PipelineManager:
    """全书流水线状态管理"""

    def __init__(self, data: Optional[BookData] = None):
        self.data = data or load_all()
        self.chapters: dict[int, ChapterPipeline] = {}
        self._init_from_existing()

    def _init_from_existing(self):
        """从已有文件推断各章状态"""
        from data_layer import DIR_TEXT, DIR_FACTCHECK

        for num in range(1, 11):
            title = ""
            if num in self.data.chapters:
                title = self.data.chapters[num].title

            # 推断状态：有正文 → 至少到 DRAFT；有核证附录 → 到 FACT_CHECK
            has_text = (DIR_TEXT / f"第{self._cn_num(num)}章").exists() or any(
                f.name.startswith(f"第{self._cn_num(num)}章") for f in DIR_TEXT.glob("*.md")
            ) if DIR_TEXT.exists() else False

            has_appendix = any(
                f.name.startswith(f"第{self._cn_num(num)}章") for f in DIR_FACTCHECK.glob("*.md")
            ) if DIR_FACTCHECK.exists() else False

            if has_appendix:
                stage = PipelineStage.FINALIZE
                passed = STAGE_ORDER[:]  # 全部通过
            elif has_text:
                stage = PipelineStage.FACT_CHECK
                passed = STAGE_ORDER[:2]  # RESEARCH + DRAFT
            else:
                stage = PipelineStage.RESEARCH
                passed = []

            gates = {s: (s in passed) for s in STAGE_ORDER}

            self.chapters[num] = ChapterPipeline(
                chapter_num=num,
                chapter_title=title,
                current_stage=stage,
                stages_passed=passed,
                gates=gates,
                notes={},
            )

    def _cn_num(self, num: int) -> str:
        cn = {1:"一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"七",8:"八",9:"九",10:"十"}
        return cn.get(num, str(num))

    def get_status(self, chapter_num: int) -> ChapterPipeline:
        return self.chapters.get(chapter_num)

    def all_finalized(self) -> bool:
        return all(c.is_finalized for c in self.chapters.values())

    def progress_report(self) -> str:
        """生成进度报告"""
        lines = ["流水线进度报告", "=" * 50]
        for num in sorted(self.chapters.keys()):
            cp = self.chapters[num]
            status_icon = "✅" if cp.is_finalized else "🔄"
            lines.append(
                f"  {status_icon} 第{self._cn_num(num)}章 "
                f"[{cp.status.value}] 当前阶段: {cp.current_stage.label}"
            )
        finalized = sum(1 for c in self.chapters.values() if c.is_finalized)
        lines.append(f"\n  总进度: {finalized}/{len(self.chapters)} 章定稿")
        return "\n".join(lines)

    def checklist(self, chapter_num: int) -> list[dict]:
        """返回该章的流水线检查清单"""
        cp = self.chapters.get(chapter_num)
        if not cp:
            return []
        checklist = []
        for stage in STAGE_ORDER:
            passed = stage in cp.stages_passed
            checklist.append({
                "stage": stage.code,
                "label": stage.label,
                "desc": stage.desc,
                "passed": passed,
                "is_current": stage == cp.current_stage and not passed,
            })
        return checklist


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    pm = PipelineManager()
    print(pm.progress_report())
    print()
    print("第八章检查清单:")
    for item in pm.checklist(8):
        icon = "✅" if item["passed"] else ("👉" if item["is_current"] else "⬜")
        print(f"  {icon} [{item['stage']}] {item['label']}: {item['desc']}")
