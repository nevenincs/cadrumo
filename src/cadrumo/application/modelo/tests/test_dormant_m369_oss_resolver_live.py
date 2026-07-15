"""Live M369 OSS/IOSS resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage import SecureObjectRepository
from ....core import BindingSourceKind, Period
from ....domain.calculations.registry import CasillaId
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus, derive_invoice_id
from ....domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    WorkUnit,
    derive_calculation_revision_id,
    upsert_work_unit,
)
from ....tests.secure_sql import isolated_injected_secure_object_repository, isolated_runtime_profile
from ...aggregation import (
    CalculationSourceContext,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
)
from .. import (
    BucketAggregationCalculationResult,
    CalculationRevisionStateError,
    ModeloExportCommand,
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
    export_modelo_revision,
    verify_modelo_revision,
)
from ._dormant_resolver_live_support import _T0, _T1, _casilla_id, _revision, _seed_ready_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Chain 2 — M369 OSS/IOSS (ledger_oss_aggregation): live invoice projection
# ---------------------------------------------------------------------------

_M369_BUCKET = "36900000-0000-4000-8000-000000000013"
_M369_REVISION = "esquema-union"
_M369_YEAR = 2026

# Three DISTINCT OSS candidates whose persisted IVA matches the destination MS
# published rate (DE general 19%, FR general 20%): the resolver validates each
# against lookup_rate before aggregating, so the iva_amount must equal
# base * rate. Distinct bases -> distinct cuotas (19.00 / 40.00 / 57.00).
_M369_DE_SERVICES = OssIossLedgerCandidate(
    ledger_id="oss-de-services",
    transaction_date=date(2026, 2, 15),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.DE,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
    base_amount=Decimal("100.00"),
    iva_amount=Decimal("19.00"),  # 100 * 19% (DE general)
)
_M369_FR_SERVICES = OssIossLedgerCandidate(
    ledger_id="oss-fr-services",
    transaction_date=date(2026, 2, 16),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.FR,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_SERVICES,
    base_amount=Decimal("200.00"),
    iva_amount=Decimal("40.00"),  # 200 * 20% (FR general)
)
_M369_DE_GOODS = OssIossLedgerCandidate(
    ledger_id="oss-de-goods",
    transaction_date=date(2026, 2, 17),
    regime=OssIossRegime.UNION_SCHEME,
    destination_member_state=EUMemberState.DE,
    rate_kind=IvaRateKind.GENERAL,
    invoice_direction=InvoiceKind.ISSUED,
    transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
    base_amount=Decimal("300.00"),
    iva_amount=Decimal("57.00"),  # 300 * 19% (DE general)
)
_M369_DE_SERVICES_BINDING = "modelo-369-union-de-services-21pct"
_M369_FR_SERVICES_BINDING = "modelo-369-union-fr-services-21pct"
_M369_DE_GOODS_BINDING = "modelo-369-union-de-goods-distance-21pct"
_M369_CUOTA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.union.cuota-total")
# Casilla bound to the DE-services OSS binding (used by the carve-out test).
_M369_DE_SERVICES_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.de.services-cuota")
_M369_FR_SERVICES_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.fr.services-cuota")
_M369_DE_GOODS_BINDING_CASILLA: CasillaId = _casilla_id("iva.union.de.goods-distance-cuota")


def _workflow_profile() -> TaxpayerProfile:
    """Return the real profile projection used by the M369 verify/export gates."""
    return TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)


def _legacy_revision_without_source_assessment(revision: CalculationRevision) -> CalculationRevision:
    """Rehydrate the real calculation payload as a pre-repair draft."""
    legacy_id = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        row_binding_values=revision.row_binding_values,
        relation_overrides=revision.relation_overrides,
        casilla_values=revision.casilla_values,
        source_transaction_ids=revision.source_transaction_ids,
        m210_official_tipo_renta_code=revision.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=revision.m210_gross_income_source_mode,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        detail_rows=revision.detail_rows,
    )
    payload = revision.model_dump()
    payload.update(
        calculation_revision_id=legacy_id,
        source_issues=(),
        source_resolution_assessed=False,
    )
    return CalculationRevision.model_validate(payload)


def _persist_legacy_current_revision(
    *,
    work_unit: WorkUnit,
    legacy: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
) -> None:
    """Persist one pre-repair revision as the actual current encrypted draft."""
    calculation_repository.save(CalculationRevisionCatalogue(revisions={legacy.calculation_revision_id: legacy}))
    work_units = work_unit_repository.load()
    persisted_work_unit = work_units.work_units[work_unit.work_unit_id]
    work_unit_repository.save(
        upsert_work_unit(
            work_units,
            persisted_work_unit.model_copy(
                update={
                    "current_calculation_revision_id": legacy.calculation_revision_id,
                    "updated_at": _T1,
                },
            ),
        ),
    )


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
    candidates = (_M369_DE_SERVICES, _M369_FR_SERVICES, _M369_DE_GOODS)

    # Resolver path (what the live mesh WOULD fold if it had candidates).
    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id=_M369_BUCKET,
            modelo="369",
            filing_year=_M369_YEAR,
            period=Period.from_year_and_code(_M369_YEAR, "1T"),
            revision=revision,
        ),
    )
    assert resolution.binding_values[_M369_DE_SERVICES_BINDING] == Decimal("19.00")
    assert resolution.binding_values[_M369_FR_SERVICES_BINDING] == Decimal("40.00")
    assert resolution.binding_values[_M369_DE_GOODS_BINDING] == Decimal("57.00")
    # Cross-check the registry aggregation wrapper agrees with the resolver.
    assert aggregate_oss_ioss_bindings(revision, candidates) == dict(resolution.binding_values)
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
) -> Invoice:
    line = InvoiceLine(
        description=f"OSS supply {invoice_number}",
        quantity=Decimal("1"),
        unit_price=base_amount,
        subtotal=base_amount,
        iva_rate=IvaRate.RATE_21,
        oss_rate_kind=IvaRateKind.GENERAL,
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
        oss_ioss_regime=OssIossRegime.UNION_SCHEME,
        oss_transaction_kind=transaction_kind,
    )


def test_m369_live_path_folds_oss_invoices_not_no_live_source_advisory(
    tmp_path: Path,
) -> None:
    """Live M369 calculate and legacy verification use the injected store."""
    with isolated_runtime_profile(tmp_path=tmp_path / "ambient", bucket_id=_M369_BUCKET) as runtime:  # noqa: SIM117
        with isolated_injected_secure_object_repository(
            tmp_path=tmp_path / "injected",
            bucket_id=_M369_BUCKET,
            database_name="m369-injected.db",
        ) as injected_objects:
            _seed_ready_profile(runtime.repository, bucket_id=_M369_BUCKET)
            wu_repo = WorkUnitCatalogueRepository(objects=runtime.repository)
            cr_repo = CalculationRevisionCatalogueRepository(objects=runtime.repository)
            tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=runtime.repository)
            ambient_invoice_repo = InvoiceCatalogueRepository(objects=runtime.repository)
            invoice_repo = InvoiceCatalogueRepository(objects=injected_objects)
            invoice_repo.save(
                InvoiceCatalogue.from_invoices(
                    (
                        _m369_invoice(
                            invoice_number="OSS-DE-SERV-001",
                            issued_at=date(2026, 2, 15),
                            counterparty_name="DE Consumer",
                            counterparty_tax_id="DE123456789",
                            counterparty_country="DE",
                            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
                            base_amount=Decimal("100.00"),
                            iva_amount=Decimal("19.00"),
                        ),
                        _m369_invoice(
                            invoice_number="OSS-FR-SERV-001",
                            issued_at=date(2026, 2, 16),
                            counterparty_name="FR Consumer",
                            counterparty_tax_id="FR12345678901",
                            counterparty_country="FR",
                            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
                            base_amount=Decimal("200.00"),
                            iva_amount=Decimal("40.00"),
                        ),
                        _m369_invoice(
                            invoice_number="OSS-DE-GOODS-001",
                            issued_at=date(2026, 2, 17),
                            counterparty_name="DE Consumer Goods",
                            counterparty_tax_id="DE987654321",
                            counterparty_country="DE",
                            transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
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
                repository=wu_repo,
                clock=_T0,
            )
            result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                transaction_repository=tx_repo,
                invoice_repository=invoice_repo,
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

            legacy = _legacy_revision_without_source_assessment(result.revision)
            assert legacy.calculation_revision_id != result.revision.calculation_revision_id
            assert legacy.source_resolution_assessed is False
            _persist_legacy_current_revision(
                work_unit=work_unit,
                legacy=legacy,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
            )
            report = verify_modelo_revision(
                legacy.calculation_revision_id,
                actor="m369-live-operator",
                workflow_profile=_workflow_profile(),
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                transaction_repository=tx_repo,
                invoice_repository=invoice_repo,
                clock=_T1,
            )
            assert ambient_invoice_repo.exists() is False
            assert any(
                ref.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION
                for ref in result.revision.source_provenance
            ), result.revision.source_provenance
            assert legacy.source_issues == ()
            assert result.revision.source_resolution_assessed is True
            assert report.granted_verificado_completo is True, report.findings
            recalculated = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                transaction_repository=tx_repo,
                invoice_repository=invoice_repo,
                clock=_T1,
            )
            assert recalculated.revision.calculation_revision_id != legacy.calculation_revision_id
            assert recalculated.revision.source_resolution_assessed is True
            assert wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id == (
                recalculated.revision.calculation_revision_id
            )


def test_m369_unresolved_oss_source_refuses_verification_and_export(
    m369_objects: SecureObjectRepository,
    tmp_path: Path,
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
        repository=wu_repo,
        clock=_T0,
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "oss_no_live_source"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert result.revision.source_provenance == (), "unresolved OSS source must persist no resolved-source trace"

    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="m369-unresolved-operator",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )

    assert report.granted_verificado_completo is False
    finding = next(
        (
            candidate
            for candidate in report.findings
            if candidate.kind.value == "blocking_rule"
            and "unresolved OSS/IOSS aggregation sources" in candidate.message
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
    with pytest.raises(CalculationRevisionStateError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-unresolved-operator",
            ),
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
        )
    assert not output_path.exists()
    assert not (tmp_path / "modelo-369.txt.tmp").exists()


def test_m369_recalculate_existing_unrouted_draft_refuses_verification_and_export(
    m369_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A persisted positive OSS line outside the registry shape cannot be verified or exported."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        InvoiceCatalogue.from_invoices(
            (
                _m369_invoice(
                    invoice_number="OSS-FR-GOODS-UNROUTED-001",
                    issued_at=date(2026, 2, 17),
                    counterparty_name="FR Consumer Goods",
                    counterparty_tax_id="FR98765432109",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
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
        repository=wu_repo,
        clock=_T0,
    )

    initial = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    legacy = _legacy_revision_without_source_assessment(initial.revision)
    assert legacy.calculation_revision_id != initial.revision.calculation_revision_id
    _persist_legacy_current_revision(
        work_unit=work_unit,
        legacy=legacy,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
    )

    retired_keyword: dict[str, Any] = {"source_provenance": initial.revision.source_provenance}
    with pytest.raises(TypeError, match="source_provenance"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            **retired_keyword,
        )
    assert cr_repo.load().get(legacy.calculation_revision_id) == legacy
    assert (
        wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id
        == legacy.calculation_revision_id
    )

    legacy_report = verify_modelo_revision(
        legacy.calculation_revision_id,
        actor="m369-legacy-unrouted-operator",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    assert legacy_report.granted_verificado_completo is False
    assert any(
        "legacy OSS/IOSS source resolution cannot be confirmed" in finding.message for finding in legacy_report.findings
    ), legacy_report.findings
    legacy_persisted = cr_repo.load().get(legacy.calculation_revision_id)
    assert legacy_persisted is not None
    assert legacy_persisted.state is CalculationRevisionState.BORRADOR
    legacy_output_path = tmp_path / "modelo-369-legacy-unrouted.txt"
    with pytest.raises(CalculationRevisionStateError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=legacy.calculation_revision_id,
                output_path=legacy_output_path,
                actor="m369-legacy-unrouted-operator",
            ),
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
        )
    assert not legacy_output_path.exists()
    assert not (tmp_path / "modelo-369-legacy-unrouted.txt.tmp").exists()

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert result.revision.calculation_revision_id != legacy.calculation_revision_id
    assert cr_repo.load().get(legacy.calculation_revision_id) == legacy
    assert any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "unrouted_observation"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert any(
        issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION and issue.reason == "unrouted_observation"
        for issue in result.revision.source_issues
    ), result.revision.source_issues
    assert any(ref.source_kind == "ledger_oss_aggregation" for ref in result.revision.source_provenance), (
        result.revision.source_provenance
    )

    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="m369-unrouted-operator",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert report.granted_verificado_completo is False
    finding = next(
        (
            candidate
            for candidate in report.findings
            if candidate.kind.value == "blocking_rule"
            and "no declared aggregation binding consumes" in candidate.message
        ),
        None,
    )
    assert finding is not None, report.findings
    assert finding.severity.value == "blocking"
    assert finding.legal_refs
    assert finding.source_refs
    source_ref = next(issue.source_ref for issue in result.revision.source_issues if issue.source_ref is not None)
    assert source_ref in finding.message
    persisted = cr_repo.load().get(result.revision.calculation_revision_id)
    assert persisted is not None
    assert persisted.state is CalculationRevisionState.BORRADOR
    output_path = tmp_path / "modelo-369-unrouted.txt"
    with pytest.raises(CalculationRevisionStateError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=result.revision.calculation_revision_id,
                output_path=output_path,
                actor="m369-unrouted-operator",
            ),
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
        )
    assert not output_path.exists()
    assert not (tmp_path / "modelo-369-unrouted.txt.tmp").exists()


def test_m369_zero_valued_oss_invoice_remains_verifiable(
    m369_objects: SecureObjectRepository,
) -> None:
    """A real all-zero OSS invoice is source evidence, not an unrouted under-declaration."""
    wu_repo = WorkUnitCatalogueRepository(objects=m369_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=m369_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_M369_BUCKET, objects=m369_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m369_objects)
    invoice_repo.save(
        InvoiceCatalogue.from_invoices(
            (
                _m369_invoice(
                    invoice_number="OSS-FR-GOODS-ZERO-001",
                    issued_at=date(2026, 2, 18),
                    counterparty_name="FR Zero Consumer Goods",
                    counterparty_tax_id="FR00000000000",
                    counterparty_country="FR",
                    transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
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
        repository=wu_repo,
        clock=_T0,
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert not any(
        diagnostic.source_kind == "ledger_oss_aggregation" and diagnostic.reason == "unrouted_observation"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
    assert result.revision.source_issues == ()
    assert result.revision.source_resolution_assessed is True
    assert any(ref.source_kind == "ledger_oss_aggregation" for ref in result.revision.source_provenance), (
        result.revision.source_provenance
    )
    legacy = _legacy_revision_without_source_assessment(result.revision)
    assert legacy.calculation_revision_id != result.revision.calculation_revision_id
    _persist_legacy_current_revision(
        work_unit=work_unit,
        legacy=legacy,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
    )
    report = verify_modelo_revision(
        legacy.calculation_revision_id,
        actor="m369-zero-operator",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    assert report.granted_verificado_completo is True, report.findings
    recalculated = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    assert recalculated.revision.calculation_revision_id != legacy.calculation_revision_id
    assert recalculated.revision.source_resolution_assessed is True
    assert wu_repo.load().work_units[work_unit.work_unit_id].current_calculation_revision_id == (
        recalculated.revision.calculation_revision_id
    )


# ---------------------------------------------------------------------------
