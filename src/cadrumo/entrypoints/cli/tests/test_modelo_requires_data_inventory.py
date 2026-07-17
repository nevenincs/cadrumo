"""Data-inventory checklist proof for ``aeat app modelo requires``.

``requires`` composes the registry snapshot for one
``(modelo, filing_year, period)`` into an operator-facing checklist: which
casillas must be hand-entered, which are optional, which the bucket ledger
populates automatically, and which come from the active taxpayer profile
(warning when a profile-derivable coefficient is still unset). This module
proves the classification against the REAL bundled registry snapshot for
Modelo 130 (no external numeric authority is needed — the assertion is that
the composer's classification matches the registry's own
``input_kind``/``binding.source`` declarations, not a hand-computed figure)
and the profile-coefficient warning against a REAL partial taxpayer profile
for Modelo 100, mirroring the strict-subset pattern of
``test_bindings_list_missing_filter.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile import profile_create_storage_span, set_active_fields
from ....application.workflow import workflow_state_repository
from ....core import Period
from ....core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ....core.resources import resources
from ....domain.calculations.registry import InputKind
from ....domain.user_profile import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .envelope_helpers import unwrap_envelope_notices, unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M130_MODELO = "130"
_M130_YEAR = 2024
_M130_PERIOD = "2T"

_M100_MODELO = "100"
_M100_YEAR = 2025
_M100_PERIOD = "0A"


def _registry_derived_expectation(*, modelo: str, filing_year: int, period: str) -> dict[str, set[str]]:
    """Derive the expected casilla-number classification from the live registry.

    Mirrors exactly the classification rule the composer implements
    (``input_kind``/``binding.source``), reading it independently from the
    bundled registry snapshot so the test does not assert against a
    hand-copied literal casilla list that could silently drift from the
    registry.
    """
    authority = resources().modelos.authority
    snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    binding_sources = {binding.id: binding.source for binding in snapshot.revision.bindings}
    required_manual: set[str] = set()
    optional_manual: set[str] = set()
    ledger_derivable: set[str] = set()
    profile_derivable: set[str] = set()
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind == InputKind.MANUAL:
            (required_manual if casilla.required else optional_manual).add(casilla.number)
        elif casilla.input_kind == InputKind.BOUND and casilla.binding is not None:
            source = binding_sources.get(casilla.binding)
            if source in LEDGER_BINDING_SOURCE_KINDS:
                ledger_derivable.add(casilla.number)
            elif source == BindingSourceKind.PROFILE:
                profile_derivable.add(casilla.number)
    return {
        "required_manual": required_manual,
        "optional_manual": optional_manual,
        "ledger_derivable": ledger_derivable,
        "profile_derivable": profile_derivable,
    }


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()


def _numbers_by_section(result: dict[str, list[dict[str, str]]]) -> dict[str, set[str]]:
    return {
        section: {row["number"] for row in result[section]}
        for section in ("required_manual", "optional_manual", "ledger_derivable", "profile_derivable")
    }


def test_requires_classifies_m130_casillas_against_live_registry_no_active_profile() -> None:
    """``requires`` for Modelo 130 matches the registry's own input_kind/source split.

    No active profile is set: the operator has not created a taxpayer profile
    yet, but the checklist must still tell them what data is needed from the
    registry alone (required/optional manual casillas, ledger-derivable casillas).
    """
    expected = _registry_derived_expectation(
        modelo=_M130_MODELO,
        filing_year=_M130_YEAR,
        period=Period.from_year_and_code(_M130_YEAR, _M130_PERIOD).registry_token,
    )

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
    assert _numbers_by_section(result) == expected

    # Real Modelo 130 2T-2024 has no required manual casillas (H1 gasto bind;
    # see test_verificado_completo_regression.py) and two ledger-derivable
    # income/expense casillas -- a real, non-trivial classification, proving
    # this is not a vacuous all-empty comparison.
    assert expected["ledger_derivable"], "fixture expectation must be non-trivial"
    assert {"01", "02"} == expected["ledger_derivable"]
    assert expected["optional_manual"], "fixture expectation must be non-trivial"

    # Ledger-derivable rows carry their binding provenance for the checklist.
    ledger_rows = {row["number"]: row["binding_source"] for row in result["ledger_derivable"]}
    assert ledger_rows["01"] == "ledger_renta_income_aggregation"
    assert ledger_rows["02"] == "ledger_renta_gasto_aggregation"

    # No active profile: the checklist cannot check profile coefficients and
    # must say so via a non-blocking advisory notice, not silently.
    assert result["profile_checked"] is False
    assert result["unresolved_profile_bindings"] == []
    notices = unwrap_envelope_notices(invocation.output)
    assert any(notice["code"] == "modelo.requires.no_active_profile" for notice in notices)


def test_requires_omits_previous_filing_bound_casillas_from_every_section() -> None:
    """A ``previous_filing``-bound casilla needs no operator data-gathering action.

    Modelo 130 casilla 05 (pagos fraccionados anteriores) is BOUND with
    ``source = "previous_filing"`` -- a same-modelo direct carry the engine
    resolves automatically once a prior period is filed. It must not appear
    in any of the four checklist sections (it is neither hand-entered, nor
    ledger-derived, nor profile-derived).
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
    all_numbers = set().union(*_numbers_by_section(result).values())
    assert "05" not in all_numbers


@pytest.fixture
def _partial_m100_profile() -> Iterator[None]:
    """Seed a real active profile satisfying a proper subset of M100 profile bindings.

    Mirrors ``test_bindings_list_missing_filter.py``'s partial-profile
    pattern: real facts persisted through the workflow state repository, not
    a mock or a placeholder.
    """
    with profile_create_storage_span("22222222-2222-4222-8222-222222222222"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="22222222-2222-4222-8222-222222222222"),
        )
        workflow_state_repository().update(
            lambda state: set_active_fields(
                state,
                (
                    UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
                    UserProfileFact(path="filing_export.declaration_type", value="1"),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                    UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
                ),
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
    assert warning["suggestion"] == "aeat app ledger ratios set"
    for binding_id in unresolved:
        assert binding_id in warning["context"]["missing_bindings"]

    assert unwrap_schema_envelope('{"schema_version": "2", "command": "x", "status": "warning", "result": {}}') == {}
