"""``modelo aggregate`` reports the stored withholding rows an annual summary's calculation reads.

Modelos 180, 190 and 193 are composed from stored windows rather than typed in:
180 from the year's Modelo 115 retención windows, 190 from the year's Modelo 111
per-perceptor-clave windows, and 193 from its own per-perceptor-clave window
(plus, in the editions that bind it, its own retención window). Each test enrols
a profile served by its native worker, seeds its real encrypted stores with
synthetic rows, including rows the calculation must NOT read, runs the live CLI
through the registered aggregate operation, and compares the report with what
the real calculation resolver materialises from the same stores.

An empty store and a stored zero are different facts: the first must reach the
operator as a structured warning naming the source the calculation reads, the
second is a counted row with zero amounts and no warning.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import manual_capital_row
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import withholding_work_profile
from cadrumo.application.modelo.aggregate_contracts import MODELO_AGGREGATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts

from ....adapters.persistence.profile.tests.percepcion_observation_authoring import replace_percepcion_observations
from ....adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
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
from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.user_profile.values import ProfileSetupState
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ...adapter_composition import build_percepcion_observation_ports, build_retencion_observation_ports
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

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


type _Seed = Callable[[str], None]


def _no_rows(_bucket_id: str) -> None:
    return None


def _aggregate_scope(client_id: UUID) -> AccessScope:
    """Grant the aggregate read and the invoice capture route the refusal case probes."""
    operations = (MODELO_AGGREGATE_OPERATION_DEFINITION_ID, MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID)
    return AccessScope(
        operations=frozenset(operations),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in operations
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _operator_profile_preparer(operation: PinnedAuthorityOperation, seed: _Seed) -> Callable[[UUID, Path], None]:
    """Complete the readiness-baseline profile the resolver context mirrors, then seed its stores."""

    def prepare(profile_id: UUID, root: Path) -> None:
        facts = complete_profile_facts(operation.profile_schema(), MODELO_READY_PROFILE_FACTS)
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                populated.profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        seed(str(profile_id))

    return prepare


def _operator_session(tmp_path: Path, operation: PinnedAuthorityOperation, seed: _Seed = _no_rows):
    return native_api_cli_session(
        tmp_path,
        scope_for_destination=_aggregate_scope,
        prepare_profile=_operator_profile_preparer(operation, seed),
        profile_label="Annual withholding report",
    )


def _aggregate(session: NativeApiCliSession[None], modelo: str, *options: str) -> Result:
    return session.invoke_password(
        "--language", "en",
        "app", "modelo", "aggregate",
        "--modelo", modelo, "--year", str(_YEAR), "--period", "0A" if modelo in {"180", "190", "193"} else "1T",
        *options,
    )  # fmt: skip


def _report(session: NativeApiCliSession[None], modelo: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the aggregate payload and the notices the aggregate itself raised.

    Every password-authenticated command also notes that its authentication is
    not persisted; that notice belongs to the credential channel, not to the report.
    """
    result = _aggregate(session, modelo)
    assert result.exit_code == 0, result.output
    notices = [notice for notice in unwrap_envelope_notices(result.output) if notice["code"].startswith("modelo.")]
    return unwrap_schema_envelope(result.output), notices


def _context(bucket_id: str, modelo: str, operation: PinnedAuthorityOperation) -> CalculationSourceContext:
    profile: ModeloWorkProfile = withholding_work_profile(operation, profile_id=bucket_id)
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=_YEAR,
        period=_ANNUAL,
        revision=operation.revision_for_context(modelo, filing_year=_YEAR, period="0A"),
        profile=profile,
    )


def _calculated_retenciones(
    session: NativeApiCliSession[None], modelo: str, operation: PinnedAuthorityOperation
) -> CalculationSourceResolution:
    bucket_id = str(session.profile_id)
    with password_profile_session(session.profile_id, operation):
        return RetencionesAggregationSourceResolver(
            ports=build_retencion_observation_ports(bucket_id=bucket_id)
        ).resolve(_context(bucket_id, modelo, operation))


def _calculated_percepciones(
    session: NativeApiCliSession[None], modelo: str, operation: PinnedAuthorityOperation
) -> CalculationSourceResolution:
    bucket_id = str(session.profile_id)
    with password_profile_session(session.profile_id, operation):
        return WithholdingSourceResolver(
            ports=build_percepcion_observation_ports(bucket_id=bucket_id),
            retencion_ports=build_retencion_observation_ports(bucket_id=bucket_id),
        ).resolve(_context(bucket_id, modelo, operation))


def _binding_id_for_fact(revision: ModeloRevision, source: BindingSourceKind, fact: str) -> str:
    (binding_id,) = (
        binding.id
        for binding in revision.bindings
        if binding.source == source and getattr(binding.provider, "fact", None) == fact
    )
    return binding_id


def _store_retenciones(bucket_id: str, modelo: str, period: Period, *rows: RetencionObservation) -> None:
    replace_retencion_observations(
        build_retencion_observation_ports(bucket_id=bucket_id).repository,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        observations=rows,
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _store_percepciones(bucket_id: str, modelo: str, period: Period, *rows: WithholdingObservation) -> None:
    replace_percepcion_observations(
        build_percepcion_observation_ports(bucket_id=bucket_id).repository,
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

    def seed(bucket_id: str) -> None:
        _store_retenciones(
            bucket_id, "115", Period.from_year_and_code(_YEAR, "1T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-a-q1", accrued_on=date(_YEAR, 2, 1), base="1000.00", retencion="190.00"),
        )  # fmt: skip
        _store_retenciones(
            bucket_id, "115", Period.from_year_and_code(_YEAR, "2T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-a-q2", accrued_on=date(_YEAR, 5, 1), base="1000.00", retencion="190.00"),
            _rent(landlord=_LANDLORD_B, source_id="rent-b-q2", accrued_on=date(_YEAR, 5, 1), base="500.00", retencion="95.00"),
        )  # fmt: skip
        _store_retenciones(
            bucket_id, "115", Period.from_year_and_code(_YEAR - 1, "4T"),
            _rent(landlord=_LANDLORD_OTHER_YEAR, source_id="rent-prior", accrued_on=date(_YEAR - 1, 11, 1), base="700.00", retencion="133.00"),
        )  # fmt: skip
        _store_retenciones(
            bucket_id, "180", _ANNUAL,
            _rent(landlord=_LANDLORD_OWN_WINDOW, source_id="rent-own", accrued_on=date(_YEAR, 7, 1), base="900.00", retencion="171.00"),
        )  # fmt: skip

    with _operator_session(tmp_path, authority_operation, seed) as session:
        payload, notices = _report(session, "180")
        calculated = _calculated_retenciones(session, "180", authority_operation)

    # Three stored 115 rows of the year, two landlords: A twice and B once.
    assert payload["provider"] == "retenciones"
    assert payload["observation_count"] == 3
    assert payload["result_row_count"] == 2
    assert payload["clave_breakdown"] == []
    assert notices == []
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

    def seed(bucket_id: str) -> None:
        _store_percepciones(
            bucket_id, "111", Period.from_year_and_code(_YEAR, "1T"),
            _percepcion(perceptor=_PROFESSIONAL, clave="G", source_id="g-q1", paid_on=date(_YEAR, 3, 10), percibido="1000.00", retencion="150.00"),
        )  # fmt: skip
        _store_percepciones(
            bucket_id, "111", Period.from_year_and_code(_YEAR, "3T"),
            _percepcion(perceptor=_EMPLOYEE, clave="A", source_id="a-q3", paid_on=date(_YEAR, 8, 10), percibido="2000.00", retencion="300.00"),
            _percepcion(perceptor=_PROFESSIONAL, clave="G", source_id="g-q3", paid_on=date(_YEAR, 8, 10), percibido="500.00", retencion="75.00"),
        )  # fmt: skip
        _store_percepciones(
            bucket_id, "111", Period.from_year_and_code(_YEAR - 1, "4T"),
            _percepcion(perceptor=_PERCEPTOR_OTHER_YEAR, clave="A", source_id="a-prior", paid_on=date(_YEAR - 1, 11, 10), percibido="800.00", retencion="120.00"),
        )  # fmt: skip
        _store_percepciones(
            bucket_id, "190", _ANNUAL,
            _percepcion(perceptor=_PERCEPTOR_OWN_WINDOW, clave="A", source_id="a-own", paid_on=date(_YEAR, 9, 10), percibido="600.00", retencion="90.00"),
        )  # fmt: skip

    with _operator_session(tmp_path, authority_operation, seed) as session:
        payload, notices = _report(session, "190")
        calculated = _calculated_percepciones(session, "190", authority_operation)

    # Clave G: one perceptor paid twice is one percepción; clave A: the employee.
    assert _breakdown(payload) == {
        "A": (1, Decimal("2000.00"), Decimal("300.00")),
        "G": (1, Decimal("1500.00"), Decimal("225.00")),
    }
    # Modelo 190's calculation reads no retención rows, so its retenciones summary is empty by construction.
    assert payload["observation_count"] == 0
    assert notices == []
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

    def seed(bucket_id: str) -> None:
        _store_percepciones(bucket_id, "193", _ANNUAL, first, second)
        _store_retenciones(
            bucket_id, "193", _ANNUAL,
            _rent(landlord=_LANDLORD_OWN_WINDOW, source_id="unread", accrued_on=date(_YEAR, 4, 1), base="100.00", retencion="19.00"),
        )  # fmt: skip

    with _operator_session(tmp_path, authority_operation, seed) as session:
        payload, notices = _report(session, "193")
        calculated = _calculated_percepciones(session, "193", authority_operation)
        calculated_retenciones = _calculated_retenciones(session, "193", authority_operation)

    clave = str(first.clave)
    expected_percibido = first.percibido_dinerario + second.percibido_dinerario
    expected_retencion = first.retencion_practicada + second.retencion_practicada
    assert _breakdown(payload) == {clave: (2, expected_percibido, expected_retencion)}
    assert len(calculated.provenance) == 2
    assert payload["observation_count"] == 0
    assert calculated_retenciones.binding_values == {}
    assert notices == []


def _seed_zero_row(bucket_id: str, modelo: str) -> None:
    if modelo == "180":
        _store_retenciones(
            bucket_id, "115", Period.from_year_and_code(_YEAR, "1T"),
            _rent(landlord=_LANDLORD_A, source_id="rent-zero", accrued_on=date(_YEAR, 2, 1), base="0.00", retencion="0.00"),
        )  # fmt: skip
    elif modelo == "190":
        _store_percepciones(
            bucket_id, "111", Period.from_year_and_code(_YEAR, "1T"),
            _percepcion(perceptor=_EMPLOYEE, clave="A", source_id="a-zero", paid_on=date(_YEAR, 3, 10), percibido="0.00", retencion="0.00"),
        )  # fmt: skip
    else:
        _store_percepciones(
            bucket_id,
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
    with _operator_session(tmp_path, authority_operation) as session:
        payload, notices = _report(session, modelo)

    revision = authority_operation.revision_for_context(modelo, filing_year=_YEAR, period="0A")
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
    with _operator_session(
        tmp_path, authority_operation, lambda bucket_id: _seed_zero_row(bucket_id, modelo)
    ) as session:
        payload, notices = _report(session, modelo)

    assert notices == []
    if source_family == BindingSourceKind.RETENCIONES_AGGREGATION.value:
        assert payload["observation_count"] == 1
        assert payload["result_row_count"] == 1
    else:
        ((count, percibido, retencion),) = _breakdown(payload).values()
        assert (count, percibido, retencion) == (1, Decimal("0"), Decimal("0"))


def _catalogue_pattern(translation_key: str, **groups: str) -> re.Pattern[str]:
    """Match the live English catalogue text of ``translation_key``, capturing the named placeholders."""
    template = lookup_translation(translation_key, locale="en")
    assert template is not None, translation_key
    pattern = re.escape(template)
    for name, group in groups.items():
        pattern = pattern.replace(re.escape(f"%{{{name}}}"), f"(?P<{name}>{group})")
    return re.compile(pattern)


_WRONG_MODELO_REFUSAL = _catalogue_pattern(
    "cli.app.modelo.aggregate.invoice_retencion_wrong_modelo", accepted_modelos=r"[0-9, ]+", modelo=r"[0-9]+"
)
_M123_REFUSAL = _catalogue_pattern("cli.app.modelo.aggregate.m123_ledger_payment_only")


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
    with _operator_session(tmp_path, authority_operation) as session:
        for modelo in ("111", "115", "123", "180", "190", "193"):
            result = _aggregate(session, modelo, "--received-invoice-retencion", request)
            assert result.exit_code != 0, result.output
            message = json.loads(result.output)["error"]["message"]
            if match := _WRONG_MODELO_REFUSAL.search(message):
                assert match["modelo"] == modelo
                named[modelo] = frozenset(match["accepted_modelos"].split(", "))
            elif _M123_REFUSAL.search(message):
                refused_elsewhere.add(modelo)

    accepting = {"111", "115", "123", "180", "190", "193"} - set(named) - refused_elsewhere
    assert refused_elsewhere == {"123"}
    assert set(named) == {"180", "190", "193"}
    assert set(named.values()) == {frozenset(accepting)}
    assert accepting == {"111", "115"}
