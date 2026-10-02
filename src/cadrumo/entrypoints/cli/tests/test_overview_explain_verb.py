"""CLI surface tests for ``aeat app overview explain``."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# Active since the first supported exercise, so every year the schedule is
# asked about falls inside the activity.
_EARLIEST_ACTIVITY_START = f"{min(PublishedGovernedFactSource().supported_filing_years().years)}-01-01"


@pytest.fixture
def _native_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label="Native overview explain",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Native",
                "identity.surnames": "Overview",
                "activities.description": "design",
                "censo.activity_start_date": _EARLIEST_ACTIVITY_START,
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "directa_normal",
                "taxpayer_type.fiscal_residency": "resident_irpf",
                "tax_residence.ccaa": "madrid",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        close_active_bucket_session()
        yield fixture


def _invoke(fixture: NativeCliProfileFixture, args: list[str]):
    close_active_bucket_session()
    if fixture.label is None:
        raise ValueError("native profile must be registered before CLI invocation")
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            ["--profile", fixture.label, "--profile-secrets-stdin", *args],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def test_explain_requires_modelo_argument(_native_profile: NativeCliProfileFixture) -> None:
    """The MODELO positional argument is required."""

    result = _invoke(_native_profile, ["app", "overview", "explain"])
    assert result.exit_code != 0


def test_explain_renders_envelope_for_known_modelo(_native_profile: NativeCliProfileFixture) -> None:
    """A known modelo with an explicit --year yields the typed envelope
    with applicable + rationale + profile_facts rows."""

    result = _invoke(
        _native_profile,
        ["app", "overview", "explain", "303", "--year", "2026"],
    )
    assert result.exit_code == 0
    assert "modelo\t303" in result.output
    assert "year\t2026" in result.output
    assert "applicable\t" in result.output
    assert "rationale\t" in result.output
    assert "profile_fact\ttax_id\t" in result.output


@pytest.mark.parametrize("year", PublishedGovernedFactSource().supported_filing_years().years)
def test_explain_json_uses_the_registry_backed_modelo_303_schedule(
    _native_profile: NativeCliProfileFixture,
    year: int,
) -> None:
    result = _invoke(
        _native_profile,
        ["--format", "json", "app", "overview", "explain", "303", "--year", str(year)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)["result"]
    assert (payload["modelo"], payload["year"]) == ("303", year)
    assert payload["applicable"] is True
    assert payload["scheduling_rationale"]


def test_explain_refuses_unknown_modelo(_native_profile: NativeCliProfileFixture) -> None:
    """An unknown modelo identifier surfaces as a refusal at the CLI
    exit code rather than a stack trace."""

    result = _invoke(
        _native_profile,
        ["app", "overview", "explain", "999999", "--year", "2026"],
    )
    assert result.exit_code != 0


def test_explain_help_advertises_local_only(_native_profile: NativeCliProfileFixture) -> None:
    """Help text must signal `local-only` across locales."""

    result = _invoke(_native_profile, ["app", "overview", "explain", "--help"])
    assert result.exit_code == 0
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_explain_721_returns_structured_payload_not_crash(_native_profile: NativeCliProfileFixture) -> None:
    """M721 explain must return exit 0 and keep an unanswered crypto fact incomplete.

    Regression guard for the defect-of-record state where Modelo 721 was absent
    from the registry and ``build_overview_explain`` raised
    ``OverviewExplainError("could not evaluate")``.
    """

    result = _invoke(
        _native_profile,
        ["--language", "en", "app", "overview", "explain", "721", "--year", "2024"],
    )
    assert result.exit_code == 0
    assert "OverviewExplainError" not in result.output
    assert "could not evaluate" not in result.output
    assert "applicable\tfalse" in result.output
    assert "verdict\tincomplete" in result.output
    # The test profile never answers the Modelo 721 question, so the fact is
    # surfaced as undeclared rather than as a stored "no".
    assert "profile_fact\tmonedas_virtuales_extranjero_above_threshold\t\n" in result.output
    assert "ley-58-2003:da-18" in result.output
    assert "rd-1065-2007:art-42-quater" in result.output
    assert "orden-hfp-886-2023:art-2" in result.output
