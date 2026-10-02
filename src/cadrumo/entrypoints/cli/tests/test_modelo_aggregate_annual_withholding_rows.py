"""``modelo aggregate`` reports the stored withholding rows an annual summary's calculation reads.

Modelos 180, 190 and 193 are composed from stored windows rather than typed in:
180 from the year's Modelo 115 retención windows, 190 from the year's Modelo 111
per-perceptor-clave windows, and 193 from its own per-perceptor-clave window
(plus, in the editions that bind it, its own retención window). Each test seeds
the real encrypted stores of an isolated profile with synthetic rows, including
rows the calculation must NOT read, runs the live CLI, and compares the report
with what the real calculation resolver materialises from the same stores.

An empty store and a stored zero are different facts: the first must reach the
operator as a structured warning naming the source the calculation reads, the
second is a counted row with zero amounts and no warning.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import manual_capital_row
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import withholding_work_profile

from ....adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from ....adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ....application.aggregation.percepciones_observations_repository import PercepcionObservationPorts
from ....application.aggregation.retencion_observations_repository import RetencionObservationPorts
from ....application.aggregation.retenciones import (
    Modelo180PropertyEvidence,
    Modelo180StructuredAddress,
    RetencionObservation,
)
from ....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.aggregation.withholding_source import WithholdingSourceResolver
from ....application.modelo.work_profile import ModeloWorkProfile
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionClave, RetencionScheme
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000529"
_YEAR = 2025
_ANNUAL = Period.from_year_and_code(_YEAR, "0A")
_ABSENT_CODE = "modelo.aggregate.calculation_rows_absent"

_LANDLORD_A = "B12345674"
_LANDLORD_B = "A08000143"
_LANDLORD_OTHER_YEAR = "B00000011"
_LANDLORD_OWN_WINDOW = "B00000022"
_EMPLOYEE = "11111111H"
_PROFESSIONAL = "22222222J"
_PERCEPTOR_OTHER_YEAR = "33333333P"
_PERCEPTOR_OWN_WINDOW = "44444444A"


@contextmanager
def _operator_bucket(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> Iterator[tuple[SecureObjectRepository, ModeloWorkProfile]]:
    """Open an isolated active bucket whose profile the CLI and the resolver both read."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="Annual withholding report") as bucket:
        work_profile = withholding_work_profile(operation, profile_id=_BUCKET_ID)
        seed_test_profile_record(work_profile.record, root=bucket.storage_root)
        yield bucket.repository, work_profile


def _aggregate(modelo: str) -> Result:
    return invoke_cached_cli(
        [
            "--format", "json", "--language", "en",
            "app", "modelo", "aggregate",
            "--modelo", modelo, "--year", str(_YEAR), "--period", "0A",
        ],
    )  # fmt: skip


def _report(modelo: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    result = _aggregate(modelo)
    assert result.exit_code == 0, result.output
    return (
        unwrap_schema_envelope(result.output),
        unwrap_envelope_notices(result.output),
        json.loads(result.output)["status"],
    )


def _context(modelo: str, operation: PinnedAuthorityOperation, profile: ModeloWorkProfile) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=_ANNUAL,
        revision=operation.revision_for_context(modelo, filing_year=_YEAR, period="0A"),
        profile=profile,
    )


def _retencion_ports(objects: SecureObjectRepository) -> RetencionObservationPorts:
    return RetencionObservationPorts(repository=RetencionObservationRepositoryAdapter(objects=objects))


def _percepcion_ports(objects: SecureObjectRepository) -> PercepcionObservationPorts:
    return PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=objects))


def _calculated_retenciones(
    objects: SecureObjectRepository, modelo: str, operation: PinnedAuthorityOperation, profile: ModeloWorkProfile
) -> CalculationSourceResolution:
    return RetencionesAggregationSourceResolver(ports=_retencion_ports(objects)).resolve(
        _context(modelo, operation, profile)
    )


def _calculated_percepciones(
    objects: SecureObjectRepository, modelo: str, operation: PinnedAuthorityOperation, profile: ModeloWorkProfile
) -> CalculationSourceResolution:
    return WithholdingSourceResolver(
        ports=_percepcion_ports(objects),
        retencion_ports=_retencion_ports(objects),
    ).resolve(_context(modelo, operation, profile))


def _binding_id_for_fact(revision: ModeloRevision, source: BindingSourceKind, fact: str) -> str:
    (binding_id,) = (
        binding.id
        for binding in revision.bindings
        if binding.source == source and getattr(binding.provider, "fact", None) == fact
    )
    return binding_id


def _store_retenciones(
    objects: SecureObjectRepository, modelo: str, period: Period, *rows: RetencionObservation
) -> None:
    RetencionObservationRepositoryAdapter(objects=objects).replace_observations(
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        observations=rows,
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _store_percepciones(
    objects: SecureObjectRepository, modelo: str, period: Period, *rows: WithholdingObservation
) -> None:
    PercepcionObservationRepositoryAdapter(objects=objects).replace_observations(
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        observations=rows,
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _rent(*, landlord: str, source_id: str, accrued_on: date, base: str, retencion: str) -> RetencionObservation:
    """One urban-rent retención with the property detail the Modelo 180 rows require."""
    return RetencionObservation(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id=source_id,
        perceptor_nif=landlord,
        perceptor_name="Arrendador Sintetico",
        scheme=RetencionScheme("arrendamiento_urbano"),
        taxable_base=Decimal(base),
        retencion_amount=Decimal(retencion),
        accrued_on=accrued_on.isoformat(),
        modelo_180_property=Modelo180PropertyEvidence(
            property_key="synthetic-rented-premises",
            situation="1",
            cadastral_reference="1234567VK4713C0001XY",
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code="28",
            modality="1",
            accrual_year=accrued_on.year,
            withholding_percentage=Decimal("19.00"),
        ),
    )


def _percepcion(
    *, perceptor: str, clave: str, source_id: str, paid_on: date, percibido: str, retencion: str
) -> WithholdingObservation:
    """One per-perceptor-clave Modelo 190 detail row."""
    return WithholdingObservation(
        source_id=source_id,
        source_allocation_id=f"{source_id}-allocation",
        perceptor_tax_id=perceptor,
        perceptor_legal_name="Perceptor Sintetico",
        transaction_date=paid_on,
        clave=RetencionClave.from_registry(clave),
        subclave="01",
        percibido_dinerario=Decimal(percibido),
        retencion_practicada=Decimal(retencion),
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
        base_retenciones=Decimal(percibido),
        porcentaje_retencion=Decimal("15"),
    )


def _breakdown(payload: dict[str, Any]) -> dict[str, tuple[int, Decimal, Decimal]]:
    return {
        row["clave"]: (row["percepcion_count"], Decimal(row["percibido_total"]), Decimal(row["retencion_total"]))
        for row in payload["clave_breakdown"]
    }


def test_modelo_180_reports_the_modelo_115_windows_its_calculation_reads(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The year's Modelo 115 rows are summarised; another year and 180's own window are not."""
    with _operator_bucket(tmp_path, authority_operation) as (objects, profile):
        _store_retenciones(
            objects, "115", Period.from_year_and_code(_YEAR, "1T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-a-q1", accrued_on=date(_YEAR, 2, 1), base="1000.00", retencion="190.00"),
        )  # fmt: skip
        _store_retenciones(
            objects, "115", Period.from_year_and_code(_YEAR, "2T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-a-q2", accrued_on=date(_YEAR, 5, 1), base="1000.00", retencion="190.00"),
            _rent(landlord=_LANDLORD_B, source_id="rent-b-q2", accrued_on=date(_YEAR, 5, 1), base="500.00", retencion="95.00"),
        )  # fmt: skip
        _store_retenciones(
            objects, "115", Period.from_year_and_code(_YEAR - 1, "4T"),
            _rent(landlord=_LANDLORD_OTHER_YEAR, source_id="rent-prior", accrued_on=date(_YEAR - 1, 11, 1), base="700.00", retencion="133.00"),
        )  # fmt: skip
        _store_retenciones(
            objects, "180", _ANNUAL,
            _rent(landlord=_LANDLORD_OWN_WINDOW, source_id="rent-own", accrued_on=date(_YEAR, 7, 1), base="900.00", retencion="171.00"),
        )  # fmt: skip

        payload, notices, status = _report("180")
        calculated = _calculated_retenciones(objects, "180", authority_operation, profile)

    # Three stored 115 rows of the year, two landlords: A twice and B once.
    assert payload["provider"] == "retenciones"
    assert payload["observation_count"] == 3
    assert payload["result_row_count"] == 2
    assert payload["clave_breakdown"] == []
    assert (notices, status) == ([], "success")
    # The calculation's per-perceptor provenance names exactly the rows the report summarised.
    assert {provenance.source_ref for provenance in calculated.provenance} == {
        f"perceptor:{_LANDLORD_A}",
        f"perceptor:{_LANDLORD_B}",
    }
    assert len(calculated.provenance) == payload["result_row_count"]
    type2_count = _binding_id_for_fact(
        authority_operation.revision_for_context("180", filing_year=_YEAR, period="0A"),
        BindingSourceKind.RETENCIONES_AGGREGATION,
        "type2_record_count",
    )
    assert calculated.binding_values[type2_count] == Decimal("2")


def test_modelo_190_reports_the_modelo_111_percepciones_its_calculation_reads(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The year's Modelo 111 per-clave rows are projected; another year and 190's own window are not."""
    with _operator_bucket(tmp_path, authority_operation) as (objects, profile):
        _store_percepciones(
            objects, "111", Period.from_year_and_code(_YEAR, "1T"),
            _percepcion(perceptor=_PROFESSIONAL, clave="G", source_id="g-q1", paid_on=date(_YEAR, 3, 10), percibido="1000.00", retencion="150.00"),
        )  # fmt: skip
        _store_percepciones(
            objects, "111", Period.from_year_and_code(_YEAR, "3T"),
            _percepcion(perceptor=_EMPLOYEE, clave="A", source_id="a-q3", paid_on=date(_YEAR, 8, 10), percibido="2000.00", retencion="300.00"),
            _percepcion(perceptor=_PROFESSIONAL, clave="G", source_id="g-q3", paid_on=date(_YEAR, 8, 10), percibido="500.00", retencion="75.00"),
        )  # fmt: skip
        _store_percepciones(
            objects, "111", Period.from_year_and_code(_YEAR - 1, "4T"),
            _percepcion(perceptor=_PERCEPTOR_OTHER_YEAR, clave="A", source_id="a-prior", paid_on=date(_YEAR - 1, 11, 10), percibido="800.00", retencion="120.00"),
        )  # fmt: skip
        _store_percepciones(
            objects, "190", _ANNUAL,
            _percepcion(perceptor=_PERCEPTOR_OWN_WINDOW, clave="A", source_id="a-own", paid_on=date(_YEAR, 9, 10), percibido="600.00", retencion="90.00"),
        )  # fmt: skip

        payload, notices, status = _report("190")
        calculated = _calculated_percepciones(objects, "190", authority_operation, profile)

    # Clave G: one perceptor paid twice is one percepción; clave A: the employee.
    assert _breakdown(payload) == {
        "A": (1, Decimal("2000.00"), Decimal("300.00")),
        "G": (1, Decimal("1500.00"), Decimal("225.00")),
    }
    # Modelo 190's calculation reads no retención rows, so its retenciones summary is empty by construction.
    assert payload["observation_count"] == 0
    assert (notices, status) == ([], "success")
    percepcion_count = _binding_id_for_fact(
        authority_operation.revision_for_context("190", filing_year=_YEAR, period="0A"),
        BindingSourceKind.WITHHOLDING,
        "percepcion_count",
    )
    assert calculated.binding_values[percepcion_count] == sum(count for count, _, _ in _breakdown(payload).values())
    assert len(calculated.provenance) == 3


def test_modelo_193_reports_the_percepciones_its_calculation_reads_and_not_an_unread_retencion_window(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """193's own per-perceptor-clave window is projected; a retención row its edition does not bind is not read."""
    first = manual_capital_row(filing_year=_YEAR, source_id="coupon-one", source_allocation_id="coupon-one-1")
    second = manual_capital_row(
        filing_year=_YEAR, source_id="coupon-two", source_allocation_id="coupon-two-1"
    ).model_copy(update={"perceptor_tax_id": _PERCEPTOR_OWN_WINDOW})
    revision = authority_operation.revision_for_context("193", filing_year=_YEAR, period="0A")
    assert not any(binding.source == BindingSourceKind.RETENCIONES_AGGREGATION for binding in revision.bindings), (
        "this case needs a Modelo 193 edition whose calculation reads no retención rows"
    )
    with _operator_bucket(tmp_path, authority_operation) as (objects, profile):
        _store_percepciones(objects, "193", _ANNUAL, first, second)
        _store_retenciones(
            objects, "193", _ANNUAL,
            _rent(landlord=_LANDLORD_OWN_WINDOW, source_id="unread", accrued_on=date(_YEAR, 4, 1), base="100.00", retencion="19.00"),
        )  # fmt: skip

        payload, notices, status = _report("193")
        calculated = _calculated_percepciones(objects, "193", authority_operation, profile)
        calculated_retenciones = _calculated_retenciones(objects, "193", authority_operation, profile)

    clave = str(first.clave)
    expected_percibido = first.percibido_dinerario + second.percibido_dinerario
    expected_retencion = first.retencion_practicada + second.retencion_practicada
    assert _breakdown(payload) == {clave: (2, expected_percibido, expected_retencion)}
    assert len(calculated.provenance) == 2
    assert payload["observation_count"] == 0
    assert calculated_retenciones.binding_values == {}
    assert (notices, status) == ([], "success")


def _seed_zero_row(objects: SecureObjectRepository, modelo: str) -> None:
    if modelo == "180":
        _store_retenciones(
            objects, "115", Period.from_year_and_code(_YEAR, "1T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-zero", accrued_on=date(_YEAR, 2, 1), base="0.00", retencion="0.00"),
        )  # fmt: skip
    elif modelo == "190":
        _store_percepciones(
            objects, "111", Period.from_year_and_code(_YEAR, "1T"),
            _percepcion(perceptor=_EMPLOYEE, clave="A", source_id="a-zero", paid_on=date(_YEAR, 3, 10), percibido="0.00", retencion="0.00"),
        )  # fmt: skip
    else:
        _store_percepciones(
            objects,
            "193",
            _ANNUAL,
            manual_capital_row(filing_year=_YEAR, base=Decimal("0.00"), retencion=Decimal("0.00")),
        )


_ANNUAL_SOURCES = pytest.mark.parametrize(
    ("modelo", "source_family"),
    [
        ("180", BindingSourceKind.RETENCIONES_AGGREGATION.value),
        ("190", BindingSourceKind.WITHHOLDING.value),
        ("193", BindingSourceKind.WITHHOLDING.value),
    ],
)


@_ANNUAL_SOURCES
def test_an_empty_store_is_reported_as_missing_data(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, modelo: str, source_family: str
) -> None:
    """No stored row for the source the calculation reads warns, naming modelo, revision and source."""
    with _operator_bucket(tmp_path, authority_operation):
        payload, notices, status = _report(modelo)

    revision = authority_operation.revision_for_context(modelo, filing_year=_YEAR, period="0A")
    assert status == "warning"
    assert [(notice["code"], notice["severity"], notice["context"]) for notice in notices] == [
        (
            _ABSENT_CODE,
            "warning",
            {
                "filing_year": str(_YEAR),
                "modelo": modelo,
                "period": "0A",
                "reason": "stored_rows_absent",
                "revision": str(revision.id),
                "source_family": source_family,
            },
        ),
    ]
    assert payload["observation_count"] == 0
    assert payload["clave_breakdown"] == []


@_ANNUAL_SOURCES
def test_a_stored_zero_row_is_counted_and_not_reported_missing(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, modelo: str, source_family: str
) -> None:
    """A stored row whose amounts are zero is a proven zero: counted, and no absence warning."""
    with _operator_bucket(tmp_path, authority_operation) as (objects, _profile):
        _seed_zero_row(objects, modelo)
        payload, notices, status = _report(modelo)

    assert (notices, status) == ([], "success")
    if source_family == BindingSourceKind.RETENCIONES_AGGREGATION.value:
        assert payload["observation_count"] == 1
        assert payload["result_row_count"] == 1
    else:
        ((count, percibido, retencion),) = _breakdown(payload).values()
        assert (count, percibido, retencion) == (1, Decimal("0"), Decimal("0"))


_INVOICE_REFUSAL = re.compile(r"for Modelos (?P<accepted>[0-9, ]+) only; modelo (?P<modelo>[0-9]+) does not accept")


def _invoice_evidence_request() -> str:
    """A well-formed request naming an invoice no catalogue holds: only the modelo guard can decide it."""
    return InvoiceWithholdingEvidenceRequest(
        invoice_id="a" * 64,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme="actividades_profesionales",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="synthetic-payment",
        payment_occurred_on=date(_YEAR, 3, 31),
        allocation_id="synthetic-allocation",
        allocated_base=Decimal("1000.00"),
        allocated_withholding=Decimal("150.00"),
        allocated_settlement=Decimal("850.00"),
        idempotency_key="synthetic-capture",
    ).model_dump_json()


def test_the_invoice_evidence_refusal_names_exactly_the_modelos_that_accept_it(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The accepting set is observed from behaviour, then compared with the list the refusal names."""
    request = _invoice_evidence_request()
    named: dict[str, frozenset[str]] = {}
    refused_elsewhere: set[str] = set()
    with _operator_bucket(tmp_path, authority_operation):
        for modelo in ("111", "115", "123", "180", "190", "193"):
            result = invoke_cached_cli(
                [
                    "--format", "json", "--language", "en",
                    "app", "modelo", "aggregate",
                    "--modelo", modelo, "--year", str(_YEAR),
                    "--period", "0A" if modelo in {"180", "190", "193"} else "1T",
                    "--received-invoice-retencion", request,
                ],
            )  # fmt: skip
            assert result.exit_code != 0, result.output
            if match := _INVOICE_REFUSAL.search(result.output):
                assert match["modelo"] == modelo
                named[modelo] = frozenset(match["accepted"].split(", "))
            elif "invoice evidence is refused" in result.output:
                refused_elsewhere.add(modelo)

    accepting = {"111", "115", "123", "180", "190", "193"} - set(named) - refused_elsewhere
    assert refused_elsewhere == {"123"}
    assert set(named) == {"180", "190", "193"}
    assert set(named.values()) == {frozenset(accepting)}
    assert accepting == {"111", "115"}
