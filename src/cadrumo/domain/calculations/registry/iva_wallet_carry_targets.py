"""The Modelo 303 iva-wallet carry carve-out, declared once.

One carry coordinate in the whole registry is owned by the iva-wallet
compensación decision rather than by the cross-filing fold mesh, so it is
exempt from the slot-source hygiene gate that otherwise governs how a
compensación-pendiente slot is fed.

The exemption is a REVISION-EXACT binding coordinate, never a globally-owned
binding name: the same identifier appearing in another modelo or another
revision does not inherit the carve-out.
"""

from __future__ import annotations

from typing import Final

from ....core.modelo import Modelo
from .ids import BindingId, ModeloId, RevisionId

__all__ = [
    "IVA_WALLET_OWNED_CARRY_TARGETS",
    "MODELO_303_IVA_COMPENSATION_BINDING_ID",
    "IvaWalletCarryTarget",
    "is_iva_wallet_owned_carry_target",
    "iva_wallet_owned_binding_ids_for_revision",
]

#: The single M303 compensación-pendiente binding id, owned by the iva-wallet
#: compensación decision. This is the one canonical declaration of the
#: identifier: the calculate orchestrator's mesh exclusion and the
#: previous-filing exclusion both consume it rather than re-spelling the
#: literal. It rides down here in the registry domain so both the domain and
#: the application orchestrator (application -> domain) read one source of
#: truth.
MODELO_303_IVA_COMPENSATION_BINDING_ID: Final[str] = "modelo-303-compensacion-pendiente-anteriores"

type IvaWalletCarryTarget = tuple[ModeloId, RevisionId, BindingId]

#: The exact revision coordinates the carve-out covers. Every M303 revision
#: that declares the compensación-pendiente carry is listed; a revision absent
#: from this set is governed by the ordinary fold rules even if it declares a
#: binding of the same name.
IVA_WALLET_OWNED_CARRY_TARGETS: frozenset[IvaWalletCarryTarget] = frozenset(
    (Modelo("303").value, revision_id, MODELO_303_IVA_COMPENSATION_BINDING_ID)
    for revision_id in (
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    )
)


def is_iva_wallet_owned_carry_target(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    binding_id: str,
) -> bool:
    """Return whether one exact binding coordinate belongs to the wallet."""
    return (modelo_id, revision_id, binding_id) in IVA_WALLET_OWNED_CARRY_TARGETS


def iva_wallet_owned_binding_ids_for_revision(
    *,
    modelo_id: str,
    revision_id: RevisionId,
) -> frozenset[BindingId]:
    """Return wallet-owned binding ids within one exact revision coordinate."""
    return frozenset(
        binding_id
        for owned_modelo, owned_revision, binding_id in IVA_WALLET_OWNED_CARRY_TARGETS
        if owned_modelo == modelo_id and owned_revision == revision_id
    )
