"""The overview projections render a profile with unanswered facts instead of refusing it.

An unanswered fact decides only the obligations that depend on it. The coverage
contract reports those as undetermined, beside the rows the profile's answered
facts make positively applicable, and each unanswered fact arrives as a warning
naming the profile edit that answers it. Refusing the whole projection hid the
obligations the profile does establish. Only a profile that declares no
taxpayer model at all, from which no obligation can be derived, still refuses.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.cli_exception_preconditions import CliExceptionPrecondition
from ....application.overview.coverage import CoverageAdviceReason
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.irpf_income_categories import irpf_income_category_actividad_economica_token
from ....domain.contribuyente.entity_type import entity_type_natural_person_token
from .cli_fixture_worlds import invoke_joined_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"


@pytest.fixture(autouse=True)
def _isolated_profiles(tmp_path: Path) -> Iterator[None]:
    """Give each test its own profile store, so every test registers its own profile."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _horizon() -> int:
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon


def _activity_facts(*, declares_income: bool) -> dict[str, str]:
    """An economically active natural person who has not answered the payer facts."""
    with bundled_indexed_authority().operation():
        facts = {
            "taxpayer_type.entity_type": entity_type_natural_person_token().value,
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        }
        # The registration placeholders declare an income category and an estimation
        # regime; a blank value withdraws each. Both must go for an undeclared model,
        # because an estimation regime proves economic-activity income on its own.
        if declares_income:
            facts["taxpayer_type.irpf_income_categories"] = irpf_income_category_actividad_economica_token().value
        else:
            facts["taxpayer_type.irpf_income_categories"] = ""
            facts["irpf.estimation_regime"] = ""
        return facts


def _json(args: list[str]) -> tuple[int, Mapping[str, object]]:
    result = invoke_joined_cli(["--format", "json", *args])
    envelope: object = json.loads(result.output)
    assert isinstance(envelope, dict), result.output
    return result.exit_code, {str(key): value for key, value in envelope.items()}


def test_the_calendar_shows_undetermined_obligations_beside_the_applicable_rows() -> None:
    register_cli_profile(label="unanswered", facts=_activity_facts(declares_income=True), log_in=False)
    horizon = _horizon()

    exit_code, envelope = _json(
        [
            "app",
            "overview",
            "calendar",
            "--from",
            date(horizon, 1, 1).isoformat(),
            "--to",
            date(horizon, 12, 31).isoformat(),
        ]
    )

    assert exit_code == 0, envelope
    result = envelope["result"]
    assert isinstance(result, dict), envelope
    assert result["taxpayer_model_declared"] is True
    rows = {entry["modelo"] for entry in result["entries"]}
    assert rows, result
    undetermined = {
        item["modelo"]
        for item in result["coverage"]["advised"]
        if item["reason"] == CoverageAdviceReason.APPLICABILITY_UNDETERMINED.value
    }
    assert undetermined, result["coverage"]
    assert not undetermined & rows, (undetermined, rows)
    assert any(
        warning["fix_action"]["action"]["action"]["action_id"] == _PROFILE_EDIT_ACTION_ID
        for warning in result["warnings"]
    ), result["warnings"]


@pytest.mark.parametrize("projection", ["agenda", "backlog"])
def test_the_agenda_and_backlog_render_the_same_profile(projection: str) -> None:
    register_cli_profile(label="unanswered", facts=_activity_facts(declares_income=True), log_in=False)
    horizon = _horizon()
    window = (
        ["--date", date(horizon, 4, 15).isoformat()]
        if projection == "agenda"
        else ["--from", date(horizon, 1, 1).isoformat(), "--to", date(horizon, 12, 31).isoformat()]
    )

    exit_code, envelope = _json(["app", "overview", projection, *window])

    assert exit_code == 0, envelope
    result = envelope["result"]
    assert isinstance(result, dict), envelope
    assert result["warnings"], result


def test_a_profile_without_a_taxpayer_model_still_refuses_and_names_the_missing_fact() -> None:
    register_cli_profile(label="undeclared", facts=_activity_facts(declares_income=False), log_in=False)
    horizon = _horizon()

    exit_code, envelope = _json(
        [
            "app",
            "overview",
            "calendar",
            "--from",
            date(horizon, 1, 1).isoformat(),
            "--to",
            date(horizon, 12, 31).isoformat(),
        ]
    )

    assert exit_code != 0, envelope
    error = envelope["error"]
    assert isinstance(error, dict), envelope
    assert (error["action"] or {})["failed_condition_id"] == CliExceptionPrecondition.OVERVIEW_PROFILE_COMPLETE.value
