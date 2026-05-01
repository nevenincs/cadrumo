"""Parametrised CLI smoke test over every registered schema.

For each ``(modelo, ejercicio)`` entry in
:data:`._schema_registry.SCHEMA_REGISTRY`, the
produce -> verify -> diff-against-self loop must complete with zero
exit codes:

1. ``aeat submission export <draft>`` writes a byte-exact fichero-BOE
   file.
2. ``aeat submission verify <file> --json`` decodes the file back
   through the matching schema without raising.
3. ``aeat submission diff <file> <file> --json`` reports the file
   identical to itself (``status == "identical"``).

A registry entry whose module, ``build_headers``, and ``kind``
combination is internally inconsistent would slip past the unit-level
checks but fail here. This module exercises the full command dispatch
the same way an operator's shell does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app
from ._schema_registry import SCHEMA_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()

_REGISTRY_IDS = [f"{m}-{e}" for (m, e) in sorted(SCHEMA_REGISTRY.keys())]
_REGISTRY_KEYS = sorted(SCHEMA_REGISTRY.keys())


def _unwrap_result(output: str) -> dict[str, Any]:
    """Return the ``result`` payload from a CLI JSON-success envelope."""
    return cast(dict[str, Any], json.loads(output)["result"])


def _ingreso_and_negativa_cases() -> list[tuple[str, str, str]]:
    """Build ``(modelo, ejercicio, tipo)`` tuples for the ``I`` and ``N`` smokes.

    Every registered schema is exercised in both ingreso and negativa
    modes.
    """
    out: list[tuple[str, str, str]] = []
    for modelo, ejercicio in _REGISTRY_KEYS:
        out.append((modelo, ejercicio, "I"))
        out.append((modelo, ejercicio, "N"))
    return out


def _devolucion_cases() -> list[tuple[str, str, str]]:
    """Return ``tipo=D`` smoke cases for envelope schemas only.

    Only envelope schemas carry a SEPA page (``DP303DID``) where the
    IBAN gets stamped. Record-style schemas (Modelo 130) have no SEPA
    slot, so ``tipo=D`` smoke there would only exercise the IBAN
    CLI-level guard without a payload-level assertion.
    """
    return [
        (modelo, ejercicio, "D")
        for (modelo, ejercicio), entry in sorted(SCHEMA_REGISTRY.items())
        if entry.kind == "envelope"
    ]


def _ejercicio_to_period(ejercicio: str) -> str:
    """Render Q1 of the target ejercicio as a canonical ``YYYYQ1`` token."""
    return f"{ejercicio}Q1"


def _write_draft(tmp_path: Path, *, modelo: str, period: str) -> Path:
    """Write a minimal valid draft JSON exercising casilla 01 only.

    Enough to satisfy the serialiser's required-header check without
    requiring modelo-specific knowledge of cascade rules.
    """
    payload = {
        "draft_id": f"SMOKE-{modelo}-{period}",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "10000.00"},
        "findings": [],
    }
    draft_path = tmp_path / f"draft-{modelo}-{period}.json"
    draft_path.write_text(json.dumps(payload), encoding="utf-8")
    return draft_path


@pytest.mark.parametrize(("modelo", "ejercicio"), _REGISTRY_KEYS, ids=_REGISTRY_IDS)
def test_registered_schema_round_trips_through_cli(tmp_path: Path, modelo: str, ejercicio: str) -> None:
    """Every registered schema must export, re-verify, and self-diff clean.

    Uses ``--json`` on verify + diff so we assert on the machine-readable
    status field rather than grep-matching rich-formatted output.
    """
    period = _ejercicio_to_period(ejercicio)
    draft_path = _write_draft(tmp_path, modelo=modelo, period=period)
    output_dir = tmp_path / "out"

    # 1. export
    export_result = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "I",
        ],
    )
    assert export_result.exit_code == 0, (
        f"export failed for modelo={modelo} ejercicio={ejercicio}: {export_result.stdout}"
    )
    # Canonical filename {NIF}{YYYY}{PERIODO}.{modelo}
    output_file = output_dir / f"X1234567L{ejercicio}1T.{modelo}"
    assert output_file.exists(), f"expected output file {output_file} not written"
    payload = output_file.read_bytes()
    assert payload.endswith(b"\r\n"), "fichero-BOE payload missing CRLF terminator"

    # 2. verify
    verify_result = _runner.invoke(app, ["verify", str(output_file), "--json"])
    assert verify_result.exit_code == 0, f"verify failed for {output_file.name}: {verify_result.stdout}"
    verify_doc = _unwrap_result(verify_result.stdout)
    assert verify_doc["status"] == "ok"
    assert verify_doc["modelo"] == modelo
    assert verify_doc["ejercicio"] == ejercicio

    # 3. diff against self — must report identical
    diff_result = _runner.invoke(app, ["diff", str(output_file), str(output_file), "--json"])
    assert diff_result.exit_code == 0, f"self-diff failed: {diff_result.stdout}"
    diff_doc = _unwrap_result(diff_result.stdout)
    assert diff_doc["status"] == "identical"
    assert diff_doc["bytes"] == len(payload)
    assert diff_doc["casilla_deltas"] == []
    assert diff_doc["field_deltas"] == []


_INGRESO_AND_NEGATIVA = _ingreso_and_negativa_cases()
_DEVOLUCION = _devolucion_cases()


@pytest.mark.parametrize(
    ("modelo", "ejercicio", "tipo"),
    _INGRESO_AND_NEGATIVA,
    ids=[f"{m}-{e}-tipo_{t}" for m, e, t in _INGRESO_AND_NEGATIVA],
)
def test_tipo_i_and_n_round_trip(tmp_path: Path, modelo: str, ejercicio: str, tipo: str) -> None:
    """Every ``(modelo, ejercicio, tipo)`` combo must round-trip cleanly.

    Catches a regression where a tipo mode breaks end-to-end even if
    ``tipo=I`` works.
    """
    period = _ejercicio_to_period(ejercicio)
    draft_path = _write_draft(tmp_path, modelo=modelo, period=period)
    output_dir = tmp_path / "out"
    export = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            tipo,
        ],
    )
    assert export.exit_code == 0, f"tipo={tipo} export failed: {export.stdout}"
    output_file = output_dir / f"X1234567L{ejercicio}1T.{modelo}"
    assert output_file.exists()

    verify = _runner.invoke(app, ["verify", str(output_file), "--json"])
    assert verify.exit_code == 0
    verify_doc = _unwrap_result(verify.stdout)
    # Locate the tipo_declaracion field regardless of modelo shape (130 =
    # "TIPO_DECLARACION", 303 = "DP30301_F006_TIPO_DECLARACI_N").
    fields = cast(dict[str, Any], verify_doc.get("fields", {}))
    tipo_values = {v for k, v in fields.items() if "TIPO" in k and "DECLARACI" in k}
    # rich output surfaces the string with quotes around it for record schemas
    # (repr) whereas JSON serialises the raw value; accept either shape.
    assert any(tipo in str(v) for v in tipo_values), f"tipo={tipo} not visible in verify output fields: {tipo_values!r}"


@pytest.mark.parametrize(
    ("modelo", "ejercicio", "tipo"),
    _DEVOLUCION,
    ids=[f"{m}-{e}-tipo_{t}" for m, e, t in _DEVOLUCION],
)
def test_tipo_d_with_iban_round_trip(tmp_path: Path, modelo: str, ejercicio: str, tipo: str) -> None:
    """``tipo=D`` (devolución) must export cleanly when ``--iban`` is supplied.

    Verify must surface the IBAN through ``DP303DID``.
    """
    period = _ejercicio_to_period(ejercicio)
    draft_path = _write_draft(tmp_path, modelo=modelo, period=period)
    output_dir = tmp_path / "out"
    iban = "ES9121000418450200051332"
    export = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            tipo,
            "--iban",
            iban,
        ],
    )
    assert export.exit_code == 0, f"tipo={tipo} --iban export failed: {export.stdout}"
    output_file = output_dir / f"X1234567L{ejercicio}1T.{modelo}"
    assert output_file.exists()

    verify = _runner.invoke(app, ["verify", str(output_file), "--json"])
    assert verify.exit_code == 0
    verify_doc = _unwrap_result(verify.stdout)
    fields = cast(dict[str, Any], verify_doc.get("fields", {}))
    # IBAN should be visible at DP303DID_F006_DOMICILIACI_N_DEVOLUCI_N_IBA.
    assert any(iban in str(v) for v in fields.values()), (
        f"IBAN {iban!r} not surfaced in verify output fields — devolución builder may have silently dropped it."
    )


def test_tipo_d_without_iban_exits_3(tmp_path: Path) -> None:
    """``tipo=D`` must be refused when ``--iban`` is absent."""
    period = _ejercicio_to_period("2024")
    draft_path = _write_draft(tmp_path, modelo="303", period=period)
    output_dir = tmp_path / "out"
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "D",
        ],
    )
    assert result.exit_code == 3, f"expected exit 3 without IBAN, got {result.exit_code}"
    assert "REFUSED" in result.stdout
