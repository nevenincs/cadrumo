"""Modelo 100 formula evaluators for the registry calculation runtime.

This module owns the Modelo 100 operation that evaluates the
estimación-objetiva agraria índice cascade.  The generic
dispatcher in :mod:`.formula_runtime` imports these evaluators directly; this
is the canonical home for that Modelo 100 operation rather than a
forwarding layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId
from ....core.decimal.constants import ZERO
from .errors import RegistryValidationError
from .formula_runtime_ops import (
    numeric_casilla_value,
    require_casilla_leaf,
    text_tolerant_casilla_value,
)
from .schema_formula import FormulaExpression

if TYPE_CHECKING:
    from .formula_expression import EvalContext


@dataclass(frozen=True, slots=True)
class _M100ResolveEoAgrariaIndicesCorrectoresArgs:
    """Resolved registry ids for the M100 EO-agraria Fase 3ª índices-correctores dispatcher."""

    minorado_casilla_id: CasillaId
    indice_casilla_ids: tuple[CasillaId, ...]


def _m100_resolve_eo_agraria_indices_correctores_args(
    expression: FormulaExpression,
) -> _M100ResolveEoAgrariaIndicesCorrectoresArgs:
    op = "m100_resolve_eo_agraria_indices_correctores"
    minorado_arg = expression.args[0]
    if minorado_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    indice_casilla_ids: list[CasillaId] = []
    for position, indice_arg in enumerate(expression.args[1:], start=1):
        indice_casilla_ids.append(require_casilla_leaf(indice_arg, op=op, position=position))
    return _M100ResolveEoAgrariaIndicesCorrectoresArgs(
        minorado_casilla_id=minorado_arg.casilla_id,
        indice_casilla_ids=tuple(indice_casilla_ids),
    )


def evaluate_m100_resolve_eo_agraria_indices_correctores(
    expression: FormulaExpression,
    ctx: EvalContext,
) -> Decimal:
    """Resolve the M100 estimación-objetiva agraria Fase 3ª índices correctores.

    Orden HAC/1347/2024, Anexo I instrucción 2.3 (letras a) to h)) fixes the
    mechanism: the rendimiento neto minorado (Fase 2ª, casilla 1539) is
    corrected by applying, in sequence, the índice or índices correctores that
    correspond to the activity — each índice applying "sobre el rendimiento
    neto minorado o, en su caso, sobre el rectificado por aplicación de los
    [índices] anteriores": a sequential cascade over the Anexo's own letra
    ordering (a → h), not a single-index pick nor a simultaneous product.

    Each índice casilla (1540 to 1547, one per letra a) to h)) is an
    operator/preparer-declared rate (AEAT Diseño de Registros field type
    ``P012`` for seven of the eight, ``X`` for índice 4, fields ``E5AI1`` to ``E5AI8``; read through
    :func:`~domain.calculations.registry.formula_runtime_ops.text_tolerant_casilla_value`) — the
    taxpayer reads the applicable índice off the Anexo I table for their
    activity and enters it directly, mirroring how the M131
    estimación-objetiva módulos engine resolves its own índice corrector de
    exceso. A blank índice casilla resolves to zero (indistinguishable, at
    this op's boundary, from "not declared"); because every real índice in the
    Anexo I table is strictly positive (0,50 to 0,95), a non-positive read is
    treated as "índice not applied" — the cascade step is skipped (factor of
    1, never a fabricated zero-out) rather than multiplying the accumulator by
    zero. This never over-states nor under-states the reduction: a real but
    undeclared índice simply goes uncredited, and a declared índice is applied
    exactly once, in the Anexo's own order.

    A non-positive rendimiento neto minorado never receives índices
    correctores and resolves to the minorado figure unchanged. Índice 9
    (mejillón en batea, letra i) is not modelled by this dispatcher: it applies
    to a separate producto (casilla 0160) outside the 1539→1548 cascade.
    """
    args = _m100_resolve_eo_agraria_indices_correctores_args(expression)
    minorado = numeric_casilla_value(args.minorado_casilla_id, ctx)
    ctx.operand_refs.append(args.minorado_casilla_id)
    ctx.operand_casilla_refs.append(args.minorado_casilla_id)
    if minorado <= ZERO:
        return minorado
    rendimiento = minorado
    for indice_casilla_id in args.indice_casilla_ids:
        indice = text_tolerant_casilla_value(indice_casilla_id, ctx)
        if indice <= ZERO:
            continue
        rendimiento = rendimiento * indice
    return rendimiento
