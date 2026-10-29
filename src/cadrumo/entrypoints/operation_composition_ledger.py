"""Sole production composition seam for the supervised operation platform.

Every registered operation is built by one named composition group, one per
owning operation module. A group imports its builders inside its own function,
so composing one group costs only that operation family's imports. The eager
production registry composes every group; the manifest-backed registry answers
contracts from the generated manifest and composes a group only when one of
its operations is used.

Core types: :class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..application.operations.contract_manifest import (
    OperationGroupBuild,
)

if TYPE_CHECKING:
    from ..application.ledger.import_operation import LedgerImportOperationPorts
    from ..application.ledger.llm_review_execution import LedgerLlmOperationPorts
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


from .operation_composition_inputs import (
    OperationCompositionInputs,
    built,
    supplied,
)


def compose_workflow_run_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose workflow run read operation."""
    from ..application.workflow.run_read_operation import (
        build_workflow_run_list_definition,
        build_workflow_run_list_registration,
        build_workflow_run_read_definition,
        build_workflow_run_read_registration,
    )

    runs = inputs.workflow_runs()
    read = build_workflow_run_read_definition(runs)
    listing = build_workflow_run_list_definition(runs)
    return built(
        (read, listing),
        (build_workflow_run_read_registration(read, runs), build_workflow_run_list_registration(listing, runs)),
    )


def compose_workflow_resume_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose workflow resume operation."""
    from ..application.workflow.resume_operation import (
        build_workflow_resume_definition,
        build_workflow_resume_registration,
    )

    definition = build_workflow_resume_definition(inputs.workflow_runs(), inputs.calculation_actions())
    return built((definition,), (build_workflow_resume_registration(definition),))


def compose_overview_pipeline_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose overview pipeline operation."""
    from ..application.overview.pipeline_operation import (
        build_overview_pipeline_definition,
        build_overview_pipeline_registration,
    )
    from .overview_pipeline_composition import build_pipeline_read_ports

    definition = build_overview_pipeline_definition(
        supplied(inputs.pipeline_read_ports_factory, build_pipeline_read_ports)
    )
    return built((definition,), (build_overview_pipeline_registration(definition),))


def compose_overview_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose overview read operation."""
    from ..application.overview.read_operation import build_overview_read_definition, build_overview_read_registration
    from ..application.overview.read_request import OverviewReadKind
    from .overview_read_composition import build_overview_read_ports

    ports = supplied(inputs.overview_read_ports_factory, build_overview_read_ports)
    definitions = tuple(build_overview_read_definition(kind, ports) for kind in OverviewReadKind)
    return built(definitions, (build_overview_read_registration(definition) for definition in definitions))


# -- invoices ----------------------------------------------------------------------------------------------------------


def compose_invoices_catalogue_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose invoices catalogue add operation."""
    from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
    from ..application.invoices.catalogue_add_operation import (
        build_invoice_add_definition,
        build_invoice_add_registration,
    )

    definition = build_invoice_add_definition(
        supplied(inputs.invoice_creation_ports_factory, build_catalogue_creation_ports),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built((definition,), (build_invoice_add_registration(definition),))


def compose_invoices_catalogue_intake_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose invoices catalogue intake operation."""
    from ..application.invoices.catalogue_intake_operation import (
        build_invoice_import_definition,
        build_invoice_intake_registration,
        build_invoice_wizard_definition,
    )
    from .invoice_intake_operation_composition import build_invoice_intake_ports

    imported = build_invoice_import_definition(build_invoice_intake_ports)
    wizard = build_invoice_wizard_definition(
        build_invoice_intake_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built(
        (imported, wizard), (build_invoice_intake_registration(imported), build_invoice_intake_registration(wizard))
    )


def compose_invoices_catalogue_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose invoices catalogue read operation."""
    from ..application.invoices.catalogue_read_operation import (
        build_invoice_list_definition,
        build_invoice_list_registration,
        build_invoice_view_definition,
        build_invoice_view_registration,
    )

    inspection = inputs.invoice_inspection()
    listing = build_invoice_list_definition(inspection)
    view = build_invoice_view_definition(inspection)
    return built((listing, view), (build_invoice_list_registration(listing), build_invoice_view_registration(view)))


def compose_invoices_catalogue_remove_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose invoices catalogue remove operation."""
    from ..application.invoices.catalogue_remove_operation import (
        build_invoice_remove_definition,
        build_invoice_remove_registration,
    )

    definition = build_invoice_remove_definition(inputs.invoice_lifecycle())
    return built((definition,), (build_invoice_remove_registration(definition),))


def compose_invoices_catalogue_update_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose invoices catalogue update operation."""
    from ..application.invoices.catalogue_update_operation import (
        build_invoice_update_definition,
        build_invoice_update_registration,
    )

    definition = build_invoice_update_definition(
        inputs.invoice_lifecycle(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_invoice_update_registration(definition),))


# -- ledger ------------------------------------------------------------------------------------------------------------


def compose_ledger_evidence_followup_registration(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence followup registration."""
    from ..application.ledger.evidence_followup_registration import (
        build_ledger_evidence_followup_definitions,
        build_ledger_evidence_followup_registrations,
        build_ledger_evidence_review_summary_definition,
        build_ledger_evidence_review_summary_registration,
    )
    from .evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports

    ports = inputs.evidence_followup_ports or build_ledger_evidence_followup_operation_ports(
        settings=inputs.resolved_settings
    )
    followups = build_ledger_evidence_followup_definitions(ports)
    summary = build_ledger_evidence_review_summary_definition(ports)
    return built(
        (*followups, summary),
        (
            *build_ledger_evidence_followup_registrations(followups),
            build_ledger_evidence_review_summary_registration(summary),
        ),
    )


def compose_ledger_evidence_ingestion_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence ingestion operation."""
    from ..application.ledger.evidence_ingestion_operation import (
        build_ledger_evidence_ingestion_definitions,
        build_ledger_evidence_ingestion_registrations,
    )
    from .ledger_evidence_ingestion_operation_composition import build_ledger_evidence_ingestion_operation_ports

    del inputs
    definitions = build_ledger_evidence_ingestion_definitions(build_ledger_evidence_ingestion_operation_ports)
    return built(definitions, build_ledger_evidence_ingestion_registrations(definitions))


def compose_ledger_ratios_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger ratios operation."""
    from ..application.ledger.ratios_operation import (
        build_ledger_ratios_eligible_definition,
        build_ledger_ratios_eligible_registration,
        build_ledger_ratios_list_definition,
        build_ledger_ratios_list_registration,
        build_ledger_ratios_set_definition,
        build_ledger_ratios_set_registration,
        build_ledger_ratios_unset_definition,
        build_ledger_ratios_unset_registration,
        build_ledger_ratios_validate_definition,
        build_ledger_ratios_validate_registration,
    )

    caller = inputs.execution_caller_reader
    listing = build_ledger_ratios_list_definition()
    ratios_set = build_ledger_ratios_set_definition(execution_caller_reader=caller)
    unset = build_ledger_ratios_unset_definition(execution_caller_reader=caller)
    eligible = build_ledger_ratios_eligible_definition()
    validate = build_ledger_ratios_validate_definition()
    return built(
        (listing, ratios_set, unset, eligible, validate),
        (
            build_ledger_ratios_list_registration(listing),
            build_ledger_ratios_set_registration(ratios_set),
            build_ledger_ratios_unset_registration(unset),
            build_ledger_ratios_eligible_registration(eligible),
            build_ledger_ratios_validate_registration(validate),
        ),
    )


def compose_ledger_llm_diagnostics_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger llm diagnostics operation."""
    from ..application.ledger.llm_diagnostics_operation import (
        build_ledger_llm_diagnostics_definition,
        build_ledger_llm_diagnostics_registration,
    )
    from .ledger_llm_diagnostics_composition import build_ledger_llm_diagnostics_operation_ports

    del inputs
    definition = build_ledger_llm_diagnostics_definition(build_ledger_llm_diagnostics_operation_ports)
    return built((definition,), (build_ledger_llm_diagnostics_registration(definition),))


def compose_ledger_status_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger status operation."""
    from ..application.ledger.status_operation import build_ledger_status_definition, build_ledger_status_registration

    definition = build_ledger_status_definition(inputs.ledger_actions(), inputs.verification_bundle())
    return built((definition,), (build_ledger_status_registration(definition),))


def compose_ledger_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger history operation."""
    from ..application.ledger.history_operation import (
        build_ledger_history_definition,
        build_ledger_history_registration,
        build_ledger_history_typed_definition,
        build_ledger_history_typed_registration,
    )

    reads = inputs.ledger_reads()
    history = build_ledger_history_definition(reads)
    typed = build_ledger_history_typed_definition(reads)
    return built(
        (history, typed), (build_ledger_history_registration(history), build_ledger_history_typed_registration(typed))
    )


def compose_ledger_export_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger export operation."""
    from ..application.ledger.export_operation import build_ledger_export_definition, build_ledger_export_registration
    from .ledger_export_link_operation_composition import build_ledger_export_link_operation_ports

    definition = build_ledger_export_definition(
        build_ledger_export_link_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_export_registration(definition),))


def compose_ledger_link_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger link operation."""
    from ..application.ledger.link_operation import build_ledger_link_definition, build_ledger_link_registration
    from .ledger_export_link_operation_composition import build_ledger_export_link_operation_ports

    definition = build_ledger_link_definition(
        build_ledger_export_link_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_link_registration(definition),))


def compose_ledger_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger import operation."""
    from ..application.exchange_rate_provider import exchange_rate_provider
    from ..application.ledger.import_operation import (
        LedgerImportOperationPorts,
        build_ledger_import_definition,
        build_ledger_import_registration,
    )
    from ..domain.currency.service import CurrencyNormalizationService
    from .ledger_action_composition import compose_ledger_import_ports

    ledger_actions, own_accounts = inputs.ledger_actions(), inputs.own_accounts

    def import_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerImportOperationPorts:
        ledger_ports = ledger_actions(bucket_id=bucket_id, operation=operation)
        return LedgerImportOperationPorts(
            import_ports=compose_ledger_import_ports(),
            transaction_repository=ledger_ports.transaction_repository,
            bucket_event_repository=ledger_ports.bucket_event_repository,
            currency_normalizer=CurrencyNormalizationService(rate_provider=exchange_rate_provider()),
            operation=operation,
            own_accounts=own_accounts(bucket_id=bucket_id),
        )

    definition = build_ledger_import_definition(import_ports, execution_caller_reader=inputs.execution_caller_reader)
    return built((definition,), (build_ledger_import_registration(definition),))


def compose_ledger_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger add operation."""
    from ..application.ledger.add_operation import build_ledger_add_definition, build_ledger_add_registration
    from .adapter_composition_ports import build_prorrata_register_repository

    definition = build_ledger_add_definition(
        inputs.ledger_actions(),
        build_prorrata_register_repository,
        inputs.own_accounts,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built((definition,), (build_ledger_add_registration(definition),))


def compose_ledger_allocate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger allocate operation."""
    from ..application.ledger.allocate_operation import (
        build_ledger_allocate_definition,
        build_ledger_allocate_registration,
    )

    definition = build_ledger_allocate_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_allocate_registration(definition),))


def compose_ledger_classify_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger classify operation."""
    from ..application.ledger.classify_operation import (
        build_ledger_classify_definition,
        build_ledger_classify_registration,
    )

    definition = build_ledger_classify_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_classify_registration(definition),))


def compose_ledger_operator_iva_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger operator iva operation."""
    from ..application.ledger.operator_iva_operation import (
        build_ledger_operator_iva_definition,
        build_ledger_operator_iva_registration,
    )

    definition = build_ledger_operator_iva_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_operator_iva_registration(definition),))


def compose_ledger_llm_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger llm review operation."""
    from ..application.ledger.llm_review_contracts import (
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
        LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    )
    from ..application.ledger.llm_review_execution import LedgerLlmOperationPorts
    from ..application.ledger.llm_review_operation import (
        build_ledger_llm_review_definition,
        build_ledger_llm_review_registration,
    )

    ledger_actions, settings = inputs.ledger_actions(), inputs.resolved_settings

    def llm_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerLlmOperationPorts:
        from .ledger_llm_composition import compose_ledger_llm

        return LedgerLlmOperationPorts(
            ledger=ledger_actions(bucket_id=bucket_id, operation=operation),
            llm=compose_ledger_llm(bucket_id=bucket_id, settings=settings).ports,
            settings=settings,
        )

    caller = inputs.execution_caller_reader
    classify = build_ledger_llm_review_definition(
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, llm_ports, execution_caller_reader=caller
    )
    split = build_ledger_llm_review_definition(
        LEDGER_SPLIT_REVIEW_DEFINITION_ID, llm_ports, execution_caller_reader=caller
    )
    return built(
        (classify, split), (build_ledger_llm_review_registration(classify), build_ledger_llm_review_registration(split))
    )


def compose_ledger_bulk_classify_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger bulk classify operation."""
    from ..application.ledger.bulk_classify_operation import (
        build_ledger_bulk_classify_definition,
        build_ledger_bulk_classify_registration,
    )

    definition = build_ledger_bulk_classify_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_bulk_classify_registration(definition),))


def compose_ledger_rule_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger rule operation."""
    from ..application.ledger.rule_operation import (
        build_ledger_rule_add_definition,
        build_ledger_rule_add_registration,
        build_ledger_rule_apply_definition,
        build_ledger_rule_apply_registration,
        build_ledger_rule_list_definition,
        build_ledger_rule_list_registration,
    )

    rules, caller = inputs.ledger_rules(), inputs.execution_caller_reader
    add = build_ledger_rule_add_definition(rules, execution_caller_reader=caller)
    listing = build_ledger_rule_list_definition(rules)
    apply = build_ledger_rule_apply_definition(inputs.ledger_actions(), rules, execution_caller_reader=caller)
    return built(
        (add, listing, apply),
        (
            build_ledger_rule_add_registration(add),
            build_ledger_rule_list_registration(listing),
            build_ledger_rule_apply_registration(apply),
        ),
    )


def compose_ledger_evidence_add_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence add operation."""
    from ..application.ledger.evidence_add_operation import (
        build_ledger_evidence_add_definition,
        build_ledger_evidence_add_registration,
    )
    from .adapter_composition_work_ports import build_ledger_evidence_ports

    definition = build_ledger_evidence_add_definition(
        build_ledger_evidence_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_evidence_add_registration(definition),))


def compose_ledger_evidence_page_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence page operation."""
    from ..application.ledger.evidence_page_operation import (
        build_ledger_evidence_page_definition,
        build_ledger_evidence_page_registration,
    )
    from .evidence_page_operation_composition import build_ledger_evidence_page_operation_ports

    del inputs
    definition = build_ledger_evidence_page_definition(build_ledger_evidence_page_operation_ports())
    return built((definition,), (build_ledger_evidence_page_registration(definition),))


def compose_ledger_evidence_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence read operation."""
    from ..application.ledger.evidence_read_operation import (
        build_ledger_evidence_list_definition,
        build_ledger_evidence_list_registration,
        build_ledger_evidence_query_definition,
        build_ledger_evidence_query_registration,
        build_ledger_evidence_view_definition,
        build_ledger_evidence_view_registration,
    )
    from .adapter_composition_work_ports import build_ledger_evidence_ports

    del inputs
    listing = build_ledger_evidence_list_definition(build_ledger_evidence_ports)
    view = build_ledger_evidence_view_definition(build_ledger_evidence_ports)
    query = build_ledger_evidence_query_definition(build_ledger_evidence_ports)
    return built(
        (listing, view, query),
        (
            build_ledger_evidence_list_registration(listing),
            build_ledger_evidence_view_registration(view),
            build_ledger_evidence_query_registration(query),
        ),
    )


def compose_ledger_evidence_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger evidence mutation operation."""
    from ..application.ledger.evidence_mutation_operation import (
        build_ledger_evidence_remove_definition,
        build_ledger_evidence_remove_registration,
        build_ledger_evidence_update_definition,
        build_ledger_evidence_update_registration,
    )
    from .adapter_composition_work_ports import build_ledger_evidence_ports

    caller = inputs.execution_caller_reader
    update = build_ledger_evidence_update_definition(build_ledger_evidence_ports, execution_caller_reader=caller)
    remove = build_ledger_evidence_remove_definition(build_ledger_evidence_ports, execution_caller_reader=caller)
    return built(
        (update, remove),
        (build_ledger_evidence_update_registration(update), build_ledger_evidence_remove_registration(remove)),
    )


def compose_ledger_invoice_evidence_readiness_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger invoice evidence readiness operation."""
    from ..application.ledger.invoice_evidence_readiness_operation import (
        build_ledger_evidence_reader_readiness_definition,
        build_ledger_evidence_reader_readiness_registration,
    )
    from ..application.local_reader import read_local_reader_status

    del inputs
    definition = build_ledger_evidence_reader_readiness_definition(read_local_reader_status)
    return built((definition,), (build_ledger_evidence_reader_readiness_registration(definition),))


def compose_ledger_invoice_evidence_extract_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger invoice evidence extract operation."""
    from ..application.ledger.invoice_evidence_extract_operation import (
        build_ledger_evidence_extract_definition,
        build_ledger_evidence_extract_registration,
    )
    from .invoice_evidence_operation_composition import build_invoice_evidence_operation_ports

    del inputs
    definition = build_ledger_evidence_extract_definition(build_invoice_evidence_operation_ports)
    return built((definition,), (build_ledger_evidence_extract_registration(definition),))


def compose_ledger_invoice_evidence_confirm_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger invoice evidence confirm operation."""
    from ..application.ledger.invoice_evidence_confirm_operation import (
        build_ledger_evidence_confirm_definition,
        build_ledger_evidence_confirm_registration,
    )
    from .invoice_evidence_operation_composition import build_invoice_evidence_operation_ports

    del inputs
    definition = build_ledger_evidence_confirm_definition(build_invoice_evidence_operation_ports)
    return built((definition,), (build_ledger_evidence_confirm_registration(definition),))


def compose_ledger_split_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger split operation."""
    from ..application.ledger.split_operation import build_ledger_split_definition, build_ledger_split_registration

    definition = build_ledger_split_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_split_registration(definition),))


def compose_ledger_merge_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger merge operation."""
    from ..application.ledger.merge_operation import build_ledger_merge_definition, build_ledger_merge_registration

    definition = build_ledger_merge_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_merge_registration(definition),))


def compose_ledger_update_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger update operation."""
    from ..application.ledger.update_operation import build_ledger_update_definition, build_ledger_update_registration

    definition = build_ledger_update_definition(
        inputs.ledger_actions(), inputs.own_accounts, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_update_registration(definition),))


def compose_ledger_attachment_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger attachment mutation operation."""
    from ..application.ledger.attachment_mutation_operation import (
        build_ledger_attach_definition,
        build_ledger_attach_registration,
        build_ledger_detach_definition,
        build_ledger_detach_registration,
    )

    actions, caller = inputs.ledger_actions(), inputs.execution_caller_reader
    attach = build_ledger_attach_definition(actions, execution_caller_reader=caller)
    detach = build_ledger_detach_definition(actions, execution_caller_reader=caller)
    return built((attach, detach), (build_ledger_attach_registration(attach), build_ledger_detach_registration(detach)))


def compose_ledger_lifecycle_mutation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger lifecycle mutation operation."""
    from ..application.ledger.lifecycle_mutation_operation import (
        build_ledger_archive_definition,
        build_ledger_archive_registration,
        build_ledger_exclude_definition,
        build_ledger_exclude_registration,
        build_ledger_restore_definition,
        build_ledger_restore_registration,
        build_ledger_stash_definition,
        build_ledger_stash_registration,
    )

    actions, caller = inputs.ledger_actions(), inputs.execution_caller_reader
    archive = build_ledger_archive_definition(actions, execution_caller_reader=caller)
    stash = build_ledger_stash_definition(actions, execution_caller_reader=caller)
    restore = build_ledger_restore_definition(actions, execution_caller_reader=caller)
    exclude = build_ledger_exclude_definition(actions, execution_caller_reader=caller)
    return built(
        (archive, stash, restore, exclude),
        (
            build_ledger_archive_registration(archive),
            build_ledger_stash_registration(stash),
            build_ledger_restore_registration(restore),
            build_ledger_exclude_registration(exclude),
        ),
    )


def compose_ledger_remove_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger remove operation."""
    from ..application.ledger.remove_operation import build_ledger_remove_definition, build_ledger_remove_registration

    definition = build_ledger_remove_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_remove_registration(definition),))


def compose_ledger_reset_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger reset operation."""
    from ..application.ledger.reset_operation import build_ledger_reset_definition, build_ledger_reset_registration

    definition = build_ledger_reset_definition(
        inputs.ledger_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_reset_registration(definition),))


def compose_ledger_counterparty_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger counterparty operation."""
    from ..application.ledger.counterparty_operation import (
        build_ledger_counterparty_definition,
        build_ledger_counterparty_registration,
    )

    repository = inputs.counterparty_repository_factory
    if repository is None:
        from ..adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )

        repository = build_counterparty_establishment_repository
    definition = build_ledger_counterparty_definition(
        repository, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_ledger_counterparty_registration(definition),))


def compose_ledger_own_account_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger own account operation."""
    from ..application.ledger.own_account_operation import (
        build_ledger_own_account_definition,
        build_ledger_own_account_registration,
    )

    definition = build_ledger_own_account_definition(inputs.own_accounts)
    return built((definition,), (build_ledger_own_account_registration(definition),))


def compose_ledger_check_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger check operation."""
    from ..application.ledger.check_operation import build_ledger_check_definition, build_ledger_check_registration

    definition = build_ledger_check_definition(inputs.ledger_actions())
    return built((definition,), (build_ledger_check_registration(definition),))


def compose_ledger_preflight_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger preflight operation."""
    from ..application.ledger.preflight_operation import (
        build_ledger_preflight_definition,
        build_ledger_preflight_registration,
    )

    definition = build_ledger_preflight_definition(inputs.ledger_actions())
    return built((definition,), (build_ledger_preflight_registration(definition),))


def compose_ledger_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger review operation."""
    from ..application.ledger.review_operation import build_ledger_review_definition, build_ledger_review_registration

    definition = build_ledger_review_definition(inputs.ledger_actions())
    return built((definition,), (build_ledger_review_registration(definition),))


def compose_ledger_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger list operation."""
    from ..application.ledger.list_operation import build_ledger_list_definition, build_ledger_list_registration

    definition = build_ledger_list_definition(inputs.ledger_reads())
    return built((definition,), (build_ledger_list_registration(definition),))


def compose_ledger_view_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger view operation."""
    from ..application.ledger.view_operation import build_ledger_view_definition, build_ledger_view_registration

    definition = build_ledger_view_definition(inputs.ledger_actions())
    return built((definition,), (build_ledger_view_registration(definition),))


def compose_ledger_track_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger track operation."""
    from ..application.ledger.track_operation import build_ledger_track_definition, build_ledger_track_registration

    definition = build_ledger_track_definition(inputs.ledger_actions(), inputs.ledger_participation())
    return built((definition,), (build_ledger_track_registration(definition),))


def compose_ledger_participation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger participation operation."""
    from ..application.ledger.participation_operation import (
        build_ledger_participation_definition,
        build_ledger_participation_registration,
    )

    definition = build_ledger_participation_definition(inputs.ledger_actions(), inputs.ledger_participation())
    return built((definition,), (build_ledger_participation_registration(definition),))


def compose_ledger_participation_rebuild_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose ledger participation rebuild operation."""
    from ..application.ledger.participation_rebuild_operation import (
        build_ledger_participation_rebuild_definition,
        build_ledger_participation_rebuild_registration,
    )
    from .adapter_composition_ports import build_participation_index_rebuild_ports

    definition = build_ledger_participation_rebuild_definition(
        supplied(inputs.participation_rebuild_ports_factory, build_participation_index_rebuild_ports)
    )
    return built((definition,), (build_ledger_participation_rebuild_registration(definition),))
