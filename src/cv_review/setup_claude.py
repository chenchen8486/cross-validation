"""Claude Code CLI Slash Command 自动部署模块。

负责将工程 docs/ 目录下的命令定义文件（cv.md, cv_help.md, cv_debate.md）
一键复制到用户级的 ``~/.claude/commands/`` 目录，实现 /cv 系列命令的
零手动部署。
"""

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SLASH_COMMAND_FILES = ("cv.md", "cv_help.md", "cv_debate.md")
COMMANDS_DIR = Path.home() / ".claude" / "commands"


def _find_source_docs_dir() -> Path:
    """定位工程 docs/ 目录的绝对路径。

    查找策略（按优先级）：
    1. 当前工作目录下的 ``docs/``（用户通常在项目根目录运行）。
    2. 从本包安装位置回推两级得到的 ``docs/``（适用于 ``pip install -e .``
       的可编辑安装模式）。

    Returns:
        Path: 确认存在的 ``docs/`` 目录路径。

    Raises:
        RuntimeError: 所有策略均未找到 ``docs/`` 目录。
    """
    # 策略 1：当前工作目录
    cwd_docs = Path.cwd() / "docs"
    if cwd_docs.is_dir() and (cwd_docs / "cv.md").exists():
        logger.debug("使用当前工作目录的 docs/: %s", cwd_docs)
        return cwd_docs

    # 策略 2：从包位置回推（可编辑安装时，包位于 src/cv_review/）
    package_dir = Path(__file__).resolve().parent
    editable_docs = package_dir.parent.parent / "docs"
    if editable_docs.is_dir() and (editable_docs / "cv.md").exists():
        logger.debug("使用可编辑安装路径的 docs/: %s", editable_docs)
        return editable_docs

    raise RuntimeError(
        "找不到工程 docs/ 目录。请确保你在项目根目录运行此命令，"
        "或从源码仓库重新安装：pip install -e ."
    )


def deploy_slash_commands(force: bool = False) -> Path:
    """部署 Slash Command 定义文件到 ``~/.claude/commands/``。

    Args:
        force: 若为 True，则强制覆盖目标目录中已存在的同名文件。

    Returns:
        Path: 目标命令目录的绝对路径。

    Raises:
        RuntimeError: 源文件缺失或复制失败。
    """
    src_dir = _find_source_docs_dir()
    dst_dir = COMMANDS_DIR

    if not dst_dir.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        logger.info("已创建 Claude Code 命令目录: %s", dst_dir)

    for filename in SLASH_COMMAND_FILES:
        src = src_dir / filename
        dst = dst_dir / filename

        if not src.exists():
            raise RuntimeError(f"源文件缺失: {src}")

        if dst.exists() and not force:
            logger.info("目标文件已存在，跳过（加 --force 可覆盖）: %s", dst)
            continue

        try:
            shutil.copy2(str(src), str(dst))
            action = "强制覆盖" if force and dst.exists() else "复制"
            logger.info("已%s: %s → %s", action, src.name, dst)
        except OSError as exc:
            logger.error("复制文件失败 [%s]: %s", filename, exc)
            raise RuntimeError(f"复制文件失败 [{filename}]: {exc}") from exc

    return dst_dir
