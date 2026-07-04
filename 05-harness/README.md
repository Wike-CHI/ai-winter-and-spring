# AI之书 Harness —— 可编程查询与验证框架

> 把这本书的全部资产（史料库、对位台账、正文、实验数据、术语表），变成 Agent 可查询的 API + 自动化回归测试 + 写作流水线固化。

## 这是什么

这套 harness 是《智能之冬与智能之春》项目的**工程基础设施**——它把五份编排资产 + 十章正文 + Agent 实验数据解析为 Python 对象，提供三层能力：

```
05-harness/
├── data_layer.py         ← 数据层：解析全部资产（零外部依赖）
├── query_api.py          ← 查询层：Agent 可调用的 ~20 个查询函数
├── regression_tests.py   ← 回归层：36 项自动化史实一致性测试
├── pipeline.py           ← 流水线层：写作流水线状态追踪
└── README.md             ← 本文件
```

## 快速开始

```bash
# 1. 数据层自检（验证解析正确）
python data_layer.py

# 2. 查询层演示
python query_api.py

# 3. 回归测试（36 项全部通过）
python regression_tests.py

# 4. 流水线状态
python pipeline.py
```

## 查询 API 示例

```python
from query_api import lookup_card, alignment_table, search_cards, translate

# 查史料卡片
card = lookup_card("XCON-02")  # XCON 规则增长曲线
print(card.status)  # CardStatus.VERIFIED
print(card.exact_text[:100])

# 查对位表
print(alignment_table())  # A1-A10 全部闭合状态

# 搜索
for c in search_cards("第五代机"):
    print(c.id, c.status.value)

# 翻译
translate("Herbert A. Simon")  # → "司马贺"
translate("Rule Explosion")    # → "规则爆炸"
```

## 回归测试覆盖

| 类别 | 测试数 | 说明 |
|---|---|---|
| 数据完整性 | 5 | 卡片/对位/伏笔/章节/实验数量 |
| 史料来源 | 1 | 无来源卡片阈值检查 |
| 待核证状态 | 1 | 全书定稿后无 🔲 |
| 对位闭环 | 11 | A1-A10 全部 ✅已闭合 |
| 对位-史料引用 | 4 | 引用的卡片 ID 必须存在 |
| 跨章伏笔 | 1 | 核心伏笔 F1-F3 已推进 |
| 术语一致性 | 1 | 全书无禁用译法 |
| 实验完整性 | 6 | 三个实验有结果且无错误 |
| 数字一致性 | 4 | XCON 17,500 / 第五代机预算 / GPT 参数量 |
| 实验-报告一致 | 2 | 报告含关键发现 |
| **合计** | **36** | **全部通过 ✅** |

## 数据层解析能力

| 资产 | 解析结果 | 数量 |
|---|---|---|
| 史料库 | `{card_id: HistoryCard}` | 105 张卡片 |
| 对位台账 | `{id: AlignmentItem}` + `{id: Foreshadowing}` | 10 + 6 |
| 正文章节 | `{num: Chapter}` | 10 章 |
| 实验结果 | `list[ExperimentResult]` | 16 条 |
| 术语表 | `{en: PersonEntry}` + `{en: TermEntry}` | 43 + 105 |

## 技术特点

- **零外部依赖**：仅用 Python 标准库（re, json, dataclasses, pathlib, enum）
- **全程 UTF-8**：正确处理中文路径、全角标点、emoji 状态标记
- **两套状态体系**：史料库用 ✅⚠️❓🔲，对位台账用 🔲🟡🔵🟢✅
- **容错设计**：前导零自动补全（XCON-2 → XCON-02）、斜杠引用拆分（FEIG-01/02）

## 与全书的元叙事关系

这套 harness 本身就是第十章"Agent Operating System"论点的实践——它把易腐的 Markdown 文档，固化为**可查询、可测试、可版本化的工程资产**。每次内容改动后跑一遍回归测试，就能确保史实一致性不退化。
