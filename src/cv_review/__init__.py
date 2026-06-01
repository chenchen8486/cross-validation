"""cv-review: 基于独立 API 盲审的文档交叉验证框架。

本包提供命令行工具 `cv-review`，支持对指定文档调用独立大模型 API
进行无污染的盲审交叉验证，并可选完整多轮闭环博弈模式。
"""

__version__ = "0.2.0"
__all__ = ["config", "api", "reviewer", "cli", "setup_claude", "doctor"]
