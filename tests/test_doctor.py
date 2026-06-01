"""doctor module unit tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cv_review.doctor import (
    _check_cli_availability,
    _check_slash_commands,
    _check_user_config,
    _check_env_and_keys,
    _check_api_settings,
    run_diagnosis,
    SLASH_COMMAND_FILES,
    COMMANDS_DIR,
)


class TestCheckCliAvailability:
    """Test CLI availability check."""

    def test_returns_true_when_cli_works(self) -> None:
        """Should return True when cv-review --help exits with 0."""
        with patch(
            "cv_review.doctor.subprocess.run",
            return_value=type("R", (), {"returncode": 0})(),
        ):
            assert _check_cli_availability() is True

    def test_returns_false_when_not_found(self) -> None:
        """Should return False when command is not found."""
        with patch(
            "cv_review.doctor.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert _check_cli_availability() is False


class TestCheckSlashCommands:
    """Test Slash Command deployment check."""

    def test_all_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when all files exist."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()
        for fname in SLASH_COMMAND_FILES:
            (cmd_dir / fname).write_text("", encoding="utf-8")

        monkeypatch.setattr("cv_review.doctor.COMMANDS_DIR", cmd_dir)
        ok, missing = _check_slash_commands()
        assert ok is True
        assert missing == []

    def test_missing_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False and list missing files."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()
        (cmd_dir / "cv.md").write_text("", encoding="utf-8")

        monkeypatch.setattr("cv_review.doctor.COMMANDS_DIR", cmd_dir)
        ok, missing = _check_slash_commands()
        assert ok is False
        assert "cv_help.md" in missing
        assert "cv_debate.md" in missing


class TestCheckUserConfig:
    """Test user config directory check."""

    def test_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when directory exists."""
        cfg_dir = tmp_path / ".cv-review"
        cfg_dir.mkdir()
        monkeypatch.setattr(
            "cv_review.doctor._get_user_config_dir", lambda: cfg_dir
        )
        exists, path = _check_user_config()
        assert exists is True
        assert path == cfg_dir

    def test_not_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when directory does not exist."""
        cfg_dir = tmp_path / ".cv-review"
        monkeypatch.setattr(
            "cv_review.doctor._get_user_config_dir", lambda: cfg_dir
        )
        exists, path = _check_user_config()
        assert exists is False


class TestCheckEnvAndKeys:
    """Test environment variable and API Key check."""

    def test_detects_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when at least one key exists."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        ok, found = _check_env_and_keys()
        assert ok is True
        assert "DEEPSEEK_API_KEY" in found

    def test_no_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when no keys are present."""
        for k in ["ANTHROPIC_AUTH_TOKEN", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "KIMI_API_KEY"]:
            monkeypatch.delenv(k, raising=False)
        # Prevent python-dotenv from loading project root .env
        monkeypatch.setattr("cv_review.doctor._load_dotenv_files", lambda: None)
        ok, found = _check_env_and_keys()
        assert ok is False
        assert found == []


class TestCheckApiSettings:
    """Test api_settings.json structure validation."""

    def test_valid_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True for valid configuration."""
        cfg_dir = tmp_path / ".cv-review"
        cfg_dir.mkdir()
        settings = {
            "channels": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "model_name": "deepseek-chat",
                    "api_key_env": "DEEPSEEK_API_KEY",
                }
            },
            "runtime_routing": {
                "architect_channel": "deepseek",
                "reviewer_channel": "deepseek",
                "temperature": 0.3,
            },
        }
        (cfg_dir / "api_settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        monkeypatch.setattr(
            "cv_review.doctor._get_user_config_dir", lambda: cfg_dir
        )
        ok, err = _check_api_settings()
        assert ok is True
        assert err == ""

    def test_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when file does not exist."""
        cfg_dir = tmp_path / ".cv-review"
        cfg_dir.mkdir()

        def _raise_file_not_found(filename: str) -> Path:
            raise FileNotFoundError(f"missing {filename}")

        monkeypatch.setattr(
            "cv_review.config._resolve_config_path", _raise_file_not_found
        )
        ok, err = _check_api_settings()
        assert ok is False
        assert "找不到 api_settings.json" in err


class TestRunDiagnosis:
    """Test full diagnosis flow return codes."""

    def test_returns_zero_when_all_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return 0 when everything is ready."""
        monkeypatch.setattr("cv_review.doctor._check_cli_availability", lambda: True)
        monkeypatch.setattr(
            "cv_review.doctor._check_slash_commands", lambda: (True, [])
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_user_config",
            lambda: (True, tmp_path / ".cv-review"),
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_env_and_keys",
            lambda: (True, ["DEEPSEEK_API_KEY"]),
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_api_settings", lambda: (True, "")
        )

        assert run_diagnosis() == 0

    def test_returns_one_when_any_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return 1 when any check fails."""
        monkeypatch.setattr("cv_review.doctor._check_cli_availability", lambda: False)
        monkeypatch.setattr(
            "cv_review.doctor._check_slash_commands", lambda: (True, [])
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_user_config",
            lambda: (True, tmp_path / ".cv-review"),
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_env_and_keys", lambda: (True, [])
        )
        monkeypatch.setattr(
            "cv_review.doctor._check_api_settings", lambda: (True, "")
        )

        assert run_diagnosis() == 1
