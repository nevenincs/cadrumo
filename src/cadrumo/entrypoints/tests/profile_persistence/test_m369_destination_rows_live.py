"""Modelo 369 rows from the invoice catalogue to the emitted bytes, for each regime.

Each scenario calculates, verifies, exports and parses back through the real
services. The wire expectations are written out by hand from DR369: a line is
country (2), percentage (5: three integers and two decimals), code (1), base (17)
and cuota (17: fifteen integers and two decimals), with no decimal separator.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.fx.ecb_provider import EcbReferenceRateProvider
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.errors import AggregationValidationError
from cadrumo.application.aggregation.oss_ioss_wire_geometry import record_row_slots
from cadrumo.application.aggregation.tests.oss_rate_change_support import variant_pct
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.application.modelo.action_errors import AmendmentKindNotPermittedError
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_amendment_evidence import resolve_persisted_amendment_export_evidence
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_form import build_modelo_work_form
from cadrumo.application.modelo.work_form_field_vocabulary import address_key
from cadrumo.application.modelo.work_form_service import modelo_form_snapshot
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    build_modelo_work_review_casillas,
)
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo_work_progress_state import ModeloWorkProgressState
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.invoices.enums import InvoiceOperationDateRole, IvaRate, PaymentStatus, invoice_class_simplificada
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import TransactionKind
from cadrumo.domain.iva.oss import OssIossRegime
from cadrumo.domain.iva.rates import IVA_RATE_FACT_ID
from cadrumo.domain.iva.schema import InvoiceKind, IvaRateKind
from cadrumo.domain.modelos.calculation_revision_amendment import (
    AMENDMENT_DECLARATION_KINDS,
    CalculationRevisionAmendmentIdentity,
)
from cadrumo.domain.modelos.errors import ModeloExportError
from cadrumo.domain.modelos.verification_report import VerificationReport
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.tests.profile_persistence.dormant_resolver_live_support import (
    T0,
    T1,
    seed_ready_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.secure_store_baseline import (
    SeededDurableProfile,
    provision_seeded_profile,
    reopened_seeded_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.tests.ecb_stub import ecb_csv_fetch

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "36900000-0000-4000-8000-000000000019"
_YEAR = filing_year_envelope().horizon
_SUPPLY = date(_YEAR, 2, 17)
_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("GENERAL"))


@dataclass(frozen=True)
class _Scenario:
    revision_id: str
    period_code: str
    regime: str
    kind: str
    fichero: str
    page_tag: bytes
    first_position: int
    total_casilla: str
    declarant: dict[str, str]
    period_number: str
    record: str


_EXTERIOR = _Scenario(
    "esquema-exterior",
    "EXT-1T",
    "external_scheme",
    "external_scheme_services",
    "modelo-369-exterior-fichero",
    b"<T36901>",
    221,
    "iva.exterior.cuota-total",
    {
        "regimen": "VOES",
        "categoria": "D",
        "1-declarante-pais": "US",
        "1-declarante-numero-de-operador-en-el-regimen-neuoss": "EU724000000001",
    },
    "1",
    "modelo-369-exterior-t36901",
)
_UNION = _Scenario(
    "esquema-union",
    "1T",
    "union_scheme",
    "oss_union_services",
    "modelo-369-union-fichero",
    b"<T36904>",
    222,
    "iva.union.cuota-total",
    {"regimen": "MOSS", "categoria": "D", "1-declarante-pais": "ES"},
    "1",
    "modelo-369-union-t36904",
)
_IMPORT = _Scenario(
    "esquema-importacion",
    "02",
    "import_scheme",
    "ioss_distance_sale_low_value",
    "modelo-369-importacion-fichero",
    b"<T36910>",
    253,
    "iva.importacion.cuota-total",
    {
        "regimen": "IMPO",
        "categoria": "D",
        "1-declarante-pais": "ES",
        "1-declarante-numero-de-operador-en-el-regimen-nioss": "IM7240000001",
        "1-actua-a-traves-de-intermediario": "1",
        "1-no-de-identificacion-del-intermediario-niossin": "IN7240000001",
    },
    "2",
    "modelo-369-importacion-t36910",
)
_SCENARIOS = (_EXTERIOR, _UNION, _IMPORT)
_ids = [scenario.revision_id for scenario in _SCENARIOS]


@pytest.fixture(scope="module", name="_seeded_profile")
def seeded_profile(tmp_path_factory: pytest.TempPathFactory) -> SeededDurableProfile:
    return provision_seeded_profile(
        tmp_path_factory.mktemp("m369-rows"),
        _BUCKET,
        lambda profile: seed_ready_profile(
            profile.repository,
            bucket_id=_BUCKET,
            # Modelo 369 applies only to a filer enrolled in the OSS/IOSS special regime.
            extra_facts=(UserProfileFact(path="iva.oss_enrolled", value=True),),
        ),
    )


@pytest.fixture
def objects(_seeded_profile: SeededDurableProfile) -> Iterator[SecureObjectRepository]:
    with reopened_seeded_profile(_seeded_profile) as profile:
        yield profile.repository


def _invoice(
    scenario: _Scenario,
    number: str,
    country: str,
    tier: str,
    base: str,
    cuota: str,
    *,
    currency: str = "EUR",
    fx_stamp: dict[str, object] | None = None,
    supply: date = _SUPPLY,
) -> Invoice:
    amount, tax = Decimal(base), Decimal(cuota)
    return Invoice.model_validate(
        {
            "invoice_id": derive_invoice_id(
                kind=InvoiceKind.ISSUED,
                invoice_number=number,
                issued_at=supply,
                counterparty_tax_id=None,
                currency=currency,
                grand_total=amount + tax,
            ),
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": supply,
            "operation_date": supply,
            "operation_date_role": InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED"),
            "counterparty_name": "Consumidor ficticio",
            "invoice_class": invoice_class_simplificada(),
            "counterparty_country": country,
            "base_total": amount,
            "iva_total": tax,
            "grand_total": amount + tax,
            "currency": currency,
            "lines": (
                InvoiceLine(
                    description="Operación ficticia",
                    quantity=Decimal("1"),
                    unit_price=amount,
                    subtotal=amount,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    oss_rate_kind=IvaRateKind(tier),
                    iva_amount=tax,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime(scenario.regime),
            "oss_transaction_kind": TransactionKind(scenario.kind),
            **(fx_stamp or {}),
        }
    )


def _calculate(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    invoices: tuple[Invoice, ...],
    operation: PinnedAuthorityOperation,
    *,
    extra_rows: dict[str, Decimal] | None = None,
    extra_enums: dict[str, str] | None = None,
) -> tuple[BucketAggregationCalculationResult, WorkUnit]:
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=objects)
    invoice_repo.save(build_invoice_catalogue(invoices))
    events = BucketEventHistoryRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="369",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, scenario.period_code),
        revision_id=scenario.revision_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=events),
        clock=T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=events,
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
        invoice_repository=invoice_repo,
    ) as ports:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=ports,
            binding_values={**_period_rows(scenario), **(extra_rows or {})},
            enum_binding_values={
                **{f"{scenario.fichero}.{key}": value for key, value in scenario.declarant.items()},
                **(extra_enums or {}),
            },
            clock=T1,
        )
    return result, work_unit


def _period_rows(scenario: _Scenario) -> dict[str, Decimal]:
    """The one header row the operator answers; every regime derives its exercise and period from the work."""
    return {f"{scenario.fichero}.2-ejercicio-y-periodo-declaracion-sin-actividad": Decimal("0")}


def _cuota_bindings(scenario: _Scenario) -> list[str]:
    """Each line's cuota binding, in line order, found by the position DR369 prints."""
    revision = (
        published_authority_operation()
        .snapshot("369", filing_year=_YEAR, period=scenario.period_code, revision_id=scenario.revision_id)
        .revision
    )
    by_position = {
        binding.provider.offset: binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, ManualInputProvider) and binding.provider.record == scenario.record
    }
    return [by_position[scenario.first_position + 25 + 42 * row] for row in range(28)]


def _form_values(
    work_unit: WorkUnit, result: BucketAggregationCalculationResult, operation: PinnedAuthorityOperation
) -> dict[tuple[str, str], object]:
    """Read every value the operator's form shows, through the real review and form builders."""
    revision = result.revision
    snapshot = modelo_form_snapshot(
        operation, work_unit.modelo, work_unit.filing_year, work_unit.period, work_unit.revision_id
    )
    form = build_modelo_work_form(
        review=ModeloWorkReview(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            registry_revision_id=work_unit.revision_id,
            work_unit_id=work_unit.work_unit_id,
            calculation_revision_id=revision.calculation_revision_id,
            lifecycle_state=revision.state,
            verification_outcome=None,
            progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
            casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=revision, operation=operation),
            findings=(),
            blockers=(),
        ),
        snapshot=snapshot,
        revision=revision,
        layout=operation.form_layout("369", work_unit.revision_id),
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )
    return {address_key(field.address): field.value for field in form.fields()}


def _line(country: str, pct: str, code: str, base: str, cuota: str) -> bytes:
    return f"{country}{pct}{code}{base:0>17}{cuota:0>17}".encode("ascii")


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_two_states_at_both_rates_agree_from_calculation_to_bytes(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """France 20/10 and Poland 23/8. Cuotas: 22.00 + 3.00 + 23.00 + 4.00 = 52.00."""
    result, work_unit = _calculate(
        objects,
        scenario,
        (
            _invoice(scenario, "OSS-1", "FR", "general", "110.00", "22.00"),
            _invoice(scenario, "OSS-2", "FR", "reduced", "30.00", "3.00"),
            _invoice(scenario, "OSS-3", "PL", "general", "100.00", "23.00"),
            _invoice(scenario, "OSS-4", "PL", "reduced", "50.00", "4.00"),
        ),
        operation,
    )
    assert result.revision.source_issues == ()
    assert Decimal(result.revision.casilla_values[scenario.total_casilla]) == Decimal("52.00")

    form_values = _form_values(work_unit, result, operation)
    assert Decimal(str(form_values[("casilla", scenario.total_casilla)])) == Decimal("52.00")
    form_cuotas = [Decimal(str(form_values[("binding", binding_id)])) for binding_id in _cuota_bindings(scenario)[:4]]
    assert form_cuotas == [Decimal("22.00"), Decimal("3.00"), Decimal("23.00"), Decimal("4.00")]

    report = _verify(result)
    assert report.granted_verificado_completo is True, [
        (finding.message_locale_key, finding.message_facts) for finding in report.findings
    ]

    wire = _export(objects, tmp_path, scenario, result)
    start = wire.index(scenario.page_tag) + scenario.first_position - 1
    assert wire[start : start + 4 * 42] == (
        _line("FR", "02000", "S", "11000", "2200")
        + _line("FR", "01000", "R", "3000", "300")
        + _line("PL", "02300", "S", "10000", "2300")
        + _line("PL", "00800", "R", "5000", "400")
    )
    # DR369 note 7: every field of an empty line is blank, numbers included.
    assert wire[start + 4 * 42 : start + 5 * 42] == b" " * 42

    revision = (
        published_authority_operation()
        .snapshot("369", filing_year=_YEAR, period=scenario.period_code, revision_id=scenario.revision_id)
        .revision
    )
    cuota_bindings = _cuota_bindings(scenario)
    assert len(cuota_bindings) == 28
    parsed = parse_export_payload(revision.export_layouts[0], wire)
    amounts = [
        field.value
        for field in parsed.fields
        if field.binding_id in cuota_bindings and isinstance(field.value, Decimal)
    ]
    assert sorted(amounts) == [Decimal("3.00"), Decimal("4.00"), Decimal("22.00"), Decimal("23.00")]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_a_twenty_ninth_row_stops_the_calculation_before_any_byte(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    invoices = _published_rows(scenario, operation)[:29]
    assert len(invoices) == 29, "the published schedule cannot overflow the page"
    with pytest.raises(AggregationValidationError) as refused:
        _calculate(objects, scenario, invoices, operation)
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.detail_rows_exceed_page"


_CLOSE = date(_YEAR, 3, 31)
_MARCH_SUPPLY = date(_YEAR, 3, 3)
_STAMPED_AT_OPERATION_DATE: dict[str, object] = {
    "fx_rate": Decimal("0.2"),
    "fx_rate_date": _MARCH_SUPPLY,
    "fx_rate_source": "ecb_reference",
}


def _march(scenario: _Scenario) -> _Scenario:
    """Every regime's period that closes on 31 March, an ECB publication day."""
    return replace(scenario, period_code="03", period_number="3") if scenario is _IMPORT else scenario


def _zloty_invoice(scenario: _Scenario) -> Invoice:
    return _invoice(
        scenario,
        "OSS-PLN",
        "PL",
        "general",
        "400.00",
        "92.00",
        currency="PLN",
        fx_stamp=_STAMPED_AT_OPERATION_DATE,
        supply=_MARCH_SUPPLY,
    )


def _verify(result: BucketAggregationCalculationResult) -> VerificationReport:
    with bundled_indexed_authority().operation() as verification_operation:
        return verify_modelo_revision_with_preconditions(
            result.revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="m369-rows-reviewer",
            workflow_profile=_profile(),
            clock=T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=verification_operation,
        ).report


def _export(
    objects: SecureObjectRepository, tmp_path: Path, scenario: _Scenario, result: BucketAggregationCalculationResult
) -> bytes:
    output_path = tmp_path / f"modelo-369-{scenario.revision_id}.txt"
    with bundled_indexed_authority().operation() as export_operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-rows-exporter",
            ),
            workflow_profile=_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_BUCKET,
                secure_objects=objects,
                work_unit=WorkUnitCatalogueRepository(objects=objects),
                calculation=CalculationRevisionCatalogueRepository(objects=objects),
            ),
            operation=export_operation,
        )
    return output_path.read_bytes()


@pytest.mark.parametrize("scenario", [_march(scenario) for scenario in _SCENARIOS], ids=_ids)
def test_a_foreign_invoice_files_at_the_period_close_rate_not_its_stamp(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """LIVA art. 163 noniesdecies.Uno.c) and siblings: 1 EUR = 4 PLN on 31 March.

    400.00 PLN is 100.00 EUR and 92.00 PLN is 23.00 EUR; the invoice's own stamp
    of 0.20 would have filed 80.00 and 18.40.
    """
    provider = EcbReferenceRateProvider(fetch=ecb_csv_fetch({"PLN": {_CLOSE: Decimal("4")}}))
    with bind_exchange_rate_provider_factory(lambda: provider):
        result, _ = _calculate(objects, scenario, (_zloty_invoice(scenario),), operation)
        assert Decimal(result.revision.casilla_values[scenario.total_casilla]) == Decimal("23.00")
        assert _verify(result).granted_verificado_completo is True
        wire = _export(objects, tmp_path, scenario, result)
    start = wire.index(scenario.page_tag) + scenario.first_position - 1
    assert wire[start : start + 42] == _line("PL", "02300", "S", "10000", "2300")


@pytest.mark.parametrize("scenario", [_march(scenario) for scenario in _SCENARIOS], ids=_ids)
def test_a_missing_period_close_rate_refuses_and_the_stamp_does_not_stand_in(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    provider = EcbReferenceRateProvider(fetch=ecb_csv_fetch({"PLN": {date(_YEAR, 3, 30): Decimal("4")}}))
    with bind_exchange_rate_provider_factory(lambda: provider), pytest.raises(AggregationValidationError) as refused:
        _calculate(objects, scenario, (_zloty_invoice(scenario),), operation)
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.invoice_line_currency_unconverted"
    assert refused.value.context is not None
    assert refused.value.context["rate_date"] == _CLOSE.isoformat()


def test_a_consignment_exactly_at_the_ceiling_files(
    objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """LIVA art. 163 quinvicies.Uno admits a value that does not exceed 150 euros: 20% of 150.00 is 30.00."""
    result, _ = _calculate(
        objects, _IMPORT, (_invoice(_IMPORT, "IOSS-150", "FR", "general", "150.00", "30.00"),), operation
    )
    assert Decimal(result.revision.casilla_values[_IMPORT.total_casilla]) == Decimal("30.00")


def test_a_consignment_a_cent_over_the_ceiling_refuses_before_any_figure(
    objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(AggregationValidationError) as refused:
        _calculate(objects, _IMPORT, (_invoice(_IMPORT, "IOSS-OVER", "FR", "general", "150.01", "30.00"),), operation)
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.consignment_exceeds_ceiling"
    assert refused.value.context is not None
    assert refused.value.context["consignment_value_eur"] == "150.01"


def test_the_ceiling_belongs_to_the_import_regime_alone(
    objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    result, _ = _calculate(
        objects, _UNION, (_invoice(_UNION, "OSS-BIG", "FR", "general", "1000.00", "200.00"),), operation
    )
    assert Decimal(result.revision.casilla_values[_UNION.total_casilla]) == Decimal("200.00")


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_an_amended_return_refuses_export_because_the_design_cannot_declare_it(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Orden HAC/610/2021 art. 7.5: a filed return is never modified, whichever amendment kind is asked for."""
    result, work_unit = _calculate(
        objects, scenario, (_invoice(scenario, "OSS-A", "FR", "general", "100.00", "20.00"),), operation
    )
    ports = modelo_export_ports_for_test(
        bucket_id=_BUCKET,
        secure_objects=objects,
        work_unit=WorkUnitCatalogueRepository(objects=objects),
        calculation=CalculationRevisionCatalogueRepository(objects=objects),
    )
    for kind in AMENDMENT_DECLARATION_KINDS:
        amended = result.revision.model_copy(
            update={
                "amendment_identity": CalculationRevisionAmendmentIdentity(
                    kind=kind, amends_filing_record_id="a" * 64, m303_rectificativa_motive=None
                )
            }
        )
        with pytest.raises(AmendmentKindNotPermittedError) as refused:
            resolve_persisted_amendment_export_evidence(
                ModeloExportCommand(
                    calculation_revision_id=amended.calculation_revision_id,
                    output_path=Path("nunca-escrito.txt"),
                    actor="m369-rows-exporter",
                ),
                amended,
                work_unit=work_unit,
                workflow_profile=_profile(),
                work_unit_repository=ports.work_unit,
                filing_repository=ports.filing,
                justificante_repository=None,
                operation=operation,
            )
        assert refused.value.translated_message == "application.modelo.errors.amendment_later_period_only"


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_an_ordinary_single_page_return_leaves_every_page_indicator_blank(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    result, _ = _calculate(
        objects, scenario, (_invoice(scenario, "OSS-A", "FR", "general", "100.00", "20.00"),), operation
    )
    assert _verify(result).granted_verificado_completo is True
    wire = _export(objects, tmp_path, scenario, result)
    revision = (
        published_authority_operation()
        .snapshot("369", filing_year=_YEAR, period=scenario.period_code, revision_id=scenario.revision_id)
        .revision
    )
    markers = [
        field
        for field in parse_export_payload(revision.export_layouts[0], wire).fields
        if field.field_id.endswith("complementaria")
    ]
    assert markers
    assert {field.value for field in markers} == {" "}


@pytest.mark.parametrize(
    ("scenario", "printed"),
    [
        (_EXTERIOR, f"{_YEAR}T01".encode("ascii")),
        (_UNION, f"{_YEAR}T01".encode("ascii")),
        (_IMPORT, f"{_YEAR}M02".encode("ascii")),
    ],
    ids=_ids,
)
def test_the_period_rows_print_the_work_units_period_when_nobody_entered_them(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    printed: bytes,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """DR369: Ejercicio (4), Tipo de periodo (1), Periodo (2), consecutive on each regime's first page."""
    result, _ = _calculate(
        objects, scenario, (_invoice(scenario, "OSS-P", "FR", "general", "100.00", "20.00"),), operation
    )
    assert _verify(result).granted_verificado_completo is True
    wire = _export(objects, tmp_path, scenario, result)
    assert printed in wire[wire.index(scenario.page_tag) : wire.index(scenario.page_tag) + scenario.first_position]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_an_entered_period_contradicting_the_work_blocks_verification_by_name(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    result, _ = _calculate(
        objects,
        scenario,
        (_invoice(scenario, "OSS-W", "FR", "general", "100.00", "20.00"),),
        operation,
        extra_rows={f"{scenario.fichero}.2-ejercicio-y-periodo-ejercicio": Decimal(_YEAR + 1)},
    )
    report = _verify(result)
    assert report.granted_verificado_completo is False
    assert "application.modelo.findings.scheme_period_contradicted" in {
        finding.message_locale_key for finding in report.findings
    }


_NO_ACTIVITY_POSITION = {_EXTERIOR.revision_id: 220, _UNION.revision_id: 221, _IMPORT.revision_id: 252}


def _declaring_no_activity(scenario: _Scenario) -> dict[str, Decimal]:
    return {f"{scenario.fichero}.2-ejercicio-y-periodo-declaracion-sin-actividad": Decimal("1")}


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_a_declared_nil_period_files_blank_rows_and_a_zero_total(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """LIVA arts. 163 noniesdecies, duovicies, septvicies and Orden HAC/610/2021 art. 7.4: a nil return is still due."""
    result, _ = _calculate(objects, scenario, (), operation, extra_rows=_declaring_no_activity(scenario))
    report = _verify(result)
    assert report.granted_verificado_completo is True, [f.message_locale_key for f in report.findings]
    wire = _export(objects, tmp_path, scenario, result)
    page = wire.index(scenario.page_tag)
    flag = _NO_ACTIVITY_POSITION[scenario.revision_id]
    assert wire[page + flag - 1 : page + flag] == b"1"
    start = page + scenario.first_position - 1
    assert wire[start : start + 28 * 42] == b" " * (28 * 42)
    assert Decimal(result.revision.casilla_values[scenario.total_casilla]) == Decimal("0")


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_an_empty_period_nobody_declared_stays_blocked(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """No invoices is not proof of no activity, so the zero stays unproven until the operator says so."""
    result, _ = _calculate(objects, scenario, (), operation)
    assert "application.modelo.findings.oss_evidence_missing" in {
        finding.message_locale_key for finding in _verify(result).findings
    }


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_declaring_no_activity_beside_an_invoice_is_a_named_contradiction(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    result, _ = _calculate(
        objects,
        scenario,
        (_invoice(scenario, "OSS-N", "FR", "general", "100.00", "20.00"),),
        operation,
        extra_rows=_declaring_no_activity(scenario),
    )
    report = _verify(result)
    assert report.granted_verificado_completo is False
    assert "application.modelo.findings.oss_no_activity_contradicted" in {
        finding.message_locale_key for finding in report.findings
    }


def test_a_direct_ioss_filer_without_intermediary_number_still_refuses_at_export(
    objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """DR369 T36910 marks NIOSSIn obligatory with no alternative content and never names the filer's own number."""
    declarant = {
        key: value
        for key, value in _IMPORT.declarant.items()
        if key != "1-no-de-identificacion-del-intermediario-niossin"
    }
    scenario = replace(_IMPORT, declarant={**declarant, "1-actua-a-traves-de-intermediario": "0"})
    result, _ = _calculate(
        objects, scenario, (_invoice(scenario, "IOSS-D", "FR", "general", "100.00", "20.00"),), operation
    )
    assert _verify(result).granted_verificado_completo is True
    with pytest.raises(ModeloExportError) as refused:
        _export(objects, tmp_path, scenario, result)
    assert refused.value.translated_message == "application.modelo.errors.export_draft_write_failed"
    assert not (tmp_path / f"modelo-369-{scenario.revision_id}.txt").exists()


def _published_rows(scenario: _Scenario, operation: PinnedAuthorityOperation) -> tuple[Invoice, ...]:
    """Build one invoice per destination and tier the fact publishes on the supply date."""
    rows: list[tuple[str, str, Decimal]] = []
    for variant in operation.governed_fact(IVA_RATE_FACT_ID).variants:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        covers = (variant.valid_from or date.max) <= _SUPPLY and (
            variant.valid_to is None or variant.valid_to >= _SUPPLY
        )
        if (
            covers
            and selectors.get("kind") in {"general", "reduced"}
            and selectors.get("rate_role") == "ordinary"
            and selectors.get("member_state") != "es"
        ):
            rows.append((str(selectors["member_state"]), str(selectors["kind"]), variant_pct(variant)))
    return tuple(
        _invoice(scenario, f"OSS-BREADTH-{index}", state.upper(), tier, "100.00", f"{pct:.2f}")
        for index, (state, tier, pct) in enumerate(sorted(rows))
    )


@dataclass(frozen=True)
class _CorrectionPage:
    record: str
    tag: bytes
    prefix: str
    period_type: str
    period: str


_CORRECTION_PAGES = {
    _EXTERIOR.revision_id: _CorrectionPage("modelo-369-exterior-t36902", b"<T36902>", "iva.exterior", "T", "4"),
    _UNION.revision_id: _CorrectionPage("modelo-369-union-t36908", b"<T36908>", "iva.union", "T", "4"),
    _IMPORT.revision_id: _CorrectionPage("modelo-369-importacion-t36911", b"<T36911>", "iva.importacion", "M", "11"),
}
_PREVIOUS_YEAR_SUPPLY = date(_YEAR - 1, 11, 17)
_CORRECTION_ROW = 26


def _reducing(scenario: _Scenario) -> tuple[Invoice, Invoice]:
    """F-OLD, filed the year before at 1.000,00 + 200,00, and the rectificativa issued in this return's period."""
    first = _invoice(scenario, "F-OLD", "FR", "general", "1000.00", "200.00", supply=_PREVIOUS_YEAR_SUPPLY)
    correction = Invoice.model_validate(
        {
            **_invoice(scenario, "R-1", "FR", "general", "100.00", "20.00").model_dump(exclude={"invoice_id"}),
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "counterparty_tax_id": "FR40303265045",
            "rectifies_invoice_number": "F-OLD",
        }
    )
    return first, correction


def _correction_wire(scenario: _Scenario, country: str, cuota: str) -> bytes:
    page = _CORRECTION_PAGES[scenario.revision_id]
    return f"{country}{_YEAR - 1}{page.period_type}{page.period:<2}{cuota}".encode("ascii")


def _correction_page_rows(wire: bytes, scenario: _Scenario, count: int) -> bytes:
    start = wire.index(_CORRECTION_PAGES[scenario.revision_id].tag) + 9
    return wire[start : start + count * _CORRECTION_ROW]


def _parsed_correction_amounts(wire: bytes, scenario: _Scenario) -> list[Decimal]:
    revision = (
        published_authority_operation()
        .snapshot("369", filing_year=_YEAR, period=scenario.period_code, revision_id=scenario.revision_id)
        .revision
    )
    slots = record_row_slots(revision, _CORRECTION_PAGES[scenario.revision_id].record)
    amounts = {slot[4] for slot in slots}
    parsed = parse_export_payload(revision.export_layouts[0], wire)
    return [field.value for field in parsed.fields if field.binding_id in amounts and isinstance(field.value, Decimal)]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_a_reduction_of_an_earlier_period_settles_against_this_periods_services(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """France: services 50,00 this period, correction -20,00 of last year's, so 30,00 to pay."""
    page = _CORRECTION_PAGES[scenario.revision_id]
    result, _ = _calculate(
        objects,
        scenario,
        (
            *_reducing(scenario),
            _invoice(scenario, "OSS-1", "FR", "general", "125.00", "25.00"),
            _invoice(scenario, "OSS-2", "FR", "general", "125.00", "25.00"),
        ),
        operation,
    )
    values = result.revision.casilla_values
    assert result.revision.source_issues == ()
    assert Decimal(values[scenario.total_casilla]) == Decimal("50.00")
    assert Decimal(values[f"{page.prefix}.resultado.fr.correcciones-negativas"]) == Decimal("-20.00")
    assert Decimal(values[f"{page.prefix}.resultado.fr.correcciones-positivas"]) == Decimal("0")
    assert Decimal(values[f"{page.prefix}.resultado.fr.resultado"]) == Decimal("30.00")
    assert Decimal(values[f"{page.prefix}.resultado.fr.ingresar"]) == Decimal("30.00")
    report = _verify(result)
    assert report.granted_verificado_completo is True, [
        (finding.message_locale_key, finding.message_facts) for finding in report.findings
    ]

    wire = _export(objects, tmp_path, scenario, result)
    start = wire.index(scenario.page_tag) + scenario.first_position - 1
    assert wire[start : start + 42] == _line("FR", "02000", "S", "25000", "5000")
    assert _correction_page_rows(wire, scenario, 2) == _correction_wire(scenario, "FR", "-0000000000002000") + (
        b" " * _CORRECTION_ROW
    )
    assert _parsed_correction_amounts(wire, scenario) == [Decimal("-20.00")]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_a_reduction_above_the_periods_services_is_to_be_returned_by_that_state(
    objects: SecureObjectRepository,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """France: -20,00 with nothing to set it against, while Poland's 23,00 stays payable on its own."""
    page = _CORRECTION_PAGES[scenario.revision_id]
    result, _ = _calculate(
        objects,
        scenario,
        (*_reducing(scenario), _invoice(scenario, "OSS-3", "PL", "general", "100.00", "23.00")),
        operation,
    )
    values = result.revision.casilla_values
    assert Decimal(values[f"{page.prefix}.resultado.fr.resultado"]) == Decimal("-20.00")
    assert Decimal(values[f"{page.prefix}.resultado.fr.devolver"]) == Decimal("20.00")
    assert Decimal(values[f"{page.prefix}.resultado.fr.ingresar"]) == Decimal("0")
    assert Decimal(values[f"{page.prefix}.resultado.pl.ingresar"]) == Decimal("23.00")


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_ids)
def test_an_entered_increase_of_an_earlier_period_files_with_no_sign(
    objects: SecureObjectRepository,
    tmp_path: Path,
    scenario: _Scenario,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Poland: services 23,00 this period, +15,00 for last year's, so 38,00 to pay."""
    page = _CORRECTION_PAGES[scenario.revision_id]
    revision = (
        published_authority_operation()
        .snapshot("369", filing_year=_YEAR, period=scenario.period_code, revision_id=scenario.revision_id)
        .revision
    )
    country, year, period_type, period, cuota = record_row_slots(revision, page.record)[0]
    result, _ = _calculate(
        objects,
        scenario,
        (_invoice(scenario, "OSS-3", "PL", "general", "100.00", "23.00"),),
        operation,
        extra_rows={year: Decimal(_YEAR - 1), cuota: Decimal("15.00")},
        extra_enums={country: "PL", period_type: page.period_type, period: page.period},
    )
    values = result.revision.casilla_values
    assert Decimal(values[f"{page.prefix}.resultado.pl.correcciones-positivas"]) == Decimal("15.00")
    assert Decimal(values[f"{page.prefix}.resultado.pl.ingresar"]) == Decimal("38.00")
    report = _verify(result)
    assert report.granted_verificado_completo is True, [
        (finding.message_locale_key, finding.message_facts) for finding in report.findings
    ]
    wire = _export(objects, tmp_path, scenario, result)
    assert _correction_page_rows(wire, scenario, 1) == _correction_wire(scenario, "PL", "00000000000001500")
    assert _parsed_correction_amounts(wire, scenario) == [Decimal("15.00")]
