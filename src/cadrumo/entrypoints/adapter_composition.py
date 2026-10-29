"""The adapter composition shared by the CLI and TUI entrypoints.

A frontend process must bind the persistence and outbound adapters the
application layer resolves through explicitly composed ports before it serves
any work. That inventory is a property of the product, not of the frontend, so
it is declared once here and entered by the CLI root and the TUI devtools
fixture. The separately shipped external client distribution owns its independent
composition root and does not import this entrypoint module.

An entrypoint that forgets this scope fails on every custody-touching verb,
which is exactly the symptom that made the original external client gap visible.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..application.aggregation.percepciones_observations_repository import (
        PercepcionObservationPortsFactory,
    )
    from ..application.aggregation.retencion_observations_repository import (
        RetencionObservationPortsFactory,
    )
    from ..application.aggregation.withholding_observation_service import WithholdingObservationService
    from ..application.auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..application.auth.operator_probe_ports import OperatorProbePorts
    from ..application.auth.operator_scope_ports import OperatorScopePorts
    from ..application.bienes_inversion.ports import (
        BienesInversionIvaRegisterRepositoryFactory,
    )
    from ..application.diagnostics_ports import DiagnosticsPorts
    from ..application.filing.draft_review_ports import DraftReviewPortsFactory
    from ..application.inventory.ports import InventoryServicePortsFactory
    from ..application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
    from ..application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
    from ..application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
    from ..application.ledger.evidence_ports import LedgerEvidencePortsFactory
    from ..application.ledger.invoice_confirmation_ports import InvoiceConfirmationPortsFactory
    from ..application.live.censo_ports import CensalFetchPort
    from ..application.live.expedientes_ports import ExpedientesPortsFactory
    from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
    from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
    from ..application.modelo.edit_receipt_ports import (
        ModeloEditReceiptRepositoryFactory,
    )
    from ..application.modelo.export_ports import ModeloExportPortsFactory
    from ..application.modelo.filing_action_ports import FilingActionPortsFactory
    from ..application.modelo.history_ports import ModeloHistoryPortsFactory
    from ..application.modelo.iva_wallet_seed_ports import (
        ModeloIvaWalletSeedPortsFactory,
    )
    from ..application.modelo.participation_index_rebuild_ports import (
        ParticipationIndexRebuildPortsFactory,
    )
    from ..application.modelo.recipient_encryption import RecipientEncryptionCapabilityFactory
    from ..application.modelo.review_package_recipient_registry_ports import (
        RecipientFingerprintRegistryPortsFactory,
    )
    from ..application.modelo.review_package_signing_ports import (
        ReviewPackageSigningKeypairCapabilityFactory,
    )
    from ..application.modelo.verification_repository_ports import (
        VerificationRepositoryBundleFactory,
    )
    from ..application.modelo.work_lifecycle_ports import WorkLifecyclePortsFactory
    from ..application.prorrata_register.ports import (
        ProrrataRegisterRepositoryFactory,
    )
    from ..application.state_projection_ports import StateProjectionReadPorts
    from ..application.user_profile.automation_custody_port import AutomationSecretStore
    from ..application.user_profile.custody_ports import ProfileBucketStoragePort, ProfileCustodyPort
    from ..application.user_profile.profile_read_ports import ProfileReadPortsFactory
    from ..domain.attachments.protocols import AttachmentStoreProtocol


from .adapter_composition_ports import (
    build_attachment_store,
    build_bienes_inversion_repository,
    build_censal_fetch_port,
    build_diagnostics_ports,
    build_draft_review_ports,
    build_inventory_service_ports,
    build_modelo_edit_receipt_repository,
    build_modelo_export_ports,
    build_modelo_history_ports,
    build_modelo_iva_wallet_seed_ports,
    build_operator_probe_ports,
    build_participation_index_rebuild_ports,
    build_percepcion_observation_ports,
    build_prorrata_register_repository,
    build_retencion_observation_ports,
    build_withholding_observation_service,
    profile_read_ports_for_bucket,
)
from .adapter_composition_work_ports import (
    bucket_event_history_repository,
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_expedientes_ports,
    build_filing_action_ports,
    build_ledger_evidence_ports,
    build_state_projection_read_ports,
    build_verification_repository_bundle,
    build_work_lifecycle_ports,
    calculation_revision_catalogue_repository,
    confirmation_record_repository,
    extraction_draft_repository,
    justificante_repository,
    ledger_classification_rule_repository,
    load_usage_ratios,
    load_usage_ratios_with_censo_guard,
    modelo_reconciliation_persistence,
    modelo_record_catalogue_repository,
    resolve_column_roles,
    save_usage_ratios,
    statement_reader,
    transaction_catalogue_repository,
    transaction_participation_index_repository,
    work_unit_catalogue_repository,
)


class ProfileAdapterComposition:
    """Concrete capabilities composed for one executable profile session.

    Each capability resolves on first read, so a command imports only the
    adapter trees it actually uses.
    """

    def __init__(self, *, profile_custody: ProfileCustodyPort) -> None:
        """Hold the custody port the session scope already bound."""
        self._profile_custody = profile_custody

    @cached_property
    def state_projection_read_ports(self) -> StateProjectionReadPorts:
        """Resolve the state projection read ports on first read."""
        return build_state_projection_read_ports(diagnostics_ports=self.diagnostics_ports, operation=None)

    @cached_property
    def diagnostics_ports(self) -> DiagnosticsPorts:
        """Resolve the diagnostics ports on first read."""
        return build_diagnostics_ports()

    @cached_property
    def certificate_secret_backend_factory(self) -> CertificateSecretBackendFactory:
        """Resolve the certificate secret backend factory on first read."""
        from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend

        return build_certificate_secret_backend

    @cached_property
    def operator_probe_ports(self) -> OperatorProbePorts:
        """Resolve the operator probe ports on first read."""
        return build_operator_probe_ports()

    @cached_property
    def operator_scope_ports(self) -> OperatorScopePorts:
        """Resolve the operator scope ports on first read."""
        from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports

        return build_operator_scope_ports()

    @cached_property
    def bucket_storage(self) -> ProfileBucketStoragePort:
        """Resolve the bucket storage on first read."""
        return self._profile_custody.bucket_storage()

    @property
    def verification_repository_bundle_factory(self) -> VerificationRepositoryBundleFactory:
        """Resolve the verification repository bundle factory on first read."""
        return build_verification_repository_bundle

    @property
    def profile_read_ports_factory(self) -> ProfileReadPortsFactory:
        """Resolve the per-bucket profile read ports factory."""
        return profile_read_ports_for_bucket

    @property
    def calculation_action_ports_factory(self) -> CalculationActionPortsFactory:
        """Resolve the calculation action ports factory on first read."""
        return build_calculation_action_ports

    @property
    def attachment_store_factory(self) -> Callable[[str], AttachmentStoreProtocol]:
        """Resolve the encrypted attachment custody store factory."""
        return build_attachment_store

    @property
    def amendment_action_ports_factory(self) -> AmendmentActionPortsFactory:
        """Resolve the amendment action ports factory on first read."""
        return build_amendment_action_ports

    @property
    def filing_action_ports_factory(self) -> FilingActionPortsFactory:
        """Resolve the filing action ports factory on first read."""
        return build_filing_action_ports

    @property
    def bienes_inversion_repository_factory(self) -> BienesInversionIvaRegisterRepositoryFactory:
        """Resolve the bienes inversion repository factory on first read."""
        return build_bienes_inversion_repository

    @property
    def retencion_observation_ports_factory(self) -> RetencionObservationPortsFactory:
        """Resolve the retencion observation ports factory on first read."""
        return build_retencion_observation_ports

    @property
    def withholding_observation_service_factory(self) -> Callable[[str], WithholdingObservationService]:
        """Resolve the sole atomic withholding mutation service for one bucket."""
        return lambda bucket_id: build_withholding_observation_service(bucket_id=bucket_id)

    @property
    def percepcion_observation_ports_factory(self) -> PercepcionObservationPortsFactory:
        """Resolve the percepcion observation ports factory on first read."""
        return build_percepcion_observation_ports

    @cached_property
    def censal_fetch_port(self) -> CensalFetchPort:
        """Resolve the censal fetch port on first read."""
        return build_censal_fetch_port()

    @property
    def expedientes_ports_factory(self) -> ExpedientesPortsFactory:
        """Resolve the expedientes ports factory on first read."""
        return build_expedientes_ports

    @property
    def ledger_evidence_ports_factory(self) -> LedgerEvidencePortsFactory:
        """Resolve the ledger evidence ports factory on first read."""
        return build_ledger_evidence_ports

    @cached_property
    def invoice_confirmation_ports_factory(self) -> InvoiceConfirmationPortsFactory:
        """Resolve the invoice confirmation ports factory on first read."""
        from ..adapters.persistence.profile.invoice_confirmation import build_invoice_confirmation_ports

        return build_invoice_confirmation_ports

    @cached_property
    def counterparty_establishment_repository_factory(self) -> CounterpartyEstablishmentRepositoryFactory:
        """Resolve the counterparty establishment repository factory on first read."""
        from ..adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )

        return build_counterparty_establishment_repository

    @property
    def inventory_service_ports_factory(self) -> InventoryServicePortsFactory:
        """Resolve the inventory service ports factory on first read."""
        return build_inventory_service_ports

    @cached_property
    def catalogue_creation_ports_factory(self) -> CatalogueCreationPortsFactory:
        """Resolve the catalogue creation ports factory on first read."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports

        return build_catalogue_creation_ports

    @cached_property
    def catalogue_lifecycle_ports_factory(self) -> CatalogueLifecyclePortsFactory:
        """Resolve the catalogue lifecycle ports factory on first read."""
        from ..adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports

        return build_catalogue_lifecycle_ports

    @property
    def draft_review_ports_factory(self) -> DraftReviewPortsFactory:
        """Resolve the draft review ports factory on first read."""
        return build_draft_review_ports

    @property
    def modelo_export_ports_factory(self) -> ModeloExportPortsFactory:
        """Resolve the modelo export ports factory on first read."""
        return build_modelo_export_ports

    @property
    def modelo_edit_receipt_repository_factory(self) -> ModeloEditReceiptRepositoryFactory:
        """Resolve the modelo edit receipt repository factory on first read."""
        return build_modelo_edit_receipt_repository

    @property
    def modelo_history_ports_factory(self) -> ModeloHistoryPortsFactory:
        """Resolve the modelo history ports factory on first read."""
        return build_modelo_history_ports

    @property
    def participation_index_rebuild_ports_factory(self) -> ParticipationIndexRebuildPortsFactory:
        """Resolve the participation index rebuild ports factory on first read."""
        return build_participation_index_rebuild_ports

    @cached_property
    def review_package_signing_keypair_capability_factory(self) -> ReviewPackageSigningKeypairCapabilityFactory:
        """Resolve the review package signing keypair capability factory on first read."""
        from ..adapters.persistence.profile.review_package_signing import (
            build_review_package_signing_keypair_capability,
        )

        return build_review_package_signing_keypair_capability

    @property
    def modelo_iva_wallet_seed_ports_factory(self) -> ModeloIvaWalletSeedPortsFactory:
        """Resolve the modelo IVA wallet seed ports factory on first read."""
        return build_modelo_iva_wallet_seed_ports

    @property
    def prorrata_register_repository_factory(self) -> ProrrataRegisterRepositoryFactory:
        """Resolve the prorrata register repository factory on first read."""
        return build_prorrata_register_repository

    @property
    def work_lifecycle_ports_factory(self) -> WorkLifecyclePortsFactory:
        """Resolve the work lifecycle ports factory on first read."""
        return build_work_lifecycle_ports

    @cached_property
    def recipient_fingerprint_registry_ports_factory(self) -> RecipientFingerprintRegistryPortsFactory:
        """Resolve the recipient fingerprint registry ports factory on first read."""
        from ..adapters.persistence.profile.review_package_recipient_registry import (
            build_recipient_fingerprint_registry_ports,
        )

        return build_recipient_fingerprint_registry_ports

    @cached_property
    def recipient_encryption_capability_factory(self) -> RecipientEncryptionCapabilityFactory:
        """Resolve the recipient encryption capability factory on first read."""
        from ..adapters.persistence.profile.review_package_recipient_encryption import (
            build_recipient_encryption_capability,
        )

        return build_recipient_encryption_capability


@contextmanager
def profile_free_adapter_composition() -> Generator[None]:
    """Bind only what a command that reads no profile still touches.

    Every envelope names the selected profile from its plaintext summary, and
    output follows its plaintext language hint, so the custody port and the
    language resolver are bound; the persistence and outbound trees a
    profile-bound command needs are not imported at all.
    """
    from ..adapters.persistence.storage.profile_custody import build_profile_custody_port
    from ..application.user_profile.custody_ports import bind_profile_custody_port
    from ..application.user_profile.language_resolver import register_language_resolver
    from ..core.redaction.tax_identity_admission import bind_tax_identity_admission
    from ..domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

    with (
        bind_tax_identity_admission(RegistryTaxIdentityAdmission()),
        bind_profile_custody_port(build_profile_custody_port()),
    ):
        register_language_resolver()
        yield


@contextmanager
def connection_read_adapter_composition() -> Generator[ProfileAdapterComposition]:
    """Bind profile metadata while connection-backed operations own ledger persistence."""
    from ..adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
    from ..core.redaction.tax_identity_admission import bind_tax_identity_admission
    from ..domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

    with (
        bind_tax_identity_admission(RegistryTaxIdentityAdmission()),
        composed_profile_persistence_ports() as profile_custody,
    ):
        yield ProfileAdapterComposition(profile_custody=profile_custody)


@contextmanager
def profile_adapter_composition(
    *, automation_secrets_store: AutomationSecretStore | None = None
) -> Generator[ProfileAdapterComposition]:
    """Bind every adapter port a frontend session resolves, and unbind after.

    The imports are function-local because entering this scope is what pulls the
    adapter layer into the process: a frontend that never serves work should not
    pay for the persistence and outbound trees at import time. The yielded
    capabilities resolve on first read for the same reason.
    """
    from ..adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from ..adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ..adapters.outbound.aeat.auth.session_store import build_session_store
    from ..adapters.persistence.storage.profile_persistence_composition import (
        composed_profile_persistence_ports,
    )
    from ..application.auth.protocols import bind_session_store
    from ..application.auth.providers import bind_auth_provider_selector
    from ..application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from ..application.ledger.column_roles import bind_column_role_mapping_resolver
    from ..application.ledger.confirmation_record_repository import bind_confirmation_record_repository_factory
    from ..application.ledger.extraction_draft_repository import bind_extraction_draft_repository_factory
    from ..application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from ..application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from ..application.ledger.statement_reading import bind_statement_reader_factory
    from ..application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from ..application.ledger.usage_ratio_repository import (
        bind_usage_ratio_censo_guard_loader,
        bind_usage_ratio_profile_persistence,
    )
    from ..application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from ..application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from ..application.modelo.justificante_repository import bind_justificante_repository_factory
    from ..application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from ..application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from ..application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from ..core.redaction.tax_identity_admission import bind_tax_identity_admission
    from ..domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

    with ExitStack() as composition:
        composition.enter_context(bind_tax_identity_admission(RegistryTaxIdentityAdmission()))
        profile_custody = composition.enter_context(
            composed_profile_persistence_ports(automation_secrets_store=automation_secrets_store)
        )
        composition.enter_context(bind_bucket_event_history_repository_factory(bucket_event_history_repository))
        composition.enter_context(bind_confirmation_record_repository_factory(confirmation_record_repository))
        composition.enter_context(bind_column_role_mapping_resolver(resolve_column_roles))
        composition.enter_context(bind_statement_reader_factory(statement_reader))
        composition.enter_context(bind_extraction_draft_repository_factory(extraction_draft_repository))
        composition.enter_context(
            bind_transaction_participation_index_repository_factory(transaction_participation_index_repository)
        )
        composition.enter_context(
            bind_ledger_classification_rule_repository_factory(ledger_classification_rule_repository)
        )
        composition.enter_context(bind_transaction_catalogue_repository_factory(transaction_catalogue_repository))
        composition.enter_context(
            bind_usage_ratio_profile_persistence(loader=load_usage_ratios, saver=save_usage_ratios)
        )
        composition.enter_context(bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard))
        composition.enter_context(
            bind_calculation_revision_catalogue_repository_factory(calculation_revision_catalogue_repository)
        )
        composition.enter_context(bind_modelo_record_catalogue_repository_factory(modelo_record_catalogue_repository))
        composition.enter_context(bind_justificante_repository_factory(justificante_repository))
        composition.enter_context(bind_work_unit_catalogue_repository_factory(work_unit_catalogue_repository))
        composition.enter_context(bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()))
        composition.enter_context(bind_modelo_reconciliation_persistence_factory(modelo_reconciliation_persistence))
        composition.enter_context(bind_auth_provider_selector(select_outbound_auth_provider))
        composition.enter_context(bind_session_store(build_session_store()))
        yield ProfileAdapterComposition(profile_custody=profile_custody)
