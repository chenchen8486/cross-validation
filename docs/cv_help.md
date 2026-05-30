---
name: cv_help
description: 显示 /cv 命令的完整用法、参数说明、路径格式提示与前置配置检查清单。
---

请将以下内容原样输出给用户（不要总结，不要改写，不要包裹在代码块中，保持 Markdown 格式）：

# /cv 命令使用指南

通过独立 API 盲审技术文档，解决单模型长期运行的幻觉与注意力衰退问题。

## 场景速查

| 你想做什么                                 | 命令 |
|:--------------------------------------| :--- |
| 已有文档，单独调用一次没有任何记忆的API模型进行交叉验证，让结果得到最优 | `/cv <文件> [指令]` |
| 使用内部自动的回合制，自动反复校验生成最终最优的结论            | `/cv_debate <文件> [指令]` |
| 直接说出需求，让系统自己扫描工程文件并交叉验证（智能意图）        | `/cv <自然语言请求>` |

## 示例

```bash
# 轻量盲审（指定文件）
/cv docs/api-design.md
/cv src/core/auth.py 审查登录函数异常处理
/cv outputs/DESIGN_DOCUMENT.md

# 智能意图（不指定文件，系统自动扫描）
/cv 你帮我校验当前工程的代码合理吗
/cv 检查一下这个项目的架构设计有没有漏洞
/cv 看看这个工程的异常处理是否完善

# 多轮闭环博弈
/cv_debate docs/requirement.md
/cv_debate docs/draft-design.md 重点关注高并发一致性
/cv_debate
```

## 关键参数

- `<文件路径>`：支持 `.md` `.txt` `.py` 等常见文本文件
- `<自然语言请求>`：直接描述你想检查什么，系统自动扫描工程文件
- `[定向指令]`：追加关注点。推荐"重点审查第三章并发安全"
- `--rounds N`：迭代轮数，默认 2（仅 `/cv_debate`）
- `--output`：输出目录，默认 `outputs/`（仅 `/cv_debate`）

## 路径格式说明（跨平台兼容）

`/cv` 支持所有常见路径格式，底层会自动处理：

| 格式 | 示例 | 说明 |
| :--- | :--- | :--- |
| 相对路径 | `docs/design.md` | 基于当前工程目录解析 |
| Windows 正斜杠 | `D:/project/docs/design.md` | 推荐，避免转义问题 |
| Windows 反斜杠 | `D:\project\docs\design.md` | 支持，双引号包裹后安全传递 |
| Windows 混合斜杠 | `D:/project\docs/design.md` | 支持，pathlib 自动标准化 |
| Windows 盘符（大小写不敏感） | `c:/project/docs.md` / `C:\project\docs.md` | 支持 |
| Linux / macOS | `/home/user/docs/design.md` | 原生支持 |
| 当前目录 | `./config.py` / `.gitignore` | 支持 |
| 上级目录 | `../shared/utils.py` | 支持 |

> 如果路径不存在，`/cv` 会明确提示错误原因，并请求重新输入。

## 输出

- `/cv`：评审意见直接显示在对话中
- `/cv_debate`：最终结果保存到 `outputs/DESIGN_DOCUMENT.md`

## 智能意图模式说明

当你不指定文件路径，而是直接输入自然语言时（如 `/cv 帮我检查代码合理性`），`/cv` 会自动：

1. 识别你的意图（关注代码、文档还是全面检查）
2. 扫描工程中的相关文件（自动排除测试、缓存、依赖目录）
3. 将文件内容聚合成临时文档
4. 调用独立 API 进行盲审

**注意**：智能意图模式扫描的文件数上限为 10 个，聚合内容上限约 80KB，以保证 API 调用效率。如需深度审查单个文件，请直接指定文件路径。

## 前置配置

```bash
pip install -e .
cv-review init
export DEEPSEEK_API_KEY="sk-xxx"
export KIMI_API_KEY="sk-xxx"
```

路径提示：Windows 建议用正斜杠 `/`。
