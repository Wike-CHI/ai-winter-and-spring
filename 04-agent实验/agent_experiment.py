"""
Agent 边界实验主脚本
=====================
通用 Agent (G) vs 专用 Agent (DENDRAL 升级版 D) 的边界对照实验。

验证本书第三章↔第九章对位论证的三个核心病灶在 Agent 时代是否重演：
  - A1 Prompt 爆炸
  - A3 长程任务漂移
  - A4 脆弱性

运行：python agent_experiment.py
需配置环境变量 DEEPSEEK_API_KEY
"""

import os
import sys
import json
import time
import traceback

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

# 导入工具集
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools_dendral import SPECIALIST_TOOLS, GENERAL_TOOLS

# ===========================================================================
# 配置
# ===========================================================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ZAI_API_KEY = "8b7219683f1f475b8f3d33887a824e2b.7CmO7hCEGPHbxkZe"
API_KEY = ZAI_API_KEY  # 使用 z.ai (智谱 GLM)
if not API_KEY:
    print("❌ 未设置 API key")
    sys.exit(1)

BASE_URL = "https://api.z.ai/api/coding/paas/v4"
MODEL = "glm-5.2"


def make_llm():
    return ChatOpenAI(
        model=MODEL, api_key=API_KEY, base_url=BASE_URL, temperature=0
    )


# ===========================================================================
# 测试题集（5 题，含 2 题边界外）
# ===========================================================================

TEST_CASES = [
    {
        "id": "T1-乙醇",
        "in_boundary": True,
        "question": (
            "某有机化合物，质谱分子离子峰 M+ = 46，主要碎片峰 m/z 31 (强度 100%)。"
            "请推断这是什么分子，给出分子式和结构。"
        ),
        "expected": "乙醇 C2H6O (CH3CH2OH)。m/z 31 是 CH2=OH+ 特征碎片。",
        "elements": ["C", "H", "O"],
    },
    {
        "id": "T2-丙酮",
        "in_boundary": True,
        "question": (
            "某化合物 M+ = 58，强峰 m/z 43 (100%)。推断分子式与可能的化合物。"
        ),
        "expected": "丙酮 C3H6O (CH3COCH3)。m/z 43 是 CH3CO+ 乙酰基特征。",
        "elements": ["C", "H", "O"],
    },
    {
        "id": "T3-乙酸",
        "in_boundary": True,
        "question": (
            "某有机酸 M+ = 60，特征峰 m/z 45 和 m/z 60 (McLafferty)。推断分子。"
        ),
        "expected": "乙酸 C2H4O2 (CH3COOH)。m/z 45=COOH+, m/z 60=McLafferty 重排。",
        "elements": ["C", "H", "O"],
    },
    {
        "id": "T4-二茂铁(边界外)",
        "in_boundary": False,
        "question": (
            "某橙色晶体，M+ = 186，含铁元素。它是金属有机化合物，"
            "由两个环戊二烯基和一个铁原子组成。请推断结构。"
        ),
        "expected": "二茂铁 Fe(C5H5)2。这是 DENDRAL 工具库不覆盖的金属有机化合物——"
        "专用工具的 validate_structure 和 infer_molecular_formula 无法处理 Fe。",
        "elements": ["Fe", "C", "H"],
    },
    {
        "id": "T5-青霉素核心(边界外)",
        "in_boundary": False,
        "question": (
            "某天然产物 M+ = 350，含 C/H/O/N/S，结构极复杂（β-内酰胺并环）。"
            "请推断分子式与结构类型。"
        ),
        "expected": "类似青霉素核心的复杂含硫天然产物。"
        "DENDRAL 工具库不覆盖 S 元素的复杂环系推断——这是设计边界外。",
        "elements": ["C", "H", "O", "N", "S"],
    },
]

# ===========================================================================
# Agent G / Agent D 的 Prompt 配置（子实验1用 4 个版本）
# ===========================================================================

PROMPT_VERSIONS = {
    "G": {
        "v1": "你是一个化学分析助手。请用可用工具帮助用户。",
        "v2": "你是一个化学分析助手。质谱分析时：m/z 31 提示羟基，m/z 43 提示乙酰基，m/z 45 提示羧酸。M-18 提示醇失水。请用工具。",
        "v3": "你是一个化学分析助手。质谱分析时：m/z 31 提示羟基，m/z 43 提示乙酰基，m/z 45 提示羧酸。M-18 提示醇失水。氮规则：奇数分子量含奇数氮。常见官能团：羟基C/H/O、羰基C=O、羧基COOH、氨基NH2。DBE=0 饱和，DBE=4 苯环。请用工具。",
        "v4": "你是一个化学分析助手。质谱分析时：m/z 31 提示羟基，m/z 43 提示乙酰基，m/z 45 提示羧酸。M-18 提示醇失水。氮规则：奇数分子量含奇数氮。常见官能团：羟基C/H/O、羰基C=O、羧基COOH、氨基NH2。DBE=0 饱和，DBE=4 苯环。McLafferty 重排在 m/z 60 提示羧酸/酯。m/z 30 提示氨基或硝基。金属有机化合物需特殊处理。复杂天然产物请谨慎。请用工具。",
    },
    "D": {
        "v1": "你是一个有机小分子结构推断专家，使用 DENDRAL 方法：质谱→官能团→候选结构→校验。",
        "v2": "你是一个有机小分子结构推断专家，使用 DENDRAL 方法：质谱→官能团→候选结构→校验。优先调用专用工具。",
        "v3": "你是一个有机小分子结构推断专家，使用 DENDRAL 方法：质谱→官能团→候选结构→校验。优先调用专用工具。氮规则与 DBE 由工具自动处理。",
        "v4": "你是一个有机小分子结构推断专家，使用 DENDRAL 方法：质谱→官能团→候选结构→校验。优先调用专用工具。氮规则与 DBE 由工具自动处理。遇到金属有机或含硫复杂天然产物时，明确告知超范围。",
    },
}


def count_tokens_approx(text: str) -> int:
    """粗略估算 token 数（中文按 1.5 字/token，英文按 0.75 词/token）。"""
    cn = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    en_words = len([w for w in text.split() if all(ord(c) < 128 for c in w)])
    return int(cn * 1.5 + en_words * 1.3)


def build_agent(agent_type: str, prompt_version: str):
    """构建 agent。agent_type='G' 通用，'D' 专用。prompt_version='v1'..'v4'。"""
    llm = make_llm()
    prompt = PROMPT_VERSIONS[agent_type][prompt_version]
    if agent_type == "D":
        tools = SPECIALIST_TOOLS
    else:
        tools = GENERAL_TOOLS
    agent = create_react_agent(
        llm, tools, prompt=prompt, checkpointer=InMemorySaver()
    )
    return agent


def run_one(agent, question: str, thread_id: str, timeout_per_call: int = 120) -> dict:
    """跑单个 case，返回 {answer, elapsed, error}。"""
    t0 = time.time()
    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 40},
        )
        elapsed = time.time() - t0
        messages = result.get("messages", [])
        # 取最后一条 AI 消息作为答案
        ai_answer = ""
        tool_calls_count = 0
        for msg in reversed(messages):
            msg_type = type(msg).__name__
            if msg_type == "AIMessage" and msg.content:
                ai_answer = msg.content
                break
        for msg in messages:
            if type(msg).__name__ == "AIMessage" and getattr(msg, "tool_calls", None):
                tool_calls_count += len(msg.tool_calls)
        return {
            "answer": ai_answer[:800],
            "elapsed": round(elapsed, 1),
            "tool_calls": tool_calls_count,
            "num_messages": len(messages),
            "error": None,
        }
    except Exception as e:
        return {
            "answer": "",
            "elapsed": round(time.time() - t0, 1),
            "tool_calls": 0,
            "num_messages": 0,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }


# ===========================================================================
# 子实验 1：Prompt 爆炸（A1）
# ===========================================================================


def experiment_prompt_explosion() -> dict:
    """G 和 D 各 2 个 prompt 版本（v1 极简 vs v4 最复杂），跑 T1（边界内简单题）。"""
    print("\n" + "=" * 70)
    print("子实验 1：Prompt 爆炸（对位 A1）")
    print("=" * 70)

    results = {"G": {}, "D": {}}
    case = TEST_CASES[0]  # T1 乙醇

    for agent_type in ["D", "G"]:
        for ver in ["v1", "v4"]:
            prompt = PROMPT_VERSIONS[agent_type][ver]
            prompt_tokens = count_tokens_approx(prompt)
            label = f"{agent_type}-{ver}"
            print(f"\n▶ 跑 {label} (prompt ~{prompt_tokens} tokens)...")
            agent = build_agent(agent_type, ver)
            tid = f"exp1_{label}"
            r = run_one(agent, case["question"], tid)
            r["prompt_tokens_approx"] = prompt_tokens
            r["case_id"] = case["id"]
            results[agent_type][ver] = r
            status = "✓" if r["error"] is None else "✗"
            print(f"  {status} 耗时 {r['elapsed']}s, 工具调用 {r['tool_calls']} 次, "
                  f"消息 {r['num_messages']} 条")
            if r["error"]:
                print(f"  错误: {r['error'][:100]}")

    return results


# ===========================================================================
# 子实验 2：长程任务漂移（A3）
# ===========================================================================


def experiment_long_range_drift() -> dict:
    """3 步 / 5 步 / 8 步任务链，G vs D。"""
    print("\n" + "=" * 70)
    print("子实验 2：长程任务漂移（对位 A3）")
    print("=" * 70)

    # 任务链定义
    CHAINS = {
        3: (
            "请完成以下 3 步任务：\n"
            "1. 推断这个分子的结构：M+ = 46, m/z 31 强峰。\n"
            "2. 给出它的分子式。\n"
            "3. 用一句话总结你的判断。"
        ),
        5: (
            "请完成以下 5 步任务：\n"
            "1. 推断这个分子的结构：M+ = 46, m/z 31 强峰。\n"
            "2. 给出它的分子式。\n"
            "3. 计算它的不饱和度。\n"
            "4. 说明它的主要官能团。\n"
            "5. 用一句话总结你的判断，并说明你用了哪些工具。"
        ),
        8: (
            "请完成以下 8 步任务：\n"
            "1. 推断这个分子的结构：M+ = 46, m/z 31 强峰。\n"
            "2. 给出它的分子式。\n"
            "3. 计算它的不饱和度。\n"
            "4. 说明它的主要官能团。\n"
            "5. 写出它的化学命名。\n"
            "6. 推测它在质谱中的另一个可能的碎片峰。\n"
            "7. 判断它是否溶于水，简述理由。\n"
            "8. 用一句话总结你的判断，并列出你调用过的工具。"
        ),
    }

    results = {"G": {}, "D": {}}
    for agent_type in ["G", "D"]:
        for steps, question in CHAINS.items():
            label = f"{agent_type}-{steps}步"
            print(f"\n▶ 跑 {label}...")
            agent = build_agent(agent_type, "v3")  # 用中等 prompt
            tid = f"exp2_{agent_type}_{steps}"
            r = run_one(agent, question, tid)
            r["steps"] = steps
            r["case_id"] = "T1-乙醇"
            results[agent_type][str(steps)] = r
            status = "✓" if r["error"] is None else "✗"
            print(f"  {status} 耗时 {r['elapsed']}s, 工具调用 {r['tool_calls']} 次, "
                  f"消息 {r['num_messages']} 条")

    return results


# ===========================================================================
# 子实验 3：脆弱性（A4）⭐ 核心
# ===========================================================================


def experiment_brittleness() -> dict:
    """3 题（2 边界内 + 1 边界外），G vs D 的失效模式。"""
    print("\n" + "=" * 70)
    print("子实验 3：脆弱性（对位 A4）⭐ 核心")
    print("=" * 70)

    # 精简为 3 题：T1 乙醇(内)、T3 乙酸(内)、T4 二茂铁(外)
    selected = [TEST_CASES[0], TEST_CASES[2], TEST_CASES[3]]
    results = {"D": {}, "G": {}}
    for agent_type in ["D", "G"]:
        agent = build_agent(agent_type, "v3")
        for case in selected:
            cid = case["id"]
            label = f"{agent_type}-{cid}"
            print(f"\n▶ 跑 {label} (边界{'内' if case['in_boundary'] else '外'})...")
            full_q = case["question"] + f"\n（已知含元素：{', '.join(case['elements'])}）"
            tid = f"exp3_{agent_type}_{cid}"
            r = run_one(agent, full_q, tid)
            r["case_id"] = cid
            r["in_boundary"] = case["in_boundary"]
            r["expected"] = case["expected"]
            ans = r["answer"].lower() if r["answer"] else ""
            admits_limit = any(
                kw in ans
                for kw in ["无法", "不能", "不在", "超范围", "不清楚", "难以", "超出", "不支持", "无法处理"]
            )
            r["admits_limitation"] = admits_limit
            results[agent_type][cid] = r
            status = "✓" if r["error"] is None else "✗"
            bound = "内" if case["in_boundary"] else "外"
            print(f"  {status} [{bound}] 耗时 {r['elapsed']}s, "
                  f"承认局限={admits_limit}, 工具调用 {r['tool_calls']} 次")

    return results


# ===========================================================================
# 主函数
# ===========================================================================


def main():
    print("=" * 70)
    print("Agent 边界实验：通用 G vs 专用 D（DENDRAL 升级版）")
    print(f"模型：{MODEL} | {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    all_results = {"experiment_date": time.strftime("%Y-%m-%d %H:%M:%S"), "model": MODEL}

    try:
        all_results["exp1_prompt_explosion"] = experiment_prompt_explosion()
    except Exception as e:
        print(f"\n❌ 子实验1失败: {e}")
        traceback.print_exc()
        all_results["exp1_prompt_explosion"] = {"error": str(e)}

    try:
        all_results["exp2_long_range_drift"] = experiment_long_range_drift()
    except Exception as e:
        print(f"\n❌ 子实验2失败: {e}")
        traceback.print_exc()
        all_results["exp2_long_range_drift"] = {"error": str(e)}

    try:
        all_results["exp3_brittleness"] = experiment_brittleness()
    except Exception as e:
        print(f"\n❌ 子实验3失败: {e}")
        traceback.print_exc()
        all_results["exp3_brittleness"] = {"error": str(e)}

    # 保存原始结果
    out_path = os.path.join(os.path.dirname(__file__), "实验结果.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n{'=' * 70}")
    print(f"✅ 全部完成。原始结果已保存至：{out_path}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
