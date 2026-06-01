"""环境诊断模块，提供一键检测安装就绪度的能力。

检查项覆盖：
1. ``cv-review`` CLI 是否在 PATH 中可用；
2. Slash Command 文件是否已部署到 ``~/.claude/commands/``；
3. 用户级配置目录 ``~/.cv-review/`` 是否存在；
4. ``.env`` 文件及 API Key 环境变量是否配置；
5. ``api_settings.json`` 结构是否有效。
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from cv_review.config import (
    _get_user_config_dir,
    _load_dotenv_files,
    _validate_api_settings,
)

logger = logging.getLogger(__name__)

SLASH_COMMAND_FILES = ("cv.md", "cv_help.md", "cv_debate.md")
COMMANDS_DIR = Path.home() / ".claude" / "commands"

_OK = "[32m[✓][0m"
_FAIL = "[31m[✗][0m"
_WARN = "[33m[!][0m"


def _print_item(status: str, message: str) -> None:
    """打印单行诊断结果（自动适配无 ANSI 支持的终端）。"""
    if sys.platform == "win32" and os.environ.get("TERM") is None:
        # Windows CMD 默认不支持 ANSI，使用纯文本
        symbol = "[OK]" if "32m" in status else "[FAIL]" if "31m" in status else "[WARN]"
        print(f"  {symbol} {message}")
    else:
        print(f"  {status} {message}")


def _check_cli_availability() -> bool:
    """检查 ``cv-review`` 是否在 PATH 中可用。

    Returns:
        bool: 可用返回 True，否则返回 False。
    """
    try:
        result = subprocess.run(
            ["cv-review", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _check_slash_commands() -> tuple[bool, list[str]]:
    """检查 Slash Command 文件是否已部署。

    Returns:
        tuple: ``(全部存在, 缺失文件名列表)``
    """
    missing: list[str] = []
    for filename in SLASH_COMMAND_FILES:
        if not (COMMANDS_DIR / filename).exists():
            missing.append(filename)
    return len(missing) == 0, missing


def _check_user_config() -> tuple[bool, Path]:
    """检查用户级配置目录是否存在。

    Returns:
        tuple: ``(存在, 配置目录路径)``
    """
    config_dir = _get_user_config_dir()
    return config_dir.exists(), config_dir


def _check_env_and_keys() -> tuple[bool, list[str]]:
    """检查 ``.env`` 加载情况及 API Key 环境变量。

    先触发 ``python-dotenv`` 加载逻辑，再检测常见 Key 名。

    Returns:
        tuple: ``(至少有一个 Key, 已检测到 Key 名列表)``
    """
    _load_dotenv_files()
    key_names = [
        "ANTHROPIC_AUTH_TOKEN",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "KIMI_API_KEY",
    ]
    found = [k for k in key_names if os.environ.get(k)]
    return bool(found), found


def _check_api_settings() -> tuple[bool, str]:
    """校验 ``api_settings.json`` 的结构有效性。

    Returns:
        tuple: ``(有效, 错误信息)``。有效时错误信息为空字符串。
    """
    from cv_review.config import _resolve_config_path

    try:
        import json
        path = _resolve_config_path("api_settings.json")
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        _validate_api_settings(data)
        return True, ""
    except FileNotFoundError:
        return False, "找不到 api_settings.json，请先执行 cv-review init"
    except json.JSONDecodeError as exc:
        return False, f"api_settings.json JSON 格式错误: {exc}"
    except RuntimeError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, f"未知错误: {exc}"


def run_diagnosis() -> int:
    """执行完整环境诊断并打印报告。

    Returns:
        int: 0 表示全部就绪；1 表示存在需要修复的问题。
    """
    print("=" * 50)
    print("cv-review 环境诊断报告")
    print("=" * 50)

    all_ok = True

    # 1. CLI 可用性
    print("\n[1/5] CLI 工具")
    if _check_cli_availability():
        _print_item(_OK, "cv-review 已在 PATH 中可用")
    else:
        _print_item(_FAIL, "cv-review 不在 PATH 中")
        print(
            "      提示: 请确保安装目录的 Scripts/ 或 bin/ 已加入系统 PATH，"
            "或在虚拟环境中运行。"
        )
        all_ok = False

    # 2. Slash Command 部署
    print("\n[2/5] Claude Code Slash Command")
    sc_ok, sc_missing = _check_slash_commands()
    if sc_ok:
        _print_item(_OK, f"已部署到 {COMMANDS_DIR}")
    else:
        _print_item(_FAIL, f"缺失文件: {', '.join(sc_missing)}")
        print("      提示: 执行 cv-review setup-claude 一键部署")
        all_ok = False

    # 3. 用户配置目录
    print("\n[3/5] 用户配置目录")
    cfg_ok, cfg_dir = _check_user_config()
    if cfg_ok:
        _print_item(_OK, f"{cfg_dir} 已存在")
    else:
        _print_item(_FAIL, f"{cfg_dir} 不存在")
        print("      提示: 执行 cv-review init 初始化配置模板")
        all_ok = False

    # 4. API Key
    print("\n[4/5] API Key 环境变量")
    key_ok, found_keys = _check_env_and_keys()
    if key_ok:
        _print_item(_OK, f"已检测到: {', '.join(found_keys)}")
    else:
        _print_item(_FAIL, "未检测到任何 API Key 环境变量")
        print(
            "      提示: 在项目根目录创建 .env 文件，写入：\n"
            "            ANTHROPIC_AUTH_TOKEN=sk-xxx\n"
            "            DEEPSEEK_API_KEY=sk-xxx"
        )
        all_ok = False

    # 5. API 配置有效性
    print("\n[5/5] API 配置结构")
    settings_ok, settings_err = _check_api_settings()
    if settings_ok:
        _print_item(_OK, "api_settings.json 结构正确")
    else:
        _print_item(_FAIL, settings_err)
        all_ok = False

    # 汇总
    print("\n" + "=" * 50)
    if all_ok:
        print("全部就绪！重启 Claude Code CLI 后即可使用 /cv 系列命令。")
    else:
        print("存在未就绪项，请按上方提示修复后再次运行 cv-review doctor。")
    print("=" * 50)

    return 0 if all_ok else 1
