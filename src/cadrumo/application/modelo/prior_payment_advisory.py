"""Calculate-path advisories around the Modelo 130 prior-payment carry.

Modelo 130 is cumulative from the start of the ejercicio, and its prior-payment
casilla carries the positive part of each same-ejercicio prior trimestre's
result, minored by that trimestre's minoración (RD 439/2007 art. 110). This
module does not compute the carry. It raises two non-blocking advisories around
it, with every casilla identity read from the dated
``m130-prior-payment-verification-mapping`` declaration:

* ``prior_payment_not_deducted``: a non-first trimestre with positive cumulative
  income still carries a zero prior payment although a prior trimestre was
  filed, so the carry could not populate.
* ``prior_payment_minoracion_not_captured``: a carried prior filing declares its
  positive part but no minoración entry. The carry treats the absence as zero;
  the advisory keeps that gap visible, while a filed zero stays silent.

A first trimestre, or a quarter with no stored prior filing, has nothing to
carry and raises neither advisory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.period_offset_math import same_ejercicio_prior_quarter_anchors
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    require_observation_envelope_coordinates_current,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "collect_prior_payment_minoracion_not_captured_diagnostics",
    "collect_prior_payment_not_deducted_diagnostics",
]

_MAPPING_FACT_ID = "m130-prior-payment-verification-mapping"
_SOURCE_KIND = "modelo_130_prior_pago_fraccionado"


@dataclass(frozen=True, slots=True)
class _PriorPaymentDeclaration:
    """The selected declaration's casilla identities for one Modelo 130 revision."""

    modelo: str
    prior_payment: CasillaId
    cumulative_income: CasillaId
    prior_positive_part: CasillaId
    prior_minoracion: CasillaId


def _declared_casilla(declarations: Mapping[str, str], key: str) -> CasillaId:
    value = declarations.get(key)
    if not value:
        raise RegistryValidationError(f"prior-payment declaration lacks {key!r}")
    return validated_casilla_id(value, surface=f"{_MAPPING_FACT_ID} {key}")


def _selected_registry_declaration(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> _PriorPaymentDeclaration | None:
    """Resolve the dated declaration when it applies to the selected work scope."""
    effective_date = date(filing_year, 12, 31)
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MAPPING_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("selected prior-payment declaration must resolve as a mapping fact")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    selected_modelo = declarations.get("modelo")
    if not selected_modelo:
        raise RegistryValidationError("selected prior-payment declaration lacks a model coordinate")
    if selected_modelo != modelo:
        return None
    selected_revision = declarations.get("revision")
    if not selected_revision:
        raise RegistryValidationError("selected prior-payment declaration lacks a revision coordinate")
    if selected_revision != str(revision.id):
        return None
    operation.revision_for_context(selected_modelo, filing_year=filing_year, period=period_token, on=effective_date)
    return _PriorPaymentDeclaration(
        modelo=selected_modelo,
        prior_payment=_declared_casilla(declarations, "casilla.prior_payment"),
        cumulative_income=_declared_casilla(declarations, "casilla.cumulative_income"),
        prior_positive_part=_declared_casilla(declarations, "casilla.prior_positive_part"),
        prior_minoracion=_declared_casilla(declarations, "casilla.prior_minoracion"),
    )


def _prior_trimestre_codes(period_token: str) -> tuple[str, ...]:
    """Return the same-ejercicio trimestres before ``period_token``; empty for a first or non-quarterly one."""
    try:
        anchors = same_ejercicio_prior_quarter_anchors(period_token)
    except RegistryValidationError:
        return ()
    return tuple(period for _year_delta, period in anchors)


def _prior_casilla_values(
    repository: CalculationObservationRepositoryProtocol,
    *,
    modelo: str,
    filing_year: int,
    prior_codes: tuple[str, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[tuple[str, Mapping[CasillaId, Decimal]], ...]:
    """Return each stored prior-trimestre filing's period and casilla values, re-confirmed."""
    wanted = set(prior_codes)
    found: list[tuple[str, Mapping[CasillaId, Decimal]]] = []
    for payload in repository.iter_modelo(modelo):
        require_observation_envelope_coordinates_current(payload, operation=operation)
        observation = payload.observation
        if observation.filing_year == filing_year and observation.period in wanted:
            found.append((observation.period, observation.casilla_values))
    return tuple(found)


def _casilla_legal_refs(revision: ModeloRevision, casilla_id: CasillaId) -> tuple[str, ...]:
    casilla = casillas_by_id(revision).get(casilla_id)
    return () if casilla is None else tuple(str(ref) for ref in casilla.legal_refs)


def collect_prior_payment_not_deducted_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when a non-first trimestre deducts no prior payment despite a prior filing."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return collect_prior_payment_not_deducted_diagnostics(
                revision,
                casilla_values,
                modelo=modelo,
                period_token=period_token,
                filing_year=filing_year,
                observation_repository=observation_repository,
                operation=indexed_operation,
            )
    declaration = _selected_registry_declaration(
        revision,
        modelo=modelo,
        period_token=period_token,
        filing_year=filing_year,
        operation=operation,
    )
    if declaration is None:
        return ()
    prior_codes = _prior_trimestre_codes(period_token)
    if not prior_codes:
        return ()
    if casilla_values.get(declaration.cumulative_income, Decimal(0)) <= Decimal(0):
        return ()
    if casilla_values.get(declaration.prior_payment, Decimal(0)) != Decimal(0):
        return ()
    prior_filings = _prior_casilla_values(
        observation_repository,
        modelo=declaration.modelo,
        filing_year=filing_year,
        prior_codes=prior_codes,
        operation=operation,
    )
    if not prior_filings:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="prior_payment_not_deducted",
            source_kind=_SOURCE_KIND,
            message=(
                f"Modelo {declaration.modelo} {period_token} is cumulative, but casilla "
                f"{declaration.prior_payment} (pagos fraccionados anteriores) is zero while a prior "
                f"{filing_year} trimestre was filed ({', '.join(prior_codes)}); the pago fraccionado already "
                f"paid is not deducted. Re-file the prior trimestre or enter its pago fraccionado before filing"
            ),
            casilla_id=declaration.prior_payment,
            legal_refs=_casilla_legal_refs(revision, declaration.prior_payment),
        ),
    )


def collect_prior_payment_minoracion_not_captured_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when a carried prior filing declares no minoración entry."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return collect_prior_payment_minoracion_not_captured_diagnostics(
                revision,
                modelo=modelo,
                period_token=period_token,
                filing_year=filing_year,
                observation_repository=observation_repository,
                operation=indexed_operation,
            )
    declaration = _selected_registry_declaration(
        revision,
        modelo=modelo,
        period_token=period_token,
        filing_year=filing_year,
        operation=operation,
    )
    if declaration is None:
        return ()
    prior_codes = _prior_trimestre_codes(period_token)
    if not prior_codes:
        return ()
    uncaptured = sorted(
        {
            period
            for period, values in _prior_casilla_values(
                observation_repository,
                modelo=declaration.modelo,
                filing_year=filing_year,
                prior_codes=prior_codes,
                operation=operation,
            )
            if declaration.prior_positive_part in values and declaration.prior_minoracion not in values
        },
    )
    if not uncaptured:
        return ()
    gap = ", ".join(uncaptured)
    return (
        CalculationSourceDiagnostic(
            reason="prior_payment_minoracion_not_captured",
            source_kind=_SOURCE_KIND,
            message=(
                f"Modelo {declaration.modelo} {period_token} casilla {declaration.prior_payment} carries the prior "
                f"pago fraccionado from {gap}, but those {filing_year} filings carry no casilla "
                f"{declaration.prior_minoracion} (minoración) entry. The carry treats it as zero; re-file the prior "
                f"trimestre(s) so it is captured, or confirm it was genuinely zero"
            ),
            casilla_id=declaration.prior_payment,
            legal_refs=_casilla_legal_refs(revision, declaration.prior_payment),
        ),
    )
