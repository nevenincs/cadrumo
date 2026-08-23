"""Application tests for relation prefill source mesh enrollment.

``resolve_relations_from_local_store`` catches only
``RegistryValidationError`` (never a bare ``except Exception``), so that
unexpected failures surface instead of silently downgrading to
``operator_manual`` provenance. The operator-manual fallback is legitimate
when the local store genuinely has no prior filings; it must not mask
structural failures.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core import BindingSourceKind, CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    RegistryFoldRequirement,
    RegistryModeloObservation,
    RegistrySnapshot,
    relation_consumption_channels,
    relation_consumption_index,
)
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext, CalculationSourceResolution
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import (
    RelationPrefillSourceResolver,
    _scoped_relation_source_requirements,
    resolve_relations_from_local_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19")
_M202_2023_2024_PRIOR_PAYMENTS_BINDING = "modelo-202-2023-2024-pagos-fraccionados-anteriores"


@cache
def _snapshot(modelo: str, filing_year: int, period: str) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


def _modelo_115_observations() -> tuple[RegistryModeloObservation, ...]:
    values_by_period: dict[str, dict[CasillaId, Decimal]] = {
        "1T": {
            _M115_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_CASILLA: Decimal("250.10"),
            _M115_RETENCIONES_CASILLA: Decimal("47.52"),
        },
        "2T": {
            _M115_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_CASILLA: Decimal("749.90"),
            _M115_RETENCIONES_CASILLA: Decimal("142.48"),
        },
        "3T": {
            _M115_PERCEPTORES_CASILLA: Decimal("2"),
            _M115_BASE_CASILLA: Decimal("1200.00"),
            _M115_RETENCIONES_CASILLA: Decimal("228.00"),
        },
        "4T": {
            _M115_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_CASILLA: Decimal("-50.25"),
            _M115_RETENCIONES_CASILLA: Decimal("0.00"),
        },
    }
    return tuple(
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in values_by_period.items()
    )


def test_relation_prefill_source_resolver_matches_local_store_prefill(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        for observation in _modelo_115_observations():
            repository.save(repository.prepare_observation_envelope(observation, source_kind="app_filing"))

        snapshot = _snapshot("180", 2026, "0A")
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
        assert source_resolution.owned_sources == (BindingSourceKind.RELATION_PREFILL,)
        assert source_resolution.provenance
        assert all(item.contributor_source_kind == "relation_prefill" for item in source_resolution.provenance)
        relations_by_id = {relation.id: relation for relation in snapshot.revision.relations}
        for item in prefill.values:
            relation = relations_by_id[item.relation]
            assert item.source_modelo == relation.source_modelo
            assert item.source_casilla_ids == (relation.source_casilla_id,)
            assert item.legal_refs == tuple(relation.legal_refs)
            assert item.source_refs == tuple(relation.source_refs)
        # RET-1: the perceptores relation is retired (decl.total-perceptores is now
        # a distinct-NIF count from the retención store); only the monetary
        # base/retenciones relations remain on the relation_prefill source.
        assert {item.source_ref for item in source_resolution.provenance} == {
            "modelo-180-rel-115-base-anual:115:2026:1T,2T,3T,4T:02",
            "modelo-180-rel-115-retenciones-anual:115:2026:1T,2T,3T,4T:03",
        }
        resolved_prefill = {item.relation: item for item in prefill.values if item.value is not None}
        provenance_by_relation = {item.relation_id: item for item in source_resolution.provenance}
        assert set(provenance_by_relation) == set(resolved_prefill)
        for relation_id, provenance in provenance_by_relation.items():
            # Every provenance item here is confirmed relation_prefill-sourced (line
            # above), which always carries a relation_id; the field is Optional only
            # for other source kinds' provenance shape.
            assert relation_id is not None
            prefilled = resolved_prefill[relation_id]
            assert provenance.source_modelo == prefilled.source_modelo
            assert provenance.source_filing_year == prefilled.source_filing_year
            assert provenance.source_periods == prefilled.source_periods
            assert provenance.source_casilla_ids == prefilled.source_casilla_ids
            assert provenance.legal_refs == prefilled.legal_refs
            assert provenance.source_refs == prefilled.source_refs
            # The registry's declared dependency classification for M115 (the M180
            # dep-115 dependency_classification) survives the resolver join intact:
            # a real, non-default declared treatment reaches the operator-facing
            # provenance trace, not a silently dropped/defaulted empty string.
            assert provenance.dependency_treatment == prefilled.dependency_treatment
            assert provenance.dependency_treatment == "direct_annual_settlement"


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
        snapshot = _snapshot("180", 2026, "0A")
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
            repository.save(repository.prepare_observation_envelope(observation, source_kind="app_filing"))

        snapshot = _snapshot("180", 2026, "0A")
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


def test_unresolved_bound_carry_the_taxpayer_files_is_advised(tmp_path: Path) -> None:
    """A bound carry whose source the taxpayer FILES is advised when it is absent.

    This reverses what this module previously pinned. The old contract was that a
    non-formula relation materialising a declared ``target_binding`` must never
    surface a diagnostic, on the ground that its unresolved state is the intended
    cross-modelo cold start.

    That rationale was measured and does not hold. Cold start is already handled
    upstream: ``_scoped_relation_source_requirements`` removes source periods the
    taxpayer had no obligation for, against the declared activity start, so a
    genuine first-ejercicio filer's carries never reach the advisory at all (pinned
    by the sibling first-ejercicio test in the Modelo 200 live module). What the
    blanket silence additionally hid was the filer who DID have the obligation and
    whose filing is simply absent — and there the engine threads the slot as a
    zero, which reduces no liability and over-declares.

    Two narrowings keep it honest and are asserted below: the source period must
    have survived activity-start scoping, and the source modelo must be one the
    taxpayer FILES. A retención the payer files is unactionable for this taxpayer
    and stays silent.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # empty store
        snapshot = _snapshot("202", 2025, "2P")

        declared_binding_ids = {binding.id for binding in snapshot.revision.bindings}
        consumption_index = relation_consumption_index(snapshot.revision)
        non_formula = {
            relation.id
            for relation in snapshot.revision.relations
            if not any(
                channel.startswith("formula_") for channel in relation_consumption_channels(relation, consumption_index)
            )
        }
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

    advised = _diagnosed_relation_ids(source_resolution)
    taxpayer_filed = {
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if classification.taxpayer_files_source
    }
    relation_source = {relation.id: relation.source_modelo for relation in snapshot.revision.relations}
    expected = {
        relation_id
        for relation_id in non_formula
        if relation_source.get(relation_id) in taxpayer_filed and relation_id in advised
    }
    assert expected, (
        "this fixture must exercise at least one bound carry whose source the taxpayer files, "
        "or the advisory it pins is never reached"
    )
    # No carry whose source the taxpayer does NOT file may be advised: that filer
    # cannot act on it, so it would be unactionable noise.
    unactionable = {
        relation_id
        for relation_id in advised
        if relation_source.get(relation_id) is not None and relation_source[relation_id] not in taxpayer_filed
    }
    assert not unactionable, (
        f"a carry whose source modelo the taxpayer does not file must stay silent; got {unactionable}"
    )


def test_relation_consumption_index_traverses_committed_m100_settlement_expression() -> None:
    """The relation prefill path must retain both real M100 instalment relation leaves."""
    snapshot = _snapshot("100", 2024, "0A")
    index = relation_consumption_index(snapshot.revision)
    formula_relation_ids = {
        relation.id
        for relation in snapshot.revision.relations
        if "formula_relation" in relation_consumption_channels(relation, index)
    }

    assert {
        "renta-2024-rel-130-pagos-fraccionados",
        "renta-2024-rel-131-pagos-fraccionados",
    }.issubset(formula_relation_ids)


def test_operator_manual_relation_detail_is_a_debug_breadcrumb_not_a_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The unresolved-source 'remains operator-manual' detail is DEBUG, never WARNING stderr.

    An empty local store leaves the M202 cross-modelo carries unresolved — the
    intended cold-start (materialised zero slot). Their 'remains operator-manual'
    detail was formerly a ``_log.warning`` stderr line, which was
    environment-inconsistent (present under one logging config, absent under
    another) and made replay goldens unportable, and bypassed the typed Notice
    channel (aeat-cli-contract). It must now be emitted
    at DEBUG only. The DEBUG-level capture below still sees the breadcrumb (proving
    the cold-start path fired — the anti-tautology leg), and every such record is
    DEBUG, so a default WARNING-level operator surface sees none of it.
    """
    logger_name = "cadrumo.application.calculations._relation_prefill"
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # empty store — cold-start
        snapshot = _snapshot("202", 2025, "2P")
        with caplog.at_level(logging.DEBUG, logger=logger_name):
            RelationPrefillSourceResolver(
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

    operator_manual_records = [
        record
        for record in caplog.records
        if record.name == logger_name and "remains operator-manual" in record.getMessage()
    ]
    assert operator_manual_records, (
        "the cold-start path must still emit the 'remains operator-manual' detail at DEBUG "
        "(anti-tautology: an empty store must exercise the unresolved-requirement branch)"
    )
    warning_or_above = [record for record in operator_manual_records if record.levelno >= logging.WARNING]
    assert not warning_or_above, (
        "the 'remains operator-manual' detail must be a DEBUG breadcrumb, never a WARNING+ stderr line "
        "(aeat-cli-contract); found: "
        f"{[(r.levelname, r.getMessage()) for r in warning_or_above]}"
    )


def test_m202_1p_previous_payments_materialises_zero_without_prior_relation(tmp_path: Path) -> None:
    """Modelo 202 1P has no previous same-year installment to fold into casilla 30."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        snapshot = _snapshot("202", 2024, "1P")

        source_resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="202",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "1P"),
                revision=snapshot.revision,
            ),
        )

    assert source_resolution.binding_values[_M202_2023_2024_PRIOR_PAYMENTS_BINDING] == Decimal("0")
    assert source_resolution.relation_values == {}


def test_m202_2p_previous_payments_stays_unresolved_without_prior_filing(tmp_path: Path) -> None:
    """Modelo 202 2P still requires the actual 1P installment relation."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        snapshot = _snapshot("202", 2024, "2P")

        source_resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="202",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "2P"),
                revision=snapshot.revision,
            ),
        )

    assert _M202_2023_2024_PRIOR_PAYMENTS_BINDING not in source_resolution.binding_values
    assert source_resolution.relation_values == {}


def test_orphaned_non_formula_relation_surfaces_advisory_diagnostic(tmp_path: Path) -> None:
    """An unresolved non-formula relation that reaches nothing is surfaced.

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
        snapshot = _snapshot("202", 2025, "2P")

        consumption_index = relation_consumption_index(snapshot.revision)
        seed_relation = next(
            relation
            for relation in snapshot.revision.relations
            if not any(
                channel.startswith("formula_") for channel in relation_consumption_channels(relation, consumption_index)
            )
        )
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
        "diagnostic — the narrow silent gap this guard closes"
    )


def test_modelo_190_2025_empty_store_collapses_absent_m111_source_to_one_diagnostic(tmp_path: Path) -> None:
    """Ten Modelo 190 relations reading the same absent Modelo 111 quarter fold to one advisory.

    The real-corpus measurement the grouping change was built against: an
    empty local store leaves every one of the annual resumen's monetary
    relations unresolved, each reading a different Modelo 111 casilla (02,
    05, 08, ..., 28) off the SAME absent 1T-4T filing. Un-grouped, that is
    ten diagnostics naming one root cause; grouped by
    ``(source_modelo, filing_year, periods)``, it must be exactly one.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # empty store — nothing to resolve
        snapshot = _snapshot("190", 2025, "0A")
        source_resolution = RelationPrefillSourceResolver(
            repository=repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="190",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
            ),
        )

    m111_diagnostics = [
        diagnostic for diagnostic in source_resolution.diagnostics if diagnostic.message.startswith("modelo 111 2025")
    ]
    assert len(m111_diagnostics) == 1, (
        "one absent Modelo 111 source filing must fold to one diagnostic, not one per relation "
        f"(got {len(m111_diagnostics)} diagnostics naming it)"
    )
    diagnostic = m111_diagnostics[0]
    # The row's own measurement: ten annual-summary relations share this absent
    # source. The structured field carries every one, machine-readable, whatever
    # the length-capped prose message elides.
    assert len(diagnostic.relation_ids) >= 9
    assert set(diagnostic.relation_ids) <= set(source_resolution.unresolved_relation_ids)


# ---------------------------------------------------------------------------
# IRPF-1: activity-start-scoped relation fold (partial-year-start filer)
# ---------------------------------------------------------------------------


def _modelo_130_pagos_observations(values_by_period: dict[str, Decimal]) -> tuple[RegistryModeloObservation, ...]:
    """Build M130 observations carrying casilla 19 (resultado / pago fraccionado) per period."""
    return tuple(
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=2024,
            period=period,
            casilla_values={_M130_RESULTADO_FINAL_CASILLA: value},
        )
        for period, value in values_by_period.items()
    )


def _m130_pagos_requirement(
    requirements: tuple[RegistryFoldRequirement, ...],
) -> RegistryFoldRequirement:
    return next(
        r for r in requirements if r.source_modelo == "130" and r.source_casilla_ids == (_M130_RESULTADO_FINAL_CASILLA,)
    )


def test_scoped_relation_source_requirements_drops_pre_activity_quarters() -> None:
    """A mid-year-start filer's pre-activity source quarters are scoped out of the fold (IRPF-1).

    Grounded in the activity-start first-filer rule (the same partition the
    cross-period clean-state gate applies): a quarter whose span ends strictly
    before the operator's activity start carries no filing obligation, so it must
    not be required by the annual fold. Expected period sets derive from the
    calendar boundary (1T ends 31-Mar), not from the relation formula.
    """
    snapshot = _snapshot("100", 2024, "0A")
    # Activity started 2024-04-01: 1T (ends 2024-03-31) is STRICTLY before it.
    scoped = _scoped_relation_source_requirements(snapshot, date(2024, 4, 1))
    assert _m130_pagos_requirement(scoped).periods == ("2T", "3T", "4T")
    # Full-year filer (activity 2024-01-01): the alta-containing 1T is in scope; nothing dropped.
    full = _scoped_relation_source_requirements(snapshot, date(2024, 1, 1))
    assert _m130_pagos_requirement(full).periods == ("1T", "2T", "3T", "4T")
    # None (fail-closed / non-operator context): no scoping.
    none = _scoped_relation_source_requirements(snapshot, None)
    assert _m130_pagos_requirement(none).periods == ("1T", "2T", "3T", "4T")


def test_mid_year_start_folds_available_quarters_not_all_or_nothing(tmp_path: Path) -> None:
    """A Q2-start filer folds the quarters it filed; the pre-activity 1T is scoped, not left unresolved (IRPF-1)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        # The filer started activity in Q2, so it has no 1T M130 obligation; it
        # filed 2T/3T/4T only. Zero-valued later filings prove the fold resolves
        # rather than going all-or-nothing because 1T is absent.
        q2_payment = Decimal("640")
        for observation in _modelo_130_pagos_observations(
            {"2T": q2_payment, "3T": Decimal("0"), "4T": Decimal("0")},
        ):
            repository.save(repository.prepare_observation_envelope(observation, source_kind="app_filing"))
        snapshot = _snapshot("100", 2024, "0A")
        prefill = resolve_relations_from_local_store(
            snapshot,
            repository=repository,
            activity_start_date=date(2024, 4, 1),
        )
        m130 = next(v for v in prefill.values if v.relation == "renta-2024-rel-130-pagos-fraccionados")
        assert m130.value == q2_payment


def test_genuinely_missing_in_scope_quarter_still_unresolves(tmp_path: Path) -> None:
    """A missing POST-activity quarter still unresolves — no-silent-under-declaration is preserved (IRPF-1)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        # Q2-start filer filed 2T and 4T but NOT 3T — a genuine in-scope gap, not a
        # pre-activity period. The fold must stay unresolved (blank for the operator
        # to confirm), never silently summed over the hole.
        for observation in _modelo_130_pagos_observations({"2T": Decimal("640"), "4T": Decimal("800")}):
            repository.save(repository.prepare_observation_envelope(observation, source_kind="app_filing"))
        snapshot = _snapshot("100", 2024, "0A")
        prefill = resolve_relations_from_local_store(
            snapshot,
            repository=repository,
            activity_start_date=date(2024, 4, 1),
        )
        m130 = next(v for v in prefill.values if v.relation == "renta-2024-rel-130-pagos-fraccionados")
        assert m130.value is None
