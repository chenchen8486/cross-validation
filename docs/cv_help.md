---
name: cv_help
description: 显示 /cv 命令的完整用法、参数说明、路径格式提示与前置配置检查清单。
---

# 📋 /cv — 独立 API 盲审交叉验证工具

通过外部独立 API（如 DeepSeek / Kimi）对技术文档进行盲审，评审结果与当前 Claude Code 会话物理隔离，解决单一 AI 模型长期使用导致的记忆刷退货与注意力分散问题，实现真正的交叉验证。

## 🎯 核心目标

通过独立 API 对技术文档进行盲审，解决单一 AI 模型长期使用导致的记忆刷退货与注意力分散问题，实现真正的交叉验证。

## 📖 用法

| 命令 | 说明 |
| :--- | :--- |
| `/cv <文件路径> [定向指令]` | 轻量盲审（最常用，1 次 API 调用） |
| `/cv debate [<文件路径>] [定向指令]` | 多轮闭环博弈（交互向导，自动写+改） |
| `/cv_debate [<文件路径>] [定向指令]` | 多轮闭环博弈的快捷方式 |
| `/cv_help` | 显示此帮助 |
| `/cv help` | 同 `/cv_help` |

## 📂 文件路径格式说明

- **相对路径**：`docs/design.md`
- **Windows 绝对路径**：`D:/project/docs/design.md` 或 `D:\project\docs\design.md`
- **Linux / macOS 绝对路径**：`/home/user/docs/design.md`
- 支持 `.md` / `.txt` / `.py` 等纯文本文件

> 💡 **提示**：Windows 用户建议统一使用正斜杠 `/` 以避免转义问题。

## 📝 参数说明

- **`<文件路径>`**：待评审或博弈的文档路径（必填）
- **`[定向指令]`**：可选。如"重点审查第三章并发安全"，追加到评审 Prompt 中，避免泛泛而谈

## 💡 典型示例

```bash
/cv docs/api-design.md
/cv docs/api-design.md 重点审查认证模块时序漏洞
/cv src/core/auth.py 审查登录函数的异常处理
/cv debate docs/requirement.md
/cv_debate docs/requirement.md
/cv_help
```

## ⚙️ 前置配置（首次使用必做）

1. `pip install -e .`（安装 cv-review 包）
2. `cv-review init`（生成 `~/.cv-review/` 配置目录）
3. 配置环境变量 `DEEPSEEK_API_KEY` / `KIMI_API_KEY`

## 🔄 两种模式对比

| 维度 | 轻量盲审（默认） | 多轮闭环博弈（debate / cv_debate） |
| :--- | :--- | :--- |
| **输入** | 已有文档，找人挑错 | 只有需求，让 AI 自动写+改 |
| **API 调用** | 1 次 reviewer | 1 + 2×N 次 |
| **输出** | 评审意见文本 | 完整设计文档 |
| **特点** | 成本低、响应快 | 成本较高、质量更高 |
