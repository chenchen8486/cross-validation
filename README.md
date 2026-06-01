# cv-review：文档交叉验证工具

> **cv-review** 首先是一个**命令**——安装后你在终端输入 `cv-review --file 文档.md`，它就会调用独立模型做交叉验证。
> 
> 它同时也是 **PyPI 包名**（`pip install cv-review`）和**产品名**。源码内部的 Python 模块叫 `cv_review`（下划线），而你正在阅读的 git 仓库叫 `cross-validation`。

让 AI 写代码、写文档时，你是否遇到过这种情况：它越写越顺，你却越看越心虚？方案看似合理，实则暗藏漏洞；它反复强调的"最佳实践"，可能只是训练数据里的偏见。

这不是你的错觉。大型语言模型在单一会话中长期运行，必然会出现**思维疲劳**——它会陷入自我重复，对明显的逻辑漏洞视而不见，甚至开始说你想听的话，而不是正确的话。

cv-review 的核心价值很简单：**用另一个模型来验证当前模型的输出**。我们把这叫作**交叉验证**。

同时提供 **Claude Code CLI 全局 Slash Command `/cv`**，支持在任意工程目录下对任意文档进行轻量或深度验证，无需关心源码位置。



假设 AI 刚帮你起草了一份《登录模块设计》，文件保存在 `docs/login-module.md`，核心内容如下：

```markdown
## 登录模块设计

### 身份认证
- 使用 JWT Token，过期时间 2 小时

### 会话存储
- 使用 Redis 缓存 Token

### 安全防护
- 接口限流：每秒最多 100 次请求
- 密码传输使用 HTTPS
```

AI 信誓旦旦地表示逻辑自洽、考虑周全。你也挑不出毛病。

然后你执行了：

```bash
/cv docs/login-module.md
```

一分钟后，另一个独立模型的交叉验证意见返回了——

### 校验前 vs 校验后

| 文档原文（校验前） | 交叉验证发现（校验后） |
| :--- | :--- |
| "JWT Token 过期时间 2 小时，安全性高" | ❌ **Token 刷新机制缺失**：2 小时后用户被强制登出，体验断裂；文档完全未说明如何无感知续期 |
| "使用 Redis 缓存 Token，性能好" | ❌ **缓存未设 TTL**：过期 Token 永不删除，内存持续增长，最终 OOM |
| "接口限流，每秒 100 次请求" | ❌ **限流粒度太粗**：只限接口级别，同一 IP 可无限次尝试不同账号密码，存在暴力破解风险 |
| "密码传输使用 HTTPS，安全可靠" | ❌ **密码错误次数无锁定**：攻击者可无限次猜测密码，HTTPS 只防窃听不防爆破 |

结果出乎意料。这些漏洞 AI 在起草时**完全没意识到**——因为它们恰恰是它"觉得自己考虑到了"的盲区。

**修正后的文档应该补充**：
- Token 自动续期策略（Refresh Token 或滑动过期）
- Redis Key 的 TTL 设置与过期清理机制
- IP 级别的登录失败锁定（如 5 次错误锁定 15 分钟）
- 账户级别的异常登录告警

这就是交叉验证的核心价值：**单模型对自身的输出永远有盲区，而另一个没有先入之见的模型不会**。cv-review 把这个"第二双眼睛"变成了可复用的工具。

---

## 1. 快速开始

```bash
git clone https://github.com/your-org/cv-review.git
cd cv-review
pip install -e ".[dev,anthropic]"
cv-review init                 # 生成 ~/.cv-review/ 配置模板
cv-review setup-claude         # 一键部署 /cv 系列 Slash Command
cv-review doctor               # 诊断环境，确认全部就绪
```

然后在项目根目录创建 `.env` 并写入你的 API Key（详见 2.4 节），**重启 Claude Code CLI**，即可在任意工程使用：

```bash
/cv README.md
```

---

## 2. 安装指南

### 2.1 环境要求

- Python >= 3.10
- 推荐使用虚拟环境（conda / venv）

### 2.2 安装包

```bash
git clone <仓库地址>
cd cv-review
pip install -e .
```

安装完成后，全局 `cv-review` 命令即加入 PATH，任意目录均可调用。

### 2.3 初始化配置

```bash
cv-review init
```

首次运行会在用户家目录生成 `~/.cv-review/`，将内置的默认配置模板（`api_settings.json` + `prompts.txt`）复制过去。

> **为什么要放在 `~/.cv-review/` 而不是工程目录？**
> 
> API 通道配置（base_url、model_name、api_key_env）属于**个人偏好**，不是工程代码的一部分。类似于 `~/.aws/` 或 `~/.ssh/` 的设计——个人凭证放在家目录，换工程时无需重复配置。工程目录里只需要放 `.env` 文件（已自动被 `.gitignore` 忽略）。

> **注意**：`cv-review init` 不会覆盖你已存在的配置文件，放心执行。

### 2.4 API Key 配置

API Key 配置分为两层，不要混淆：

| 层级 | 文件 | 位置 | 内容 |
|------|------|------|------|
| **第一层（真实密钥）** | `.env` | **项目根目录**（当前工程） | `ANTHROPIC_AUTH_TOKEN=sk-xxx` |
| **第二层（通道结构）** | `api_settings.json` | `~/.cv-review/`（用户家目录） | 定义 base_url、model_name、`api_key_env` |

**`.env` 存放真实密钥，`api_settings.json` 只存放"哪个环境变量名对应哪个通道"。两者通过 `api_key_env` 字段关联，程序启动时自动从 `.env` 读取并注入。**

#### 步骤 1：在项目根目录创建 `.env`

```bash
# Windows
notepad .env

# Linux / macOS
touch .env
```

写入你的 API Key（变量名**必须与默认配置一致**）：

```text
ANTHROPIC_AUTH_TOKEN=sk-你的-Kimi-Key
DEEPSEEK_API_KEY=sk-你的-DeepSeek-Key
```

> `.env` 已加入 `.gitignore`，**不会误提交到 Git**。
> 
> **⚠️ 安全提示**：绝不要将 API Key 明文写入项目源码或提交到 Git。`api_settings.json` 中不支持直接填写 `api_key`，必须通过 `api_key_env` 指定环境变量名。

#### 步骤 2：确认变量名对应关系（通常无需操作）

若你执行过 `cv-review init`，通道配置在 `~/.cv-review/api_settings.json` 中。默认配置已预填好变量名：

- Kimi 通道 → `api_key_env`: `"ANTHROPIC_AUTH_TOKEN"`
- DeepSeek 通道 → `api_key_env`: `"DEEPSEEK_API_KEY"`

**只要 `.env` 中的变量名与上述保持一致，即可直接使用。** 若你修改了 `.env` 中的变量名（如改成 `MY_KIMI_KEY`），才需要同步修改 `~/.cv-review/api_settings.json` 中的 `api_key_env`。

#### 步骤 3：验证

```bash
cv-review --file README.md
```

或直接在 Claude Code 中：

```
/cv README.md
```

### 2.5 支持的 API 通道

默认内置配置支持以下通道（可在 `~/.cv-review/api_settings.json` 中自定义）：

| 通道 | 基础地址 | 环境变量 | 默认模型 | API 格式 |
| :--- | :--- | :--- | :--- | :--- |
| Kimi | `https://api.kimi.com/coding/` | `ANTHROPIC_AUTH_TOKEN` | `kimi-k2.6` | `anthropic` |
| DeepSeek | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | `deepseek-chat` | `openai` |

如需接入其他模型（OpenAI、Claude、GLM 等），在配置文件 `api_settings.json` 中新增通道时，需指定对应的 `api_format`（`openai` 或 `anthropic`）。

> 如需使用 Anthropic 格式（如 Claude API），请确保已安装 Anthropic 支持：
> ```bash
> pip install cv-review[anthropic]
> ```

### 2.6 Claude Code CLI 集成（推荐使用）

#### 一键部署（推荐）

```bash
cv-review setup-claude
```

该命令会自动将 `docs/cv*.md` 复制到 `~/.claude/commands/`，无需手动操作。

#### 手动部署（备用）

若一键部署失败，可手动复制：

```bash
# 所有平台通用（Windows Git Bash / WSL / macOS / Linux）
mkdir -p ~/.claude/commands
cp docs/cv.md docs/cv_help.md docs/cv_debate.md ~/.claude/commands/
```

> **Windows CMD 用户**：若使用原生 CMD，请将 `~` 替换为 `%USERPROFILE%`，将 `cp` 替换为 `copy`：
> ```cmd
> copy "docs\cv.md" "%USERPROFILE%\.claude\commands\"
> copy "docs\cv_help.md" "%USERPROFILE%\.claude\commands\"
> copy "docs\cv_debate.md" "%USERPROFILE%\.claude\commands\"
> ```

#### 重启生效

**完全退出并重新启动 Claude Code CLI**（不是刷新窗口），重启后输入 `/` 即可看到 `/cv`、`/cv_help`、`/cv_debate` 三个命令。

#### 环境诊断

部署后运行以下命令，一键检测所有前置条件是否就绪：

```bash
cv-review doctor
```

诊断项包括：
- `cv-review` 是否在 PATH 中可用
- Slash Command 文件是否已部署
- `~/.cv-review/` 配置目录是否存在
- `.env` 及 API Key 环境变量是否配置
- `api_settings.json` 结构是否有效

---

## 3. 使用模式大全

### 3.1 Claude Code 中 `/cv` 的所有用法（推荐日常开发）

`/cv` 是 Claude Code CLI 的**全局 Slash Command**，安装后可在任意工程目录使用。它的核心价值是提供**"评审 → 询问是否修改 → 直接 Edit 改文件"**的交互闭环。

#### 模式 A：轻量验证（最常用）

```bash
/cv docs/api-design.md
```

- 对指定文档执行一次独立模型的交叉验证。
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
- 对代码的验证同样保持完全隔离与客观独立原则。

#### 模式 D：智能意图模式（自动扫描）

```bash
/cv 你帮我校验当前工程的代码合理吗
/cv 检查一下这个项目的架构设计有没有漏洞
/cv 看看这个工程的异常处理是否完善
```

- **不指定文件路径**，直接输入自然语言请求。
- `/cv` 会自动识别意图，扫描工程中的相关文件（代码、文档或两者），聚合成临时文档后提交交叉验证。
- 自动排除缓存目录、依赖目录和版本控制目录，文件扫描范围由系统自动判断，无固定上限。
- 评审完成后会提示："如需针对单个文件深度审查，请使用 `/cv <文件路径>`。"

#### 模式 E：多轮闭环博弈（深度生成）

```bash
/cv_debate docs/requirement.md
```

- 进入**交互式向导**，Claude 会依次询问：迭代轮数、输出目录、定向关注点。
- 系统自动调用 `architect + reviewer` 双通道进行多轮博弈，最终输出完整设计文档。
- 全程只需回答几个问题，无需记忆 CLI 参数。

#### 模式 F：查看帮助

```bash
/cv help
```

- 展示 `/cv` 的完整用法、参数说明、路径格式提示与前置配置检查清单。
- 不确定怎么用时，随时输入 `/cv help`。
- 也可直接输入 `/cv`（无参数），会自动进入帮助模式。

#### 路径提示

`/cv` 支持相对路径、绝对路径（含 Windows 盘符）、正斜杠与反斜杠混用等所有常见格式，底层 `pathlib` 会自动标准化。Windows 用户建议优先使用正斜杠 `/`，可减少 Shell 转义问题。如果路径不存在，`/cv` 会明确提示并请求重新输入。

---

### 3.2 多轮闭环博弈详解（`/cv_debate`）

这是 `cv-review` 的**高阶模式**，适合"只有原始需求、没有现成文档"的场景。在 Claude Code 中通过 `/cv_debate` 进入**交互式向导**，无需记忆任何 CLI 参数。

#### 交互流程（在 Claude Code 中）

```
你：/cv_debate docs/requirement.md

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
第 1 轮：reviewer（如 DeepSeek）验证初稿 → 指出漏洞
  │
  ▼
第 1 轮：architect 根据 reviewer 意见 → 修复并输出新版
  │
  ▼
第 2 轮：reviewer 再次验证新版 → 继续挑错
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

#### 与轻量验证的区别

| 维度 | 轻量验证（默认） | 多轮博弈（`/cv_debate`） |
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

### 3.3 附录：底层 `cv-review` CLI 速查

`cv-review` 是 `/cv` 和 `/cv_debate` 的底层引擎，任何终端均可独立调用。完整参数请运行 `cv-review --help` 查看。

```bash
# 轻量验证
cv-review --file docs/design.md

# 定向验证
cv-review --file docs/design.md --instruction "重点审查并发安全"

# JSON 输出（适合脚本解析）
cv-review --file docs/design.md --output-format json

# 多轮博弈
cv-review --file docs/requirement.md --mode debate --rounds 2 --output outputs/

# 调试模式（查看完整 API 调用日志）
cv-review --file docs/design.md -v
```

---

## 4. 自定义提示词（ prompts.txt ）

`cv-review` 内置了两组角色提示词（`reviewer_system` 与 `architect_system`），分别用于**交叉验证**与**多轮博弈**场景。如果你希望调整评审风格（例如让 reviewer 更关注安全、让 architect 更关注性能），无需改动源码，直接修改个人配置即可。

### 4.1 配置优先级

`cv-review` 采用**用户级配置优先**策略：

```
~/.cv-review/prompts.txt   ← 优先使用（用户个人配置）
    若不存在，则回退到
src/cv_review/config/prompts.txt   ← 包内默认模板
```

这意味着每个人的提示词修改只影响自己，不会污染团队仓库。

### 4.2 初始化个人配置目录

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

> **注意**：`cv-review init` 不会覆盖你已存在的配置文件。日常修改提示词时，直接编辑 `~/.cv-review/prompts.txt` 即可，**无需重新执行 init**。仅在首次安装或需要重置为默认模板时才执行 init。

### 4.3 修改提示词

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

### 4.4 生效方式

**保存后立即生效，无需重启任何服务。**

因为 `cv-review` 每次运行时都会重新从磁盘读取 `prompts.txt`（无缓存层、无守护进程）。修改保存后，下一次运行 `/cv` 或 `cv-review` 就直接使用新提示词。

### 4.5 多人协作的最佳实践

| 场景 | 推荐做法 |
| :--- | :--- |
| **个人自由发挥** | 各自执行 `cv-review init` 后自行修改 `~/.cv-review/prompts.txt`，配置天然隔离 |
| **团队统一标准** | 将优化后的 `prompts.txt` 放到仓库 `docs/templates/cv-review-prompts.txt`，新成员复制到个人目录 |
| **CI / 自动化流水线** | 在流水线镜像中预置 `~/.cv-review/` 或使用 `--config-dir` 参数（未来可扩展） |

### 4.6 两组提示词的区别：`reviewer_system` vs `architect_system`

你可能会有疑问："不就是一个单纯的第三方 API 独立审阅吗，为啥有两组提示词？"

答案是：**你最常用、最核心的功能（轻量验证）确实只用 `reviewer_system` 一组。** `architect_system` 是多轮博弈模式（`--mode debate`）的扩展，不是必需品。

| 维度 | `reviewer_system` | `architect_system` |
| :--- | :--- | :--- |
| **角色** | 外部评审专家（批判者） | 内部架构师（创作者） |
| **任务** | 找漏洞、挑毛病、给出改进方向 | 写文档、修文档、保持逻辑自洽 |
| **使用模式** | 轻量验证（默认）+ debate 每轮评审 | 仅 debate 模式的写稿/改稿环节 |
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

## 5. 目录结构

```text
cross-validation/               # 本仓库根目录（git clone 后的本地目录）
├── pyproject.toml              # 标准 Python 包定义，注册 cv-review CLI 入口
├── README.md                   # 本文档
├── .gitignore                  # Git 忽略规则
├── src/
│   └── cv_review/              # 主包
│       ├── __init__.py
│       ├── cli.py              # argparse 主入口（init / review / debate）
│       ├── config.py           # 配置加载器（~/.cv-review/ > 内置默认）
│       ├── api.py              # OpenAI / Anthropic 兼容客户端封装（适配器模式）
│       ├── reviewer.py         # 验证逻辑（轻量验证 + 多轮闭环）
│       └── config/             # 内置默认配置模板
│           ├── api_settings.json
│           └── prompts.txt
├── tests/
│   ├── test_api.py             # API 客户端与重试策略测试
│   ├── test_config.py          # 配置加载与路径优先级测试
│   └── test_reviewer.py        # 评审逻辑与输出格式测试
└── docs/
    ├── cv.md                   # Claude Code Slash Command `/cv` 定义文件
    ├── cv_help.md              # Claude Code Slash Command `/cv_help` 定义文件
    └── cv_debate.md            # Claude Code Slash Command `/cv_debate` 定义文件
```

---

## 6. 架构与调用流程

### 6.1 轻量验证模式

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
  ├─→ api.py 初始化 reviewer 通道客户端适配器
  │       （支持 OpenAI / Anthropic 双格式，与当前 CLI 上下文完全隔离）
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
  ├─→ 初始化 architect + reviewer 双通道客户端适配器
  │       （支持 OpenAI / Anthropic 混合，如 Kimi + DeepSeek）
  │
  ├─→ 第 1 轮：architect 出初稿
  │
  ├─→ 第 1~N 轮循环：
  │       reviewer 交叉验证 → 指出漏洞
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

### 7.1 为什么使用独立进程 + 独立模型？

- **完全隔离**：`cv-review` 运行在独立 Python 进程中，每次请求只传递 system prompt + 当前文档，不携带 Claude Code 会话的任何历史上下文。
- **客观独立**：Reviewer 完全不知道作者是谁、也不知道当前对话的主题，只能基于文档本身进行批判。
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

