"""Unallocated autoconsumo refuses verification and export through the real gates.

The published registry requires the profile's autoconsumo base to equal its
per-rate rows. An unallocated base cannot silently contribute an assumed 21%
quota. The same declaration without that base verifies and exports.

Real encrypted persistence, published authority, calculation, verification and
CLI export are used for both sides of the control.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingKind
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    calculate_and_verify_modelo_303_revision,
)
from cadrumo.tests.cli_envelope import require_error_document
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import invoke_cached_cli

from .runtime_profile_backend import runtime_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The general-rate cuota the shared fixture binds, the only printed amount in [27].
_GENERAL_CUOTA = Decimal("1000.00")
_AUTOCONSUMO_BASE = Decimal("1000.00")


def _export(revision_id: str, output: Path):
    return invoke_cached_cli(
        ["--format", "json", "app", "modelo", "export", "--revision", revision_id, "--output", str(output)],
    )


def test_an_autoconsumo_base_refuses_verification_and_export(tmp_path: Path) -> None:
    # Replay the May fixture at its own as-of date; wallet freshness remains
    # enforced. This non-live tax clock does not change monotonic deadlines.
    with (
        frozen_clock(datetime(2026, 5, 21, 12, 3, tzinfo=UTC)),
        runtime_cli_profile(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        _nif, _bucket, report, revision, *_repositories = calculate_and_verify_modelo_303_revision(
            autoconsumo_promotor_base=_AUTOCONSUMO_BASE,
            operation=operation,
        )
        output = tmp_path / "303-autoconsumo.txt"
        exported = _export(revision.calculation_revision_id, output)

    assert Decimal(revision.casilla_values["09"]) == _GENERAL_CUOTA
    assert Decimal(revision.casilla_values["27"]) == _GENERAL_CUOTA
    assert Decimal(revision.casilla_values["iva.autoconsumo.promotor.base"]) == _AUTOCONSUMO_BASE
    assert Decimal(revision.casilla_values["iva.autoconsumo.promotor.base.por-tipo"]) == 0
    assert report.granted_verificado_completo is False
    allocation_findings = [
        finding
        for finding in report.findings
        if finding.message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
        and finding.message_facts.get("predicate_id") == "modelo-303-iva-autoconsumo-promotor-base-equals-por-tipo"
    ]
    assert len(allocation_findings) == 1, report.findings
    assert allocation_findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert revision.state is CalculationRevisionState.BORRADOR

    assert exported.exit_code != 0, exported.output
    error = require_error_document(exported.output)["error"]
    assert (error["category"], error["code"]) == ("ERROR", "ERROR_MODELO_CALCULATION_REVISION_STATE"), error
    assert error["context"]["state"] == CalculationRevisionState.BORRADOR.value
    assert error["context"]["calculation_revision_id"] == revision.calculation_revision_id
    assert error["context"]["terminal_condition"] == "failed"
    assert error["context"]["operation_id"]
    assert not output.exists()


def test_the_same_declaration_without_autoconsumo_verifies_and_exports(tmp_path: Path) -> None:
    # Replay the May fixture at its own as-of date; wallet freshness remains
    # enforced. This non-live tax clock does not change monotonic deadlines.
    with (
        frozen_clock(datetime(2026, 5, 21, 12, 3, tzinfo=UTC)),
        runtime_cli_profile(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
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
