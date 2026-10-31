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

from .form_codes import form_for_role
from .ids import BindingId, RevisionId

__all__ = [
    "MODELO_303_IVA_COMPENSATION_BINDING_ID",
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
MODELO_303_IVA_COMPENSATION_BINDING_ID: Final[BindingId] = "modelo-303-compensacion-pendiente-anteriores"


def is_iva_wallet_owned_carry_target(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    binding_id: str,
) -> bool:
    """Return whether one exact binding coordinate belongs to the wallet."""
    del revision_id  # the carry keeps its binding id in every edition that declares it
    return modelo_id == form_for_role("iva.periodic") and binding_id == MODELO_303_IVA_COMPENSATION_BINDING_ID


def iva_wallet_owned_binding_ids_for_revision(
    *,
    modelo_id: str,
    revision_id: RevisionId,
) -> frozenset[BindingId]:
    """Return wallet-owned binding ids within one exact revision coordinate."""
    del revision_id  # the carry keeps its binding id in every edition that declares it
    if modelo_id != form_for_role("iva.periodic"):
        return frozenset[BindingId]()
    return frozenset((MODELO_303_IVA_COMPENSATION_BINDING_ID,))
