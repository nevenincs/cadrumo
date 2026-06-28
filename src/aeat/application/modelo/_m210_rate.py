"""Modelo 210 treaty-rate resolution helpers.

The resolver reads baseline and Convenio rate parameters from the
:class:`RegistrySnapshot`, selects the treaty country from the
:class:`TaxpayerProfile`, and returns either the resolved IRNR rate or
blocking :class:`ModeloVerificationFinding` records for deferred baseline
coverage, missing treaty rows, or ``NOT_YET_AUTHORED`` convenio entries.
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
    """Build a BLOCKING_RULE M210 rate finding with the shared severity/kind."""
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

    Emits the ``m210-convenio-rate-missing`` BLOCKING finding when no row exists
    and the ``m210-convenio-rate-not-yet-authored`` BLOCKING finding when the row
    carries the ``NOT_YET_AUTHORED`` placeholder.
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

    if matched_row.rate == "NOT_YET_AUTHORED":
        finding = _m210_blocking_finding(
            message=(
                f"M210 Convenio rate row for country={country_code!r} "
                f"tipo_renta={tipo_renta!r} year={year} carries the "
                "NOT_YET_AUTHORED placeholder; predicate "
                "'m210-convenio-rate-not-yet-authored' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_not_yet_authored.next_action",
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

    The :class:`RegistrySnapshot` supplies the ``m210-tipo-gravamen-2025`` and
    ``m210-convenio-rates`` parameter rows; the :class:`TaxpayerProfile`
    supplies ``country_of_fiscal_residence`` for treaty lookup. Returns
    ``(rate, findings)`` where ``findings`` contains blocking
    :class:`ModeloVerificationFinding` records when a required rate is deferred
    or unavailable.
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
