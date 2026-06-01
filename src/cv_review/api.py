"""OpenAI / Anthropic 兼容 API 客户端封装模块。

采用**适配器模式**将不同 SDK 的差异隔离在各自的 Adapter 中，
上层 ``ask_agent`` 只与统一的 ``ApiClientAdapter`` 接口交互，
无需关心底层是 OpenAI 还是 Anthropic。

同时提供通道初始化与单次无状态调用的能力，确保每次请求都携带独立的
system prompt + user content，与外部上下文彻底物理隔离。
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class RetryableError(RuntimeError):
    """网络或服务端瞬时错误，允许触发指数退避重试。"""


class ApiClientAdapter(ABC):
    """API 客户端适配器抽象基类。

    屏蔽 OpenAI、Anthropic 等不同 SDK 的差异，向上层提供统一的
    ``chat()`` 接口。
    """

    @abstractmethod
    def chat(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        """发起单次对话请求并返回模型生成的文本。

        Args:
            model: 模型名称。
            system_prompt: 系统级角色设定。
            user_content: 当前用户输入。
            temperature: 采样温度。
            timeout: 请求超时（秒）。

        Returns:
            str: 模型生成的文本内容。

        Raises:
            RetryableError: 网络连接、超时等可重试错误。
            RuntimeError: 业务逻辑错误或响应结构异常。
        """
        ...


class OpenAIAdapter(ApiClientAdapter):
    """OpenAI SDK 适配器。"""

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    def chat(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as exc:
            # OpenAI SDK 1.0+ 的网络异常通常继承自 APIConnectionError / APITimeoutError
            exc_name = type(exc).__name__
            if "Connection" in exc_name or "Timeout" in exc_name or "Network" in exc_name:
                logger.warning("OpenAI 网络异常: %s", exc)
                raise RetryableError(f"OpenAI 网络异常: {exc}") from exc
            logger.error("OpenAI 业务异常: %s", exc)
            raise RuntimeError(f"OpenAI 业务异常: {exc}") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError(f"OpenAI 响应结构异常: {exc}") from exc

        if content is None:
            raise RuntimeError("模型返回了空内容（content is None）")
        return content


class AnthropicAdapter(ApiClientAdapter):
    """Anthropic SDK 适配器。"""

    def __init__(self, client: Any) -> None:
        """Args:
            client: ``anthropic.Anthropic`` 实例。
        """
        self._client = client

    def chat(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": user_content}],
                system=system_prompt,
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            if "Connection" in exc_name or "Timeout" in exc_name or "Network" in exc_name:
                logger.warning("Anthropic 网络异常: %s", exc)
                raise RetryableError(f"Anthropic 网络异常: {exc}") from exc
            logger.error("Anthropic 业务异常: %s", exc)
            raise RuntimeError(f"Anthropic 业务异常: {exc}") from exc

        try:
            content = response.content[0].text
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Anthropic 响应结构异常: {exc}") from exc

        if not content:
            raise RuntimeError("模型返回了空内容（content is empty）")
        return content


def _mask_key(key: str) -> str:
    """对 API Key 进行脱敏显示。

    Args:
        key: 原始 API Key。

    Returns:
        str: 脱敏后的 Key，如 ``sk-...xxxx``。
    """
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


def init_api_client(channel_config: dict[str, Any]) -> tuple[ApiClientAdapter, str]:
    """根据通道配置初始化对应的 API 客户端适配器。

    API Key 统一通过环境变量读取（由 ``python-dotenv`` 自动加载 ``.env`` 文件
    到环境变量）。禁止在配置文件中直接写入明文密钥。

    Args:
        channel_config: 单个通道的字典，至少包含：
            - ``base_url``: API 基础地址。
            - ``model_name``: 请求时使用的模型名。
            - ``api_key_env``: 环境变量名（必填）。
            - ``api_format``: API 格式，``openai``（默认）或 ``anthropic``。

    Returns:
        tuple: ``(适配器实例, 模型名称字符串)``

    Raises:
        RuntimeError: 缺少 API Key、依赖未安装或客户端初始化失败。
    """
    api_format = channel_config.get("api_format", "openai")

    api_key_env = channel_config.get("api_key_env")
    if not api_key_env:
        raise RuntimeError(
            "通道配置缺少 'api_key_env' 字段，"
            "请在 api_settings.json 中设置环境变量名。"
        )

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"未检测到环境变量 [{api_key_env}]，"
            f"请在项目根目录创建 .env 文件并写入 [{api_key_env}=sk-xxx]，"
            f"或在系统环境变量中配置该变量后再试。"
        )

    base_url = channel_config.get("base_url", "")
    model_name = channel_config.get("model_name", "")

    if api_format == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "当前通道需要 anthropic SDK，请执行 `pip install cv-review[anthropic]` 安装。"
            ) from exc
        try:
            raw_client = Anthropic(api_key=api_key, base_url=base_url)
        except Exception as exc:
            logger.exception(
                "初始化 Anthropic 客户端失败 [%s]: %s", model_name, exc
            )
            raise RuntimeError(
                f"初始化 Anthropic 客户端失败: {exc}"
            ) from exc
        adapter: ApiClientAdapter = AnthropicAdapter(raw_client)
    else:
        try:
            raw_client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as exc:
            logger.exception(
                "初始化 OpenAI 客户端失败 [%s]: %s", model_name, exc
            )
            raise RuntimeError(
                f"初始化 OpenAI 客户端失败: {exc}"
            ) from exc
        adapter = OpenAIAdapter(raw_client)

    logger.debug(
        "API 客户端初始化成功: model=%s, base_url=%s, format=%s, key=%s",
        model_name,
        base_url,
        api_format,
        _mask_key(api_key),
    )
    return adapter, model_name


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RetryableError),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "API 调用失败，第 %d 次重试...",
        retry_state.attempt_number,
    ),
)
def ask_agent(
    adapter: ApiClientAdapter,
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float,
    timeout: int = 300,
) -> str:
    """向指定模型发起单次无状态对话请求。

    每次调用仅传递 system prompt 与当前 user content，不携带任何历史
    上下文，确保盲审的绝对隔离性。

    内置指数退避重试策略：最多 3 次，等待时间 2s → 4s → 8s。
    **仅对网络瞬时错误（``RetryableError``）触发重试**，业务逻辑错误
    （如参数非法、响应结构异常、模型返回空内容）会直接抛出，避免无意义等待。

    Args:
        adapter: 已初始化的 API 客户端适配器。
        model: 模型名称。
        system_prompt: 系统级角色设定文本。
        user_content: 当前轮次的用户输入内容。
        temperature: 采样温度，控制输出的随机性。
        timeout: 请求超时时间（秒），默认 300。

    Returns:
        str: 模型生成的文本内容。

    Raises:
        ValueError: temperature 超出合法范围 [0, 2]。
        RuntimeError: API 调用过程中发生不可恢复的业务或逻辑异常。
        RetryableError: 网络瞬时错误（由 ``@retry`` 自动处理，通常不会传递到调用方）。
    """
    if not (0 <= temperature <= 2):
        raise ValueError(
            f"temperature 必须在 0~2 之间，当前值: {temperature}"
        )

    try:
        return adapter.chat(
            model=model,
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
            timeout=timeout,
        )
    except RetryableError:
        raise  # 交由 @retry 处理
    except RuntimeError:
        raise  # 直接向上抛出，不被重试
    except Exception as exc:
        logger.exception("API 调用未知异常 [%s]: %s", model, exc)
        raise RuntimeError(
            f"API 调用未知异常 [{model}]: {exc}"
        ) from exc
