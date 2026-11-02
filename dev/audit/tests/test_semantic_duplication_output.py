"""The semantic-duplication report: uncapped on request, and encodable on a Windows console."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ..semantic_duplication import Candidate, _emit, _render, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _candidates(count: int) -> list[Candidate]:
    return [
        Candidate(detector="enum_subset", fingerprint=f"E{{M{index}}}", sites=("a.py", "b.py"), weight=count - index)
        for index in range(count)
    ]


def test_the_default_report_caps_each_detector_and_says_how_to_see_the_rest() -> None:
    report = _render(_candidates(30), 12)

    assert report.count("  [") == 12
    assert "showing up to 12, --full for all" in report


def test_an_uncapped_report_lists_every_candidate() -> None:
    report = _render(_candidates(30), None)

    assert report.count("  [") == 30
    assert "showing all" in report


def test_full_and_json_runs_list_every_candidate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    for name in ("one", "two"):
        (package / f"{name}.py").write_text("from alpha import thing\n", encoding="utf-8")

    assert main(["--root", str(package), "--full"]) == 0
    assert "candidate(s) across" in capsys.readouterr().out
    assert main(["--root", str(package), "--json"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), list)


def test_a_literal_outside_the_console_codec_is_written_rather_than_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252", newline="", write_through=True)
    monkeypatch.setattr("sys.stdout", console)

    _emit("lit:'▲'\n")

    assert raw.getvalue().decode("utf-8") == "lit:'▲'\n"
