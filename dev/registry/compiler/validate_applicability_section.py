"""Applicability-rule fragment-family validation.

Validates the ``applicability`` schema family declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision`: its legal refs
and those of its exclusions resolve to grounded legal authority, at most one
rule is declared per revision, the rule hydrates into the runtime
:class:`~cadrumo.domain.calculations.registry.applicability.ModeloApplicabilityRule`
without error, and a ledger source declared on the rule's payer fact names
this modelo and a declared-record count binding of this revision.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes every section validator,
        including relation, dependency-classification and filing-schedule
        validation in :mod:`_validate_dependency_sections`. This module's
        :func:`validate_applicability_section` follows the same
        accumulate-never-raise shape (returning ``list[str]``) and is meant
        to be dispatched from there alongside its siblings.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.applicability import hydrate_applicability_rule
from cadrumo.domain.calculations.registry.applicability_payer_facts import PayerFactLedgerSource, PayerFactProjection
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from ._validate_helpers import missing_refs


def validate_applicability_section(
    *,
    prefix: str,
    modelo: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
) -> list[str]:
    """Return applicability-rule reference, cardinality and hydration failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    the ``applicability`` family. Accumulates rather than raises, and
    preserves the underlying enum-coercion error text from
    :func:`hydrate_applicability_rule` in the diagnostic rather than
    flattening it to a generic message, so a bad token names itself and the
    field it broke.

    Args:
        prefix: The revision-scoped diagnostic prefix every failure line
            starts with, matching the sibling section validators.
        modelo: The modelo id the revision belongs to (a plain ``str``,
            matching the dispatcher's ``modelo_id`` contract), needed to
            hydrate the rule -- the fragment carries no self-referential
            ``modelo`` field.
        revision: The revision supplying the ``applicability`` family.
        legal_refs: The bundled legal-reference catalogue, keyed by id.
    """
    failures: list[str] = []
    rules = revision.applicability
    if len(rules) > 1:
        failures.append(
            f"{prefix}: revision declares {len(rules)} applicability rules; at most one is expected per revision",
        )
    for rule in rules:
        owner = f"applicability rule {rule.id}"
        failures.extend(missing_refs(prefix, owner, rule.legal_refs, legal_refs, "legal"))
        for exclusion in rule.exclusions:
            failures.extend(
                missing_refs(prefix, f"{owner} exclusion {exclusion.id}", exclusion.legal_refs, legal_refs, "legal"),
            )
        try:
            hydrated = hydrate_applicability_rule(Modelo(modelo), rule)
        except RegistryValidationError as exc:
            failures.append(f"{prefix}: {owner}: {exc}")
            continue
        fact = hydrated.required_payer_fact
        if isinstance(fact, PayerFactProjection) and fact.ledger_source is not None:
            failures.extend(
                _ledger_source_failures(
                    f"{prefix}: {owner} payer fact {fact.token}",
                    modelo=modelo,
                    revision=revision,
                    source=fact.ledger_source,
                ),
            )
    return failures


def _ledger_source_failures(
    owner: str,
    *,
    modelo: str,
    revision: ModeloRevision,
    source: PayerFactLedgerSource,
) -> list[str]:
    """Check a ledger source against the revision whose rule requires the fact.

    The source answers the fact from the modelo's own filing, so it must name
    this modelo, and its binding must be a distinct count this revision
    declares; an unknown or non-count binding would make the runtime signal
    read nothing, or read an amount as a record count.
    """
    if source.modelo != Modelo(modelo):
        return [f"{owner}: ledger source names modelo {source.modelo.value!r}, not the rule's own modelo {modelo!r}"]
    binding = next((item for item in revision.bindings if item.id == source.record_count_binding), None)
    if binding is None:
        return [f"{owner}: ledger source names unknown binding {source.record_count_binding!r}"]
    if binding_aggregation_op(binding) is not BindingAggregationOp.COUNT_DISTINCT:
        return [f"{owner}: ledger source binding {binding.id!r} is not a distinct count"]
    return []
