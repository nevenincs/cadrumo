"""Fictional repeating records using the registry's existing saved binding channel."""

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.core.aggregation import RetencionClave
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    resolve_atribucion_binding_row_values,
)
from cadrumo.domain.calculations.registry.export import row_binding_casilla_ids_by_field
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_row_values,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.row_models import Modelo184MemberRow


def member_attribution_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Supply two typed members; attributed amounts are declared, not recalculated."""
    if str(snapshot.modelo.id) != "184":
        raise ValueError("member attribution example requires Modelo 184")
    rows = tuple(
        Modelo184MemberRow(
            nif=nif,
            nombre=name,
            porcentaje=Decimal(share),
            importe=Decimal(amount),
            clave="D",
            subclave="01",
            codigo_provincia=province,
        )
        for nif, name, share, amount, province in (
            ("12345678Z", "Miembro ficticio A", "60", "3600", "28"),
            ("87654321X", "Miembro ficticio B", "40", "2400", "08"),
        )
    )
    work_id = sha256_hex(f"fictional-184-{snapshot.revision.id}-{snapshot.filing_year}".encode())
    timestamp = datetime(snapshot.filing_year, 12, 31, tzinfo=UTC)
    observations = tuple(
        AtributionMemberObservation(
            source_id=f"fictional-member-{index}",
            member_tax_id=row.nif,
            member_legal_name=row.nombre,
            country_code=row.pais,
            transaction_date=timestamp.date(),
            share_percentage=row.porcentaje,
            base_imponible_assigned=row.importe,
            clave=row.clave,
            subclave=row.subclave,
            codigo_provincia=row.codigo_provincia,
        )
        for index, row in enumerate(rows, 1)
    )
    bindings: dict[BindingId, dict[str, str]] = {}
    for (binding, index), value in resolve_atribucion_binding_row_values(snapshot.revision, observations).items():
        bindings.setdefault(binding, {})[str(index)] = str(value)
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


def annual_rent_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Resolve fictional recipient facts to declared row bindings, never cell coordinates."""
    if str(snapshot.modelo.id) != "180":
        raise ValueError("annual rent example requires Modelo 180")
    rows = (
        {
            "perc.nif": "12345678Z",
            "perc.nombre": "Arrendador ficticio A",
            "perc.provincia": "28",
            "perc.modalidad": "1",
            "perc.base": "12000",
            "perc.porcentaje-retencion": "19",
            "perc.retenciones": "2280",
            "perc.inmueble-tipo-via": "CL",
            "perc.inmueble-nombre-via": "EJEMPLO A",
            "perc.inmueble-numero-casa": "10",
            "perc.inmueble-municipio": "MADRID",
            "perc.inmueble-provincia": "28",
        },
        {
            "perc.nif": "87654321X",
            "perc.nombre": "Arrendador ficticio B",
            "perc.provincia": "08",
            "perc.modalidad": "1",
            "perc.base": "6000",
            "perc.porcentaje-retencion": "19",
            "perc.retenciones": "1140",
            "perc.inmueble-tipo-via": "CL",
            "perc.inmueble-nombre-via": "EJEMPLO B",
            "perc.inmueble-numero-casa": "20",
            "perc.inmueble-municipio": "BARCELONA",
            "perc.inmueble-provincia": "08",
        },
    )
    return _recipient_records(snapshot, rows, "modelo-180-perceptor")


def annual_employment_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Two fictional recipients using declared Modelo 190 row bindings."""
    if str(snapshot.modelo.id) != "190":
        raise ValueError("annual employment example requires Modelo 190")
    rows = tuple(
        {
            "perc.nif": nif,
            "perc.nombre": name,
            "perc.provincia": province,
            "perc.clave": "A",
            "perc.percepcion-dineraria": amount,
            "perc.retenciones-practicadas": withheld,
        }
        for nif, name, province, amount, withheld in (
            ("12345678Z", "Persona ficticia A", "28", "24000", "2400"),
            ("87654321X", "Persona ficticia B", "08", "18000", "1800"),
        )
    )
    return _recipient_records(snapshot, rows, "modelo-190-perceptor")


def annual_capital_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Separate fictional capital-income recipients from custody expense owners."""
    if str(snapshot.modelo.id) != "193":
        raise ValueError("annual capital example requires Modelo 193")
    recipients = tuple(
        {
            "perc.nif": nif,
            "perc.nombre": name,
            "perc.provincia": province,
            "perc.percepciones": amount,
            "perc.base": amount,
            "perc.porcentaje": "19",
            "perc.retenciones": withheld,
        }
        for nif, name, province, amount, withheld in (
            ("12345678Z", "Perceptor ficticio A", "28", "1000", "190"),
            ("87654321X", "Perceptor ficticio B", "08", "2000", "380"),
        )
    )
    expenses = ({"gasto.nif": "12345678Z", "gasto.nombre": "Perceptor ficticio A", "gasto.importe": "25"},)
    return _saved_record_groups(snapshot, (("modelo-193-perceptor", recipients), ("modelo-193-gastos", expenses)))


def financial_asset_observations(year: int) -> tuple[WithholdingObservation, ...]:
    """Five fictional operations on one recipient, including zero and losses."""
    return tuple(
        WithholdingObservation(
            source_id=f"fictional-asset-{index}",
            perceptor_tax_id="12345678Z",
            perceptor_legal_name="Perceptora ficticia Ejemplo",
            transaction_date=date(year, 6, index),
            province_code="28",
            clave=RetencionClave.from_registry("G"),
            financial_asset_origin="A",
            financial_asset_acquisition_value=Decimal("1000"),
            financial_asset_disposal_value=Decimal("1000") + Decimal(base),
            base_retenciones=Decimal(base),
            porcentaje_retencion=Decimal("19") if Decimal(base) > 0 else Decimal("0"),
            retencion_practicada=Decimal(retention),
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
        )
        for index, (base, retention) in enumerate(
            (("100", "19"), ("25", "4.75"), ("0", "0"), ("-40", "0"), ("-10", "0")), 1
        )
    )


def financial_asset_records(snapshot: RegistrySnapshot) -> CalculationRevision:
    """Resolve the same typed transactions used for the five summary boxes."""
    if str(snapshot.modelo.id) != "194":
        raise ValueError("financial asset example requires Modelo 194")
    bindings: dict[BindingId, dict[str, str]] = {}
    for (binding, index), value in resolve_withholding_binding_row_values(
        snapshot.revision, financial_asset_observations(snapshot.filing_year)
    ).items():
        bindings.setdefault(binding, {})[str(index)] = str(value)
    return _saved_binding_records(snapshot, bindings)


def _recipient_records(
    snapshot: RegistrySnapshot, rows: tuple[dict[str, str], ...], record_id: str
) -> CalculationRevision:
    return _saved_record_groups(snapshot, ((record_id, rows),))


def _saved_record_groups(
    snapshot: RegistrySnapshot, groups: tuple[tuple[str, tuple[dict[str, str], ...]], ...]
) -> CalculationRevision:
    (layout,) = snapshot.revision.export_layouts
    targets = row_binding_casilla_ids_by_field(snapshot.revision, layout)
    bindings: dict[BindingId, dict[str, str]] = {}
    for record_id, rows in groups:
        record = next(record for record in layout.records if record.id == record_id)
        binding_by_target = {
            str(targets[field.id]): field.binding
            for field in record.fields
            if field.id in targets and field.binding is not None
        }
        supplied = {target for row in rows for target in row}
        if not supplied <= binding_by_target.keys():
            raise ValueError("fictional recipient fields no longer match the selected registry")
        for index, row in enumerate(rows, 1):
            for target, value in row.items():
                binding = binding_by_target[target]
                bindings.setdefault(binding, {})[str(index)] = value
    return _saved_binding_records(snapshot, bindings)


def _saved_binding_records(
    snapshot: RegistrySnapshot, bindings: dict[BindingId, dict[str, str]]
) -> CalculationRevision:
    work_id = sha256_hex(f"fictional-{snapshot.modelo.id}-{snapshot.revision.id}-{snapshot.filing_year}".encode())
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values=bindings,
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    timestamp = datetime(snapshot.filing_year, 12, 31, tzinfo=UTC)
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
