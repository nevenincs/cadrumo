"""Contract tests for the relation prefill resolver.

The CLI's ``--prefill-relations`` flag delegates to
``resolve_relations_from_local_store``: it walks every relation
the snapshot's revision declares, looks up prior filings in the
local observation store, and folds them through the declared
aggregation op. The output is the ``RelationValues`` record the
engine consumes to render the Sheets workbook's relation cells.

Wrong behaviour here means the Sheets workbook exports either
blank cells (operator must hand-enter) or stale prefilled values
the operator does not notice. Tests load the modelo 190 snapshot
(which has the annual-summary relations rolling up modelo 111
quarterly perceptors) and verify resolver behaviour against a
real fixture of stored observations.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from ...core.paths import PROJECT_ROOT
from ...domain.calculations.registry._bindings import CasillaObservation, RegistryFilingObservation
from ...domain.calculations.registry._loader import load_registry_tree
from ._observations_repository import CalculationObservationRepository, _ObservationEnvelopePayload
from ._relation_prefill import _gather_observations_for_snapshot, _provenance_note, resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class _FakeRepository:
    """In-memory `CalculationObservationRepository` substitute.

    Implements only the `iter_modelo` surface the relation resolver
    consumes. Keeps the test free of the SecureObjectRepository's
    encryption / SQL backing — the resolver does not care which
    backend produced the observations, only that they have the
    right shape.
    """

    def __init__(self, observations: tuple[RegistryFilingObservation, ...]) -> None:
        self._observations = observations

    def iter_modelo(self, modelo: str) -> Iterator[_ObservationEnvelopePayload]:
        for obs in self._observations:
            if obs.modelo != modelo:
                continue
            yield _ObservationEnvelopePayload(
                observation=obs,
                captured_at=datetime.now(UTC),
                source_kind="app_filing",
            )


def _modelo_190_snapshot():
    from ...domain.calculations.registry._snapshot import build_snapshot

    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(m for m in modelos if m.id == "190")
    return build_snapshot(
        modelo=modelo,
        catalogues=catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2025,
        period="0A",
    )


def _quarterly_111_observations(filing_year: int) -> tuple[RegistryFilingObservation, ...]:
    """One observation per quarter with a tiny set of casilla values."""

    seed: dict[str, Decimal] = {
        "01": Decimal("10"),  # number of perceptors
        "02": Decimal("1000"),  # base
        "03": Decimal("150"),  # retencion
    }
    # Pad with zero-valued observations for every other casilla number the
    # 111 registry declares so the typed-observation contract holds for
    # downstream consumers that index by casilla id.
    for n in range(1, 31):
        seed.setdefault(f"{n:02d}", Decimal("0"))

    return tuple(
        RegistryFilingObservation(
            modelo="111",
            filing_year=filing_year,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in seed.items()),
        )
        for period in ("1T", "2T", "3T", "4T")
    )


def test_resolve_relations_empty_repository_yields_all_none_values() -> None:
    """No prior filings → every RelationValue gets ``value=None`` + no provenance."""

    snapshot = _modelo_190_snapshot()
    repo = _FakeRepository(observations=())

    result = resolve_relations_from_local_store(snapshot, repository=cast(CalculationObservationRepository, repo))

    assert len(result.values) == len(snapshot.revision.relations)
    for relation_value in result.values:
        assert relation_value.value is None
        # provenance defaults to operator_manual when value is None
        assert relation_value.provenance == "operator_manual"


def test_resolve_relations_populated_repository_returns_local_filing_provenance() -> None:
    """Snapshot's modelo 190 relations roll up modelo 111 quarterlies."""

    snapshot = _modelo_190_snapshot()
    repo = _FakeRepository(observations=_quarterly_111_observations(filing_year=2025))

    result = resolve_relations_from_local_store(snapshot, repository=cast(CalculationObservationRepository, repo))

    populated = [rv for rv in result.values if rv.value is not None]
    assert populated, "modelo 190 should resolve at least one relation from quarterly 111 observations"
    for relation_value in populated:
        assert relation_value.provenance == "local_filing"
        assert relation_value.source_filing_year == 2025
        assert relation_value.resolved_at is not None
        assert relation_value.note is not None
        assert "modelo 111" in relation_value.note


def test_resolve_relations_resolved_values_match_sum_of_quarterly_inputs() -> None:
    """Annual rollup relations sum the quarterly source casillas."""

    snapshot = _modelo_190_snapshot()
    repo = _FakeRepository(observations=_quarterly_111_observations(filing_year=2025))

    result = resolve_relations_from_local_store(snapshot, repository=cast(CalculationObservationRepository, repo))

    # Total perceptors: casilla 01 from each of the 4 quarters in 111
    # (each quarter declares 10 perceptors) should sum to 40 when the
    # rollup relation targets source_output "01".
    perceptor_relations_with_value = {rv.relation: rv for rv in result.values if rv.value is not None}
    rollup_01 = next(
        (
            rel
            for rel in snapshot.revision.relations
            if rel.source_output == "01" and rel.id in perceptor_relations_with_value
        ),
        None,
    )
    if rollup_01 is not None:
        assert perceptor_relations_with_value[rollup_01.id].value == Decimal("40")


def test_resolve_relations_partial_observations_downgrades_to_none() -> None:
    """Repository missing some quarters → resolver downgrades cleanly to None.

    Provides only 1T observation for modelo 111. The runtime resolver
    expects all four quarters for an annual rollup; rather than crash
    the prefill resolver catches the failure and emits operator_manual
    provenance so the engine renders blank cells.
    """

    snapshot = _modelo_190_snapshot()
    partial = (_quarterly_111_observations(filing_year=2025)[0],)
    repo = _FakeRepository(observations=partial)

    result = resolve_relations_from_local_store(snapshot, repository=cast(CalculationObservationRepository, repo))

    # Every relation should fall back to operator_manual.
    for relation_value in result.values:
        assert relation_value.provenance == "operator_manual"
        assert relation_value.value is None


def test_provenance_note_renders_modelo_periods_year_and_timestamp() -> None:
    when = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    note = _provenance_note(
        "modelo-190-rel-111-perceptores-anual",
        "111",
        ("1T", "2T", "3T", "4T"),
        2025,
        when,
    )
    assert "modelo 111" in note
    assert "1T+2T+3T+4T" in note
    assert "2025" in note
    assert "2025-06-01" in note


def test_gather_observations_filters_by_filing_year_and_period() -> None:
    """The gatherer only keeps observations matching a relation's source slice."""

    snapshot = _modelo_190_snapshot()
    # Include a 2024 observation and a 2025 observation; only the 2025
    # one should be gathered (the 190 relations specify
    # filing_year_delta=0 against the target).
    obs_2024 = _quarterly_111_observations(filing_year=2024)
    obs_2025 = _quarterly_111_observations(filing_year=2025)
    repo = _FakeRepository(observations=obs_2024 + obs_2025)

    gathered = _gather_observations_for_snapshot(snapshot, repository=cast(CalculationObservationRepository, repo))

    years = {obs.filing_year for obs in gathered}
    assert years == {2025}, f"expected only 2025 observations, got {years}"
