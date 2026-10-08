"""A Modelo 303 whose box [27] its printed boxes do not add up to is refused before export.

The autoconsumo del promotor cuota adds into ``iva.cuota-devengada-total`` and
so into [27], but no printed box of the form carries it. The verify gate must
refuse that declaration, naming [27] and the sum of the printed boxes, and the
export verb must then refuse to write the fichero. The same declaration without
the autoconsumo base verifies complete and exports.

Real encrypted persistence, the published registry authority, the real
calculation engine, the real verify gate and the real CLI export verb.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend_context
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingKind
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    calculate_and_verify_modelo_303_revision,
)
from cadrumo.tests.cli_envelope import require_error_document

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The general-rate cuota the shared fixture binds, the only printed amount in [27].
_GENERAL_CUOTA = Decimal("1000.00")
_AUTOCONSUMO_BASE = Decimal("1000.00")
#: LIVA art. 90.Uno: the general rate applies to the autoconsumo base (art. 79.Cuatro).
_STATUTORY_GENERAL_RATE = Decimal("0.21")


def _export(revision_id: str, output: Path):
    return invoke_cached_cli(
        ["--format", "json", "app", "modelo", "export", "--revision", revision_id, "--output", str(output)],
    )


def test_an_autoconsumo_base_refuses_verification_and_export(tmp_path: Path) -> None:
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _nif, _bucket, report, revision, *_repositories = calculate_and_verify_modelo_303_revision(
            autoconsumo_promotor_base=_AUTOCONSUMO_BASE,
            operation=operation,
        )
        output = tmp_path / "303-autoconsumo.txt"
        exported = _export(revision.calculation_revision_id, output)

    assert Decimal(revision.casilla_values["09"]) == _GENERAL_CUOTA
    assert Decimal(revision.casilla_values["27"]) == _GENERAL_CUOTA + _AUTOCONSUMO_BASE * _STATUTORY_GENERAL_RATE

    assert report.granted_verificado_completo is False
    printed_total = [
        finding
        for finding in report.findings
        if finding.message_locale_key == "application.modelo.findings.printed_total_mismatch"
    ]
    assert len(printed_total) == 1, report.findings
    (finding,) = printed_total
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.casilla_id == "27"
    assert finding.message_facts["box"] == "27"
    assert finding.message_facts["printed_sum"] == _GENERAL_CUOTA
    assert revision.state is CalculationRevisionState.BORRADOR

    assert exported.exit_code != 0, exported.output
    error = require_error_document(exported.output)["error"]
    assert (error["category"], error["code"]) == ("REFUSED", "REFUSED_CLI_BOUNDARY"), error
    # The refusal names the unverified state and the states export requires.
    assert CalculationRevisionState.BORRADOR.value in error["message"], error
    assert CalculationRevisionState.VERIFICADO_COMPLETO.value in error["message"], error
    assert not output.exists()


def test_the_same_declaration_without_autoconsumo_verifies_and_exports(tmp_path: Path) -> None:
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _nif, _bucket, report, revision, *_repositories = calculate_and_verify_modelo_303_revision(
            operation=operation,
        )
        output = tmp_path / "303-ordinary.txt"
        exported = _export(revision.calculation_revision_id, output)

    assert Decimal(revision.casilla_values["27"]) == _GENERAL_CUOTA
    assert report.granted_verificado_completo is True
    assert not [
        finding
        for finding in report.findings
        if finding.message_locale_key == "application.modelo.findings.printed_total_mismatch"
    ]
    assert exported.exit_code == 0, exported.output
    assert output.is_file()
