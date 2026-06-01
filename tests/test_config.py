"""配置加载模块的单元测试。

验证用户级配置初始化、内置默认配置回退、以及 prompts.txt 解析逻辑。
"""

import json
import tempfile
from pathlib import Path

import pytest

from cv_review import config


class TestInitUserConfig:
    """测试 ``init_user_config()`` 初始化行为。"""

    def test_creates_user_config_dir(self, monkeypatch):
        """首次调用应在临时目录中创建配置文件夹及默认模板。"""
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr(
                config, "_get_user_config_dir", lambda: Path(tmp) / ".cv-review"
            )
            result = config.init_user_config()
            assert result.exists()
            assert (result / "api_settings.json").exists()
            assert (result / "prompts.txt").exists()

    def test_skips_existing_files(self, monkeypatch):
        """目标文件已存在时不应覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp) / ".cv-review"
            user_dir.mkdir()
            (user_dir / "api_settings.json").write_text("{}", encoding="utf-8-sig")

            monkeypatch.setattr(
                config, "_get_user_config_dir", lambda: user_dir
            )
            config.init_user_config()
            content = (user_dir / "api_settings.json").read_text(encoding="utf-8-sig")
            assert content == "{}"


class TestResolveConfigPath:
    """测试配置路径优先级解析。"""

    def test_prefers_user_config(self, monkeypatch):
        """用户级配置存在时应优先使用。"""
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp) / ".cv-review"
            user_dir.mkdir()
            user_file = user_dir / "api_settings.json"
            user_file.write_text('{"user": true}', encoding="utf-8-sig")

            monkeypatch.setattr(
                config, "_get_user_config_dir", lambda: user_dir
            )
            resolved = config._resolve_config_path("api_settings.json")
            assert resolved == user_file

    def test_fallback_to_builtin(self, monkeypatch):
        """用户级配置缺失时应回退到内置默认。"""
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp) / ".cv-review"
            # 不创建 user_dir，强制回退
            monkeypatch.setattr(
                config, "_get_user_config_dir", lambda: user_dir
            )
            resolved = config._resolve_config_path("api_settings.json")
            assert resolved.exists()
            assert "config" in str(resolved)

    def test_raises_when_missing(self, monkeypatch):
        """用户级与内置目录均缺失时应抛出 FileNotFoundError。"""
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr(
                config, "_get_user_config_dir", lambda: Path(tmp) / ".cv-review"
            )
            monkeypatch.setattr(
                config, "_get_builtin_config_dir", lambda: Path(tmp) / "builtin"
            )
            with pytest.raises(FileNotFoundError):
                config._resolve_config_path("nonexistent.json")


class TestLoadPrompts:
    """测试 ``load_prompts()`` 的文本格式解析。"""

    def test_parses_sections_correctly(self):
        """应正确提取 [section] 及其后续多行内容。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write("[architect_system]\n你是架构师。\n\n[reviewer_system]\n你是评审员。\n")
            tmp_path = f.name

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            config, "_resolve_config_path", lambda _name: Path(tmp_path)
        )
        try:
            prompts = config.load_prompts()
            assert "architect_system" in prompts
            assert "reviewer_system" in prompts
            assert "你是架构师。" in prompts["architect_system"]
            assert "你是评审员。" in prompts["reviewer_system"]
        finally:
            monkeypatch.undo()
            Path(tmp_path).unlink()


class TestValidateApiSettings:
    """测试 ``_validate_api_settings()`` 的字段校验逻辑。"""

    def setup_method(self):
        """每个测试前清除配置加载缓存，避免 lru_cache 导致测试隔离失效。"""
        config.load_api_settings.cache_clear()
        config.load_prompts.cache_clear()

    def _make_valid(self) -> dict:
        """构造一个最小合法的 api_settings 字典。"""
        return {
            "channels": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "model_name": "deepseek-chat",
                }
            },
            "runtime_routing": {
                "architect_channel": "deepseek",
                "reviewer_channel": "deepseek",
            },
        }

    def test_accepts_api_key_env(self):
        """配置 ``api_key_env`` 时应通过校验。"""
        data = self._make_valid()
        config._validate_api_settings(data)

    def test_rejects_missing_api_key_env(self):
        """缺少 ``api_key_env`` 时应报错。"""
        data = self._make_valid()
        del data["channels"]["deepseek"]["api_key_env"]
        with pytest.raises(RuntimeError, match="缺少必需字段 'api_key_env'"):
            config._validate_api_settings(data)
