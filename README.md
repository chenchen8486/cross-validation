# cv-review: 基于独立 API 盲审的文档交叉验证 CLI 工具

## 1. 核心目标

在复杂软件系统架构设计、算法推演以及技术方案制定过程中，设计文档的严谨性直接决定后续工程的成败。然而，传统的单会话 AI 辅助工具存在**思维定势、用户谄媚以及长文本注意力分散**等缺陷。

**cv-review** 通过引入**"同行评审（Peer Review）"**机制，在**完全物理隔离的独立进程**中调用未被污染的外部大模型 API，对指定文档进行盲审交叉验证，从而逼近更优的设计质量。

同时，本工具提供 **Claude Code CLI 全局 Slash Command `/cv`**，支持在任意工程目录下对任意 Markdown 文档进行轻量或深度评审，无需关心源码位置。

---

## 2. 环境配置

### 2.1 Python 环境

- Python >= 3.10
- 推荐使用虚拟环境（conda / venv）

### 2.2 API Key 配置

本工具依赖两个独立的外部 API 通道（ architect 与 reviewer ），你需要分别配置对应的环境变量。

**Windows 用户（持久化环境变量）**：

```powershell
# PowerShell 管理员
[Environment]::SetEnvironmentVariable('KIMI_API_KEY', 'sk-你的-Kimi-Key', 'User')
[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY', 'sk-你的-DeepSeek-Key', 'User')
```

配置完成后，**重新打开终端**使变量生效。验证：

```bash
echo $KIMI_API_KEY
echo $DEEPSEEK_API_KEY
```

**macOS / Linux 用户（持久化到 ~/.bashrc 或 ~/.zshrc）**：

```bash
echo 'export KIMI_API_KEY="sk-你的-Kimi-Key"' >> ~/.bashrc
echo 'export DEEPSEEK_API_KEY="sk-你的-DeepSeek-Key"' >> ~/.bashrc
source ~/.bashrc
```

### 2.3 支持的 API 通道

默认内置配置支持以下通道（可在 `~/.cv-review/api_settings.json` 中自定义）：

| 通道 | 基础地址 | 环境变量 | 默认模型 |
| :--- | :--- | :--- | :--- |
| Kimi | `https://api.kimi.com/coding/` | `KIMI_API_KEY` | `kimi-k2.6` |
| DeepSeek | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | `deepseek-chat` |

如需接入其他模型（OpenAI、Claude、GLM 等），直接在配置文件中新增通道即可。

---

## 3. 快速启动

### 3.1 安装

```bash
git clone https://github.com/your-org/cv-review.git
cd cv-review
pip install -e .
```

安装完成后，全局 `cv-review` 命令即加入 PATH，任意目录均可调用。

### 3.2 初始化配置

```bash
cv-review init
```

首次运行会在用户家目录生成 `~/.cv-review/`，包含默认的 `api_settings.json` 与 `prompts.txt` 模板。

**注意**：`init` 不会覆盖你已存在的配置文件，放心执行。

### 3.3 执行盲审

```bash
# 轻量盲审（默认，只调用 reviewer，成本最低）
cv-review --file docs/design.md

# 定向盲审（聚焦特定章节或维度）
cv-review --file docs/design.md --instruction "重点审查第三章并发模型的竞态条件"

# 完整多轮闭环博弈（architect + reviewer 交替迭代）
cv-review --file docs/design.md --mode debate --rounds 2
```

### 3.4 在 Claude Code CLI 中使用 `/cv`

在任意工程目录打开 Claude Code，输入：

```bash
/cv docs/design.md
/cv docs/design.md 重点审查第三章并发模型
```

底层会自动调用独立 API 执行盲审，评审意见在当前 CLI 会话中完整展示，随后询问是否根据意见修改文档。

---

## 4. 目录结构

```text
cross_validation/               # 仓库根目录
├── pyproject.toml              # 标准 Python 包定义，注册 cv-review CLI 入口
├── README.md                   # 本文档
├── .gitignore                  # Git 忽略规则
├── src/
│   └── cv_review/              # 主包
│       ├── __init__.py
│       ├── cli.py              # argparse 主入口（init / review / debate）
│       ├── config.py           # 配置加载器（~/.cv-review/ > 内置默认）
│       ├── api.py              # OpenAI 兼容客户端封装
│       ├── reviewer.py         # 评审逻辑（轻量盲审 + 多轮闭环）
│       └── config/             # 内置默认配置模板
│           ├── api_settings.json
│           └── prompts.txt
├── tests/
│   └── test_config.py          # 单元测试（配置加载与路径优先级）
└── docs/
    └── plan.md                 # 重构计划文档
```

---

## 5. 程序框架与调用流程

### 5.1 轻量盲审模式（默认）

```
用户输入
  │
  ▼
cv-review --file <path> [--instruction "xxx"]
  │
  ├─→ config.py 加载 api_settings.json + prompts.txt
  │       （优先级：~/.cv-review/ > 包内默认）
  │
  ├─→ reviewer.py 读取文件内容
  │       组装 user_prompt = 文件内容 + 定向指令
  │
  ├─→ api.py 初始化 reviewer 通道客户端
  │       （独立 API，与当前 CLI 上下文物理隔离）
  │
  └─→ reviewer.py 调用 ask_agent()
          单次无状态调用，不携带任何历史上下文
          返回 Markdown 评审意见到 stdout
```

### 5.2 完整多轮闭环模式（`--mode debate`）

```
用户输入
  │
  ▼
cv-review --file <path> --mode debate --rounds N
  │
  ├─→ 初始化 architect + reviewer 双通道客户端
  │
  ├─→ 第 1 轮：architect 出初稿
  │
  ├─→ 第 1~N 轮循环：
  │       reviewer 盲审 → 指出漏洞
  │       architect 修复 → 输出新版文档
  │
  └─→ 输出最终文档到 outputs/DESIGN_DOCUMENT.md
```

### 5.3 `/cv` Slash Command 调用链

```
Claude Code CLI
  │
  ├─→ /cv docs/design.md [定向指令]
  │       解析 $ARGUMENTS 提取文件路径与指令
  │
  ├─→ Bash: cv-review --file <路径> [--instruction <指令>]
  │       独立进程调用，与 Claude 当前会话完全隔离
  │
  └─→ 展示评审意见 → 询问是否修改 → Edit 工具修改文档
```

---

## 6. 安装指南（面向多开发者推广）

### 6.1 开发者安装

```bash
git clone <仓库地址>
cd cv-review
pip install -e .
cv-review init
```

### 6.2 环境变量配置

参见本文档 **2.2 API Key 配置** 章节。

### 6.3 Claude Code CLI 集成

将 `cv.md` 复制到用户级命令目录：

```bash
# Windows
mkdir %USERPROFILE%\.claude\commands
copy docs\cv.md %USERPROFILE%\.claude\commands\

# macOS / Linux
mkdir -p ~/.claude/commands
cp docs/cv.md ~/.claude/commands/
```

重启 Claude Code CLI 后，输入 `/cv` 即可使用。

---

## 7. 使用示例

### 7.1 对当前目录的 README 进行盲审

```bash
cv-review --file README.md
```

### 7.2 定向盲审：聚焦并发安全

```bash
cv-review --file docs/architecture.md --instruction "请逐条分析第三章中所有并发模型的潜在竞态条件与死锁风险"
```

### 7.3 完整闭环：对需求文档进行 3 轮博弈

```bash
cv-review --file docs/requirement.md --mode debate --rounds 3 --output outputs/
```

### 7.4 在 Claude Code 中快速调用

```bash
# 轻量评审
/cv docs/api-design.md

# 定向评审
/cv docs/api-design.md 重点审查认证模块的时序漏洞

# 评审后让 Claude 直接修改
# （CLI 会询问：是否需要根据以上盲审意见直接修改该文档？）
```

---

## 8. 关键设计决策

### 8.1 为什么使用独立进程 + 独立 API？

- **物理隔离**：`cv-review` 运行在独立 Python 进程中，每次请求只传递 system prompt + 当前文档，不携带 Claude Code 会话的任何历史上下文。
- **盲审真实**：Reviewer 完全不知道作者是谁、也不知道当前对话的主题，只能基于文档本身进行批判。
- **成本可控**：轻量模式只调用一次 reviewer，响应快、Token 消耗最低。

### 8.2 为什么配置放在 `~/.cv-review/`？

- **多开发者推广**：每个开发者只需配置一次自己的 API Key，不受源码仓库路径限制。
- **版本隔离**：升级包时不会覆盖个人配置。
- **跨平台**：Windows / macOS / Linux 均通过 `Path.home()` 自动定位。

### 8.3 为什么使用标准 Python 包而非脚本？

- `pip install -e .` 即可全局使用 `cv-review` 命令。
- 内置默认模板随包分发，`cv-review init` 后立即可用。
- 其他开发者无需关心源码被 clone 到了哪个目录。

---

## 9. 变更记录

### 2026-05-29 v0.2.0 推广级重构

- **架构升级**：从手动运行 `python run_debate.py` 升级为全局 CLI 命令 `cv-review`。
- **包化重构**：工程重构为标准 Python 包（`pyproject.toml` + `src/cv_review/`）。
- **配置解耦**：支持用户级 `~/.cv-review/` 与内置默认模板的层级覆盖。
- **定向盲审**：新增 `--instruction` 参数，支持聚焦特定章节的精准评审。
- **Claude Code 集成**：新增全局 `/cv` Slash Command，任意目录可用。
- **旧体系清理**：彻底卸载 CVDebate MCP Server 及 `/algo-*` 命令。
- **单元测试**：新增 `tests/test_config.py`，覆盖配置加载与路径优先级。
- **Windows 编码修复**：解决终端中文乱码问题。

### 早期版本

- v0.1.0：初代多智能体博弈框架（`run_debate.py`），由 GEMINI 编写。
