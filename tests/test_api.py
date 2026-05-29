"""API 客户端封装模块的单元测试。

验证重试装饰器、超时参数以及异常处理逻辑。
"""

import logging
from unittest.mock import MagicMock

import pytest

from cv_review.api import ask_agent


class TestAskAgentRetry:
    """测试 ``ask_agent()`` 的 tenacity 重试策略。"""

    def test_retry_success_on_third_attempt(self):
        """前两次调用失败，第三次成功，应返回正确结果。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("模拟网络异常"),
            Exception("模拟超时"),
            MagicMock(
                choices=[MagicMock(message=MagicMock(content="评审意见文本"))]
            ),
        ]

        result = ask_agent(
            mock_client, "deepseek-chat", "system prompt", "user content", 0.3
        )
        assert result == "评审意见文本"
        assert mock_client.chat.completions.create.call_count == 3

    def test_retry_exhausted_raises_runtime_error(self):
        """连续 3 次失败，应最终抛出 RuntimeError。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Persistent failure"
        )

        with pytest.raises(RuntimeError, match="API 调用异常"):
            ask_agent(
                mock_client, "deepseek-chat", "system prompt", "user content", 0.3
            )

        assert mock_client.chat.completions.create.call_count == 3

    def test_timeout_argument_passed(self):
        """验证 timeout=60 被正确传递给 API 调用。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )

        ask_agent(mock_client, "m", "s", "u", 0.3)

        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs.get("timeout") == 60

    def test_content_none_raises_runtime_error(self):
        """模型返回 content=None 时应抛出 RuntimeError。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=None))]
        )

        with pytest.raises(RuntimeError, match="模型返回了空内容"):
            ask_agent(mock_client, "m", "s", "u", 0.3)
