"""Cross-model relation and previous-filing source validation helpers.

Validates cross-model relations declared on each
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` against the source
:class:`~cadrumo.domain.calculations.registry.ModeloDefinition`, checking selector
coverage, source-casilla-id existence, and period alignment.

See Also:
    :mod:`cadrumo.domain.calculations.registry.validate_source_casilla_ids`
        Shared source-casilla membership and non-canonical token diagnostics.
    :mod:`cadrumo.domain.calculations.registry.validate_relation_periods`
        Source revision selection and period/year coverage gates.
    :mod:`cadrumo.domain.calculations.registry.validate_previous_filing_sources`
        Sibling closure check for previous-filing binding selectors.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import RelationDefinition

from ....core.aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS, BindingSourceKind
from ._validate_previous_filing_sources import (
    validate_previous_filing_binding_closure as validate_previous_filing_binding_closure,
)
from ._validate_relation_periods import (
    RelationCoverageFailure,
    select_relation_source_revisions,
    validate_relation_source_coordinate_coverage,
)
from ._validate_relation_periods import (
    period_selectors_overlap as period_selectors_overlap,
)
from ._validate_source_casilla_ids import source_casilla_id_reference_failure
from .bindings_previous_filing import is_direct_previous_filing_binding
from .errors import RegistryValidationError
from .ids import ModeloId, RelationId
from .iva_wallet_relation_targets import (
    IvaWalletRevisionRelationTarget,
    iva_wallet_owned_relation_targets_for_revision,
)
from .period_offset_math import apply_period_offset
from .relations import derive_offset_source_period

#: Allowance key: ``(relation_id, source_modelo, source_period,
#: missing_from_year, missing_through_year)``.
_RelationAllowanceKey = tuple[RelationId, ModeloId, str, int, int]


@dataclass(frozen=True, slots=True)
class RelationSourceYearCoverageAllowance:
    """One documented, currently-necessary relation source-year gap.

    Mirrors :class:`~._validate_previous_filing_year_coverage._PreviousFilingYearCoverageAllowance`
    for the relation mechanism. Every field is required so the entry states
    its own argument rather than being a bare exemption a later reader has
    to reconstruct the reason for. Matched by ``(relation_id, source_modelo,
    source_period, missing_from_year, missing_through_year)`` -- the FULL
    coordinate and range, never by line number, so a registry reflow cannot
    silently detach an entry from the finding it was written for.

    KNOWN LIMITATION, shared with the previous_filing sibling allowlist and
    recorded here rather than only in an exec record so the next author
    inherits it: a staleness check keyed on "encountered but no longer
    needed" cannot detect an entry whose relation was PERMANENTLY DELETED --
    a deleted relation is simply never encountered again, so its allowance
    would sit unflagged forever instead of being reported stale. The
    mitigation is procedural, not mechanical: removing an allowance MUST
    ride the SAME commit that deletes or narrows the relation it was
    written for, never a later cleanup pass.
    """

    relation_id: RelationId
    source_modelo: ModeloId
    source_period: str
    missing_from_year: int
    missing_through_year: int
    reason: str
    discharge: str


_ALLOWANCES: tuple[RelationSourceYearCoverageAllowance, ...] = ()


def validate_relation_closure(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
    *,
    source_year_coverage_allowances: Iterable[RelationSourceYearCoverageAllowance] | None = None,
) -> list[str]:
    """Validate cross-model relation closure for registry modelos.

    Args:
        modelos: Iterable of
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
            entries whose :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
            relations are checked.
        modelos_by_id: Mapping of modelo id to
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
            used to resolve each relation's source modelo.
        source_year_coverage_allowances: Explicit documented source-year gaps
            for this validation sweep. ``None`` uses the production registry
            allowances.

    Every "lacks exact source revision coverage" finding is reconciled
    against :data:`_ALLOWANCES` after the full sweep, exactly as
    :func:`~._validate_previous_filing_year_coverage.validate_previous_filing_source_year_coverage`
    reconciles its own sibling gate: a matched allowance suppresses its
    finding, and an allowance that never matched anything in THIS sweep
    (but whose relation WAS reached) is itself reported as a stale-entry
    failure.
    """
    allowances = tuple(_ALLOWANCES if source_year_coverage_allowances is None else source_year_coverage_allowances)
    structured_failures: list[RelationCoverageFailure] = []
    allowance_relation_keys = {(allowance.relation_id, allowance.source_modelo) for allowance in allowances}
    encountered_relations: set[tuple[RelationId, ModeloId]] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for relation in revision.relations:
                if (relation.id, relation.source_modelo) in allowance_relation_keys:
                    encountered_relations.add((relation.id, relation.source_modelo))
                structured_failures.extend(
                    _validate_single_relation(
                        relation,
                        revision=revision,
                        relation_scope=f"{prefix}: relation {relation.id!r}",
                        modelos_by_id=modelos_by_id,
                    ),
                )
    return _reconcile_relation_coverage_allowances(
        structured_failures,
        encountered_relations=encountered_relations,
        allowances=allowances,
    )


def _reconcile_relation_coverage_allowances(
    structured_failures: list[RelationCoverageFailure],
    *,
    encountered_relations: set[tuple[RelationId, ModeloId]],
    allowances: tuple[RelationSourceYearCoverageAllowance, ...],
) -> list[str]:
    """Suppress every allowlisted finding and report every stale allowance, once per full sweep."""
    allowances_by_key: dict[_RelationAllowanceKey, RelationSourceYearCoverageAllowance] = {
        (
            allowance.relation_id,
            allowance.source_modelo,
            allowance.source_period,
            allowance.missing_from_year,
            allowance.missing_through_year,
        ): allowance
        for allowance in allowances
    }
    consumed: set[_RelationAllowanceKey] = set()
    failures: list[str] = []
    for structured in structured_failures:
        key = structured.allowance_key
        if key is not None and key in allowances_by_key:
            consumed.add(key)
            continue
        failures.append(structured.message)

    for key, allowance in allowances_by_key.items():
        if key in consumed:
            continue
        if (allowance.relation_id, allowance.source_modelo) not in encountered_relations:
            # This sweep's modelo set never reached the allowance's relation at
            # all (a synthetic single-modelo test fixture is the common case),
            # so this call cannot judge whether the gap still holds.
            continue
        failures.append(
            f"stale relation source-year-coverage allowance: relation {allowance.relation_id!r} "
            f"source {allowance.source_modelo!r} period {allowance.source_period!r} from "
            f"{allowance.missing_from_year} through {allowance.missing_through_year} no longer "
            "matches a real gap; remove or update the documented allowance",
        )
    return failures


def _validate_single_relation(
    relation: RelationDefinition,
    *,
    revision: ModeloRevision,
    relation_scope: str,
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[RelationCoverageFailure]:
    failures: list[RelationCoverageFailure] = []
    source_modelo = modelos_by_id.get(relation.source_modelo)
    if source_modelo is None:
        failures.append(
            RelationCoverageFailure(
                message=f"{relation_scope} references unknown source modelo {relation.source_modelo!r}",
            ),
        )
        return failures
    source_periods, period_failures = _relation_source_periods_for_validation(relation)
    failures.extend(RelationCoverageFailure(message=f"{relation_scope} {failure}") for failure in period_failures)
    if not source_periods:
        failures.append(RelationCoverageFailure(message=f"{relation_scope} must declare source periods"))
    if not relation.target_periods:
        failures.append(RelationCoverageFailure(message=f"{relation_scope} must declare target periods"))
    # The relation op is the strict ``RelationAggregation.op`` field; an unknown op
    # is rejected at registry-build when the RelationDefinition is constructed,
    # earlier than this section validator (parity with the binding op gate).
    source_revisions, selector_failures = select_relation_source_revisions(
        source_modelo,
        relation.source_revision_selector,
    )
    failures.extend(RelationCoverageFailure(message=f"{relation_scope} {failure}") for failure in selector_failures)
    if not source_revisions:
        failures.append(
            RelationCoverageFailure(
                message=(
                    f"{relation_scope} selector "
                    f"{relation.source_revision_selector.model_dump(exclude_none=True)!r} "
                    f"matches no source revisions in modelo {source_modelo.id}"
                ),
            ),
        )
        return failures
    source_is_observation_history = _relation_is_prior_year_filing_carry(relation, revision)
    covered_source_revisions, coordinate_failures = validate_relation_source_coordinate_coverage(
        relation_scope,
        relation=relation,
        target_selector=revision.period_selector,
        source_revisions=source_revisions,
        source_periods=source_periods,
        source_is_observation_history=source_is_observation_history,
    )
    failures.extend(coordinate_failures)
    for source_revision, covered_source_periods in covered_source_revisions:
        failures.extend(
            RelationCoverageFailure(message=message)
            for message in _validate_relation_source_revision(
                relation,
                source_revision=source_revision,
                relation_scope=relation_scope,
                source_periods=covered_source_periods,
            )
        )
    return failures


def _relation_is_prior_year_filing_carry(relation: RelationDefinition, revision: ModeloRevision) -> bool:
    """Return whether the relation is a prior-year carry of a historical filing.

    The relation is a
    :class:`~cadrumo.domain.calculations.registry.RelationDefinition` declared on
    the supplied :class:`~cadrumo.domain.calculations.registry.ModeloRevision`.
    Two conditions, both required:

    - The relation's target binding has ``source = "previous_filing"`` — the
      value is the operator's historical filing (an observation), not a
      modeled/derived computation.
    - The effective source coordinate can fall in a strictly-prior ejercicio:
      either the selector carries a negative ``filing_year_delta``, or its
      period offset wraps across the New Year. This distinguishes a genuine
      cross-year prior carry (M200 BIN N-1 -> N, M202 40.2 1P/2P, M303 1T ->
      the preceding 4T) — which may legitimately reference a year before the
      earliest modeled revision — from a same-year periodic→annual roll-up.
    """
    # The carry's target slot is the operator's historical filing (an
    # observation), whether the slot is declared as a direct previous_filing
    # carry or as a relation_prefill fold-in slot. Both source kinds name a
    # prior-filed observation rather than a modeled/derived computation; the
    # year-coverage relaxation applies equally to both.
    targets_observation_slot = any(
        binding.id == relation.target_binding and binding.source in OBSERVATION_BACKED_BINDING_SOURCE_KINDS
        for binding in revision.bindings
    )
    if not targets_observation_slot:
        return False
    selector_delta = relation.source_revision_selector.filing_year_delta or 0
    if selector_delta < 0:
        return True
    if relation.source_period_offset_from_target is None:
        return False
    for target_period in relation.target_periods:
        try:
            offset_delta, _ = apply_period_offset(
                relation.source_period_offset_from_target,
                target_period=target_period,
            )
        except RegistryValidationError:
            continue
        if selector_delta + offset_delta < 0:
            return True
    return False


def _validate_relation_source_revision(
    relation: RelationDefinition,
    *,
    source_revision: ModeloRevision,
    relation_scope: str,
    source_periods: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    source_scope = f"{relation_scope} source revision {source_revision.id!r}"
    failures.extend(
        source_casilla_id_reference_failure(
            source_revision,
            relation.source_casilla_id,
            source_scope=source_scope,
            missing_failure=f"{source_scope} has no source casilla id {relation.source_casilla_id!r}",
        ),
    )
    unknown_source_periods = sorted(set(source_periods).difference(source_revision.period_selector.periods))
    if unknown_source_periods:
        failures.append(f"{source_scope} does not support source periods {unknown_source_periods!r}")
    return failures


def validate_slot_source_hygiene(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    """Validate the relation/previous_filing slot-source hygiene gates.

    Two gates, applied per revision (defence-in-depth against a dual-modelling
    overlap between the two mechanisms):

    (a) A binding with ``source = "previous_filing"`` MUST satisfy the
        direct-selector predicate (``is_direct_previous_filing_binding``). A
        NON-direct previous_filing binding (e.g. ``{source_modelo, source_casilla_id}``
        with no period anchor) is a mis-stamped relation-materialisation slot and
        becomes a registry validation ERROR — it MUST declare
        ``source = "relation_prefill"`` instead.

    (b) No binding may be BOTH a relation's ``target_binding`` AND a
        ``previous_filing`` source. The two mechanisms (relation fold-in vs direct
        cross-period carry) must have disjoint declared ownership. The single
        documented carve-out is the iva-wallet-owned M303 compensación slot
        (D3): it is owned pre-mesh by the iva-wallet compensación decision, not
        by the relation mesh, and is exempt from this gate.

    Args:
        modelos: Iterable of
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition` entries
            to validate.
        modelos_by_id: Mapping of modelo id to
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition` (unused
            here; accepted for signature parity with the sibling closure gates).
    """
    del modelos_by_id  # signature parity with sibling closure validators
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            relation_targets = tuple(revision.relations)
            wallet_relation_targets = iva_wallet_owned_relation_targets_for_revision(
                modelo_id=str(modelo.id),
                revision_id=str(revision.id),
                relations=relation_targets,
            )
            for binding in revision.bindings:
                failures.extend(
                    _validate_slot_binding_source(
                        binding,
                        binding_scope=f"{prefix}: binding {binding.id!r}",
                        relation_targets=relation_targets,
                        wallet_relation_targets=wallet_relation_targets,
                    ),
                )
    return failures


def _validate_slot_binding_source(
    binding: DataBindingDefinition,
    *,
    binding_scope: str,
    relation_targets: tuple[RelationDefinition, ...],
    wallet_relation_targets: frozenset[IvaWalletRevisionRelationTarget],
) -> list[str]:
    failures: list[str] = []
    is_previous_filing = binding.source is BindingSourceKind.PREVIOUS_FILING
    relation_ids = {relation.id for relation in relation_targets if relation.target_binding == binding.id}
    wallet_relation_ids = {
        relation_id for relation_id, target_binding in wallet_relation_targets if target_binding == binding.id
    }
    # Gate (a): a previous_filing binding must carry a DIRECT selector.
    if is_previous_filing and not wallet_relation_ids and not is_direct_previous_filing_binding(binding):
        failures.append(
            f"{binding_scope} declares source 'previous_filing' with a non-direct selector "
            f"(no period/source_periods/offset anchor); a relation-materialisation slot must "
            f"declare source 'relation_prefill' instead",
        )
    # Gate (b): no binding both relation-targeted and previous_filing-sourced.
    non_wallet_relation_ids = sorted(relation_ids.difference(wallet_relation_ids))
    if is_previous_filing and non_wallet_relation_ids:
        failures.append(
            f"{binding_scope} is both a relation target_binding and a 'previous_filing' source "
            f"(non-wallet relation target_binding(s) {non_wallet_relation_ids!r}); "
            f"a relation-targeted slot must declare source 'relation_prefill' (the relation owns "
            f"the cross-period fold-in)",
        )
    return failures


def _relation_source_periods_for_validation(relation: RelationDefinition) -> tuple[tuple[str, ...], list[str]]:
    if relation.source_periods:
        return relation.source_periods, []
    if relation.source_period_offset_from_target is None:
        return (), []
    derived: list[str] = []
    failures: list[str] = []
    for target_period in relation.target_periods:
        try:
            source_period = derive_offset_source_period(relation, target_period=target_period)
        except RegistryValidationError as exc:
            failures.append(str(exc))
            continue
        if source_period is not None:
            derived.append(source_period)
    return tuple(dict.fromkeys(derived)), failures
