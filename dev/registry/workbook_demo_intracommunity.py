"""Fictional 349 invoice facts shared by the summary and saved detail rows."""

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)


def intracommunity_observations(year: int) -> tuple[InvoiceObservation, ...]:
    """Include two invoices for one operator and a correction of an earlier quarter."""
    rows = tuple(
        InvoiceObservation(
            invoice_id=f"fictional-349-{year}-{index}",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            party_tax_id=nif,
            party_legal_name=name,
            country_code=country,
            transaction_date=date(year, 12, index),
            base_amount=Decimal(amount),
            intracommunity_clave=clave,
        )
        for index, (country, nif, name, clave, amount) in enumerate(
            (
                ("DE", "DE123456789", "Empresa ficticia A", "E", "7000"),
                ("DE", "DE123456789", "Empresa ficticia A", "E", "5000"),
                ("FR", "FR12345678901", "Empresa ficticia B", "S", "4500"),
            ),
            1,
        )
    )
    return (
        *rows,
        InvoiceObservation(
            invoice_id=f"fictional-349-{year}-correction",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            party_tax_id="IT12345678901",
            party_legal_name="Empresa ficticia C",
            country_code="IT",
            transaction_date=date(year, 12, 4),
            base_amount=Decimal("900"),
            intracommunity_clave="E",
            is_rectification=True,
            rectified_year=year,
            rectified_period="3T",
            rectified_base_previous=Decimal("1000"),
        ),
    )


def intracommunity_summary(snapshot: RegistrySnapshot) -> dict[BindingId, Decimal]:
    """Let the registry decide grouping, counts and corrected-base totals."""
    if str(snapshot.modelo.id) != "349":
        raise ValueError("intracommunity example requires Modelo 349")
    return resolve_invoice_binding_values(snapshot.revision, intracommunity_observations(snapshot.filing_year))


def intracommunity_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Persist the same backend row projection consumed by filing replay."""
    if str(snapshot.modelo.id) != "349":
        raise ValueError("intracommunity example requires Modelo 349")
    bindings: dict[BindingId, dict[str, str]] = {}
    for (binding, index), value in resolve_invoice_binding_row_values(
        snapshot.revision, intracommunity_observations(snapshot.filing_year)
    ).items():
        bindings.setdefault(binding, {})[str(index)] = str(value)
    work_id = sha256_hex(f"fictional-349-{snapshot.revision.id}-{snapshot.filing_year}-4T".encode())
    timestamp = datetime(snapshot.filing_year, 12, 31, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(),
        row_binding_values=bindings,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        row_binding_values=bindings,
        created_at=timestamp,
        updated_at=timestamp,
        filing_instance_evidence=None,
        source_provenance=(),
    )
