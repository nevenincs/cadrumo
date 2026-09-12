"""The absorbed fold resolves end to end against the converted corpus.

The relation family is gone: a ``relation_prefill`` binding carries the whole
fold -- source modelo, source casilla, dependency role, and the relative
temporal window -- and the slot id IS the fold id. These cases drive the REAL
resolver against the REAL bundled authority and a real local observation store,
so a corpus row that failed to absorb, or a resolver still keyed on a relation
id, fails here rather than passing on a substitute.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ....domain.calculations.registry.relations import (
    relation_prefill_bindings_for_period,
    relation_requirement_index,
    relation_source_requirements,
)
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...aggregation.source_mesh import CalculationSourceContext
from ..observations_repository import CalculationObservationRepository
from ..relation_prefill import RelationPrefillSourceResolver, resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M115_PERCEPTORES: CasillaId = validated_casilla_id("01")
_M115_BASE: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES: CasillaId = validated_casilla_id("03")

#: Per-quarter modelo 115 values the modelo 180 annual summary folds. Chosen so
#: every quarter differs and the expected annual totals below are derived by
#: hand from these numbers, never read back off the resolver.
_M115_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {_M115_PERCEPTORES: Decimal("1"), _M115_BASE: Decimal("250.10"), _M115_RETENCIONES: Decimal("47.52")},
    "2T": {_M115_PERCEPTORES: Decimal("1"), _M115_BASE: Decimal("749.90"), _M115_RETENCIONES: Decimal("142.48")},
    "3T": {_M115_PERCEPTORES: Decimal("2"), _M115_BASE: Decimal("100.00"), _M115_RETENCIONES: Decimal("19.00")},
    "4T": {_M115_PERCEPTORES: Decimal("2"), _M115_BASE: Decimal("400.00"), _M115_RETENCIONES: Decimal("76.00")},
}
_EXPECTED_ANNUAL_BASE = Decimal("1500.00")
_EXPECTED_ANNUAL_RETENCIONES = Decimal("285.00")


@cache
def _snapshot(modelo: str, filing_year: int, period: str) -> RegistrySnapshot:
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)


def _observations() -> tuple[RegistryModeloObservation, ...]:
    return tuple(
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in _M115_QUARTERS.items()
    )


def _seeded_repository() -> CalculationObservationRepository:
    repository = CalculationObservationRepository()
    for observation in _observations():
        repository.save(
            repository.prepare_observation_envelope(
                observation,
                source_kind="app_filing",
                stamped_revision_id=revision_id_for_observation(observation),
            ),
        )
    return repository


def test_the_corpus_declares_the_m180_fold_entirely_on_the_binding_provider() -> None:
    """No second declaration remains: the slot names its own source and window."""
    snapshot = _snapshot("180", 2026, "0A")
    folds = relation_prefill_bindings_for_period(snapshot.revision, period="0A")

    assert folds, "modelo 180 declares at least one relation-prefill fold slot"
    for binding, provider in folds:
        assert isinstance(provider, RelationPrefillProvider)
        assert provider.source_modelo == "115"
        assert provider.relation_kind == "annual_summary"
        assert provider.dependency_role == "periodic_to_annual_summary"
        assert provider.required_period_anchors_for_target("0A") == (
            (0, "1T"),
            (0, "2T"),
            (0, "3T"),
            (0, "4T"),
        )
        assert binding.legal_refs


def test_requirements_are_indexed_by_the_slot_binding_id() -> None:
    snapshot = _snapshot("180", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    index = relation_requirement_index(requirements)

    slot_ids = {binding.id for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period="0A")}
    assert set(index) == slot_ids
    for requirement in requirements:
        assert requirement.source_modelo == "115"
        assert requirement.filing_year == 2026
        assert requirement.periods == ("1T", "2T", "3T", "4T")
        assert requirement.target_bindings


def test_the_real_resolver_folds_the_quarters_into_the_slot_values(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _seeded_repository()
        snapshot = _snapshot("180", 2026, "0A")

        resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="180",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "0A"),
                revision=snapshot.revision,
            ),
        )

    assert resolution.owned_sources == (BindingSourceKind.RELATION_PREFILL,)
    # The fold slot IS the binding, so the two channels carry the same keys and
    # the same values; a divergence would mean a second materialisation step
    # had crept back in.
    assert dict(resolution.relation_values) == dict(resolution.binding_values)
    assert set(resolution.relation_values) <= {
        binding.id for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period="0A")
    }
    assert Decimal(_EXPECTED_ANNUAL_BASE) in set(resolution.binding_values.values())
    assert Decimal(_EXPECTED_ANNUAL_RETENCIONES) in set(resolution.binding_values.values())


def test_resolved_provenance_names_the_filed_casilla_terminal_origin(tmp_path: Path) -> None:
    """Every value this resolver produces is read off a filed modelo casilla.

    Naming the origin class on the provenance is what lets the terminal-origin
    audit compare the resolved origin against the binding's authored
    expectation instead of inferring it from the resolver id.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _seeded_repository()
        snapshot = _snapshot("180", 2026, "0A")

        resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="180",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "0A"),
                revision=snapshot.revision,
            ),
        )

    assert resolution.provenance
    for item in resolution.provenance:
        assert item.terminal_origin is TerminalOriginClass.FILED_MODELO_CASILLA
        assert item.contributor_binding_source is BindingSourceKind.RELATION_PREFILL
        assert item.source_modelo == "115"
        assert item.source_filing_year == 2026


def test_prefill_values_carry_the_slot_bindings_own_grounding(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _seeded_repository()
        snapshot = _snapshot("180", 2026, "0A")
        prefill = resolve_relations_from_local_store(snapshot, repository=repository)

    bindings_by_id = {
        binding.id: binding for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period="0A")
    }
    assert prefill.values
    for item in prefill.values:
        binding = bindings_by_id[item.relation]
        assert item.legal_refs == tuple(binding.legal_refs)
        assert item.source_refs == tuple(binding.source_refs)
        assert item.source_modelo == "115"
