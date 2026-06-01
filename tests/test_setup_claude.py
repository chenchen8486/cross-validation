"""setup_claude module unit tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cv_review.setup_claude import (
    _find_source_docs_dir,
    deploy_slash_commands,
    SLASH_COMMAND_FILES,
    COMMANDS_DIR,
)


class TestFindSourceDocsDir:
    """Test _find_source_docs_dir lookup strategies."""

    def test_finds_from_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should prefer cwd/docs/ when it exists and contains cv.md."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "cv.md").write_text("test", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = _find_source_docs_dir()
        assert result == docs_dir

    def test_raises_when_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should raise RuntimeError when all strategies fail."""
        monkeypatch.chdir(tmp_path)
        # Ensure editable fallback also fails by pointing __file__ to a location
        # where ../../docs does not exist.
        fake_file = tmp_path / "src" / "cv_review" / "setup_claude.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.write_text("", encoding="utf-8")

        with patch("cv_review.setup_claude.__file__", str(fake_file)):
            with pytest.raises(RuntimeError) as exc_info:
                _find_source_docs_dir()
            assert "找不到工程 docs/ 目录" in str(exc_info.value)


class TestDeploySlashCommands:
    """Test deploy_slash_commands behavior."""

    def _create_all_source_files(self, docs_dir: Path) -> None:
        """Helper: create all required source files."""
        for fname in SLASH_COMMAND_FILES:
            (docs_dir / fname).write_text(f"content of {fname}", encoding="utf-8")

    def test_creates_commands_dir_and_copies_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should create target dir and copy all files when it does not exist."""
        src_docs = tmp_path / "docs"
        src_docs.mkdir()
        self._create_all_source_files(src_docs)

        monkeypatch.chdir(tmp_path)
        target_dir = tmp_path / ".claude" / "commands"
        monkeypatch.setattr(
            "cv_review.setup_claude.COMMANDS_DIR", target_dir
        )

        result = deploy_slash_commands()
        assert result == target_dir
        assert target_dir.exists()
        for fname in SLASH_COMMAND_FILES:
            assert (target_dir / fname).exists()
            assert (target_dir / fname).read_text(encoding="utf-8") == f"content of {fname}"

    def test_skips_existing_when_not_forced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should skip existing files when force=False."""
        src_docs = tmp_path / "docs"
        src_docs.mkdir()
        self._create_all_source_files(src_docs)

        target_dir = tmp_path / ".claude" / "commands"
        target_dir.mkdir(parents=True)
        (target_dir / "cv.md").write_text("old", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "cv_review.setup_claude.COMMANDS_DIR", target_dir
        )

        deploy_slash_commands(force=False)
        assert (target_dir / "cv.md").read_text(encoding="utf-8") == "old"

    def test_overwrites_when_forced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should overwrite existing files when force=True."""
        src_docs = tmp_path / "docs"
        src_docs.mkdir()
        self._create_all_source_files(src_docs)

        target_dir = tmp_path / ".claude" / "commands"
        target_dir.mkdir(parents=True)
        (target_dir / "cv.md").write_text("old", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "cv_review.setup_claude.COMMANDS_DIR", target_dir
        )

        deploy_slash_commands(force=True)
        assert (target_dir / "cv.md").read_text(encoding="utf-8") == "content of cv.md"

    def test_raises_on_missing_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should raise RuntimeError when a source file is missing."""
        src_docs = tmp_path / "docs"
        src_docs.mkdir()
        # Only create two files, intentionally missing one
        (src_docs / "cv.md").write_text("", encoding="utf-8")
        (src_docs / "cv_help.md").write_text("", encoding="utf-8")

        target_dir = tmp_path / ".claude" / "commands"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "cv_review.setup_claude.COMMANDS_DIR", target_dir
        )

        with pytest.raises(RuntimeError) as exc_info:
            deploy_slash_commands()
        assert "源文件缺失" in str(exc_info.value)
