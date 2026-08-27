"""Tests that the canonical feeder→summary modelo chains are wired bidirectionally.

The AEAT filing cycle has well-defined chains where a periodic modelo
(filed monthly or quarterly) feeds an annual-receiver modelo:

- 111 (worker/professional withholdings) → 190 (annual summary)
- 115 (rental withholdings)               → 180 (annual summary)
- 123 (movable-capital withholdings)      → 193 (annual summary)
- 303 (IVA periodic settlement)           → 390 (annual summary)
- 130 + 131 (IRPF pagos fraccionados)     → 100 (renta annual)
- 202 (IS pago fraccionado)               → 200 (IS annual)

Each chain is declared on the receiver side either as a ``cross_model_output``
relation or as a ``previous_filing`` binding pointing at the feeder's
``source_modelo``. These tests enforce that expectation so a future change
cannot silently drop the chain. When a chain is missing, the test fails
with a message that names both the feeder and the summary modelo so the
gap is diagnosable from the failure alone.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from .._validate_relation_periods import select_relation_source_revisions
from ..binding_selector_utils import selector_as_dict
from ..schema import ModeloDefinition
from ..schema_surfaces import RelationDefinition
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Canonical (feeder modelo id, summary modelo id) chains that the AEAT
# filing cycle requires. Each pair represents a periodic feeder whose
# outputs roll up into an annual receiver. The receiver declares the
# relation; this list is the contract that the relation is present.
_CANONICAL_FEEDER_SUMMARY_CHAINS: tuple[tuple[str, str], ...] = (
    ("111", "190"),
    ("115", "180"),
    ("123", "193"),
    ("303", "390"),
    ("130", "100"),
    ("131", "100"),
    ("202", "200"),
)

_RELATION_BACKED_FEEDER_SUMMARY_CHAINS = tuple(
    pair for pair in _CANONICAL_FEEDER_SUMMARY_CHAINS if pair != ("303", "390")
)


def _registry() -> dict[str, ModeloDefinition]:
    modelos, _ = _committed_registry_tree()
    return {modelo.id: modelo for modelo in modelos}


def _summary_relation_source_modelos(modelo: ModeloDefinition) -> set[str]:
    """Return the set of source-modelo ids declared by the modelo's relations.

    Aggregates across every revision; returns only the source modelo ids
    of relations of kind ``cross_model_output`` or ``annual_summary``.
    """

    seen: set[str] = set()
    for revision in modelo.revisions.values():
        for relation in revision.relations:
            if relation.kind in {"cross_model_output", "annual_summary"}:
                seen.add(relation.source_modelo)
    return seen


def _summary_previous_filing_source_modelos(modelo: ModeloDefinition) -> set[str]:
    """Return source-modelo ids declared by previous-filing bindings."""

    seen: set[str] = set()
    for revision in modelo.revisions.values():
        for binding in revision.bindings:
            if binding.source != "previous_filing":
                continue
            source_modelo = selector_as_dict(binding).get("source_modelo")
            if isinstance(source_modelo, str):
                seen.add(source_modelo)
    return seen


def _summary_source_modelos(modelo: ModeloDefinition) -> set[str]:
    return _summary_relation_source_modelos(modelo) | _summary_previous_filing_source_modelos(modelo)


@pytest.mark.parametrize(("feeder_id", "summary_id"), _CANONICAL_FEEDER_SUMMARY_CHAINS)
def test_canonical_feeder_summary_chain_is_declared(feeder_id: str, summary_id: str) -> None:
    registry = _registry()
    feeder = registry.get(feeder_id)
    summary = registry.get(summary_id)
    assert feeder is not None, f"feeder modelo {feeder_id!r} is not in the registry"
    assert summary is not None, f"summary modelo {summary_id!r} is not in the registry"

    sources = _summary_source_modelos(summary)
    assert feeder_id in sources, (
        f"summary modelo {summary_id!r} declares no cross_model_output relation or previous_filing binding "
        f"to feeder modelo {feeder_id!r}; the canonical chain is broken. "
        f"Either add a receiver-side chain declaration on {summary_id} that names {feeder_id} as source_modelo, "
        f"or remove the chain from the canonical list if the AEAT cycle no longer requires it."
    )


def test_every_canonical_feeder_appears_in_at_least_one_summary() -> None:
    """Every canonical feeder must feed at least one summary modelo."""

    registry = _registry()
    feeders_in_canonical_list = {feeder for feeder, _ in _CANONICAL_FEEDER_SUMMARY_CHAINS}
    feeders_seen_as_sources: set[str] = set()
    for modelo in registry.values():
        feeders_seen_as_sources.update(_summary_source_modelos(modelo))

    orphan_feeders = sorted(feeders_in_canonical_list.difference(feeders_seen_as_sources))
    assert not orphan_feeders, (
        f"feeder modelos {orphan_feeders!r} are canonical but no summary modelo "
        f"declares them as a source_modelo. Declare the missing relation."
    )


def test_declared_canonical_chains_use_pago_or_summary_dependency_role() -> None:
    """Every declared chain carries at least one contract-shaped dependency_role.

    A canonical feeder -> summary chain must be declared with a structural role
    (annual-summary roll-up, instalment-to-final-settlement, or factual evidence)
    on at least one of the feeder's relations, so the chain is modelled as a real
    AEAT reconciliation rather than an incidental data feed. A feeder may ALSO
    carry a ``direct_calculation`` value feed alongside its structural relation
    (e.g. Modelo 131 supplies both the pago fraccionado, an instalment, and the
    módulos rendimiento, a direct calculation input to M100 income); such a
    value feed is separately guarded by the value-consumption and per-role
    cross-dependency contracts and is not an offence here.
    """

    registry = _registry()
    failures: list[str] = []
    for feeder_id, summary_id in _RELATION_BACKED_FEEDER_SUMMARY_CHAINS:
        summary = registry.get(summary_id)
        if summary is None:
            continue
        failures.extend(_chain_role_offences(summary=summary, feeder_id=feeder_id, summary_id=summary_id))
    assert not failures, "\n".join(failures)


_ACCEPTED_CHAIN_DEPENDENCY_ROLES = frozenset(
    {
        # Annual-summary chains (e.g., 111->190, 115->180): periodic returns
        # roll up into an informative annual summary.
        "periodic_to_annual_summary",
        # IRPF/IS pago-fraccionado chains (e.g., 130->100, 202->200): the
        # quarterly prepayment reconciles against the final annual settlement.
        "instalment_to_final_settlement",
        # Generic cross-modelo evidence (e.g., 100 picking up 111 retentions):
        # the source filing is consumed as factual data, not as a structural roll-up.
        "factual_evidence",
    },
)


def _chain_role_offences(
    *,
    summary: ModeloDefinition,
    feeder_id: str,
    summary_id: str,
) -> tuple[str, ...]:
    """Return an offence per revision where a declared (feeder -> summary) chain
    carries no relation with a contract-shaped dependency_role.

    The chain must be structurally declared by at least one accepted-role
    relation; additional ``direct_calculation`` value feeds from the same feeder
    are legitimate and do not constitute an offence.
    """
    offences: list[str] = []
    for revision in summary.revisions.values():
        chain_relations = [
            relation
            for relation in revision.relations
            if relation.source_modelo == feeder_id and relation.kind in _CROSS_MODEL_RELATION_KINDS
        ]
        if not chain_relations:
            continue
        if not any(relation.dependency_role in _ACCEPTED_CHAIN_DEPENDENCY_ROLES for relation in chain_relations):
            roles_present = sorted({relation.dependency_role for relation in chain_relations})
            offences.append(
                f"summary modelo {summary_id!r} revision {revision.id!r} declares "
                f"relations from feeder {feeder_id!r} but none carry a contract-shaped "
                f"dependency_role; roles present: {roles_present!r}; expected at least one of "
                f"{sorted(_ACCEPTED_CHAIN_DEPENDENCY_ROLES)!r}",
            )
    return tuple(offences)


def test_every_declared_relation_resolves_to_a_real_source_casilla() -> None:
    """For every cross_model_output / annual_summary relation, the source modelo's
    revision must declare the named ``source_casilla_id`` as a casilla. The registry
    validator already asserts this; this test makes the cohesion contract visible
    at the chain level so a regression is named in chain-cohesion terms.
    """

    registry = _registry()
    failures: list[str] = []
    for modelo in registry.values():
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                offence = _relation_source_offence(relation, modelo_id=modelo.id, registry=registry)
                if offence is not None:
                    failures.append(offence)
    assert not failures, "\n".join(failures)


_CROSS_MODEL_RELATION_KINDS = frozenset({"cross_model_output", "annual_summary"})


def _relation_source_offence(
    relation: RelationDefinition,
    *,
    modelo_id: str,
    registry: Mapping[str, ModeloDefinition],
) -> str | None:
    """Return a chain-cohesion offence message for one relation, or ``None`` when it resolves.

    Only ``cross_model_output`` and ``annual_summary`` relations
    participate in this gate; other relation kinds are noise here
    and short-circuit to ``None``. Two failure modes are reported:
    a relation citing a non-existent source modelo, a selector that matches no
    source revision, and a relation whose declared ``source_casilla_id`` is not
    declared as a casilla on every selected source revision.
    """
    if relation.kind not in _CROSS_MODEL_RELATION_KINDS:
        return None
    source_modelo = registry.get(relation.source_modelo)
    if source_modelo is None:
        return f"modelo {modelo_id} relation {relation.id!r} cites unknown source modelo {relation.source_modelo!r}"
    source_revisions, selector_failures = select_relation_source_revisions(
        source_modelo,
        relation.source_revision_selector,
    )
    if selector_failures:
        return f"modelo {modelo_id} relation {relation.id!r} source selector errors: {selector_failures!r}"
    if not source_revisions:
        selector = relation.source_revision_selector.model_dump(exclude_none=True)
        return (
            f"modelo {modelo_id} relation {relation.id!r} selector "
            f"{selector!r} matches no source revisions on modelo {relation.source_modelo!r}"
        )
    for source_revision in source_revisions:
        source_casilla_ids = {casilla.id for casilla in source_revision.casillas}
        if relation.source_casilla_id in source_casilla_ids:
            continue
        return (
            f"modelo {modelo_id} relation {relation.id!r} expects "
            f"source casilla {relation.source_casilla_id!r} on modelo "
            f"{relation.source_modelo!r} revision {source_revision.id!r}, but that revision "
            f"does not declare it"
        )
    return None
