"""Modelo 100 formula evaluators for the registry calculation runtime.

This module owns the Modelo 100 operations that evaluate imputed real-estate
income and the estimación-objetiva agraria índice cascade.  The generic
dispatcher in :mod:`.formula_runtime` imports these evaluators directly; this
is the canonical home for the Modelo 100 operation family rather than a
forwarding layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError
from .formula_runtime_ops import (
    numeric_casilla_value as _numeric_casilla_value,
)
from .formula_runtime_ops import (
    resolve_scalar_parameter as _resolve_scalar_parameter,
)
from .ids import ParameterId
from .schema_formula import FormulaExpression

if TYPE_CHECKING:
    from .formula_runtime import EvalContext as _EvalContext

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class _M100ResolveImputedRentArgs:
    """Resolved registry ids for the M100 imputed-rent dispatcher."""

    catastral_value_casilla_id: CasillaId
    revised_flag_casilla_id: CasillaId
    disposal_days_casilla_id: CasillaId
    mixed_use_flag_casilla_id: CasillaId
    disposal_percentage_casilla_id: CasillaId
    mixed_use_days_casilla_id: CasillaId
    recent_rate_parameter: ParameterId
    old_rate_parameter: ParameterId
    year_days_parameter: ParameterId


def evaluate_m100_resolve_renta_inmobiliaria_imputada(
    expression: FormulaExpression,
    ctx: _EvalContext,
) -> Decimal:
    """Resolve M100 Art. 85 imputed real-estate income for cadastral-value rows.

    M100's 0083-0089 property row has the cadastral-value branch inputs:
    value, revised-value checkbox, days at disposal, and the mixed-use
    percentage/days override. The same row does not carry the no-cadastral
    substitute base (max of acquisition and administration-checked values), so
    that branch fails closed instead of inventing a base or silently returning
    zero for a positive imputation period.
    """
    op = "m100_resolve_renta_inmobiliaria_imputada"
    args = _m100_resolve_imputed_rent_args(expression)

    catastral_value = _numeric_casilla_value(args.catastral_value_casilla_id, ctx)
    disposal_days = _numeric_casilla_value(args.disposal_days_casilla_id, ctx)
    mixed_use = _m100_boolean_casilla_value(args.mixed_use_flag_casilla_id, ctx, op=op)
    disposal_percentage = _numeric_casilla_value(args.disposal_percentage_casilla_id, ctx)
    mixed_use_days = _numeric_casilla_value(args.mixed_use_days_casilla_id, ctx)
    is_revised = _m100_revised_cadastral_value_flag(args.revised_flag_casilla_id, ctx)

    if catastral_value < _ZERO:
        raise RegistryValidationError(
            "M100 Art.85 valor catastral must be non-negative",
            translated_message="errors.calc.m100_art85_catastral_value_negative",
            context={"casilla_id": args.catastral_value_casilla_id, "value": str(catastral_value)},
        )
    for casilla_id, value in (
        (args.disposal_days_casilla_id, disposal_days),
        (args.disposal_percentage_casilla_id, disposal_percentage),
        (args.mixed_use_days_casilla_id, mixed_use_days),
    ):
        if value < _ZERO:
            raise RegistryValidationError(
                "M100 Art.85 numeric inputs must be non-negative",
                translated_message="errors.calc.m100_art85_input_negative",
                context={"casilla_id": casilla_id, "value": str(value)},
            )
    if catastral_value == _ZERO:
        if disposal_days > _ZERO or mixed_use_days > _ZERO or mixed_use or disposal_percentage > _ZERO:
            raise RegistryValidationError(
                "M100 Art.85 no-catastral imputation requires substitute-base casillas that are not "
                "present in the 0083-0089 registry row",
                translated_message="errors.calc.m100_art85_no_catastral_base_missing",
                context={
                    "catastral_value_casilla_id": args.catastral_value_casilla_id,
                    "disposal_days_casilla_id": args.disposal_days_casilla_id,
                    "mixed_use_days_casilla_id": args.mixed_use_days_casilla_id,
                },
            )
        return _ZERO

    effective_days = mixed_use_days if mixed_use else disposal_days
    year_days = _resolve_scalar_parameter(args.year_days_parameter, ctx, op=op)
    _m100_validate_imputation_days(
        effective_days,
        casilla_id=args.mixed_use_days_casilla_id if mixed_use else args.disposal_days_casilla_id,
        max_days=year_days,
        max_days_parameter_id=args.year_days_parameter,
    )
    if not mixed_use and (mixed_use_days != _ZERO or disposal_percentage != _ZERO):
        raise RegistryValidationError(
            "M100 Art.85 mixed-use days or percentage require casilla 0086 to be checked",
            translated_message="errors.calc.m100_art85_mixed_use_inputs_without_flag",
            context={
                "mixed_use_flag_casilla_id": args.mixed_use_flag_casilla_id,
                "mixed_use_days_casilla_id": args.mixed_use_days_casilla_id,
                "disposal_percentage_casilla_id": args.disposal_percentage_casilla_id,
            },
        )
    share = _ONE
    if mixed_use:
        if disposal_percentage <= _ZERO or disposal_percentage > Decimal("100"):
            raise RegistryValidationError(
                "M100 Art.85 mixed-use percentage must be in (0, 100]",
                translated_message="errors.calc.m100_art85_disposal_percentage_invalid",
                context={
                    "casilla_id": args.disposal_percentage_casilla_id,
                    "value": str(disposal_percentage),
                },
            )
        share = disposal_percentage / Decimal("100")

    recent_rate = _resolve_scalar_parameter(args.recent_rate_parameter, ctx, op=op)
    old_rate = _resolve_scalar_parameter(args.old_rate_parameter, ctx, op=op)
    rate = recent_rate if is_revised else old_rate
    return catastral_value * rate * (effective_days / year_days) * share


def _m100_resolve_imputed_rent_args(expression: FormulaExpression) -> _M100ResolveImputedRentArgs:
    op = "m100_resolve_renta_inmobiliaria_imputada"
    if len(expression.args) != 9:
        raise RegistryValidationError(f"formula op {op!r} expects 9 args, got {len(expression.args)}")
    (
        catastral_value_arg,
        revised_flag_arg,
        disposal_days_arg,
        mixed_use_flag_arg,
        disposal_percentage_arg,
        mixed_use_days_arg,
        year_days_arg,
        recent_rate_arg,
        old_rate_arg,
    ) = expression.args
    if catastral_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if revised_flag_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if disposal_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a casilla leaf")
    if mixed_use_flag_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a casilla leaf")
    if disposal_percentage_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a casilla leaf")
    if mixed_use_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[5] to be a casilla leaf")
    if year_days_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[6] to be a parameter leaf")
    if recent_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[7] to be a parameter leaf")
    if old_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[8] to be a parameter leaf")
    return _M100ResolveImputedRentArgs(
        catastral_value_casilla_id=catastral_value_arg.casilla_id,
        revised_flag_casilla_id=revised_flag_arg.casilla_id,
        disposal_days_casilla_id=disposal_days_arg.casilla_id,
        mixed_use_flag_casilla_id=mixed_use_flag_arg.casilla_id,
        disposal_percentage_casilla_id=disposal_percentage_arg.casilla_id,
        mixed_use_days_casilla_id=mixed_use_days_arg.casilla_id,
        recent_rate_parameter=recent_rate_arg.parameter,
        old_rate_parameter=old_rate_arg.parameter,
        year_days_parameter=year_days_arg.parameter,
    )


def _m100_revised_cadastral_value_flag(casilla_id: CasillaId, ctx: _EvalContext) -> bool:
    raw_value = ctx.text_values.get(casilla_id, "")
    ctx.operand_refs.append(casilla_id)
    ctx.operand_casilla_refs.append(casilla_id)
    if raw_value == "":
        return False
    normalised = raw_value.strip().upper()
    if normalised == "X":
        return True
    raise RegistryValidationError(
        "M100 Art.85 revised cadastral value flag must be the official X checkbox value",
        translated_message="errors.calc.m100_art85_revision_flag_invalid",
        context={"casilla_id": casilla_id, "value": raw_value},
    )


def _m100_boolean_casilla_value(casilla_id: CasillaId, ctx: _EvalContext, *, op: str) -> bool:
    value = _numeric_casilla_value(casilla_id, ctx)
    if value not in {_ZERO, _ONE}:
        raise RegistryValidationError(
            "M100 Art.85 boolean casilla must be 0 or 1",
            translated_message="errors.calc.m100_art85_boolean_invalid",
            context={"casilla_id": casilla_id, "value": str(value), "op": op},
        )
    return value == _ONE


def _m100_validate_imputation_days(
    days: Decimal,
    *,
    casilla_id: CasillaId,
    max_days: Decimal,
    max_days_parameter_id: ParameterId,
) -> None:
    if max_days != max_days.to_integral_value() or max_days <= _ZERO or max_days > Decimal("366"):
        raise RegistryValidationError(
            "M100 Art.85 imputation year-days parameter must be an integer in [1, 366]",
            translated_message="errors.calc.m100_art85_imputation_days_invalid",
            context={"parameter_id": max_days_parameter_id, "value": str(max_days), "max_days": "366"},
        )
    if days != days.to_integral_value() or days <= _ZERO or days > max_days:
        raise RegistryValidationError(
            f"M100 Art.85 imputation days must be an integer in [1, {max_days}]",
            translated_message="errors.calc.m100_art85_imputation_days_invalid",
            context={"casilla_id": casilla_id, "value": str(days), "max_days": str(max_days)},
        )


#: Índice-corrector casilla count the M100 estimación-objetiva agraria Fase 3ª
#: dispatcher carries (Anexo I instrucción 2.3, letras a) to h) — índices 1 to 8;
#: índice 9, mejillón en batea (letra i), applies to a separate producto
#: (casilla 0160) outside this cascade).
_M100_EO_AGRARIA_INDICE_COUNT = 8


@dataclass(frozen=True, slots=True)
class _M100ResolveEoAgrariaIndicesCorrectoresArgs:
    """Resolved registry ids for the M100 EO-agraria Fase 3ª índices-correctores dispatcher."""

    minorado_casilla_id: CasillaId
    indice_casilla_ids: tuple[CasillaId, ...]


def _m100_resolve_eo_agraria_indices_correctores_args(
    expression: FormulaExpression,
) -> _M100ResolveEoAgrariaIndicesCorrectoresArgs:
    op = "m100_resolve_eo_agraria_indices_correctores"
    expected_arg_count = 1 + _M100_EO_AGRARIA_INDICE_COUNT
    if len(expression.args) != expected_arg_count:
        raise RegistryValidationError(
            f"formula op {op!r} expects {expected_arg_count} args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": str(expected_arg_count)},
        )
    minorado_arg = expression.args[0]
    if minorado_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    indice_casilla_ids: list[CasillaId] = []
    for position, indice_arg in enumerate(expression.args[1:], start=1):
        if indice_arg.casilla_id is None:
            raise RegistryValidationError(
                f"formula op {op!r} requires args[{position}] to be a casilla leaf",
                translated_message="errors.calc.lookup_dispatch_arg_kind",
                context={"op": op, "position": f"args[{position}]", "expected_kind": "casilla"},
            )
        indice_casilla_ids.append(indice_arg.casilla_id)
    return _M100ResolveEoAgrariaIndicesCorrectoresArgs(
        minorado_casilla_id=minorado_arg.casilla_id,
        indice_casilla_ids=tuple(indice_casilla_ids),
    )


def _m100_eo_agraria_read_indice(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    """Read one Fase 3ª índice-corrector casilla, tolerating either declared type.

    Every índice casilla in the Anexo I instrucción 2.3 cascade (letras a) to
    h)) is a rate the operator/preparer reads off the Anexo table, but the
    AEAT Diseño de Registros declares one of the eight (índice 4, «piensos
    adquiridos a terceros», casilla 1543) with field type ``X`` (text) while
    the other seven use ``P012`` (decimal) — an AEAT dictionary quirk, not a
    semantic difference in the índice itself. A text-typed casilla's value
    only ever reaches :attr:`_EvalContext.text_values`, never
    :attr:`_EvalContext.values` (the numeric map defaults it to zero and never
    receives the operator's real figure), so reading it through
    :func:`~domain.calculations.registry.formula_runtime_ops.numeric_casilla_value`
    alone would silently and permanently treat índice 4 as never declared.
    Checking ``text_values`` first — and falling back to the numeric map only
    when the casilla is genuinely absent from ``text_values`` (true for every
    ``P012`` índice, which a caller never routes through ``text_inputs``) —
    lets the same cascade loop handle both declared types without a
    position-keyed special case. An unparsable or blank text value resolves to
    zero, the same "índice not applied" signal a blank decimal casilla gives.
    """
    if casilla_id in ctx.text_values:
        ctx.operand_refs.append(casilla_id)
        ctx.operand_casilla_refs.append(casilla_id)
        raw_text = ctx.text_values[casilla_id].strip()
        try:
            value = Decimal(raw_text) if raw_text else _ZERO
        except ArithmeticError:
            value = _ZERO
        ctx.operand_values.append(value)
        return value
    return _numeric_casilla_value(casilla_id, ctx)


def evaluate_m100_resolve_eo_agraria_indices_correctores(
    expression: FormulaExpression,
    ctx: _EvalContext,
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
    ``P012`` for seven of the eight, ``X`` for índice 4 — see
    :func:`_m100_eo_agraria_read_indice`, fields ``E5AI1`` to ``E5AI8``) — the
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
    minorado = _numeric_casilla_value(args.minorado_casilla_id, ctx)
    ctx.operand_refs.append(args.minorado_casilla_id)
    ctx.operand_casilla_refs.append(args.minorado_casilla_id)
    if minorado <= _ZERO:
        return minorado
    rendimiento = minorado
    for indice_casilla_id in args.indice_casilla_ids:
        indice = _m100_eo_agraria_read_indice(indice_casilla_id, ctx)
        if indice <= _ZERO:
            continue
        rendimiento = rendimiento * indice
    return rendimiento
