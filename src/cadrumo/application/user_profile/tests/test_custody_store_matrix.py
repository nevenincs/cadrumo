"""Per-store custody round-trip matrix through the real recovery transport.

Seeds one valid row in every generically-carried secure-object store, exports a
sealed recovery archive, imports it into a *fresh storage root that re-provisions
the same bucket id under a new data-encryption key* (the production recovery
scenario), and reads every store back through its owning repository. A store that
reads back proves its natural-key resolver re-keys correctly under the recipient
DEK and that the payload survives the boundary.

One archive cycle covers every store so the expensive Argon2id recovery wrap runs
once; each store asserts independently with a descriptive message.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.hashing import sha256_hex
from ....core.resources import resources
from ....domain.filing import ModeloDraft
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.custody_store_matrix_adapters import (
    AmortizacionLedgerRepository,
    AssetsLedgerRepository,
    BucketEventHistoryRepository,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    InventoryLedgerRepository,
    InvoiceCatalogueRepository,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    ModeloAmendmentRepository,
    ModeloDraftRepository,
    SubmissionRepository,
    VerificationReportCatalogueRepository,
    load_usage_ratios,
    save_usage_ratios,
    secure_object_repository_for_active_bucket,
)
from ....tests.secure_sql import (
    TestRuntimeProfile,
    dev_test_database_password,
    isolated_profile_storage_root,
    isolated_runtime_profile,
)
from ...bucket_maintenance import (
    BucketMaintenanceService,
    ExportBucketCommand,
    ImportBucketCommand,
)
from ...user_profile._commands import RegisterProfileCommand
from ...user_profile._orchestration import profile_storage_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "7c7c7c7c-7c7c-47c7-87c7-7c7c7c7c7c7c"
_LABEL = "Matrix source"
_RECOVERY = "matrix recovery correct horse battery"
_NOW = datetime(2026, 6, 30, 6, 0, 0, tzinfo=UTC)
_HEX64 = "a" * 64


@dataclass(frozen=True)
class StoreCase:
    namespace: str
    seed: Callable[[str], None]
    verify: Callable[[str], None]


# --------------------------------------------------------------------------
# Seed + verify per carried store (run inside the relevant bucket session).
# --------------------------------------------------------------------------


def _seed_classification_rule(bucket_id: str) -> None:
    from ....domain.transactions import BusinessClassification, LedgerClassificationRule
    from ...ledger import LedgerClassificationRuleRepository

    rule = LedgerClassificationRule.create(
        description_pattern="amazon",
        classification=BusinessClassification.BUSINESS,
        actor="operator",
        created_at=_NOW,
    )
    LedgerClassificationRuleRepository().save(rule)


def _verify_classification_rule(bucket_id: str) -> None:
    from ...ledger import LedgerClassificationRuleRepository

    assert LedgerClassificationRuleRepository().list_rules(), "classification rule lost"


def _seed_submission(bucket_id: str) -> None:
    from ....core import Period
    from ....domain.submission import (
        ModeloPresentado,
        SubmissionAttempt,
        SubmissionStatus,
        make_submission_id,
    )

    attempt = SubmissionAttempt(
        attempt_id="draft-1.1",
        started_at=_NOW,
        ended_at=_NOW,
        status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
    )
    SubmissionRepository().save(
        ModeloPresentado(
            submission_id=make_submission_id("draft-1", 1),
            draft_id="draft-1",
            modelo="303",
            period=Period.from_year_and_code(2024, "4T"),
            profile_tax_id="12345678Z",
            status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
            submitted_at=_NOW,
            attempts=(attempt,),
        ),
    )


def _verify_submission(bucket_id: str) -> None:
    assert tuple(SubmissionRepository().iter_submissions()), "submission record lost"


def _seed_evidence_bundle(bucket_id: str) -> None:
    from ...evidence import (
        BundleVerificationState,
        EvidenceBundle,
        EvidenceBundleRepository,
        derive_bundle_id,
    )

    bundle_id = derive_bundle_id(bucket_id=bucket_id, work_unit_id=_HEX64, manifest_version=1, records=())
    EvidenceBundleRepository().save(
        EvidenceBundle(
            bundle_id=bundle_id,
            manifest_version=1,
            bucket_id=bucket_id,
            work_unit_id=_HEX64,
            records=(),
            verification_state=BundleVerificationState.PENDING,
            created_at=_NOW,
        ),
    )


def _verify_evidence_bundle(bucket_id: str) -> None:
    from ...evidence import EvidenceBundleRepository

    assert tuple(EvidenceBundleRepository().iter_records()), "evidence bundle lost"


def _seed_iva_compensation(bucket_id: str) -> None:
    from ....core import Period
    from ....domain.iva_compensation import IvaCompensationPeriodState
    from ...calculations import IvaCompensationHistoryRepository

    IvaCompensationHistoryRepository().save_period(
        IvaCompensationPeriodState(
            taxpayer_nif="12345678Z",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "4T"),
            expediente_id="EXP-001",
            status="seeded",
            presented_at=_NOW,
            generated_amount=Decimal("0"),
            available_end_amount=Decimal("100"),
            source_observation_key="303:2024:4T",
        ),
    )


def _verify_iva_compensation(bucket_id: str) -> None:
    from ...calculations import IvaCompensationHistoryRepository

    assert IvaCompensationHistoryRepository().list_periods(), "iva compensation history lost"


def _seed_filing_history(bucket_id: str) -> None:
    from ....core import Period
    from ....domain import ModeloIdentifier
    from ...filing import (
        ModeloHistory,
        ModeloHistoryEntry,
        ModeloHistoryRepository,
    )

    modelo = ModeloIdentifier("303")
    entry = ModeloHistoryEntry(
        modelo=modelo,
        period=Period.from_year_and_code(2024, "4T"),
        submitted_at=_NOW,
        status="PRESENTADA",
    )
    ModeloHistoryRepository().save(ModeloHistory(modelo=modelo, entries=(entry,)))


def _verify_filing_history(bucket_id: str) -> None:
    from ...filing import ModeloHistoryRepository

    assert tuple(ModeloHistoryRepository().iter_records()), "filing history lost"


def _seed_draft(bucket_id: str) -> None:
    from ....core import Period
    from ....domain.calculations.registry import RegistrySnapshotRef
    from ....domain.filing import ModeloDraft
    from ....domain.submission import ModeloDraftStatus

    draft = ModeloDraft(
        draft_id="draft-303-2024-4t",
        modelo="303",
        period=Period.from_year_and_code(2024, "4T"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(modelo="303", revision_id="303-2026-v1", modelo_year=2026, period="4T"),
        status=ModeloDraftStatus.BORRADOR,
        values=(),
        created_at=_NOW,
        updated_at=_NOW,
        schema_version="1",
    )
    ModeloDraftRepository().save(draft)


def _verify_draft(bucket_id: str) -> None:
    assert tuple(ModeloDraftRepository().iter_drafts()), "draft lost"


def _seed_usage_ratios(bucket_id: str) -> None:
    from ....domain.usage_ratios import UsageRatioProfile

    save_usage_ratios(UsageRatioProfile(), bucket_id=bucket_id)


def _verify_usage_ratios(bucket_id: str) -> None:
    assert load_usage_ratios(bucket_id=bucket_id) is not None, "usage ratios lost"


def _seed_invoice_catalogue(bucket_id: str) -> None:
    from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus, derive_invoice_id
    from ....domain.iva import InvoiceKind

    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_0,
        iva_amount=Decimal("0"),
    )
    kind = InvoiceKind.RECEIVED
    invoice_number = "F-2026-001"
    issued_at = date(2026, 1, 15)
    counterparty_tax_id = "12345678Z"
    currency = "EUR"
    grand_total = Decimal("100.00")
    invoice = Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=invoice_number,
            issued_at=issued_at,
            counterparty_tax_id=counterparty_tax_id,
            currency=currency,
            grand_total=grand_total,
        ),
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name="Proveedor SL",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country="ES",
        base_total=Decimal("100.00"),
        iva_total=Decimal("0"),
        grand_total=grand_total,
        currency=currency,
        lines=(line,),
        payment_status=PaymentStatus.PAID,
    )
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((invoice,)))


def _verify_invoice_catalogue(bucket_id: str) -> None:
    assert InvoiceCatalogueRepository().load().invoices, "invoice catalogue lost"


def _seed_verification_reports(bucket_id: str) -> None:
    from ....domain.modelos import VerificationReportCatalogue

    # An empty catalogue still persists one secure-object row to carry.
    VerificationReportCatalogueRepository().save(VerificationReportCatalogue())


def _verify_verification_reports(bucket_id: str) -> None:
    assert VerificationReportCatalogueRepository().load() is not None, "verification reports lost"


def _seed_iva_wallet_decision(bucket_id: str) -> None:
    from ....core import Period
    from ....domain.iva_compensation import IvaCompensationReconciliationDecision
    from ...calculations import IvaWalletDecisionRepository

    IvaWalletDecisionRepository().save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2024,
            target_period=Period.from_year_and_code(2024, "4T"),
            selected_authority="aeat_wallet",
            selected_amount=Decimal("100"),
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason="latest valid wallet observation",
            decided_at=_NOW,
        ),
    )


def _verify_iva_wallet_decision(bucket_id: str) -> None:
    from ....core import Period
    from ...calculations import IvaWalletDecisionRepository

    repo = IvaWalletDecisionRepository()
    assert repo.list_decisions(), "iva wallet decision lost"
    # ``save_decision`` also appends an immutable audit-event row in the separate
    # decision-events namespace; confirm that namespace round-trips too.
    history = repo.load_decision_history("12345678Z", Period.from_year_and_code(2024, "4T"))
    assert history, "iva wallet decision-events lost"


def _seed_iva_remote_state(bucket_id: str) -> None:
    from ....core import Period
    from ...live import (
        IvaRemoteStateAcquisitionManifest,
        IvaRemoteStateAcquisitionManifestRepository,
        LiveIvaAcquisitionFailureMode,
        LiveIvaAuthOutcome,
        LiveIvaReadStatus,
    )

    manifest = IvaRemoteStateAcquisitionManifest(
        acquisition_id="live-iva-acquisition:2024:4T:1",
        captured_at=_NOW,
        year_from=2024,
        year_to=2024,
        target_year=2024,
        target_period=Period.from_year_and_code(2024, "4T"),
        auth=LiveIvaAuthOutcome(
            status=LiveIvaReadStatus.SUCCEEDED,
            outcome_mode=LiveIvaAcquisitionFailureMode.AUTHENTICATED,
        ),
        filed_history_succeeded=True,
        wallet_succeeded=True,
        surfaces=(),
    )
    IvaRemoteStateAcquisitionManifestRepository().save(manifest)


def _verify_iva_remote_state(bucket_id: str) -> None:
    from ...live import IvaRemoteStateAcquisitionManifestRepository

    assert tuple(IvaRemoteStateAcquisitionManifestRepository().iter_records()), "iva remote state lost"


def _seed_justificante_capture(bucket_id: str) -> None:
    from ....core import Period
    from ...live import (
        JustificanteCaptureSnapshot,
        JustificanteCaptureSnapshotRepository,
        SnapshotLifecycleState,
    )

    pdf = b"%PDF-1.4 minimal"
    snap = JustificanteCaptureSnapshot(
        snapshot_id="just-1",
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "4T"),
        expediente_id="2024303EXP0001",
        csv="ABCD1234EFGH",
        pdf_sha256=sha256_hex(pdf),
        pdf_base64=base64.b64encode(pdf).decode("ascii"),
        captured_at=_NOW,
        state=SnapshotLifecycleState.ACTIVE,
    )
    JustificanteCaptureSnapshotRepository(bucket_id=bucket_id).save(snap)


def _verify_justificante_capture(bucket_id: str) -> None:
    from ...live import JustificanteCaptureSnapshotRepository

    assert JustificanteCaptureSnapshotRepository(bucket_id=bucket_id).list_snapshots(), "justificante capture lost"


def _seed_notifications(bucket_id: str) -> None:
    from ....core.config import load_settings
    from ...live import PersistedNotificationsSnapshot
    from ...live._notifications import _notifications_repository

    snap = PersistedNotificationsSnapshot(
        snapshot_id=_HEX64,
        bucket_id=bucket_id,
        captured_at=_NOW,
        source_url="https://sede.aeat.es/notif",
        rows=(),
        persisted_at=_NOW,
    )
    _notifications_repository(load_settings(), bucket_id).save(snap)


def _verify_notifications(bucket_id: str) -> None:
    from ....core.config import load_settings
    from ...live._notifications import _notifications_repository

    assert _notifications_repository(load_settings(), bucket_id).list_snapshots(), "notifications snapshot lost"


def _seed_expedientes(bucket_id: str) -> None:
    from ....core.config import load_settings
    from ...live import PersistedExpedientesSnapshot
    from ...live._expedientes import _expedientes_repository

    snap = PersistedExpedientesSnapshot(
        snapshot_id=_HEX64,
        bucket_id=bucket_id,
        captured_at=_NOW,
        source_url="https://sede.aeat.es/expedientes",
        declarations=(),
        persisted_at=_NOW,
    )
    _expedientes_repository(load_settings(), bucket_id).save(snap)


def _verify_expedientes(bucket_id: str) -> None:
    from ....core.config import load_settings
    from ...live._expedientes import _expedientes_repository

    assert _expedientes_repository(load_settings(), bucket_id).list_snapshots(), "expedientes snapshot lost"


def _seed_apoderado(bucket_id: str) -> None:
    from ...auth import ApoderadoConfiguration
    from ...auth._apoderado import _ApoderadoConfigRepository

    _ApoderadoConfigRepository(bucket_id=bucket_id).save(
        ApoderadoConfiguration(
            bucket_id=bucket_id,
            represented_nif="12345678Z",
            granted_scopes=("modelo-filing",),
            catalogue_version="1",
            configured_at=_NOW,
        ),
    )


def _verify_apoderado(bucket_id: str) -> None:
    from ...auth._apoderado import _ApoderadoConfigRepository

    assert _ApoderadoConfigRepository(bucket_id=bucket_id).load(bucket_id) is not None, "apoderado config lost"


def _build_modelo_draft() -> ModeloDraft:
    from ....core import Period
    from ....domain.calculations.registry import RegistrySnapshotRef
    from ....domain.filing import ModeloDraft
    from ....domain.submission import ModeloDraftStatus

    return ModeloDraft(
        draft_id="draft-303-2024-4t-amend",
        modelo="303",
        period=Period.from_year_and_code(2024, "4T"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(modelo="303", revision_id="303-2026-v1", modelo_year=2026, period="4T"),
        status=ModeloDraftStatus.BORRADOR,
        values=(),
        created_at=_NOW,
        updated_at=_NOW,
        schema_version="1",
    )


def _seed_amendment(bucket_id: str) -> None:
    from ....core import Period
    from ....domain.filing import (
        AmendmentKind,
        CasillaChange,
        ModeloComplementaria,
        make_amendment_id,
    )

    delta = (CasillaChange(casilla_id="01", new_value=Decimal("10.00"), reason="fix"),)
    amendment_id = make_amendment_id(submission_id="sub-1", amendment_kind=AmendmentKind.COMPLEMENTARIA, delta=delta)
    amendment = ModeloComplementaria(
        amendment_id=amendment_id,
        submission_id="sub-1",
        original_csv="TUD4V9XAUV7QJ8QV",
        original_model="303",
        original_period=Period.from_year_and_code(2024, "4T"),
        delta=delta,
        amended_draft=_build_modelo_draft(),
        created_at=_NOW,
    )
    ModeloAmendmentRepository(bucket_id=bucket_id).save(amendment)


def _verify_amendment(bucket_id: str) -> None:
    assert ModeloAmendmentRepository(bucket_id=bucket_id).list_amendment_ids(), "amendment lost"


def _seed_inventory_ledger(bucket_id: str) -> None:
    from ....domain.contribuyente.inventory import InventoryLedger, InventoryLedgerDocument, ValuationMethod

    ledger = InventoryLedger(
        actividad_id="act-1",
        year=2024,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0"),
    )
    InventoryLedgerRepository().save(InventoryLedgerDocument(ledgers=(ledger,)))


def _verify_inventory_ledger(bucket_id: str) -> None:
    assert InventoryLedgerRepository().load().ledgers, "inventory ledger lost"


def _seed_assets_ledger(bucket_id: str) -> None:
    from ....domain.contribuyente.assets import AssetClass, AssetRecord, AssetsLedgerDocument

    asset = AssetRecord(
        identifier="asset-1",
        description="laptop",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2024, 1, 10),
        cost_basis=Decimal("1000.00"),
    )
    AssetsLedgerRepository().save(AssetsLedgerDocument(assets=(asset,)))


def _verify_assets_ledger(bucket_id: str) -> None:
    assert AssetsLedgerRepository().load().assets, "assets ledger lost"


def _seed_amortization_ledger(bucket_id: str) -> None:
    from ....domain.contribuyente.assets import AmortizacionEntry, AmortizacionLedger

    ledger = AmortizacionLedger(entries=(AmortizacionEntry(asset_id="asset-1", year=2024, amount=Decimal("200.00")),))
    AmortizacionLedgerRepository().save(ledger)


def _verify_amortization_ledger(bucket_id: str) -> None:
    assert AmortizacionLedgerRepository().load().entries, "amortization ledger lost"


def _seed_borrador_100(bucket_id: str) -> None:
    from ....core import Modelo, Period
    from ...live import (
        Borrador100Snapshot,
        Borrador100SnapshotRepository,
        SnapshotLifecycleState,
        derive_borrador_100_snapshot_id,
    )

    period = Period.from_year_and_code(2024, "0A")
    snap_id = derive_borrador_100_snapshot_id(
        filing_year=2024,
        period=period,
        captured_at=_NOW,
        source_url="https://sede.aeat.es/borrador",
        binding_values={},
    )
    snap = Borrador100Snapshot(
        snapshot_id=snap_id,
        bucket_id=bucket_id,
        modelo=Modelo.M100.value,
        filing_year=2024,
        period=period,
        captured_at=_NOW,
        source_url="https://sede.aeat.es/borrador",
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={},
    )
    Borrador100SnapshotRepository(bucket_id=bucket_id).save(snap)


def _verify_borrador_100(bucket_id: str) -> None:
    from ...live import Borrador100SnapshotRepository

    assert Borrador100SnapshotRepository(bucket_id=bucket_id).list_snapshots(), "borrador 100 snapshot lost"


def _seed_m036(bucket_id: str) -> None:
    from ....domain.calculations.registry import CensoModeloEventKind
    from ...modelo import M036DeclarationResult, derive_m036_declaration_id
    from ...modelo._m036_lifecycle import _m036_declaration_repository

    decl_id = derive_m036_declaration_id(
        profile_id=bucket_id,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2024, 3, 1),
        sede_justificante=None,
    )
    result = M036DeclarationResult(
        declaration_id=decl_id,
        bucket_id=bucket_id,
        profile_id=bucket_id,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2024, 3, 1),
        sede_justificante=None,
        note=None,
        recorded_at=_NOW,
    )
    _m036_declaration_repository(bucket_id).save(result)


def _verify_m036(bucket_id: str) -> None:
    from ...modelo._m036_lifecycle import _m036_declaration_repository

    assert _m036_declaration_repository(bucket_id).list_snapshots(), "m036 declaration lost"


def _seed_verify_observation(bucket_id: str) -> None:
    from ...live import (
        VerifyObservation,
        VerifyObservationRepository,
        VerifySurface,
    )

    obs = VerifyObservation(
        observation_id=sha256_hex(b"nif_iva|ESX1234567L|valid"),
        bucket_id=bucket_id,
        surface=VerifySurface.NIF_IVA,
        nif="ESX1234567L",
        verdict="valid",
        checked_at=_NOW,
        persisted_at=_NOW,
    )
    VerifyObservationRepository(bucket_id=bucket_id).save(obs)


def _verify_verify_observation(bucket_id: str) -> None:
    from ...live import VerifyObservationRepository

    assert VerifyObservationRepository(bucket_id=bucket_id).list_observations(), "verify observation lost"


#: ``UserProfileSnapshot.from_profile`` stamps a wall-clock time into the
#: snapshot id, so the seeded id is remembered for the verify rather than
#: recomputed (which would differ).
_SEEDED_SNAPSHOT_ID: dict[str, str] = {}


def _seed_user_profile_snapshot(bucket_id: str) -> None:
    from ....domain.user_profile import (
        UserProfileRecord,
        UserProfileSnapshot,
    )
    from .._repository import UserProfileSnapshotRepository

    record = UserProfileRecord(profile_id=bucket_id, display_name="Snapshot Operator")
    snap = UserProfileSnapshot.from_profile(record)
    UserProfileSnapshotRepository(bucket_id=bucket_id).save(snap)
    _SEEDED_SNAPSHOT_ID[bucket_id] = snap.snapshot_id


def _verify_user_profile_snapshot(bucket_id: str) -> None:
    from .._repository import UserProfileSnapshotRepository

    snap_id = _SEEDED_SNAPSHOT_ID[bucket_id]
    assert UserProfileSnapshotRepository(bucket_id=bucket_id).exists(snap_id), "user profile snapshot lost"


def _seed_observations(bucket_id: str) -> None:
    from ....domain.calculations.registry import RegistryModeloObservation
    from ...calculations import CalculationObservationRepository

    obs = RegistryModeloObservation(modelo="303", filing_year=2024, period="4T")
    CalculationObservationRepository().save_observation(obs, source_kind="app_filing")


def _verify_observations(bucket_id: str) -> None:
    from ....core import Period
    from ...calculations import CalculationObservationRepository

    loaded = CalculationObservationRepository().load_observation("303", Period(filing_year=2024, code="4T"))
    assert loaded is not None, "calculation observation lost"


def _seed_retencion(bucket_id: str) -> None:
    from ....core import Period
    from ....core.aggregation import BindingSourceKind, RetencionScheme
    from ...aggregation import RetencionObservation, RetencionObservationRepository

    obs = RetencionObservation(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id="inv-1",
        perceptor_nif="12345678Z",
        scheme=RetencionScheme.URBAN_RENTAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on="2024-02-15",
    )
    RetencionObservationRepository().save_observation(
        modelo="115",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "1T"),
        observation=obs,
        source_kind="aggregate_pull",
    )


def _verify_retencion(bucket_id: str) -> None:
    from ....core import Period
    from ...aggregation import RetencionObservationRepository

    assert RetencionObservationRepository().load_observations("115", Period.from_year_and_code(2024, "1T")), (
        "retencion observation lost"
    )


def _seed_withholding(bucket_id: str) -> None:
    from ....core import Period
    from ....core.aggregation import RetencionClave
    from ....domain.calculations.registry import WithholdingObservation
    from ...aggregation import PercepcionObservationRepository

    obs = WithholdingObservation(
        source_id="wh-1",
        perceptor_tax_id="12345678Z",
        transaction_date=date(2024, 2, 15),
        clave=RetencionClave.A,
        percibido_dinerario=Decimal("1000.00"),
        retencion_practicada=Decimal("190.00"),
    )
    PercepcionObservationRepository().save_observation(
        modelo="190",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        observation=obs,
        source_kind="aggregate_pull",
    )


def _verify_withholding(bucket_id: str) -> None:
    from ....core import Period
    from ...aggregation import PercepcionObservationRepository

    assert PercepcionObservationRepository().load_observations("190", Period.from_year_and_code(2024, "0A")), (
        "withholding observation lost"
    )


def _seed_purchase_invoice_evidence(bucket_id: str) -> None:
    from ...ledger import (
        MediaKind,
        PurchaseInvoiceEvidence,
        PurchaseInvoiceEvidenceDocument,
        PurchaseInvoiceEvidenceRepository,
    )

    rec = PurchaseInvoiceEvidence(
        evidence_id="evidence-0001",
        bucket_id=bucket_id,
        source_path="invoice.pdf",
        source_sha256="0" * 64,
        media_kind=MediaKind.PDF,
        created_at=_NOW,
        updated_at=_NOW,
    )
    PurchaseInvoiceEvidenceRepository().save(PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=(rec,)))


def _verify_purchase_invoice_evidence(bucket_id: str) -> None:
    from ...ledger import PurchaseInvoiceEvidenceRepository

    document = PurchaseInvoiceEvidenceRepository().load(bucket_id)
    assert document is not None, "purchase invoice evidence lost"
    assert document.records, "purchase invoice evidence lost"


def _seed_business_operation_invoice(bucket_id: str) -> None:
    from ...ledger import (
        BusinessOperationInvoice,
        BusinessOperationInvoiceDirection,
        BusinessOperationInvoiceDocument,
        BusinessOperationInvoiceRepository,
    )

    rec = BusinessOperationInvoice(
        invoice_id="boi-0001",
        source_kind=BusinessOperationInvoiceDirection.PAYABLE_INVOICE,
        bucket_id=bucket_id,
        counterparty_nif="12345678Z",
        invoice_number="INV-001",
        invoice_date="2024-02-15",
        country_code=None,
        eu_iva_id=None,
        operation_type=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    BusinessOperationInvoiceRepository().save(
        BusinessOperationInvoiceDocument(
            bucket_id=bucket_id,
            source_kind=BusinessOperationInvoiceDirection.PAYABLE_INVOICE,
            records=(rec,),
        ),
    )


def _verify_business_operation_invoice(bucket_id: str) -> None:
    from ...ledger import BusinessOperationInvoiceRepository

    document = BusinessOperationInvoiceRepository().load(f"{bucket_id}:payable_invoice")
    assert document is not None, "business operation invoice lost"
    assert document.records, "business operation invoice lost"


def _filed_declaration_store() -> FiledDeclaracionObservationStore:
    return FiledDeclaracionObservationStore(Path("unused"), objects=secure_object_repository_for_active_bucket())


def _filed_artefact(body: bytes) -> FiledDeclaracionArtefact:
    from pydantic import AnyHttpUrl

    return FiledDeclaracionArtefact(
        kind="register_row",
        source_url=AnyHttpUrl(aeat_url("sede", "/x")),
        content_type="text/html",
        byte_count=len(body),
        sha256=sha256_hex(body),
        captured_at=_NOW,
    )


def _seed_filed_observation(bucket_id: str) -> None:
    from ....core import Period

    fobs = FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "1T"),
        expediente_id="202300000001T",
        status="presentada",
        presented_at=_NOW,
        authenticated_identity="12345678Z",
        artefacts=(_filed_artefact(b"<row/>"),),
    )
    _filed_declaration_store().persist_observation(fobs)


def _verify_filed_observation(bucket_id: str) -> None:
    assert _filed_declaration_store().list_observations(), "filed declaration observation lost"


def _seed_filed_artefact(bucket_id: str) -> None:
    from ....core import Period

    body = b"<row/>"
    _filed_declaration_store().persist_artefact(
        ("303", 2024, Period.from_year_and_code(2024, "1T"), "202300000001T"),
        _filed_artefact(body),
        body,
    )


def _verify_filed_artefact(bucket_id: str) -> None:
    repo = secure_object_repository_for_active_bucket()
    assert repo.list_keys("cadrumo.outbound.aeat.sede.filed_declaration.artefacts"), "filed declaration artefact lost"


def _seed_iva_wallet_observation(bucket_id: str) -> None:
    from pydantic import AnyHttpUrl

    from ....core import Period

    wobs = IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2024,
        target_period=Period.from_year_and_code(2024, "1T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2023,
                generation_period=Period.from_year_and_code(2023, "1T"),
                pending_amount=Decimal("50.00"),
            ),
        ),
        total_pending=Decimal("50.00"),
        source_url=AnyHttpUrl(aeat_url("sede", "/cartera")),
        captured_at=_NOW,
    )
    _filed_declaration_store().persist_iva_wallet_observation(wobs)


def _verify_iva_wallet_observation(bucket_id: str) -> None:
    assert _filed_declaration_store().list_iva_wallet_observations(), "iva wallet observation lost"


_CASES: tuple[StoreCase, ...] = (
    StoreCase("cadrumo.ledger.classification.rules", _seed_classification_rule, _verify_classification_rule),
    StoreCase("cadrumo.auth.apoderado", _seed_apoderado, _verify_apoderado),
    StoreCase("cadrumo.domain.filing.amendments", _seed_amendment, _verify_amendment),
    StoreCase("cadrumo.persistence.profile.inventory", _seed_inventory_ledger, _verify_inventory_ledger),
    StoreCase("cadrumo.persistence.profile.assets", _seed_assets_ledger, _verify_assets_ledger),
    StoreCase(
        "cadrumo.persistence.profile.assets.amortization",
        _seed_amortization_ledger,
        _verify_amortization_ledger,
    ),
    StoreCase("cadrumo.application.live.borrador_100_snapshot", _seed_borrador_100, _verify_borrador_100),
    StoreCase("cadrumo.application.modelo.m036_declaration", _seed_m036, _verify_m036),
    StoreCase("cadrumo.application.live.verify_observations", _seed_verify_observation, _verify_verify_observation),
    StoreCase("cadrumo.application.user_profile.snapshot", _seed_user_profile_snapshot, _verify_user_profile_snapshot),
    StoreCase("cadrumo.calculations.observations", _seed_observations, _verify_observations),
    StoreCase("cadrumo.retenciones.observations", _seed_retencion, _verify_retencion),
    StoreCase("cadrumo.withholding.observations", _seed_withholding, _verify_withholding),
    StoreCase(
        "cadrumo.application.ledger.purchase_invoice_evidence",
        _seed_purchase_invoice_evidence,
        _verify_purchase_invoice_evidence,
    ),
    StoreCase(
        "cadrumo.application.ledger.business_operation_invoices",
        _seed_business_operation_invoice,
        _verify_business_operation_invoice,
    ),
    StoreCase(
        "cadrumo.outbound.aeat.sede.filed_declaration.observations",
        _seed_filed_observation,
        _verify_filed_observation,
    ),
    StoreCase(
        "cadrumo.outbound.aeat.sede.filed_declaration.artefacts",
        _seed_filed_artefact,
        _verify_filed_artefact,
    ),
    StoreCase(
        "cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations",
        _seed_iva_wallet_observation,
        _verify_iva_wallet_observation,
    ),
    StoreCase("cadrumo.domain.submission.records", _seed_submission, _verify_submission),
    StoreCase("cadrumo.application.evidence.bundles", _seed_evidence_bundle, _verify_evidence_bundle),
    StoreCase("cadrumo.calculations.iva_compensation.history", _seed_iva_compensation, _verify_iva_compensation),
    StoreCase("cadrumo.application.filing.history", _seed_filing_history, _verify_filing_history),
    StoreCase("cadrumo.domain.filing.drafts", _seed_draft, _verify_draft),
    StoreCase("cadrumo.domain.usage_ratios", _seed_usage_ratios, _verify_usage_ratios),
    StoreCase("cadrumo.domain.invoices", _seed_invoice_catalogue, _verify_invoice_catalogue),
    StoreCase("cadrumo.domain.modelos.verification_reports", _seed_verification_reports, _verify_verification_reports),
    StoreCase(
        "cadrumo.calculations.iva_wallet.reconciliation_decisions",
        _seed_iva_wallet_decision,
        _verify_iva_wallet_decision,
    ),
    StoreCase(
        "cadrumo.application.live.iva_remote_state_acquisitions",
        _seed_iva_remote_state,
        _verify_iva_remote_state,
    ),
    StoreCase(
        "cadrumo.application.live.justificante_capture_snapshot",
        _seed_justificante_capture,
        _verify_justificante_capture,
    ),
    StoreCase("cadrumo.application.live.notifications_snapshot", _seed_notifications, _verify_notifications),
    StoreCase("cadrumo.application.live.expedientes_snapshot", _seed_expedientes, _verify_expedientes),
)


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: dict[str, UserProfileFact] = {}
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                path = f"{section.key}.{field.key}"
                facts[path] = UserProfileFact(path=path, value="placeholder")
    facts.update(
        {
            "taxpayer_type.entity_type": UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            "identity.name": UserProfileFact(path="identity.name", value="Matrix"),
            "identity.surnames": UserProfileFact(path="identity.surnames", value="Source"),
            "identity.tax_id": UserProfileFact(path="identity.tax_id", value="12345678Z"),
        },
    )
    return tuple(facts.values())


@pytest.fixture
def source_runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_LABEL) as profile:
        from ...user_profile._lifecycle import ProfileLifecycleService
        from ...user_profile._repository import UserProfileLifecycleRepository
        from ...user_profile._validation import ProfileValidationService

        schema = resources().user_profile_schema.singleton
        assert isinstance(schema, ProfileSchemaDefinition)
        ProfileLifecycleService(
            repository=UserProfileLifecycleRepository(bucket_id=profile.bucket_id, objects=profile.repository),
            validator=ProfileValidationService(schema=schema),
            events=BucketEventHistoryRepository(objects=profile.repository),
        ).register(
            RegisterProfileCommand(profile_id=profile.bucket_id, display_name=_LABEL, facts=_required_facts(schema)),
        )
        yield profile


def test_every_carried_store_round_trips_through_recovery(
    source_runtime: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    bucket_id = source_runtime.bucket_id
    for case in _CASES:
        case.seed(bucket_id)

    # Also populate a deliberately-excluded PROCESS_LOCAL store (as a real bucket
    # does: workflow/credential state) so the full export proves it tolerates an
    # excluded-but-populated namespace end to end rather than failing the gate.
    from ....core.classification import SensitivityClass

    source_runtime.repository.save(
        namespace="cadrumo.workflow",
        object_key="state",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_NOW,
        payload=(b'{"schema_version":1,"written_at":"2026-06-30T00:00:00Z","classification":"financial","payload":{}}'),
    )

    archive = tmp_path / "exports" / "matrix.cadrumo-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(bucket_id=bucket_id, output_path=archive, recovery_wrap_passphrase=_RECOVERY),
    )

    with isolated_profile_storage_root(tmp_path=tmp_path / "recipient"):
        BucketMaintenanceService().import_(
            ImportBucketCommand(source_path=archive, recovery_wrap_passphrase=_RECOVERY),
        )
        with profile_storage_session(bucket_id):
            failures: list[str] = []
            for case in _CASES:
                try:
                    case.verify(bucket_id)
                except Exception as exc:
                    failures.append(f"{case.namespace}: {exc!r}")
            assert not failures, "stores lost across recovery:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# S74/S78: recovery lifecycle custody matrix.
#
# The recovery and passphrase lifecycle operations rewrap the master key under
# a file passphrase, which only the encrypted-file backend supports. This
# matrix proves the file backend works and that the keyring and unsecured
# backends refuse every lifecycle operation with a typed SecretStoreError
# before touching any custody artefact.
# ---------------------------------------------------------------------------

_RECOVERY_NOW = datetime(2026, 6, 30, 6, 0, 0, tzinfo=UTC)
_RECOVERY_PASSPHRASE = "correct horse battery staple"  # noqa: S105 - synthetic test fixture


def test_file_custody_supports_the_full_recovery_lifecycle(tmp_path: Path) -> None:
    from ....adapters.persistence.storage.master_key import (
        FileFallbackMasterKeyProvider,
        RecoveryEnrollmentOutcome,
        recovery_create,
        recovery_recover,
        recovery_rotate,
        recovery_status,
        recovery_verify,
    )

    store_dir = tmp_path / "secrets"
    provider = FileFallbackMasterKeyProvider(store_dir=store_dir, passphrase_callback=lambda: _RECOVERY_PASSPHRASE)
    provider.provision_master_key()
    path = store_dir / "master.recovery.key"

    assert recovery_status(path=path).enrolled is False

    staged: dict[str, str] = {}

    def _capture(mnemonic: str) -> str:
        staged["mnemonic"] = mnemonic
        return mnemonic

    created = recovery_create(provider=provider, path=path, created_at=_RECOVERY_NOW, confirm=_capture)
    assert isinstance(created, RecoveryEnrollmentOutcome)
    assert recovery_status(path=path).enrolled is True
    assert recovery_verify(provider=provider, path=path, mnemonic=staged["mnemonic"]).verified is True

    rotated = recovery_rotate(provider=provider, path=path, created_at=_RECOVERY_NOW, confirm=_capture)
    assert rotated.rotated is True

    _new_passphrase = f"{dev_test_database_password()}-rotated"
    recover_provider = FileFallbackMasterKeyProvider(
        store_dir=store_dir, passphrase_callback=lambda: _new_passphrase
    )
    recovered = recovery_recover(provider=recover_provider, path=path, mnemonic=staged["mnemonic"])
    assert recovered.recovery_fingerprint == rotated.recovery_fingerprint


@pytest.mark.parametrize("backend", ["keyring", "unsecured"])
def test_non_file_custody_refuses_every_recovery_operation(tmp_path: Path, backend: str) -> None:
    from ....adapters.persistence.storage import SecretStoreError
    from ....adapters.persistence.storage.master_key import (
        KeyringMasterKeyProvider,
        UnsecuredMasterKeyProvider,
        recovery_create,
        recovery_recover,
        recovery_rotate,
        recovery_verify,
    )

    provider = KeyringMasterKeyProvider() if backend == "keyring" else UnsecuredMasterKeyProvider()
    path = tmp_path / "secrets" / "master.recovery.key"

    def _echo(mnemonic: str) -> str:
        return mnemonic

    with pytest.raises(SecretStoreError):
        recovery_create(provider=provider, path=path, created_at=_RECOVERY_NOW, confirm=_echo)
    with pytest.raises(SecretStoreError):
        recovery_rotate(provider=provider, path=path, created_at=_RECOVERY_NOW, confirm=_echo)
    with pytest.raises(SecretStoreError):
        recovery_verify(provider=provider, path=path, mnemonic="a b c")
    with pytest.raises(SecretStoreError):
        recovery_recover(provider=provider, path=path, mnemonic="a b c")

    # A refused operation never creates the recovery envelope.
    assert not path.exists()
