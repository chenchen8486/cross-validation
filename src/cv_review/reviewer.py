"""评审逻辑模块，提供轻量盲审与完整多轮闭环博弈两种模式。

轻量模式（默认）仅调用一次 reviewer 通道，对输入文档进行独立盲审，
成本最低、响应最快；完整闭环模式则复用 architect + reviewer 双通道
进行多轮迭代，输出经过交叉验证的高置信度设计文档。
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from cv_review.config import init_user_config, load_api_settings, load_prompts
from cv_review.api import init_api_client, ask_agent

logger = logging.getLogger(__name__)

# 常见二进制文件扩展名，直接拒绝评审以避免乱码和 Token 浪费
BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".pdf",
    ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz",
    ".rar", ".exe", ".dll", ".so", ".dylib", ".bin", ".dat",
}

# 应被排除的目录名片段
IGNORED_DIR_SEGMENTS: set[str] = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "build", "dist", ".pytest_cache", ".idea", ".vscode",
}


# 文件大小限制：100 KB（超出则拒绝，防止 Token 超限和成本失控）
MAX_FILE_SIZE = 100 * 1024

# 内容长度限制：50,000 字符（约 12K tokens）
MAX_CHARS = 50000


def _should_ignore(path: Path) -> bool:
    """判断路径是否应被排除（如缓存、依赖、版本控制目录）。

    Args:
        path: 待检查的文件或目录路径。

    Returns:
        bool: 若路径包含被排除的目录片段，则返回 True。
    """
    for part in path.parts:
        if part.lower() in IGNORED_DIR_SEGMENTS:
            return True
    return False


def _check_file(path: Path) -> str:
    """读取文件并执行基础有效性检查。

    Args:
        path: 已解析的文件路径。

    Returns:
        str: 文件内容（若超长会自动截断）。

    Raises:
        ValueError: 文件为空、仅含空白、为二进制文件或过大。
        RuntimeError: 读取失败。
    """
    if _should_ignore(path):
        raise ValueError(f"路径位于被排除的目录中: {path}")

    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        raise ValueError(f"不支持评审二进制文件 [{path.suffix}]: {path}")

    try:
        file_size = path.stat().st_size
    except OSError as exc:
        logger.error("获取文件大小失败 [%s]: %s", path, exc)
        raise RuntimeError(f"获取文件大小失败 [{path}]: {exc}") from exc

    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"文件过大 ({file_size / 1024:.1f} KB)，"
            f"超过 {MAX_FILE_SIZE / 1024:.0f} KB 限制: {path}"
        )

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except OSError as exc:
        logger.error("读取文档失败 [%s]: %s", path, exc)
        raise RuntimeError(f"读取文档失败 [{path}]: {exc}") from exc

    if not content.strip():
        raise ValueError(f"文档内容为空或仅含空白字符: {path}")

    if len(content) > MAX_CHARS:
        logger.warning(
            "文件内容过长 (%d 字符)，已截断至 %d 字符",
            len(content),
            MAX_CHARS,
        )
        content = content[:MAX_CHARS] + "\n\n...（内容已截断）"

    if suffix not in (".md", ".txt", ".markdown"):
        logger.warning(
            "文件扩展名为 [%s]，非标准 Markdown/Text 格式，"
            "评审效果可能不佳: %s",
            path.suffix,
            path,
        )

    return content


def review(
    file_path: str,
    instruction: str | None = None,
    output_format: str = "markdown",
) -> str:
    """对指定文档执行轻量盲审。

    读取文档内容后，以 ``reviewer_system`` 为角色设定，调用独立 API
    返回一次性评审意见。若用户提供了定向指令，则将其追加到 prompt
    中，实现精准评审。

    Args:
        file_path: 待评审文档的绝对或相对路径。
        instruction: 用户追加的定向指令，如 ``"重点审查第三章并发模型"``。
        output_format: 输出格式，``"markdown"`` 或 ``"json"``，默认 ``"markdown"``。

    Returns:
        str: 模型返回的 Markdown 或 JSON 格式评审意见。

    Raises:
        FileNotFoundError: 指定文档不存在。
        ValueError: 文档内容为空。
        RuntimeError: 配置缺失或 API 调用异常。
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到待评审文档: {path}")

    doc_content = _check_file(path)

    api_settings = load_api_settings()
    prompts = load_prompts()
    routing = api_settings.get("runtime_routing", {})
    channels = api_settings.get("channels", {})

    reviewer_channel_name = routing.get("reviewer_channel", "deepseek")
    reviewer_cfg = channels.get(reviewer_channel_name)
    if not reviewer_cfg:
        raise RuntimeError(
            f"配置中找不到评审通道 [{reviewer_channel_name}]，"
            f"请检查 api_settings.json 的 channels 定义。"
        )

    adapter, model = init_api_client(reviewer_cfg)
    temperature = routing.get("temperature", 0.3)
    system_prompt = prompts.get("reviewer_system", "")

    user_content_parts = [
        "请盲审以下技术文档，直接指出其中的漏洞与不合理之处。",
    ]
    if instruction:
        user_content_parts.append(f"\n【用户定向关注点】\n{instruction}")
    user_content_parts.append(f"\n【待评审文档内容】\n\n{doc_content}")
    user_content = "\n".join(user_content_parts)

    logger.info(
        "启动轻量盲审: file=%s, model=%s, instruction=%s",
        path,
        model,
        bool(instruction),
    )
    feedback = ask_agent(
        adapter, model, system_prompt, user_content, temperature,
    )
    logger.info("盲审完成: file=%s", path)

    if output_format == "json":
        return json.dumps(
            {
                "file": str(path),
                "model": model,
                "feedback": feedback,
            },
            ensure_ascii=False,
            indent=2,
        )
    return feedback


def debate(
    file_path: str,
    rounds: int = 2,
    output_dir: str = "outputs",
    output_format: str = "markdown",
    instruction: str | None = None,
) -> str:
    """执行完整多轮闭环博弈，输出经过交叉验证的设计文档。

    流程：
    1. architect 根据文档/需求出初稿；
    2. reviewer 盲审并给出意见；
    3. architect 根据意见修复；
    4. 重复步骤 2-3 共 ``rounds`` 轮；
    5. 输出最终文档到 ``outputs/DESIGN_DOCUMENT.md``。

    Args:
        file_path: 初始需求或设计文档路径。
        rounds: 迭代轮数，默认 2。
        output_dir: 输出目录，默认 ``outputs``。
        output_format: 输出格式，``"markdown"`` 或 ``"json"``，默认 ``"markdown"``。
        instruction: 用户追加的定向关注点，会拼接到 architect 的初始需求中。

    Returns:
        str: 最终输出文件的绝对路径，或 JSON 字符串。

    Raises:
        FileNotFoundError: 输入文档不存在。
        ValueError: 文档内容为空。
        RuntimeError: 配置缺失或 API 调用异常。
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到输入文档: {path}")

    requirement = _check_file(path)

    api_settings = load_api_settings()
    prompts = load_prompts()
    routing = api_settings.get("runtime_routing", {})
    channels = api_settings.get("channels", {})

    arch_channel_name = routing.get("architect_channel", "kimi")
    rev_channel_name = routing.get("reviewer_channel", "deepseek")
    arch_cfg = channels.get(arch_channel_name)
    rev_cfg = channels.get(rev_channel_name)

    if not arch_cfg or not rev_cfg:
        raise RuntimeError(
            "配置中找不到 architect_channel 或 reviewer_channel，"
            "请检查 api_settings.json 的 runtime_routing 定义。"
        )

    adapter_arch, arch_model = init_api_client(arch_cfg)
    adapter_rev, rev_model = init_api_client(rev_cfg)
    temperature = routing.get("temperature", 0.3)
    max_rounds = rounds  # cli.py 已确保 rounds >= 1

    logger.info(
        "启动多轮闭环博弈: architect=%s, reviewer=%s, rounds=%d",
        arch_model,
        rev_model,
        max_rounds,
    )

    architect_input = f"原始需求：{requirement}"
    if instruction:
        architect_input += f"\n\n【用户定向关注点】\n{instruction}"

    logger.info("[初始化] 调用【%s】构建初始技术方案...", arch_model)
    current_doc = ask_agent(
        adapter_arch,
        arch_model,
        prompts.get("architect_system", ""),
        architect_input,
        temperature,
    )

    for r in range(1, max_rounds + 1):
        logger.info(
            "[第 %d/%d 轮] 调用【%s】盲审...",
            r,
            max_rounds,
            rev_model,
        )
        reviewer_prompt_parts = [
            "请盲审以下技术文档，直接指出其中的漏洞与不合理之处。",
        ]
        if instruction:
            reviewer_prompt_parts.append(f"\n【用户定向关注点】\n{instruction}")
        reviewer_prompt_parts.append(f"\n\n【待评审文档内容】\n\n{current_doc}")
        reviewer_prompt = "\n".join(reviewer_prompt_parts)

        feedback = ask_agent(
            adapter_rev,
            rev_model,
            prompts.get("reviewer_system", ""),
            reviewer_prompt,
            temperature,
        )

        logger.info(
            "[第 %d/%d 轮] 调用【%s】修复...",
            r,
            max_rounds,
            arch_model,
        )
        architect_input = (
            f"这是你前一版的设计文档：\n\n{current_doc}\n\n"
            f"这是外部独立审计专家给出的修改意见：\n\n{feedback}\n\n"
            f"请结合上述意见，输出优化后的全新一版技术设计文档。"
        )
        current_doc = ask_agent(
            adapter_arch,
            arch_model,
            prompts.get("architect_system", ""),
            architect_input,
            temperature,
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "DESIGN_DOCUMENT.md"

    try:
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write(current_doc)
    except OSError as exc:
        logger.error("写入输出文件失败 [%s]: %s", output_path, exc)
        raise RuntimeError(f"写入输出文件失败 [{output_path}]: {exc}") from exc

    logger.info("交叉验证迭代结束，文档已输出至: %s", output_path.resolve())

    if output_format == "json":
        return json.dumps(
            {
                "file": str(path),
                "output_path": str(output_path.resolve()),
                "rounds": max_rounds,
                "model": arch_model,
            },
            ensure_ascii=False,
            indent=2,
        )
    return str(output_path.resolve())
