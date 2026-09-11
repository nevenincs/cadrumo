"""Resolve the Modelo 210 rate through selected registry declarations.

The application boundary only coordinates generic formula metadata, typed
parameter lookup, and the shared treaty-fact resolver.  Rate tables, income
selection, applicability, and legal provenance remain registry-owned.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.decimal.constants import ZERO
from ...core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ._m210_convenio_facts import resolve_m210_convenio_override

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
    from ...domain.calculations.registry.schema_formula import ParameterDefinition
    from ...domain.deadlines.models import TaxpayerProfile


def _rate_finding(
    *,
    casilla_id: CasillaId | None,
    reason_code: str,
    message_facts: dict[str, str | int],
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build the application finding for an unavailable selected rate."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.m210_rate_unavailable",
        message_facts={"reason_code": reason_code, **message_facts},
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _selected_rate_parameters(
    snapshot: RegistrySnapshot,
    *,
    year: int,
) -> tuple[ParameterDefinition, ParameterDefinition]:
    """Read rate-parameter identities from the selected formula declaration."""
    report = RegistryQueryService(bundled_authority()).formulas_for_scope(
        snapshot.modelo.id,
        filing_year=year,
        period=snapshot.period,
    )
    formula = next(
        (row for row in report.rows if row.expression.get("op") == "irnr_resolve_tipo_gravamen"),
        None,
    )
    if formula is None or len(formula.input_parameters) < 2:
        raise LookupError("selected M210 registry has no complete rate formula declaration")

    parameters = {parameter.id: parameter for parameter in snapshot.revision.parameters}
    baseline = parameters.get(formula.input_parameters[0])
    tariff = parameters.get(formula.input_parameters[1])
    if baseline is None or tariff is None:
        raise LookupError("selected M210 rate formula references an unavailable parameter")
    return baseline, tariff


def _rate_from_parameter(
    parameter: ParameterDefinition,
    *,
    tipo_renta: str,
    year: int,
) -> tuple[Decimal | None, bool]:
    """Return a dated keyed rate and whether its payload was parseable."""
    for entry in parameter.keyed_brackets:
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


def _tariff_declared(parameter: ParameterDefinition, *, year: int) -> bool:
    """Report whether a dated bracket tariff is present in the selected revision."""
    if parameter.data_type != "bracket_table":
        return False
    return any(
        bracket.valid_from.year <= year and (bracket.valid_to is None or bracket.valid_to.year >= year)
        for bracket in parameter.brackets
    )


def _treaty_rate(
    *,
    baseline: ParameterDefinition,
    country_code: str,
    tipo_renta: str,
    year: int,
    devengo_date: date,
    baseline_rate: Decimal | None,
    casilla_id: CasillaId | None,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the shared dated treaty fact and apply its typed result."""
    try:
        income_kind = TipoRentaIrnr(tipo_renta)
    except ValueError:
        income_kind = None

    override = (
        resolve_m210_convenio_override(
            country_code=country_code,
            tipo_renta=income_kind,
            devengo_date=devengo_date,
        )
        if income_kind is not None
        else None
    )
    legal_refs: tuple[LegalRefId, ...] = tuple(baseline.legal_refs)
    source_refs: tuple[SourceRefId, ...] = tuple(baseline.source_refs)

    if override is None:
        return None, [
            _rate_finding(
                casilla_id=casilla_id,
                reason_code="convenio_rate_missing",
                message_facts={
                    "country_code": country_code,
                    "tipo_renta_code": tipo_renta,
                    "filing_year": year,
                },
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        ]
    if override.kind is ConvenioOverrideKind.EXEMPT:
        return ZERO, []
    if override.kind is ConvenioOverrideKind.FLAT and override.rate is not None:
        return override.rate, []
    if override.kind is ConvenioOverrideKind.CEILING and override.rate is not None:
        if baseline_rate is None:
            return None, []
        return min(baseline_rate, override.rate), []
    # Base-dependent treaty branches remain owned by the registry formula runtime.
    return None, []


# fact-relocation: M210 rate selection and convenio applicability are resolved through generic registry/fact queries; authored authority publication remains external.
def resolve_m210_rate(
    profile: TaxpayerProfile,
    tipo_renta: str,
    year: int,
    snapshot: RegistrySnapshot,
    *,
    devengo_date: date,
    casilla_id: CasillaId | None = None,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the scalar rate or return a typed application finding."""
    baseline, tariff = _selected_rate_parameters(snapshot, year=year)
    baseline_rate, parseable = _rate_from_parameter(baseline, tipo_renta=tipo_renta, year=year)
    if not parseable:
        raise ValueError("selected M210 rate parameter contains a non-decimal value")

    treaty_country = profile.country_of_fiscal_residence
    if treaty_country is not None:
        return _treaty_rate(
            baseline=baseline,
            country_code=treaty_country.upper(),
            tipo_renta=tipo_renta,
            year=year,
            devengo_date=devengo_date,
            baseline_rate=baseline_rate,
            casilla_id=casilla_id,
        )

    if baseline_rate is not None:
        return baseline_rate, []
    if tipo_renta == TipoRentaIrnr.PENSION.value and _tariff_declared(tariff, year=year):
        return None, []
    return None, [
        _rate_finding(
            casilla_id=casilla_id,
            reason_code="baseline_rate_unavailable",
            message_facts={"tipo_renta_code": tipo_renta, "filing_year": year},
            legal_refs=tuple(baseline.legal_refs),
            source_refs=tuple(baseline.source_refs),
        ),
    ]
