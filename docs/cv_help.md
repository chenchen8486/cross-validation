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

## 示例

```bash
/cv docs/api-design.md
/cv src/core/auth.py 审查登录函数异常处理
/cv outputs/DESIGN_DOCUMENT.md

/cv_debate docs/requirement.md
/cv_debate docs/draft-design.md 重点关注高并发一致性
/cv_debate
```

## 关键参数

- `<文件路径>`：支持 `.md` `.txt` `.py`
- `[定向指令]`：追加关注点。推荐"重点审查第三章并发安全"
- `--rounds N`：迭代轮数，默认 2
- `--output`：输出目录，默认 `outputs/`

## 输出

- `/cv`：评审意见直接显示在对话中
- `/cv_debate`：最终结果保存到 `outputs/DESIGN_DOCUMENT.md`

## 前置配置

```bash
pip install -e .
cv-review init
export DEEPSEEK_API_KEY="sk-xxx"
export KIMI_API_KEY="sk-xxx"
```

路径提示：Windows 建议用正斜杠 `/`。
