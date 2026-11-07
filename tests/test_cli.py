"""Tests for sidecar protect, revert, and clean."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lupaxa.protect.cli import main


def _set_mtime(path: Path, when: int) -> None:
    os.utime(path, (when, when))


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("protect ")


def test_protect_revert_and_clean(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("one", encoding="utf-8")
    sidecar = tmp_path / "note.txt.protect"

    assert main(["-p", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "one"

    source.write_text("two", encoding="utf-8")
    assert main(["-p", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "one"

    assert main(["-p", "--force", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "two"

    source.write_text("three", encoding="utf-8")
    assert main(["-v", "-d", str(tmp_path), "-y"]) == 0
    assert source.read_text(encoding="utf-8") == "two"

    assert main(["-c", "-d", str(tmp_path), "-y"]) == 0
    assert not sidecar.exists()


def test_node_modules_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    nested = tmp_path / "node_modules"
    nested.mkdir()
    (nested / "skip.txt").write_text("skip", encoding="utf-8")
    assert main(["-p", "-R", "-d", str(tmp_path), "-y"]) == 0
    assert (tmp_path / "keep.txt.protect").is_file()
    assert not (nested / "skip.txt.protect").exists()


def test_config_dir_is_the_base_when_flag_is_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    other = tmp_path / "other"
    work.mkdir()
    other.mkdir()
    (other / "note.txt").write_text("hi", encoding="utf-8")
    (work / ".protect.config").write_text(
        json.dumps({"dir": str(other)}),
        encoding="utf-8",
    )
    monkeypatch.chdir(work)
    assert main(["-p", "-y"]) == 0
    assert (other / "note.txt.protect").is_file()


def test_verbose_prints_each_action_and_quiet_does_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "note.txt").write_text("one", encoding="utf-8")

    assert main(["-p", "-d", str(tmp_path), "-y"]) == 0
    assert "BACKUP:" not in capsys.readouterr().out

    (tmp_path / "note.txt.protect").unlink()
    assert main(["-q", "-p", "-d", str(tmp_path), "-y"]) == 0
    assert "BACKUP:" not in capsys.readouterr().out

    (tmp_path / "note.txt.protect").unlink()
    assert main(["--verbose", "-p", "-d", str(tmp_path), "-y"]) == 0
    assert "BACKUP:" in capsys.readouterr().out


def test_quiet_and_verbose_cannot_be_combined() -> None:
    with pytest.raises(SystemExit) as caught:
        main(["-q", "--verbose", "-p", "note.txt"])
    assert caught.value.code == 2


def test_check_fails_when_a_sidecar_is_missing_or_stale(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    stale = tmp_path / "stale.txt"
    newer = tmp_path / "newer.txt"
    current = tmp_path / "current.txt"
    for path in (missing, stale, newer, current):
        path.write_text("original", encoding="utf-8")
    for path in (stale, newer, current):
        sidecar = tmp_path / f"{path.name}.protect"
        sidecar.write_text("copy", encoding="utf-8")
        _set_mtime(path, 1_000)
        _set_mtime(sidecar, 1_000)
    _set_mtime(stale, 2_000)
    _set_mtime(tmp_path / "newer.txt.protect", 3_000)

    assert main(["-s", "-d", str(tmp_path)]) == 0
    assert main(["--check", str(missing)]) == 1
    assert main(["-s", "--check", str(stale)]) == 1
    assert main(["-s", "--check", str(newer)]) == 0
    assert main(["-s", "--check", str(current)]) == 0
    assert not (tmp_path / "missing.txt.protect").exists()


def test_requires_an_action(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert "required" in capsys.readouterr().err


def test_status_reports_each_sidecar_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.txt"
    stale = tmp_path / "stale.txt"
    newer = tmp_path / "newer.txt"
    current = tmp_path / "current.txt"
    for path in (missing, stale, newer, current):
        path.write_text("original", encoding="utf-8")
    for path in (stale, newer, current):
        sidecar = tmp_path / f"{path.name}.protect"
        sidecar.write_text("copy", encoding="utf-8")
        _set_mtime(path, 1_000)
        _set_mtime(sidecar, 1_000)
    _set_mtime(stale, 2_000)
    _set_mtime(tmp_path / "newer.txt.protect", 3_000)

    assert main(["-s", "-d", str(tmp_path)]) == 0
    report = capsys.readouterr().out
    assert f"missing {missing.resolve()}" in report
    assert f"stale {stale.resolve()}" in report
    assert f"newer {newer.resolve()}" in report
    assert f"current {current.resolve()}" in report
    assert not (tmp_path / "missing.txt.protect").exists()
    assert (tmp_path / "stale.txt.protect").read_text(encoding="utf-8") == "copy"


def test_update_refreshes_only_when_the_original_is_newer(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    sidecar = tmp_path / "note.txt.protect"
    source.write_text("old", encoding="utf-8")
    sidecar.write_text("copy", encoding="utf-8")
    _set_mtime(source, 2_000)
    _set_mtime(sidecar, 1_000)

    assert main(["-p", "--update", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "old"

    source.write_text("edited", encoding="utf-8")
    _set_mtime(source, 1_500)
    _set_mtime(sidecar, 3_000)
    assert main(["-p", "--update", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "old"

    assert main(["-p", "--force", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "edited"


def test_no_recursive_overrides_config(tmp_path: Path) -> None:
    nested = tmp_path / "sub"
    nested.mkdir()
    (tmp_path / "top.txt").write_text("top", encoding="utf-8")
    (nested / "deep.txt").write_text("deep", encoding="utf-8")
    (tmp_path / ".protect.config").write_text(
        json.dumps({"recursive": True}),
        encoding="utf-8",
    )

    assert main(["-p", "--no-recursive", "-d", str(tmp_path), "-y"]) == 0
    assert (tmp_path / "top.txt.protect").is_file()
    assert not (nested / "deep.txt.protect").exists()


def test_no_update_overrides_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "note.txt"
    sidecar = tmp_path / "note.txt.protect"
    source.write_text("new", encoding="utf-8")
    sidecar.write_text("old", encoding="utf-8")
    _set_mtime(sidecar, 1_000)
    _set_mtime(source, 2_000)
    (tmp_path / ".protect.config").write_text(
        json.dumps({"update": True}),
        encoding="utf-8",
    )

    assert main(["-p", "--no-update", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "old"
    assert "Use --update to refresh it" in capsys.readouterr().err

    assert main(["-p", "-d", str(tmp_path), "-y"]) == 0
    assert sidecar.read_text(encoding="utf-8") == "new"
