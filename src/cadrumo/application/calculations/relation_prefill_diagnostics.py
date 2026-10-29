"""Diagnostics for unresolved cross-period relation values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from ...core.period import Period
from ...domain.calculations.registry.handoffs import relation_consumption_channels, relation_consumption_index
from ...domain.calculations.registry.ids import ModeloId, RelationId, RevisionId
from ...domain.calculations.registry.iva_wallet_carry_targets import is_iva_wallet_owned_carry_target
from ...domain.calculations.registry.relations import RegistryFoldRequirement, relation_prefill_bindings_for_period
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..storage.calc_sheets.records import RelationValues


def _requirement_periods_are_datable(requirement: RegistryFoldRequirement) -> bool:
    """Whether every source period of ``requirement`` can be positioned against a date.

    The activity-start scoping that keeps the absent-bound-carry advisory honest
    can only suppress a period it can place on a calendar: a non-calendar
    instalment clave (1P/2P/3P) has no span and is documented as never suppressed.
    For such a period the scoping cannot establish that the taxpayer HAD the
    obligation, so the advisory must not claim they did — a sociedad whose activity
    began after the first instalment window would otherwise be told a filing it
    never owed is missing.

    Silence is the fail-closed direction here, and deliberately so: it preserves
    the prior behaviour for exactly the periods where the obligation is
    undeterminable, rather than guessing.
    """
    for token in requirement.periods:
        try:
            period = Period.from_year_and_code(requirement.filing_year, token)
        except Exception:
            # A token that will not construct a Period is by definition undatable.
            return False
        if not period.has_date_span():
            return False
    return True


def absent_bound_carry_diagnostics(
    *,
    unresolved_relation_ids: frozenset[RelationId],
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on a bound carry whose source filing is absent, so the slot threads a zero.

    Distinct from the orphaned-relation advisory in what it tells the operator.
    An orphan reaches nothing; this one reaches a casilla, as a zero, and every
    carry on this path reduces the amount owed — a prior instalment already paid,
    a loss carried forward, an opening stock. So the zero does not look wrong. It
    looks like a taxpayer who had no prior filing, and it declares more tax than
    is owed.

    The advisory is non-blocking, and it does not fire for a filer who genuinely
    had no obligation: those source periods are scoped out upstream against the
    declared activity start before any requirement reaches here.

    The message states the FACT and the remedy names only what the operator can
    always do. It deliberately does not tell them to capture or file the source
    period, because whether that is possible depends on the source modelo: the
    declarations register does not serve every modelo, and Sociedades in
    particular. An instruction an automation-operator will follow and cannot satisfy is
    worse than no instruction, so the capture route is omitted here rather than
    asserted, and stating what AEAT does or does not offer is left to whoever
    measures it rather than inferred from this registry's own silence.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        binding_id = relation_id
        if requirement is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="relation_prefill",
                    resolver_id=resolver_id,
                    binding_id=binding_id,
                    relation_id=relation_id,
                    message=(
                        f"carry {relation_id!r} has no resolved source filing, so its bound casilla "
                        "declares zero; a carry that reduces the amount owed is missing, which "
                        "over-declares"
                    ),
                    remedy=(
                        "Supply the value for this casilla directly, through a binding override on "
                        "calculate, if you hold the prior return."
                    ),
                ),
            )
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=relation_id,
                message=(
                    f"carry {relation_id!r} found no modelo {requirement.source_modelo} "
                    f"{requirement.filing_year} {','.join(requirement.periods)} filing in the local "
                    f"store, so its bound casilla declares zero rather than the carried "
                    f"{requirement.source_casilla_ids[0]}. That reduces no liability and therefore "
                    "over-declares."
                ),
                remedy=(
                    "Supply the value for this casilla directly, through a binding override on "
                    "calculate, if you hold the prior return."
                ),
            ),
        )
    return tuple(diagnostics)


class _UnresolvedRelationIds(NamedTuple):
    """The three silences an unresolved relation can be, kept apart on purpose.

    They are separate sets because their CONSEQUENCES differ, not because the
    predicates do. Collapsing them would make one advisory speak for three
    outcomes, only one of which over-declares.
    """

    formula_fed: frozenset[RelationId]
    """Unresolved and read by a formula: the value feeds a computed casilla."""

    orphaned: frozenset[RelationId]
    """Unresolved and reaches no declared consumption channel.

    Produces no value, no slot and nothing observable, so its absence reaches
    nothing at all.
    """

    bound: frozenset[RelationId]
    """Unresolved and consumed through a primary or alternate casilla binding.

    The subtle one, and the reason this set exists. It was once left silent as
    "intended cold-start behaviour", but cold start is not what that silence
    protected: a source period the taxpayer had no obligation for is already
    removed upstream against the declared activity start, so a genuine
    first-ejercicio filer's prior-year carries never reach here. What the
    silence additionally covered was the filer who DID have the obligation and
    whose filing is simply not in the store -- and there the engine threads the
    absent slot as a zero, which reduces no liability and therefore
    over-declares (no-silent-under-declaration).
    """


class _RelationConsumption(NamedTuple):
    """Canonical registry channels projected for one unresolved-value pass."""

    formula_fed: frozenset[RelationId]
    bound: frozenset[RelationId]
    consumed: frozenset[RelationId]


def unresolved_relation_ids(
    snapshot: RegistrySnapshot,
    *,
    relation_values: RelationValues,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    modelo_id: str,
) -> _UnresolvedRelationIds:
    """Partition the unresolved relations by what their silence actually reaches.

    Three narrowings keep the ``bound`` advisory honest, and each is
    load-bearing rather than incidental:

    * membership in ``requirements_by_relation``, which is built from the SCOPED
      requirement set -- testing ``value is None`` alone would fire on every
      genuine first-ejercicio filer, because a scoped-out relation still appears
      here unresolved;
    * ``taxpayer_files_source``, because a carry the taxpayer does not FILE (a
      retención suffered, where the payer files the source modelo) cannot be
      remedied by capturing or filing anything, so advising on it would put an
      unactionable line in front of every filer who simply had no such
      withholding. That axis is registry-declared per dependency, never
      inferred;
    * ownership, because the Modelo 303 compensación slot belongs to the IVA
      wallet decision under the one-mechanism-per-calculation-type taxonomy, so
      advising on it here would be a second mechanism speaking about a value it
      does not own. The check is the registry's own predicate rather than a
      binding-id comparison invented here.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    consumption = _relation_consumption(snapshot)
    unresolved_ids = frozenset(item.relation for item in relation_values.values if item.value is None)
    taxpayer_filed_source_modelos = frozenset(
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if classification.taxpayer_files_source
    )
    return _UnresolvedRelationIds(
        formula_fed=unresolved_ids & consumption.formula_fed,
        orphaned=unresolved_ids - consumption.consumed,
        bound=_unresolved_bound_relation_ids(
            unresolved_ids,
            consumption=consumption,
            requirements_by_relation=requirements_by_relation,
            taxpayer_filed_source_modelos=taxpayer_filed_source_modelos,
            modelo_id=modelo_id,
            revision_id=snapshot.revision.id,
        ),
    )


def _relation_consumption(snapshot: RegistrySnapshot) -> _RelationConsumption:
    """Derive only the registry's declared fold consumption channels."""
    consumption_index = relation_consumption_index(snapshot.revision)
    channels_by_relation = {
        binding.id: relation_consumption_channels(binding.id, consumption_index)
        for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    return _RelationConsumption(
        formula_fed=_relation_ids_for_channels(
            channels_by_relation,
            "formula_binding",
        ),
        bound=_relation_ids_for_channels(
            channels_by_relation,
            "primary_binding",
            "alternate_binding",
        ),
        consumed=_consumed_relation_ids(channels_by_relation),
    )


def _relation_ids_for_channels(
    channels_by_relation: Mapping[RelationId, tuple[str, ...]],
    *required_channels: str,
) -> frozenset[RelationId]:
    required = frozenset(required_channels)
    return frozenset(
        relation_id for relation_id, channels in channels_by_relation.items() if required.intersection(channels)
    )


def _consumed_relation_ids(
    channels_by_relation: Mapping[RelationId, tuple[str, ...]],
) -> frozenset[RelationId]:
    return frozenset(relation_id for relation_id, channels in channels_by_relation.items() if channels)


def _unresolved_bound_relation_ids(
    unresolved_ids: frozenset[RelationId],
    *,
    consumption: _RelationConsumption,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    taxpayer_filed_source_modelos: frozenset[ModeloId],
    modelo_id: str,
    revision_id: RevisionId,
) -> frozenset[RelationId]:
    """Keep only actionable, non-wallet unresolved bound carries."""
    return frozenset(
        relation_id
        for relation_id in unresolved_ids
        if _is_actionable_unresolved_bound_relation(
            relation_id,
            consumption=consumption,
            requirements_by_relation=requirements_by_relation,
            taxpayer_filed_source_modelos=taxpayer_filed_source_modelos,
            modelo_id=modelo_id,
            revision_id=revision_id,
        )
    )


def _is_actionable_unresolved_bound_relation(
    relation_id: RelationId,
    *,
    consumption: _RelationConsumption,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    taxpayer_filed_source_modelos: frozenset[ModeloId],
    modelo_id: str,
    revision_id: RevisionId,
) -> bool:
    if relation_id in consumption.formula_fed or relation_id not in requirements_by_relation:
        return False
    requirement = requirements_by_relation[relation_id]
    if requirement.source_modelo not in taxpayer_filed_source_modelos:
        return False
    if not _requirement_periods_are_datable(requirement) or relation_id not in consumption.bound:
        return False
    return not is_iva_wallet_owned_carry_target(
        modelo_id=modelo_id,
        revision_id=revision_id,
        binding_id=relation_id,
    )


def unresolved_relation_diagnostics(
    *,
    unresolved_relation_ids: frozenset[RelationId],
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise once per ABSENT SOURCE FILING, not once per relation reading it.

    Measured on Modelo 190 for 2025 with an empty store and a long-running
    filer: ten annual-summary relations each read a different fact off the
    SAME absent Modelo 111 return, so the un-grouped form produced ten lines
    naming one root cause. Grouped by ``(source_modelo, filing_year,
    periods)`` — deliberately NOT including ``source_casilla_ids``, since the
    casilla read is exactly the axis that varies across the grouped
    relations and enumerating it is the "affected facts" the grouped
    advisory names. A relation with no requirement at all (an orphan the
    scoped requirement set never produced) has no source coordinate to group
    by and stays one diagnostic per relation — there is no shared cause to
    fold it into.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    orphaned_ids: list[RelationId] = []
    grouped: dict[tuple[str, int, tuple[str, ...]], list[tuple[RelationId, RegistryFoldRequirement]]] = {}
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        if requirement is None:
            orphaned_ids.append(relation_id)
            continue
        key = (requirement.source_modelo, requirement.filing_year, requirement.periods)
        grouped.setdefault(key, []).append((relation_id, requirement))

    for relation_id in orphaned_ids:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                relation_id=relation_id,
                message=f"relation {relation_id!r} has no resolved source filing",
            ),
        )

    for (source_modelo, filing_year, periods), members in sorted(grouped.items()):
        member_relation_ids = tuple(sorted(relation_id for relation_id, _ in members))
        binding_ids = {
            requirement.target_bindings[0] for _, requirement in members if len(requirement.target_bindings) == 1
        }
        binding_id = next(iter(binding_ids)) if len(binding_ids) == 1 else None
        period_text = ",".join(periods)
        # Facts (the casilla ids the group reads) come first, so a long group's
        # elision cuts into the trailing relation-id listing rather than the
        # facts themselves; `relation_ids` above is the full, un-elided,
        # machine-readable membership regardless of what the prose keeps.
        facts_text = ", ".join(sorted({requirement.source_casilla_ids[0] for _, requirement in members}))
        relation_ids_text = ", ".join(member_relation_ids)
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=member_relation_ids[0],
                relation_ids=member_relation_ids,
                message=(
                    f"modelo {source_modelo} {filing_year} periods {period_text} is missing or "
                    f"incomplete in the local store; {len(members)} relation(s) read it, needing: "
                    f"{facts_text}. Affected relations: {relation_ids_text}"
                ),
            ),
        )
    return tuple(diagnostics)
