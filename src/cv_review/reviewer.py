"""评审逻辑模块，提供轻量盲审与完整多轮闭环博弈两种模式。

轻量模式（默认）仅调用一次 reviewer 通道，对输入文档进行独立盲审，
成本最低、响应最快；完整闭环模式则复用 architect + reviewer 双通道
进行多轮迭代，输出经过交叉验证的高置信度设计文档。
"""

import logging
import os
from pathlib import Path
from typing import Any

from cv_review.config import init_user_config, load_api_settings, load_prompts
from cv_review.api import init_api_client, ask_agent

logger = logging.getLogger(__name__)


def review(file_path: str, instruction: str | None = None) -> str:
    """对指定文档执行轻量盲审。

    读取文档内容后，以 ``reviewer_system`` 为角色设定，调用独立 API
    返回一次性评审意见。若用户提供了定向指令，则将其追加到 prompt
    中，实现精准评审。

    Args:
        file_path: 待评审文档的绝对或相对路径。
        instruction: 用户追加的定向指令，如 ``"重点审查第三章并发模型"``。

    Returns:
        str: 模型返回的 Markdown 格式评审意见。

    Raises:
        FileNotFoundError: 指定文档不存在。
        RuntimeError: 配置缺失或 API 调用异常。
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到待评审文档: {path}")

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            doc_content = f.read()
    except OSError as exc:
        logger.error("读取文档失败 [%s]: %s", path, exc)
        raise RuntimeError(f"读取文档失败 [{path}]: {exc}") from exc

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

    client, model = init_api_client(reviewer_cfg)
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
    feedback = ask_agent(client, model, system_prompt, user_content, temperature)
    logger.info("盲审完成: file=%s", path)
    return feedback


def debate(
    file_path: str,
    rounds: int = 2,
    output_dir: str = "outputs",
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

    Returns:
        str: 最终输出文件的绝对路径。

    Raises:
        FileNotFoundError: 输入文档不存在。
        RuntimeError: 配置缺失或 API 调用异常。
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到输入文档: {path}")

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            requirement = f.read()
    except OSError as exc:
        logger.error("读取输入文档失败 [%s]: %s", path, exc)
        raise RuntimeError(f"读取输入文档失败 [{path}]: {exc}") from exc

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

    arch_client, arch_model = init_api_client(arch_cfg)
    rev_client, rev_model = init_api_client(rev_cfg)
    temperature = routing.get("temperature", 0.3)
    max_rounds = rounds if rounds > 0 else routing.get("max_rounds", 2)

    logger.info(
        "启动多轮闭环博弈: architect=%s, reviewer=%s, rounds=%d",
        arch_model,
        rev_model,
        max_rounds,
    )

    logger.info("[1/3] 调用【%s】构建初始技术方案...", arch_model)
    current_doc = ask_agent(
        arch_client,
        arch_model,
        prompts.get("architect_system", ""),
        f"原始需求：{requirement}",
        temperature,
    )

    for r in range(1, max_rounds + 1):
        logger.info(
            "[2/3] 第 %d 轮交叉验证：调用【%s】盲审...", r, rev_model
        )
        feedback = ask_agent(
            rev_client,
            rev_model,
            prompts.get("reviewer_system", ""),
            f"请盲审以下技术文档，直接指出其中的漏洞与不合理之处：\n\n{current_doc}",
            temperature,
        )

        logger.info(
            "[3/3] 第 %d 轮审计意见返回，交由【%s】修复...", r, arch_model
        )
        architect_input = (
            f"这是你前一版的设计文档：\n\n{current_doc}\n\n"
            f"这是外部独立审计专家给出的修改意见：\n\n{feedback}\n\n"
            f"请结合上述意见，输出优化后的全新一版技术设计文档。"
        )
        current_doc = ask_agent(
            arch_client,
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
    return str(output_path.resolve())
