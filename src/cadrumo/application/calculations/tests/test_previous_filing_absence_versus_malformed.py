"""Absence and malformation are two different conditions at the previous-filing raise site.

``_resolve_anchor_values`` used to raise the SAME ``RegistryValidationError``
for a source filing that is genuinely absent (AEAT has simply never confirmed
it) and for a structurally malformed binding or observation (an ambiguous
multiple-match, or a matched filing missing a required source casilla). That
asymmetry made an absent Modelo 100 prior year produce a refusal or an
advisory purely depending on whether the operator had declared an unrelated
profile fact (``activity_start_date``) — the two-bucket differential this
module reuses as its own instrument, per the row that decided ADVISE is the
correct behaviour for absence and left the malformed case refusing.

Real registry, real (encrypted) observation repository, no mocks. The
incomplete and ambiguous observations exercise the two malformed inputs that
must keep refusing, while the empty repository exercises genuine absence.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings_previous_filing import resolve_previous_filing_binding_values
from ....domain.calculations.registry.errors import RegistryValidationError
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import resolve_bindings_from_local_store
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BINDING_ID = "irpf.previous_year_economic_activity_net_income"
_M130_FILING_YEAR = 2025
_M130_PERIOD = "1T"
_M100_FILING_YEAR = 2024
_SOURCE_CASILLAS = ("0224", "1479", "1553", "1577")


def _m130_snapshot():
    return bundled_authority().snapshot("130", filing_year=_M130_FILING_YEAR, period=_M130_PERIOD)


def test_absent_previous_filing_produces_the_same_unsatisfied_result_regardless_of_activity_start(
    tmp_path: Path,
) -> None:
    """The two-bucket differential: an empty store, with and without a declared activity start.

    Both buckets are identical but for ``activity_start_date`` — the profile
    fact whose mere presence used to route the SAME absent Modelo 100 filing
    to a raise on one side and an advisory on the other. Neither anchor in
    this Modelo 130 target is scoped out by the declared start (2015 predates
    the required Modelo 100 2024 anchor), so both buckets reach the resolver
    with the identical genuinely-absent condition.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = _m130_snapshot()
        repository = CalculationObservationRepository()

        report_without_activity_start = resolve_bindings_from_local_store(
            snapshot,
            repository=repository,
            activity_start_date=None,
        )
        report_with_activity_start = resolve_bindings_from_local_store(
            snapshot,
            repository=repository,
            activity_start_date=date(2015, 1, 1),
        )

    for report in (report_without_activity_start, report_with_activity_start):
        assert _BINDING_ID not in report.binding_values
        unsatisfied_ids = {item.binding_id for item in report.unsatisfied}
        assert _BINDING_ID in unsatisfied_ids

    assert set(report_without_activity_start.binding_values) == set(report_with_activity_start.binding_values)
    without_unsatisfied = {item.binding_id for item in report_without_activity_start.unsatisfied}
    with_unsatisfied = {item.binding_id for item in report_with_activity_start.unsatisfied}
    assert without_unsatisfied == with_unsatisfied


def test_a_matched_previous_filing_resolves_from_its_applicable_source_casilla(tmp_path: Path) -> None:
    """The canonical ``y/o`` binding sums whichever applicable M100 source is observed."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = _m130_snapshot()
        repository = CalculationObservationRepository()
        incomplete_observation = registry_grounded_modelo_observation(
            modelo="100",
            filing_year=_M100_FILING_YEAR,
            period="0A",
            casilla_values={validated_casilla_id(_SOURCE_CASILLAS[0], surface="test fixture"): Decimal("1")},
        )
        repository.save(
            repository.prepare_observation_envelope(incomplete_observation, source_kind="app_filing"),
        )

        report = resolve_bindings_from_local_store(snapshot, repository=repository)

    assert report.binding_values[_BINDING_ID] == Decimal("1")


def test_a_matched_previous_filing_with_no_declared_source_casilla_still_refuses(tmp_path: Path) -> None:
    """Optional candidates cannot turn a structurally unrelated observation into a silent zero."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = _m130_snapshot()
        repository = CalculationObservationRepository()
        unrelated_observation = registry_grounded_modelo_observation(
            modelo="100",
            filing_year=_M100_FILING_YEAR,
            period="0A",
            casilla_values={validated_casilla_id("0670", surface="test fixture"): Decimal("1")},
        )
        repository.save(repository.prepare_observation_envelope(unrelated_observation, source_kind="app_filing"))

        with pytest.raises(RegistryValidationError, match="requires at least one observed source casilla"):
            resolve_bindings_from_local_store(snapshot, repository=repository)


def test_an_ambiguous_multiple_observed_filing_match_still_refuses() -> None:
    """Two observed filings for the same (modelo, year, period) key is malformed, not absent.

    Exercises the domain resolver directly with a hand-built observation pair
    sharing one key — the shape a real repository (one envelope per key)
    cannot itself produce, but the resolver's own invariant must still catch.
    """
    snapshot = _m130_snapshot()
    casilla_values = {
        validated_casilla_id(casilla_id, surface="test fixture"): Decimal(index + 1)
        for index, casilla_id in enumerate(_SOURCE_CASILLAS)
    }
    duplicate_observations = (
        registry_grounded_modelo_observation(
            modelo="100",
            filing_year=_M100_FILING_YEAR,
            period="0A",
            casilla_values=casilla_values,
        ),
        registry_grounded_modelo_observation(
            modelo="100",
            filing_year=_M100_FILING_YEAR,
            period="0A",
            casilla_values=casilla_values,
        ),
    )

    with pytest.raises(RegistryValidationError, match="found 2"):
        resolve_previous_filing_binding_values(
            snapshot.revision,
            duplicate_observations,
            filing_year=_M130_FILING_YEAR,
            period=_M130_PERIOD,
        )
