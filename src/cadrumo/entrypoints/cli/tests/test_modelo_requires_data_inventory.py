"""Data-inventory checklist proof for ``aeat app modelo requires``.

``requires`` composes the registry snapshot for one
``(modelo, filing_year, period)`` into an operator-facing checklist: which
casillas must be hand-entered, which are optional, which the bucket ledger
populates automatically, and which come from the active taxpayer profile
(warning when a profile-derivable coefficient is still unset). This module
proves the classification against committed, non-trivial bindings in the REAL
bundled registry for Modelos 100, 130, and 390, plus the profile-coefficient
warning against a REAL partial taxpayer profile. Expected rows are anchored to
those registry declarations rather than produced by a second implementation
of the classifier under test.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ....tests.user_profile import register_minimal_profile
from ._modelo_empty_profile_fixture import _isolated_backend

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M130_MODELO = "130"
_M130_YEAR = 2024
_M130_PERIOD = "2T"

_M100_MODELO = "100"
_M100_YEAR = 2025
_M100_PERIOD = "0A"

_M390_MODELO = "390"
_M390_YEAR = 2025
_M390_PERIOD = "0A"


def _numbers_by_section(result: dict[str, list[dict[str, str]]]) -> dict[str, set[str]]:
    return {
        section: {row["number"] for row in result[section]}
        for section in ("required_manual", "optional_manual", "ledger_derivable", "profile_derivable")
    }


def test_requires_classifies_real_m130_sources_without_an_active_profile() -> None:
    """``requires`` exposes committed manual, ledger, and prior-filing rows.

    No active profile is set: the operator has not created a taxpayer profile
    yet, but the checklist must still tell them what data is needed from the
    registry alone (required/optional manual casillas, ledger-derivable casillas).
    """
    invocation = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M130_MODELO,
            "--year",
            str(_M130_YEAR),
            "--period",
            _M130_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    assert result["modelo"] == _M130_MODELO
    assert result["filing_year"] == _M130_YEAR
    assert result["period"] == _M130_PERIOD
    sections = _numbers_by_section(result)
    assert {"01", "02"} <= sections["ledger_derivable"]
    assert result["optional_manual"]

    # Ledger-derivable rows carry their binding provenance for the checklist.
    ledger_rows = {row["number"]: row["binding_source"] for row in result["ledger_derivable"]}
    assert ledger_rows["01"] == "ledger_renta_income_aggregation"
    assert ledger_rows["02"] == "ledger_renta_gastos_pago_fraccionado_aggregation"
    assert {(row["number"], row["binding_source"]) for row in result["previous_filing"]} >= {
        ("05", "previous_filing"),
    }

    # No active profile: the checklist cannot check profile coefficients and
    # must say so via a non-blocking advisory notice, not silently.
    assert result["profile_checked"] is False
    assert result["unresolved_profile_bindings"] == []
    notices = unwrap_envelope_notices(invocation.output)
    no_profile_notice = next(notice for notice in notices if notice["code"] == "modelo.requires.no_active_profile")
    assert no_profile_notice["action"] is None


def test_requires_reads_relation_prefill_alternates_and_advises_on_unbucketed_sources() -> None:
    """Real M100 alternates remain visible instead of collapsing to the primary."""
    invocation = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M100_MODELO,
            "--year",
            str(_M100_YEAR),
            "--period",
            _M100_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)
    relation_pairs = {(row["binding_id"], row["binding_source"]) for row in result["relation_prefill"]}
    assert {
        ("renta-2025-modelo-111-retenciones-periodicas", "relation_prefill"),
        ("renta-2025-modelo-190-retenciones-anuales", "relation_prefill"),
    } <= relation_pairs
    unbucketed_pairs = {(row["binding_id"], row["binding_source"]) for row in result["unbucketed_sources"]}
    assert ("renta-2025-certificado-trabajo-retenciones", "manual_input") in unbucketed_pairs

    notices = unwrap_envelope_notices(invocation.output)
    advisory = next(notice for notice in notices if notice["code"] == "modelo.requires.unbucketed_binding_source")
    assert advisory["severity"] == "warning"
    assert advisory["action"] is None
    assert "manual_input" in advisory["context"]["source_kinds"]
    assert "renta-2025-certificado-trabajo-retenciones" in advisory["context"]["binding_ids"]


def test_requires_buckets_local_register_resolvers_as_live_observations() -> None:
    """M390 exposes its committed local-state resolver bindings without claiming a remote read."""
    invocation = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M390_MODELO,
            "--year",
            str(_M390_YEAR),
            "--period",
            _M390_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    live_pairs = {(row["number"], row["binding_source"]) for row in result["live_observation"]}
    assert {
        ("63", "bienes_inversion_regularizacion"),
        ("97", "iva_compensation_annual_partition"),
        ("662", "iva_compensation_annual_partition"),
    } <= live_pairs


@pytest.fixture
def _partial_m100_profile() -> Iterator[None]:
    """Seed a real active profile satisfying a proper subset of M100 profile bindings.

    Mirrors ``test_bindings_list_missing_filter.py``'s partial-profile
    pattern: real facts persisted through the workflow state repository, not
    a mock or a placeholder.
    """
    with open_test_profile_session("22222222-2222-4222-8222-222222222222"):
        register_minimal_profile(profile_id="22222222-2222-4222-8222-222222222222")
        set_active_test_profile_facts(
            (
                UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            ),
        )
        yield


def test_requires_warns_about_unresolved_profile_coefficients(_partial_m100_profile: None) -> None:
    """With an active but incomplete profile, unresolved coefficients surface as a warning.

    Modelo 100 declares dozens of ``source = "profile"`` bindings (marital
    status, spouse identity, descendant/ascendant rows, ...). The seeded
    profile resolves only a proper subset (tax residence, declaration type,
    birth date, minor children count); every other profile-derivable binding
    must be reported as unresolved so the operator knows exactly which
    coefficient is still owed -- never a silent gap.
    """
    resolved = {
        "renta-2025-profile-tax-residence-ccaa",
        "renta-2025-profile-declaration-type",
        "renta-2025-profile-taxpayer-birth-date",
    }
    invocation = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M100_MODELO,
            "--year",
            str(_M100_YEAR),
            "--period",
            _M100_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    assert result["profile_checked"] is True
    profile_binding_ids = {row["binding_id"] for row in result["profile_derivable"]}
    assert profile_binding_ids, "fixture expectation must be non-trivial"
    # The seeded resolved bindings must actually be declared bindings for
    # this revision (otherwise the fixture proves nothing).
    assert resolved <= profile_binding_ids

    unresolved = set(result["unresolved_profile_bindings"])
    assert unresolved, "a proper subset must leave real gaps"
    # The bindings the profile explicitly resolved must not be reported as
    # unresolved.
    assert unresolved.isdisjoint(resolved)
    # Every unresolved id must be a genuinely declared profile binding for
    # this revision (never an invented id).
    assert unresolved <= profile_binding_ids

    notices = unwrap_envelope_notices(invocation.output)
    warning = next(notice for notice in notices if notice["code"] == "modelo.requires.missing_profile_coefficient")
    assert warning["severity"] == "warning"
    assert warning["action"] is None
    for binding_id in unresolved:
        assert binding_id in warning["context"]["missing_bindings"]

    assert unwrap_schema_envelope('{"schema_version": "2", "command": "x", "status": "warning", "result": {}}') == {}
