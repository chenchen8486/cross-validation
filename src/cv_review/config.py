"""配置加载模块，支持用户级配置与内置默认配置的层级覆盖。

本模块负责定位、初始化及加载运行时所需的全部外部配置，包括：
- API 通道与路由参数（`api_settings.json`）
- 角色 System Prompt（`prompts.txt`）

配置优先级：用户级目录 ``~/.cv-review/`` > 包内内置默认模板。
"""

import functools
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from importlib.resources import files

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_DIR_NAME = ".cv-review"
CONFIG_FILES = ("api_settings.json", "prompts.txt")


def _load_dotenv_files() -> None:
    """自动加载 ``.env`` 文件到环境变量。

    加载顺序（后加载的优先级更高，可覆盖前者）：
    1. ``~/.cv-review/.env``（用户级全局配置）
    2. 当前工作目录下的 ``.env``（项目级配置）

    """
    # 用户级 .env
    user_env = _get_user_config_dir() / ".env"
    if user_env.exists():
        load_dotenv(str(user_env), override=False)
        logger.debug("已加载用户级 .env: %s", user_env)

    # 项目级 .env（当前工作目录）
    cwd_env = Path(".env").resolve()
    if cwd_env.exists():
        load_dotenv(str(cwd_env), override=True)
        logger.debug("已加载项目级 .env: %s", cwd_env)


def _get_user_config_dir() -> Path:
    """返回用户级配置目录路径（跨平台兼容）。

    Returns:
        Path: ``~/.cv-review`` 的绝对路径。
    """
    return Path.home() / DEFAULT_CONFIG_DIR_NAME


def _get_builtin_config_dir() -> Path:
    """返回包内内置默认配置目录路径。

    Returns:
        Path: 指向 ``cv_review.config`` 包内 ``config/`` 子目录的路径。
    """
    return Path(str(files("cv_review") / "config"))


def init_user_config(force: bool = False) -> Path:
    """将内置默认配置模板复制到用户家目录，生成 ``~/.cv-review/``。

    Args:
        force: 若为 True，则强制覆盖已有配置文件。

    Returns:
        Path: 用户级配置目录路径。

    Raises:
        RuntimeError: 复制文件过程中发生 I/O 错误。
    """
    user_dir = _get_user_config_dir()
    builtin_dir = _get_builtin_config_dir()

    if not user_dir.exists():
        user_dir.mkdir(parents=True, exist_ok=True)
        logger.info("已创建用户级配置目录: %s", user_dir)

    for filename in CONFIG_FILES:
        src = builtin_dir / filename
        dst = user_dir / filename
        if src.exists() and (not dst.exists() or force):
            try:
                shutil.copy2(str(src), str(dst))
                action = "强制覆盖" if force and dst.exists() else "复制"
                logger.info("已%s配置模板: %s", action, dst)
            except OSError as exc:
                logger.error("复制配置文件失败 [%s]: %s", filename, exc)
                raise RuntimeError(f"复制配置文件失败 [{filename}]: {exc}") from exc
        elif dst.exists() and force and not src.exists():
            try:
                dst.unlink()
                logger.info("已删除用户配置（内置模板已移除）: %s", dst)
            except OSError as exc:
                logger.error("删除用户配置失败 [%s]: %s", filename, exc)
                raise RuntimeError(f"删除用户配置失败 [{filename}]: {exc}") from exc
        elif dst.exists():
            logger.debug("用户配置已存在，跳过: %s", dst)

    return user_dir


def _resolve_config_path(filename: str) -> Path:
    """按优先级解析配置文件路径。

    先查找用户级目录 ``~/.cv-review/``，若不存在则回退到包内默认模板。

    Args:
        filename: 配置文件名，如 ``api_settings.json``。

    Returns:
        Path: 最终选用的配置文件绝对路径。

    Raises:
        FileNotFoundError: 用户级与内置目录均未找到该文件。
    """
    user_path = _get_user_config_dir() / filename
    if user_path.exists():
        logger.debug("使用用户级配置: %s", user_path)
        return user_path

    builtin_path = _get_builtin_config_dir() / filename
    if builtin_path.exists():
        logger.debug("使用内置默认配置: %s", builtin_path)
        return builtin_path

    raise FileNotFoundError(
        f"找不到配置文件 [{filename}]，"
        f"请执行 `cv-review init` 初始化配置目录。"
    )


def _validate_api_settings(data: dict[str, Any]) -> None:
    """校验 ``api_settings.json`` 的结构完整性。

    Args:
        data: 已解析的配置字典。

    Raises:
        RuntimeError: 缺少必需字段、类型错误或通道配置不完整。
    """
    if not isinstance(data, dict):
        raise RuntimeError("配置文件根节点必须是 JSON 对象（dict）")

    channels = data.get("channels")
    if not isinstance(channels, dict):
        raise RuntimeError("配置文件缺少必需的 'channels' 字段，或该字段不是对象")
    if not channels:
        raise RuntimeError("channels 不能为空，请至少配置一个 API 通道")

    routing = data.get("runtime_routing")
    if not isinstance(routing, dict):
        raise RuntimeError("配置文件缺少必需的 'runtime_routing' 字段，或该字段不是对象")

    required_routing_keys = ("architect_channel", "reviewer_channel")
    for key in required_routing_keys:
        channel_name = routing.get(key)
        if not channel_name:
            raise RuntimeError(f"runtime_routing 缺少必需的字段: '{key}'")
        if channel_name not in channels:
            raise RuntimeError(
                f"runtime_routing['{key}'] = '{channel_name}' 在 channels 中找不到对应配置"
            )

    required_channel_keys = ("base_url", "model_name")
    for name, cfg in channels.items():
        if not isinstance(cfg, dict):
            raise RuntimeError(f"channels['{name}'] 必须是对象")
        for k in required_channel_keys:
            if not cfg.get(k):
                raise RuntimeError(
                    f"channels['{name}'] 缺少必需字段 '{k}'"
                )
        if not cfg.get("api_key_env"):
            raise RuntimeError(
                f"channels['{name}'] 缺少必需字段 'api_key_env'"
            )
        api_format = cfg.get("api_format", "openai")
        if api_format not in ("openai", "anthropic"):
            raise RuntimeError(
                f"channels['{name}'] 的 api_format 必须是 'openai' 或 'anthropic'，"
                f"当前值: {api_format}"
            )

    temperature = routing.get("temperature")
    if temperature is not None and not (0 <= temperature <= 2):
        raise RuntimeError(
            f"runtime_routing['temperature'] 必须在 0~2 之间，当前值: {temperature}"
        )

    max_rounds = routing.get("max_rounds")
    if max_rounds is not None and max_rounds < 1:
        raise RuntimeError(
            f"runtime_routing['max_rounds'] 必须 >= 1，当前值: {max_rounds}"
        )


@functools.lru_cache(maxsize=1)
def load_api_settings() -> dict[str, Any]:
    """加载 ``api_settings.json``，返回完整的 API 通道与路由配置。

    Returns:
        dict: 包含 ``channels`` 与 ``runtime_routing`` 的字典。

    Raises:
        FileNotFoundError: 找不到配置文件。
        json.JSONDecodeError: JSON 格式损坏。
        RuntimeError: 配置结构校验失败。
    """
    path = _resolve_config_path("api_settings.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("配置文件 [%s] JSON 格式损坏: %s", path, exc)
        raise

    _validate_api_settings(data)
    return data


@functools.lru_cache(maxsize=1)
def load_prompts() -> dict[str, str]:
    """解析 ``prompts.txt``，返回角色 System Prompt 字典。

    文本格式约定：以 ``[section_name]`` 作为键名，后续非空行直至下一个
    ``[section_name]`` 之前的全部内容作为该键的值。

    Returns:
        dict: 键名为 section 名，值为对应的多行文本内容。

    Raises:
        FileNotFoundError: 找不到配置文件。
    """
    path = _resolve_config_path("prompts.txt")
    prompts: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    if current_key is not None:
                        value = "\n".join(current_lines).strip()
                        if value:
                            prompts[current_key] = value
                    current_key = stripped[1:-1]
                    current_lines = []
                else:
                    if current_key is not None:
                        current_lines.append(raw_line.rstrip())
            if current_key is not None:
                value = "\n".join(current_lines).strip()
                if value:
                    prompts[current_key] = value
    except OSError as exc:
        logger.error("读取 Prompt 配置文件失败 [%s]: %s", path, exc)
        raise

    if not prompts:
        raise RuntimeError(f"Prompt 配置文件 [{path}] 为空或格式无效")

    return prompts


# 模块初始化时自动加载 .env 文件
_load_dotenv_files()
