"""Shared helpers for Modelo work UX CLI tests."""

from __future__ import annotations

import json

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does.
from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core.aggregation import BindingSourceKind
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_PROFILE_ID = "operator"


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile(*, activity_start_date: str | None = None) -> None:
    args = [
        "config",
        "profile",
        "create",
        "operator",
        "--quiet",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "12345678Z",
        "--name",
        "Operator",
        "--surnames",
        "Readiness",
        "--activity",
        "design",
    ]
    if activity_start_date is not None:
        args.extend(["--activity-start-date", activity_start_date])
    result = _invoke(args)  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_gb_non_resident_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Readiness",
            "--activity", "Spanish-source rent",
            "--fiscal-residency", "non_resident_irnr",
            "--country-of-fiscal-residence", "GB",
            "--representante-fiscal-nif", "12345678Z",
            "--representante-fiscal-nombre", "Test Representative",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_de_nonresident_legal_entity_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "legal_entity",
            "--legal-entity-form", "sl",
            "--tax-id", "B66012345",
            "--legal-name", "NordHaus GmbH",
            "--activity", "Spanish-source services",
            "--fiscal-residency", "non_resident_irnr",
            "--country-of-fiscal-residence", "DE",
            "--iva-regime", "GENERAL",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_attribution_entity_intracom_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "attribution_entity",
            "--tax-id", "E12345674",
            "--name", "M349 Readiness CB",
            "--activity", "intracommunity operations",
            "--does-intracomunitario",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _attempt_incomplete_profile_create():
    return _invoke(
        [
            "--format", "json",
            "config", "profile", "create", _PROFILE_ID,
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--activity", "design",
        ],
    )  # fmt: skip


def _create_m130_work_unit(*, period: str = "1T") -> str:
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2025,
        period=period,
        revision="2019-y-siguientes",
    )


def _create_m303_work_unit() -> str:
    return create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2025,
        period="1T",
        revision="2023-y-siguientes",
    )


def _seed_m111_retencion_observation() -> None:
    """Seed one work-income retención percepción so a Modelo 111 work unit's
    ``work calculate`` resolves the ``retenciones_aggregation`` source.

    Modelo 111 calculation requires per-perceptor retención evidence: the
    source resolver refuses an all-blank quarter rather than silently filing
    a zero return. One real ``rendimientos_trabajo`` percepción is the
    minimum that makes the 2025 1T quarter calculable.
    """
    observation = json.dumps(
        {
            "source_kind": BindingSourceKind.LEDGER_TRANSACTION.value,
            "source_object_id": "m111-work-income-row-001",
            "perceptor_nif": "A12345678",
            "perceptor_name": "Empresa Pagadora SL",
            "scheme": "rendimientos_trabajo",
            "taxable_base": "1000.00",
            "retencion_amount": "190.00",
            "accrued_on": "2025-01-15",
        },
    )
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--retencion-observation", observation,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_calculable_work_unit() -> str:
    """Create a modelo 111 work unit whose `work calculate` succeeds.

    Seeds one real work-income retención percepción so the
    ``retenciones_aggregation`` source resolves the quarter; the calc path
    then needs no further operator-supplied casilla inputs.
    """
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="111",
        filing_year=2025,
        period="1T",
        revision="2019-y-siguientes",
    )
    _seed_m111_retencion_observation()
    return work_unit_id
