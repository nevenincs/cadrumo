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
``source_modelo``. These tests codify that expectation so a future change
cannot silently drop the chain. When a chain is missing, the test fails
with a message that names both the feeder and the summary modelo so the
gap is diagnosable from the failure alone.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

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
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
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
            source_modelo = binding.selector.get("source_modelo")
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
    """A declared chain's dependency_role must be one of the contract-shaped roles."""

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


def _chain_role_offences(*, summary, feeder_id: str, summary_id: str) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    """Return any dependency_role offences for one (feeder -> summary) pair across all revisions."""
    offences: list[str] = []
    for revision in summary.revisions.values():
        for relation in revision.relations:
            if relation.source_modelo != feeder_id:
                continue
            if relation.kind not in _CROSS_MODEL_RELATION_KINDS:
                continue
            if relation.dependency_role not in _ACCEPTED_CHAIN_DEPENDENCY_ROLES:
                offences.append(
                    f"summary modelo {summary_id!r} revision {revision.id!r} "
                    f"relation {relation.id!r} feeds from {feeder_id!r} but uses "
                    f"dependency_role {relation.dependency_role!r}; expected one of "
                    f"{sorted(_ACCEPTED_CHAIN_DEPENDENCY_ROLES)!r}",
                )
    return tuple(offences)


def test_every_declared_relation_resolves_to_a_real_source_casilla() -> None:
    """For every cross_model_output / annual_summary relation, the source modelo's
    revision must declare the named ``source_output`` as a casilla. The registry
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


def _relation_source_offence(relation, *, modelo_id: str, registry) -> str | None:  # type: ignore[no-untyped-def]
    """Return a chain-cohesion offence message for one relation, or ``None`` when it resolves.

    Only ``cross_model_output`` and ``annual_summary`` relations
    participate in this gate; other relation kinds are noise here
    and short-circuit to ``None``. Two failure modes are reported:
    a relation citing a non-existent source modelo, and a relation
    whose declared ``source_output`` is not declared as a casilla
    on any revision of the named source modelo.
    """
    if relation.kind not in _CROSS_MODEL_RELATION_KINDS:
        return None
    source_modelo = registry.get(relation.source_modelo)
    if source_modelo is None:
        return f"modelo {modelo_id} relation {relation.id!r} cites unknown source modelo {relation.source_modelo!r}"
    source_casilla_ids = {
        c.id for source_revision in source_modelo.revisions.values() for c in source_revision.casillas
    }
    if relation.source_output not in source_casilla_ids:
        return (
            f"modelo {modelo_id} relation {relation.id!r} expects "
            f"source casilla {relation.source_output!r} on modelo "
            f"{relation.source_modelo!r}, but no revision of that modelo "
            f"declares it"
        )
    return None
