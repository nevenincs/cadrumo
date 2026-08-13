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
malformed-still-refuses proof is backed by an out-of-repo mutation: collapsing
the two exception types back into one shows the malformed case would ALSO be
silently swallowed, so the distinct type — not merely the test — is what
keeps the two conditions apart.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import RegistryValidationError, resolve_previous_filing_binding_values
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import resolve_bindings_from_local_store
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BINDING_ID = "irpf.previous_year_economic_activity_net_income"
_M130_FILING_YEAR = 2025
_M130_PERIOD = "1T"
_M100_FILING_YEAR = 2024
_SOURCE_CASILLAS = ("0224", "1479", "1553", "1577")


def _m130_snapshot():
    return resources().modelos.authority.snapshot("130", filing_year=_M130_FILING_YEAR, period=_M130_PERIOD)


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


def test_a_matched_but_incomplete_previous_filing_observation_still_refuses(tmp_path: Path) -> None:
    """A FOUND filing missing a required source casilla is malformed, not absent, and still refuses.

    The source-casilla completeness check is genuinely structural: the
    binding declares four source casillas to sum, and a stored Modelo 100
    observation carrying only one of them is not the same defect as no
    observation at all.
    """
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

        with pytest.raises(RegistryValidationError, match="requires observed casilla"):
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


def test_collapsing_the_two_exception_types_would_swallow_the_malformed_case_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-repo mutation: without the distinct absence signal, malformed also goes silent.

    Monkeypatches the module's absence-signal exception to BE
    :class:`RegistryValidationError` — the collapse this row explicitly
    forbids ("widening the application resolver's except clause ... suppresses
    malformed-binding refusals along with absent observations"). With the two
    types identical, the SAME matched-but-incomplete observation from the
    sibling refusal test is silently absorbed into "unsatisfied" instead of
    refusing, proving the distinct exception type — not merely the test
    asserting a message string — is what keeps the malformed case refusing.
    """
    from ....domain.calculations.registry import _bindings_previous_filing as _module

    snapshot = _m130_snapshot()
    incomplete_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=_M100_FILING_YEAR,
        period="0A",
        casilla_values={validated_casilla_id(_SOURCE_CASILLAS[0], surface="test fixture"): Decimal("1")},
    )

    # Positive control: unmutated, the malformed case still refuses.
    with pytest.raises(RegistryValidationError, match="requires observed casilla"):
        resolve_previous_filing_binding_values(
            snapshot.revision,
            (incomplete_observation,),
            filing_year=_M130_FILING_YEAR,
            period=_M130_PERIOD,
        )

    monkeypatch.setattr(_module, "_PreviousFilingObservationAbsentError", RegistryValidationError)

    resolved = resolve_previous_filing_binding_values(
        snapshot.revision,
        (incomplete_observation,),
        filing_year=_M130_FILING_YEAR,
        period=_M130_PERIOD,
    )
    assert _BINDING_ID not in resolved, (
        "the mutation must collapse the malformed case into unsatisfied — if this still refuses, "
        "the mutation did not actually bite and the proof is void"
    )
