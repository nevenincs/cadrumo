"""Typed fictional members for the contribution calendar demonstration."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.m156_rows import Modelo156AfiliadoRow, Modelo156MonthlyContribution

from .m156_row_materialisation import materialize_m156_member_bindings


def contribution_members() -> tuple[Modelo156AfiliadoRow, ...]:
    """Keep independent monthly statuses, money, missing data and leading zeros."""
    amounts = (
        "100.25",
        "110.50",
        "100.25",
        "0",
        "125.75",
        "125.75",
        "130.25",
        "130.25",
        "0",
        "140.50",
        "140.50",
        "150.75",
    )
    statuses: tuple[Literal["S", "N"], ...] = ("S", "S", "S", "N", "S", "S", "S", "S", "N", "S", "S", "S")
    return (
        Modelo156AfiliadoRow(
            nif="12345678Z",
            nombre="Ejemplo Prueba Ana",
            numero_afiliacion="001234567890",
            cotizaciones=tuple(
                Modelo156MonthlyContribution(month=m, status=status, amount=Decimal(amount))
                for m, (status, amount) in enumerate(zip(statuses, amounts, strict=True), 1)
            ),
        ),
        Modelo156AfiliadoRow(
            nif="87654321X",
            nombre="Ejemplo Prueba Luis",
            numero_afiliacion="001234567891",
            cotizaciones=tuple(
                Modelo156MonthlyContribution(
                    month=m,
                    status=None if m == 12 else "N" if m == 4 else "S",
                    amount=None if m == 12 else Decimal("0") if m == 4 else Decimal("75.50"),
                )
                for m in range(1, 13)
            ),
        ),
    )


def contribution_member_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Save real typed rows and their canonical registry binding projection."""
    if str(snapshot.modelo.id) != "156":
        raise ValueError("contribution calendar example requires Modelo 156")
    rows = contribution_members()
    bindings: dict[BindingId, dict[str, str]] = {}
    for (binding, index), value in materialize_m156_member_bindings(snapshot.revision, rows).items():
        bindings.setdefault(binding, {})[str(index)] = str(value)
    work_id = sha256_hex(f"fictional-156-{snapshot.revision.id}-{snapshot.filing_year}".encode())
    timestamp = datetime(snapshot.filing_year, 12, 31, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=rows,
        row_binding_values=bindings,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        detail_rows=rows,
        row_binding_values=bindings,
        created_at=timestamp,
        updated_at=timestamp,
        filing_instance_evidence=None,
        source_provenance=(),
    )
