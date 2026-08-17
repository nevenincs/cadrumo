"""The Modelo 303 iva-wallet relation carve-out, declared once.

One relation coordinate in the whole registry is owned by the iva-wallet
compensación decision rather than by the relation mesh, so it is exempt from the
slot-source hygiene gate that otherwise forbids a binding being both a relation
target and a previous_filing source. That exemption is a safety-relevant hole in
a validator, so it lives in its own module where the exact declarations are the
whole file rather than seventy lines inside a three-hundred-line validator.

Extracted from ``_validate_relation_sources`` per
``aeat-architecture-boundaries``: a family's declarations live in their own
module and the aggregator re-exports rather than accreting them. The validator
imports back only the two names it actually uses.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from ....core import Modelo
from ._ids import BindingId, ModeloId, RelationId, RevisionId
from ._schema import RelationDefinition

#: The single M303 compensación-pendiente binding id, owned by the iva-wallet
#: compensación decision. This is the one
#: canonical declaration of the identifier: the registry relation-source validator
#: (below), the calculate orchestrator's mesh exclusion, and the previous-filing
#: exclusion all consume it rather than re-spelling the literal. It rides down here
#: in the registry domain so both the domain validator and the application
#: orchestrator (application -> domain) read one source of truth.
MODELO_303_IVA_COMPENSATION_BINDING_ID: Final[str] = "modelo-303-compensacion-pendiente-anteriores"

type IvaWalletRelationTarget = tuple[ModeloId, RevisionId, RelationId, BindingId]
type IvaWalletRevisionRelationTarget = tuple[RelationId, BindingId]

# The wallet exception is a relation coordinate, not a globally-owned binding
# name. Keep the exact declarations here so a future reuse of the binding id in
# another modelo, revision, or relation cannot inherit the carve-out.
IVA_WALLET_OWNED_RELATION_TARGETS: frozenset[IvaWalletRelationTarget] = frozenset(
    {
        (
            Modelo.M303.value,
            "2009-2022",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
        (
            Modelo.M303.value,
            "2023",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
        (
            Modelo.M303.value,
            "2024-hasta-08-y-2t",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
        (
            Modelo.M303.value,
            "2024-desde-09-y-3t",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
        (
            Modelo.M303.value,
            "2025",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
        (
            Modelo.M303.value,
            "2026-y-siguientes",
            "modelo-303-rel-self-compensacion-anteriores",
            MODELO_303_IVA_COMPENSATION_BINDING_ID,
        ),
    },
)


def is_iva_wallet_owned_relation_target(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    relation_id: str,
    target_binding: str,
) -> bool:
    """Return whether one validated relation coordinate belongs to the wallet."""
    return (modelo_id, revision_id, relation_id, target_binding) in IVA_WALLET_OWNED_RELATION_TARGETS


def iva_wallet_owned_relation_targets_for_revision(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    relations: Iterable[RelationDefinition],
) -> frozenset[IvaWalletRevisionRelationTarget]:
    """Return exact wallet-owned relation targets declared by one revision."""
    return frozenset(
        (relation.id, relation.target_binding)
        for relation in relations
        if is_iva_wallet_owned_relation_target(
            modelo_id=modelo_id,
            revision_id=revision_id,
            relation_id=str(relation.id),
            target_binding=str(relation.target_binding),
        )
    )


def iva_wallet_owned_binding_ids_for_revision(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    relations: Iterable[RelationDefinition],
) -> frozenset[BindingId]:
    """Return wallet-owned binding ids only within one exact revision coordinate."""
    return frozenset(
        target_binding
        for _relation_id, target_binding in iva_wallet_owned_relation_targets_for_revision(
            modelo_id=modelo_id,
            revision_id=revision_id,
            relations=relations,
        )
    )
