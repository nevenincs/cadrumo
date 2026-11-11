from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering
from cadrumo.tests.log_records import delivered_text

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli
from .profile_cli_support import invoke_protected_profile

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = str(filing_year_envelope().horizon)
_REVISION = str(revision_covering("200", int(_YEAR)).id)
_ACTIVITY_START = date(int(_YEAR), 1, 1).isoformat()


def _invoke(arguments: list[str]):
    return invoke_cached_cli(["--format", "json", *arguments])


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
            "taxpayer_type.new_entity_first_two_profit_periods": "false",
            "tax_residence.ccaa": "madrid",
        },
        log_in=False,
    )

    work = _invoke(
        [
            "app", "modelo", "work", "create",
            "--modelo", "200", "--year", _YEAR, "--period", "0A",
            "--revision", _REVISION, "--name", f"SA M200 {_YEAR}", "--by", "s421",
        ],
    )  # fmt: skip
    assert work.exit_code == 0, work.output

    calculation = _invoke(
        [
            "app", "modelo", "work", "calculate",
            "--modelo", "200", "--year", _YEAR, "--period", "0A",
            "--revision", _REVISION,
            "--casilla", "DP200012:00501=100000",
            "--casilla", "DP200013:00417=0",
            "--casilla", "DP200013:00418=0",
            "--casilla", "01032=0",
            "--casilla", "DP200014:00547=0",
            "--casilla", "DP200014:01033=0",
            "--casilla", "DP200014:01034=0",
            "--binding", "modelo-200-profile-legal-entity-form=sa",
            "--binding", "modelo-200-profile-incn-prior-12-months=500000",
            "--binding", "modelo-200-profile-tributacion-estado-porcentaje=100",
            "--binding", "modelo-200-bin-pendiente-ejercicios-anteriores=0",
            "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
            "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
            "--by", "s421",
        ],
    )  # fmt: skip
    assert calculation.exit_code == 0, calculation.output

    profile_edit = invoke_protected_profile(
        "sa-drift", "edit", "--quiet", "--activity-start-date", _ACTIVITY_START, json_output=True
    )
    assert profile_edit.exit_code == 0, profile_edit.output

    caplog.set_level(logging.WARNING, logger="cadrumo.application.workflow.engine")
    verification = _invoke(
        [
            "app", "modelo", "work", "verify",
            "--modelo", "200", "--year", _YEAR, "--period", "0A",
            "--revision", _REVISION, "--by", "s421",
        ],
    )  # fmt: skip

    assert verification.exit_code == 0, verification.output
    assert "Traceback" not in verification.output
    assert "Traceback" not in delivered_text(caplog)
    response = json.loads(verification.output)
    report = response["result"]
    assert report["registry_snapshot_ref"]["revision_id"] == _REVISION
    assert report["completeness_status"] == "complete"
    assert report["granted_verificado_completo"] is True
    assert report["findings"]
    assert all(finding["kind"] == "advisory" for finding in report["findings"])
    assert any(_ACTIVITY_START in finding["message"] for finding in report["findings"])
