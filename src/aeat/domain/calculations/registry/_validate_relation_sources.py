"""Cross-model relation and previous-filing source validation helpers.

Validates cross-model relations declared on each :class:`ModeloRevision`
against the source :class:`ModeloDefinition`, checking selector coverage,
source-output existence, and period alignment.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._errors import RegistryValidationError
from ._relations import _derive_offset_source_period
from ._schema import (
    ModeloDefinition,
    ModeloRevision,
    RelationDefinition,
)
from ._validate_previous_filing_sources import (
    validate_previous_filing_binding_closure as validate_previous_filing_binding_closure,
)
from ._validate_relation_periods import (
    period_selectors_overlap as period_selectors_overlap,
)
from ._validate_relation_periods import (
    relation_filing_year_delta,
    relation_fixed_source_year,
    select_relation_source_revisions,
    validate_source_year_coverage,
)
from ._validate_source_outputs import revision_output_ids as _revision_output_ids


def validate_relation_closure(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for relation in revision.relations:
                failures.extend(
                    _validate_single_relation(
                        relation,
                        revision=revision,
                        relation_scope=f"{prefix}: relation {relation.id!r}",
                        modelos_by_id=modelos_by_id,
                    )
                )
    return failures


def _validate_single_relation(
    relation: RelationDefinition,
    *,
    revision: ModeloRevision,
    relation_scope: str,
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    failures: list[str] = []
    source_modelo = modelos_by_id.get(relation.source_modelo)
    if source_modelo is None:
        failures.append(f"{relation_scope} references unknown source modelo {relation.source_modelo!r}")
        return failures
    source_periods, period_failures = _relation_source_periods_for_validation(relation)
    failures.extend(f"{relation_scope} {failure}" for failure in period_failures)
    if not source_periods:
        failures.append(f"{relation_scope} must declare source periods")
    if not relation.target_periods:
        failures.append(f"{relation_scope} must declare target periods")
    aggregation = relation.aggregation or {"op": "copy"}
    op = aggregation.get("op")
    if op not in {"copy", "sum"}:
        failures.append(f"{relation_scope} uses unsupported aggregation op {op!r}")
    source_revisions, selector_failures = select_relation_source_revisions(
        source_modelo,
        relation.source_revision_selector,
    )
    failures.extend(f"{relation_scope} {failure}" for failure in selector_failures)
    if not source_revisions:
        failures.append(
            f"{relation_scope} selector {dict(relation.source_revision_selector)!r} "
            f"matches no source revisions in modelo {source_modelo.id}"
        )
        return failures
    for source_revision in source_revisions:
        failures.extend(
            _validate_relation_source_revision(
                relation,
                source_revision=source_revision,
                relation_scope=relation_scope,
            )
        )
    # A relation that carries a PRIOR-YEAR copy of the operator's historical
    # filing (a previous_filing binding fed by a strictly-negative
    # filing_year_delta) references an observation that exists for any filed
    # year, independent of whether this app models that year's engine. Such
    # relations relax the year-coverage check (see
    # ``validate_source_year_coverage``). Same-year periodic→annual roll-ups
    # (annual_summary, filing_year_delta 0 / fixed year_from) stay strict: they
    # aggregate the same ejercicio's filings, which the source modelo must
    # model. The strictly-negative-delta gate is what separates a genuine
    # cross-year prior carry from a same-year aggregation.
    source_is_observation_history = _relation_is_prior_year_filing_carry(relation, revision)
    failures.extend(
        validate_source_year_coverage(
            relation_scope,
            target_selector=revision.period_selector,
            source_revisions=source_revisions,
            source_periods=source_periods,
            filing_year_delta=relation_filing_year_delta(relation.source_revision_selector),
            fixed_source_year=relation_fixed_source_year(relation.source_revision_selector),
            source_is_observation_history=source_is_observation_history,
        )
    )
    return failures


def _relation_is_prior_year_filing_carry(
    relation: RelationDefinition, revision: ModeloRevision
) -> bool:
    """Return whether the relation is a prior-year carry of a historical filing.

    Two conditions, both required:

    - The relation's target binding has ``source = "previous_filing"`` — the
      value is the operator's historical filing (an observation), not a
      modeled/derived computation.
    - The relation references a STRICTLY-PRIOR ejercicio, i.e. its
      ``source_revision_selector`` carries a strictly-negative
      ``filing_year_delta``. This is what distinguishes a genuine cross-year
      prior carry (M200 BIN N-1 -> N, M202 40.2 1P/2P) — which may legitimately
      reference a year before the earliest modeled revision — from a same-year
      periodic→annual roll-up (the 180/190/193 ←115/111/123 annual_summary
      relations use a fixed ``year_from`` with delta 0, aggregate the same
      ejercicio's filings, and MUST stay under the strict modeled-coverage
      check so a widened target revision still demands matching source years).
    """
    targets_previous_filing = any(
        binding.id == relation.target_binding and binding.source == "previous_filing"
        for binding in revision.bindings
    )
    if not targets_previous_filing:
        return False
    delta = relation.source_revision_selector.get("filing_year_delta")
    return isinstance(delta, int) and delta < 0


def _validate_relation_source_revision(
    relation: RelationDefinition,
    *,
    source_revision: ModeloRevision,
    relation_scope: str,
) -> list[str]:
    failures: list[str] = []
    source_scope = f"{relation_scope} source revision {source_revision.id!r}"
    source_values = _revision_output_ids(source_revision)
    if relation.source_output not in source_values:
        failures.append(f"{source_scope} has no source output {relation.source_output!r}")
    source_periods, period_failures = _relation_source_periods_for_validation(relation)
    failures.extend(f"{source_scope} {failure}" for failure in period_failures)
    unknown_source_periods = sorted(set(source_periods).difference(source_revision.period_selector.periods))
    if unknown_source_periods:
        failures.append(f"{source_scope} does not support source periods {unknown_source_periods!r}")
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
            source_period = _derive_offset_source_period(relation, target_period=target_period)
        except RegistryValidationError as exc:
            failures.append(str(exc))
            continue
        if source_period is not None:
            derived.append(source_period)
    return tuple(dict.fromkeys(derived)), failures
