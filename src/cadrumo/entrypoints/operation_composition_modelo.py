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
    pass


from .operation_composition_inputs import (
    OperationCompositionInputs,
    build_modelo_aggregate_operation_ports,
    build_modelo_invoice_withholding_capture_ports,
    build_modelo_workbench_read_ports,
    built,
    supplied,
)


def compose_modelo_operation_definitions(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo operation definitions."""
    from ..adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
    from ..adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_capability
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access
    from ..application.modelo.operation_definitions import (
        build_modelo_lifecycle_operation_definitions,
        build_modelo_lifecycle_operation_registrations,
    )
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access
    from .adapter_composition_ports import build_modelo_edit_receipt_repository
    from .adapter_composition_work_ports import build_amendment_action_ports, build_filing_action_ports

    definitions = build_modelo_lifecycle_operation_definitions(
        profile_resolver=inputs.modelo_profile(),
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=inputs.scope,
        export_ports_factory=inputs.modelo_exports(),
        # The calculation report's provenance key is derived from the profile's
        # existing review-package signing key, so the export enrolment is bound
        # to the adapter that already owns that key's custody.
        signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
        # The summary PDF writer is the same adapter the command line hands the
        # report service, so both surfaces draw one revision's summary with one
        # writer. It imports ReportLab only when it draws.
        calculation_summary_pdf_writer=write_calculation_summary_pdf,
        calculation_action_ports_factory=inputs.calculation_actions(),
        attachment_store_factory=inputs.attachments(),
        amendment_action_ports_factory=supplied(inputs.amendment_action_ports_factory, build_amendment_action_ports),
        filing_action_ports_factory=supplied(inputs.filing_action_ports_factory, build_filing_action_ports),
        work_lifecycle_ports_factory=inputs.work_lifecycle(),
        receipt_repository_factory=supplied(
            inputs.modelo_edit_receipt_repository_factory, build_modelo_edit_receipt_repository
        ),
        verification_repository_bundle_factory=inputs.verification_bundle(),
        edit_prerequisite_observer=inputs.edit_prerequisites.retain,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built(
        definitions,
        build_modelo_lifecycle_operation_registrations(
            definitions,
            metadata_access_resolver=compose_modelo_metadata_access(inputs.work_lifecycle()),
            revision_access_resolver=compose_modelo_revision_access(inputs.verification_bundle()),
        ),
    )


def compose_modelo_workbench_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo workbench operations."""
    from ..application.modelo.workbench_operations import (
        build_modelo_workbench_operation_definitions,
        build_modelo_workbench_operation_registrations,
        compose_modelo_workbench_access,
    )

    definitions = build_modelo_workbench_operation_definitions(
        ports_factory=supplied(inputs.modelo_workbench_read_ports_factory, build_modelo_workbench_read_ports),
        contracts=inputs.registry_contracts,
        prerequisites=inputs.edit_prerequisites,
    )
    return built(
        definitions,
        build_modelo_workbench_operation_registrations(
            definitions, access_resolver=compose_modelo_workbench_access(inputs.work_lifecycle())
        ),
    )


def compose_modelo_query_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo query read operation."""
    from ..application.modelo.query_read_operation import (
        build_modelo_bindings_list_definition,
        build_modelo_bindings_list_registration,
        build_modelo_bindings_resolve_definition,
        build_modelo_bindings_resolve_registration,
        build_modelo_readiness_definition,
        build_modelo_readiness_registration,
        build_modelo_requires_definition,
        build_modelo_requires_registration,
    )
    from .modelo_query_read_operation_composition import build_modelo_query_read_ports

    bindings_list = build_modelo_bindings_list_definition()
    bindings_resolve = build_modelo_bindings_resolve_definition()
    requires = build_modelo_requires_definition()
    readiness = build_modelo_readiness_definition(
        supplied(inputs.modelo_query_read_ports_factory, build_modelo_query_read_ports)
    )
    return built(
        (bindings_list, bindings_resolve, requires, readiness),
        (
            build_modelo_bindings_list_registration(bindings_list),
            build_modelo_bindings_resolve_registration(bindings_resolve),
            build_modelo_requires_registration(requires),
            build_modelo_readiness_registration(readiness),
        ),
    )


def compose_modelo_typed_query_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo typed query operation."""
    from ..application.modelo.typed_query_operation import (
        build_modelo_bindings_resolve_typed_definition,
        build_modelo_bindings_resolve_typed_registration,
        build_modelo_readiness_summary_definition,
        build_modelo_readiness_summary_registration,
    )
    from .modelo_query_read_operation_composition import build_modelo_query_read_ports

    resolve_typed = build_modelo_bindings_resolve_typed_definition()
    readiness_summary = build_modelo_readiness_summary_definition(
        supplied(inputs.modelo_query_read_ports_factory, build_modelo_query_read_ports)
    )
    return built(
        (resolve_typed, readiness_summary),
        (
            build_modelo_bindings_resolve_typed_registration(resolve_typed),
            build_modelo_readiness_summary_registration(readiness_summary),
        ),
    )


def compose_modelo_calculation_report_verification_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo calculation report verification operation."""
    from ..application.modelo.calculation_report_verification_operation import (
        build_modelo_calculation_report_verify_definition,
        build_modelo_calculation_report_verify_registration,
    )
    from .calculation_report_verification_operation_composition import (
        build_modelo_calculation_report_verification_ports,
    )

    del inputs
    definition = build_modelo_calculation_report_verify_definition(build_modelo_calculation_report_verification_ports)
    return built((definition,), (build_modelo_calculation_report_verify_registration(definition),))


def compose_modelo_review_package_recipient_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo review package recipient operations."""
    from ..application.modelo.review_package_recipient_operations import (
        build_review_package_recipient_add_definition,
        build_review_package_recipient_add_registration,
        build_review_package_recipient_list_definition,
        build_review_package_recipient_list_registration,
        build_review_package_recipient_remove_definition,
        build_review_package_recipient_remove_registration,
    )

    registry, events = inputs.recipient_registry(), inputs.recipient_events()
    add = build_review_package_recipient_add_definition(registry, events)
    listing = build_review_package_recipient_list_definition(registry)
    remove = build_review_package_recipient_remove_definition(registry, events)
    return built(
        (add, listing, remove),
        (
            build_review_package_recipient_add_registration(add),
            build_review_package_recipient_list_registration(listing),
            build_review_package_recipient_remove_registration(remove),
        ),
    )


def compose_modelo_quickfile_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo quickfile operation."""
    from ..application.modelo.quickfile_operation import build_quickfile_definition, build_quickfile_registration
    from .quickfile_operation_composition import build_quickfile_operation_ports

    definition = build_quickfile_definition(
        build_quickfile_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_quickfile_registration(definition),))


def compose_modelo_m036_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo m036 operation."""
    from ..application.modelo.m036_operation import (
        build_m036_operation_definitions,
        build_m036_operation_registrations,
    )
    from .m036_operation_composition import build_m036_operation_ports

    del inputs
    definitions = build_m036_operation_definitions(build_m036_operation_ports)
    return built(definitions, build_m036_operation_registrations(definitions))


def compose_modelo_audit_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo audit operation."""
    from ..application.modelo.audit_operation import (
        build_modelo_audit_operation_definitions,
        build_modelo_audit_operation_registrations,
    )
    from .modelo_audit_operation_composition import build_modelo_audit_operation_ports

    del inputs
    definitions = build_modelo_audit_operation_definitions(build_modelo_audit_operation_ports)
    return built(definitions, build_modelo_audit_operation_registrations(definitions))


def compose_modelo_maritime_preview_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo maritime preview operation."""
    from ..application.modelo.maritime_preview_operation import (
        build_modelo_maritime_preview_definition,
        build_modelo_maritime_preview_registration,
    )
    from .modelo_maritime_operation_composition import build_modelo_maritime_preview_ports

    del inputs
    definition = build_modelo_maritime_preview_definition(build_modelo_maritime_preview_ports)
    return built((definition,), (build_modelo_maritime_preview_registration(definition),))


def compose_modelo_spreadsheet_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo spreadsheet operation."""
    from ..application.modelo.modelo_spreadsheet_operation import build_modelo_spreadsheet_definitions
    from ..application.modelo.modelo_spreadsheet_registration import build_modelo_spreadsheet_registration
    from .modelo_spreadsheet_operation_composition import build_modelo_spreadsheet_operation_ports

    del inputs
    definitions = build_modelo_spreadsheet_definitions(build_modelo_spreadsheet_operation_ports)
    return built(definitions, (build_modelo_spreadsheet_registration(definition) for definition in definitions))


def compose_modelo_review_package_exchange_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo review package exchange operation."""
    from ..application.modelo.review_package_exchange_operation import (
        build_review_package_exchange_operation_definitions,
        build_review_package_exchange_operation_registrations,
    )
    from .review_package_exchange_operation_composition import build_review_package_exchange_operation_ports

    definitions = build_review_package_exchange_operation_definitions(
        build_review_package_exchange_operation_ports, execution_caller_reader=inputs.execution_caller_reader
    )
    return built(definitions, build_review_package_exchange_operation_registrations(definitions))


def compose_modelo_m145_communication_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo m145 communication operation."""
    from ..adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
    from ..adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
    from ..application.modelo.m145_communication_operation import (
        build_m145_communication_operation_definitions,
        build_m145_communication_operation_registrations,
    )

    definitions = build_m145_communication_operation_definitions(
        records_ports_factory=build_m145_communication_records_ports,
        renderer_factory=RegistryFixedWidthRecordRenderer,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built(definitions, build_m145_communication_operation_registrations(definitions))


def compose_modelo_reconciliation_export_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo reconciliation export operation."""
    from ..application.modelo.reconciliation_export_operation import (
        build_reconciliation_export_xlsx_definition,
        build_reconciliation_export_xlsx_registration,
    )
    from .reconciliation_export_operation_composition import build_reconciliation_export_xlsx_ports

    del inputs
    definition = build_reconciliation_export_xlsx_definition(build_reconciliation_export_xlsx_ports)
    return built((definition,), (build_reconciliation_export_xlsx_registration(definition),))


def compose_modelo_metadata_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo metadata read operation."""
    from ..application.modelo.metadata_read_operation import (
        build_modelo_metadata_definition,
        build_modelo_metadata_registration,
    )

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_metadata_definition(lifecycle)
    return built((definition,), (build_modelo_metadata_registration(definition, lifecycle),))


def compose_modelo_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo history operation."""
    from ..application.modelo.history_operation import (
        build_modelo_work_history_definition,
        build_modelo_work_history_registration,
    )

    history = inputs.modelo_history()
    definition = build_modelo_work_history_definition(history)
    return built((definition,), (build_modelo_work_history_registration(definition, history),))


def compose_modelo_lifecycle_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo lifecycle history operation."""
    from ..application.modelo.lifecycle_history_operation import (
        build_modelo_history_definition,
        build_modelo_history_registration,
    )

    definition = build_modelo_history_definition(inputs.modelo_history())
    return built((definition,), (build_modelo_history_registration(definition),))


def compose_modelo_history_timeline_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo history timeline operation."""
    from ..application.modelo.history_timeline_operation import (
        build_modelo_history_timeline_definition,
        build_modelo_history_timeline_registration,
    )

    definition = build_modelo_history_timeline_definition(inputs.modelo_history())
    return built((definition,), (build_modelo_history_timeline_registration(definition),))


def compose_modelo_projection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo projection operation."""
    from ..adapters.persistence.profile.guarded_calculation_revision_migration import (
        GuardedCalculationRevisionMigration,
    )
    from ..application.modelo.projection_operation import (
        build_modelo_compare_definition,
        build_modelo_compare_registration,
        build_modelo_project_definition,
        build_modelo_project_registration,
    )

    migration = GuardedCalculationRevisionMigration()
    project = build_modelo_project_definition(factory=inputs.calculation_actions(), migration=migration)
    compare = build_modelo_compare_definition(factory=inputs.calculation_actions(), migration=migration)
    return built(
        (project, compare), (build_modelo_project_registration(project), build_modelo_compare_registration(compare))
    )


def compose_modelo_reconciliation_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo reconciliation import operation."""
    from ..application.modelo.reconciliation_import_operation import (
        build_modelo_reconciliation_import_definition,
        build_modelo_reconciliation_import_registration,
    )

    definition = build_modelo_reconciliation_import_definition(execution_caller_reader=inputs.execution_caller_reader)
    return built((definition,), (build_modelo_reconciliation_import_registration(definition),))


def compose_modelo_reconciliation_pull_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo reconciliation pull operation."""
    from ..application.modelo.reconciliation_pull_operation import (
        build_modelo_reconciliation_pull_definition,
        build_modelo_reconciliation_pull_registration,
    )
    from .justificante_composition import build_justificante_capture_service, load_reconciliation_filed_observation

    definition = build_modelo_reconciliation_pull_definition(
        build_justificante_capture_service,
        load_reconciliation_filed_observation,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built((definition,), (build_modelo_reconciliation_pull_registration(definition),))


def compose_modelo_reconciliation_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo reconciliation list operation."""
    from ..application.modelo.reconciliation_list_operation import (
        build_modelo_reconciliation_list_definition,
        build_modelo_reconciliation_list_registration,
    )

    del inputs
    definition = build_modelo_reconciliation_list_definition()
    return built((definition,), (build_modelo_reconciliation_list_registration(definition),))


def compose_modelo_declarations_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo declarations list operation."""
    from ..application.modelo.declarations_list_operation import (
        build_modelo_declarations_list_definition,
        build_modelo_declarations_list_registration,
    )
    from .workbench_generation_composition import compose_secure_declaration_list_reader

    del inputs
    definition = build_modelo_declarations_list_definition(
        lambda profile_id, operation: compose_secure_declaration_list_reader(profile_id=profile_id, operation=operation)
    )
    return built((definition,), (build_modelo_declarations_list_registration(definition),))


def compose_modelo_work_inventory_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo work inventory operation."""
    from ..application.modelo.work_inventory_operation import (
        build_modelo_work_list_definition,
        build_modelo_work_list_registration,
    )

    definition = build_modelo_work_list_definition(inputs.work_lifecycle())
    return built((definition,), (build_modelo_work_list_registration(definition),))


def compose_modelo_work_create_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo work create operation."""
    from ..application.modelo.work_create_operation import (
        build_modelo_work_create_definition,
        build_modelo_work_create_registration,
    )

    definition = build_modelo_work_create_definition(
        inputs.work_lifecycle(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_modelo_work_create_registration(definition),))


def compose_modelo_work_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo work review operation."""
    from ..application.modelo.work_review_operation import (
        build_modelo_work_review_definition,
        build_modelo_work_review_registration,
    )

    history = inputs.modelo_history()
    definition = build_modelo_work_review_definition(history)
    return built((definition,), (build_modelo_work_review_registration(definition, history),))


def compose_modelo_dependency_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo dependency operation."""
    from ..application.modelo.dependency_operation import (
        build_modelo_dependency_definition,
        build_modelo_dependency_registration,
    )
    from .modelo_dependency_composition import build_dependency_read_ports

    definition = build_modelo_dependency_definition(
        supplied(inputs.dependency_read_ports_factory, build_dependency_read_ports)
    )
    return built((definition,), (build_modelo_dependency_registration(definition),))


def compose_modelo_aggregate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo aggregate operation."""
    from ..application.modelo.aggregate_operation import (
        build_modelo_aggregate_operation_definition,
        build_modelo_aggregate_operation_registration,
    )

    definition = build_modelo_aggregate_operation_definition(
        supplied(inputs.modelo_aggregate_operation_ports_factory, build_modelo_aggregate_operation_ports)
    )
    return built((definition,), (build_modelo_aggregate_operation_registration(definition),))


def compose_modelo_invoice_withholding_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo invoice withholding capture operation."""
    from ..application.modelo.invoice_withholding_capture_operation import (
        build_modelo_invoice_withholding_capture_definition,
        build_modelo_invoice_withholding_capture_registration,
    )

    definition = build_modelo_invoice_withholding_capture_definition(
        supplied(
            inputs.modelo_invoice_withholding_capture_ports_factory, build_modelo_invoice_withholding_capture_ports
        )
    )
    return built((definition,), (build_modelo_invoice_withholding_capture_registration(definition),))


def compose_modelo_wizard_context_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo wizard context operation."""
    from ..application.modelo.wizard_context_operation import (
        build_modelo_work_wizard_context_definition,
        build_modelo_work_wizard_context_registration,
    )

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_work_wizard_context_definition(lifecycle)
    return built((definition,), (build_modelo_work_wizard_context_registration(definition, lifecycle),))


def compose_modelo_wizard_attempt_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo wizard attempt operation."""
    from ..application.modelo.wizard_attempt_operation import (
        build_modelo_work_wizard_attempt_definition,
        build_modelo_work_wizard_attempt_registration,
    )

    definition = build_modelo_work_wizard_attempt_definition(
        calculation_action_ports_factory=inputs.calculation_actions(),
        attachment_store_factory=inputs.attachments(),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built((definition,), (build_modelo_work_wizard_attempt_registration(definition, inputs.work_lifecycle()),))


def compose_modelo_revision_selection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo revision selection operation."""
    from ..application.modelo.revision_selection_operation import (
        build_modelo_work_revision_definition,
        build_modelo_work_revision_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revision_definition(bundle)
    return built((definition,), (build_modelo_work_revision_registration(definition, bundle),))


def compose_modelo_revision_inventory_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo revision inventory operation."""
    from ..application.modelo.revision_inventory_operation import (
        build_modelo_work_revisions_definition,
        build_modelo_work_revisions_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revisions_definition(bundle)
    return built((definition,), (build_modelo_work_revisions_registration(definition, bundle),))


def compose_modelo_revision_snapshot_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo revision snapshot operation."""
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access
    from ..application.modelo.revision_snapshot_operation import (
        build_modelo_work_revision_snapshot_definition,
        build_modelo_work_revision_snapshot_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_revision_snapshot_definition(bundle)
    return built(
        (definition,),
        (
            build_modelo_work_revision_snapshot_registration(
                definition, access_resolver=compose_modelo_revision_access(bundle)
            ),
        ),
    )


def compose_modelo_filing_selection_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo filing selection operation."""
    from ..application.modelo.filing_selection_operation import (
        build_modelo_work_filing_record_definition,
        build_modelo_work_filing_record_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_filing_record_definition(bundle)
    return built((definition,), (build_modelo_work_filing_record_registration(definition, bundle),))


def compose_modelo_filing_record_list_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo filing record list operation."""
    from ..application.modelo.filing_record_list_operation import (
        build_modelo_filing_record_list_definition,
        build_modelo_filing_record_list_registration,
    )

    definition = build_modelo_filing_record_list_definition(inputs.verification_bundle())
    return built((definition,), (build_modelo_filing_record_list_registration(definition),))


def compose_modelo_filing_record_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo filing record import operation."""
    from ..application.modelo.filing_record_import_operation import (
        build_modelo_filing_record_import_definition,
        build_modelo_filing_record_import_registration,
    )

    calculations = inputs.calculation_actions()
    definition = build_modelo_filing_record_import_definition(
        calculations, execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_modelo_filing_record_import_registration(definition, calculations),))


def compose_modelo_filing_record_view_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo filing record view operation."""
    from ..application.modelo.filing_record_view_operation import (
        build_modelo_filing_record_view_definition,
        build_modelo_filing_record_view_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_filing_record_view_definition(bundle)
    return built((definition,), (build_modelo_filing_record_view_registration(definition, bundle),))


def compose_modelo_taxation_comparison_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo taxation comparison operation."""
    from ..adapters.persistence.profile.taxation_comparison import build_taxation_comparison_ports
    from ..application.modelo.taxation_comparison_operation import (
        build_modelo_taxation_comparison_definition,
        build_modelo_taxation_comparison_registration,
    )

    del inputs
    definition = build_modelo_taxation_comparison_definition(build_taxation_comparison_ports)
    return built(
        (definition,), (build_modelo_taxation_comparison_registration(definition, build_taxation_comparison_ports),)
    )


def compose_modelo_local_observation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo local observation operation."""
    from ..application.modelo.local_observation_operation import (
        build_modelo_local_observation_definition,
        build_modelo_local_observation_registration,
    )

    definition = build_modelo_local_observation_definition(
        inputs.calculation_actions(), execution_caller_reader=inputs.execution_caller_reader
    )
    return built((definition,), (build_modelo_local_observation_registration(definition),))


def compose_modelo_verification_report_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo verification report read operation."""
    from ..application.modelo.verification_report_read_operation import (
        build_modelo_verification_report_list_definition,
        build_modelo_verification_report_list_registration,
        build_modelo_verification_report_view_definition,
        build_modelo_verification_report_view_registration,
    )

    bundle = inputs.verification_bundle()
    listing = build_modelo_verification_report_list_definition(bundle)
    view = build_modelo_verification_report_view_definition(bundle)
    return built(
        (listing, view),
        (
            build_modelo_verification_report_list_registration(listing, bundle),
            build_modelo_verification_report_view_registration(view, bundle),
        ),
    )


def compose_modelo_amendment_context_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo amendment context operation."""
    from ..application.modelo.amendment_context_operation import (
        build_modelo_work_amendment_context_definition,
        build_modelo_work_amendment_context_registration,
    )

    bundle = inputs.verification_bundle()
    definition = build_modelo_work_amendment_context_definition(bundle)
    return built((definition,), (build_modelo_work_amendment_context_registration(definition, bundle),))


def compose_modelo_m303_attestation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo m303 attestation operation."""
    from ..application.modelo.m303_attestation_operation import (
        build_modelo_work_m303_attestation_definition,
        build_modelo_work_m303_attestation_registration,
    )
    from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access

    lifecycle = inputs.work_lifecycle()
    definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=lifecycle,
        attachment_store_factory=inputs.attachments(),
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built(
        (definition,),
        (
            build_modelo_work_m303_attestation_registration(
                definition, access_resolver=compose_modelo_metadata_access(lifecycle)
            ),
        ),
    )


def compose_modelo_iva_wallet_correction_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo iva wallet correction operation."""
    from ..application.modelo.iva_wallet_correction_operation import (
        build_modelo_iva_wallet_correction_definition,
        build_modelo_iva_wallet_correction_registration,
    )
    from .adapter_composition_ports import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_correction_definition(build_modelo_iva_wallet_seed_ports)
    return built((definition,), (build_modelo_iva_wallet_correction_registration(definition),))


def compose_modelo_iva_wallet_balance_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo iva wallet balance operation."""
    from ..application.modelo.iva_wallet_balance_operation import (
        build_modelo_iva_wallet_balance_definition,
        build_modelo_iva_wallet_balance_registration,
    )
    from .adapter_composition_ports import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_balance_definition(build_modelo_iva_wallet_seed_ports)
    return built((definition,), (build_modelo_iva_wallet_balance_registration(definition),))


def compose_modelo_iva_wallet_seed_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo iva wallet seed operation."""
    from ..application.modelo.iva_wallet_seed_operation import (
        build_modelo_iva_wallet_seed_definition,
        build_modelo_iva_wallet_seed_registration,
    )
    from .adapter_composition_ports import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_seed_definition(build_modelo_iva_wallet_seed_ports)
    return built((definition,), (build_modelo_iva_wallet_seed_registration(definition),))


def compose_modelo_iva_wallet_override_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo iva wallet override operation."""
    from ..application.modelo.iva_wallet_override_operation import (
        build_modelo_iva_wallet_override_definition,
        build_modelo_iva_wallet_override_registration,
    )
    from .adapter_composition_ports import build_modelo_iva_wallet_seed_ports

    del inputs
    definition = build_modelo_iva_wallet_override_definition(build_modelo_iva_wallet_seed_ports)
    return built((definition,), (build_modelo_iva_wallet_override_registration(definition),))


def compose_modelo_review_package_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo review package operation."""
    from ..application.modelo.review_package_operation import (
        build_modelo_review_package_build_definition,
        build_modelo_review_package_build_registration,
    )
    from ..application.modelo.revision_operation_access import compose_modelo_revision_access

    bundle = inputs.verification_bundle()
    definition = build_modelo_review_package_build_definition(
        profile_resolver=inputs.modelo_profile(),
        export_ports_factory=inputs.modelo_exports(),
        repositories=bundle,
        execution_caller_reader=inputs.execution_caller_reader,
    )
    return built(
        (definition,),
        (
            build_modelo_review_package_build_registration(
                definition, access_resolver=compose_modelo_revision_access(bundle)
            ),
        ),
    )


def compose_modelo_m360_solicitud_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose modelo m360 solicitud operation."""
    from ..adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository
    from ..application.modelo.m360_solicitud_operation import (
        build_modelo_360_solicitud_definition,
        build_modelo_360_solicitud_registration,
    )

    definition = build_modelo_360_solicitud_definition(Modelo360SolicitudRepository, inputs.own_accounts)
    return built((definition,), (build_modelo_360_solicitud_registration(definition),))
