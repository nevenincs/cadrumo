"""Relation prefill: resolve registry relations from prior filings.

Sits between the engine and the local observation store. The engine
asks "what's the resolved value of every relation this revision
declares?" and this module answers by consulting a :class:`RegistrySnapshot`
to enumerate the declared relations:

1. Reading the revision's relations to determine `(source_modelo,
   source_revision_selector, source_periods, source_output,
   aggregation.op)`.
2. Scanning the local `CalculationObservationRepository` for prior
   filings matching the source quadruple.
3. Folding the source filings' casilla values through the declared
   aggregation op (`sum`, `copy`).
4. Returning a `RelationValues` record stamped with provenance the
   apply adapter writes onto the workbook so the pull adapter can
   detect stale prefills.

When no prior filings exist for a relation, the resolver returns a
`RelationValue` with `value=None` and `provenance="operator_manual"`
so the engine emits a blank cell the operator must fill by hand.

This is the local-tier prefill. The AEAT-live tier (parsing
justificantes from Sede) lives in a separate adapter that produces
the same `RelationValues` shape; callers route between tiers based
on the operator's preferences and the local store's coverage.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Final

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...application.storage.calc_sheets._records import RelationValue, RelationValues
from ...core import Modelo, Period
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryRelationSourceRequirement,
    RegistrySnapshot,
    RegistryValidationError,
    materialize_relation_binding_values,
    relation_source_requirements,
)
from ...domain.iva_compensation import (
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    derive_iva_compensation_year_end_carry_partition,
)
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_log = get_logger(__name__)

#: The shared Modelo 303 source-output the two Modelo 390 year-end carry boxes
#: (97 / 662) fold. The two relations sum/copy this per-period casilla, but the
#: 97-vs-662 split is a FIFO partition of the year's pending credit, not a
#: per-period sum, so the relation path is OVERRIDDEN by the FIFO projection for
#: these two bindings (ADR 2026-06-21-m390-iva-carry-boxes).
_M303_COMPENSACION_GENERADA_SOURCE: Final = "iva.compensacion-generada-periodo"
#: Modelo 303 compensation casilla semantic ids (and their official box-number
#: aliases) read from the filed 303 observation to reconstruct each period's
#: FIFO state. A justificante may key a value by either form.
_303_GENERADA_IDS: Final = ("iva.compensacion-generada-periodo", "compensacion-generada-periodo")
_303_APLICADA_IDS: Final = ("iva.compensacion-aplicada-periodo", "78")
_303_DISPONIBLE_IDS: Final = ("iva.compensacion-disponible-fin-periodo", "compensacion-disponible-fin-periodo")
_303_POSTERIOR_IDS: Final = ("iva.compensacion-pendiente-periodos-posteriores", "87")
_ZERO: Final = Decimal("0")


def _gather_observations_for_snapshot(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
) -> tuple[RegistryModeloObservation, ...]:
    """Collect every observation a relation in `snapshot.revision` could need.

    Uses the registry relation requirement resolver to compute the set of
    `(source_modelo, filing_year, period)` requirements, and pulls matching observations
    from the local store. Returns the union (deduplicated) so the
    runtime resolver can fold them through the declared aggregation
    in one pass.
    """
    needed: dict[tuple[str, int, str], RegistryModeloObservation] = {}
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    for requirement in requirements:
        for period in requirement.periods:
            payload = repository.load_observation(
                requirement.source_modelo,
                Period.from_year_and_code(requirement.filing_year, period),
            )
            if payload is None:
                continue
            # R2 carry gate (shared with binding-prefill and cross-period
            # clean-state): re-confirm the carried observation's revision stamp
            # against the law-determined revision. A divergent stamp means the
            # prior was filed under a revision that is no longer the law-determined
            # revision for its source context; drop it from the fold rather than
            # silently injecting a stale-revision value into the relation.
            obs = payload.observation
            diverges, _advisory = revision_carry_outcome(
                payload.stamped_revision_id,
                source_modelo=obs.modelo,
                source_filing_year=obs.filing_year,
                source_period=obs.period,
            )
            if diverges:
                continue
            key = (obs.modelo, obs.filing_year, obs.period)
            needed.setdefault(key, obs)
    return tuple(needed.values())


def _provenance_note(
    relation_id: str,
    source_modelo: str,
    source_periods: tuple[str, ...],
    source_year: int,
    resolved_at: datetime,
) -> str:
    period_text = "+".join(source_periods) if source_periods else "(any)"
    when = resolved_at.isoformat()
    return (
        f"prefilled from operator's local filing of modelo {source_modelo} "
        f"{period_text} {source_year} (resolved {when})"
    )


def _first_year_modalidad_cuota_no_m202(bucket_id: str, *, filing_year: int) -> bool:
    """Engine-side counterpart of the clean-state first-year-fractional suppression (IS-3).

    Reuses the SINGLE modality definition (:func:`derive_modelo_202_modality`) and
    the SINGLE profile builder (:func:`taxpayer_profile_from_mapping`) — no
    duplicated INCN/threshold logic. Fail-closed: a missing or unprojectable
    profile, a missing activity-start date, or any modality other than
    ``ART_40_2_OPTIONAL`` (i.e. ``ART_40_3_MANDATORY`` / ``INCOMPLETE``) returns
    ``False``, so the Modelo 202 relation stays unresolved and the gate keeps
    blocking — never a silent under-declaration. ADR
    2026-06-19-m202-first-period-attestation.
    """
    from pydantic import ValidationError

    from ...core.wizard_catalogue import WizardCatalogueNotRegisteredError
    from ...domain.calculations.registry import Modelo202Modality, derive_modelo_202_modality
    from ...domain.deadlines import ProfileError, taxpayer_profile_from_mapping
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile._profile_repository import ProfileRepository
    from ..user_profile._projections import record_to_path_values

    try:
        aggregate = ProfileRepository().load(bucket_id)
        profile = taxpayer_profile_from_mapping(
            record_to_path_values(aggregate.record),
            tax_id_default="",
        )
    except (ProfileNotFoundError, ProfileError, WizardCatalogueNotRegisteredError, ValidationError):
        # Fail-closed: an absent / unprojectable profile, or an unregistered wizard
        # catalogue (non-operator contexts), keeps the M202 relation unresolved and
        # the gate blocking — never a silent under-declaration.
        return False
    if derive_modelo_202_modality(profile).modality is not Modelo202Modality.ART_40_2_OPTIONAL:
        return False
    if profile.activity_start_date is None:
        return False
    return profile.activity_start_date.year >= filing_year


def resolve_relations_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    captured_at: datetime | None = None,
    modelo_202_first_year_cuota: bool = False,
) -> RelationValues:
    """Build a :class:`RelationValues` record from the local observation store.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose declared relations are resolved
            from prior observation records in the local store.
        repository: Optional observation repository. Defaults to the active
            profile's calculation observation repository.
        captured_at: Optional timestamp for relation provenance. Defaults to
            the current clock.
        modelo_202_first_year_cuota: When ``True`` (IS-3), an otherwise-unresolved
            Modelo 202 (``source_modelo == "202"``) fold-in relation resolves to
            ``0`` instead of ``None`` — a first-year IS filer under modalidad cuota
            (LIS art. 40.2) has no pago-fraccionado obligation. The caller derives
            this fail-closed (only for a Modelo 200 target); a resolved M202 value
            is never overridden.

    Returns a :class:`RelationValues` whose ``values`` tuple has one
    ``RelationValue`` per relation declared in the snapshot's
    revision, with provenance stamped per entry. Relations the
    local store cannot resolve get ``value=None`` and
    ``provenance="operator_manual"`` so the engine emits a blank cell
    the operator can fill by hand.
    """
    repo = repository if repository is not None else CalculationObservationRepository()
    when = captured_at if captured_at is not None else now()
    observations = _gather_observations_for_snapshot(snapshot, repository=repo)
    requirements_by_relation = {
        relation_id: requirement
        for requirement in relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        for relation_id in requirement.relation_ids
    }

    resolved_map = _resolve_available_relation_values(observations, requirements_by_relation=requirements_by_relation)

    values: list[RelationValue] = []
    for relation in snapshot.revision.relations:
        requirement = requirements_by_relation.get(relation.id)
        target_year = (
            requirement.filing_year
            if requirement is not None
            else snapshot.filing_year
            + int(
                relation.source_revision_selector.get("filing_year_delta", 0)
                if relation.source_revision_selector
                else 0,
            )
        )
        source_periods = requirement.periods if requirement is not None else tuple(relation.source_periods)
        resolved = resolved_map.get(relation.id)
        if resolved is None:
            # IS-3 / ADR 2026-06-19-m202-first-period-attestation: a first-year IS
            # filer under modalidad cuota (LIS art. 40.2) has no Modelo 202
            # pago-fraccionado obligation, so the M202 fold-in relation has no
            # source filing to resolve. Resolve it to 0 (rather than leaving it
            # None, which would crash draft-build on the cuota-diferencial formula
            # that requires the value). Fail-closed: only when the caller derived
            # the first-year-modalidad-cuota flag AND the source is Modelo 202 — a
            # genuinely-resolved M202 value, modalidad base, or an undeterminable
            # modality is never zeroed here. The clean-state gate surfaces the
            # operator-facing advisory; this mirrors that single determination.
            if (
                modelo_202_first_year_cuota
                and requirement is not None
                and requirement.source_modelo == str(Modelo.M202)
            ):
                values.append(
                    RelationValue(
                        relation=relation.id,
                        value=Decimal("0"),
                        provenance="operator_manual",
                        source_filing_year=target_year,
                        source_periods=source_periods,
                        resolved_at=when,
                        note=(
                            "first-year IS filer under modalidad cuota (LIS art. 40.2): no Modelo 202 "
                            "pago-fraccionado obligation; relation resolved to 0 (see verify advisory)"
                        ),
                    ),
                )
                continue
            values.append(RelationValue(relation=relation.id, value=None))
            continue
        values.append(
            RelationValue(
                relation=relation.id,
                value=Decimal(resolved),
                provenance=_LOCAL_FILING_PROVENANCE,
                source_filing_year=target_year,
                source_periods=source_periods,
                resolved_at=when,
                note=_provenance_note(
                    relation.id,
                    relation.source_modelo,
                    source_periods,
                    target_year,
                    when,
                ),
            ),
        )
    return RelationValues(values=tuple(values))


def _resolve_available_relation_values(
    observations: tuple[RegistryModeloObservation, ...],
    *,
    requirements_by_relation: dict[str, RegistryRelationSourceRequirement],
) -> dict[str, Decimal]:
    """Resolve each relation requirement independently from available observations."""
    by_requirement = {requirement: requirement for requirement in requirements_by_relation.values()}
    resolved: dict[str, Decimal] = {}
    for requirement in by_requirement:
        try:
            value = _resolve_requirement_value(requirement, observations)
        except RegistryValidationError as exc:
            _log.warning(
                "relation prefill: relation requirement %s remains operator-manual: %s",
                requirement.relation_ids,
                exc,
            )
            continue
        for relation_id in requirement.relation_ids:
            resolved[relation_id] = value
    return resolved


def _resolve_requirement_value(
    requirement: RegistryRelationSourceRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> Decimal:
    values = tuple(_observed_requirement_values(requirement, observations))
    if requirement.aggregation_op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(
                f"relation requirement {requirement.relation_ids!r} copy aggregation requires one observation",
            )
        return values[0]
    if requirement.aggregation_op == "sum":
        return sum(values, Decimal("0"))
    raise RegistryValidationError(
        f"relation requirement {requirement.relation_ids!r} uses unsupported aggregation op "
        f"{requirement.aggregation_op!r}",
    )


def _observed_requirement_values(
    requirement: RegistryRelationSourceRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for source_period in requirement.periods:
        matches = tuple(
            observation
            for observation in observations
            if observation.modelo == requirement.source_modelo
            and observation.filing_year == requirement.filing_year
            and observation.period == source_period
        )
        if len(matches) != 1:
            raise RegistryValidationError(
                f"expected one observed filing {requirement.source_modelo!r}/"
                f"{requirement.filing_year}/{source_period!r}, found {len(matches)}",
            )
        value = matches[0].casilla_values.get(requirement.source_output)
        if value is None:
            raise RegistryValidationError(
                f"requires observed output {requirement.source_output!r} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}",
            )
        values.append(value)
    return tuple(values)


def _formula_relation_ids(snapshot: RegistrySnapshot) -> frozenset[str]:
    relation_ids: set[str] = set()
    for formula in snapshot.revision.formulas:
        _collect_expression_relation_ids(formula.expression, relation_ids)
    return frozenset(relation_ids)


def _collect_expression_relation_ids(expression: object, relation_ids: set[str]) -> None:
    relation_id = getattr(expression, "relation", None)
    if relation_id is not None:
        relation_ids.add(str(relation_id))
    for arg in getattr(expression, "args", ()):
        _collect_expression_relation_ids(arg, relation_ids)


def _unresolved_relation_diagnostics(
    *,
    unresolved_relation_ids: frozenset[str],
    requirements_by_relation: dict[str, RegistryRelationSourceRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    diagnostics: list[CalculationSourceDiagnostic] = []
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        if requirement is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="relation_prefill",
                    resolver_id=resolver_id,
                    relation_id=relation_id,
                    message=f"relation {relation_id!r} has no resolved source filing",
                ),
            )
            continue
        period_text = ",".join(requirement.periods)
        binding_id = requirement.target_bindings[0] if len(requirement.target_bindings) == 1 else None
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=relation_id,
                message=(
                    f"relation {relation_id!r} requires modelo {requirement.source_modelo} "
                    f"{requirement.filing_year} periods {period_text} output {requirement.source_output}; "
                    "the source filing is missing or incomplete"
                ),
            ),
        )
    return tuple(diagnostics)


def _observed_value(values: Mapping[str, Decimal], *candidate_ids: str) -> Decimal | None:
    for candidate in candidate_ids:
        value = values.get(candidate)
        if value is not None:
            return value
    return None


def _period_state_from_303_observation(observation: RegistryModeloObservation) -> IvaCompensationPeriodState:
    """Reconstruct one filed Modelo 303 period's FIFO compensation state.

    Reads the compensación casillas the 303 calculation already produces
    (generated / applied / disponible / posterior). The disponible
    (``available_end_amount``) is the saldo the period carries forward — when
    absent (an observation that only carries the per-period generada casilla,
    with no carry chain) it falls back to ``posterior + generated``, which for a
    stand-alone period equals its own generated credit.
    """
    values = observation.casilla_values
    generated = _observed_value(values, *_303_GENERADA_IDS) or _ZERO
    applied = _observed_value(values, *_303_APLICADA_IDS) or _ZERO
    posterior = _observed_value(values, *_303_POSTERIOR_IDS)
    available = _observed_value(values, *_303_DISPONIBLE_IDS)
    if available is None:
        available = (posterior or _ZERO) + generated
    period = Period.from_year_and_code(observation.filing_year, observation.period)
    return IvaCompensationPeriodState(
        taxpayer_nif="relation-prefill",
        filing_year=observation.filing_year,
        period=period,
        expediente_id=f"obs-{observation.filing_year}-{observation.period}",
        status="filed",
        presented_at=now(),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=posterior,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=f"303:{observation.filing_year}:{observation.period}:relation-prefill",
    )


def _compensation_carry_binding_ids(snapshot: RegistrySnapshot) -> tuple[str | None, str | None]:
    """Identify the box-97 (ultimo-periodo) and box-662 (generada-no-97) binding ids.

    Resolved structurally from the revision's relations: both fold the shared
    303 ``iva.compensacion-generada-periodo`` source-output; box 97 is the
    ``copy`` of the last period (its ``source_periods`` does not span the early
    quarters) and box 662 is the ``sum`` of the non-last periods. Returns
    ``(box_97_binding_id, box_662_binding_id)``; either is ``None`` when the
    revision declares no such relation (every non-390 revision).
    """
    box_97: str | None = None
    box_662: str | None = None
    for relation in snapshot.revision.relations:
        if relation.source_output != _M303_COMPENSACION_GENERADA_SOURCE:
            continue
        op = str((relation.aggregation or {}).get("op", ""))
        if op == "copy":
            box_97 = str(relation.target_binding)
        elif op == "sum":
            box_662 = str(relation.target_binding)
    return box_97, box_662


def _fifo_compensation_carry_binding_values(
    snapshot: RegistrySnapshot,
    observations: tuple[RegistryModeloObservation, ...],
) -> dict[str, Decimal]:
    """Derive the box-97 / box-662 binding values from the FIFO carry partition.

    The two Modelo 390 year-end carry boxes are ONE FIFO partition of the year's
    pending compensation credit (no double-count, no drop, the AEAT identity
    ``[97] + [662] = year pending``), so they are computed together from the
    single :func:`build_iva_compensation_carry_forward_report` projection over
    the year's filed 303 period states — never as two independent per-period
    303-casilla sums. Returns the slot values for whichever of the two bindings
    the revision declares; empty when the revision has no carry boxes.
    """
    box_97_binding, box_662_binding = _compensation_carry_binding_ids(snapshot)
    if box_97_binding is None and box_662_binding is None:
        return {}
    states = tuple(
        _period_state_from_303_observation(observation)
        for observation in observations
        if observation.modelo == "303" and observation.filing_year == snapshot.filing_year
    )
    if not states:
        return {}
    report = build_iva_compensation_carry_forward_report(states, as_of_year=snapshot.filing_year)
    partition = derive_iva_compensation_year_end_carry_partition(
        report,
        states,
        filing_year=snapshot.filing_year,
    )
    overrides: dict[str, Decimal] = {}
    if box_97_binding is not None:
        overrides[box_97_binding] = partition.last_period_amount
    if box_662_binding is not None:
        overrides[box_662_binding] = partition.generated_not_in_last_amount
    return overrides


class RelationPrefillSourceResolver:
    """Source mesh adapter for local relation prefill values."""

    resolver_id = "relation_prefill"
    owned_sources = ("relation_prefill",)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
        captured_at: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot
        self._captured_at = captured_at

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        try:
            relation_values = resolve_relations_from_local_store(
                snapshot,
                repository=self._repository,
                captured_at=self._captured_at or context.calculated_at,
                # Scope the first-year M202 zero-resolution to the Modelo 200 annual
                # fold-in target only — NEVER to a Modelo 202 snapshot's own
                # intra-year cumulation (2P folds 1P, also source_modelo 202), which
                # must keep its real prior-instalment values.
                modelo_202_first_year_cuota=(
                    str(context.modelo) == str(Modelo.M200)
                    and _first_year_modalidad_cuota_no_m202(
                        str(context.bucket_id),
                        filing_year=context.filing_year,
                    )
                ),
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        requirements_by_relation = {
            relation_id: requirement
            for requirement in relation_source_requirements(
                snapshot.revision,
                filing_year=snapshot.filing_year,
                period=snapshot.period,
            )
            for relation_id in requirement.relation_ids
        }
        resolved = tuple(item for item in relation_values.values if item.value is not None)
        formula_relation_ids = _formula_relation_ids(snapshot)
        unresolved_relation_ids = frozenset(
            item.relation
            for item in relation_values.values
            if item.value is None and item.relation in formula_relation_ids
        )
        # Narrow silent gap (no-silent-under-declaration): a declared relation
        # that resolves to no value, is referenced by no formula, AND whose
        # ``target_binding`` is NOT a declared binding on the revision produces
        # neither a value, nor a materialised binding slot, nor a diagnostic — its
        # absence reaches nothing observable. Surface a non-blocking advisory for
        # exactly that orphaned case. A non-formula relation whose target_binding
        # IS a declared binding still materialises an (absent/zero) slot the engine
        # threads, which is the intended cold-start behaviour for the cross-modelo
        # carries (M200/M202/M100), so it is deliberately NOT flagged here.
        declared_binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)
        relation_target_binding = {relation.id: relation.target_binding for relation in snapshot.revision.relations}
        unresolved_non_formula_relation_ids = frozenset(
            item.relation
            for item in relation_values.values
            if item.value is None
            and item.relation not in formula_relation_ids
            and relation_target_binding.get(item.relation) not in declared_binding_ids
        )
        resolved_relation_values = {item.relation: item.value for item in resolved if item.value is not None}
        # Materialise the resolved relation values into their declared
        # ``target_binding`` slots HERE, inside the resolver, so the merged
        # resolution carries them in ``binding_values`` and the mesh
        # ``_claim_binding`` exclusive-ownership guard adjudicates any collision
        # with another resolver loudly (aggregation-taxonomy ADR ruling 4). This
        # replaces the silent post-mesh merge that previously let every other
        # source override a relation-materialised value without a finding.
        binding_values = materialize_relation_binding_values(
            snapshot.revision,
            resolved_relation_values,
            period=context.period.registry_token,
        )
        # Modelo 390 year-end carry boxes 97 / 662 are ONE FIFO partition of the
        # year's pending compensation credit, not two independent per-period 303
        # sums. The per-period relation values materialised above double-count or
        # drop the carried pending; override the two slots with the values
        # derived TOGETHER from the FIFO carry projection so they partition the
        # year's pending with no double-count and no drop (the AEAT identity).
        # Only the slots the per-period relation already materialised are
        # replaced — the box stays owned by this single resolver, so the mesh
        # exclusive-ownership guard is unaffected.
        if binding_values:
            repo = self._repository if self._repository is not None else CalculationObservationRepository()
            observations = _gather_observations_for_snapshot(snapshot, repository=repo)
            for binding_id, fifo_value in _fifo_compensation_carry_binding_values(snapshot, observations).items():
                if binding_id in binding_values:
                    binding_values[binding_id] = fifo_value
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            relation_values=resolved_relation_values,
            unresolved_relation_ids=tuple(sorted(unresolved_relation_ids)),
            binding_values=binding_values,
            diagnostics=_unresolved_relation_diagnostics(
                unresolved_relation_ids=unresolved_relation_ids,
                requirements_by_relation=requirements_by_relation,
                resolver_id=self.resolver_id,
            )
            + _unresolved_relation_diagnostics(
                unresolved_relation_ids=unresolved_non_formula_relation_ids,
                requirements_by_relation=requirements_by_relation,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="relation_prefill",
                    source_ref=(f"{item.relation}:{item.source_filing_year}:{','.join(item.source_periods)}"),
                )
                for item in resolved
            ),
        )


__all__ = ["RelationPrefillSourceResolver", "resolve_relations_from_local_store"]
