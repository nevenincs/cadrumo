"""Modelo 210 rate resolution helpers."""

from __future__ import annotations

from decimal import Decimal

from ...core.i18n import tr
from ...domain.calculations.registry import ConvenioRateRow, RegistrySnapshot
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)


def resolve_m210_rate(
    profile: TaxpayerProfile,
    tipo_renta: str,
    year: int,
    snapshot: RegistrySnapshot,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the M210 rate for (profile, tipo_renta, year)."""
    baseline_param = None
    convenio_param = None
    for parameter in snapshot.revision.parameters:
        if parameter.id == "m210-tipo-gravamen-2025":
            baseline_param = parameter
        elif parameter.id == "m210-convenio-rates":
            convenio_param = parameter

    if baseline_param is None:
        return None, []

    baseline_rate: Decimal | None = None
    for entry in baseline_param.keyed_brackets:
        if (
            entry.key == tipo_renta
            and entry.valid_from.year <= year
            and (entry.valid_to is None or entry.valid_to.year >= year)
        ):
            try:
                baseline_rate = Decimal(entry.value)
            except (ArithmeticError, ValueError):
                return None, []
            break

    treaty_country = profile.country_of_fiscal_residence
    if treaty_country is None:
        if baseline_rate is None:
            baseline_legal_refs = tuple(str(r) for r in baseline_param.legal_refs)
            baseline_source_refs = tuple(str(r) for r in baseline_param.source_refs)
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=(
                    f"M210 baseline tipo_renta={tipo_renta!r} year={year} is "
                    "deferred to a future Phase per corpus-blocking; "
                    "predicate 'm210-baseline-tipo-deferred' fires"
                ),
                next_action=tr(
                    "application.modelo.findings.m210_baseline_tipo_deferred.next_action",
                    tipo_renta=tipo_renta,
                ),
                legal_refs=baseline_legal_refs,
                source_refs=baseline_source_refs,
            )
            return None, [finding]
        return baseline_rate, []

    cc = treaty_country.upper()

    convenio_lookup: dict[tuple[str, str], ConvenioRateRow] = {}
    if convenio_param is not None:
        for row in convenio_param.convenio_rates:
            if row.valid_from.year <= year and (row.valid_to is None or row.valid_to.year >= year):
                convenio_lookup[(row.country_code, row.tipo_renta)] = row

    matched_row = convenio_lookup.get((cc, tipo_renta))
    legal_refs: tuple[str, ...] = tuple(str(r) for r in convenio_param.legal_refs) if convenio_param is not None else ()
    source_refs: tuple[str, ...] = (
        tuple(str(r) for r in convenio_param.source_refs) if convenio_param is not None else ()
    )

    if matched_row is None:
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message=(
                f"M210 Convenio rate row missing for country={cc!r} "
                f"tipo_renta={tipo_renta!r} year={year}; "
                "predicate 'm210-convenio-rate-missing' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_missing.next_action",
                cc=cc,
                tipo_renta=tipo_renta,
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    if matched_row.rate == "NOT_YET_AUTHORED":
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message=(
                f"M210 Convenio rate row for country={cc!r} "
                f"tipo_renta={tipo_renta!r} year={year} carries the "
                "NOT_YET_AUTHORED placeholder; predicate "
                "'m210-convenio-rate-not-yet-authored' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_not_yet_authored.next_action",
                cc=cc,
                tipo_renta=tipo_renta,
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    return Decimal(matched_row.rate), []
