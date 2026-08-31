"""IRNR / Modelo 210 formula-op evaluators for the registry runtime.

Extracted from :mod:`~domain.calculations.registry._formula_runtime` to
keep that module under its size budget (`aeat-architecture-boundaries`,
`aeat-architecture-boundaries`). Holds the two IRNR-specific formula
ops -- ``irnr_resolve_tipo_gravamen`` and ``m210_resolve_base_imponible`` --
and their private argument-resolution and rate-computation helpers. Dispatch
still lives in :func:`~domain.calculations.registry._formula_runtime._evaluate_with_ctx`,
which imports this module at package level and calls
:func:`evaluate_irnr_resolve_tipo_gravamen` /
:func:`evaluate_m210_resolve_base_imponible` exactly as it calls the sibling
:mod:`~domain.calculations.registry._formula_runtime_ops` helpers. The
shared error types, the unresolved-outcome reason enum, and the generic
numeric-casilla-value accessor live in ``_formula_runtime_ops`` (not in
``_formula_runtime`` itself) so this module can depend on them without a
runtime import cycle back into the dispatcher module.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime`
        Owns the dispatcher and :class:`_EvalContext`.
    :mod:`~domain.calculations.registry._formula_runtime_ops`
        Owns the shared unresolved-formula error types,
        :class:`RegistryUnresolvedOutcomeReason`, and
        :func:`~domain.calculations.registry._formula_runtime_ops.numeric_casilla_value`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, NoReturn

from ....core.casilla_id import CasillaId
from ....core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ...contribuyente.renta_codes import UE_EEA_COUNTRY_CODES
from .convenio import ConvenioOverride
from .errors import RegistryValidationError
from .formula_runtime_ops import (
    RegistryUnresolvedOutcomeReason,
    UnresolvedFormulaOutcomeError,
)
from .formula_runtime_ops import numeric_casilla_value as _numeric_casilla_value
from .formula_runtime_ops import (
    resolve_bracket as _resolve_bracket,
)
from .formula_runtime_ops import (
    resolve_keyed_bracket as _resolve_keyed_bracket,
)
from .formula_runtime_ops import (
    resolve_scalar_parameter as _resolve_scalar_parameter,
)
from .ids import BindingId, ParameterId
from .schema_formula import FormulaExpression

if TYPE_CHECKING:
    from .formula_runtime import EvalContext

    _EvalContext = EvalContext

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class _IrnrResolveTipoGravamenArgs:
    """Resolved registry ids for the M210 IRNR rate dispatcher."""

    tipo_casilla_id: CasillaId
    baseline_parameter: ParameterId
    country_binding: BindingId
    base_casilla_id: CasillaId
    pension_tariff_parameter: ParameterId


@dataclass(frozen=True, slots=True)
class _M210ResolveBaseArgs:
    """Resolved registry ids for the M210 base-imponible dispatcher."""

    tipo_casilla_id: CasillaId
    gross_casilla_id: CasillaId
    deductible_expenses_casilla_id: CasillaId
    country_binding: BindingId
    catastral_value_casilla_id: CasillaId
    imputation_coefficient_casilla_id: CasillaId
    imputation_days_casilla_id: CasillaId
    acquisition_value_casilla_id: CasillaId
    administrative_value_casilla_id: CasillaId
    recent_rate_parameter: ParameterId
    old_rate_parameter: ParameterId
    no_catastral_fraction_parameter: ParameterId


def evaluate_irnr_resolve_tipo_gravamen(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the IRNR tipo de gravamen rate, applying any treaty override.

    The single tipo-de-gravamen resolution path for every IRNR consumer
    (Modelo 210 today, the retenciones-a-no-residentes modelos when they
    land). It resolves the TRLIRNR domestic baseline and, when the profile
    declares a fiscal-residence country, consults the cross-cutting
    :class:`~._convenio.ConvenioAuthority` projected onto the snapshot. On a
    matched override it branches on the typed
    :class:`~core.ConvenioOverrideKind`:

    * ``flat`` replaces the domestic rate outright,
    * ``ceiling`` applies ``min(domestic, treaty)`` so "más favorable" is
      computed rather than assumed,
    * ``allocation_domestic_tariff`` delegates the amount to the domestic
      tariff (the Art. 25.1.b progressive pension tariff for ``pension``, the
      baseline rate otherwise),
    * ``exempt`` drives the source-state rate to zero.

    A declared treaty country with no override row yields a typed unresolved
    outcome (``no-silent-under-declaration``); the modelo verification workflow
    converts it into a finding post-engine.
    """
    args = _irnr_resolve_tipo_gravamen_args(expression)
    tipo_renta = ctx.text_values.get(args.tipo_casilla_id, "")
    ctx.operand_refs.append(args.tipo_casilla_id)
    ctx.operand_casilla_refs.append(args.tipo_casilla_id)
    if not tipo_renta:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country="",
        )

    baseline_param = ctx.parameters.get(args.baseline_parameter)
    ctx.operand_refs.extend((args.baseline_parameter, args.country_binding))
    baseline_rate = _resolve_keyed_bracket(baseline_param, key=tipo_renta, filing_year=ctx.filing_year)
    country = ctx.enum_binding_values.get(args.country_binding) or ""
    override = _resolve_convenio_override(ctx, country=country, tipo_renta=tipo_renta)

    if tipo_renta == TipoRentaIrnr.PENSION.value:
        rate = _irnr_pension_effective_rate(args, ctx, override=override, country=country)
        if rate is None:
            _raise_m210_unresolved_outcome(
                RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
                ctx=ctx,
                args=args,
                tipo_renta=tipo_renta,
                country=country,
            )
        ctx.operand_values.append(rate)
        return rate

    if not country:
        if baseline_rate is None:
            _raise_m210_unresolved_outcome(
                RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
                ctx=ctx,
                args=args,
                tipo_renta=tipo_renta,
                country=country,
            )
        ctx.operand_values.append(baseline_rate)
        return baseline_rate

    if override is None:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country=country,
        )
    rate = _apply_convenio_override(override, baseline_rate=baseline_rate)
    if rate is None:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country=country,
        )
    ctx.operand_values.append(rate)
    return rate


def _raise_m210_unresolved_outcome(
    reason: RegistryUnresolvedOutcomeReason,
    *,
    ctx: _EvalContext,
    args: _IrnrResolveTipoGravamenArgs,
    tipo_renta: str,
    country: str,
) -> NoReturn:
    raise UnresolvedFormulaOutcomeError(
        reason,
        context={
            "tipo_renta": tipo_renta,
            "country": country,
            "filing_year": str(ctx.filing_year),
            "baseline_parameter": args.baseline_parameter,
            "country_binding": args.country_binding,
        },
    )


def _irnr_resolve_tipo_gravamen_args(expression: FormulaExpression) -> _IrnrResolveTipoGravamenArgs:
    op = "irnr_resolve_tipo_gravamen"
    if len(expression.args) != 5:
        raise RegistryValidationError(f"formula op {op!r} expects 5 args, got {len(expression.args)}")
    tipo_arg, base_arg, baseline_arg, pension_tariff_arg, country_arg = expression.args
    if tipo_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if base_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if baseline_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a parameter leaf")
    if pension_tariff_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a parameter leaf")
    if country_arg.binding is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a binding leaf")
    return _IrnrResolveTipoGravamenArgs(
        tipo_casilla_id=tipo_arg.casilla_id,
        baseline_parameter=baseline_arg.parameter,
        country_binding=country_arg.binding,
        base_casilla_id=base_arg.casilla_id,
        pension_tariff_parameter=pension_tariff_arg.parameter,
    )


def _resolve_convenio_override(
    ctx: _EvalContext,
    *,
    country: str,
    tipo_renta: str,
) -> ConvenioOverride | None:
    """Resolve the treaty override for the declared country + income type, or None.

    Hydrates the free-text ``tipo_renta`` casilla value to the closed
    :class:`~core.TipoRentaIrnr` enum at this boundary; an unrecognised
    value carries no treaty override (the domestic baseline stands).
    """
    if not country:
        return None
    try:
        tipo_enum = TipoRentaIrnr(tipo_renta)
    except ValueError:
        return None
    return ctx.convenio.resolve(country.upper(), tipo_enum, ctx.filing_year)


def _apply_convenio_override(override: ConvenioOverride, *, baseline_rate: Decimal | None) -> Decimal | None:
    """Apply a non-pension treaty override to the domestic baseline rate."""
    kind = override.kind
    if kind is ConvenioOverrideKind.EXEMPT:
        return _ZERO
    if kind is ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF:
        return baseline_rate
    if override.rate is None:
        return None
    if kind is ConvenioOverrideKind.FLAT:
        return override.rate
    # CEILING: min(domestic, treaty) — "más favorable" computed, not assumed.
    if baseline_rate is None:
        return None
    return min(baseline_rate, override.rate)


def _irnr_pension_effective_rate(
    args: _IrnrResolveTipoGravamenArgs,
    ctx: _EvalContext,
    *,
    override: ConvenioOverride | None,
    country: str,
) -> Decimal | None:
    if country:
        if override is None:
            return None
        if override.kind is ConvenioOverrideKind.EXEMPT:
            return _ZERO
        if override.kind is ConvenioOverrideKind.FLAT and override.rate is not None:
            return override.rate
        if override.kind is ConvenioOverrideKind.CEILING and override.rate is not None:
            effective = _m210_effective_rate_from_tariff(args.base_casilla_id, args.pension_tariff_parameter, ctx)
            return min(effective, override.rate)
        # ALLOCATION_DOMESTIC_TARIFF delegates the amount to the domestic tariff.
    return _m210_effective_rate_from_tariff(args.base_casilla_id, args.pension_tariff_parameter, ctx)


def _m210_effective_rate_from_tariff(
    base_casilla_id: CasillaId,
    tariff_parameter_id: ParameterId,
    ctx: _EvalContext,
) -> Decimal:
    base = _numeric_casilla_value(base_casilla_id, ctx)
    tariff_parameter = ctx.parameters.get(tariff_parameter_id)
    if tariff_parameter is None:
        raise RegistryValidationError(
            f"parameter {tariff_parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": tariff_parameter_id},
        )
    if tariff_parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {tariff_parameter_id!r} must declare data_type='bracket_table' "
            "to be used by M210 pension tariff resolution",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": tariff_parameter_id, "op": "irnr_resolve_tipo_gravamen"},
        )
    ctx.operand_refs.append(tariff_parameter_id)
    cuota = _resolve_bracket(tariff_parameter, base, ctx.date_context)
    ctx.operand_values.append(cuota)
    if base == _ZERO:
        return _ZERO
    return cuota / base


def evaluate_m210_resolve_base_imponible(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve M210 base imponible, including Art. 24.6 and Art. 13.1.h branches.

    Non-imputed Art. 24.1 tipos start from ``rendimientos_integros``. Art.
    24.6 permits deducting linked expenses when the filer is in the EU/EEA
    path, represented by ``tipo_renta='ue_residente'`` or an EU/EEA
    ``country_of_fiscal_residence`` binding. For ``inmobiliaria``, the
    operator applies the LIRPF Art. 85 imputation mechanics reached through
    TRLIRNR Arts. 13.1.h and 24.5; own-use imputation admits no expenses.
    """
    args = _m210_resolve_base_args(expression)
    tipo_renta = ctx.text_values.get(args.tipo_casilla_id, "")
    ctx.operand_refs.append(args.tipo_casilla_id)
    ctx.operand_casilla_refs.append(args.tipo_casilla_id)
    country = (ctx.enum_binding_values.get(args.country_binding) or "").upper()
    ctx.operand_refs.append(args.country_binding)
    deductible_expenses = _numeric_casilla_value(args.deductible_expenses_casilla_id, ctx)
    if deductible_expenses < _ZERO:
        raise RegistryValidationError(
            "M210 gastos_deducibles must be non-negative",
            translated_message="errors.calc.m210_gastos_deducibles_negative",
            context={"casilla_id": args.deductible_expenses_casilla_id, "value": str(deductible_expenses)},
        )
    if tipo_renta != "inmobiliaria":
        gross = _numeric_casilla_value(args.gross_casilla_id, ctx)
        if deductible_expenses == _ZERO:
            return gross
        if not _m210_allows_art_24_6_expenses(tipo_renta=tipo_renta, country_code=country):
            raise RegistryValidationError(
                "M210 gastos_deducibles require the EU/EEA Art. 24.6 path",
                translated_message="errors.calc.m210_gastos_deducibles_not_allowed",
                context={
                    "casilla_id": args.deductible_expenses_casilla_id,
                    "tipo_renta": tipo_renta,
                    "country_of_fiscal_residence": country,
                },
            )
        return gross - deductible_expenses
    if deductible_expenses != _ZERO:
        raise RegistryValidationError(
            "M210 imputed real-estate own-use base cannot deduct gastos_deducibles",
            translated_message="errors.calc.m210_gastos_deducibles_not_allowed",
            context={
                "casilla_id": args.deductible_expenses_casilla_id,
                "tipo_renta": tipo_renta,
                "country_of_fiscal_residence": country,
            },
        )

    days = _m210_imputation_days(args.imputation_days_casilla_id, ctx)
    days_fraction = days / Decimal(_m210_days_in_filing_year(ctx.filing_year))
    catastral_value = _numeric_casilla_value(args.catastral_value_casilla_id, ctx)
    if catastral_value > _ZERO:
        recent_rate = _resolve_scalar_parameter(
            args.recent_rate_parameter,
            ctx,
            op="m210_resolve_base_imponible",
        )
        old_rate = _resolve_scalar_parameter(
            args.old_rate_parameter,
            ctx,
            op="m210_resolve_base_imponible",
        )
        coefficient = _numeric_casilla_value(args.imputation_coefficient_casilla_id, ctx)
        if coefficient not in {recent_rate, old_rate}:
            raise RegistryValidationError(
                "M210 inmobiliaria coefficient must be one of the registry-authored "
                f"LIRPF art.85 rates ({recent_rate} or {old_rate}); got {coefficient}",
                translated_message="errors.calc.m210_imputation_coefficient_invalid",
                context={
                    "casilla_id": args.imputation_coefficient_casilla_id,
                    "value": str(coefficient),
                    "allowed_values": f"{recent_rate},{old_rate}",
                },
            )
        return catastral_value * coefficient * days_fraction

    acquisition_value = _numeric_casilla_value(args.acquisition_value_casilla_id, ctx)
    administrative_value = _numeric_casilla_value(args.administrative_value_casilla_id, ctx)
    substitute_value = max(acquisition_value, administrative_value)
    if substitute_value <= _ZERO:
        raise RegistryValidationError(
            "M210 inmobiliaria without cadastral value requires a positive acquisition or administrative checked value",
            translated_message="errors.calc.m210_imputation_no_catastral_value_missing",
            context={
                "acquisition_casilla_id": args.acquisition_value_casilla_id,
                "administrative_casilla_id": args.administrative_value_casilla_id,
            },
        )
    no_catastral_fraction = _resolve_scalar_parameter(
        args.no_catastral_fraction_parameter,
        ctx,
        op="m210_resolve_base_imponible",
    )
    recent_rate = _resolve_scalar_parameter(
        args.recent_rate_parameter,
        ctx,
        op="m210_resolve_base_imponible",
    )
    return substitute_value * no_catastral_fraction * recent_rate * days_fraction


def _m210_resolve_base_args(expression: FormulaExpression) -> _M210ResolveBaseArgs:
    op = "m210_resolve_base_imponible"
    if len(expression.args) != 12:
        raise RegistryValidationError(f"formula op {op!r} expects 12 args, got {len(expression.args)}")
    (
        tipo_arg,
        gross_arg,
        deductible_expenses_arg,
        country_arg,
        catastral_value_arg,
        imputation_coefficient_arg,
        imputation_days_arg,
        acquisition_value_arg,
        administrative_value_arg,
        recent_rate_arg,
        old_rate_arg,
        no_catastral_fraction_arg,
    ) = expression.args
    if tipo_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if gross_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if deductible_expenses_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a casilla leaf")
    if country_arg.binding is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a binding leaf")
    if catastral_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a casilla leaf")
    if imputation_coefficient_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[5] to be a casilla leaf")
    if imputation_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[6] to be a casilla leaf")
    if acquisition_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[7] to be a casilla leaf")
    if administrative_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[8] to be a casilla leaf")
    if recent_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[9] to be a parameter leaf")
    if old_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[10] to be a parameter leaf")
    if no_catastral_fraction_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[11] to be a parameter leaf")
    return _M210ResolveBaseArgs(
        tipo_casilla_id=tipo_arg.casilla_id,
        gross_casilla_id=gross_arg.casilla_id,
        deductible_expenses_casilla_id=deductible_expenses_arg.casilla_id,
        country_binding=country_arg.binding,
        catastral_value_casilla_id=catastral_value_arg.casilla_id,
        imputation_coefficient_casilla_id=imputation_coefficient_arg.casilla_id,
        imputation_days_casilla_id=imputation_days_arg.casilla_id,
        acquisition_value_casilla_id=acquisition_value_arg.casilla_id,
        administrative_value_casilla_id=administrative_value_arg.casilla_id,
        recent_rate_parameter=recent_rate_arg.parameter,
        old_rate_parameter=old_rate_arg.parameter,
        no_catastral_fraction_parameter=no_catastral_fraction_arg.parameter,
    )


def _m210_allows_art_24_6_expenses(*, tipo_renta: str, country_code: str) -> bool:
    return tipo_renta == "ue_residente" or country_code in UE_EEA_COUNTRY_CODES


def _m210_imputation_days(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    days = _numeric_casilla_value(casilla_id, ctx)
    year_days = Decimal(_m210_days_in_filing_year(ctx.filing_year))
    if days != days.to_integral_value() or days <= _ZERO or days > year_days:
        raise RegistryValidationError(
            f"M210 inmobiliaria imputation days must be an integer in [1, {year_days}]",
            translated_message="errors.calc.m210_imputation_days_invalid",
            context={"casilla_id": casilla_id, "value": str(days), "max_days": str(year_days)},
        )
    return days


def _m210_days_in_filing_year(year: int) -> int:
    if year <= 0:
        raise RegistryValidationError(
            "m210_resolve_base_imponible requires a non-zero filing_year in evaluation context",
            translated_message="errors.calc.m210_imputation_no_filing_year",
        )
    return (date(year, 12, 31) - date(year, 1, 1)).days + 1
