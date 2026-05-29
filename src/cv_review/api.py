"""OpenAI 兼容 API 客户端封装模块。

提供通道初始化与单次无状态调用的能力，确保每次请求都携带独立的
system prompt + user content，与外部上下文彻底物理隔离。
"""

import logging
import os
from typing import Any

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def init_api_client(channel_config: dict[str, Any]) -> tuple[OpenAI, str]:
    """根据通道配置初始化对应的 API 客户端。

    Args:
        channel_config: 单个通道的字典，至少包含：
            - ``base_url``: API 基础地址。
            - ``api_key_env``: 存储 API Key 的环境变量名。
            - ``model_name``: 请求时使用的模型名。

    Returns:
        tuple: ``(OpenAI 客户端实例, 模型名称字符串)``

    Raises:
        RuntimeError: 环境变量未配置或客户端初始化失败。
    """
    api_key_env = channel_config.get("api_key_env")
    if not api_key_env:
        raise RuntimeError("通道配置缺少必需字段: api_key_env")

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"未检测到环境变量 [{api_key_env}]，"
            f"请在 Shell 中配置该变量后再试。"
        )

    base_url = channel_config.get("base_url", "")
    model_name = channel_config.get("model_name", "")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as exc:
        logger.exception("初始化 API 客户端失败 [%s]: %s", model_name, exc)
        raise RuntimeError(f"初始化 API 客户端失败: {exc}") from exc

    logger.debug("API 客户端初始化成功: model=%s, base_url=%s", model_name, base_url)
    return client, model_name


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "API 调用失败 [%s]，第 %d 次重试...",
        retry_state.args[1] if len(retry_state.args) > 1 else "unknown",
        retry_state.attempt_number,
    ),
)
def ask_agent(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float,
) -> str:
    """向指定模型发起单次无状态对话请求。

    每次调用仅传递 system prompt 与当前 user content，不携带任何历史
    上下文，确保盲审的绝对隔离性。

    内置指数退避重试策略：最多 3 次，等待时间 2s → 4s → 8s。

    Args:
        client: 已初始化的 OpenAI 兼容客户端。
        model: 模型名称。
        system_prompt: 系统级角色设定文本。
        user_content: 当前轮次的用户输入内容。
        temperature: 采样温度，控制输出的随机性。

    Returns:
        str: 模型生成的文本内容。

    Raises:
        RuntimeError: API 调用过程中发生网络或逻辑异常，且重试全部失败。
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            timeout=60,
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("模型返回了空内容（content is None）")
        return content
    except Exception as exc:
        logger.exception("API 调用异常 [%s]: %s", model, exc)
        raise RuntimeError(f"API 调用异常 [{model}]: {exc}") from exc
