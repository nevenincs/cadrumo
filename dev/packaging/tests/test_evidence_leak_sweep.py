"""Real-behavior tests for the publication leak sweep.

Every test writes real files and drives the real CLI entry point; the detector
under test is the same one the evidence builders run at mint time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..evidence_leak_sweep import main

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class TestPublicationLeakSweep:
    """The fail-closed tripwire over everything a release is about to carry."""

    def _attach_dir(self, tmp_path: Path) -> Path:
        """A publication directory whose rows were scrubbed at mint time."""
        directory = tmp_path / "attach"
        directory.mkdir()
        (directory / "python-linux-x86-64-row.json").write_text(
            json.dumps({"cwd": "C:\\Users\\scrubbed-user\\work", "status": "passed"}),
            encoding="utf-8",
        )
        (directory / "homebrew-linux-x86-64-row.json").write_text(
            json.dumps({"workflow_path": ".github/workflows/packaging-homebrew.yml"}),
            encoding="utf-8",
        )
        return directory

    def test_clean_publication_directory_passes(self, tmp_path: Path) -> None:
        """Scrubbed rows and manifests sweep clean and exit 0."""
        directory = self._attach_dir(tmp_path)
        assert main(["leak-sweep", "--directory", str(directory)]) == 0

    def test_leaking_json_field_refuses_naming_the_asset(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A home-dir username anywhere in a JSON asset refuses the publication."""
        directory = self._attach_dir(tmp_path)
        (directory / "rogue-row.json").write_text(
            json.dumps({"novel_field": {"deep": ["/home/gwuser/.local/state"]}}),
            encoding="utf-8",
        )
        assert main(["leak-sweep", "--directory", str(directory)]) == 1
        err = capsys.readouterr().err
        assert "rogue-row.json" in err
        assert "gwuser" in err

    def test_leaking_plain_text_asset_is_caught_too(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Non-JSON text assets (archived transcripts) are scanned line-wise."""
        directory = self._attach_dir(tmp_path)
        (directory / "transcript.log").write_text("ran under C:\\Users\\hiddenop\\workdir\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(directory)]) == 1
        assert "transcript.log" in capsys.readouterr().err

    def test_explicit_machine_token_is_refused(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A named hostname token anywhere in the payload refuses publication."""
        directory = self._attach_dir(tmp_path)
        (directory / "notes.txt").write_text("built on build-host-example runner\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(directory), "--token", "build-host-example"]) == 1
        assert "notes.txt" in capsys.readouterr().err

    def test_missing_directory_is_a_hard_error(self, tmp_path: Path) -> None:
        """Sweeping nothing is never success — an absent directory refuses."""
        assert main(["leak-sweep", "--directory", str(tmp_path / "absent")]) == 1

    def test_union_sweep_catches_a_leak_in_the_second_root(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A clean attach dir cannot launder a leaking cohort dir (union sweep)."""
        attach = self._attach_dir(tmp_path)
        cohort = tmp_path / "cohort"
        cohort.mkdir()
        (cohort / "release-cohort.json").write_text(json.dumps({"version": "0.2.1"}), encoding="utf-8")
        (cohort / "build-log.txt").write_text("built from C:\\Users\\builderop\\src\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(attach), "--directory", str(cohort)]) == 1
        err = capsys.readouterr().err
        assert "build-log.txt" in err
        (cohort / "build-log.txt").write_text("built from a clean checkout\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(attach), "--directory", str(cohort)]) == 0
