"""Name-casing preservation contract.

``--apellidos`` and ``--nombre`` preserve Kent's casing verbatim.
We do NOT silently upper-case: Kent's casing is his responsibility,
and a silent transform would hide typos he'd want to catch at
verify/diff time.

the preserve-case contract so a future refactor
(e.g. adding ``.upper()`` in ``build_130_headers`` or a typer
callback) fails here and forces a deliberate discussion before
changing Kent-observable behaviour.

AEAT convention is upper-case — the ``--help`` text nudges Kent
toward that — but we don't enforce it at the CLI because that
would cross into silent-data-transformation territory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()


def _write_draft(tmp_path: Path, *, modelo: str = "130") -> Path:
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
        """Sanity check: uppercase vs mixed-case exports are NOT byte-identical,
        proving the preserve-case contract actually holds."""
        upper = _export(tmp_path, modelo="130", nombre="KENT", apellidos="DOE").read_bytes()
        mixed = _export(tmp_path, modelo="130", nombre="Kent", apellidos="Doe").read_bytes()
        assert upper != mixed, (
            "casing was silently normalised — KENT/DOE and Kent/Doe should yield "
            "different bytes, but got identical output. Fix the regression or "
            "update this test if the preserve-case contract is intentionally changed."
        )


class TestModelo303CasingPreserved:
    def test_apellidos_y_nombre_combined_preserves_case(self, tmp_path: Path) -> None:
        payload = _export(tmp_path, modelo="303", nombre="Kent", apellidos="Doe Rodriguez").read_bytes()
        # DP30301_F008 (APELLIDOS_Y_NOMBRE, 80 bytes) lives at DP30301 offset 23 (1-based)
        # → absolute 328 + 22 = 350 .. 430
        apellidos_y_nombre = payload[350:430]
        # The builder joins with space: "Doe Rodriguez Kent"
        assert apellidos_y_nombre.startswith(b"Doe Rodriguez Kent")
