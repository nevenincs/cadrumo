"""M131 módulos formula-op evaluators for the registry runtime.

Extracted from :mod:`~domain.calculations.registry._formula_runtime` to keep
that dispatcher under its size budget while preserving the existing registry op
names. Dispatch still lives in ``_formula_runtime``; this module owns the
Modelo 131 estimación-objetiva módulos Fase 1ª-3ª evaluators and advisory flag
helpers.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime`
        Central formula dispatcher that routes M131 operation names here.
    :mod:`~domain.calculations.registry._formula_runtime_ops`
        Shared numeric-casilla, parameter, and arithmetic helpers used by these
        evaluators.
    :class:`~domain.calculations.registry.FormulaExpression`
        Registry-authored operation graph consumed by each evaluator.
    :class:`~domain.calculations.registry.ParameterDefinition`
        Keyed-bracket and scalar parameter rows that carry the módulo tables and
        index rates.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Public calculation entry point that records these evaluator results in
        registry calculation provenance.
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
        Advisory predicates that surface untabled or conflicting M131 módulo
        results instead of allowing silent zeros.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ....core import CasillaId
from .errors import RegistryValidationError
from ._formula_runtime_ops import (
    numeric_casilla_value as _numeric_casilla_value,
)
from ._formula_runtime_ops import (
    resolve_bracket as _resolve_bracket,
)
from ._formula_runtime_ops import (
    resolve_keyed_bracket as _resolve_keyed_bracket,
)
from ._formula_runtime_ops import (
    resolve_scalar_parameter as _resolve_scalar_parameter,
)
from ._ids import ParameterId
from ._schema import FormulaExpression

if TYPE_CHECKING:
    from ._formula_runtime import EvalContext

    _EvalContext = EvalContext

_ZERO = Decimal("0")


def _read_modulos_indice(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
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


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosPrevioArgs:
    """Resolved registry ids for the M131 estimación-objetiva módulos Fase 1ª dispatcher."""

    epigrafe_casilla_id: CasillaId
    modulo_unit_casilla_ids: tuple[CasillaId, CasillaId, CasillaId, CasillaId, CasillaId, CasillaId, CasillaId]
    coefficient_parameter: ParameterId


#: Módulo slot count the M131 first-slice coefficient tables carry (the
#: highest-cardinality tabled activities — 644.1 "Comercio al por menor de
#: pan, pastelería..." and 644.2/644.3 — use all seven; activities with fewer
#: signos pass a literal ``0`` for the unused trailing slots).
_M131_MODULOS_SLOT_COUNT = 7


def _m131_resolve_modulos_previo_args(expression: FormulaExpression) -> _M131ResolveModulosPrevioArgs:
    op = "m131_resolve_modulos_previo"
    expected_arg_count = 2 + _M131_MODULOS_SLOT_COUNT
    if len(expression.args) != expected_arg_count:
        raise RegistryValidationError(
            f"formula op {op!r} expects {expected_arg_count} args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": str(expected_arg_count)},
        )
    epigrafe_arg = expression.args[0]
    modulo_args = expression.args[1 : 1 + _M131_MODULOS_SLOT_COUNT]
    coefficient_arg = expression.args[1 + _M131_MODULOS_SLOT_COUNT]
    if epigrafe_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    resolved_modulo_ids: list[CasillaId] = []
    for index, modulo_arg in enumerate(modulo_args, start=1):
        if modulo_arg.casilla_id is None:
            raise RegistryValidationError(
                f"formula op {op!r} requires args[{index}] to be a casilla leaf",
                translated_message="errors.calc.lookup_dispatch_arg_kind",
                context={"op": op, "position": f"args[{index}]", "expected_kind": "casilla"},
            )
        resolved_modulo_ids.append(modulo_arg.casilla_id)
    if coefficient_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[{1 + _M131_MODULOS_SLOT_COUNT}] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={
                "op": op,
                "position": f"args[{1 + _M131_MODULOS_SLOT_COUNT}]",
                "expected_kind": "parameter",
            },
        )
    modulo_ids = (
        resolved_modulo_ids[0],
        resolved_modulo_ids[1],
        resolved_modulo_ids[2],
        resolved_modulo_ids[3],
        resolved_modulo_ids[4],
        resolved_modulo_ids[5],
        resolved_modulo_ids[6],
    )
    return _M131ResolveModulosPrevioArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        modulo_unit_casilla_ids=modulo_ids,
        coefficient_parameter=coefficient_arg.parameter,
    )


def evaluate_m131_resolve_modulos_previo(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M131/M100 estimación-objetiva Fase 1ª rendimiento neto previo.

    LIRPF art. 31 + the annual Orden de módulos (Anexo II) fix the mechanism:
    rendimiento neto previo = Σ(unidades_módulo × rendimiento anual por unidad
    antes de amortización), per IAE epígrafe. This op reads the operator-
    declared IAE epígrafe (a text casilla) and up to seven módulo unit-count
    casillas (the highest signo count among the tabled activities), looks up
    each módulo's coefficient in the registry-declared
    :class:`~domain.calculations.registry.ParameterDefinition`
    (``data_type='keyed_bracket_table'``, key ``"<epígrafe>:<módulo>"``), and
    sums the per-módulo products.

    An untabled epígrafe (the engine covers a bounded initial set of
    activities) or a blank epígrafe resolves to ``Decimal('0')`` — this
    op feeds an internal-only
    advisory-support casilla, never the filed casilla 01 directly, so a zero
    here means "the table-driven engine has no coverage for this activity",
    not "the rendimiento is zero". The
    ``advisory_when_computed_diverges`` verification predicate surfaces the
    gap or the discrepancy to the operator; it never silently substitutes.
    """
    args = _m131_resolve_modulos_previo_args(expression)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    parameter = ctx.parameters.get(args.coefficient_parameter)
    ctx.operand_refs.append(args.coefficient_parameter)
    if not epigrafe or parameter is None:
        return _ZERO
    total = _ZERO
    for modulo_index, modulo_casilla_id in enumerate(args.modulo_unit_casilla_ids, start=1):
        units = _numeric_casilla_value(modulo_casilla_id, ctx)
        if units == _ZERO:
            continue
        coefficient = _resolve_keyed_bracket(
            parameter,
            key=f"{epigrafe}:{modulo_index}",
            filing_year=ctx.filing_year,
        )
        if coefficient is None:
            # This módulo slot has no row for the declared epígrafe (either the
            # epígrafe is entirely untabled, or this slot does not apply to it).
            # A non-zero unit count against an untabled epígrafe means the
            # WHOLE Fase 1ª product is untabled — the engine cannot mix tabled
            # and untabled módulos for one activity — so the running total is
            # abandoned and the internal casilla resolves to zero.
            return _ZERO
        ctx.operand_values.append(coefficient)
        total += units * coefficient
    return total


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosMinoracionEmpleoArgs:
    """Resolved registry ids for the M131 Fase 2ª minoración por incentivos al empleo dispatcher."""

    epigrafe_casilla_id: CasillaId
    modulo_1_actual_casilla_id: CasillaId
    modulo_1_anterior_casilla_id: CasillaId
    coefficient_parameter: ParameterId
    tramos_parameter: ParameterId
    incremento_rate_parameter: ParameterId


def _m131_resolve_modulos_minoracion_empleo_args(
    expression: FormulaExpression,
) -> _M131ResolveModulosMinoracionEmpleoArgs:
    op = "m131_resolve_modulos_minoracion_empleo"
    if len(expression.args) != 6:
        raise RegistryValidationError(
            f"formula op {op!r} expects 6 args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "6"},
        )
    epigrafe_arg, actual_arg, anterior_arg, coefficient_arg, tramos_arg, incremento_arg = expression.args
    if epigrafe_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    if actual_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[1] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "casilla"},
        )
    if anterior_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[2] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "casilla"},
        )
    if coefficient_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[3] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[3]", "expected_kind": "parameter"},
        )
    if tramos_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[4] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[4]", "expected_kind": "parameter"},
        )
    if incremento_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[5] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[5]", "expected_kind": "parameter"},
        )
    return _M131ResolveModulosMinoracionEmpleoArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        modulo_1_actual_casilla_id=actual_arg.casilla_id,
        modulo_1_anterior_casilla_id=anterior_arg.casilla_id,
        coefficient_parameter=coefficient_arg.parameter,
        tramos_parameter=tramos_arg.parameter,
        incremento_rate_parameter=incremento_arg.parameter,
    )


def evaluate_m131_resolve_modulos_minoracion_empleo(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M131/M100 estimación-objetiva Fase 2ª minoración por incentivos al empleo.

    Orden HAC/1347/2024 Anexo II, instrucción 2.2.a) fixes the mechanism
    (AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, worked example
    epígrafe 673.1): the minoración is the módulo «personal asalariado»
    coefficient (rendimiento anual por unidad antes de amortización) times a
    coeficiente de minoración, itself the sum of two sub-coefficients:

    * ``coeficiente por incremento`` — when the current year's módulo 1 unit
      count exceeds the prior year's, the positive difference times 0,40
      (a scalar ``ratio`` registry parameter, not hardcoded per
      ``aeat-registry-authority-flow``);
    * ``coeficiente por tramos`` — a progressive bracket lookup (the Orden's
      tramo table) applied to the módulo 1 units net of the increment already
      credited above (``resolve_bracket`` reused verbatim; the tramo table is
      structurally the same cumulative-progressive-scale shape as an IRPF
      escala).

    The prior-year módulo 1 casilla (``modulos-1-unidades-anterior``) is an
    optional manual input that defaults to ``Decimal('0')`` when the
    operator has not declared a prior-year comparison. Because a genuinely
    zero prior-year headcount is legally indistinguishable, at this op's
    boundary, from "no comparison declared", a non-positive ``anterior`` is
    treated as "no incremento claimed" — the coeficiente por incremento is
    skipped (never fabricated) and the coeficiente por tramos runs on the
    full current-year módulo 1 units. This never over-states the minoración
    — a real, undeclared increment simply goes uncredited, following the
    principle that omitting an undeclared reduction must not over-state
    the figure — and keeps a blank optional input from silently
    manufacturing an increment credit.

    Both a blank epígrafe and an untabled epígrafe (no módulo 1 coefficient
    row) resolve to ``Decimal('0')`` — this op feeds the same internal-only
    advisory-support casilla chain as Fase 1ª
    (:func:`evaluate_m131_resolve_modulos_previo`), so a zero here means "no
    minoración computed", never a filed figure standing in for the operator's
    manual casilla 01.
    """
    args = _m131_resolve_modulos_minoracion_empleo_args(expression)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    coefficient_parameter = ctx.parameters.get(args.coefficient_parameter)
    ctx.operand_refs.append(args.coefficient_parameter)
    if not epigrafe or coefficient_parameter is None:
        return _ZERO
    modulo_1_coefficient = _resolve_keyed_bracket(
        coefficient_parameter,
        key=f"{epigrafe}:1",
        filing_year=ctx.filing_year,
    )
    if modulo_1_coefficient is None:
        return _ZERO
    ctx.operand_values.append(modulo_1_coefficient)
    actual = _numeric_casilla_value(args.modulo_1_actual_casilla_id, ctx)
    anterior = _numeric_casilla_value(args.modulo_1_anterior_casilla_id, ctx)
    incremento = actual - anterior if anterior > _ZERO and actual > anterior else _ZERO
    incremento_rate = _resolve_scalar_parameter(
        args.incremento_rate_parameter,
        ctx,
        op="m131_resolve_modulos_minoracion_empleo",
    )
    coeficiente_incremento = incremento * incremento_rate
    base_tramos = actual - incremento
    tramos_parameter = ctx.parameters.get(args.tramos_parameter)
    ctx.operand_refs.append(args.tramos_parameter)
    if tramos_parameter is None or base_tramos <= _ZERO:
        coeficiente_tramos = _ZERO
    else:
        coeficiente_tramos = _resolve_bracket(tramos_parameter, base_tramos, ctx.date_context)
        ctx.operand_values.append(coeficiente_tramos)
    coeficiente_minoracion = coeficiente_incremento + coeficiente_tramos
    return coeficiente_minoracion * modulo_1_coefficient


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosIndiceExcesoArgs:
    """Resolved registry ids for the M131 Fase 3ª índice corrector de exceso dispatcher."""

    epigrafe_casilla_id: CasillaId
    minorado_casilla_id: CasillaId
    cuantia_parameter: ParameterId
    indice_exceso_parameter: ParameterId


def _m131_resolve_modulos_indice_exceso_args(expression: FormulaExpression) -> _M131ResolveModulosIndiceExcesoArgs:
    op = "m131_resolve_modulos_indice_exceso"
    if len(expression.args) != 4:
        raise RegistryValidationError(
            f"formula op {op!r} expects 4 args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "4"},
        )
    epigrafe_arg, minorado_arg, cuantia_arg, indice_arg = expression.args
    if epigrafe_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    if minorado_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[1] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "casilla"},
        )
    if cuantia_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[2] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "parameter"},
        )
    if indice_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[3] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[3]", "expected_kind": "parameter"},
        )
    return _M131ResolveModulosIndiceExcesoArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        minorado_casilla_id=minorado_arg.casilla_id,
        cuantia_parameter=cuantia_arg.parameter,
        indice_exceso_parameter=indice_arg.parameter,
    )


def evaluate_m131_resolve_modulos_indice_exceso(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M131/M100 estimación-objetiva Fase 3ª índice corrector de exceso.

    Orden HAC/1347/2024 Anexo II, instrucción 2.3.b.3) fixes the mechanism
    (AEAT Manual práctico de Renta 2025, Parte 1, Capítulo 8, worked example
    epígrafe 673.1): when the rendimiento neto minorado (Fase 2ª) exceeds a
    per-activity cuantía threshold, the excess above that threshold is
    multiplied by the índice 1,30 (a scalar ``ratio`` registry parameter):

        rendimiento_neto_modulos = cuantia + indice x (minorado - cuantia)

    when ``minorado > cuantia``; otherwise the módulos figure equals the
    minorado figure unchanged (no other índice corrector is modelled in this
    first slice — a legitimately-zero-index case, per the manual: "si el
    rendimiento neto minorado ... es una cantidad negativa, no se aplicarán
    los índices correctores"). A blank epígrafe, an untabled epígrafe (no
    cuantía row), or a non-positive minorado all resolve to the minorado
    figure unchanged — this op feeds the same internal-only advisory-support
    casilla chain as Fases 1ª/2ª, never a filed figure standing in for the
    operator's manual casilla 01.

    **Incompatibility gap (not modelled in this first slice).** Orden
    HAC/1347/2024 Anexo II, instrucción 2.3 (see
    ``orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades``)
    declares the índice de exceso (b.3) applied here INCOMPATIBLE with two
    other índices this op does not model: "Cuando resulte aplicable el índice
    corrector para empresas de pequeña dimensión (b.1) no se aplicará el
    índice corrector de exceso (b.3)" (b.1 excludes b.3 outright), and the
    índices correctores especiales (a.2 transporte por autotaxis, a.3
    transporte urbano colectivo, a.4 transporte de mercancías por carretera y
    servicios de mudanzas, a.5) are legally incompatible with b.1 for the
    same activities — so an activity eligible for a.2/a.4 that is ALSO
    eligible for b.1 must never apply b.3 either. Two of the tabled epígrafes
    in ``m131-modulos-cuantia-exceso-2025`` carry a documented índice especial
    ("721.2" transporte por autotaxis, letra a.2; "722" transporte de
    mercancías por carretera / servicios de mudanzas, letra a.4); this op
    applies b.3 to them unconditionally whenever ``minorado > cuantia``,
    without checking either exclusivity rule. The
    ``modelo-131-2025-modulos-indice-exceso-incompatible-autotaxi`` /
    ``-mercancias`` ADVISORY verification predicates surface a non-blocking
    review prompt for these two epígrafes when the índice-exceso path
    activates, guarding against a silent under-declaration — full
    modelling of b.1 and a.2/a.4 is not yet implemented.
    """
    args = _m131_resolve_modulos_indice_exceso_args(expression)
    minorado = _numeric_casilla_value(args.minorado_casilla_id, ctx)
    ctx.operand_refs.append(args.minorado_casilla_id)
    ctx.operand_casilla_refs.append(args.minorado_casilla_id)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    cuantia_parameter = ctx.parameters.get(args.cuantia_parameter)
    ctx.operand_refs.append(args.cuantia_parameter)
    if not epigrafe or cuantia_parameter is None or minorado <= _ZERO:
        return minorado
    cuantia = _resolve_keyed_bracket(cuantia_parameter, key=epigrafe, filing_year=ctx.filing_year)
    if cuantia is None or minorado <= cuantia:
        return minorado
    ctx.operand_values.append(cuantia)
    indice = _resolve_scalar_parameter(
        args.indice_exceso_parameter,
        ctx,
        op="m131_resolve_modulos_indice_exceso",
    )
    return cuantia + indice * (minorado - cuantia)


#: Epígrafes carrying a documented índice corrector especial (Orden
#: HAC/1347/2024 Anexo II, instrucción 2.3, letra a) that the
#: incompatibilidades clause excludes from the índice corrector para
#: empresas de pequeña dimensión (b.1) — "En ningún caso será aplicable el
#: índice corrector para empresas de pequeña dimensión (b.1) a las
#: actividades para las que están previstos los índices correctores
#: especiales enumerados en las letras a.2), a.3), a.4) y a.5)." Only the two
#: epígrafes already tabled by the índice-de-exceso dataset carry a
#: documented especial índice today (721.2 transporte por autotaxis, letra
#: a.2; 722 transporte de mercancías por carretera, letra a.4) — see the
#: sibling ``modelo-131-2025-modulos-indice-exceso-incompatible-*`` ADVISORY
#: predicates, which flag the a.2/a.4-vs-b.3 half of the same
#: incompatibilidades clause this frozenset structurally enforces for the
#: a.2/a.3/a.4/a.5-vs-b.1 half.
_M131_EPIGRAFES_INDICE_ESPECIAL = frozenset({"721.2", "722"})


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosIndicesGeneralesArgs:
    """Resolved registry ids for the M131 Fase 3ª índices correctores generales dispatcher."""

    epigrafe_casilla_id: CasillaId
    minorado_casilla_id: CasillaId
    pequena_dimension_casilla_id: CasillaId
    temporada_casilla_id: CasillaId
    inicio_actividad_casilla_id: CasillaId
    cuantia_parameter: ParameterId
    indice_exceso_parameter: ParameterId


def _m131_resolve_modulos_indices_generales_args(
    expression: FormulaExpression,
) -> _M131ResolveModulosIndicesGeneralesArgs:
    op = "m131_resolve_modulos_indices_generales"
    if len(expression.args) != 7:
        raise RegistryValidationError(
            f"formula op {op!r} expects 7 args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "7"},
        )
    (
        epigrafe_arg,
        minorado_arg,
        pequena_dimension_arg,
        temporada_arg,
        inicio_actividad_arg,
        cuantia_arg,
        indice_arg,
    ) = expression.args
    casilla_positions = {
        0: epigrafe_arg,
        1: minorado_arg,
        2: pequena_dimension_arg,
        3: temporada_arg,
        4: inicio_actividad_arg,
    }
    for position, arg in casilla_positions.items():
        if arg.casilla_id is None:
            raise RegistryValidationError(
                f"formula op {op!r} requires args[{position}] to be a casilla leaf",
                translated_message="errors.calc.lookup_dispatch_arg_kind",
                context={"op": op, "position": f"args[{position}]", "expected_kind": "casilla"},
            )
    if cuantia_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[5] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[5]", "expected_kind": "parameter"},
        )
    if indice_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[6] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[6]", "expected_kind": "parameter"},
        )
    assert epigrafe_arg.casilla_id is not None
    assert minorado_arg.casilla_id is not None
    assert pequena_dimension_arg.casilla_id is not None
    assert temporada_arg.casilla_id is not None
    assert inicio_actividad_arg.casilla_id is not None
    return _M131ResolveModulosIndicesGeneralesArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        minorado_casilla_id=minorado_arg.casilla_id,
        pequena_dimension_casilla_id=pequena_dimension_arg.casilla_id,
        temporada_casilla_id=temporada_arg.casilla_id,
        inicio_actividad_casilla_id=inicio_actividad_arg.casilla_id,
        cuantia_parameter=cuantia_arg.parameter,
        indice_exceso_parameter=indice_arg.parameter,
    )


def evaluate_m131_resolve_modulos_indices_generales(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M131 estimación-objetiva Fase 3ª índices correctores generales cascade.

    Orden HAC/1347/2024 Anexo II, instrucción 2.3 fixes both the mechanism and
    the application order for the índices correctores generales (letra b)):
    "Los índices correctores se aplicarán según el orden que aparecen
    enumerados a continuación, siempre que no resulten incompatibles, ... sobre
    el rendimiento neto minorado o, en su caso, sobre el rectificado por
    aplicación de los mismos" — b.1) empresas de pequeña dimensión, b.2)
    temporada, b.3) exceso, b.4) inicio de nuevas actividades, each a
    multiplicative factor over the RUNNING rendimiento, not a single-índice
    pick nor a simultaneous product (mirrors the M100 EO-agraria índices
    correctores cascade,
    :func:`_evaluate_m100_resolve_eo_agraria_indices_correctores`). The four
    steps are applied STRICTLY SEQUENTIALLY in that literal enumeration order
    — b.1, then b.2, then b.3, then b.4 — each on the running rendimiento left
    by the previous step; b.3's exceso threshold is non-linear
    (identity below the tabled cuantía, ``cuantía + índice × exceso`` above),
    so applying b.4 before b.3 (grouping b.2/b.4 as one step ahead of b.3)
    yields a materially different, non-commutative result and is a defect,
    not an equivalent reordering.

    Each índice casilla (pequeña dimensión, temporada, inicio de nuevas
    actividades) is an operator/preparer-declared rate: the taxpayer reads the
    applicable índice off the Anexo II tables (población del municipio /
    duración de la temporada / ejercicio de inicio, none of which this engine
    models as taxpayer facts) and enters it directly — the same honest-scalar
    pattern the índice de exceso (b.3) and the M100 agraria cascade already
    use. A blank or non-positive índice resolves to "not applied" (factor of
    1), never a fabricated value.

    Incompatibilidades (Orden HAC/1347/2024 Anexo II, instrucción 2.3,
    grounded in ``orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades``),
    enforced structurally rather than left to an advisory-only guard:

    * "En ningún caso será aplicable el índice corrector para empresas de
      pequeña dimensión (b.1) a las actividades para las que están previstos
      los índices correctores especiales" (a.2/a.3/a.4/a.5) — a declared
      pequeña-dimensión índice is IGNORED (never applied) for the two tabled
      epígrafes carrying a documented índice especial
      (:data:`_M131_EPIGRAFES_INDICE_ESPECIAL`: "721.2" transporte por
      autotaxis letra a.2, "722" transporte de mercancías letra a.4). The
      ``modelo-131-2025-modulos-pequena-dimension-ignorado-especial`` ADVISORY
      surfaces this to the operator as a non-blocking prompt (never a silent
      drop with no signal, per no-silent-under-declaration).
    * "Cuando resulte aplicable el índice corrector para empresas de pequeña
      dimensión (b.1) no se aplicará el índice corrector de exceso (b.3)" —
      when a (non-ignored) pequeña-dimensión índice applies, the índice de
      exceso is skipped for this activity.
    * "Cuando resulte aplicable el índice corrector de temporada (b.2) no se
      aplicará el índice corrector por inicio de nuevas actividades (b.4)" —
      temporada and inicio de nuevas actividades are mutually exclusive; when
      both are declared, temporada (the Anexo's own enumeration order, b.2
      before b.4) takes precedence and inicio de nuevas actividades is
      skipped. The
      ``modelo-131-2025-modulos-temporada-inicio-actividad-incompatibles``
      ADVISORY surfaces the conflicting declaration.

    A non-positive rendimiento neto minorado never receives índices
    correctores (the general estimación-objetiva principle applied uniformly
    across this engine — see the M100 agraria and M131 índice-de-exceso
    guards) and resolves to the minorado figure unchanged. This op feeds the
    same internal-only ``modulos-rendimiento-neto-modulos`` advisory-support
    casilla the índice de exceso already fed, never a filed figure standing in
    for the operator's manual casilla 01.
    """
    args = _m131_resolve_modulos_indices_generales_args(expression)
    minorado = _numeric_casilla_value(args.minorado_casilla_id, ctx)
    ctx.operand_refs.append(args.minorado_casilla_id)
    ctx.operand_casilla_refs.append(args.minorado_casilla_id)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    if minorado <= _ZERO:
        return minorado

    # b.1) Índice corrector para empresas de pequeña dimensión — first in the
    # Orden's literal enumeration order.
    pequena_dimension = _read_modulos_indice(args.pequena_dimension_casilla_id, ctx)
    aplica_pequena_dimension = pequena_dimension > _ZERO and epigrafe not in _M131_EPIGRAFES_INDICE_ESPECIAL

    rendimiento = minorado
    if aplica_pequena_dimension:
        rendimiento = rendimiento * pequena_dimension
        # b.1 excludes b.3 (índice de exceso) outright, and the Orden never
        # reaches b.2/b.4 once b.1 has been applied for this epígrafe.
        return rendimiento

    # b.2) Índice corrector de temporada — second in the Orden's literal
    # enumeration order, applied on the rendimiento rectificado by b.1 (a
    # no-op here, since b.1 did not apply) and BEFORE b.3's exceso threshold
    # check.
    temporada = _read_modulos_indice(args.temporada_casilla_id, ctx)
    if temporada > _ZERO:
        rendimiento = rendimiento * temporada

    # b.3) Índice corrector de exceso — third in the Orden's literal
    # enumeration order (b.1 -> b.2 -> b.3 -> b.4), applied on the running
    # rendimiento (already rectificado by b.2, if declared).
    if epigrafe:
        cuantia_parameter = ctx.parameters.get(args.cuantia_parameter)
        ctx.operand_refs.append(args.cuantia_parameter)
        if cuantia_parameter is not None and rendimiento > _ZERO:
            cuantia = _resolve_keyed_bracket(cuantia_parameter, key=epigrafe, filing_year=ctx.filing_year)
            if cuantia is not None and rendimiento > cuantia:
                ctx.operand_values.append(cuantia)
                indice = _resolve_scalar_parameter(
                    args.indice_exceso_parameter,
                    ctx,
                    op="m131_resolve_modulos_indices_generales",
                )
                rendimiento = cuantia + indice * (rendimiento - cuantia)

    # b.4) Índice corrector por inicio de nuevas actividades — last in the
    # Orden's literal enumeration order, applied on the b.3-rectificado
    # figure and only when b.2 (temporada) is absent (the Orden's own
    # mutual-exclusion rule).
    if temporada <= _ZERO:
        inicio_actividad = _read_modulos_indice(args.inicio_actividad_casilla_id, ctx)
        if inicio_actividad > _ZERO:
            rendimiento = rendimiento * inicio_actividad

    return rendimiento


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosPequenaDimensionIgnoradoFlagArgs:
    """Resolved registry ids for the M131 pequeña-dimensión-ignorado advisory flag."""

    epigrafe_casilla_id: CasillaId
    pequena_dimension_casilla_id: CasillaId


def _m131_resolve_modulos_pequena_dimension_ignorado_flag_args(
    expression: FormulaExpression,
) -> _M131ResolveModulosPequenaDimensionIgnoradoFlagArgs:
    op = "m131_resolve_modulos_pequena_dimension_ignorado_flag"
    if len(expression.args) != 2:
        raise RegistryValidationError(
            f"formula op {op!r} expects 2 args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "2"},
        )
    epigrafe_arg, pequena_dimension_arg = expression.args
    if epigrafe_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    if pequena_dimension_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[1] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "casilla"},
        )
    return _M131ResolveModulosPequenaDimensionIgnoradoFlagArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        pequena_dimension_casilla_id=pequena_dimension_arg.casilla_id,
    )


def evaluate_m131_resolve_modulos_pequena_dimension_ignorado_flag(
    expression: FormulaExpression,
    ctx: _EvalContext,
) -> Decimal:
    """Flag (1/0) whether a declared índice de pequeña dimensión (b.1) was ignored.

    Orden HAC/1347/2024 Anexo II, instrucción 2.3: "En ningún caso será
    aplicable el índice corrector para empresas de pequeña dimensión (b.1) a
    las actividades para las que están previstos los índices correctores
    especiales enumerados en las letras a.2), a.3), a.4) y a.5)." Resolves to
    ``Decimal('1')`` when the operator declared a positive índice de pequeña
    dimensión for an epígrafe carrying a documented índice especial
    (:data:`_M131_EPIGRAFES_INDICE_ESPECIAL`) — the exact condition
    :func:`evaluate_m131_resolve_modulos_indices_generales` uses to ignore
    the índice — never fabricating a value, only signalling the ignored
    declaration so the paired ADVISORY (via ``advisory_when_positive``) can
    surface it to the operator (no-silent-under-declaration).
    """
    args = _m131_resolve_modulos_pequena_dimension_ignorado_flag_args(expression)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    pequena_dimension = _numeric_casilla_value(args.pequena_dimension_casilla_id, ctx)
    if pequena_dimension > _ZERO and epigrafe in _M131_EPIGRAFES_INDICE_ESPECIAL:
        return Decimal("1")
    return _ZERO


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosTemporadaInicioConflictoFlagArgs:
    """Resolved registry ids for the M131 temporada/inicio-actividad conflict advisory flag."""

    temporada_casilla_id: CasillaId
    inicio_actividad_casilla_id: CasillaId


def _m131_resolve_modulos_temporada_inicio_conflicto_flag_args(
    expression: FormulaExpression,
) -> _M131ResolveModulosTemporadaInicioConflictoFlagArgs:
    op = "m131_resolve_modulos_temporada_inicio_conflicto_flag"
    if len(expression.args) != 2:
        raise RegistryValidationError(
            f"formula op {op!r} expects 2 args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "2"},
        )
    temporada_arg, inicio_actividad_arg = expression.args
    if temporada_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    if inicio_actividad_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[1] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "casilla"},
        )
    return _M131ResolveModulosTemporadaInicioConflictoFlagArgs(
        temporada_casilla_id=temporada_arg.casilla_id,
        inicio_actividad_casilla_id=inicio_actividad_arg.casilla_id,
    )


def evaluate_m131_resolve_modulos_temporada_inicio_conflicto_flag(
    expression: FormulaExpression,
    ctx: _EvalContext,
) -> Decimal:
    """Flag (1/0) whether both índice de temporada (b.2) and índice de inicio (b.4) were declared.

    Orden HAC/1347/2024 Anexo II, instrucción 2.3: "Cuando resulte aplicable
    el índice corrector de temporada (b.2) no se aplicará el índice corrector
    por inicio de nuevas actividades (b.4)." Resolves to ``Decimal('1')`` when
    both índices are positive — the mutually-exclusive declaration
    :func:`evaluate_m131_resolve_modulos_indices_generales` resolves by
    preferring temporada (the Anexo's own enumeration order) and skipping
    inicio de nuevas actividades — so the paired ADVISORY (via
    ``advisory_when_positive``) can surface the conflicting declaration to the
    operator.
    """
    args = _m131_resolve_modulos_temporada_inicio_conflicto_flag_args(expression)
    temporada = _numeric_casilla_value(args.temporada_casilla_id, ctx)
    inicio_actividad = _numeric_casilla_value(args.inicio_actividad_casilla_id, ctx)
    if temporada > _ZERO and inicio_actividad > _ZERO:
        return Decimal("1")
    return _ZERO
