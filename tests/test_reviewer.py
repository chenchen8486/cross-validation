"""评审逻辑模块的单元测试。

验证空文件检查、非标准格式警告以及 JSON 输出格式。
"""

import json
from pathlib import Path

import pytest

from cv_review.reviewer import _check_file


class TestCheckFile:
    """测试 ``_check_file()`` 的基础有效性检查。"""

    def test_empty_file_raises_value_error(self, tmp_path):
        """空文件（仅含空白）应抛出 ValueError。"""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("   \n   ", encoding="utf-8-sig")

        with pytest.raises(ValueError, match="文档内容为空"):
            _check_file(empty_file)

    def test_non_markdown_logs_warning(self, tmp_path, caplog):
        """非 Markdown/Text 扩展名应记录警告，但不阻止读取。"""
        py_file = tmp_path / "script.py"
        py_file.write_text("# some code", encoding="utf-8-sig")

        with caplog.at_level("WARNING"):
            content = _check_file(py_file)

        assert content == "# some code"
        assert "非标准 Markdown/Text 格式" in caplog.text

    def test_valid_markdown_file(self, tmp_path):
        """正常 Markdown 文件应成功读取并返回内容。"""
        md_file = tmp_path / "design.md"
        md_file.write_text("# 标题\n正文", encoding="utf-8-sig")

        content = _check_file(md_file)
        assert "# 标题" in content


class TestReviewOutputFormat:
    """测试 ``review()`` 的 output_format 参数。"""

    @pytest.fixture
    def mock_settings(self, monkeypatch):
        """Mock 配置与 API 调用，避免真实网络请求。"""
        import cv_review.reviewer as reviewer_module
        import cv_review.config as config_module

        monkeypatch.setattr(
            config_module,
            "load_api_settings",
            lambda: {
                "channels": {
                    "test": {
                        "base_url": "https://api.test.com",
                        "api_key_env": "TEST_KEY",
                        "model_name": "test-model",
                    }
                },
                "runtime_routing": {
                    "reviewer_channel": "test",
                    "temperature": 0.3,
                },
            },
        )
        monkeypatch.setattr(config_module, "load_prompts", lambda: {"reviewer_system": "sys"})
        monkeypatch.setattr(
            reviewer_module,
            "init_api_client",
            lambda cfg: (None, "test-model"),
        )
        monkeypatch.setattr(
            reviewer_module,
            "ask_agent",
            lambda *a, **k: "评审意见",
        )

    def test_json_output(self, tmp_path, mock_settings):
        """output_format='json' 时应返回结构化 JSON 字符串。"""
        from cv_review.reviewer import review

        md_file = tmp_path / "doc.md"
        md_file.write_text("# 文档", encoding="utf-8-sig")

        result = review(str(md_file), output_format="json")
        data = json.loads(result)
        assert data["model"] == "test-model"
        assert data["feedback"] == "评审意见"
        assert "file" in data

    def test_markdown_output(self, tmp_path, mock_settings):
        """output_format='markdown' 时应返回原始文本。"""
        from cv_review.reviewer import review

        md_file = tmp_path / "doc.md"
        md_file.write_text("# 文档", encoding="utf-8-sig")

        result = review(str(md_file), output_format="markdown")
        assert result == "评审意见"
