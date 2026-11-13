"""The prorrata register as the year's last Modelo 303 leaves it.

LIVA art. 105.Cuatro calculates the definitive percentage in the last return of
the year, and art. 105.Uno reads the filed definitive as the next year's
provisional one. The register therefore gains its explicit entry for the year
from the casillas of that last return. This module derives that entry from a
revision's own casillas as a pure function, so local filing writes the register
with it and the export of the same revision reads the register as filing will
leave it, without writing anything before the filing exists.

RIVA art. 28.1.2º keeps an especial-prorrata option in force for at least three
years: a year whose predecessor stands under it cannot be settled into a
general entry the filer never declared, so that settlement is refused.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.casilla_id import validated_casilla_id
from ...core.i18n.translatable import Translatable as tr
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.prorrata_register_catalogue import (
    especial_prorrata_register_regime,
    general_prorrata_register_regime,
    ninguna_prorrata_register_regime,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ...domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
)

PRORRATA_VOLUMEN_TOTAL_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-total",
    surface="prorrata settlement volumen total casilla id",
)

PRORRATA_VOLUMEN_CON_DERECHO_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="prorrata settlement volumen con derecho casilla id",
)

PRORRATA_PORCENTAJE_CASILLA = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata settlement definitive percentage casilla id",
)

#: The words of the refusal, shared with the verification finding that reports the same condition.
PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_KEY = "application.modelo.findings.prorrata_settlement_especial_continuation"


class ProrrataSettlementEspecialContinuationError(ProrrataRegisterValidationError):
    """The year's prior entry stands under the especial regime and the register holds no declaration for this year."""

    def __init__(self, *, filing_year: int) -> None:
        """Name the settled year and the prior year whose especial entry stands."""
        super().__init__(
            tr(PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_KEY),
            context={"filing_year": filing_year, "prior_filing_year": filing_year - 1},
        )
        self.filing_year = filing_year


def prorrata_settlement_values(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
) -> tuple[Decimal, Decimal, Decimal] | None:
    """The annual volumes and definitive percentage a last-of-year Modelo 303 states, or ``None``.

    ``None`` when the work unit is not the periodic IVA return, is not the
    year's annual settlement period, or its revision lacks any of the three
    casillas.
    """
    if str(work_unit.modelo) != form_for_role("iva.periodic"):
        return None
    if not is_m303_annual_settlement_period(work_unit.period, authority=operation):
        return None

    casilla_values = revision.casilla_values
    volumen_total = casilla_values.get(PRORRATA_VOLUMEN_TOTAL_CASILLA)
    volumen_con_derecho = casilla_values.get(PRORRATA_VOLUMEN_CON_DERECHO_CASILLA)
    definitive_percentage = casilla_values.get(PRORRATA_PORCENTAJE_CASILLA)
    if volumen_total is None or volumen_con_derecho is None or definitive_percentage is None:
        return None
    return volumen_total, volumen_con_derecho, definitive_percentage


def settled_prorrata_register_entry(
    *,
    work_unit: WorkUnit,
    register: ProrrataRegister,
    volumen_total: Decimal,
    volumen_con_derecho: Decimal,
    definitive_percentage: Decimal,
) -> ProrrataRegisterEntry:
    """The whole-entity entry of the work unit's year with its definitive figures settled.

    An entry the register already holds keeps its regime, provisional figure and
    option or revocation evidence; a year without one starts general when
    operations without the right to deduct exist and ``ninguna`` otherwise.
    """
    volumen_sin_derecho = volumen_total - volumen_con_derecho
    settlement_snapshot_ref = RegistrySnapshotRef(
        modelo=work_unit.modelo,
        revision_id=work_unit.revision_id,
        modelo_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    settlement_fields = {
        "definitive_percentage": definitive_percentage,
        "definitive_volume_con_derecho": volumen_con_derecho,
        "definitive_volume_sin_derecho": volumen_sin_derecho,
    }
    existing = register.entry_for(work_unit.filing_year)
    if existing is not None:
        return ProrrataRegisterEntry.model_validate(
            {
                **existing.model_dump(),
                **settlement_fields,
                "source_registry_snapshot_refs": tuple(
                    dict.fromkeys((*existing.source_registry_snapshot_refs, settlement_snapshot_ref))
                ),
            }
        )

    prior = register.entry_for(work_unit.filing_year - 1)
    if prior is not None and prior.regime == especial_prorrata_register_regime():
        raise ProrrataSettlementEspecialContinuationError(filing_year=work_unit.filing_year)

    regime = (
        general_prorrata_register_regime() if volumen_sin_derecho > Decimal("0") else ninguna_prorrata_register_regime()
    )
    return ProrrataRegisterEntry(
        ejercicio=work_unit.filing_year,
        regime=regime,
        especial_transition=None,
        definitive_percentage=definitive_percentage,
        definitive_volume_con_derecho=volumen_con_derecho,
        definitive_volume_sin_derecho=volumen_sin_derecho,
        source_registry_snapshot_refs=(settlement_snapshot_ref,),
    )


def settled_prorrata_register(
    register: ProrrataRegister,
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
) -> ProrrataRegister | None:
    """The register as filing ``revision`` leaves it, or ``None`` when that filing settles nothing.

    A filing settles nothing when its work unit is not the year's annual
    settlement return, its revision lacks the settlement casillas, or the
    register declares the year interrupted (LIVA art. 105.Cinco).

    Pure: the caller decides whether the result is written (local filing) or
    only read (export of the revision about to be filed).

    Raises:
        ProrrataSettlementEspecialContinuationError: When the prior year's
            whole-entity entry is especial and the register holds no entry for
            the settled year.
    """
    values = prorrata_settlement_values(revision=revision, work_unit=work_unit, operation=operation)
    if values is None:
        return None
    current = register.entry_for(work_unit.filing_year)
    if current is not None and current.interrupted:
        # An art. 105.Cinco year without operations carries no definitive percentage; the return cannot give it one.
        return None
    entry = settled_prorrata_register_entry(
        work_unit=work_unit,
        register=register,
        volumen_total=values[0],
        volumen_con_derecho=values[1],
        definitive_percentage=values[2],
    )
    retained = tuple(
        existing
        for existing in register.entries
        if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
    )
    return ProrrataRegister(
        entries=(*retained, entry),
        sector_definitions=register.sector_definitions,
        activity_rows=register.activity_rows,
        gross_declarations=register.gross_declarations,
    )


__all__ = [
    "PRORRATA_PORCENTAJE_CASILLA",
    "PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_KEY",
    "PRORRATA_VOLUMEN_CON_DERECHO_CASILLA",
    "PRORRATA_VOLUMEN_TOTAL_CASILLA",
    "ProrrataSettlementEspecialContinuationError",
    "prorrata_settlement_values",
    "settled_prorrata_register",
    "settled_prorrata_register_entry",
]
