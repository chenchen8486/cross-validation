# Plan: 重构为 CLI `/cv` 轻量交叉验证命令（推广级）

## Context

当前工程 `cross_validation` 是一个多智能体博弈交叉验证框架，核心脚本为 `run_debate.py`。用户认为"必须手动运行 Python 脚本"的体验不佳，希望在 Claude Code CLI 中通过 `/cv` 命令直接触发交叉验证。

用户早期另有一套 `CVDebate` MCP + `/algo-*` Slash Commands 体系，现已决定弃用，要求彻底卸载并独立开发新的 `/cv`。

**核心诉求**：
- **全局可用**：`~/.claude/commands/cv.md`，在任何目录下都能调用。
- **轻量评审（默认）**：`/cv docs/design.md` 调用独立 API 做盲审，返回评审意见，由当前 CLI 会话决定是否修改。
- **定向盲审**：支持在 `/cv` 后追加明确指令，如 `/cv docs/design.md 重点审查第三章并发模型`。
- **底层隔离**：评审必须由未被污染的独立 API 完成，不能复用当前 Claude Code 上下文。
- **保留扩展性**：底层引擎仍保留完整多轮闭环能力，可作为 `--mode debate` 可选触发。
- **面向多开发者推广**：其他开发者只需 `pip install -e .` 即可在任意工程使用 `/cv`，配置通过用户级目录 `~/.cv-review/` 管理，零硬编码路径。

## 推荐方案概述

采用**"全局 Slash Command + 标准 Python 包 CLI"**架构：

1. **前端**：在 `~/.claude/commands/cv.md` 定义 `/cv` Slash Command。它负责解析用户输入、读取文件、调用全局 `cv-review` CLI、展示结果。
2. **后端**：将 `cross_validation` 重构为标准 Python 包，通过 `pyproject.toml` 注册全局 CLI 命令 `cv-review`。安装后任意目录均可调用。
3. **配置管理**：首次运行 `cv-review init` 在用户家目录生成 `~/.cv-review/`（内置默认模板），实现配置与代码分离，便于多开发者各自管理 API Key。
4. **清理**：彻底卸载旧 `CVDebate` MCP Server 及 `/algo-*` 命令。

此方案的优势：
- **推广零成本**：其他开发者 `git clone` + `pip install -e .` 即可使用，无需关心代码路径。
- **路径零硬编码**：`cv.md` 直接调用 `cv-review` 命令，不依赖任何绝对路径。
- **定向盲审**：支持用户在 `/cv` 后追加明确指令，实现精准评审。
- **上下文绝对隔离**：独立进程调用独立 API，与当前 Claude Code 会话物理隔离。
- **轻量模式下只走一次 API 调用**（评审员），响应快、成本低。

## 实施步骤

### Phase 1: 彻底清理旧 CVDebate 体系

1. **移除 MCP Server 配置**
   - 修改 `C:\Users\chenc\.claude\settings.json`：
     - 删除 `"mcpServers": { "CVDebate": ... }` 整个节点。
     - 删除 `permissions.allow` 中所有 `mcp__CVDebate__*` 条目。
   - 检查 `cv-debate-serve` 是否存在于 PATH，若存在则执行卸载（`pip uninstall cv-debate-serve` 或删除对应可执行文件）。

2. **移除旧 Slash Commands**
   - 删除 `C:\Users\chenc\.claude\commands\algo-question.md`
   - 删除 `C:\Users\chenc\.claude\commands\algo-talk.md`
   - 删除 `C:\Users\chenc\.claude\commands\algo-audit.md`
   - 删除 `C:\Users\chenc\.claude\commands\algo-list.md`

### Phase 2: 重构为推广级 Python 包

3. **新建 `pyproject.toml`（包定义）**
   - 定义包名 `cv-review`（或保留 `cross-validation`）。
   - 注册全局 CLI 入口：`[project.scripts] cv-review = "cv_review.cli:main"`。
   - 依赖：`openai>=1.0`。
   - 包含内置默认配置：`config/api_settings.json`、`config/prompts.txt` 作为包数据。

4. **新建 `src/cv_review/` 核心包**
   - `__init__.py`：版本号与包信息。
   - `cli.py`：`argparse` 主入口，支持：
     - `cv-review init`：在用户家目录生成 `~/.cv-review/`（复制内置默认配置模板）。
     - `cv-review --file <path> [--instruction "定向指令"]`：轻量盲审。
     - `cv-review --file <path> --mode debate [--rounds N]`：完整多轮闭环（可选）。
   - `config.py`：配置加载器，优先级：`~/.cv-review/` > 内置默认。支持跨平台路径（Windows `%USERPROFILE%\.cv-review\`，Linux/macOS `~/.cv-review/`）。
   - `api.py`：`init_api_client()` + `ask_agent()`，带完整 Type Hints、Docstring、日志与异常处理。
   - `reviewer.py`：评审逻辑，组装 prompt（支持追加用户定向指令）。

5. **保留并迁移 `run_debate.py`**
   - 逻辑拆分为 `cli.py` 的 `--mode debate` 子流程，或保留为 `cv_debate.py` 作为兼容入口。
   - 原 `load_prompts()` 和 `init_api_client()` 不再重复，统一调用 `config.py` 和 `api.py`。

6. **补齐项目规范**
   - 所有文件读写强制 `encoding="utf-8-sig"`。
   - 所有公共函数带 Type Hints 与 Google Style Docstring。
   - 使用 `logging` 分级记录，底层异常捕获后记录 traceback 再抛出。
   - 目录结构（推广版）：
     ```text
     cross_validation/               # 仓库根目录
     ├── pyproject.toml              # 包定义、CLI 入口、依赖
     ├── README.md                   # 安装指南、快速开始
     ├── src/
     │   └── cv_review/
     │       ├── __init__.py
     │       ├── cli.py              # argparse + 主入口
     │       ├── config.py           # 配置加载（~/.cv-review/ > 内置默认）
     │       ├── api.py              # OpenAI 客户端封装
     │       └── reviewer.py         # 评审逻辑（支持定向指令）
     ├── config/                     # 内置默认配置模板
     │   ├── api_settings.json
     │   └── prompts.txt
     ├── tests/
     │   └── test_config.py
     └── docs/                       # 设计文档（可选）
     ```

### Phase 3: 部署全局 `/cv` 命令

6. **新建 `~/.claude/commands/cv.md`**
   - Frontmatter：`description: 对指定文档调用独立 API 进行盲审交叉验证`
   - Prompt 流程：
     1. 解析 `$ARGUMENTS`，提取第一个看起来像文件路径的参数（支持相对路径与绝对路径），剩余文本作为**定向指令**。
     2. 调用 `Read(file_path=...)` 确认文件存在并获取内容（用于展示摘要给用户）。
     3. 调用 `Bash(command='cv-review --file "<绝对路径>" --instruction "<定向指令>"')` 执行盲审（若无可选指令则省略 `--instruction`）。
     4. 捕获 stdout，将独立 API 的评审意见完整展示给用户。
     5. 最后询问：「是否需要我根据以上盲审意见直接修改该文档？」若用户确认，当前 CLI 会话直接调用 `Edit` 工具修改文件。

### Phase 4: 验证与交付

7. **测试步骤**
   - **安装验证**：在全新目录执行 `pip install -e .`，确认 `cv-review` 命令已加入 PATH，且 `cv-review init` 能在用户家目录生成 `~/.cv-review/`。
   - **轻量评审**：在任意工程目录打开 Claude Code CLI，输入 `/cv docs/design.md`。
     - 期望：CLI 展示文档摘要 → Bash 调用 `cv-review` → 返回盲审意见 → 询问是否修改。
   - **定向盲审**：输入 `/cv docs/design.md 重点审查第三章并发模型设计的潜在竞态条件`。
     - 期望：评审意见聚焦第三章，而非全文泛泛而谈。
   - **完整闭环（可选）**：命令行执行 `cv-review --file docs/design.md --mode debate --rounds 2`。
     - 期望：走完整的多轮博弈流程，输出到 `outputs/DESIGN_DOCUMENT.md`。
   - **跨目录验证**：在 `cross_validation` 仓库之外任意目录使用 `/cv`，确认无需关心源码位置。

8. **回归验证**
   - 确认旧的 `/algo-question`、`/algo-talk` 等命令不再出现在 `/commands` 列表中。
   - 确认 `settings.json` 中无 `CVDebate` MCP 配置。
   - 确认旧 pip 包 `cv-debate-mcp` 已卸载：`pip show cv-debate-mcp` 应提示未安装。

## 关键文件变更清单

### 删除（旧体系清理）
- `C:\Users\chenc\.claude\commands\algo-question.md`
- `C:\Users\chenc\.claude\commands\algo-talk.md`
- `C:\Users\chenc\.claude\commands\algo-audit.md`
- `C:\Users\chenc\.claude\commands\algo-list.md`

### 修改
- `C:\Users\chenc\.claude\settings.json`：移除 `mcpServers.CVDebate` 及 `mcp__CVDebate__*` 权限条目。
- `D:\project\python_release\cross_validation\config\api_settings.json`：确认 `reviewer_channel` 指向用于盲审的独立模型。

### 新建
- `C:\Users\chenc\.claude\commands\cv.md`：全局 Slash Command 定义。
- `D:\project\python_release\cross_validation\pyproject.toml`：标准 Python 包定义，注册 `cv-review` CLI 入口。
- `D:\project\python_release\cross_validation\src\cv_review\__init__.py`
- `D:\project\python_release\cross_validation\src\cv_review\cli.py`：`argparse` 主入口，支持 `init`、`--file`、`--instruction`、`--mode`。
- `D:\project\python_release\cross_validation\src\cv_review\config.py`：配置加载（`~/.cv-review/` > 内置默认），跨平台兼容。
- `D:\project\python_release\cross_validation\src\cv_review\api.py`：OpenAI 客户端封装，带 Type Hints 与日志。
- `D:\project\python_release\cross_validation\src\cv_review\reviewer.py`：评审逻辑，支持定向指令拼接。
- `D:\project\python_release\cross_validation\tests\test_config.py`：单元测试。

### 保留/迁移
- `D:\project\python_release\cross_validation\run_debate.py`：逻辑拆分为 `cli.py` 的 `--mode debate` 子流程，或保留为兼容入口。

## 风险与注意事项

- **推广安装前提**：其他开发者需具备 Python 环境，并执行 `pip install -e .`。若目标用户无 Python 基础，后续可考虑打包为独立可执行文件（PyInstaller）。
- **API Key 环境变量**：`api_settings.json` 依赖 `MOONSHOT_API_KEY`、`DEEPSEEK_API_KEY` 等环境变量。`cv-review init` 生成的模板中会提示用户配置，但无法自动替用户写入系统环境变量。
- **旧 MCP 卸载**：旧包 `cv-debate-mcp` 需执行 `pip uninstall cv-debate-mcp` 才能彻底移除 `cv-debate-serve` 命令。
- **跨平台路径**：`~/.cv-review/` 在 Windows 下实际路径为 `%USERPROFILE%\.cv-review\`，需在 `config.py` 中用 `pathlib.Path.home()` 统一处理。
