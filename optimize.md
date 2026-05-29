# cv-review 优化建议跟踪

> **来源**：DeepSeek 独立 API 盲审生成  
> **评审对象**：README.md + 工程实现（v0.2.0）  
> **更新时间**：2026-05-29

---

## 评估结论

经代码核实，18 条建议中 **4 条为 P0（必须修复）**，**4 条为 P1（强烈建议）**，其余为 P2 或基于错误假设，当前阶段不修改。

---

## P0 — 必须修复

- [x] **6. API 调用无重试/超时**  
  `api.py:ask_agent()` 裸 try-except，网络抖动或 429 直接导致崩溃。  
  **修复**：引入 `tenacity` 实现指数退避重试（3 次），超时 60s。

- [x] **7. 配置文件无字段验证**  
  `load_api_settings()` 返回 raw dict，不校验 `channels` / `runtime_routing` 结构。  
  **修复**：返回前检查必填字段存在且类型正确。

- [x] **5. 空文件/非 Markdown 未检查**  
  `reviewer.py` 读取文件后未检查内容是否为空。  
  **修复**：`review()` / `debate()` 增加空内容校验，非 `.md` 给出警告。

- [x] **13. README 逻辑矛盾**  
  2.3（init 不覆盖）与 7.2（升级不覆盖）表述混淆，实为两个不同行为。  
  **修复**：明确区分 "`init` 命令行为" 与 "pip 升级行为"。

---

## P1 — 强烈建议

- [x] **3. debate 模式成本未说明**  
  `--mode debate --rounds 3` 约 6 次 API 调用，5000 tokens 文档约耗 42,000 tokens（$3~5）。  
  **修复**：README 使用示例旁补充成本提示。

- [x] **9. 缺乏 JSON 输出格式**  
  当前仅输出 Markdown，CI 无法解析。  
  **修复**：`cli.py` 增加 `--output-format {markdown,json}`。

- [x] **16. README 未提及 `-v` / `-h`**  
  `--verbose` 已存在但文档未介绍；`-h` 为 argparse 默认行为，同样未提及。  
  **修复**：在使用指南中补充 `-v`（详细日志）与 `-h`（帮助）说明。

- [x] **17. 测试覆盖不足**  
  仅 `test_config.py`，未覆盖 API 调用与 reviewer 逻辑。  
  **修复**：新增 `tests/test_api.py`（mock 重试逻辑）、`tests/test_reviewer.py`（空文件检查）。

---

## P2 — 后续优化（当前非刚需）

| 序号 | 问题 | 延后理由 |
| :--- | :--- | :--- |
| 1, 2 | 核心悖论（自我指涉、评审者污染） | 哲学讨论，可在 FAQ 中补充，非代码修改 |
| 4 | 大文档分块评审 | 实现复杂，需改动 prompt 组装，待有真实需求 |
| 8 | API 适配器抽象 | 当前仅 OpenAI 兼容格式，抽象收益有限 |
| 10 | 插件系统 | 过于宏大，当前阶段不需要 |
| 12 | 文档脱敏 | 有价值，但敏感信息识别需复杂正则/NLP |
| 14 | 版本迁移路径 | 当前 v0.2.0 为首个推广版，无历史迁移负担 |
| 18 | FAQ / CONTRIBUTING | 用户量尚小，待社区成型后补充 |

---

## 不修改（基于错误假设或不成立）

- **11. API Key 泄露**：`init` 生成的模板中**只有环境变量名，不含实际 Key**，指责不成立。
- **15. 安装流程冗余**：2.2（详细安装）与 3.2（快速开始）是 README 标准结构，不构成冗余。

---

## 变更文件清单（预计）

### 修改
- `pyproject.toml` — 新增 `tenacity` 依赖
- `src/cv_review/api.py` — 重试装饰器 + 超时
- `src/cv_review/config.py` — 配置结构校验
- `src/cv_review/reviewer.py` — 空文件检查 + `output_format`
- `src/cv_review/cli.py` — `--output-format` 参数
- `README.md` — 修正矛盾、补充成本提示、补充 `-v` / `-h` 说明

### 新建
- `tests/test_api.py` — mock 测试重试逻辑
- `tests/test_reviewer.py` — 空文件与格式测试
