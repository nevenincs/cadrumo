"""Lock the submission CLI's exit-code contract (wave 131).

Kent scripts the CLI into pipelines (``aeat submission verify ...
&& aeat submission diff ...``), so every command's exit code is a
public contract. A refactor that silently changes exit 2 to
``typer.Exit`` default 1 — or conflates draft-refusal (3) with
semantic-diff (1) — breaks every downstream script.

Documented exit-code convention across the sub-app:

- **0** — success / happy path.
- **1** — semantic difference (``diff`` only; files parse but
  differ at casilla or field level).
- **2** — unsupported modelo, corrupt payload, filename-inference
  failure, check-letter failure, or other input-validation error.
- **3** — draft status refusal (``export`` when draft is
  INCOMPLETE; tipo=D export without ``--iban``).

Wave 131 pins this per command so a future scope change has to
update both the test and the command in lockstep.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _minimal_draft(tmp_path: Path, *, status: str = "DRAFT", modelo: str = "130") -> Path:
    payload = {
        "draft_id": "EXIT-001",
        "modelo": modelo,
        "period": "2024Q1",
        "profile_tax_id": "X1234567L",
        "status": status,
        "values": {"01": "10000.00"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestExportExitCodes:
    def test_happy_path_exits_0(self, tmp_path: Path) -> None:
        draft = _minimal_draft(tmp_path)
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(tmp_path / "out"),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code == 0

    def test_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        draft = _minimal_draft(tmp_path, modelo="390")
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(tmp_path / "out"),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code == 2

    def test_incomplete_draft_exits_3(self, tmp_path: Path) -> None:
        draft = _minimal_draft(tmp_path, status="VALIDATED")
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(tmp_path / "out"),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        assert result.exit_code == 3

    def test_devolucion_without_iban_exits_3(self, tmp_path: Path) -> None:
        draft = _minimal_draft(tmp_path, modelo="303")
        result = _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(tmp_path / "out"),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
                "--tipo",
                "D",
            ],
        )
        assert result.exit_code == 3


class TestVerifyExitCodes:
    def test_happy_path_exits_0(self, tmp_path: Path) -> None:
        # Run export first to generate a valid file.
        draft = _minimal_draft(tmp_path)
        _runner.invoke(
            app,
            [
                "export",
                str(draft),
                "--output-dir",
                str(tmp_path / "out"),
                "--nombre",
                "KENT",
                "--apellidos",
                "DOE",
            ],
        )
        path = tmp_path / "out" / "X1234567L20241T.130"
        result = _runner.invoke(app, ["verify", str(path)])
        assert result.exit_code == 0

    def test_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        bad = tmp_path / "fake.390"
        bad.write_bytes(b"  ")
        result = _runner.invoke(app, ["verify", str(bad), "--modelo", "390", "--ejercicio", "2024"])
        assert result.exit_code == 2

    def test_corrupt_payload_exits_2(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.130"
        bad.write_bytes(b"GARBAGE\r\n")
        result = _runner.invoke(app, ["verify", str(bad), "--modelo", "130", "--ejercicio", "2024"])
        assert result.exit_code == 2

    def test_inference_failure_exits_2(self, tmp_path: Path) -> None:
        bad = tmp_path / "kent.bin"
        bad.write_bytes(b"  ")
        result = _runner.invoke(app, ["verify", str(bad)])
        assert result.exit_code == 2


class TestDiffExitCodes:
    def test_identical_exits_0(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        for sub in ("a", "b"):
            draft = _minimal_draft(tmp_path / sub)
            _runner.invoke(
                app,
                [
                    "export",
                    str(draft),
                    "--output-dir",
                    str(tmp_path / sub / "out"),
                    "--nombre",
                    "KENT",
                    "--apellidos",
                    "DOE",
                ],
            )
        a = tmp_path / "a" / "out" / "X1234567L20241T.130"
        b = tmp_path / "b" / "out" / "X1234567L20241T.130"
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 0

    def test_semantic_mismatch_exits_1(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        draft_a = _minimal_draft(tmp_path / "a")
        draft_b_raw = json.loads(draft_a.read_text(encoding="utf-8"))
        draft_b_raw["values"]["01"] = "99999.00"
        draft_b = tmp_path / "b" / "draft.json"
        draft_b.write_text(json.dumps(draft_b_raw), encoding="utf-8")
        for draft, sub in ((draft_a, "a"), (draft_b, "b")):
            _runner.invoke(
                app,
                [
                    "export",
                    str(draft),
                    "--output-dir",
                    str(tmp_path / sub / "out"),
                    "--nombre",
                    "KENT",
                    "--apellidos",
                    "DOE",
                ],
            )
        a = tmp_path / "a" / "out" / "X1234567L20241T.130"
        b = tmp_path / "b" / "out" / "X1234567L20241T.130"
        result = _runner.invoke(app, ["diff", str(a), str(b)])
        assert result.exit_code == 1

    def test_unsupported_modelo_exits_2(self, tmp_path: Path) -> None:
        a = tmp_path / "fake.390"
        b = tmp_path / "fake2.390"
        a.write_bytes(b" ")
        b.write_bytes(b" ")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "390", "--ejercicio", "2024"])
        assert result.exit_code == 2


class TestCheckNifExitCodes:
    def test_valid_exits_0(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567L"])
        assert result.exit_code == 0

    def test_invalid_exits_2(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567Z"])
        assert result.exit_code == 2


class TestSchemasExitCodes:
    def test_schemas_always_exits_0(self) -> None:
        """schemas is a pure registry read with no failure mode."""
        result = _runner.invoke(app, ["schemas"])
        assert result.exit_code == 0
        json_result = _runner.invoke(app, ["schemas", "--json"])
        assert json_result.exit_code == 0
