"""CLI transport access to the root-composed state-projection ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import typer

from ...core.errors.hierarchy import InternalInvariantError
from ..adapter_composition import ProfileAdapterComposition

if TYPE_CHECKING:
    from ...application.aggregation.percepciones_observations_repository import PercepcionObservationPortsFactory
    from ...application.aggregation.retencion_observations_repository import RetencionObservationPortsFactory
    from ...application.aggregation.withholding_observation_service import WithholdingObservationService
    from ...application.auth.apoderado_repository import ApoderadoConfigurationRepositoryFactory
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
    from ...application.user_profile.profile_read_ports import ProfileReadPortsFactory
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_ADAPTER_COMPOSITION_KEY = "adapter_composition"
_AUTHORITY_OPERATION_KEY = "authority_operation"


def _adapter_composition(ctx: typer.Context) -> ProfileAdapterComposition:
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_ADAPTER_COMPOSITION_KEY)
    if not isinstance(value, ProfileAdapterComposition):
        raise InternalInvariantError("profile adapter composition was not entered")
    return value


def authority_operation(ctx: typer.Context) -> PinnedAuthorityOperation:
    """Return one lazy generation pin owned by the root command context."""
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

    root = ctx.find_root()
    root_state = cast("dict[str, object]", root.ensure_object(dict))
    existing = root_state.get(_AUTHORITY_OPERATION_KEY)
    if isinstance(existing, PinnedAuthorityOperation):
        return existing
    operation = root.with_resource(bundled_indexed_authority().operation())
    root_state[_AUTHORITY_OPERATION_KEY] = operation
    return operation


def state_projection_read_ports(ctx: typer.Context) -> StateProjectionReadPorts:
    """Return the required bundle composed by the executable CLI root."""
    return _adapter_composition(ctx).state_projection_read_ports


def diagnostics_ports(ctx: typer.Context) -> DiagnosticsPorts:
    """Return the required diagnostics capabilities composed by the CLI root."""
    return _adapter_composition(ctx).diagnostics_ports


def certificate_secret_backend_factory(ctx: typer.Context) -> CertificateSecretBackendFactory:
    """Return the certificate-secret factory supplied by the CLI composition root."""
    return _adapter_composition(ctx).certificate_secret_backend_factory


def operator_probe_ports(ctx: typer.Context) -> OperatorProbePorts:
    """Return the operator-probe capabilities supplied by the CLI root."""
    return _adapter_composition(ctx).operator_probe_ports


def operator_scope_ports(ctx: typer.Context) -> OperatorScopePorts:
    """Return the operator-scope capabilities supplied by the CLI root."""
    return _adapter_composition(ctx).operator_scope_ports


def bucket_storage(ctx: typer.Context) -> ProfileBucketStoragePort:
    """Return the bucket layout and lock capability composed by the CLI root."""
    return _adapter_composition(ctx).bucket_storage


def verification_repository_bundle_factory(ctx: typer.Context) -> VerificationRepositoryBundleFactory:
    """Return the required verification bundle factory from the CLI root."""
    return _adapter_composition(ctx).verification_repository_bundle_factory


def profile_read_ports_factory(ctx: typer.Context) -> ProfileReadPortsFactory:
    """Return the per-bucket profile read ports factory from the CLI root."""
    return _adapter_composition(ctx).profile_read_ports_factory


def calculation_action_ports_factory(ctx: typer.Context) -> CalculationActionPortsFactory:
    """Return the required calculation bundle factory from the CLI root."""
    return _adapter_composition(ctx).calculation_action_ports_factory


def amendment_action_ports_factory(ctx: typer.Context) -> AmendmentActionPortsFactory:
    """Return the required amendment bundle factory from the CLI root."""
    return _adapter_composition(ctx).amendment_action_ports_factory


def filing_action_ports_factory(ctx: typer.Context) -> FilingActionPortsFactory:
    """Return the required filing bundle factory from the CLI root."""
    return _adapter_composition(ctx).filing_action_ports_factory


def bienes_inversion_repository_factory(ctx: typer.Context) -> BienesInversionIvaRegisterRepositoryFactory:
    """Return the required bucket-bound bienes-inversión register factory."""
    return _adapter_composition(ctx).bienes_inversion_repository_factory


def expedientes_ports_factory(ctx: typer.Context) -> ExpedientesPortsFactory:
    """Return the required expedientes bundle factory from the CLI root."""
    return _adapter_composition(ctx).expedientes_ports_factory


def borrador_100_snapshot_repository_factory(ctx: typer.Context) -> Borrador100SnapshotRepositoryFactory:
    """Return the required borrador snapshot repository factory from the CLI root."""
    return _adapter_composition(ctx).borrador_100_snapshot_repository_factory


def censal_fetch_port(ctx: typer.Context) -> CensalFetchPort:
    """Return the translated censo fetch capability from the CLI root."""
    return _adapter_composition(ctx).censal_fetch_port


def retencion_observation_ports_factory(ctx: typer.Context) -> RetencionObservationPortsFactory:
    """Return the required retención observation capability factory from the CLI root."""
    return _adapter_composition(ctx).retencion_observation_ports_factory


def withholding_observation_service(ctx: typer.Context, *, bucket_id: str) -> WithholdingObservationService:
    """Return the root-composed atomic withholding mutation service."""
    return _adapter_composition(ctx).withholding_observation_service_factory(bucket_id)


def percepcion_observation_ports_factory(ctx: typer.Context) -> PercepcionObservationPortsFactory:
    """Return the required percepciones capability factory from the CLI root."""
    return _adapter_composition(ctx).percepcion_observation_ports_factory


def ledger_evidence_ports_factory(ctx: typer.Context) -> LedgerEvidencePortsFactory:
    """Return the required ledger-evidence bundle factory from the CLI root."""
    return _adapter_composition(ctx).ledger_evidence_ports_factory


def invoice_confirmation_ports_factory(ctx: typer.Context) -> InvoiceConfirmationPortsFactory:
    """Return the required invoice-confirmation bundle factory from the CLI root."""
    return _adapter_composition(ctx).invoice_confirmation_ports_factory


def counterparty_establishment_repository_factory(
    ctx: typer.Context,
) -> CounterpartyEstablishmentRepositoryFactory:
    """Return the remembered-counterparty store factory from the CLI root."""
    return _adapter_composition(ctx).counterparty_establishment_repository_factory


def catalogue_creation_ports_factory(ctx: typer.Context) -> CatalogueCreationPortsFactory:
    """Return the required catalogue-creation bundle factory from the CLI root."""
    return _adapter_composition(ctx).catalogue_creation_ports_factory


def catalogue_lifecycle_ports_factory(ctx: typer.Context) -> CatalogueLifecyclePortsFactory:
    """Return the required catalogue-lifecycle bundle factory from the CLI root."""
    return _adapter_composition(ctx).catalogue_lifecycle_ports_factory


def modelo_export_ports_factory(ctx: typer.Context) -> ModeloExportPortsFactory:
    """Return the required Modelo export bundle factory from the CLI root."""
    return _adapter_composition(ctx).modelo_export_ports_factory


def modelo_edit_receipt_repository_factory(ctx: typer.Context) -> ModeloEditReceiptRepositoryFactory:
    """Return the required Modelo edit-receipt capability factory from the CLI root."""
    return _adapter_composition(ctx).modelo_edit_receipt_repository_factory


def modelo_history_ports_factory(ctx: typer.Context) -> ModeloHistoryPortsFactory:
    """Return the history capabilities supplied by the CLI composition root."""
    return _adapter_composition(ctx).modelo_history_ports_factory


def participation_index_rebuild_ports_factory(ctx: typer.Context) -> ParticipationIndexRebuildPortsFactory:
    """Return the participation-index rebuild capabilities supplied by the CLI root."""
    return _adapter_composition(ctx).participation_index_rebuild_ports_factory


def prorrata_register_repository_factory(ctx: typer.Context) -> ProrrataRegisterRepositoryFactory:
    """Return the required prorrata register capability factory from the CLI root."""
    return _adapter_composition(ctx).prorrata_register_repository_factory


def inventory_service_ports_factory(ctx: typer.Context) -> InventoryServicePortsFactory:
    """Return the required inventory capability factory from the CLI root."""
    return _adapter_composition(ctx).inventory_service_ports_factory


def draft_review_ports_factory(ctx: typer.Context) -> DraftReviewPortsFactory:
    """Return the required draft-review bundle factory from the CLI root."""
    return _adapter_composition(ctx).draft_review_ports_factory


def modelo_iva_wallet_seed_ports_factory(ctx: typer.Context) -> ModeloIvaWalletSeedPortsFactory:
    """Return the IVA-wallet seed capabilities supplied by the CLI root."""
    return _adapter_composition(ctx).modelo_iva_wallet_seed_ports_factory


def m145_communication_records_ports_factory(ctx: typer.Context) -> M145CommunicationRecordsPortsFactory:
    """Return the Modelo 145 communication-record capabilities from the CLI root."""
    return _adapter_composition(ctx).m145_communication_records_ports_factory


def m036_lifecycle_ports_factory(ctx: typer.Context) -> M036LifecyclePortsFactory:
    """Return the Modelo 036 lifecycle capabilities from the CLI root."""
    return _adapter_composition(ctx).m036_lifecycle_ports_factory


def work_lifecycle_ports_factory(ctx: typer.Context) -> WorkLifecyclePortsFactory:
    """Return the required work-lifecycle bundle factory from the CLI root."""
    return _adapter_composition(ctx).work_lifecycle_ports_factory


def recipient_fingerprint_registry_ports_factory(ctx: typer.Context) -> RecipientFingerprintRegistryPortsFactory:
    """Return the trusted-recipient registry capability from the CLI root."""
    return _adapter_composition(ctx).recipient_fingerprint_registry_ports_factory


def recipient_encryption_capability_factory(ctx: typer.Context) -> RecipientEncryptionCapabilityFactory:
    """Return the recipient-encryption capability factory composed by the CLI root."""
    return _adapter_composition(ctx).recipient_encryption_capability_factory


def review_package_signing_keypair_capability_factory(
    ctx: typer.Context,
) -> ReviewPackageSigningKeypairCapabilityFactory:
    """Return the review-package signing-keypair capability from the CLI root."""
    return _adapter_composition(ctx).review_package_signing_keypair_capability_factory


def apoderado_config_repository_factory(ctx: typer.Context) -> ApoderadoConfigurationRepositoryFactory:
    """Return the apoderado configuration store factory from the CLI root."""
    return _adapter_composition(ctx).apoderado_config_repository_factory


__all__ = [
    "amendment_action_ports_factory",
    "apoderado_config_repository_factory",
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
    "withholding_observation_service",
    "work_lifecycle_ports_factory",
]
