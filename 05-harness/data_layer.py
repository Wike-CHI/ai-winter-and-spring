"""
AI之书 Harness —— 数据层
=========================
解析全部编排资产为 Python 对象，是查询层/测试层/流水线层的基础。

零外部依赖，仅用标准库。全程 UTF-8。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Optional

# ===========================================================================
# 配置
# ===========================================================================

# 默认基准目录（可被外部覆盖）
BASE_DIR = Path(__file__).resolve().parent.parent  # D:/ai/AI之书/

DIR_OUTLINE = BASE_DIR / "00-大纲"
DIR_TEXT = BASE_DIR / "01-正文"
DIR_FACTCHECK = BASE_DIR / "02-史料核证"
DIR_ORCHESTRATION = BASE_DIR / "03-写作编排"
DIR_EXPERIMENT = BASE_DIR / "04-agent实验"

FILE_HISTORY_LIB = DIR_ORCHESTRATION / "史料库.md"
FILE_ALIGNMENT = DIR_ORCHESTRATION / "对位台账.md"
FILE_GLOSSARY = DIR_ORCHESTRATION / "术语表.md"
FILE_PIPELINE_DOC = DIR_ORCHESTRATION / "多智能体架构.md"


# ===========================================================================
# 状态枚举
# ===========================================================================

class CardStatus(str, Enum):
    """史料库/核证附录的状态体系"""
    VERIFIED = "✅"       # 已核证
    DISCREPANCY = "⚠️"    # 有出入（须用修正版）
    UNCERTAIN = "❓"      # 存疑
    PENDING = "🔲"        # 待核证
    WRONG = "❌"          # 错误（仅核证附录使用）

    @property
    def usable(self) -> bool:
        """是否可用于写作（✅ 和 ⚠️ 可用）"""
        return self in (CardStatus.VERIFIED, CardStatus.DISCREPANCY)


class AlignmentStatus(str, Enum):
    """对位台账的生命周期状态"""
    PENDING = "🔲"        # 待埋伏笔
    PLANTED = "🟡"        # 已埋伏笔
    ECHOING = "🔵"        # 待呼应
    ECHOED = "🟢"         # 已呼应
    CLOSED = "✅"         # 已核销/已闭合

    @property
    def is_terminal(self) -> bool:
        return self == AlignmentStatus.CLOSED


def _parse_card_status(text: str) -> CardStatus:
    """从文本提取史料卡片状态 emoji"""
    for s in CardStatus:
        if s.value in text:
            return s
    return CardStatus.UNCERTAIN


def _parse_alignment_status(text: str) -> AlignmentStatus:
    """从对位状态文本提取权威 emoji（以 emoji 前缀为准）"""
    # 按优先级匹配（✅ 优先于 🟢）
    for s in [AlignmentStatus.CLOSED, AlignmentStatus.ECHOED,
              AlignmentStatus.ECHOING, AlignmentStatus.PLANTED,
              AlignmentStatus.PENDING]:
        if s.value in text:
            return s
    return AlignmentStatus.PENDING


# ===========================================================================
# 数据类
# ===========================================================================

@dataclass
class HistoryCard:
    """史料库中的一张卡片"""
    id: str
    topic: str                     # "DART"
    assertion_short: str           # 索引表一句话
    status: CardStatus
    exact_text: str = ""           # 详细段全文
    sources: list[str] = field(default_factory=list)
    chapters: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status.usable

    @property
    def has_correction(self) -> bool:
        return self.status == CardStatus.DISCREPANCY

    def __repr__(self) -> str:
        return f"<HistoryCard {self.id} {self.status.value} {self.assertion_short[:40]}>"


@dataclass
class AlignmentItem:
    """对位台账中的核心对位项 A1-A10"""
    id: str
    expert_desc: str               # 专家系统侧
    agent_desc: str                # Agent 时代侧
    structural_flaw: str           # 共同病灶
    fix: str                       # 第十章解药
    status: AlignmentStatus
    status_detail: str = ""        # emoji 后自由文本
    evidence_card_ids: list[str] = field(default_factory=list)
    # 详细段字段
    ch3_anchor: Optional[str] = None
    ch9_anchor: Optional[str] = None
    ch10_anchor: Optional[str] = None
    verify_note: Optional[str] = None

    @property
    def is_closed(self) -> bool:
        return self.status == AlignmentStatus.CLOSED

    def __repr__(self) -> str:
        return f"<AlignmentItem {self.id} {self.status.value}>"


@dataclass
class Foreshadowing:
    """跨章伏笔 F1-F6"""
    id: str
    plant_chapter: str
    echo_chapters: list[str]
    summary: str
    status: AlignmentStatus

    def __repr__(self) -> str:
        return f"<Foreshadowing {self.id} {self.status.value}>"


@dataclass
class Chapter:
    """正文章节"""
    num: int
    title: str
    year_range: Optional[tuple[int, int]] = None
    sections: list[dict] = field(default_factory=list)  # {heading, level, text}
    raw_text: str = ""

    def __repr__(self) -> str:
        return f"<Chapter {self.num} {self.title[:30]}>"


@dataclass
class ExperimentResult:
    """Agent 实验单次结果"""
    experiment: str                # "exp1"
    method: str                    # "G" | "D"
    version: str                   # "v1" | "v4"
    case_id: str
    answer_md: str
    tool_calls: int
    num_messages: int
    elapsed_sec: float
    prompt_tokens_approx: int = 0
    error: Optional[str] = None

    def __repr__(self) -> str:
        return f"<ExperimentResult {self.experiment}/{self.method}-{self.version}>"


@dataclass
class TermEntry:
    """术语表条目"""
    en: str
    zh: str
    forbidden: list[str] = field(default_factory=list)
    era: str = ""                  # 符号主义/统计学习/Agent
    note: str = ""


@dataclass
class PersonEntry:
    """人名译名条目"""
    en: str
    zh: str
    first_use_rule: str = ""
    note: str = ""
    forbidden: list[str] = field(default_factory=list)


# ===========================================================================
# 解析器：史料库
# ===========================================================================

# 史料卡片 ID 正则（如 DART-01, XCON-02, FEIG-01）
_RE_CARD_ID = re.compile(r"\b([A-Z]{2,6})-(\d{2})\b")
# 索引表行（Markdown 表格）—— 用 MULTILINE 匹配
_RE_INDEX_ROW = re.compile(
    r"^\|\s*(\*\*)?([A-Z]{2,6}-\d{2})(\*\*)?\s*\|(.+?)\|(.+?)\|(.+?)\|",
    re.MULTILINE,
)
# 详细段开头（**ID**｜...）
_RE_DETAIL = re.compile(r"^\*\*([A-Z]{2,6}-\d{2})\*\*[｜|]")
# 来源行
_RE_SOURCE = re.compile(r"来源[：:]\s*(.+)")
# 史料引用（见史料库 **XCON-02** 或 **FEIG-01/02**）
_RE_CARD_REF = re.compile(r"史料库\s+\*\*([A-Z]{2,6}-\d{2}(?:/\d{2})?)\*\*")


def parse_history_library(path: Path = FILE_HISTORY_LIB) -> dict[str, HistoryCard]:
    """解析史料库 .md → {card_id: HistoryCard}

    主要从详细段（**ID**｜...）解析全部卡片；索引表作为状态补充。
    """
    text = path.read_text(encoding="utf-8")
    cards: dict[str, HistoryCard] = {}

    # 第一遍：从详细段解析全部卡片（**DART-01**｜...）
    # 识别当前主题标题，用于推断 chapter
    current_topic = ""
    current_chapter_hint = ""
    lines = text.split("\n")
    current_id: Optional[str] = None
    current_text_lines: list[str] = []

    def _flush():
        nonlocal current_id, current_text_lines
        if current_id and current_text_lines:
            full_text = "\n".join(current_text_lines).strip()
            if current_id not in cards:
                cards[current_id] = HistoryCard(
                    id=current_id,
                    topic=current_id.split("-")[0],
                    assertion_short="",
                    status=CardStatus.VERIFIED,  # 默认，后续从内容推断
                )
            cards[current_id].exact_text = full_text
            # 推断状态：从文本中找 emoji
            cards[current_id].status = _parse_card_status(full_text[:10])
            # 提取来源 URL
            for sm in _RE_SOURCE.finditer(full_text):
                src_line = sm.group(1)
                urls = re.findall(r"https?://[^\s｜|]+", src_line)
                cards[current_id].sources.extend(urls)

    for line in lines:
        stripped = line.strip()

        # 主题标题（### 主题 DART · ...（第一章））
        if stripped.startswith("### 主题 "):
            _flush()
            current_id = None
            current_text_lines = []
            # 提取主题名和章节
            tm = re.match(r"### 主题 (\S+) · (.+)", stripped)
            if tm:
                current_topic = tm.group(1)
                title_part = tm.group(2)
                cm = re.search(r"[（(](.+?)[)）]", title_part)
                if cm:
                    current_chapter_hint = cm.group(1)
            continue

        # 详细段开头
        dm = _RE_DETAIL.match(stripped)
        if dm:
            _flush()
            current_id = dm.group(1)
            rest = stripped.split("｜", 1)[-1] if "｜" in stripped else ""
            current_text_lines = [rest]
        elif current_id:
            # 分隔线或新主题结束当前卡片
            if stripped.startswith("---") and not current_text_lines[-1:] == [""]:
                _flush()
                current_id = None
                current_text_lines = []
            elif stripped.startswith("### ") or stripped.startswith("## "):
                _flush()
                current_id = None
                current_text_lines = []
            else:
                current_text_lines.append(line)

    _flush()  # 最后一个

    # 第二遍：从索引表补充 assertion_short 和 chapters
    for m in _RE_INDEX_ROW.finditer(text):
        card_id = m.group(2)
        assertion = m.group(4).strip().strip("*")
        chapter_text = m.group(6).strip()
        chapters = [c.strip() for c in re.split(r"[、,，]", chapter_text) if c.strip()]
        if card_id in cards:
            cards[card_id].assertion_short = assertion
            if chapters:
                cards[card_id].chapters = chapters
        # 如果索引表有但详细段没有（不应该发生，但容错）
        if card_id not in cards:
            status = _parse_card_status(m.group(5).strip())
            cards[card_id] = HistoryCard(
                id=card_id, topic=card_id.split("-")[0],
                assertion_short=assertion, status=status, chapters=chapters,
            )

    return cards


# ===========================================================================
# 解析器：对位台账
# ===========================================================================

# 对位表行（| **A1** | ... |）—— 用 MULTILINE 而非 $ 锚点
_RE_ALIGN_ROW = re.compile(
    r"^\|\s*\*\*(A\d+)\*\*\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|",
    re.MULTILINE,
)
# 伏笔行
_RE_FORE_ROW = re.compile(
    r"^\|\s*\*\*(F\d+)\*\*\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|",
    re.MULTILINE,
)


def parse_alignment_ledger(
    path: Path = FILE_ALIGNMENT
) -> tuple[dict[str, AlignmentItem], dict[str, Foreshadowing]]:
    """解析对位台账 → ({id: AlignmentItem}, {id: Foreshadowing})"""
    text = path.read_text(encoding="utf-8")
    alignments: dict[str, AlignmentItem] = {}
    fore: dict[str, Foreshadowing] = {}

    # 解析核心对位表
    for m in _RE_ALIGN_ROW.finditer(text):
        aid = m.group(1)
        expert = m.group(2).strip()
        agent = m.group(3).strip()
        flaw = m.group(4).strip()
        fix = m.group(5).strip()
        status_text = m.group(6).strip()

        status = _parse_alignment_status(status_text)
        # 去掉 emoji 得到 detail
        detail = status_text.replace(status.value, "").strip()

        alignments[aid] = AlignmentItem(
            id=aid,
            expert_desc=expert,
            agent_desc=agent,
            structural_flaw=flaw,
            fix=fix,
            status=status,
            status_detail=detail,
        )

    # 解析详细段，提取 evidence_card_ids 和 anchors
    for aid, item in alignments.items():
        # 在文本中找该 A 项的详细段
        pattern = rf"### {aid} ·.*?(?=### A\d+ ·|## |---|\Z)"
        dm = re.search(pattern, text, re.DOTALL)
        if dm:
            section = dm.group(0)
            # 提取史料引用
            refs = _RE_CARD_REF.findall(section)
            item.evidence_card_ids = [r.replace("/", "-").replace("-0", "-") for r in refs]
            # 提取埋设点（粗略）
            ch3 = re.search(r"第三章埋设点[：:]\s*(.+)", section)
            if ch3:
                item.ch3_anchor = ch3.group(1).strip()
            ch9 = re.search(r"第九章呼应点[：:]\s*(.+)", section)
            if ch9:
                item.ch9_anchor = ch9.group(1).strip()

    # 解析跨章伏笔
    for m in _RE_FORE_ROW.finditer(text):
        fid = m.group(1)
        plant = m.group(2).strip()
        echo = m.group(3).strip()
        summary = m.group(4).strip()
        status_text = m.group(5).strip()
        status = _parse_alignment_status(status_text)
        echo_chapters = [c.strip() for c in re.split(r"[、,，/]", echo) if c.strip()]
        fore[fid] = Foreshadowing(
            id=fid,
            plant_chapter=plant,
            echo_chapters=echo_chapters,
            summary=summary,
            status=status,
        )

    return alignments, fore


# ===========================================================================
# 解析器：正文章节
# ===========================================================================

_RE_CHAPTER_TITLE = re.compile(r"^#\s*第(\S+)章\s*(.*)$")
_RE_YEAR_RANGE = re.compile(r"（(\d{4})[—–-](\d{4})）")


def _chapter_file(num: int) -> Path:
    """根据章号找正文文件"""
    cn = {1:"一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"七",8:"八",9:"九",10:"十"}
    prefix = f"第{cn.get(num, str(num))}章"
    for f in DIR_TEXT.glob("*.md"):
        if f.name.startswith(prefix):
            return f
    raise FileNotFoundError(f"未找到第{num}章正文文件")


def parse_chapter(num: int, path: Optional[Path] = None) -> Chapter:
    """解析正文章节"""
    if path is None:
        path = _chapter_file(num)
    text = path.read_text(encoding="utf-8")

    # 标题
    lines = text.split("\n")
    title = ""
    for line in lines:
        m = _RE_CHAPTER_TITLE.match(line.strip())
        if m:
            num_str = m.group(1)
            title = f"第{m.group(1)}章 {m.group(2)}".strip()
            break

    # 年份范围
    year_range = None
    ym = _RE_YEAR_RANGE.search(title)
    if ym:
        year_range = (int(ym.group(1)), int(ym.group(2)))

    # 章节
    sections: list[dict] = []
    current_heading = ""
    current_level = 0
    current_text_lines: list[str] = []

    def _flush_section():
        nonlocal current_heading, current_level, current_text_lines
        if current_heading:
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "text": "\n".join(current_text_lines).strip(),
            })
        current_heading = ""
        current_level = 0
        current_text_lines = []

    for line in lines[1:]:  # 跳过一级标题
        stripped = line.strip()
        if stripped.startswith("## "):
            _flush_section()
            current_heading = stripped[3:].strip()
            current_level = 2
        elif stripped.startswith("### "):
            _flush_section()
            current_heading = stripped[4:].strip()
            current_level = 3
        elif current_heading:
            current_text_lines.append(line)
    _flush_section()

    return Chapter(
        num=num,
        title=title,
        year_range=year_range,
        sections=sections,
        raw_text=text,
    )


def parse_all_chapters() -> dict[int, Chapter]:
    """解析全部正文章节"""
    chapters = {}
    for num in range(1, 11):
        try:
            chapters[num] = parse_chapter(num)
        except FileNotFoundError:
            pass
    return chapters


# ===========================================================================
# 解析器：实验结果
# ===========================================================================

def parse_experiment(exp_name: str = "exp1") -> list[ExperimentResult]:
    """解析实验结果 JSON"""
    path = DIR_EXPERIMENT / f"{exp_name}_result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    results: list[ExperimentResult] = []

    def _parse_level(d, method=None, version=None):
        for key, val in d.items():
            if isinstance(val, dict):
                if "answer" in val:
                    # 叶子节点
                    results.append(ExperimentResult(
                        experiment=exp_name,
                        method=method or key,
                        version=version or key,
                        case_id=val.get("case_id", ""),
                        answer_md=val.get("answer", ""),
                        tool_calls=val.get("tool_calls", 0),
                        num_messages=val.get("num_messages", 0),
                        elapsed_sec=val.get("elapsed", 0),
                        prompt_tokens_approx=val.get("prompt_tokens_approx", 0),
                        error=val.get("error"),
                    ))
                else:
                    _parse_level(val, method=method or key, version=key if method else None)

    _parse_level(data)
    return results


def parse_all_experiments() -> list[ExperimentResult]:
    """解析全部三个实验"""
    all_results = []
    for exp in ["exp1", "exp2", "exp3"]:
        try:
            all_results.extend(parse_experiment(exp))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return all_results


# ===========================================================================
# 解析器：术语表
# ===========================================================================

def parse_glossary(path: Path = FILE_GLOSSARY) -> tuple[dict[str, PersonEntry], dict[str, TermEntry]]:
    """解析术语表 → ({en: PersonEntry}, {en: TermEntry})"""
    text = path.read_text(encoding="utf-8")
    persons: dict[str, PersonEntry] = {}
    terms: dict[str, TermEntry] = {}

    # 解析人名表
    person_section = re.search(
        r"## 二、人名译名表(.*?)(?=## 三、|$)", text, re.DOTALL
    )
    if person_section:
        for m in re.finditer(
            r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$",
            person_section.group(1), re.MULTILINE
        ):
            en = m.group(1).strip().strip("*")
            zh = m.group(2).strip().strip("*")
            rule = m.group(3).strip()
            note = m.group(4).strip().strip("*")
            if en.startswith("---") or en.startswith("英文"):
                continue
            persons[en] = PersonEntry(en=en, zh=zh, first_use_rule=rule, note=note)

    # 解析禁用译法
    forbidden_section = re.search(r"禁用译法[**]*[：:](.*?)(?=---|$)", text, re.DOTALL)
    if forbidden_section:
        for m in re.finditer(r'([\w\s.]+?)译["""](.+?)["""]❌', forbidden_section.group(1)):
            en_name = m.group(1).strip()
            wrong = m.group(2).strip()
            # 找到对应人名
            for p_en, p in persons.items():
                if en_name in p_en:
                    p.forbidden.append(wrong)

    # 解析术语表
    era = ""
    for line in text.split("\n"):
        if line.strip().startswith("### ") and "术语" in line:
            era = line.strip().replace("### ", "").split("（")[0].strip()
        # 术语行
        m = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if m and "术语" in line or (m and m.group(1).strip() not in ["---", "术语（英）", "英文原名"]):
            en = m.group(1).strip()
            zh = m.group(2).strip()
            forbidden_str = m.group(3).strip()
            note = m.group(4).strip()
            if en.startswith("---") or en.startswith("英文") or en.startswith("术语"):
                continue
            if forbidden_str and forbidden_str != "——":
                forbidden_list = [f.strip() for f in forbidden_str.split("/") if f.strip()]
            else:
                forbidden_list = []
            terms[en] = TermEntry(en=en, zh=zh, forbidden=forbidden_list, era=era, note=note)

    return persons, terms


# ===========================================================================
# 便捷函数：一次性加载全部
# ===========================================================================

@dataclass
class BookData:
    """全部解析后的数据"""
    cards: dict[str, HistoryCard]
    alignments: dict[str, AlignmentItem]
    foreshadowings: dict[str, Foreshadowing]
    chapters: dict[int, Chapter]
    experiments: list[ExperimentResult]
    persons: dict[str, PersonEntry]
    terms: dict[str, TermEntry]

    def summary(self) -> dict:
        """全书数据摘要"""
        return {
            "史料卡片总数": len(self.cards),
            "已核证(✅)": sum(1 for c in self.cards.values() if c.status == CardStatus.VERIFIED),
            "有出入(⚠️)": sum(1 for c in self.cards.values() if c.status == CardStatus.DISCREPANCY),
            "对位项总数": len(self.alignments),
            "已闭合(✅)": sum(1 for a in self.alignments.values() if a.is_closed),
            "跨章伏笔总数": len(self.foreshadowings),
            "正文章节数": len(self.chapters),
            "实验结果数": len(self.experiments),
            "人名条目": len(self.persons),
            "术语条目": len(self.terms),
        }


def load_all() -> BookData:
    """一次性加载全部资产"""
    cards = parse_history_library()
    alignments, fore = parse_alignment_ledger()
    chapters = parse_all_chapters()
    experiments = parse_all_experiments()
    persons, terms = parse_glossary()
    return BookData(
        cards=cards,
        alignments=alignments,
        foreshadowings=fore,
        chapters=chapters,
        experiments=experiments,
        persons=persons,
        terms=terms,
    )


# ===========================================================================
# CLI 入口
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("AI之书 Harness —— 数据层自检")
    print("=" * 60)

    data = load_all()
    s = data.summary()
    for k, v in s.items():
        print(f"  {k}: {v}")

    print(f"\n  对位项状态分布:")
    from collections import Counter
    status_dist = Counter(a.status.value for a in data.alignments.values())
    for status, count in sorted(status_dist.items()):
        print(f"    {status}: {count}")

    print(f"\n  示例查询: lookup XCON-02")
    xcon = data.cards.get("XCON-02")
    if xcon:
        print(f"    {xcon}")
        print(f"    exact_text 前 100 字: {xcon.exact_text[:100]}...")
        print(f"    sources: {len(xcon.sources)} 个 URL")

    print(f"\n  示例查询: 对位项 A1")
    a1 = data.alignments.get("A1")
    if a1:
        print(f"    {a1}")
        print(f"    evidence_card_ids: {a1.evidence_card_ids}")

    print(f"\n✅ 数据层自检通过" if s["史料卡片总数"] > 0 else "❌ 解析失败")
