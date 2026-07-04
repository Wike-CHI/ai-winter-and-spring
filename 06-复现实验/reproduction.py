"""
四十年对照实验：专家系统 vs Agent 的规则爆炸复现
================================================

一个可交互的命令行脚本，让读者亲手经历从 1977 到 2026 的四十年。

第一幕（专家系统，1977-1985）：
  - 用纯 Python 实现简化版 MYCIN（感染诊断）
  - 读者逐步加规则，观察规则爆炸（A1）、规则冲突（A3）、脆弱性（A4）

第二幕（Agent 时代，2022-2026）：
  - 同一套诊断任务，但用"规则→prompt"的方式重做
  - 观察相同的病灶以新形态重演

运行：python reproduction.py
"""

from __future__ import annotations

import random
import textwrap
from dataclasses import dataclass, field
from typing import Optional

# ===========================================================================
# 第一幕：专家系统引擎（简化版 MYCIN / XCON）
# ===========================================================================

@dataclass
class Rule:
    """专家系统的一条产生式规则"""
    rid: int                        # 规则编号
    condition: str                  # 条件描述（人类可读）
    condition_fn: callable          # 条件判断函数
    action: str                     # 结论描述
    conflicts_with: list[int] = field(default_factory=list)  # 被这条规则破坏的既有规则

    def __repr__(self):
        return f"R{self.rid}: IF {self.condition} THEN {self.action}"


class ExpertSystem:
    """
    简化版专家系统引擎。
    - 用规则库做前向推理
    - 自动检测规则间的冲突（新规则是否破坏既有规则的结论）
    - 模拟维护成本随规则数增长
    """

    def __init__(self, name: str = "MYCIN-Mini"):
        self.name = name
        self.rules: list[Rule] = []
        self.next_rid = 1
        self.conflict_log: list[str] = []  # 冲突记录

    def add_rule(self, condition: str, condition_fn: callable, action: str) -> Rule:
        """添加一条规则，自动检测与既有规则的冲突"""
        rule = Rule(
            rid=self.next_rid,
            condition=condition,
            condition_fn=condition_fn,
            action=action,
        )

        # 冲突检测：用同一组测试输入，看新规则是否改变既有规则的结论
        test_cases = self._generate_test_cases()
        for existing in self.rules:
            for tc in test_cases:
                try:
                    old_fire = existing.condition_fn(tc)
                    new_fire = rule.condition_fn(tc)
                    # 如果新规则和旧规则在同一输入下都触发但结论不同
                    if old_fire and new_fire and existing.action != rule.action:
                        rule.conflicts_with.append(existing.rid)
                        self.conflict_log.append(
                            f"⚠️  R{rule.rid} 与 R{existing.rid} 冲突！"
                            f"（输入 {tc}：R{existing.rid} 说'{existing.action}'，"
                            f"R{rule.rid} 说'{rule.action}'）"
                        )
                except Exception:
                    pass

        self.rules.append(rule)
        self.next_rid += 1
        return rule

    def infer(self, facts: dict) -> list[str]:
        """前向推理：给定事实，返回所有触发规则的动作"""
        conclusions = []
        for rule in self.rules:
            try:
                if rule.condition_fn(facts):
                    conclusions.append(f"R{rule.rid}: {rule.action}")
            except Exception:
                pass
        return conclusions

    def _generate_test_cases(self) -> list[dict]:
        """生成测试用例用于冲突检测"""
        base = [
            {"symptom": "发烧", "wbc": "高", "temp": 39, "source": "尿路"},
            {"symptom": "发烧", "wbc": "高", "temp": 39, "source": "肺部"},
            {"symptom": "发烧", "wbc": "正常", "temp": 38, "source": "未知"},
            {"symptom": "咳嗽", "wbc": "正常", "temp": 37, "source": "肺部"},
            {"symptom": "无症状", "wbc": "正常", "temp": 36.5, "source": "无"},
        ]
        return base

    def stats(self) -> dict:
        total_conflicts = sum(len(r.conflicts_with) for r in self.rules)
        return {
            "规则数": len(self.rules),
            "冲突数": total_conflicts,
            "冲突率": f"{total_conflicts/max(len(self.rules),1)*100:.0f}%",
            "维护成本指数": self._maintenance_cost(),

        }

    def _maintenance_cost(self) -> str:
        """模拟维护成本：O(N²) 增长"""
        n = len(self.rules)
        cost = n * (n - 1) / 2  # 两两检查的组合数
        if cost < 10:
            return "低"
        elif cost < 100:
            return "中"
        elif cost < 500:
            return "高 ⚠️"
        else:
            return "失控 🔴"

    def print_rules(self):
        """打印规则库"""
        for r in self.rules:
            conflict_mark = f"  [冲突: R{r.conflicts_with}]" if r.conflicts_with else ""
            print(f"  {r}{conflict_mark}")


# ===========================================================================
# 第二幕：Agent 时代的"规则→prompt"映射
# ===========================================================================

class AgentPromptSimulator:
    """
    模拟 Agent 时代的"规则→prompt"映射。

    专家系统的每条 IF-THEN 规则，在 Agent 时代变成 prompt 里的一条指令。
    观察 prompt 长度和工具调用复杂度的增长。
    """

    def __init__(self):
        self.instructions: list[str] = []  # prompt 里的指令
        self.tools: list[str] = []         # 工具列表
        self.knowledge_tokens: int = 0     # 知识承载的 token 数

    def add_knowledge_as_prompt(self, rule_text: str):
        """把知识加进 system prompt（对应通用 Agent G 的做法）"""
        self.instructions.append(rule_text)
        # 估算 token：中文约 1.5 字/token
        self.knowledge_tokens += int(len(rule_text) * 1.2)

    def add_knowledge_as_tool(self, tool_name: str, tool_desc: str):
        """把知识固化成工具（对应专用 Agent D 的做法）"""
        self.tools.append(tool_name)
        # 工具描述占的 token 远少于把全部逻辑写进 prompt
        self.knowledge_tokens += int(len(tool_desc) * 0.8)

    def stats(self) -> dict:
        prompt_tokens = sum(int(len(i) * 1.2) for i in self.instructions)
        tool_tokens = sum(15 for _ in self.tools)  # 每个工具声明约 15 token
        return {
            "prompt 指令数": len(self.instructions),
            "工具数": len(self.tools),
            "prompt token 估算": prompt_tokens,
            "工具声明 token": tool_tokens,
            "知识总 token": prompt_tokens + tool_tokens,
            "维护模式": "Prompt 爆炸 ⚠️" if prompt_tokens > 200 else "可控",
        }


# ===========================================================================
# 可视化
# ===========================================================================

def draw_rule_curve(history: list[int], conflicts: list[int]):
    """用 ASCII 画规则增长曲线和冲突曲线"""
    print("\n  规则增长 vs 冲突增长曲线：")
    print("  " + "-" * 50)

    max_rules = max(history) if history else 1
    max_conflicts = max(conflicts) if conflicts else 1

    for i, (rules, conf) in enumerate(zip(history, conflicts)):
        rules_bar = "█" * int(rules / max(max_rules, 1) * 30)
        conf_bar = "▓" * int(conf / max(max_conflicts, 1) * 20) if conf > 0 else ""
        step_labels = ["初始", "+规则", "+规则", "+规则", "+边界规则"]
        label = step_labels[i] if i < len(step_labels) else f"步骤{i}"
        print(f"  {label:>8} │ 规则 {rules:>2} {rules_bar}")
        if conf > 0:
            print(f"  {'':>8} │ 冲突 {conf:>2} {conf_bar}")

    print("  " + "-" * 50)
    print("  💡 观察：规则线性增长，冲突超线性增长（O(N²)）——这就是规则爆炸")


def draw_conflict_matrix(es: ExpertSystem):
    """画规则冲突矩阵"""
    n = len(es.rules)
    if n == 0:
        return
    print(f"\n  冲突矩阵（{n}×{n}）：")
    header = "     " + "".join(f"R{i+1:<2}" for i in range(n))
    print(header)
    for i, r1 in enumerate(es.rules):
        row = f"  R{i+1:<2} "
        for j, r2 in enumerate(es.rules):
            if i == j:
                row += " · "
            elif r2.rid in r1.conflicts_with:
                row += " ✗ "
            else:
                row += " · "
        print(row)
    print("  图例：✗ = 冲突  · = 无冲突")


# ===========================================================================
# 交互式演示
# ===========================================================================

def demo_expert_system():
    """第一幕：专家系统复现"""
    print("\n" + "=" * 70)
    print("  第一幕：专家系统时代（1977-1985）")
    print("  复现 MYCIN 简化版——感染诊断专家系统")
    print("=" * 70)

    print(textwrap.dedent("""
    1977 年，费根鲍姆命名了"知识获取瓶颈"。
    让我们回到那个年代，亲手构建一个感染诊断专家系统。
    你将看到：规则如何增长，冲突如何出现，系统如何变脆弱。

    """))

    es = ExpertSystem("MYCIN-Mini")
    rule_history = []
    conflict_history = []

    # 初始规则（1977 年的 MYCIN 起步）
    print("── 步骤 1：初始规则库（3 条）──")
    es.add_rule(
        "发烧 + 白细胞高",
        lambda f: f.get("temp", 0) >= 38 and f.get("wbc") == "高",
        "疑似细菌感染 → 建议抗生素"
    )
    es.add_rule(
        "发烧 + 尿路来源",
        lambda f: f.get("temp", 0) >= 38 and f.get("source") == "尿路",
        "疑似尿路感染 → 建议呋喃妥因"
    )
    es.add_rule(
        "咳嗽 + 肺部来源",
        lambda f: f.get("symptom") == "咳嗽" and f.get("source") == "肺部",
        "疑似肺炎 → 建议青霉素"
    )
    es.print_rules()
    s = es.stats()
    print(f"  📊 {s}")
    rule_history.append(s["规则数"])
    conflict_history.append(s["冲突数"])

    # 测试正确诊断
    print("\n── 测试：尿路感染患者 ──")
    patient = {"symptom": "发烧", "wbc": "高", "temp": 39, "source": "尿路"}
    print(f"  患者: {patient}")
    results = es.infer(patient)
    print(f"  诊断: {results}")

    # 逐步加规则——模拟 XCON 从 250→3000→10000 的增长
    print("\n── 步骤 2：加规则处理更多情况（+4 条）──")
    es.add_rule(
        "发烧 + 白细胞正常",
        lambda f: f.get("temp", 0) >= 38 and f.get("wbc") == "正常",
        "疑似病毒感染 → 不建议抗生素"
    )
    es.add_rule(
        "高烧（>39.5）",
        lambda f: f.get("temp", 0) >= 39.5,
        "高烧警告 → 建议住院观察"
    )
    es.add_rule(
        "发烧 + 肺部 + 白细胞高",
        lambda f: f.get("temp", 0) >= 38 and f.get("source") == "肺部" and f.get("wbc") == "高",
        "疑似重症肺炎 → 建议头孢类"
    )
    es.add_rule(
        "无症状 + 体温正常",
        lambda f: f.get("symptom") == "无症状" and f.get("temp", 0) < 37,
        "健康 → 无需处理"
    )

    es.print_rules()
    s = es.stats()
    print(f"  📊 {s}")
    rule_history.append(s["规则数"])
    conflict_history.append(s["冲突数"])

    if es.conflict_log:
        print("\n  ⚠️  发现冲突！")
        for log in es.conflict_log[-3:]:
            print(f"  {log}")

    # 加更多规则——触发规则爆炸
    print("\n── 步骤 3：规则爆炸（再加 6 条边界规则）──")
    extra_rules = [
        ("儿童 + 发烧", lambda f: f.get("temp", 0) >= 38, "儿童剂量减半"),
        ("孕妇 + 发烧", lambda f: f.get("temp", 0) >= 38, "禁用某些抗生素"),
        ("老人 + 高烧", lambda f: f.get("temp", 0) >= 39, "警惕并发症"),
        ("过敏 + 青霉素", lambda f: True, "改用大环内酯类"),
        ("复发感染", lambda f: f.get("temp", 0) >= 38, "建议细菌培养"),
        ("混合感染", lambda f: f.get("wbc") == "高", "联合用药"),
    ]
    for cond, fn, act in extra_rules:
        es.add_rule(cond, fn, act)

    s = es.stats()
    print(f"  📊 {s}")
    rule_history.append(s["规则数"])
    conflict_history.append(s["冲突数"])

    print(f"\n  规则总数: {len(es.rules)} 条（模拟 XCON 从 250 到 10,000+ 的增长）")
    if es.conflict_log:
        print(f"  冲突总数: {sum(len(r.conflicts_with) for r in es.rules)} 个")
        print("\n  冲突日志（最近 5 条）:")
        for log in es.conflict_log[-5:]:
            print(f"    {log}")

    # 可视化
    draw_rule_curve(rule_history, conflict_history)
    draw_conflict_matrix(es)

    # 脆弱性测试
    print("\n── 步骤 4：脆弱性测试（A4）──")
    print("  给系统一个'设计边界外'的输入：")
    edge_case = {"symptom": "皮疹", "wbc": "正常", "temp": 37.5, "source": "皮肤"}
    print(f"  边界外患者: {edge_case}")
    results = es.infer(edge_case)
    if results:
        print(f"  ❌ 系统仍然给出了诊断（但可能是错的）: {results}")
        print("  → 这就是 Brittleness：边界外不承认不会，而是 confidently 给出可能错误的结论")
    else:
        print(f"  系统没有触发任何规则——但它不会说'我不知道'")

    print("\n" + "─" * 70)
    print("  第一幕总结：专家系统三大病灶已全部复现")
    print("  A1 规则爆炸：规则线性增长，冲突 O(N²) 增长")
    print("  A3 规则冲突：加规则破坏既有规则")
    print("  A4 脆弱性：边界外不拒绝，而是给出可能错误的答案")
    print("  " + "─" * 70)

    return es


def demo_agent_era():
    """第二幕：Agent 时代的对照复现"""
    print("\n" + "=" * 70)
    print("  第二幕：Agent 时代（2022-2026）")
    print("  同样的诊断任务，但规则变成了 prompt")
    print("=" * 70)

    print(textwrap.dedent("""
    快进四十年。专家系统的 IF-THEN 规则变成了 system prompt 里的指令。
    让我们看看，同一个诊断任务，"规则→prompt"的映射会怎样。

    我们对比两种做法：
    - Agent G（通用）：把知识全塞进 system prompt
    - Agent D（专用）：把知识固化成工具

    """))

    # Agent G：知识塞进 prompt
    g = AgentPromptSimulator()
    print("── Agent G（通用）：规则 → system prompt 指令 ──")

    g.add_knowledge_as_prompt("如果患者发烧且白细胞高，疑似细菌感染，建议抗生素。")
    g.add_knowledge_as_prompt("如果患者发烧且来自尿路，疑似尿路感染，建议呋喃妥因。")
    g.add_knowledge_as_prompt("如果患者咳嗽且来自肺部，疑似肺炎，建议青霉素。")
    g.add_knowledge_as_prompt("如果患者发烧但白细胞正常，疑似病毒感染，不建议抗生素。")
    g.add_knowledge_as_prompt("如果患者高烧超过39.5度，建议住院观察。")
    g.add_knowledge_as_prompt("如果患者发烧且来自肺部且白细胞高，疑似重症肺炎，建议头孢类。")
    g.add_knowledge_as_prompt("如果患者无症状且体温低于37度，判定为健康。")
    g.add_knowledge_as_prompt("如果患者是儿童，剂量减半。")
    g.add_knowledge_as_prompt("如果患者是孕妇，禁用某些抗生素。")
    g.add_knowledge_as_prompt("如果患者对青霉素过敏，改用大环内酯类。")

    s = g.stats()
    print(f"  📊 Agent G: {s}")

    # Agent D：知识固化成工具
    d = AgentPromptSimulator()
    print("\n── Agent D（专用）：规则 → 工具 ──")

    d.add_knowledge_as_tool("diagnose_infection", "感染诊断工具：输入症状+白细胞+体温，返回感染类型")
    d.add_knowledge_as_tool("recommend_antibiotic", "抗生素推荐：输入感染类型+患者特征，返回用药建议")
    d.add_knowledge_as_tool("check_allergy", "过敏检查：输入患者+药物，返回是否安全")
    d.add_knowledge_as_tool("calc_dosage", "剂量计算：输入患者年龄+体重+药物，返回剂量")

    s = d.stats()
    print(f"  📊 Agent D: {s}")

    # 对照
    print("\n── 对照分析 ──")
    g_tokens = g.stats()["知识总 token"]
    d_tokens = d.stats()["知识总 token"]
    print(f"  Agent G 知识 token: {g_tokens}（全部在 prompt 里）")
    print(f"  Agent D 知识 token: {d_tokens}（工具描述仅声明，逻辑在工具内部）")
    print(f"  倍数差异: {g_tokens / max(d_tokens, 1):.1f}x")

    print(textwrap.dedent(f"""
    ──────────────────────────────────────────────────────────
    💡 对位分析：

    Agent G 把 10 条规则翻译成 10 条 prompt 指令，token 持续增长。
    再加 10 条规则？prompt 再翻倍。这就是 Prompt Explosion（A1）。

    Agent D 用 4 个工具吸收了全部知识，prompt 几乎不增长。
    再加 10 条规则？工具内部改，prompt 不变。这就是"把易腐上下文
    固化为可演化工程资产"（第十章 Knowledge Evolution）。

    四十年前，费根鲍姆说"知识就是力量"——规则库与推理引擎分离。
    四十年后，同样的智慧在 Agent 时代重演——工具与 prompt 分离。
    ──────────────────────────────────────────────────────────
    """))


def demo_xcon_curve():
    """彩蛋：XCON 真实规则增长曲线"""
    print("\n" + "=" * 70)
    print("  附：XCON 真实规则增长曲线（第二章史料）")
    print("=" * 70)

    data = [
        ("1978 原型", 250),
        ("1984 初", 3000),
        ("1980s末 临界", 10000),
        ("峰值", 17500),
    ]

    print("\n  XCON/R1 规则增长（McDermott 1982 / Fox 1990 / AI Magazine）：")
    print("  " + "-" * 55)
    max_val = 17500
    for label, rules in data:
        bar_len = int(rules / max_val * 40)
        bar = "█" * bar_len
        print(f"  {label:>12} │ {rules:>6} 条 {bar}")
    print("  " + "-" * 55)

    print(textwrap.dedent("""
    维护团队 CSG：数人 → 数十人
    每年修改率：约 50% 的规则需要改写
    最终：1990 年代初系统重构为 RIME 语言

    这条曲线，就是第三章"规则爆炸"的原始证据。
    """))


# ===========================================================================
# 主函数
# ===========================================================================

def main():
    print("╔" + "═" * 68 + "╗")
    print("║" + "  四十年对照实验：专家系统 vs Agent 的规则爆炸复现".center(54) + "║")
    print("║" + "  《智能之冬与智能之春》互动教学脚本".center(54) + "║")
    print("╚" + "═" * 68 + "╝")

    # 第一幕
    demo_expert_system()

    # 第二幕
    demo_agent_era()

    # 彩蛋
    demo_xcon_curve()

    print("=" * 70)
    print("  全部复现完成。")
    print("  你刚刚亲手经历了：")
    print("    1. 规则爆炸（A1）——规则线性增长，冲突 O(N²) 增长")
    print("    2. 规则冲突（A3）——加一条规则破坏既有规则")
    print("    3. 脆弱性（A4）——边界外 confidently 给出可能错误的答案")
    print("    4. Prompt 爆炸——同样的知识，塞进 prompt vs 固化成工具的差异")
    print("    5. XCON 真实曲线——从 250 条到 17,500 条的崩塌")
    print()
    print("  这些就是第三章和第八章的核心论点的活体复现。")
    print("  病灶不在容器——在'用显式手工编码知识覆盖开放世界'这个动作本身。")
    print("=" * 70)


if __name__ == "__main__":
    main()
