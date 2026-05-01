"""Verify the ``--apellidos`` / ``--nombre`` preserve-case contract.

Exercises the export-side promise that ``--apellidos`` and
``--nombre`` reach the fichero-BOE bytes verbatim — the CLI never
silently upper-cases the operator's input. A silent transform would
hide typos that ``aeat submission verify`` and ``aeat submission
diff`` would otherwise catch.

AEAT convention is upper-case (the ``--help`` text nudges the
operator toward it), but the CLI does not enforce it because that
would cross into silent-data-transformation territory.

The tests pin the contract so a future refactor — for example,
adding ``.upper()`` inside ``build_130_headers`` or a Typer
callback — trips here and forces a deliberate discussion before
changing operator-observable behaviour.

See also:
    :mod:`aeat.entrypoints.cli.submission` for the registered Typer
    app and :mod:`aeat.entrypoints.cli.submission.export` for the
    surface under test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _write_draft(tmp_path: Path, *, modelo: str = "130") -> Path:
    """Write a minimal draft JSON document to ``tmp_path`` and return its path."""
    payload = {
        "draft_id": "CASING-001",
        "modelo": modelo,
        "period": "2024Q1",
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "100.00"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _export(tmp_path: Path, *, modelo: str, nombre: str, apellidos: str) -> Path:
    """Run ``aeat submission export`` with the given identity and return the output file."""
    draft = _write_draft(tmp_path, modelo=modelo)
    out = tmp_path / f"out-{nombre}-{apellidos}"
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft),
            "--output-dir",
            str(out),
            "--nombre",
            nombre,
            "--apellidos",
            apellidos,
            "--tipo",
            "I",
        ],
    )
    assert result.exit_code == 0, f"export failed: {result.stdout}"
    ejercicio = "2024"
    return out / f"X1234567L{ejercicio}1T.{modelo}"


class TestModelo130CasingPreserved:
    """Modelo 130 single-record export must keep operator-supplied casing intact."""

    def test_mixed_case_preserved_in_apellidos(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="130", nombre="Kent", apellidos="Doe Rodriguez").read_bytes()
        # APELLIDOS = 30 bytes at position 26 (1-based) → bytes [25:55]
        assert payload[25:55] == b"Doe Rodriguez                 "

    def test_upper_case_preserved_in_apellidos(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="130", nombre="KENT", apellidos="DOE RODRIGUEZ").read_bytes()
        assert payload[25:55] == b"DOE RODRIGUEZ                 "

    def test_lower_case_preserved_in_apellidos(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="130", nombre="kent", apellidos="doe rodriguez").read_bytes()
        assert payload[25:55] == b"doe rodriguez                 "

    def test_mixed_case_preserved_in_nombre(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="130", nombre="Kent", apellidos="Doe").read_bytes()
        # NOMBRE = 15 bytes at position 56 (1-based) → bytes [55:70]
        assert payload[55:70] == b"Kent           "

    def test_differently_cased_names_produce_different_bytes(self, tmp_path: Path) -> None:
        """Confirm uppercase and mixed-case exports yield different bytes.

        Sanity check that the preserve-case contract actually holds — if
        the bytes were identical the casing was silently normalised.
        """
        upper = _export(tmp_path, modelo="130", nombre="KENT", apellidos="DOE").read_bytes()
        mixed = _export(tmp_path, modelo="130", nombre="Kent", apellidos="Doe").read_bytes()
        assert upper != mixed, (
            "casing was silently normalised — KENT/DOE and Kent/Doe should yield "
            "different bytes, but got identical output. Fix the regression or "
            "update this test if the preserve-case contract is intentionally changed."
        )


class TestModelo303CasingPreserved:
    """Modelo 303 envelope export must keep operator-supplied casing intact."""

    def test_apellidos_y_nombre_combined_preserves_case(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="303", nombre="Kent", apellidos="Doe Rodriguez").read_bytes()
        # DP30301_F008 (APELLIDOS_Y_NOMBRE, 80 bytes) lives at DP30301 offset 23 (1-based)
        # → absolute 328 + 22 = 350 .. 430
        apellidos_y_nombre = payload[350:430]
        # The builder joins with space: "Doe Rodriguez Kent"
        assert apellidos_y_nombre.startswith(b"Doe Rodriguez Kent")
