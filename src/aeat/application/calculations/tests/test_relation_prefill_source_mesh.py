"""Application tests for relation prefill source mesh enrollment.

Finding F2 — cross-domain-handoffs-swarm-audit 2026-05-16: the bare
``except Exception`` in ``resolve_relations_from_local_store`` was narrowed to
``except RegistryValidationError`` so that unexpected failures surface instead
of silently downgrading to ``operator_manual`` provenance. The operator-manual
fallback is legitimate when the local store genuinely has no prior filings; it
must not mask structural failures.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext, CalculationSourceResolution
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import RelationPrefillSourceResolver, resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo_115_observations() -> tuple[RegistryModeloObservation, ...]:
    values_by_period = {
        "1T": {"01": Decimal("1"), "02": Decimal("250.10"), "03": Decimal("47.52")},
        "2T": {"01": Decimal("1"), "02": Decimal("749.90"), "03": Decimal("142.48")},
        "3T": {"01": Decimal("2"), "02": Decimal("1200.00"), "03": Decimal("228.00")},
        "4T": {"01": Decimal("1"), "02": Decimal("-50.25"), "03": Decimal("0.00")},
    }
    return tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
        )
        for period, casilla_values in values_by_period.items()
    )


def test_relation_prefill_source_resolver_matches_local_store_prefill(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        for observation in _modelo_115_observations():
            repository.save_observation(observation, source_kind="app_filing")

        snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")
        prefill = resolve_relations_from_local_store(snapshot, repository=repository)
        source_resolution = RelationPrefillSourceResolver(
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

        assert source_resolution.relation_values == {
            item.relation: item.value for item in prefill.values if item.value is not None
        }
        assert source_resolution.owned_sources == ("relation_prefill",)
        assert source_resolution.provenance
        assert all(item.source_kind == "relation_prefill" for item in source_resolution.provenance)
        assert {item.source_ref for item in source_resolution.provenance} == {
            "modelo-180-rel-115-perceptores-anual:2026:1T,2T,3T,4T",
            "modelo-180-rel-115-base-anual:2026:1T,2T,3T,4T",
            "modelo-180-rel-115-retenciones-anual:2026:1T,2T,3T,4T",
        }


def test_resolve_relations_returns_operator_manual_blanks_when_local_store_is_empty(tmp_path: Path) -> None:
    """Empty local store produces blank relation cells without raising.

    When the operator has no prior filings in the local store,
    ``resolve_relations_from_local_store`` must return a
    :class:`RelationValues` with ``value=None`` for every relation
    declared in the snapshot, leaving the engine to emit blank cells
    the operator fills by hand. This path must NOT raise (the
    narrowed ``except RegistryValidationError`` from F2 of the
    cross-domain-handoffs audit 2026-05-16 must not accidentally
    broaden back to a silent-swallow ``except Exception``).
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")
        result = resolve_relations_from_local_store(snapshot)

    assert result.values, "M180 must have at least one relation"
    # Every relation must surface as None (operator-manual) when no
    # prior filings exist — never raises, never crashes, never fabricates.
    assert all(rv.value is None for rv in result.values), (
        "empty local store must produce all-None relation values; "
        "a non-None value means the prefill fabricated data from nothing"
    )


def test_resolve_relations_produced_values_carry_provenance_string_when_resolved(tmp_path: Path) -> None:
    """Resolved relations carry the local-filing provenance marker.

    When prior filings exist and the resolver succeeds, every
    :class:`RelationValue` with a non-None value must carry
    ``provenance='local_filing'`` so the engine can distinguish
    operator-sourced data from prefilled data in the workbook.
    This pins the provenance-string contract across the
    modelo→filing handoff boundary (F2 finding, 2026-05-16 audit).
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        for observation in _modelo_115_observations():
            repository.save_observation(observation, source_kind="app_filing")

        snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")
        result = resolve_relations_from_local_store(snapshot, repository=repository)

    resolved = [rv for rv in result.values if rv.value is not None]
    assert resolved, "at least one relation must resolve from M115 observations"
    for rv in resolved:
        assert rv.provenance == "local_filing", (
            f"resolved relation {rv.relation!r} must carry provenance='local_filing' "
            f"but got {rv.provenance!r}; the provenance contract was lost at the "
            "modelo→filing handoff boundary"
        )


def _diagnosed_relation_ids(resolution: CalculationSourceResolution) -> set[str]:
    return {
        diagnostic.relation_id
        for diagnostic in resolution.diagnostics
        if diagnostic.source_kind == "relation_prefill" and diagnostic.relation_id is not None
    }


def test_unresolved_non_formula_relation_with_materialised_slot_is_not_flagged(tmp_path: Path) -> None:
    """W03.P06.S18 false-fire guard: a cold-start non-formula relation is silent.

    Modelo 202's relations are referenced by no formula but each materialises a
    declared ``target_binding`` slot the engine threads (resolving to the
    cold-start zero). An empty local store leaves them unresolved, which is the
    intended cross-modelo carry cold-start — it MUST NOT surface a diagnostic, or
    the M200/M202/M100 fold-in contract breaks.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # empty store
        snapshot = resources().modelos.authority.snapshot("202", filing_year=2025, period="2P")

        from .._relation_prefill import _formula_relation_ids

        declared_binding_ids = {binding.id for binding in snapshot.revision.bindings}
        non_formula = {r.id for r in snapshot.revision.relations} - _formula_relation_ids(snapshot)
        assert non_formula, "M202 must declare at least one non-formula relation for this fixture"
        # Every M202 non-formula relation materialises a real binding slot.
        assert all(r.target_binding in declared_binding_ids for r in snapshot.revision.relations if r.id in non_formula)

        source_resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="202",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "2P"),
                revision=snapshot.revision,
            ),
        )

    assert non_formula.isdisjoint(_diagnosed_relation_ids(source_resolution)), (
        "a cold-start non-formula relation whose target_binding materialises an observable slot "
        "must NOT fire the S18 advisory — that would regress the cross-modelo carry contract"
    )


def test_orphaned_non_formula_relation_surfaces_advisory_diagnostic(tmp_path: Path) -> None:
    """W03.P06.S18: an unresolved non-formula relation that reaches nothing is surfaced.

    The narrow silent gap: a declared relation referenced by no formula whose
    ``target_binding`` is NOT a declared binding on the revision materialises no
    slot and previously produced neither a value nor a diagnostic — its absence
    reached nothing observable. The resolver MUST now emit a non-blocking advisory
    for exactly that orphaned case.

    The registry validator forbids an orphaned relation in shipped TOML, so the
    fixture builds the revision directly via ``model_copy`` (which does not
    re-run cross-section validation) to exercise the defensive guard.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # empty store — relation cannot resolve
        snapshot = resources().modelos.authority.snapshot("202", filing_year=2025, period="2P")

        from .._relation_prefill import _formula_relation_ids

        seed_relation = next(r for r in snapshot.revision.relations if r.id not in _formula_relation_ids(snapshot))
        declared_binding_ids = {binding.id for binding in snapshot.revision.bindings}
        orphan_target = "no-such-binding-orphan-xyz"
        assert orphan_target not in declared_binding_ids
        orphan_relation = seed_relation.model_copy(
            update={"id": "orphan-non-formula-relation-test", "target_binding": orphan_target},
        )
        orphaned_revision = snapshot.revision.model_copy(
            update={"relations": (*snapshot.revision.relations, orphan_relation)},
        )
        orphaned_snapshot = snapshot.model_copy(update={"revision": orphaned_revision})

        source_resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=orphaned_snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="202",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "2P"),
                revision=orphaned_revision,
            ),
        )

    assert orphan_relation.id in _diagnosed_relation_ids(source_resolution), (
        "an unresolved non-formula relation that materialises no binding slot produced no "
        "diagnostic — the narrow silent gap S18 closes"
    )
