"""Independent MCP composition root for concrete product adapters.

The MCP distribution is an outer process root in its own right.  It binds the
same inward application ports as the CLI and TUI, but it must not import either
entrypoint or any repository-only test composition.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager


@contextmanager
def profile_adapter_composition() -> Generator[None]:
    """Bind every concrete adapter port used by one MCP server process."""
    from cadrumo.adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from cadrumo.adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from cadrumo.adapters.outbound.aeat.auth.session_store import build_session_store
    from cadrumo.adapters.outbound.llm.column_role_mapping import resolve_column_roles as resolve_outbound_column_roles
    from cadrumo.adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from cadrumo.adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from cadrumo.adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
    from cadrumo.adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from cadrumo.adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from cadrumo.adapters.persistence.profile.usage_ratios import (
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
        save_usage_ratios,
    )
    from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
    from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
    from cadrumo.adapters.persistence.workflow import build_workflow_persistence_port
    from cadrumo.application.auth.protocols import bind_session_store
    from cadrumo.application.auth.providers import bind_auth_provider_selector
    from cadrumo.application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from cadrumo.application.ledger.column_roles import bind_column_role_mapping_resolver
    from cadrumo.application.ledger.confirmation_record import bind_confirmation_record_repository_factory
    from cadrumo.application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from cadrumo.application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from cadrumo.application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from cadrumo.application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from cadrumo.application.ledger.usage_ratio_repository import (
        bind_usage_ratio_censo_guard_loader,
        bind_usage_ratio_profile_persistence,
    )
    from cadrumo.application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from cadrumo.application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from cadrumo.application.modelo.justificante_repository import bind_justificante_repository_factory
    from cadrumo.application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from cadrumo.application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from cadrumo.application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
    from cadrumo.application.user_profile.language_resolver import register_language_resolver
    from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
    from cadrumo.application.workflow.persistence import bind_workflow_persistence_port

    with ExitStack() as composition:
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        composition.enter_context(bind_workflow_persistence_port(build_workflow_persistence_port()))
        composition.enter_context(bind_bucket_event_history_repository_factory(build_bucket_event_history_repository))
        composition.enter_context(bind_confirmation_record_repository_factory(ConfirmationRecordRepository))
        composition.enter_context(bind_column_role_mapping_resolver(resolve_outbound_column_roles))
        composition.enter_context(bind_extraction_draft_repository_factory(ExtractionDraftRepository))
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


__all__ = ["profile_adapter_composition"]
