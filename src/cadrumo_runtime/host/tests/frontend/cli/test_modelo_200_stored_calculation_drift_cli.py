from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.tests.log_records import delivered_text

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli
from .profile_cli_support import invoke_protected_profile

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_FILING_AUTHORITY_CONDITION = "modelo.work.verify.registry_snapshot.filing_authority"
_PROFILE_READS_CURRENT_CONDITION = "modelo.work.verify.profile_reads.current"
_PRECEDING_TURNOVER_CARRY = "modelo-200-incn-periodo-impositivo-anterior"


def _invoke(arguments: list[str]):
    return invoke_cached_cli(["--format", "json", *arguments])


def _reaches_filing_grade(modelo: str, *, filing_year: int, period: str) -> bool:
    with bundled_indexed_authority().operation() as operation:
        grade = operation.reachable_authority_grade(modelo, filing_year=filing_year, period=period)
    return grade is RegistryAuthorityGrade.FILING


@pytest.mark.windows_only
def test_verify_after_profile_activity_start_change_reports_scoped_advisories_without_traceback(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    register_cli_profile(
        label="sa-drift",
        facts={
            **native_general_iva_facts(),
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sa",
            "identity.tax_id": "A00015008",
            "identity.legal_name": "S.A. Drift Test",
            "activities.description": "industrial services",
            "taxpayer_type.incn_prior_12_months": "500000",
            "taxpayer_type.regimen_entidades_navieras_tonelaje": "false",
            "taxpayer_type.new_entity_first_two_profit_periods": "false",
            "tax_residence.ccaa": "madrid",
        },
        log_in=False,
    )

    work = _invoke(
        [
            "app", "modelo", "work", "create",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2025-y-siguientes", "--name", "SA M200 2026", "--by", "s421",
        ],
    )  # fmt: skip
    assert work.exit_code == 0, work.output

    calculation = _invoke(
        [
            "app", "modelo", "work", "calculate",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2025-y-siguientes",
            "--casilla", "DP200012:00501=100000",
            "--casilla", "DP200013:00417=0",
            "--casilla", "DP200013:00418=0",
            "--casilla", "01032=0",
            "--casilla", "DP200014:00547=0",
            "--casilla", "DP200014:01033=0",
            "--casilla", "DP200014:01034=0",
            "--binding", "modelo-200-profile-legal-entity-form=sa",
            "--binding", "modelo-200-profile-incn-prior-12-months=500000",
            # The rate reads the preceding período's turnover, a carry of its Modelo 200.
            "--binding", "modelo-200-incn-periodo-impositivo-anterior=500000",
            "--binding", "modelo-200-profile-tributacion-estado-porcentaje=100",
            "--binding", "modelo-200-bin-pendiente-ejercicios-anteriores=0",
            "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
            "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
            "--by", "s421",
        ],
    )  # fmt: skip
    assert calculation.exit_code == 0, calculation.output

    profile_edit = invoke_protected_profile(
        "sa-drift", "edit", "--quiet", "--activity-start-date", "2026-01-01", json_output=True
    )
    assert profile_edit.exit_code == 0, profile_edit.output

    caplog.set_level(logging.WARNING, logger="cadrumo.application.workflow.engine")
    verification = _invoke(
        [
            "app", "modelo", "work", "verify",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2025-y-siguientes", "--by", "s421",
        ],
    )  # fmt: skip

    assert "Traceback" not in verification.output
    assert "Traceback" not in delivered_text(caplog)
    response = json.loads(verification.output)
    report = response["result"]
    assert report["registry_snapshot_ref"]["revision_id"] == "2025-y-siguientes"
    findings = report["findings"]
    assert any(finding["kind"] == "advisory" and "2026-01-01" in finding["message"] for finding in findings), (
        "the activity-start change is not reported as a scoped advisory"
    )
    # Starting the activity on 2026-01-01 puts the preceding período before it, so the turnover the
    # rate read from that período's Modelo 200 stays unresolved there (never zero) and its carry is unclean.
    turnover_carry = [
        finding
        for finding in findings
        if finding["kind"] == "cross_period_dependency_unclean" and _PRECEDING_TURNOVER_CARRY in json.dumps(finding)
    ]
    assert len(turnover_carry) == 1, findings
    blocking = [finding for finding in findings if finding["kind"] != "advisory" and finding not in turnover_carry]
    # The unresolved turnover blocks at any grade. The drift surfaces as advisories, never as a
    # traceback, and at filing grade it also blocks through the profile-reads currentness gate.
    assert verification.exit_code != 0, verification.output
    assert report["completeness_status"] == "blocked"
    assert report["granted_verificado_completo"] is False
    snapshot = report["registry_snapshot_ref"]
    if _reaches_filing_grade(snapshot["modelo"], filing_year=snapshot["modelo_year"], period=snapshot["period"]):
        # At filing grade verification reaches the profile-reads gate: the profile edit after the
        # calculation makes it stale, and that refusal asks for a new calculation.
        assert [finding["action"]["failed_condition_id"] for finding in blocking] == [_PROFILE_READS_CURRENT_CONDITION]
    else:
        # Below filing grade the only other blocker is the typed grade refusal.
        assert [finding["action"]["failed_condition_id"] for finding in blocking] == [_FILING_AUTHORITY_CONDITION]
