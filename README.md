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

将 `/cv` 系列命令部署到 Claude Code：

```bash
# 所有平台通用（Windows Git Bash / WSL / macOS / Linux）
mkdir -p ~/.claude/commands
cp docs/cv.md docs/cv-help.md docs/cv-debate.md ~/.claude/commands/
```

> **Windows CMD 用户**：若使用原生 CMD，请将 `~` 替换为 `%USERPROFILE%`，将 `cp` 替换为 `copy`：
> ```cmd
> copy "docs\cv.md" "%USERPROFILE%\.claude\commands\"
> copy "docs\cv-help.md" "%USERPROFILE%\.claude\commands\"
> copy "docs\cv-debate.md" "%USERPROFILE%\.claude\commands\"
> ```

重启 Claude Code CLI 后，输入 `/` 即可看到 `/cv`、`/cv-help`、`/cv-debate` 三个命令。

---

## 4. 使用模式大全

### 4.1 Claude Code 中 `/cv` 的所有用法（推荐日常开发）

`/cv` 是 Claude Code CLI 的**全局 Slash Command**，安装后可在任意工程目录使用。它的核心价值是提供**"评审 → 询问是否修改 → 直接 Edit 改文件"**的交互闭环。

#### 模式 A：轻量盲审（最常用）

```bash
/cv docs/api-design.md
```

- 对指定文档执行一次独立 API 盲审。
- 评审结果直接打印在当前对话窗口，主 Claude 可基于结果与你讨论修改方案。

#### 模式 B：定向评审（精准聚焦）

```bash
# 聚焦特定章节
/cv docs/api-design.md 重点审查第三章中所有并发模型的竞态条件与死锁风险

# 聚焦安全维度
/cv docs/auth-design.md 请从零信任架构角度审查身份认证流程的漏洞

# 聚焦性能维度
/cv docs/db-design.md 重点分析缓存穿透、缓存击穿与缓存雪崩的防护策略是否完备
```

- 第二个参数起所有内容都会被作为**定向指令**追加到评审 Prompt 中。
- 避免泛泛而谈，让评审意见直击你真正关心的盲区。

#### 模式 C：评审代码文件

```bash
/cv src/core/auth.py 审查登录函数的异常处理与边界条件
/cv src/utils/cache.py 检查 Redis 连接池配置是否合理
```

- `/cv` 不仅支持 `.md`，也支持 `.py`、`.txt` 等任何纯文本文件。
- 对代码的评审同样保持物理隔离与盲审原则。

#### 模式 D：多轮闭环博弈（深度生成）

```bash
/cv debate docs/requirement.md
```

- 进入**交互式向导**，Claude 会依次询问：迭代轮数、输出目录、定向关注点。
- 系统自动调用 `architect + reviewer` 双通道进行多轮博弈，最终输出完整设计文档。
- 全程只需回答几个问题，无需记忆任何 CLI 参数。

#### 模式 E：查看帮助

```bash
/cv help
```

- 展示 `/cv` 的完整用法、参数说明、路径格式提示与前置配置检查清单。
- 不确定怎么用时，随时输入 `/cv help`。
- 也可直接输入 `/cv`（无参数），会自动进入帮助模式。

#### 模式 F：快捷进入 Debate 模式

```bash
/cv-debate docs/requirement.md
```

- `/cv-debate` 是 `/cv debate` 的快捷命令，功能完全一致。
- 在 Claude Code 的命令菜单中直接可见，无需记忆参数。

#### 路径兼容性说明

`/cv` 支持所有常见路径格式，底层会自动处理：

| 平台 | 示例路径 | 说明 |
| :--- | :--- | :--- |
| 相对路径 | `docs/design.md` | 基于当前工程目录解析 |
| Windows 正斜杠 | `D:/project/docs/design.md` | ✅ 推荐，避免转义问题 |
| Windows 反斜杠 | `D:\project\docs\design.md` | ✅ 支持，双引号包裹后安全传递 |
| Linux / macOS | `/home/user/docs/design.md` | ✅ 原生支持 |

> 💡 **建议**：Windows 用户优先使用正斜杠 `/`，可减少因 Shell 转义导致的路径解析问题。
> 如果路径不存在，`/cv` 会明确提示错误原因，并请求重新输入。

---

### 4.2 `cv-review` CLI 完整参数手册

`cv-review` 是底层引擎，不依赖 Claude Code，任何终端均可调用。

#### 子命令

| 命令 | 说明 |
| :--- | :--- |
| `cv-review init` | 初始化用户级配置目录 `~/.cv-review/`，复制默认模板 |
| `cv-review init --force` | 强制覆盖已有配置文件（慎用） |

#### 主命令参数（评审相关）

| 短参 | 长参 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `-f` | `--file` | （必填） | 待评审或博弈的文档路径 |
| `-i` | `--instruction` | `None` | 定向评审指令，如 `"重点审查第三章并发模型"` |
| `-m` | `--mode` | `review` | 评审模式：`review`（轻量盲审）或 `debate`（多轮闭环） |
| `-r` | `--rounds` | `2` | `debate` 模式下的迭代轮数 |
| `-o` | `--output` | `outputs` | `debate` 模式下输出目录 |
| | `--output-format` | `markdown` | 输出格式：`markdown`（默认）或 `json` |
| `-v` | `--verbose` | `False` | 启用 DEBUG 级别日志，查看完整 API 调用过程 |
| `-h` | `--help` | — | 显示帮助信息并退出 |

#### 常用组合示例

```bash
# 1. 最简用法：轻量盲审
cv-review --file docs/design.md

# 2. 定向盲审
cv-review --file docs/design.md \
  --instruction "请逐条分析第三章中所有并发模型的潜在竞态条件与死锁风险"

# 3. 调试模式：看 API 到底发了什么、收到了什么
cv-review --file docs/design.md -v

# 4. JSON 输出（适合脚本解析）
cv-review --file docs/design.md --output-format json

# 5. 多轮博弈：3 轮迭代，输出到 outputs/
cv-review --file docs/requirement.md --mode debate --rounds 3 --output outputs/

# 6. 多轮博弈 + JSON 输出（适合 CI 流水线）
cv-review --file docs/requirement.md --mode debate --rounds 2 \
  --output outputs/ --output-format json

# 7. 查看帮助
cv-review --help

# 8. 查看详细日志（DEBUG 级别）
cv-review --file README.md --verbose
```

---

### 4.3 完整多轮闭环博弈详解（`/cv debate`）

这是 `cv-review` 的**高阶模式**，适合"只有原始需求、没有现成文档"的场景。在 Claude Code 中通过 `/cv debate` 进入**交互式向导**，无需记忆任何 CLI 参数。

#### 交互流程（在 Claude Code 中）

```
你：/cv debate docs/requirement.md

Claude：📋 进入多轮闭环博弈模式。
       已定位文件：docs/requirement.md

       🔁 请输入迭代轮数（默认 2 轮）：
你：3

Claude：📁 请输入输出目录（默认 outputs/）：
你：（直接回车）

Claude：🎯 是否需要追加定向关注点？（可选，直接回车跳过）：
你：重点审查并发安全

Claude：━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       📋 Debate 参数确认
       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         文件路径：   docs/requirement.md
         迭代轮数：   3 轮
         输出目录：   outputs/
         定向指令：   重点审查并发安全
       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       🚀 正在启动多轮闭环博弈...
          预计需要 1-3 分钟，请稍候。

       （1-3 分钟后）

       ✅ 多轮闭环博弈已完成！
       📄 最终文档输出至：outputs/DESIGN_DOCUMENT.md
       （展示前 50 行摘要）

       💬 是否需要我把完整文档贴到当前对话中讨论？
```

#### 底层执行流程

```
输入：一份原始需求文档
  │
  ▼
第 0 步：architect（如 Kimi）读取需求 → 输出初稿
  │
  ▼
第 1 轮：reviewer（如 DeepSeek）盲审初稿 → 指出漏洞
  │
  ▼
第 1 轮：architect 根据 reviewer 意见 → 修复并输出新版
  │
  ▼
第 2 轮：reviewer 再次盲审新版 → 继续挑错
  │
  ▼
第 2 轮：architect 再次修复...
  │
  ▼
（循环 N 轮后）
  │
  ▼
输出：outputs/DESIGN_DOCUMENT.md（最终收敛文档）
```

#### 与轻量盲审的区别

| 维度 | 轻量盲审（默认） | 多轮博弈（`/cv debate`） |
| :--- | :--- | :--- |
| **输入** | 已有文档 | 原始需求或初稿 |
| **输出** | 评审意见文本 | 完整设计文档 |
| **调用次数** | 1 次（reviewer） | 1 + 2×N 次（architect 初稿 + N 轮交替） |
| **成本** | 低（约 1 次 API） | 较高（默认 2 轮 ≈ 5 次 API） |
| **适用场景** | 已有文档，找人挑错 | 只有需求，让 AI 自动写+改 |
| **交互方式** | 一行命令，直接出结果 | 向导式问答，确认参数后执行 |
| **是否推荐日常使用** | ✅ 强烈推荐 | ⚪ 按需使用 |

#### 成本估算

以一份 5000 tokens 的需求文档为例：

| 轮数 | 总 API 调用次数 | 预估总 Tokens | 预估费用（参考价） |
| :--- | :--- | :--- | :--- |
| 1 轮 | 3 次 | ~25,000 | ~$1.5 ~ $2 |
| 2 轮（默认） | 5 次 | ~35,000 | ~$2.5 ~ $3.5 |
| 3 轮 | 7 次 | ~50,000 | ~$3.5 ~ $5 |

> 建议：先用 1 轮测试效果，再根据质量需求逐步增加轮数。若输入轮数 > 5，`/cv` 会主动提示成本风险。

---

## 5. 自定义提示词（ prompts.txt ）

`cv-review` 内置了两组角色提示词（`reviewer_system` 与 `architect_system`），分别用于**盲审**与**多轮博弈**场景。如果你希望调整评审风格（例如让 reviewer 更关注安全、让 architect 更关注性能），无需改动源码，直接修改个人配置即可。

### 5.1 配置优先级

`cv-review` 采用**用户级配置优先**策略：

```
~/.cv-review/prompts.txt   ← 优先使用（用户个人配置）
    若不存在，则回退到
src/cv_review/config/prompts.txt   ← 包内默认模板
```

这意味着每个人的提示词修改只影响自己，不会污染团队仓库。

### 5.2 初始化个人配置目录

首次使用时，在任意终端执行：

```bash
cv-review init
```

这会在你的用户家目录生成 `~/.cv-review/`，并复制内置的默认模板：

```
~/.cv-review/
├── api_settings.json    # 个人 API 密钥与路由
└── prompts.txt          # 个人自定义提示词（从包内默认复制而来）
```

> **注意**：`cv-review init` 不会覆盖你已存在的配置文件，放心执行。若需重置，手动删除 `~/.cv-review/` 后重新 init 即可。

### 5.3 修改提示词

直接用文本编辑器打开个人配置：

```bash
# Windows
notepad %USERPROFILE%\.cv-review\prompts.txt

# macOS / Linux
nano ~/.cv-review/prompts.txt
```

文件格式为**段格式**——以 `[section_name]` 作为键名，后续所有内容（直到下一个 `[section_name]` 为止）都属于该键的值。例如：

```ini
[reviewer_system]
你是一位资深的技术评审专家，具备深厚的系统架构与算法功底。
你的任务是对一份技术文档进行独立、客观、理性的审阅...

[architect_system]
你是一位顶尖的系统架构师兼算法科学家。
你的任务是根据用户的原始需求，撰写一份结构严谨...
```

**可自由修改的内容**：
- 角色定位（例如把 reviewer 改成"安全审计专家"）
- 评审原则（增加或删减关注点）
- 语气风格（更严厉或更温和）
- 输出格式要求（增加章节模板）

**不可修改的约束**：
- 段名 `[reviewer_system]` 和 `[architect_system]` 是代码硬编码读取的键，不能改名。
- 段格式（方括号 + 内容）必须保持，否则解析会失败。

### 5.4 生效方式

**保存后立即生效，无需重启任何服务。**

因为 `cv-review` 每次运行时都会重新从磁盘读取 `prompts.txt`（无缓存层、无守护进程）。修改保存后，下一次运行 `/cv` 或 `cv-review` 就直接使用新提示词。

### 5.5 多人协作的最佳实践

| 场景 | 推荐做法 |
| :--- | :--- |
| **个人自由发挥** | 各自执行 `cv-review init` 后自行修改 `~/.cv-review/prompts.txt`，配置天然隔离 |
| **团队统一标准** | 将优化后的 `prompts.txt` 放到仓库 `docs/templates/cv-review-prompts.txt`，新成员复制到个人目录 |
| **CI / 自动化流水线** | 在流水线镜像中预置 `~/.cv-review/` 或使用 `--config-dir` 参数（未来可扩展） |

### 5.6 两组提示词的区别：`reviewer_system` vs `architect_system`

你可能会有疑问："不就是一个单纯的第三方 API 独立审阅吗，为啥有两组提示词？"

答案是：**你最常用、最核心的功能（轻量盲审）确实只用 `reviewer_system` 一组。** `architect_system` 是多轮博弈模式（`--mode debate`）的扩展，不是必需品。

| 维度 | `reviewer_system` | `architect_system` |
| :--- | :--- | :--- |
| **角色** | 外部评审专家（批判者） | 内部架构师（创作者） |
| **任务** | 找漏洞、挑毛病、给出改进方向 | 写文档、修文档、保持逻辑自洽 |
| **使用模式** | 轻量盲审（默认）+ debate 每轮评审 | 仅 debate 模式的写稿/改稿环节 |
| **是否必须** | ✅ 核心功能，必须有 | ⚪ 扩展功能，可忽略 |
| **日常推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

**类比**：
- `reviewer_system` = 期刊审稿人（你只找他看论文，不找他写）
- `architect_system` = 论文作者（你让他写初稿，再根据审稿意见修改）

如果你只做"交叉验证"（已有文档，找人挑错），完全可以把 `architect_system` 留空或忽略。两者的存在是为了满足两种不同层次的需求：

| 需求层次 | 推荐命令 | 用到的提示词 |
| :--- | :--- | :--- |
| **Level 1：已有文档，请帮我找茬**（你最常用的） | `/cv docs/design.md` | 只用 `reviewer_system` |
| **Level 2：只有需求，请帮我写+改**（自动化程度高） | `cv-review --file req.md --mode debate` | `architect_system` + `reviewer_system` 交替使用 |

---

## 6. 目录结构

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
    ├── cv.md                   # Claude Code Slash Command `/cv` 定义文件
    ├── cv-help.md              # Claude Code Slash Command `/cv-help` 定义文件
    ├── cv-debate.md            # Claude Code Slash Command `/cv-debate` 定义文件
    └── plan.md                 # 重构计划文档
```

---

## 7. 架构与调用流程

### 7.1 轻量盲审模式

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

### 7.2 完整多轮闭环模式

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

### 7.3 `/cv` Slash Command 调用链

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

## 8. 关键设计决策

### 8.1 为什么使用独立进程 + 独立 API？

- **物理隔离**：`cv-review` 运行在独立 Python 进程中，每次请求只传递 system prompt + 当前文档，不携带 Claude Code 会话的任何历史上下文。
- **盲审真实**：Reviewer 完全不知道作者是谁、也不知道当前对话的主题，只能基于文档本身进行批判。
- **成本可控**：轻量模式只调用一次 reviewer，响应快、Token 消耗最低。

### 8.2 为什么配置放在 `~/.cv-review/`？

- **多开发者推广**：每个开发者只需配置一次自己的 API Key，不受源码仓库路径限制。
- **版本隔离**：通过 `pip install --upgrade` 升级包时，不会覆盖 `~/.cv-review/` 中的个人配置。
- **跨平台**：Windows / macOS / Linux 均通过 `Path.home()` 自动定位。

### 8.3 为什么使用标准 Python 包而非脚本？

- `pip install -e .` 即可全局使用 `cv-review` 命令。
- 内置默认模板随包分发，`cv-review init` 后立即可用。
- 其他开发者无需关心源码被 clone 到了哪个目录。

---

## 9. 变更记录

### 2026-05-29 v0.2.4 命令命名标准化

- **统一连字符命名**：将命令文件名统一为标准 CLI 风格，`cvdebate.md` → `cv-debate.md`，并新增 `cv-help.md`，菜单中显示为 `/cv-debate`、`/cv-help`，更直观美观。
- **移除带空格文件名**：删除 `cv help.md`，避免 Claude Code CLI 将其解析为 `/cv-help` 时与用户预期不符。
- **参数用法与独立命令并存**：保留 `/cv help`、`/cv debate` 参数用法，同时提供 `/cv-help`、`/cv-debate` 独立快捷命令，兼顾习惯与菜单可见性。
- **README 同步更新**：安装说明、使用模式、目录结构与变更记录全面刷新。

### 2026-05-29 v0.2.3 命令菜单优化与帮助格式升级

- **拆分 Slash Command**：新增 `docs/cv help.md`（`/cv help`）与 `docs/cvdebate.md`（`/cvdebate`），解决初次使用者无法在菜单中发现 help 与 debate 入口的问题。
- **帮助格式 Markdown 化**：`/cv help` 的输出从 ASCII 框线风格全面升级为标准 Markdown 格式（含标题、表格、列表、代码块）。
- **空参数默认进帮助**：`/cv` 无参数时默认展示帮助信息，降低新用户上手门槛。
- **README 同步更新**：安装说明、使用模式大全、目录结构均更新以反映多命令体系。

### 2026-05-29 v0.2.2 /cv 交互式向导重构

- **重写 `/cv` Slash Command**：`docs/cv.md` 全面重构，支持三种模式：
  - **帮助模式**：`/cv help` 展示完整用法、路径格式说明与前置配置清单。
  - **轻量盲审模式**（默认）：`/cv <文件> [定向指令]`，增加路径不存在时的友好错误提示与跨平台路径兼容性处理。
  - **Debate 交互向导模式**：`/cv debate [<文件>]`，进入交互式问答流程，依次询问轮数、输出目录、定向关注点，无需记忆任何 CLI 参数。
- **路径兼容性**：明确支持 Windows（`/`、`\`、绝对路径含盘符）、Linux、macOS 及相对路径；路径验证失败时向用户报告具体原因并请求重新输入。
- **README 同步更新**：第 4 章使用模式新增"模式 E：查看帮助"与"路径兼容性说明"表格；第 4.3 节 debate 详解补充交互流程示例。

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
