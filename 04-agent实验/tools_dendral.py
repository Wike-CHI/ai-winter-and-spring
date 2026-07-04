"""
DENDRAL 升级版专用工具集
=========================
对应第三章"专家系统规则库"的当代化——把化学领域知识固化进 @tool。

设计哲学：
  - 这些工具承载了 DENDRAL 的领域知识（质谱规则、官能团库、分子式约束）
  - 确定性 Python 实现（不调 LLM），保证工具本身可复现
  - 与"通用工具"（计算器、查询）形成对照——验证第三章"专用 vs 通用"的当代版

边界（故意设置的，用于 A4 脆弱性实验）：
  - 官能团库只覆盖常见有机小分子官能团
  - 质谱规则只覆盖 C/H/O/N 四元素
  - 金属有机、含硫/磷/卤素的复杂天然产物在设计边界外
"""

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# 内置知识库（DENDRAL 的"规则库"当代化）
# ---------------------------------------------------------------------------

# 官能团数据库（简化版，覆盖常见有机小分子）
FUNCTIONAL_GROUPS = {
    "hydroxyl": {
        "formula": "-OH",
        "ms_signature": "M-18 失水峰; m/z 31 (CH2=OH+ 常见碎片)",
        "common_classes": "醇、酚",
    },
    "carbonyl": {
        "formula": "C=O",
        "ms_signature": "m/z 43 (CH3CO+) 或 m/z 29 (CHO+); 显著 M+ 峰",
        "common_classes": "醛、酮",
    },
    "carboxyl": {
        "formula": "-COOH",
        "ms_signature": "M-17 (OH), M-45 (COOH); m/z 45 (COOH+); m/z 60 (McLafferty 重排)",
        "common_classes": "羧酸",
    },
    "amino": {
        "formula": "-NH2",
        "ms_signature": "M-16; m/z 30 (CH2=NH2+); 氮规则的奇数分子量",
        "common_classes": "伯胺",
    },
    "ester": {
        "formula": "-COOR",
        "ms_signature": "m/z 43 (CH3CO+); McLafferty 重排特征; M+ 中等",
        "common_classes": "酯",
    },
    "ether": {
        "formula": "-O-",
        "ms_signature": "m/z 31, 45, 59 (CnH2n+1O+); M+ 较弱",
        "common_classes": "醚",
    },
    "nitro": {
        "formula": "-NO2",
        "ms_signature": "M-46 (NO2); m/z 30 (NO+); m/z 46 (NO2+)",
        "common_classes": "硝基化合物",
    },
}

# 元素原子量（简化，C/H/O/N/S/P/卤素/常见金属）
ATOMIC_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999,
    "F": 18.998, "P": 30.974, "S": 32.06, "Cl": 35.45,
    "Br": 79.904, "I": 126.904,
    # 金属（边界外元素，工具不应擅长）
    "Na": 22.990, "K": 39.098, "Fe": 55.845, "Mg": 24.305, "Ca": 40.078,
}


# ---------------------------------------------------------------------------
# 专用工具（Agent D 的工具集）
# ---------------------------------------------------------------------------

@tool
def interpret_mass_spectrum(peaks: list[dict]) -> str:
    """质谱解析工具。输入质谱峰列表（每项含 m/z 和相对强度），返回可能的官能团线索和碎片推断。

    Args:
        peaks: 质谱峰列表，每项形如 {"mz": 31, "intensity": 80}。m/z 为质荷比，intensity 为相对强度（0-100）。

    Returns:
        推断出的官能团线索、关键碎片离子、分子离子峰信息。
    """
    if not peaks:
        return "错误：未提供质谱峰。"

    # 找分子离子峰（最高 m/z，强度>0）
    sorted_peaks = sorted(peaks, key=lambda p: p.get("mz", 0), reverse=True)
    m_plus = sorted_peaks[0].get("mz")
    m_plus_intensity = sorted_peaks[0].get("intensity", 0)

    result = [f"分子离子峰 M+ = {m_plus} (相对强度 {m_plus_intensity}%)"]

    # 检查失水峰（醇/酚的特征）
    has_m18 = any(abs(p.get("mz", 0) - (m_plus - 18)) < 1 for p in peaks)
    if has_m18:
        result.append("发现 M-18 失水峰 → 提示 -OH（醇/酚）")

    # 检查关键碎片
    mz_set = {p.get("mz", 0) for p in peaks}
    if 31 in mz_set:
        result.append("m/z 31 → CH2=OH+，提示羟基/醚")
    if 43 in mz_set:
        result.append("m/z 43 → CH3CO+ (乙酰基) 或 C3H7+")
    if 29 in mz_set:
        result.append("m/z 29 → CHO+ (醛) 或 C2H5+")
    if 45 in mz_set:
        result.append("m/z 45 → COOH+ 或 C2H5O+")
    if 30 in mz_set:
        result.append("m/z 30 → NO+ (硝基) 或 CH2=NH2+ (氨基)")
    if 60 in mz_set:
        result.append("m/z 60 → McLafferty 重排，提示羧酸/酯")

    # 氮规则（边界内：C/H/O/N）
    if m_plus % 2 == 1:
        result.append("奇数分子量 → 含奇数个氮原子（氮规则）")

    # 官能团匹配
    matched = []
    for name, info in FUNCTIONAL_GROUPS.items():
        sig = info["ms_signature"]
        # 简单关键词匹配
        if "M-18" in sig and has_m18:
            matched.append(f"{name} ({info['common_classes']})")
        elif "m/z 43" in sig and 43 in mz_set and "ketone" not in name:
            matched.append(f"{name} ({info['common_classes']})")
        elif "m/z 45" in sig and 45 in mz_set:
            matched.append(f"{name} ({info['common_classes']})")
        elif "m/z 60" in sig and 60 in mz_set:
            matched.append(f"{name} ({info['common_classes']})")

    if matched:
        result.append("可能的官能团: " + ", ".join(set(matched)))
    else:
        result.append("未匹配到已知官能团模式（可能在工具知识范围外）")

    return "\n".join(result)


@tool
def lookup_functional_group(name: str) -> str:
    """查询官能团数据库。输入官能团英文名（如 hydroxyl/carbonyl/carboxyl/amino/ester/ether/nitro），返回其分子式、质谱特征、常见类别。

    Args:
        name: 官能团英文名。支持的：hydroxyl, carbonyl, carboxyl, amino, ester, ether, nitro。

    Returns:
        官能团的分子式、质谱特征、常见类别。若不在库中，返回"未收录"。
    """
    name = name.lower().strip()
    if name in FUNCTIONAL_GROUPS:
        info = FUNCTIONAL_GROUPS[name]
        return (
            f"官能团: {name}\n"
            f"分子式: {info['formula']}\n"
            f"质谱特征: {info['ms_signature']}\n"
            f"常见类别: {info['common_classes']}"
        )
    return f"官能团 '{name}' 未收录在数据库中。本工具仅覆盖常见有机小分子官能团。"


@tool
def infer_molecular_formula(molecular_mass: float, elements: list[str]) -> str:
    """从分子量和元素组成推断可能的分子式。仅支持 C/H/O/N/F/P/S/Cl/Br/I 及常见金属。

    Args:
        molecular_mass: 分子离子峰的 m/z（分子量）。
        elements: 样品中确认含有的元素符号列表，如 ["C","H","O"]。

    Returns:
        一个或多个候选分子式（基于质量数匹配，误差 ±1）。
    """
    if molecular_mass <= 0 or not elements:
        return "错误：分子量或元素列表无效。"

    # 检查是否含工具不擅长的元素
    unsupported = [e for e in elements if e not in ATOMIC_MASS]
    if unsupported:
        return f"元素 {unsupported} 不在原子量表中。本工具仅支持 {list(ATOMIC_MASS.keys())}"

    target = round(molecular_mass)
    candidates = []

    # 简化穷举：C(1-12), H(1-24), O(0-6), N(0-4)，其他元素按 0-2
    # （真实 DENDRAL 用约束满足；这里用简化枚举演示）
    for c in range(1, 13):
        for h in range(1, 25):
            for o in range(0, 7):
                for n in range(0, 5):
                    mass = round(
                        c * ATOMIC_MASS["C"]
                        + h * ATOMIC_MASS["H"]
                        + o * ATOMIC_MASS["O"]
                        + n * ATOMIC_MASS["N"]
                    )
                    if abs(mass - target) <= 1:
                        # 过滤：必须含所列元素（除 CHON）
                        formula = f"C{c}H{h}" + (f"O{o}" if o else "") + (f"N{n}" if n else "")
                        candidates.append({"formula": formula, "mass": mass})

    if not candidates:
        return f"未找到匹配分子量的 C/H/O/N 组合（目标 {target}）。可能含其他元素。"

    # 去重并取前 5 个
    seen = set()
    unique = []
    for c in candidates:
        if c["formula"] not in seen:
            seen.add(c["formula"])
            unique.append(c)
    unique = unique[:5]

    lines = [f"目标分子量 {target}，候选分子式（C/H/O/N 范围）:"]
    for c in unique:
        lines.append(f"  - {c['formula']} (计算分子量 {c['mass']})")
    if len(unique) >= 5:
        lines.append(f"  ...(共 {len(candidates)} 个候选，仅显示前 5)")
    return "\n".join(lines)


@tool
def validate_structure(formula: str) -> str:
    """校验分子式的基本化学合理性（价态、不饱和度等简化检查）。

    Args:
        formula: 分子式字符串，如 "C2H6O"。

    Returns:
        校验结果：是否合理、不饱和度（DBE）、可能的结构提示。
    """
    import re

    if not formula:
        return "错误：未提供分子式。"

    # 解析分子式
    pattern = r"([A-Z][a-z]?)(\d*)"
    matches = re.findall(pattern, formula)
    if not matches:
        return f"错误：无法解析分子式 '{formula}'。"

    composition = {}
    for elem, count in matches:
        if elem not in ATOMIC_MASS and elem:
            return f"元素 '{elem}' 不在已知原子量表中。无法校验。"
        composition[elem] = composition.get(elem, 0) + (int(count) if count else 1)

    # 不饱和度（DBE）= C + 1 - H/2 + N/2
    c = composition.get("C", 0)
    h = composition.get("H", 0)
    n = composition.get("N", 0)
    o = composition.get("O", 0)

    if h == 0 or c == 0:
        return f"分子式 {formula}：缺少 C 或 H，无法计算不饱和度。"

    dbe = c + 1 - h / 2 + n / 2

    result = [f"分子式 {formula} 校验:"]
    result.append(f"  组成: {composition}")
    result.append(f"  不饱和度 (DBE) = {dbe}")

    if dbe < 0:
        result.append("  ⚠️ DBE 为负值 → 化学不合理（H 过多）")
    elif dbe == 0:
        result.append("  DBE=0 → 饱和分子（无环无双键）")
    elif dbe == 1:
        result.append("  DBE=1 → 一个双键或一个环")
    elif dbe >= 2 and dbe <= 4:
        result.append(f"  DBE={dbe} → 可能含双键/环/苯环（苯环 DBE=4）")
    elif dbe > 7:
        result.append(f"  DBE={dbe} → 不饱和度偏高，复杂多环结构")

    # 简单合理性：C/H 比例
    if h > 2 * c + 2 + n:
        result.append("  ⚠️ H 数超过烷烃上限 → 可能不合理")

    return "\n".join(result)


# ---------------------------------------------------------------------------
# 通用工具（Agent G 的工具集）
# ---------------------------------------------------------------------------

@tool
def calculator(expression: str) -> str:
    """通用计算器。输入算术表达式（如 "12*1.008 + 2*16"），返回计算结果。

    Args:
        expression: 算术表达式字符串。

    Returns:
        计算结果。
    """
    try:
        # 仅允许基本运算符，防止注入
        allowed = set("0123456789.+-*/() ")
        if not all(ch in allowed for ch in expression):
            return f"错误：表达式含非法字符。仅允许数字和 +-*/()。"
        result = eval(expression)  # 受控输入，可接受
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


@tool
def lookup_element(symbol: str) -> str:
    """查询元素原子量。输入元素符号（如 "C"、"Fe"），返回原子量。

    Args:
        symbol: 元素符号。

    Returns:
        该元素的原子量，或"未知元素"。
    """
    s = symbol.strip()
    if s in ATOMIC_MASS:
        return f"{s} 的原子量 = {ATOMIC_MASS[s]}"
    return f"未知元素 '{s}'。"


@tool
def general_search(query: str) -> str:
    """通用知识查询（模拟）。这是一个占位工具，仅返回"无法访问外部数据库"。

    用于演示：通用 agent 缺乏领域专用知识时的局限。

    Args:
        query: 查询内容。

    Returns:
        固定回复——演示通用工具的局限。
    """
    return f"[通用查询工具] 无法直接访问化学数据库。请用你已有的知识回答关于 '{query}' 的问题。"


# 导出供主脚本使用
SPECIALIST_TOOLS = [
    interpret_mass_spectrum,
    lookup_functional_group,
    infer_molecular_formula,
    validate_structure,
]

GENERAL_TOOLS = [calculator, lookup_element, general_search]
