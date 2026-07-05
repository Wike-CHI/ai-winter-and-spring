#!/usr/bin/env python3
"""
构建读者版：合并十章正文 + 附录为单一 Markdown 文件。
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent  # D:/ai/AI之书/
DIR_TEXT = BASE / "01-正文"

# 章节顺序
CHAPTERS = [
    "第一章-第一次黄金时代.md",
    "第二章-专家系统革命.md",
    "第三章-规则帝国.md",
    "第四章-智能之冬.md",
    "第五章-连接主义的复活.md",
    "第六章-Transformer革命.md",
    "第七章-智能之春.md",
    "第八章-Agent狂热.md",
    "第九章-历史重演.md",
    "第十章-Agent操作系统.md",
    "附录-为什么它会爆炸.md",
]

def build():
    parts = []

    # 封面信息
    parts.append("---")
    parts.append("title: 智能之冬与智能之春")
    parts.append("subtitle: 专家系统、互联网、大模型与 Agent 的四十年战争")
    parts.append("author: AI之书项目")
    parts.append("date: 2026-07")
    parts.append("lang: zh-CN")
    parts.append("---")
    parts.append("")

    # 版权页
    parts.append("# 版权页")
    parts.append("")
    parts.append("本书采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 许可协议。")
    parts.append("")
    parts.append("本书用多智能体协作工程化方法写成。详见 [GitHub 仓库](https://github.com/Wike-CHI/ai-winter-and-spring)。")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 目录（pandoc 生成 EPUB 时会自动生成，这里给 Markdown 版手动加）
    parts.append("# 目录")
    parts.append("")
    for ch in CHAPTERS:
        path = DIR_TEXT / ch
        if path.exists():
            first_line = path.read_text(encoding="utf-8").split("\n")[0]
            title = first_line.replace("# ", "").strip()
            parts.append(f"- {title}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 合并正文
    for ch in CHAPTERS:
        path = DIR_TEXT / ch
        if path.exists():
            text = path.read_text(encoding="utf-8")
            parts.append(text)
            parts.append("")
            parts.append("---")
            parts.append("")

    # 后记
    parts.append("# 后记：关于本书的写作方法")
    parts.append("")
    parts.append(textwrap_postscript())

    output = BASE / "读者版.md"
    output.write_text("\n".join(parts), encoding="utf-8")
    print(f"✅ 读者版 Markdown 已生成：{output}")
    print(f"   字数：约 {len(''.join(parts))} 字符")

    # 用 pandoc 生成 EPUB
    import subprocess
    epub_path = BASE / "智能之冬与智能之春.epub"
    result = subprocess.run(
        ["pandoc", str(output), "-o", str(epub_path),
         "--metadata", "title=智能之冬与智能之春",
         "--metadata", "author=AI之书项目",
         "--toc", "--toc-depth=2"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    if result.returncode == 0:
        print(f"✅ EPUB 已生成：{epub_path}")
    else:
        print(f"⚠️ EPUB 生成失败：{result.stderr[:200]}")

    # 用 pandoc 生成 HTML（可后续转 PDF）
    html_path = BASE / "读者版.html"
    result = subprocess.run(
        ["pandoc", str(output), "-o", str(html_path),
         "--standalone", "--toc", "--toc-depth=2",
         "--metadata", "title=智能之冬与智能之春"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    if result.returncode == 0:
        print(f"✅ HTML 已生成：{html_path}")
    else:
        print(f"⚠️ HTML 生成失败：{result.stderr[:200]}")


def textwrap_postscript():
    return """这本书不是"用 AI 辅助写作"——它是一套工程化的写作流水线。

每一章都经过六个角色的协作：

1. **Researcher**（史料核证）：并行联网检索，逐条核证人名、年份、数字、原话，产出史料卡片包。
2. **Writer**（起草）：基于已核证史料，按既定文风规范起草章节正文。
3. **Fact-Checker**（逐句核证）：扫描正文每个事实性断言，独立交叉验证，标注 ✅/⚠️/❌。
4. **Continuity Editor**（连贯性审查）：检查跨章一致性——第三章埋的伏笔是否在第九章精确呼应。
5. **Style Editor**（文风审查）：扫除 AI 腔（三段排比堆砌、形容词通胀、空洞升华）。
6. **Orchestrator**（编排）：全程调度，维护全局状态。

全部史料、对位台账、术语表、实验数据、回归测试，都开源在 GitHub 仓库中，可逐条复查、可复现。

讽刺且恰当地说：**我们用第十章的 Agent OS 思想（Project Memory、Verification、Knowledge Evolution），来写了一本论证第十章的书。**
"""


if __name__ == "__main__":
    build()
