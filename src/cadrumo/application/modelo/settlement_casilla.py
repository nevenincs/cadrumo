"""Which casilla settles a modelo revision, read from the registry.

A declaration's settled result is the number an operator scans a list for, and
naming it is a filing-grade claim: showing the wrong casilla as "the result"
misreports what the taxpayer owes. So the answer comes from the registry's own
`semantic_role` declaration and from nowhere else -- never from a casilla
number, a position, or a label that reads like a total.

Coverage is deliberately narrow and will stay that way until each modelo's
settlement chain is modelled. `SETTLEMENT_SEMANTIC_ROLES` holds the grounded
terminal-liquidación roles, Modelo 100 today; modelo 303's casillas carry
positional roles such as `dr303_23` that name no meaning, so this resolver
returns nothing for them rather than guessing. A caller must render that
absence as "not available", not as a blank or a zero.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.calculations.registry.schema_ids import CasillaId

SETTLEMENT_SEMANTIC_ROLES: Final = frozenset(
    {
        "irpf_cuota_resultante_autoliquidacion",
        "irpf_resultado_declaracion",
    }
)
"""Terminal-liquidación `semantic_role` values, per settlement-bearing modelo.

Grounded in the #39 settlement-completeness audit: Modelo 100 cuota resultante
de la autoliquidación (casilla 0595, the liability before pagos a cuenta) and
resultado de la declaración (0670).

Modelo 100 today. Extend as further modelos' settlement chains are modelled --
and only from the official record design for that modelo, because the whole
point of reading a declared role is that nobody has to infer which cell is the
result. A modelo absent here yields no settlement casilla, which is a safe
false negative: the surface says it does not know rather than naming a cell on
no authority.
"""


class AmbiguousSettlementCasillaError(ValueError):
    """A revision declares more than one terminal-liquidación casilla."""


def settlement_casilla_id(revision: ModeloRevision) -> CasillaId | None:
    """Return the casilla that settles this revision, or nothing when undeclared.

    Returns `None` for a revision whose casillas declare no settlement role.
    That is the ordinary case today -- most modelos are not yet modelled to
    this depth -- and it is deliberately indistinguishable from "the registry
    has not said", because it IS that.

    Raises:
        AmbiguousSettlementCasillaError: Two or more casillas claim a terminal
            role. A revision with two results has no result, and picking the
            first would publish one of them as the answer with no grounds; the
            registry declaration is wrong and must be fixed rather than
            resolved here.
    """
    settling = [
        casilla.id
        for casilla in revision.casillas
        if casilla.semantic_role is not None and casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES
    ]
    if not settling:
        return None
    if len(settling) > 1:
        raise AmbiguousSettlementCasillaError(
            f"revision {revision.id!r} declares {len(settling)} terminal-liquidación casillas "
            f"({', '.join(sorted(settling))}); a declaration cannot have two results"
        )
    return settling[0]


__all__ = [
    "SETTLEMENT_SEMANTIC_ROLES",
    "AmbiguousSettlementCasillaError",
    "settlement_casilla_id",
]
