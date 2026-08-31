"""The one adapter composition every Cadrumo frontend enters.

A frontend process must bind the persistence and outbound adapters the
application layer resolves through explicitly composed ports before it serves
any work. That inventory is a property of the product, not of the frontend, so
it is declared once here and entered by the CLI root, the TUI devtools fixture
and the ``cadrumo-mcp`` server alike.

Keeping a copy per frontend is what let the MCP server ship with none at all:
nothing named the inventory, so nothing could observe that one entrypoint was
missing it. A frontend that forgets this scope fails on every custody-touching
verb, which is exactly the symptom that made the gap visible.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager

__all__ = ["profile_adapter_composition"]


@contextmanager
def profile_adapter_composition() -> Generator[None]:
    """Bind every adapter port a frontend session resolves, and unbind after.

    The imports are function-local because entering this scope is what pulls the
    adapter layer into the process: a frontend that never serves work should not
    pay for the persistence and outbound trees at import time.
    """
    from ..adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from ..adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ..adapters.outbound.aeat.auth.session_store import build_session_store
    from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from ..adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from ..adapters.persistence.profile.extracted_document_cache import ExtractedDocumentCacheRepository
    from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from ..adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.usage_ratios import (
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
        save_usage_ratios,
    )
    from ..adapters.persistence.storage._profile_custody import build_profile_custody_port
    from ..adapters.persistence.storage._profile_login_session import build_profile_login_session_port
    from ..adapters.persistence.workflow import build_workflow_persistence_port
    from ..application.auth.protocols import bind_session_store
    from ..application.auth.providers import bind_auth_provider_selector
    from ..application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from ..application.ledger.confirmation_record import bind_confirmation_record_repository_factory
    from ..application.ledger.extracted_document_cache import bind_extracted_document_cache_repository_factory
    from ..application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from ..application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from ..application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
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
    from ..application.user_profile.custody_ports import bind_profile_custody_port
    from ..application.user_profile.language_resolver import register_language_resolver
    from ..application.user_profile.login_session_port import bind_profile_login_session_port
    from ..application.workflow.persistence import bind_workflow_persistence_port

    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        composition.enter_context(bind_workflow_persistence_port(build_workflow_persistence_port()))
        composition.enter_context(bind_bucket_event_history_repository_factory(build_bucket_event_history_repository))
        composition.enter_context(bind_confirmation_record_repository_factory(ConfirmationRecordRepository))
        composition.enter_context(bind_extraction_draft_repository_factory(ExtractionDraftRepository))
        composition.enter_context(bind_extracted_document_cache_repository_factory(ExtractedDocumentCacheRepository))
        composition.enter_context(
            bind_transaction_participation_index_repository_factory(TransactionParticipationIndexRepository)
        )
        composition.enter_context(
            bind_ledger_classification_rule_repository_factory(LedgerClassificationRuleRepository)
        )
        composition.enter_context(bind_transaction_catalogue_repository_factory(TransactionCatalogueRepository))
        composition.enter_context(
            bind_usage_ratio_profile_persistence(loader=load_usage_ratios, saver=save_usage_ratios)
        )
        composition.enter_context(bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard))
        composition.enter_context(
            bind_calculation_revision_catalogue_repository_factory(CalculationRevisionCatalogueRepository)
        )
        composition.enter_context(bind_modelo_record_catalogue_repository_factory(ModeloRecordCatalogueRepository))
        composition.enter_context(bind_justificante_repository_factory(JustificanteRepository))
        composition.enter_context(bind_work_unit_catalogue_repository_factory(WorkUnitCatalogueRepository))
        composition.enter_context(bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()))
        composition.enter_context(
            bind_modelo_reconciliation_persistence_factory(build_modelo_reconciliation_persistence)
        )
        composition.enter_context(bind_auth_provider_selector(select_outbound_auth_provider))
        composition.enter_context(bind_session_store(build_session_store()))
        register_language_resolver()
        yield
