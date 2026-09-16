"""Live M369 OSS/IOSS resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_reads import InvoiceCatalogueReadAdapter
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests._dormant_resolver_live_support import (
    _T0,
    _T1,
    _revision,
    _seed_ready_profile,
)
from cadrumo.adapters.persistence.profile.tests._modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_injected_secure_object_repository,
    isolated_runtime_profile,
)
from cadrumo.application.aggregation import oss_ioss as oss_ioss_module
from cadrumo.application.aggregation.errors import (
    AggregationValidationError,
)
from cadrumo.application.aggregation.oss_ioss import (
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
)
from cadrumo.application.aggregation.source_mesh import (
    CalculationSourceContext,
)
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.ledger_oss_bindings import OssIossLedgerObservation
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.invoices.enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind, TransactionKind
from cadrumo.domain.iva.oss import OssIossRegime
from cadrumo.domain.iva.schema import IvaRateKind
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.transactions.models import LedgerDatePartition, TransactionCatalogue

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

# Chain 2 — M369 OSS/IOSS (ledger_oss_aggregation): live invoice projection
# ---------------------------------------------------------------------------

_M369_BUCKET = "36900000-0000-4000-8000-000000000013"
_M369_REVISION = "esquema-union"
_M369_YEAR = 2026
_DEFAULT_OSS_REGIME = OssIossRegime("union_scheme")


class _EmptyInvoiceCatalogueReader:
    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _empty_catalogue_read_ports() -> InvoiceCatalogueReadPorts:
    return InvoiceCatalogueReadPorts(
        invoice_reader=_EmptyInvoiceCatalogueReader(),
        transaction_reader=_EmptyTransactionCatalogueReader(),
    )


# Three DISTINCT OSS candidates whose persisted IVA matches the destination MS
# published rate (DE general 19%, FR general 20%): the resolver validates each
# against lookup_rate before aggregating, so the iva_amount must equal
# base * rate. Distinct bases -> distinct cuotas (19.00 / 40.00 / 57.00).
def _m369_candidate(
    *,
    ledger_id: str,
    transaction_date: date,
    destination_member_state: str,
    transaction_kind: str,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> OssIossLedgerCandidate:
    return OssIossLedgerCandidate.model_validate(
        {
            "ledger_id": ledger_id,
            "transaction_date": transaction_date,
            "regime": OssIossRegime("union_scheme"),
            "destination_member_state": destination_member_state,
            "rate_kind": IvaRateKind("general"),
            "invoice_direction": InvoiceKind.ISSUED,
            "transaction_kind": TransactionKind(transaction_kind),
            "base_amount": base_amount,
            "iva_amount": iva_amount,
        }
    )


def _m369_candidates() -> tuple[OssIossLedgerCandidate, ...]:
    return (
        _m369_candidate(
            ledger_id="oss-de-services",
            transaction_date=date(2026, 2, 15),
            destination_member_state="de",
            transaction_kind="oss_union_services",
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),  # 100 * 19% (DE general)
        ),
        _m369_candidate(
            ledger_id="oss-fr-services",
            transaction_date=date(2026, 2, 16),
            destination_member_state="fr",
            transaction_kind="oss_union_services",
            base_amount=Decimal("200.00"),
            iva_amount=Decimal("40.00"),  # 200 * 20% (FR general)
        ),
        _m369_candidate(
            ledger_id="oss-de-goods",
            transaction_date=date(2026, 2, 17),
            destination_member_state="de",
            transaction_kind="oss_union_goods_distance_sale",
            base_amount=Decimal("300.00"),
            iva_amount=Decimal("57.00"),  # 300 * 19% (DE general)
        ),
    )


_M369_DE_SERVICES_BINDING = "modelo-369-union-de-services-21pct"
_M369_FR_SERVICES_BINDING = "modelo-369-union-fr-services-21pct"
_M369_DE_GOODS_BINDING = "modelo-369-union-de-goods-distance-21pct"
_M369_CUOTA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.union.cuota-total")
# Casilla bound to the DE-services OSS binding (used by the carve-out test).
_M369_DE_SERVICES_BINDING_CASILLA: CasillaId = validated_casilla_id("iva.union.de.services-cuota")
_M369_FR_SERVICES_BINDING_CASILLA: CasillaId = validated_casilla_id("iva.union.fr.services-cuota")
_M369_DE_GOODS_BINDING_CASILLA: CasillaId = validated_casilla_id("iva.union.de.goods-distance-cuota")


def workflow_profile() -> TaxpayerProfile:
    """Return the real profile projection used by the M369 verify/export gates."""
    return TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("GENERAL"))


@pytest.fixture
def m369_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M369_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M369_BUCKET)
        yield profile.repository


def test_m369_oss_resolver_folds_real_candidates_at_mesh_boundary() -> None:
    """The OSS resolver folds REAL candidates into the bound casilla cuotas.

    This proves the resolver + binding chain is sound: three DISTINCT validated
    OSS candidates fold into their three distinct binding cuotas (DE services 19,
    FR services 40, DE goods 57). The fold is NON-tautological — distinct seeds,
    asserted as the per-binding sum of the validated candidate cuotas, never a
    re-evaluation of a registry formula. The gap proven in the companion test
    below is solely the LIVE-PATH candidate source, not this fold.
    """
    revision = _revision("369", _M369_REVISION)
    with bundled_indexed_authority().operation():
        candidates = _m369_candidates()

        # Resolver path (what the live mesh WOULD fold if it had candidates).
        resolution = OssIossLedgerSourceResolver(
            ports=_empty_catalogue_read_ports(),
            candidates=candidates,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_M369_BUCKET,
                modelo="369",
                filing_year=_M369_YEAR,
                period=Period.from_year_and_code(_M369_YEAR, "1T"),
                revision=revision,
            ),
        )
        # Cross-check the registry aggregation wrapper agrees with the resolver.
        aggregated = aggregate_oss_ioss_bindings(revision, candidates)
    assert resolution.binding_values[_M369_DE_SERVICES_BINDING] == Decimal("19.00")
    assert resolution.binding_values[_M369_FR_SERVICES_BINDING] == Decimal("40.00")
    assert resolution.binding_values[_M369_DE_GOODS_BINDING] == Decimal("57.00")
    assert aggregated == dict(resolution.binding_values)
    # The source is claimed; the resolver raises nothing and emits no diagnostics.
    assert resolution.diagnostics == ()
    assert BindingSourceKind.LEDGER_OSS_AGGREGATION in resolution.owned_sources


def _m369_invoice(
    *,
    invoice_number: str,
    issued_at: date,
    counterparty_name: str,
    counterparty_tax_id: str,
    counterparty_country: str,
    transaction_kind: TransactionKind,
    base_amount: Decimal,
    iva_amount: Decimal,
    operation_date: date | None = None,
    regime: OssIossRegime = _DEFAULT_OSS_REGIME,
) -> Invoice:
    line = InvoiceLine(
        description=f"OSS supply {invoice_number}",
        quantity=Decimal("1"),
        unit_price=base_amount,
        subtotal=base_amount,
        iva_rate=IvaRate.from_registry("RATE_21"),
        oss_rate_kind=IvaRateKind("general"),
        iva_amount=iva_amount,
    )
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_amount + iva_amount,
    )
    return Invoice(
        invoice_id=invoice_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        base_total=base_amount,
        iva_total=iva_amount,
        grand_total=base_amount + iva_amount,
        currency="EUR",
        lines=(line,),
        payment_status=PaymentStatus.PAID,
        oss_ioss_regime=regime,
        oss_transaction_kind=transaction_kind,
        operation_date=operation_date,
        operation_date_role=(
            None if operation_date is None else InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED")
        ),
    )


@pytest.mark.parametrize(
    ("period_token", "operation_date", "issued_at", "expected_wire_period"),
    (
        ("EXT-1T", date(2026, 2, 15), date(2026, 5, 15), b"01"),
        ("EXT-2T", date(2026, 5, 15), date(2026, 8, 15), b"02"),
        ("EXT-3T", date(2026, 8, 15), date(2026, 11, 15), b"03"),
        ("EXT-4T", date(2026, 11, 15), date(2027, 2, 15), b"04"),
    ),
)
def test_m369_exterior_period_calculate_review_export_e2e(
    m369_objects: SecureObjectRepository,
    tmp_path: Path,
    period_token: str,
    operation_date: date,
    issued_at: date,
    expected_wire_period: bytes,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Every Exterior quarter retains its token and renders the official ordinal."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        build_invoice_catalogue(
            (
                _m369_invoice(
                    invoice_number=f"OSS-EXT-{period_token}",
                    issued_at=issued_at,
                    operation_date=operation_date,
                    counterparty_name="DE Exterior Consumer",
                    counterparty_tax_id=f"DE{period_token[-2]}23456789",
                    counterparty_country="DE",
                    transaction_kind=TransactionKind("external_scheme_services"),
                    base_amount=Decimal("100.00"),
                    iva_amount=Decimal("19.00"),
                    regime=OssIossRegime("external_scheme"),
                ),
            ),
        ),
    )
    period = Period.from_year_and_code(_M369_YEAR, period_token)
    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period=period,
        revision_id="esquema-exterior",
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_M369_BUCKET,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects),
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_311:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_311,
            clock=_T1,
        )
    period_casilla = validated_casilla_id("decl.periodo")
    exterior_cuota = validated_casilla_id("iva.exterior.de.services-cuota")
    assert result.revision.input_values_by_casilla_id[period_casilla] == period_token
    assert Decimal(result.revision.casilla_values[exterior_cuota]) == Decimal("19.00")

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            result.revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="m369-exterior-reviewer",
            workflow_profile=workflow_profile(),
            clock=_T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
    assert report.granted_verificado_completo is True, report.findings

    output_path = tmp_path / f"modelo-369-{period_token}.txt"
    with bundled_indexed_authority().operation() as operation:
        receipt = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-exterior-exporter",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_M369_BUCKET,
                secure_objects=m369_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
            ),
            operation=operation,
        )
    assert receipt.period.registry_token == period_token
    wire = output_path.read_bytes()
    assert wire[10:12] == expected_wire_period
    assert period_token.encode("ascii") not in wire
    layout = (
        compiled_bundled_authority()
        .snapshot("369", filing_year=_M369_YEAR, period=period_token, revision_id="esquema-exterior")
        .revision.export_layouts[0]
    )
    parsed = parse_export_payload(layout, wire)
    detail = tuple(field for field in parsed.fields if field.record_id == "modelo-369-exterior-t36901")

    def detail_value(offset_token: str) -> object:
        matches = [field.value for field in detail if offset_token in str(field.binding_id)]
        assert len(matches) == 1, [(field.field_id, field.binding_id, field.value) for field in detail]
        return matches[0]

    assert detail_value(".213-216.") == 2026
    assert detail_value(".217-217.") == "T"
    assert detail_value(".218-219.") == int(period_token[-2])
    assert detail_value(".221-222.") == "DE"
    assert detail_value(".223-227.") == Decimal("19")
    assert detail_value(".228-228.") == "S"
    assert detail_value(".229-245.") == Decimal("100")
    assert detail_value(".246-262.") == Decimal("19")
    record_ids = {field.record_id for field in parsed.fields}
    assert "modelo-369-exterior-t36902" not in record_ids
    assert "modelo-369-exterior-t36903" in record_ids
    closure_start = wire.index(b"<T36903>")
    malformed_optional = wire[:closure_start] + b"<T36902>" + wire[closure_start:]
    with pytest.raises(RegistryValidationError):
        parse_export_payload(layout, malformed_optional)


@pytest.mark.parametrize("unsupported_rate_kind", (IvaRateKind("super_reduced"), IvaRateKind("zero")))
def test_m369_exterior_refuses_rate_kinds_outside_official_standard_reduced_vocabulary(
    unsupported_rate_kind: IvaRateKind,
) -> None:
    """Exterior never guesses an R/S wire token for an unsupported classification."""
    with pytest.raises(AggregationValidationError) as exc_info, bundled_indexed_authority().operation() as operation:
        observation = OssIossLedgerObservation.model_validate(
            {
                "ledger_id": f"unsupported-{unsupported_rate_kind.value}",
                "transaction_date": date(2026, 2, 15),
                "regime": OssIossRegime("external_scheme"),
                "destination_member_state": "de",
                "rate_kind": unsupported_rate_kind,
                "invoice_direction": InvoiceKind.ISSUED,
                "transaction_kind": TransactionKind("external_scheme_services"),
                "base_amount": Decimal("100"),
                "iva_amount": Decimal("0"),
            }
        )
        oss_ioss_module._exterior_detail_binding_values(
            _revision("369", "esquema-exterior"),
            (observation,),
            operation=operation,
        )

    assert exc_info.value.translated_message == "aggregation.oss_ioss.errors.exterior_rate_kind_unsupported"
    assert exc_info.value.context is not None
    assert exc_info.value.context["rate_kind"] == unsupported_rate_kind.value


def test_m369_live_path_folds_oss_invoices_not_no_live_source_advisory(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Live M369 calculate and verification use the injected store."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path / "ambient", bucket_id=_M369_BUCKET) as runtime,
        isolated_injected_secure_object_repository(
            tmp_path=tmp_path / "injected",
            bucket_id=_M369_BUCKET,
            database_name="m369-injected.db",
        ) as injected_objects,
    ):
        _seed_ready_profile(runtime.repository, bucket_id=_M369_BUCKET)
        wu_repo = WorkUnitCatalogueRepository(objects=runtime.repository)
        cr_repo = CalculationRevisionCatalogueRepository(objects=runtime.repository)
        tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=runtime.repository)
        ambient_invoice_repo = InvoiceCatalogueRepository(objects=runtime.repository)
        invoice_repo = InvoiceCatalogueRepository(objects=injected_objects)
        invoice_repo.save(
            build_invoice_catalogue(
                (
                    _m369_invoice(
                        invoice_number="OSS-DE-SERV-001",
                        issued_at=date(2026, 2, 15),
                        counterparty_name="DE Consumer",
                        counterparty_tax_id="DE123456789",
                        counterparty_country="DE",
                        transaction_kind=TransactionKind("oss_union_services"),
                        base_amount=Decimal("100.00"),
                        iva_amount=Decimal("19.00"),
                    ),
                    _m369_invoice(
                        invoice_number="OSS-FR-SERV-001",
                        issued_at=date(2026, 2, 16),
                        counterparty_name="FR Consumer",
                        counterparty_tax_id="FR12345678901",
                        counterparty_country="FR",
                        transaction_kind=TransactionKind("oss_union_services"),
                        base_amount=Decimal("200.00"),
                        iva_amount=Decimal("40.00"),
                    ),
                    _m369_invoice(
                        invoice_number="OSS-DE-GOODS-001",
                        issued_at=date(2026, 2, 17),
                        counterparty_name="DE Consumer Goods",
                        counterparty_tax_id="DE987654321",
                        counterparty_country="DE",
                        transaction_kind=TransactionKind("oss_union_goods_distance_sale"),
                        base_amount=Decimal("300.00"),
                        iva_amount=Decimal("57.00"),
                    ),
                ),
            ),
        )
        assert ambient_invoice_repo.exists() is False

        work_unit = create_work_unit(
            bucket_id=_M369_BUCKET,
            modelo="369",
            filing_year=_M369_YEAR,
            period=Period.from_year_and_code(_M369_YEAR, "1T"),
            revision_id=_M369_REVISION,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(objects=runtime.repository),
            ),
            clock=_T0,
            operation=operation,
        )
        with calculation_ports_for_test(
            bucket_id=_M369_BUCKET,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=BucketEventHistoryRepository(objects=runtime.repository),
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
        ) as _calculation_ports_488:
            result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                ports=_calculation_ports_488,
                clock=_T1,
            )

        assert isinstance(result, BucketAggregationCalculationResult)
        casilla_values = result.revision.casilla_values
        component_cuotas = (
            Decimal(casilla_values[_M369_DE_SERVICES_BINDING_CASILLA]),
            Decimal(casilla_values[_M369_FR_SERVICES_BINDING_CASILLA]),
            Decimal(casilla_values[_M369_DE_GOODS_BINDING_CASILLA]),
        )
        assert component_cuotas == (Decimal("19.00"), Decimal("40.00"), Decimal("57.00"))
        assert Decimal(casilla_values[_M369_CUOTA_TOTAL_CASILLA]) == sum(component_cuotas, Decimal("0"))
        assert not any(
            diag.source_kind == "ledger_oss_aggregation" and diag.reason == "oss_no_live_source"
            for diag in result.source_diagnostics
        )
        assert not any(
            diag.source_kind == "ledger_oss_aggregation" and diag.reason == "unhandled_binding_source"
            for diag in result.source_diagnostics
        )

        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision(
                result.revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=build_test_verification_repository_bundle(),
                actor="m369-live-operator",
                workflow_profile=workflow_profile(),
                clock=_T1,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        assert ambient_invoice_repo.exists() is False
        assert any(
            ref.resolved_binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION
            for ref in result.revision.source_provenance
        ), result.revision.source_provenance
        assert result.revision.source_issues == ()
        assert report.granted_verificado_completo is True, report.findings
        assert wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id == (
            result.revision.calculation_revision_id
        )


def test_m369_oss_projection_follows_the_devengo_date_and_discloses_the_proxy(
    m369_objects: SecureObjectRepository,
) -> None:
    """OSS period attribution is the art. 75 devengo date, and says which one it used.

    Two invoices, both issued in Q2 2026. One records a Q1 operation date, so
    it devengo'd in Q1 and belongs on Q1's Modelo 369; the other records none,
    so its Q2 placement is a substitution the operator is told about. Asserting
    both directions matters: a change that moved every invoice one quarter
    earlier, or an advisory that fired on every invoice, would each satisfy one
    half alone.
    """
    revision = _revision("369", _M369_REVISION)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        build_invoice_catalogue(
            (
                _m369_invoice(
                    invoice_number="OSS-DE-Q1-OPERATION",
                    issued_at=date(2026, 4, 10),
                    counterparty_name="DE Consumer",
                    counterparty_tax_id="DE123456789",
                    counterparty_country="DE",
                    transaction_kind=TransactionKind("oss_union_services"),
                    base_amount=Decimal("100.00"),
                    iva_amount=Decimal("19.00"),
                    operation_date=date(2026, 3, 28),
                ),
                _m369_invoice(
                    invoice_number="OSS-FR-NO-OPERATION-DATE",
                    issued_at=date(2026, 4, 12),
                    counterparty_name="FR Consumer",
                    counterparty_tax_id="FR12345678901",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind("oss_union_services"),
                    base_amount=Decimal("200.00"),
                    iva_amount=Decimal("40.00"),
                ),
            ),
        ),
    )

    def _resolve(code: str) -> Any:
        return OssIossLedgerSourceResolver(
            ports=InvoiceCatalogueReadPorts(
                invoice_reader=InvoiceCatalogueReadAdapter(repository=invoice_repo),
                transaction_reader=_EmptyTransactionCatalogueReader(),
            ),
        ).resolve(
            CalculationSourceContext(
                bucket_id=_M369_BUCKET,
                modelo="369",
                filing_year=_M369_YEAR,
                period=Period.from_year_and_code(_M369_YEAR, code),
                revision=revision,
            ),
        )

    q1 = _resolve("1T")
    q2 = _resolve("2T")

    # The declared-date invoice devengo'd in Q1 and carries no proxy advisory.
    assert Decimal(q1.binding_values[_M369_DE_SERVICES_BINDING]) == Decimal("19.00")
    assert Decimal(q1.binding_values[_M369_FR_SERVICES_BINDING]) == Decimal("0")
    assert [diag.reason for diag in q1.diagnostics] == []

    # The undated one landed in Q2 on its issue date, disclosed as a substitution.
    assert Decimal(q2.binding_values[_M369_FR_SERVICES_BINDING]) == Decimal("40.00")
    assert Decimal(q2.binding_values[_M369_DE_SERVICES_BINDING]) == Decimal("0")
    proxy = [diag for diag in q2.diagnostics if diag.reason == "devengo_date_proxy_attribution"]
    assert len(proxy) == 1
    assert "OSS-FR-NO-OPERATION-DATE" in proxy[0].message
    assert "OSS-DE-Q1-OPERATION" not in proxy[0].message


def test_m369_unresolved_oss_source_refuses_verification_and_export(
    m369_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """No live OSS source cannot turn a zero Modelo 369 draft into a filing artefact."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period=Period.from_year_and_code(_M369_YEAR, "1T"),
        revision_id=_M369_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_M369_BUCKET,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects),
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_638:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_638,
            clock=_T1,
        )

    assert any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "oss_no_live_source"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert result.revision.source_provenance == (), "unresolved OSS source must persist no resolved-source trace"

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            result.revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="m369-unresolved-operator",
            workflow_profile=workflow_profile(),
            clock=_T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert report.granted_verificado_completo is False
    finding = next(
        (
            candidate
            for candidate in report.findings
            if candidate.kind.value == "blocking_rule"
            and candidate.message_locale_key == "application.modelo.findings.oss_evidence_missing"
        ),
        None,
    )
    assert finding is not None, report.findings
    assert finding.severity.value == "blocking"
    assert finding.legal_refs
    assert finding.source_refs
    persisted = cr_repo.load().get(result.revision.calculation_revision_id)
    assert persisted is not None
    assert persisted.state is CalculationRevisionState.BORRADOR
    output_path = tmp_path / "modelo-369.txt"
    with pytest.raises(CalculationRevisionStateError), bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-unresolved-operator",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_M369_BUCKET,
                secure_objects=m369_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
            ),
            operation=operation,
        )
    assert not output_path.exists()
    assert not (tmp_path / "modelo-369.txt.tmp").exists()


def test_m369_unrouted_observation_refuses_verification_and_export(
    m369_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A persisted positive OSS line outside the registry shape cannot be verified or exported."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        build_invoice_catalogue(
            (
                _m369_invoice(
                    invoice_number="OSS-FR-GOODS-UNROUTED-001",
                    issued_at=date(2026, 2, 17),
                    counterparty_name="FR Consumer Goods",
                    counterparty_tax_id="FR98765432109",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind("oss_union_goods_distance_sale"),
                    base_amount=Decimal("200.00"),
                    iva_amount=Decimal("40.00"),
                ),
            ),
        ),
    )
    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period=Period.from_year_and_code(_M369_YEAR, "1T"),
        revision_id=_M369_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_M369_BUCKET,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects),
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_744:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_744,
            clock=_T1,
        )

    assert any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "unrouted_observation"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert any(
        issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION and issue.reason == "unrouted_observation"
        for issue in result.revision.source_issues
    ), result.revision.source_issues
    assert any(ref.contributor_source_kind == "ledger_oss_aggregation" for ref in result.revision.source_provenance), (
        result.revision.source_provenance
    )

    retired_keyword: dict[str, Any] = {"source_provenance": result.revision.source_provenance}
    with (
        pytest.raises(TypeError, match="source_provenance"),
        calculation_ports_for_test(
            bucket_id=_M369_BUCKET,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects),
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
        ) as _calculation_ports_772,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={},
            ports=_calculation_ports_772,
            **retired_keyword,
        )
    assert cr_repo.load().get(result.revision.calculation_revision_id) == result.revision
    assert (
        wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id
        == result.revision.calculation_revision_id
    )

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            result.revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="m369-unrouted-operator",
            workflow_profile=workflow_profile(),
            clock=_T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert report.granted_verificado_completo is False
    finding = next(
        (
            candidate
            for candidate in report.findings
            if candidate.kind.value == "blocking_rule"
            and candidate.message_locale_key == "application.modelo.findings.oss_source_unrouted"
        ),
        None,
    )
    assert finding is not None, report.findings
    assert finding.severity.value == "blocking"
    assert finding.legal_refs
    assert finding.source_refs
    source_ref = next(issue.source_ref for issue in result.revision.source_issues if issue.source_ref is not None)
    assert source_ref in str(finding.message_facts["source_ref_ids"]).split("|")
    persisted = cr_repo.load().get(result.revision.calculation_revision_id)
    assert persisted is not None
    assert persisted.state is CalculationRevisionState.BORRADOR
    output_path = tmp_path / "modelo-369-unrouted.txt"
    with pytest.raises(CalculationRevisionStateError), bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-unrouted-operator",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_M369_BUCKET,
                secure_objects=m369_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
            ),
            operation=operation,
        )
    assert not output_path.exists()
    assert not (tmp_path / "modelo-369-unrouted.txt.tmp").exists()


def test_m369_zero_valued_oss_invoice_remains_verifiable(
    m369_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A real all-zero OSS invoice is source evidence, not an unrouted under-declaration."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        build_invoice_catalogue(
            (
                _m369_invoice(
                    invoice_number="OSS-FR-GOODS-ZERO-001",
                    issued_at=date(2026, 2, 18),
                    counterparty_name="FR Zero Consumer Goods",
                    counterparty_tax_id="FR00000000000",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind("oss_union_goods_distance_sale"),
                    base_amount=Decimal("0.00"),
                    iva_amount=Decimal("0.00"),
                ),
            ),
        ),
    )
    work_unit = create_work_unit(
        bucket_id=_M369_BUCKET,
        modelo="369",
        filing_year=_M369_YEAR,
        period=Period.from_year_and_code(_M369_YEAR, "1T"),
        revision_id=_M369_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_M369_BUCKET,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=m369_objects),
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_878:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=_calculation_ports_878,
            clock=_T1,
        )

    assert not any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "unrouted_observation"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert result.revision.source_issues == ()
    assert any(ref.contributor_source_kind == "ledger_oss_aggregation" for ref in result.revision.source_provenance), (
        result.revision.source_provenance
    )
    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            result.revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="m369-zero-operator",
            workflow_profile=workflow_profile(),
            clock=_T1,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
    assert report.granted_verificado_completo is True, report.findings
    assert wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id == (
        result.revision.calculation_revision_id
    )


# ---------------------------------------------------------------------------
