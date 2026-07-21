from __future__ import annotations

import json
import logging

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(arguments: list[str]):
    return invoke_cached_cli(["--format", "json", *arguments])


def test_verify_after_profile_activity_start_change_refuses_without_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    profile = _invoke(
        [
            "config", "profile", "create", "sa-drift",
            "--quiet", "--accept-defaults",
            "--entity-type", "legal_entity",
            "--legal-entity-form", "sa",
            "--tax-id", "A12345674",
            "--legal-name", "S.A. Drift Test",
            "--activity", "industrial services",
            "--incn-prior-12-months", "500000",
            "--no-new-entity-first-two-profit-periods",
            "--iva-regime", "GENERAL",
            "--tax-residence-ccaa", "madrid",
        ],
    )  # fmt: skip
    assert profile.exit_code == 0, profile.output

    work = _invoke(
        [
            "app", "modelo", "work", "create",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2024-y-siguientes", "--name", "SA M200 2026", "--by", "s421",
        ],
    )  # fmt: skip
    assert work.exit_code == 0, work.output

    calculation = _invoke(
        [
            "app", "modelo", "work", "calculate",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2024-y-siguientes",
            "--casilla", "00501=100000",
            "--casilla", "DP200013:00417=0",
            "--casilla", "DP200013:00418=0",
            "--casilla", "01032=0",
            "--casilla", "DP200014:00547=0",
            "--casilla", "DP200014:01033=0",
            "--casilla", "DP200014:01034=0",
            "--binding", "modelo-200-2024-profile-legal-entity-form=sa",
            "--binding", "modelo-200-2024-profile-new-entity-flag=0",
            "--binding", "modelo-200-2024-profile-incn-prior-12-months=500000",
            "--binding", "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
            "--binding", "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
            "--by", "s421",
        ],
    )  # fmt: skip
    assert calculation.exit_code == 0, calculation.output

    profile_edit = _invoke(
        [
            "config",
            "profile",
            "edit",
            "sa-drift",
            "--quiet",
            "--activity-start-date",
            "2026-01-01",
        ],
    )
    assert profile_edit.exit_code == 0, profile_edit.output

    caplog.set_level(logging.WARNING, logger="cadrumo.application.workflow._engine")
    verification = _invoke(
        [
            "app", "modelo", "work", "verify",
            "--modelo", "200", "--year", "2026", "--period", "0A",
            "--revision", "2024-y-siguientes", "--by", "s421",
        ],
    )  # fmt: skip

    assert verification.exit_code != 0, verification.output
    assert "Traceback" not in verification.output
    assert "Traceback" not in caplog.text
    response = json.loads(verification.output)
    error = response["error"]
    assert error["code"] == "REFUSED_MODELO_WORKFLOW_GATE"
    assert error["category"] == "REFUSED"
    assert error["context"] == {"abort_code": "DRAFT_HAS_ERRORS", "stage": "ABORTED"}
    assert "modelo-200-2024-rel-202-pagos-fraccionados" in error["message"]
    assert "recalculate" in error["message"]
