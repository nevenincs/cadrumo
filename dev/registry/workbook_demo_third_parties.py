"""Fictional Modelo 347 invoices resolved through the enrolled registry bindings."""

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    m347_operation_clave,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)


def third_party_observations(year: int) -> tuple[InvoiceObservation, ...]:
    """Include purchases, sales, a rented premises and a below-threshold control.

    These are synthetic invoice totals, not assessed taxes. The premises address
    remains unknown because InvoiceObservation does not carry that fact.
    """
    rows: list[InvoiceObservation] = []
    for nif, name, source, amounts, rental in (
        (
            "12345678Z",
            "Proveedor ficticio Ana",
            BindingSourceKind.PAYABLE_INVOICE,
            ("1210", "2420", "3630", "4840"),
            False,
        ),
        (
            "87654321X",
            "Cliente ficticio Luis",
            BindingSourceKind.COLLECTIBLE_INVOICE,
            ("4840", "3630", "2420", "1210"),
            False,
        ),
        (
            "11111111H",
            "Arrendatario ficticio Carmen",
            BindingSourceKind.COLLECTIBLE_INVOICE,
            ("1815", "1815", "1815", "1815"),
            True,
        ),
        (
            "22222222J",
            "Proveedor ficticio bajo umbral",
            BindingSourceKind.PAYABLE_INVOICE,
            ("121", "242", "363", "484"),
            False,
        ),
    ):
        for quarter, amount in enumerate(amounts, 1):
            gross = Decimal(amount)
            rows.append(
                InvoiceObservation(
                    invoice_id=f"fictional-347-{year}-{nif}-{quarter}",
                    source_kind=source,
                    operation_clave=m347_operation_clave(source),
                    party_tax_id=nif,
                    party_legal_name=name,
                    country_code="ES",
                    transaction_date=date(year, quarter * 3, 15),
                    base_amount=gross / Decimal("1.21"),
                    invoice_total_amount=gross,
                    arrendamiento_local_negocio=rental,
                    situacion_inmueble="1" if rental else None,
                    referencia_catastral="9872023VH5797S0001WX" if rental else None,
                )
            )
    return tuple(rows)


def third_party_summary(snapshot: RegistrySnapshot) -> dict[BindingId, Decimal]:
    """Use the dated declaration threshold and the same invoices as saved rows.

    The caller supplies the canonical governed-fact authority scope.
    """
    if str(snapshot.modelo.id) != "347":
        raise ValueError("third-party example requires Modelo 347")
    return resolve_invoice_binding_values(
        snapshot.revision,
        third_party_observations(snapshot.filing_year),
        effective_date=date(snapshot.filing_year, 12, 31),
    )


def third_party_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Save canonical row projections without introducing operator overrides."""
    if str(snapshot.modelo.id) != "347":
        raise ValueError("third-party example requires Modelo 347")
    bindings: dict[BindingId, dict[str, str]] = {}
    for (binding, index), value in resolve_invoice_binding_row_values(
        snapshot.revision,
        third_party_observations(snapshot.filing_year),
        effective_date=date(snapshot.filing_year, 12, 31),
    ).items():
        bindings.setdefault(binding, {})[str(index)] = str(value)
    work_id = sha256_hex(f"fictional-347-{snapshot.revision.id}-{snapshot.filing_year}".encode())
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
