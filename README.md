# cv-review: 基于独立 API 盲审的文档交叉验证 CLI 工具

在复杂软件系统架构设计、算法推演以及技术方案制定过程中，设计文档的严谨性直接决定后续工程的成败。然而，传统的单会话 AI 辅助工具存在**思维定势、用户谄媚以及长文本注意力分散**等缺陷。

**cv-review** 通过引入**"同行评审（Peer Review）"**机制，在**完全物理隔离的独立进程**中调用未被污染的外部大模型 API，对指定文档进行盲审交叉验证，从而逼近更优的设计质量。

同时提供 **Claude Code CLI 全局 Slash Command `/cv`**，支持在任意工程目录下对任意 Markdown 文档进行轻量或深度评审，无需关心源码位置。

---

## 1. 为什么需要交叉验证？

假设你刚写完一份《用户登录系统技术设计文档》，核心内容如下：

```markdown
## 登录系统设计

### 身份认证
- 使用 JWT Token，过期时间 2 小时

### 会话存储
- 使用 Redis 缓存 Token

### 安全防护
- 接口限流：每秒最多 100 次请求
- 密码传输使用 HTTPS
```

你检查了两遍，觉得逻辑自洽、考虑周全，准备提交评审。

然后你执行了：

```bash
/cv docs/login-design.md
```

一分钟后，独立 API 的盲审意见返回了——

### 校验前 vs 校验后

| 文档原文（校验前） | 盲审发现（校验后） |
| :--- | :--- |
| "JWT Token 过期时间 2 小时，安全性高" | ❌ **Token 刷新机制缺失**：2 小时后用户被强制登出，体验断裂；文档完全未说明如何无感知续期 |
| "使用 Redis 缓存 Token，性能好" | ❌ **缓存未设 TTL**：过期 Token 永不删除，内存持续增长，最终 OOM |
| "接口限流，每秒 100 次请求" | ❌ **限流粒度太粗**：只限接口级别，同一 IP 可无限次尝试不同账号密码，存在暴力破解风险 |
| "密码传输使用 HTTPS，安全可靠" | ❌ **密码错误次数无锁定**：攻击者可无限次猜测密码，HTTPS 只防窃听不防爆破 |

你愣住了。这些问题你在写文档时**完全没意识到**——因为它们都是你"觉得自己考虑到了"的盲区。

**修正后的文档应该补充**：
- Token 自动续期策略（Refresh Token 或滑动过期）
- Redis Key 的 TTL 设置与过期清理机制
- IP 级别的登录失败锁定（如 5 次错误锁定 15 分钟）
- 账户级别的异常登录告警

这就是交叉验证的核心价值：**你对自己的设计永远有盲区，而独立的、未被污染的评审者没有**。cv-review 把这个"第二双眼睛"变成了可复用的工具。

---

## 2. 快速开始

```bash
git clone https://github.com/your-org/cv-review.git
cd cv-review
pip install -e .
cv-review init
cv-review --file README.md
```

---

## 3. 安装指南

### 3.1 环境要求

- Python >= 3.10
- 推荐使用虚拟环境（conda / venv）

### 3.2 安装包

```bash
git clone <仓库地址>
cd cv-review
pip install -e .
```

安装完成后，全局 `cv-review` 命令即加入 PATH，任意目录均可调用。

### 3.3 初始化配置

```bash
cv-review init
```

首次运行会在用户家目录生成 `~/.cv-review/`，包含默认的 `api_settings.json` 与 `prompts.txt` 模板。

> **注意**：`cv-review init` 命令不会覆盖你已存在的配置文件，放心执行。

### 3.4 API Key 配置

本工具依赖两个独立的外部 API 通道（architect 与 reviewer），你需要分别配置对应的环境变量。

**Windows（持久化到用户环境变量）**：

```powershell
# PowerShell
[Environment]::SetEnvironmentVariable('KIMI_API_KEY', 'sk-你的-Kimi-Key', 'User')
[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY', 'sk-你的-DeepSeek-Key', 'User')
```

配置完成后，**重新打开终端**使变量生效。验证：

```bash
echo $KIMI_API_KEY
echo $DEEPSEEK_API_KEY
```

**macOS / Linux（持久化到 shell 配置文件）**：

```bash
echo 'export KIMI_API_KEY="sk-你的-Kimi-Key"' >> ~/.bashrc
echo 'export DEEPSEEK_API_KEY="sk-你的-DeepSeek-Key"' >> ~/.bashrc
source ~/.bashrc
```

### 3.5 支持的 API 通道

默认内置配置支持以下通道（可在 `~/.cv-review/api_settings.json` 中自定义）：

| 通道 | 基础地址 | 环境变量 | 默认模型 |
| :--- | :--- | :--- | :--- |
| Kimi | `https://api.kimi.com/coding/` | `KIMI_API_KEY` | `kimi-k2.6` |
| DeepSeek | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | `deepseek-chat` |

如需接入其他模型（OpenAI、Claude、GLM 等），直接在配置文件中新增通道即可。

### 3.6 Claude Code CLI 集成（推荐使用）

将 `/cv` 命令部署到 Claude Code：

```bash
# 所有平台通用（Windows Git Bash / WSL / macOS / Linux）
mkdir -p ~/.claude/commands
cp docs/cv.md ~/.claude/commands/
```

> **Windows CMD 用户**：若使用原生 CMD，请将 `~` 替换为 `%USERPROFILE%`，将 `cp` 替换为 `copy`。

重启 Claude Code CLI 后，输入 `/cv` 即可使用。

---

## 4. 使用指南

### 4.1 在 Claude Code 中使用 `/cv`（推荐使用）

在任意工程目录打开 Claude Code，输入：

```bash
# 轻量评审
/cv docs/api-design.md

# 定向评审（聚焦特定章节或维度）
/cv docs/api-design.md 重点审查认证模块的时序漏洞
```

`/cv` 是 Claude Code 的前端集成，底层仍调用同一个 `cv-review`，但会额外提供**"评审 → 询问是否修改 → 直接 Edit 改文件"**的交互闭环。这是**日常开发中最推荐的使用方式**。

### 4.2 `cv-review` 独立 CLI（适合脚本与 CI）

如果你只想快速看评审意见，或需要在 CI 流水线中集成：

```bash
# 轻量盲审（默认，只调用 reviewer，成本最低）
cv-review --file docs/design.md

# 定向盲审
# 通过 --instruction 追加关注点，避免泛泛而谈
cv-review --file docs/design.md \
  --instruction "请逐条分析第三章中所有并发模型的潜在竞态条件与死锁风险"
```

> **常用参数**：
> - `cv-review --help`（或 `-h`）：查看全部命令与参数说明。
> - `cv-review --file README.md -v`：启用详细日志，查看 API 调用过程与调试信息。
>
> **适用场景**：任何终端（bash / zsh / PowerShell）均可直接使用，**不依赖 Claude Code**。输出评审意见到 stdout 后即结束。

### 4.3 完整多轮闭环博弈（`--mode debate`）

```bash
cv-review --file docs/requirement.md --mode debate --rounds 3 --output outputs/
```

`--mode debate` 启用 architect + reviewer 双通道交替迭代：
1. architect 根据输入出初稿
2. reviewer 盲审并指出漏洞
3. architect 根据意见修复
4. 循环 `--rounds` 轮后输出最终文档到 `outputs/DESIGN_DOCUMENT.md`

> **成本提示**：`--mode debate --rounds 3` 约消耗 6 次 API 调用。以 5000 tokens 文档为例，总消耗约 42,000 tokens（约 $3~5）。建议根据文档长度和预算调整轮数。

---

## 5. 目录结构

```text
cv-review/                      # 仓库根目录
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

## 6. 架构与调用流程

### 6.1 轻量盲审模式

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

### 6.2 完整多轮闭环模式

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

### 6.3 `/cv` Slash Command 调用链

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

## 7. 关键设计决策

### 7.1 为什么使用独立进程 + 独立 API？

- **物理隔离**：`cv-review` 运行在独立 Python 进程中，每次请求只传递 system prompt + 当前文档，不携带 Claude Code 会话的任何历史上下文。
- **盲审真实**：Reviewer 完全不知道作者是谁、也不知道当前对话的主题，只能基于文档本身进行批判。
- **成本可控**：轻量模式只调用一次 reviewer，响应快、Token 消耗最低。

### 7.2 为什么配置放在 `~/.cv-review/`？

- **多开发者推广**：每个开发者只需配置一次自己的 API Key，不受源码仓库路径限制。
- **版本隔离**：通过 `pip install --upgrade` 升级包时，不会覆盖 `~/.cv-review/` 中的个人配置。
- **跨平台**：Windows / macOS / Linux 均通过 `Path.home()` 自动定位。

### 7.3 为什么使用标准 Python 包而非脚本？

- `pip install -e .` 即可全局使用 `cv-review` 命令。
- 内置默认模板随包分发，`cv-review init` 后立即可用。
- 其他开发者无需关心源码被 clone 到了哪个目录。

---

## 8. 变更记录

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
