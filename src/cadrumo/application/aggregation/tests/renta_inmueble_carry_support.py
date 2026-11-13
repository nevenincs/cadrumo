"""Resolve one let property's anexo C.1 carry through the real resolver, for the pending-expense tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_columns,
    renta_inmueble_origin_columns,
)
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ....domain.contribuyente.inmueble_record import ValorCatastral
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from ....domain.renta.retencion_soportada import RetencionSoportadaRecord
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...modelo.work_profile import ModeloWorkProfile
from ..renta_inmueble_findings import RentaInmuebleCause
from ..renta_inmueble_resolver import RentaInmuebleSourceResolver
from ..renta_inmueble_source import RentaInmuebleRowField
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, m100_revision
from .renta_inmueble_support import expense, inmueble, lease, monthly_rent, profile_facts

ROW = "inmueble:3"
RENT = Decimal(900)
"""A month's rent: 10.800 over the year, the property's limit for interest and repairs."""


class _NoWithholding:
    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        del ejercicio
        return ()


def sentence(cause: RentaInmuebleCause) -> CalculationNoteSentence:
    """Return the catalogue sentence that states a finding of ``cause``."""
    return CalculationNoteSentence(f"renta_inmueble_{cause.value}")


def column(revision: ModeloRevision, field: RentaInmuebleRowField) -> BindingId:
    """Return the binding of one plain column of the property's row."""
    return next(
        binding.id for binding, provider in renta_inmueble_columns(revision) if provider.row_field == field.value
    )


def origin_column(revision: ModeloRevision, part: RentaInmuebleOriginPart, back: int) -> BindingId:
    """Return the anexo C.1 column of ``part`` for the origin year ``back`` ejercicios before the one filed."""
    return renta_inmueble_origin_columns(revision)[part][back].id


def window(revision: ModeloRevision) -> int:
    """Return the carry window the revision's opening columns cover."""
    return len(renta_inmueble_origin_columns(revision)[RentaInmuebleOriginPart.OPENING])


def stated(year: int, back: int, amount: str | None, *, row: str = ROW) -> RowCarryAttestation:
    """State one origin year's opening on ``row``: ``None`` that nothing is pending, else the amount."""
    binding = origin_column(m100_revision(year), RentaInmuebleOriginPart.OPENING, back)
    if amount is None:
        return RowCarryAttestation(binding_id=binding, source_row_identity=row, amount=ATTESTED_ZERO, absent=True)
    return RowCarryAttestation(binding_id=binding, source_row_identity=row, amount=amount)


def nothing_pending(year: int) -> tuple[RowCarryAttestation, ...]:
    """State that no origin year of the window left anything pending on the property."""
    return tuple(stated(year, back, None) for back in range(1, window(m100_revision(year)) + 1))


def _profile(
    year: int, operation: PinnedAuthorityOperation, property_fields: Mapping[str, object], lease_start: date
) -> ModeloWorkProfile:
    record = inmueble(
        3,
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(100000), construccion=Decimal(60000)),),
        **property_fields,
    )
    let: ArrendamientoRecord = lease(0, inmueble_clave=3, start=lease_start)
    facts = profile_facts((record,), (let,))
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in facts.items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def resolve_carry(
    year: int,
    *statements: RowCarryAttestation,
    repairs: Decimal = Decimal(1000),
    arrendado_desde: date | None = None,
    start_unstated: bool = False,
    lease_start: date | None = None,
    held: bool | None = None,
    sin_arrendar: bool = False,
) -> CalculationSourceResolution:
    """Resolve the property, first let on ``arrendado_desde`` and let under one lease from ``lease_start``.

    Unless the test names them, the property was first let, and its lease
    started, three ejercicios before the one filed; ``start_unstated`` leaves
    the first letting unstated and ``sin_arrendar`` states it was never let.
    ``held`` is what the held-return reader answers, ``None`` for no reader.
    """
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    start = date(year - 3, 1, 1)
    property_fields: dict[str, object] = {"sin_arrendar": sin_arrendar}
    if not sin_arrendar and not start_unstated:
        property_fields["arrendado_desde"] = start if arrendado_desde is None else arrendado_desde
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(
        TransactionCatalogue.from_transactions(
            (
                *monthly_rent(year, amount=RENT),
                expense(
                    "reparacion",
                    concept="reparacion_conservacion",
                    inmueble_clave=3,
                    amount=repairs,
                    booked=date(year, 6, 30),
                ),
            )
        )
    )
    return RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_NoWithholding()),
        prior_return_held=None if held is None else (lambda _context: held),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=m100_revision(year),
            profile=_profile(year, operation, property_fields, start if lease_start is None else lease_start),
            caller_row_attestations=statements,
        )
    )


def findings(resolution: CalculationSourceResolution, cause: RentaInmuebleCause) -> list[CalculationSourceDiagnostic]:
    """Return the diagnostics that state a finding of ``cause``."""
    worded = sentence(cause)
    return [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.fact is not None and diagnostic.fact.sentence == worded
    ]


PENDING_CAUSES = (
    RentaInmuebleCause.LETTING_START_UNSTATED,
    RentaInmuebleCause.PENDING_EXPENSES_UNSTATED,
    RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED,
    RentaInmuebleCause.PENDING_EXPENSES_TOTAL_UNSPLIT,
)
