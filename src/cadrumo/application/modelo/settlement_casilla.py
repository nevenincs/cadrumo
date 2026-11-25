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

:func:`declaration_result_casillas` is the one rule for which casillas hold a
revision's result: the boxes the modelo's "tipo de declaración" rule reads,
where the revision defines any, and otherwise the registry's declared final
result. The workbench's settlement result and the help card's chain to the
result both take it from here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...domain.calculations.registry.result_casillas import (
    result_disposition_casilla_ids,
    settlement_casilla_role,
    settlement_remainder_casilla_ids,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from .refusal_door_verdicts import registry_defect_verdict

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.schema import ModeloRevision

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


DECLARATION_RESULT_SEMANTIC_ROLES: Final = frozenset({"irpf_resultado_declaracion"})
"""The roles that name a declaration's FINAL result -- a strict subset of the above.

Both settlement roles are terminal-liquidación cells, and both must be computed
before filing, which is why the advisory watches the whole set. Only one of
them is the number an operator means by "the result": Modelo 100 declares
`irpf_cuota_resultante_autoliquidacion` (casilla 0595) for the liability BEFORE
pagos a cuenta, and `irpf_resultado_declaracion` (0670) for what the
declaration actually settles.

Reading the registry is what surfaced this. A first version of this resolver
matched the full settlement set and would have raised ambiguity on M100 -- the
only modelo it covers -- because that revision legitimately declares both.
"""


class AmbiguousDeclarationResultError(TerminalPreconditionErrorMixin[object], CadrumoError):
    """A revision declares more than one final-result casilla."""


class SettlementCasillaV1(Protocol):
    """The casilla surface :func:`declaration_result_casilla_id` reads."""

    @property
    def id(self) -> CasillaId: ...

    @property
    def semantic_role(self) -> str | None: ...


class SettlementRevisionV1(Protocol):
    """The revision surface :func:`declaration_result_casilla_id` reads.

    Structural rather than the whole :class:`ModeloRevision` because the reader
    consumes only an id and the casillas' roles. A revision declaring two result
    casillas is the defect this function refuses, and the shipped registry
    cannot express it, so the refusal is exercised through a value carrying just
    this surface.
    """

    @property
    def id(self) -> str: ...

    @property
    def casillas(self) -> Sequence[SettlementCasillaV1]: ...


def declaration_result_casilla_id(revision: SettlementRevisionV1) -> CasillaId | None:
    """Return the casilla holding this revision's final result, or nothing.

    Returns `None` for a revision whose casillas declare no result role. That
    is the ordinary case today -- most modelos are not yet modelled to this
    depth -- and it is deliberately indistinguishable from "the registry has
    not said", because it IS that. A caller renders the absence as unknown,
    never as a blank or a zero.

    Raises:
        AmbiguousDeclarationResultError: Two or more casillas claim the result
            role. A declaration with two results has none, and picking the
            first would publish one of them as the answer on no grounds; the
            registry declaration is wrong and must be fixed rather than
            resolved here.
    """
    settling = [
        casilla.id
        for casilla in revision.casillas
        if casilla.semantic_role is not None and casilla.semantic_role in DECLARATION_RESULT_SEMANTIC_ROLES
    ]
    if not settling:
        return None
    if len(settling) > 1:
        raise AmbiguousDeclarationResultError(
            f"revision {revision.id!r} declares {len(settling)} final-result casillas "
            f"({', '.join(sorted(settling))}); a declaration cannot have two results",
            precondition_verdict=registry_defect_verdict("declaration_result_unique"),
        )
    return settling[0]


@dataclass(frozen=True, slots=True)
class DeclarationResultCasillas:
    """The casillas that hold one revision's result, and which rule named them.

    ``by_declared_type`` is true when the modelo's "tipo de declaración" rule
    names them, in the order it declares them, so its sign rule gives the
    direction; false when the registry's final-result role names the one
    casilla, whose direction no rule states.
    """

    casilla_ids: tuple[CasillaId, ...]
    by_declared_type: bool


def declaration_result_casillas(modelo: str, revision: SettlementRevisionV1) -> DeclarationResultCasillas | None:
    """Return the casillas holding ``revision``'s result, or ``None`` when it names none.

    The result boxes the modelo's "tipo de declaración" rule reads come first,
    those of them ``revision`` defines; otherwise the casilla the registry
    declares the final result.

    Raises:
        AmbiguousDeclarationResultError: The revision falls back to the
            registry's role and two casillas claim it.
    """
    defined = {casilla.id for casilla in revision.casillas}
    declared = tuple(casilla_id for casilla_id in result_disposition_casilla_ids(modelo) or () if casilla_id in defined)
    if declared:
        return DeclarationResultCasillas(casilla_ids=declared, by_declared_type=True)
    role = declaration_result_casilla_id(revision)
    return None if role is None else DeclarationResultCasillas(casilla_ids=(role,), by_declared_type=False)


def _computed_settlement_casilla(role: str, revision: ModeloRevision) -> CasillaId | None:
    """Return the one casilla of ``role`` the revision computes, or ``None`` when it computes none.

    Raises:
        AmbiguousDeclarationResultError: Two computed casillas of the revision
            claim the role.
    """
    settling = [
        casilla.id
        for casilla in revision.casillas
        if casilla.semantic_role == role and casilla.input_kind is InputKind.COMPUTED
    ]
    if len(settling) > 1:
        raise AmbiguousDeclarationResultError(
            f"revision {revision.id!r} computes {len(settling)} casillas of the settlement role {role!r}",
            precondition_verdict=registry_defect_verdict("settlement_role_unique"),
        )
    return settling[0] if settling else None


def declaration_settlement_casilla_id(modelo: str, revision: ModeloRevision) -> CasillaId | None:
    """Return the casilla whose value ``revision`` pays or refunds, or ``None`` when it names none.

    A modelo whose record states its amount to pay or refund apart from its
    result names that box's role in the registry; the revision's box of that
    role settles it, but only where the revision computes it, because a box
    the filer may type is no declared amount. Otherwise the amount settled is
    the result itself: the one result box the "tipo de declaración" rule reads,
    where the revision defines it, which is the amount settled only while no
    part of it is suspended or waived (see :func:`declaration_settlement_remainder_casilla_ids`).

    Raises:
        AmbiguousDeclarationResultError: Two computed casillas of the revision
            claim the settlement role.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    role = settlement_casilla_role(modelo)
    computed = None if role is None else _computed_settlement_casilla(role, revision)
    if computed is not None:
        return computed
    defined = {casilla.id for casilla in revision.casillas}
    declared = [casilla_id for casilla_id in result_disposition_casilla_ids(modelo) or () if casilla_id in defined]
    return declared[0] if len(declared) == 1 else None


def declaration_settlement_remainder_casilla_ids(modelo: str, revision: ModeloRevision) -> tuple[CasillaId, ...]:
    """Return the boxes that must hold no part of the result for the result to be the amount settled.

    Non-empty only when ``revision`` computes no box of the settlement role, so
    its settlement reads the result, and the modelo's record lets a part of the
    result be suspended (an amount to pay) or waived (a refund) apart from it.
    Where one of these boxes holds a positive part the amount settled is the
    remainder, which the revision does not compute, so the result is not the
    amount to pay or refund. Empty where the revision computes the settlement
    box, and for a box the revision does not define.

    Raises:
        AmbiguousDeclarationResultError: Two computed casillas of the revision
            claim the settlement role.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    role = settlement_casilla_role(modelo)
    if role is not None and _computed_settlement_casilla(role, revision) is not None:
        return ()
    defined = {casilla.id for casilla in revision.casillas}
    return tuple(casilla_id for casilla_id in settlement_remainder_casilla_ids(modelo) if casilla_id in defined)


__all__ = [
    "DECLARATION_RESULT_SEMANTIC_ROLES",
    "SETTLEMENT_SEMANTIC_ROLES",
    "AmbiguousDeclarationResultError",
    "DeclarationResultCasillas",
    "declaration_result_casilla_id",
    "declaration_result_casillas",
    "declaration_settlement_casilla_id",
    "declaration_settlement_remainder_casilla_ids",
]
