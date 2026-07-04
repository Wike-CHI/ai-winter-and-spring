# Agent 边界实验：通用 vs 专用（DENDRAL 升级版）

> 本书第八章/第九章对位论证的一手当代实验证据。

## 这是什么

在写第八章「Agent 狂热」之前，我们**亲手跑了一个 agent 实验**，验证第三章诊断的三个专家系统病灶（规则爆炸 / 长程漂移 / 脆弱性）在 2026 年的 Agent 身上是否真实重演。

实验对比两个 agent：
- **Agent G（通用）**：通用工具（计算器、元素查询），对应今天的"通用 agent"范式
- **Agent D（DENDRAL 升级版）**：化学专用工具（质谱解析、官能团库、分子式推断、结构校验），对应专家系统"规则库"的当代化

## 核心发现（一句话版）

**专家系统的三个病灶全部在 Agent 身上重演，其中脆弱性（A4）进化成了更隐蔽的形态——LLM 会绕过工具校验层、靠预训练记忆伪装推理。**

详见 [实验报告.md](./实验报告.md)。

## 文件

| 文件 | 说明 |
|---|---|
| `tools_dendral.py` | DENDRAL 专用工具集 + 通用工具集（@tool 实现） |
| `agent_experiment.py` | 主脚本：Agent G/D 定义 + 3 个子实验 |
| `实验报告.md` | 结果分析 + 对位论证引用 |
| `exp1_result.json` | 子实验1原始数据（Prompt 爆炸） |
| `exp2_result.json` | 子实验2原始数据（长程漂移） |
| `exp3_result.json` | 子实验3原始数据（脆弱性） |

## 技术栈

- Python 3.13 + langchain 1.1 + langgraph 1.0
- LLM：GLM-5.2（智谱，OpenAI 兼容 API）
- Agent 构建：`langgraph.prebuilt.create_react_agent`

## 复现

```bash
pip install langchain langchain-openai langgraph

# 编辑 agent_experiment.py 填入你的 API key
python agent_experiment.py
```

或分别跑三个子实验（推荐，避免超时）：
```bash
python -c "
import sys; sys.path.insert(0,'.')
from agent_experiment import experiment_prompt_explosion
import json
json.dump(experiment_prompt_explosion(), open('exp1_result.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
"
```

## 诚实限定

本实验规模小（每 case 单次运行），模型单一，任务领域窄。它是"工程散文"式的实证，旨在可观察、可复现、能写进书里，而非学术论文级的严谨评测。三个对位病灶的可观察重演，足以支撑本书第八/九章的结构性论证。
