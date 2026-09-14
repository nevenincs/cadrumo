"""CLI transport access to the root-composed state-projection ports."""

from __future__ import annotations

from typing import cast

import typer

from ...application.aggregation.percepciones_observations_repository import PercepcionObservationPortsFactory
from ...application.aggregation.retencion_observations_repository import RetencionObservationPortsFactory
from ...application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...application.auth.operator_probe_ports import OperatorProbePorts
from ...application.auth.operator_scope_ports import OperatorScopePorts
from ...application.bienes_inversion.ports import BienesInversionIvaRegisterRepositoryFactory
from ...application.diagnostics_ports import DiagnosticsPorts
from ...application.filing.draft_review_ports import DraftReviewPortsFactory
from ...application.inventory.ports import InventoryServicePortsFactory
from ...application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from ...application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
from ...application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
from ...application.ledger.evidence_ports import LedgerEvidencePortsFactory
from ...application.ledger.invoice_confirmation_ports import InvoiceConfirmationPortsFactory
from ...application.live.borrador_100 import Borrador100SnapshotRepositoryFactory
from ...application.live.censo_ports import CensalFetchPort
from ...application.live.expedientes_ports import ExpedientesPortsFactory
from ...application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ...application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ...application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from ...application.modelo.export_ports import ModeloExportPortsFactory
from ...application.modelo.filing_action_ports import FilingActionPortsFactory
from ...application.modelo.history_ports import ModeloHistoryPortsFactory
from ...application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory
from ...application.modelo.m036_lifecycle_ports import M036LifecyclePortsFactory
from ...application.modelo.m145_communication_records_ports import M145CommunicationRecordsPortsFactory
from ...application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
from ...application.modelo.recipient_encryption import RecipientEncryptionCapabilityFactory
from ...application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory
from ...application.modelo.review_package_signing_ports import ReviewPackageSigningKeypairCapabilityFactory
from ...application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
from ...application.modelo.work_lifecycle_ports import WorkLifecyclePortsFactory
from ...application.prorrata_register.ports import ProrrataRegisterRepositoryFactory
from ...application.state_projection_ports import StateProjectionReadPorts
from ...application.user_profile.custody_ports import ProfileBucketStoragePort
from ...core.errors.hierarchy import InternalInvariantError

_STATE_PROJECTION_PORTS_KEY = "state_projection_read_ports"
_DIAGNOSTICS_PORTS_KEY = "diagnostics_ports"
_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY = "certificate_secret_backend_factory"
_OPERATOR_PROBE_PORTS_KEY = "operator_probe_ports"
_OPERATOR_SCOPE_PORTS_KEY = "operator_scope_ports"
_VERIFICATION_REPOSITORY_BUNDLE_FACTORY_KEY = "verification_repository_bundle_factory"
_CALCULATION_ACTION_PORTS_FACTORY_KEY = "calculation_action_ports_factory"
_AMENDMENT_ACTION_PORTS_FACTORY_KEY = "amendment_action_ports_factory"
_FILING_ACTION_PORTS_FACTORY_KEY = "filing_action_ports_factory"
_BIENES_INVERSION_REPOSITORY_FACTORY_KEY = "bienes_inversion_repository_factory"
_BORRADOR_100_SNAPSHOT_REPOSITORY_FACTORY_KEY = "borrador_100_snapshot_repository_factory"
_CENSAL_FETCH_PORT_KEY = "censal_fetch_port"
_RETENCION_OBSERVATION_PORTS_FACTORY_KEY = "retencion_observation_ports_factory"
_PERCEPCION_OBSERVATION_PORTS_FACTORY_KEY = "percepcion_observation_ports_factory"
_EXPEDIENTES_PORTS_FACTORY_KEY = "expedientes_ports_factory"
_LEDGER_EVIDENCE_PORTS_FACTORY_KEY = "ledger_evidence_ports_factory"
_INVOICE_CONFIRMATION_PORTS_FACTORY_KEY = "invoice_confirmation_ports_factory"
_COUNTERPARTY_ESTABLISHMENT_REPOSITORY_FACTORY_KEY = "counterparty_establishment_repository_factory"
_CATALOGUE_CREATION_PORTS_FACTORY_KEY = "catalogue_creation_ports_factory"
_CATALOGUE_LIFECYCLE_PORTS_FACTORY_KEY = "catalogue_lifecycle_ports_factory"
_MODELO_EXPORT_PORTS_FACTORY_KEY = "modelo_export_ports_factory"
_MODELO_EDIT_RECEIPT_REPOSITORY_FACTORY_KEY = "modelo_edit_receipt_repository_factory"
_MODELO_HISTORY_PORTS_FACTORY_KEY = "modelo_history_ports_factory"
_PARTICIPATION_INDEX_REBUILD_PORTS_FACTORY_KEY = "participation_index_rebuild_ports_factory"
_INVENTORY_SERVICE_PORTS_FACTORY_KEY = "inventory_service_ports_factory"
_DRAFT_REVIEW_PORTS_FACTORY_KEY = "draft_review_ports_factory"
_MODELO_IVA_WALLET_SEED_PORTS_FACTORY_KEY = "modelo_iva_wallet_seed_ports_factory"
_M145_COMMUNICATION_RECORDS_PORTS_FACTORY_KEY = "m145_communication_records_ports_factory"
_M036_LIFECYCLE_PORTS_FACTORY_KEY = "m036_lifecycle_ports_factory"
_WORK_LIFECYCLE_PORTS_FACTORY_KEY = "work_lifecycle_ports_factory"
_RECIPIENT_FINGERPRINT_REGISTRY_PORTS_FACTORY_KEY = "recipient_fingerprint_registry_ports_factory"
_RECIPIENT_ENCRYPTION_CAPABILITY_FACTORY_KEY = "recipient_encryption_capability_factory"
_REVIEW_PACKAGE_SIGNING_KEYPAIR_CAPABILITY_FACTORY_KEY = "review_package_signing_keypair_capability_factory"
_PRORRATA_REGISTER_REPOSITORY_FACTORY_KEY = "prorrata_register_repository_factory"
_BUCKET_STORAGE_KEY = "bucket_storage"


def state_projection_read_ports(ctx: typer.Context) -> StateProjectionReadPorts:
    """Return the required bundle composed by the executable CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_STATE_PROJECTION_PORTS_KEY)
    if not isinstance(value, StateProjectionReadPorts):
        raise InternalInvariantError("state projection read ports were not composed")
    return value


def diagnostics_ports(ctx: typer.Context) -> DiagnosticsPorts:
    """Return the required diagnostics capabilities composed by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_DIAGNOSTICS_PORTS_KEY)
    if not isinstance(value, DiagnosticsPorts):
        raise InternalInvariantError("diagnostics ports were not composed")
    return value


def certificate_secret_backend_factory(ctx: typer.Context) -> CertificateSecretBackendFactory:
    """Return the certificate-secret factory supplied by the CLI composition root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CertificateSecretBackendFactory, root_state[_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY])


def operator_probe_ports(ctx: typer.Context) -> OperatorProbePorts:
    """Return the operator-probe capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_OPERATOR_PROBE_PORTS_KEY)
    if not isinstance(value, OperatorProbePorts):
        raise InternalInvariantError("operator probe ports were not composed")
    return value


def operator_scope_ports(ctx: typer.Context) -> OperatorScopePorts:
    """Return the operator-scope capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_OPERATOR_SCOPE_PORTS_KEY)
    if not isinstance(value, OperatorScopePorts):
        raise InternalInvariantError("operator scope ports were not composed")
    return value


def bucket_storage(ctx: typer.Context) -> ProfileBucketStoragePort:
    """Return the bucket layout and lock capability composed by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ProfileBucketStoragePort, root_state[_BUCKET_STORAGE_KEY])


def verification_repository_bundle_factory(ctx: typer.Context) -> VerificationRepositoryBundleFactory:
    """Return the required verification bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(VerificationRepositoryBundleFactory, root_state[_VERIFICATION_REPOSITORY_BUNDLE_FACTORY_KEY])


def calculation_action_ports_factory(ctx: typer.Context) -> CalculationActionPortsFactory:
    """Return the required calculation bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CalculationActionPortsFactory, root_state[_CALCULATION_ACTION_PORTS_FACTORY_KEY])


def amendment_action_ports_factory(ctx: typer.Context) -> AmendmentActionPortsFactory:
    """Return the required amendment bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(AmendmentActionPortsFactory, root_state[_AMENDMENT_ACTION_PORTS_FACTORY_KEY])


def filing_action_ports_factory(ctx: typer.Context) -> FilingActionPortsFactory:
    """Return the required filing bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(FilingActionPortsFactory, root_state[_FILING_ACTION_PORTS_FACTORY_KEY])


def bienes_inversion_repository_factory(ctx: typer.Context) -> BienesInversionIvaRegisterRepositoryFactory:
    """Return the required bucket-bound bienes-inversión register factory."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(BienesInversionIvaRegisterRepositoryFactory, root_state[_BIENES_INVERSION_REPOSITORY_FACTORY_KEY])


def expedientes_ports_factory(ctx: typer.Context) -> ExpedientesPortsFactory:
    """Return the required expedientes bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ExpedientesPortsFactory, root_state[_EXPEDIENTES_PORTS_FACTORY_KEY])


def borrador_100_snapshot_repository_factory(ctx: typer.Context) -> Borrador100SnapshotRepositoryFactory:
    """Return the required borrador snapshot repository factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(Borrador100SnapshotRepositoryFactory, root_state[_BORRADOR_100_SNAPSHOT_REPOSITORY_FACTORY_KEY])


def censal_fetch_port(ctx: typer.Context) -> CensalFetchPort:
    """Return the translated censo fetch capability from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CensalFetchPort, root_state[_CENSAL_FETCH_PORT_KEY])


def retencion_observation_ports_factory(ctx: typer.Context) -> RetencionObservationPortsFactory:
    """Return the required retención observation capability factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(RetencionObservationPortsFactory, root_state[_RETENCION_OBSERVATION_PORTS_FACTORY_KEY])


def percepcion_observation_ports_factory(ctx: typer.Context) -> PercepcionObservationPortsFactory:
    """Return the required percepciones capability factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(PercepcionObservationPortsFactory, root_state[_PERCEPCION_OBSERVATION_PORTS_FACTORY_KEY])


def ledger_evidence_ports_factory(ctx: typer.Context) -> LedgerEvidencePortsFactory:
    """Return the required ledger-evidence bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(LedgerEvidencePortsFactory, root_state[_LEDGER_EVIDENCE_PORTS_FACTORY_KEY])


def invoice_confirmation_ports_factory(ctx: typer.Context) -> InvoiceConfirmationPortsFactory:
    """Return the required invoice-confirmation bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(InvoiceConfirmationPortsFactory, root_state[_INVOICE_CONFIRMATION_PORTS_FACTORY_KEY])


def counterparty_establishment_repository_factory(
    ctx: typer.Context,
) -> CounterpartyEstablishmentRepositoryFactory:
    """Return the remembered-counterparty store factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(
        CounterpartyEstablishmentRepositoryFactory,
        root_state[_COUNTERPARTY_ESTABLISHMENT_REPOSITORY_FACTORY_KEY],
    )


def catalogue_creation_ports_factory(ctx: typer.Context) -> CatalogueCreationPortsFactory:
    """Return the required catalogue-creation bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CatalogueCreationPortsFactory, root_state[_CATALOGUE_CREATION_PORTS_FACTORY_KEY])


def catalogue_lifecycle_ports_factory(ctx: typer.Context) -> CatalogueLifecyclePortsFactory:
    """Return the required catalogue-lifecycle bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CatalogueLifecyclePortsFactory, root_state[_CATALOGUE_LIFECYCLE_PORTS_FACTORY_KEY])


def modelo_export_ports_factory(ctx: typer.Context) -> ModeloExportPortsFactory:
    """Return the required Modelo export bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloExportPortsFactory, root_state[_MODELO_EXPORT_PORTS_FACTORY_KEY])


def modelo_edit_receipt_repository_factory(ctx: typer.Context) -> ModeloEditReceiptRepositoryFactory:
    """Return the required Modelo edit-receipt capability factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloEditReceiptRepositoryFactory, root_state[_MODELO_EDIT_RECEIPT_REPOSITORY_FACTORY_KEY])


def modelo_history_ports_factory(ctx: typer.Context) -> ModeloHistoryPortsFactory:
    """Return the history capabilities supplied by the CLI composition root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloHistoryPortsFactory, root_state[_MODELO_HISTORY_PORTS_FACTORY_KEY])


def participation_index_rebuild_ports_factory(ctx: typer.Context) -> ParticipationIndexRebuildPortsFactory:
    """Return the participation-index rebuild capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ParticipationIndexRebuildPortsFactory, root_state[_PARTICIPATION_INDEX_REBUILD_PORTS_FACTORY_KEY])


def prorrata_register_repository_factory(ctx: typer.Context) -> ProrrataRegisterRepositoryFactory:
    """Return the required prorrata register capability factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ProrrataRegisterRepositoryFactory, root_state[_PRORRATA_REGISTER_REPOSITORY_FACTORY_KEY])


def inventory_service_ports_factory(ctx: typer.Context) -> InventoryServicePortsFactory:
    """Return the required inventory capability factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(InventoryServicePortsFactory, root_state[_INVENTORY_SERVICE_PORTS_FACTORY_KEY])


def draft_review_ports_factory(ctx: typer.Context) -> DraftReviewPortsFactory:
    """Return the required draft-review bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(DraftReviewPortsFactory, root_state[_DRAFT_REVIEW_PORTS_FACTORY_KEY])


def modelo_iva_wallet_seed_ports_factory(ctx: typer.Context) -> ModeloIvaWalletSeedPortsFactory:
    """Return the IVA-wallet seed capabilities supplied by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(ModeloIvaWalletSeedPortsFactory, root_state[_MODELO_IVA_WALLET_SEED_PORTS_FACTORY_KEY])


def m145_communication_records_ports_factory(ctx: typer.Context) -> M145CommunicationRecordsPortsFactory:
    """Return the Modelo 145 communication-record capabilities from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(M145CommunicationRecordsPortsFactory, root_state[_M145_COMMUNICATION_RECORDS_PORTS_FACTORY_KEY])


def m036_lifecycle_ports_factory(ctx: typer.Context) -> M036LifecyclePortsFactory:
    """Return the Modelo 036 lifecycle capabilities from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(M036LifecyclePortsFactory, root_state[_M036_LIFECYCLE_PORTS_FACTORY_KEY])


def work_lifecycle_ports_factory(ctx: typer.Context) -> WorkLifecyclePortsFactory:
    """Return the required work-lifecycle bundle factory from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(WorkLifecyclePortsFactory, root_state[_WORK_LIFECYCLE_PORTS_FACTORY_KEY])


def recipient_fingerprint_registry_ports_factory(ctx: typer.Context) -> RecipientFingerprintRegistryPortsFactory:
    """Return the trusted-recipient registry capability from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(RecipientFingerprintRegistryPortsFactory, root_state[_RECIPIENT_FINGERPRINT_REGISTRY_PORTS_FACTORY_KEY])


def recipient_encryption_capability_factory(ctx: typer.Context) -> RecipientEncryptionCapabilityFactory:
    """Return the recipient-encryption capability factory composed by the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(RecipientEncryptionCapabilityFactory, root_state[_RECIPIENT_ENCRYPTION_CAPABILITY_FACTORY_KEY])


def review_package_signing_keypair_capability_factory(
    ctx: typer.Context,
) -> ReviewPackageSigningKeypairCapabilityFactory:
    """Return the review-package signing-keypair capability from the CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(
        ReviewPackageSigningKeypairCapabilityFactory, root_state[_REVIEW_PACKAGE_SIGNING_KEYPAIR_CAPABILITY_FACTORY_KEY]
    )


__all__ = [
    "amendment_action_ports_factory",
    "bienes_inversion_repository_factory",
    "borrador_100_snapshot_repository_factory",
    "bucket_storage",
    "calculation_action_ports_factory",
    "catalogue_creation_ports_factory",
    "catalogue_lifecycle_ports_factory",
    "censal_fetch_port",
    "certificate_secret_backend_factory",
    "counterparty_establishment_repository_factory",
    "diagnostics_ports",
    "draft_review_ports_factory",
    "expedientes_ports_factory",
    "filing_action_ports_factory",
    "inventory_service_ports_factory",
    "invoice_confirmation_ports_factory",
    "ledger_evidence_ports_factory",
    "m036_lifecycle_ports_factory",
    "m145_communication_records_ports_factory",
    "modelo_edit_receipt_repository_factory",
    "modelo_export_ports_factory",
    "modelo_history_ports_factory",
    "modelo_iva_wallet_seed_ports_factory",
    "operator_probe_ports",
    "operator_scope_ports",
    "participation_index_rebuild_ports_factory",
    "percepcion_observation_ports_factory",
    "prorrata_register_repository_factory",
    "recipient_encryption_capability_factory",
    "recipient_fingerprint_registry_ports_factory",
    "retencion_observation_ports_factory",
    "review_package_signing_keypair_capability_factory",
    "state_projection_read_ports",
    "verification_repository_bundle_factory",
    "work_lifecycle_ports_factory",
]
