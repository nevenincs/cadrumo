"""Modelo 210 IRNR treaty-rate resolution helpers.

The registry formula runtime computes the filing values and emits sentinel
rates when a Modelo 210 rate cannot be applied directly. This application helper
reads the same ``m210-tipo-gravamen-2025`` and ``m210-convenio-rates`` parameter
rows from a :class:`~aeat.domain.calculations.registry.RegistrySnapshot`, selects
the treaty country from :class:`~aeat.domain.deadlines.TaxpayerProfile`, and
returns either a scalar IRNR rate or blocking
:class:`~aeat.domain.modelos.ModeloVerificationFinding` records for deferred
baseline coverage or missing treaty rows.

``DOMESTIC_TARIFF`` rows are not scalar rates. They delegate to the live
base-aware tariff path in the registry runtime, so this helper returns
``(None, [])`` for that branch instead of inventing an effective rate without the
tax base.

See Also:
    :mod:`aeat.domain.calculations.registry._formula_runtime`
        Formula-runtime implementation of ``m210_resolve_rate`` and the M210
        sentinel values this application layer rewrites into findings.
    :func:`aeat.application.modelo._verification_actions.verify_modelo_revision`
        Verification path that replays this resolver for Modelo 210 observations.
    :mod:`aeat.application.calculations.tests.test_modelo_210_irnr_continuity`
        Cross-renta enrollment coverage for the registry-backed M210 engine.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.i18n import tr
from ...domain.calculations.registry import ConvenioRateRow, RegistrySnapshot
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry._schema_formula import ParameterDefinition

_M210_DOMESTIC_TARIFF_RATE = "DOMESTIC_TARIFF"


def _m210_blocking_finding(
    *,
    message: str,
    next_action: str,
    legal_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
) -> ModeloVerificationFinding:
    """Build a BLOCKING_RULE M210 rate finding with the shared severity/kind.

    The returned :class:`~aeat.domain.modelos.ModeloVerificationFinding` is the
    application-facing companion to the formula-runtime sentinel: callers surface
    it to the operator instead of letting an unavailable M210 rate silently
    produce filing output.
    """
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=message,
        next_action=next_action,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _resolve_baseline_rate(
    baseline_param: ParameterDefinition,
    tipo_renta: str,
    year: int,
) -> tuple[Decimal | None, bool]:
    """Find the baseline rate for ``(tipo_renta, year)``.

    Returns ``(rate, ok)``: ``ok`` is False only when a matching bracket was
    found but its value failed to parse as a :class:`~decimal.Decimal` (the
    caller then short-circuits to ``(None, [])``). A simply-absent bracket
    returns ``(None, True)``.
    """
    for entry in baseline_param.keyed_brackets:
        if (
            entry.key == tipo_renta
            and entry.valid_from.year <= year
            and (entry.valid_to is None or entry.valid_to.year >= year)
        ):
            try:
                return Decimal(entry.value), True
            except (ArithmeticError, ValueError):
                return None, False
    return None, True


def _resolve_convenio_rate(
    convenio_param: ParameterDefinition | None,
    *,
    country_code: str,
    tipo_renta: str,
    year: int,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the Convenio (treaty) override rate for a treaty-country profile.

    Emits the ``m210-convenio-rate-missing`` BLOCKING finding when no row exists.
    Rows whose rate is ``DOMESTIC_TARIFF`` intentionally return ``(None, [])``
    because the base-aware tariff branch in the registry runtime remains the
    calculation authority.
    """
    convenio_lookup: dict[tuple[str, str], ConvenioRateRow] = {}
    if convenio_param is not None:
        for row in convenio_param.convenio_rates:
            if row.valid_from.year <= year and (row.valid_to is None or row.valid_to.year >= year):
                convenio_lookup[(row.country_code, row.tipo_renta)] = row

    matched_row = convenio_lookup.get((country_code, tipo_renta))
    legal_refs: tuple[str, ...] = tuple(str(r) for r in convenio_param.legal_refs) if convenio_param is not None else ()
    source_refs: tuple[str, ...] = (
        tuple(str(r) for r in convenio_param.source_refs) if convenio_param is not None else ()
    )

    if matched_row is None:
        finding = _m210_blocking_finding(
            message=(
                f"M210 Convenio rate row missing for country={country_code!r} "
                f"tipo_renta={tipo_renta!r} year={year}; "
                "predicate 'm210-convenio-rate-missing' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_missing.next_action",
                cc=country_code,
                tipo_renta=tipo_renta,
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    if matched_row.rate == _M210_DOMESTIC_TARIFF_RATE:
        return None, []

    return Decimal(matched_row.rate), []


def _has_live_pension_tariff(snapshot: RegistrySnapshot, year: int) -> bool:
    """Return whether the snapshot contains an applicable M210 pension tariff table."""
    for parameter in snapshot.revision.parameters:
        if parameter.id != "m210-pension-tarifa-2025" or parameter.data_type != "bracket_table":
            continue
        return any(
            bracket.valid_from.year <= year and (bracket.valid_to is None or bracket.valid_to.year >= year)
            for bracket in parameter.brackets
        )
    return False


def resolve_m210_rate(
    profile: TaxpayerProfile,
    tipo_renta: str,
    year: int,
    snapshot: RegistrySnapshot,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the M210 rate for (profile, tipo_renta, year).

    The :class:`~aeat.domain.calculations.registry.RegistrySnapshot` supplies the
    ``m210-tipo-gravamen-2025`` and ``m210-convenio-rates`` parameter rows; the
    :class:`~aeat.domain.deadlines.TaxpayerProfile` supplies
    ``country_of_fiscal_residence`` for treaty lookup. Returns ``(rate,
    findings)`` where ``findings`` contains blocking
    :class:`~aeat.domain.modelos.ModeloVerificationFinding` records when a
    required rate is deferred or unavailable.

    A profile with no treaty country uses the baseline table. A profile with a
    treaty country must match a Convenio row for ``(country, tipo_renta)`` unless
    the row explicitly delegates back to the domestic tariff. The resolver
    returns no scalar rate for live pension tariffs because those depend on the
    actual base amount and are computed by the formula runtime.

    See Also:
        :func:`aeat.domain.calculations.registry._formula_runtime._evaluate_m210_resolve_rate`
        :class:`aeat.domain.calculations.registry.ConvenioRateRow`
        :class:`aeat.domain.deadlines.TaxpayerProfile`
    """
    baseline_param = None
    convenio_param = None
    for parameter in snapshot.revision.parameters:
        if parameter.id == "m210-tipo-gravamen-2025":
            baseline_param = parameter
        elif parameter.id == "m210-convenio-rates":
            convenio_param = parameter

    if baseline_param is None:
        return None, []

    baseline_rate, baseline_ok = _resolve_baseline_rate(baseline_param, tipo_renta, year)
    if not baseline_ok:
        return None, []

    treaty_country = profile.country_of_fiscal_residence
    if treaty_country is None:
        if baseline_rate is None:
            if tipo_renta == "pension" and _has_live_pension_tariff(snapshot, year):
                return None, []
            finding = _m210_blocking_finding(
                message=(
                    f"M210 baseline tipo_renta={tipo_renta!r} year={year} is "
                    "deferred to a future Phase per corpus-blocking; "
                    "predicate 'm210-baseline-tipo-deferred' fires"
                ),
                next_action=tr(
                    "application.modelo.findings.m210_baseline_tipo_deferred.next_action",
                    tipo_renta=tipo_renta,
                ),
                legal_refs=tuple(str(r) for r in baseline_param.legal_refs),
                source_refs=tuple(str(r) for r in baseline_param.source_refs),
            )
            return None, [finding]
        return baseline_rate, []

    return _resolve_convenio_rate(
        convenio_param,
        country_code=treaty_country.upper(),
        tipo_renta=tipo_renta,
        year=year,
    )
