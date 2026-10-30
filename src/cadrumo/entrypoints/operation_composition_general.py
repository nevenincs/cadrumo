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
    build_profile_history_read_ports,
    built,
    supplied,
)


def compose_auth_operation_definitions(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth operation definitions."""
    from ..application.auth.operation_definitions import (
        build_auth_operation_definitions,
        build_auth_operation_registrations,
    )

    definitions = (
        inputs.auth_definitions
        if inputs.auth_definitions is not None
        else build_auth_operation_definitions(
            ports=inputs.auth_ports, finalize_rotation=inputs.profile_rotation_finalizer
        )
    )
    return built(definitions, build_auth_operation_registrations(definitions))


def compose_auth_certificate_secret_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth certificate secret operation."""
    from ..application.auth.certificate_secret_operation import (
        CertificateSecretOperationPorts,
        build_certificate_secret_operation_definitions,
        build_certificate_secret_operation_registrations,
    )

    definitions = build_certificate_secret_operation_definitions(
        CertificateSecretOperationPorts(
            operator_scope_ports=inputs.scope,
            certificate_secret_backend_factory=inputs.auth_ports.certificate_secret_backend_factory,
        )
    )
    return built(definitions, build_certificate_secret_operation_registrations(definitions))


def compose_auth_certificate_source_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth certificate source operation."""
    from ..application.auth.certificate_source_execution import CertificateSourceOperationPorts
    from ..application.auth.certificate_source_operation import (
        build_certificate_source_check_definition,
        build_certificate_source_check_registration,
        build_certificate_source_list_definition,
        build_certificate_source_list_registration,
        build_certificate_source_register_definition,
        build_certificate_source_register_registration,
        build_certificate_source_remove_definition,
        build_certificate_source_remove_registration,
        build_certificate_source_select_definition,
        build_certificate_source_select_registration,
    )

    ports = CertificateSourceOperationPorts(
        operator_scope_ports=inputs.scope,
        operator_probe_ports=inputs.auth_ports.operator_probe_ports,
        certificate_secret_backend_factory=inputs.auth_ports.certificate_secret_backend_factory,
    )
    register = build_certificate_source_register_definition(ports)
    listing = build_certificate_source_list_definition(ports)
    select = build_certificate_source_select_definition(ports)
    remove = build_certificate_source_remove_definition(ports)
    check = build_certificate_source_check_definition(ports)
    return built(
        (register, listing, select, remove, check),
        (
            build_certificate_source_register_registration(register),
            build_certificate_source_list_registration(listing),
            build_certificate_source_select_registration(select),
            build_certificate_source_remove_registration(remove),
            build_certificate_source_check_registration(check),
        ),
    )


def compose_auth_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth read operation."""
    from ..application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
    from .auth_read_composition import compose_auth_read_ports

    del inputs
    definition = build_auth_read_definition(compose_auth_read_ports)
    return built((definition,), (build_auth_read_registration(definition),))


def compose_auth_apoderado_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth apoderado operation."""
    from ..application.auth.apoderado_operation import (
        build_apoderado_operation_definitions,
        build_apoderado_operation_registrations,
    )
    from .auth_apoderado_composition import build_apoderado_operation_ports

    del inputs
    definitions = build_apoderado_operation_definitions(build_apoderado_operation_ports)
    return built(definitions, build_apoderado_operation_registrations(definitions))


def compose_auth_diagnostic_report_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose auth diagnostic report operation."""
    from ..application.auth.diagnostic_report_operation import (
        build_auth_diagnostic_report_definition,
        build_auth_diagnostic_report_registration,
    )
    from .auth_apoderado_composition import build_auth_diagnostic_report_ports

    del inputs
    definition = build_auth_diagnostic_report_definition(build_auth_diagnostic_report_ports)
    return built((definition,), (build_auth_diagnostic_report_registration(definition),))


# -- profile-wide registered operations --------------------------------------------------------------------------------


def compose_review_read_registration(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose review read registration."""
    from ..application.review.read_contracts import ReviewReadOperationPorts
    from ..application.review.read_registration import build_review_read_definitions, build_review_read_registrations
    from .adapter_composition_ports import build_draft_review_ports

    definitions = build_review_read_definitions(
        ReviewReadOperationPorts(settings=inputs.resolved_settings, draft_review_ports_factory=build_draft_review_ports)
    )
    return built(definitions, build_review_read_registrations(definitions))


def compose_diagnostics_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose diagnostics operation."""
    from ..application.diagnostics_operation import (
        build_diagnostics_read_definition,
        build_diagnostics_read_registration,
    )
    from .diagnostics_operation_composition import build_diagnostics_read_ports

    del inputs
    definition = build_diagnostics_read_definition(build_diagnostics_read_ports)
    return built((definition,), (build_diagnostics_read_registration(definition),))


def compose_diagnostics_repair_composition(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose diagnostics repair composition."""
    from .diagnostics_repair_composition import build_diagnostics_repair_operations, probe_aeat_sede_connectivity

    operations = build_diagnostics_repair_operations(
        execution_caller_reader=inputs.execution_caller_reader,
        connectivity_probe=supplied(inputs.connectivity_probe, probe_aeat_sede_connectivity),
    )
    return built(operations.definitions, operations.registrations)


def compose_workbench_generation_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose workbench generation operation."""
    from ..application.workbench_generation_operation import (
        build_workbench_generation_operation_definition,
        build_workbench_generation_operation_registration,
    )

    definition = build_workbench_generation_operation_definition(inputs.workbench_generation_reader)
    return built((definition,), (build_workbench_generation_operation_registration(definition),))


def compose_actividad_asset_registered_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose actividad asset registered operations."""
    from ..application.actividad_asset.registered_operations import (
        build_activity_asset_claim_definition,
        build_activity_asset_claim_registration,
        build_activity_asset_correct_definition,
        build_activity_asset_correct_registration,
        build_activity_asset_create_definition,
        build_activity_asset_create_registration,
        build_activity_asset_describe_definition,
        build_activity_asset_describe_registration,
        build_activity_asset_dispose_definition,
        build_activity_asset_dispose_registration,
        build_activity_asset_filing_handoff_definition,
        build_activity_asset_filing_handoff_registration,
        build_activity_asset_forecast_definition,
        build_activity_asset_forecast_registration,
        build_activity_asset_inspect_definition,
        build_activity_asset_inspect_registration,
        build_activity_asset_read_definitions,
        build_activity_asset_read_registration,
    )
    from .actividad_asset_composition import build_activity_asset_operation_ports

    del inputs
    ports = build_activity_asset_operation_ports
    create = build_activity_asset_create_definition(ports)
    inspect = build_activity_asset_inspect_definition(ports)
    correct = build_activity_asset_correct_definition(ports)
    forecast = build_activity_asset_forecast_definition(ports)
    claim = build_activity_asset_claim_definition(ports)
    handoff = build_activity_asset_filing_handoff_definition(ports)
    describe = build_activity_asset_describe_definition(ports)
    dispose = build_activity_asset_dispose_definition(ports)
    reads = build_activity_asset_read_definitions(ports)
    return built(
        (create, inspect, correct, forecast, claim, handoff, describe, dispose, *reads),
        (
            build_activity_asset_create_registration(create),
            build_activity_asset_inspect_registration(inspect),
            build_activity_asset_correct_registration(correct),
            build_activity_asset_forecast_registration(forecast),
            build_activity_asset_claim_registration(claim),
            build_activity_asset_filing_handoff_registration(handoff),
            build_activity_asset_describe_registration(describe),
            build_activity_asset_dispose_registration(dispose),
            *(build_activity_asset_read_registration(definition) for definition in reads),
        ),
    )


def compose_inventory_registered_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose inventory registered operation."""
    from ..application.inventory.registered_evidence_operation import (
        build_inventory_evidence_add_definition,
        build_inventory_evidence_add_registration,
    )
    from ..application.inventory.registered_operation import (
        build_inventory_closing_authority_record_definition,
        build_inventory_closing_authority_record_registration,
        build_inventory_closing_value_record_definition,
        build_inventory_closing_value_record_registration,
        build_inventory_create_definition,
        build_inventory_create_registration,
        build_inventory_inspect_definition,
        build_inventory_inspect_registration,
        build_inventory_ledger_change_definitions,
        build_inventory_ledger_change_registration,
        build_inventory_list_definition,
        build_inventory_list_registration,
        build_inventory_movement_add_definition,
        build_inventory_movement_add_registration,
        build_inventory_valuation_preview_definition,
        build_inventory_valuation_preview_registration,
    )
    from ..application.inventory.registered_options_operation import (
        build_inventory_options_definition,
        build_inventory_options_registration,
    )
    from .adapter_composition_ports import build_inventory_service_ports
    from .adapter_composition_work_ports import build_ledger_evidence_ports

    caller = inputs.execution_caller_reader
    evidence = build_inventory_evidence_add_definition(build_ledger_evidence_ports, execution_caller_reader=caller)
    options = build_inventory_options_definition()
    listing = build_inventory_list_definition(build_inventory_service_ports)
    create = build_inventory_create_definition(build_inventory_service_ports, execution_caller_reader=caller)
    movement = build_inventory_movement_add_definition(build_inventory_service_ports, execution_caller_reader=caller)
    valuation = build_inventory_valuation_preview_definition(
        build_inventory_service_ports, execution_caller_reader=caller
    )
    closing = build_inventory_closing_authority_record_definition(
        build_inventory_service_ports, execution_caller_reader=caller
    )
    closing_value = build_inventory_closing_value_record_definition(
        build_inventory_service_ports, execution_caller_reader=caller
    )
    inspect = build_inventory_inspect_definition(build_inventory_service_ports)
    changes = build_inventory_ledger_change_definitions(build_inventory_service_ports, execution_caller_reader=caller)
    return built(
        (listing, create, movement, valuation, closing, closing_value, inspect, evidence, options, *changes),
        (
            build_inventory_list_registration(listing),
            build_inventory_create_registration(create),
            build_inventory_movement_add_registration(movement),
            build_inventory_valuation_preview_registration(valuation),
            build_inventory_closing_authority_record_registration(closing),
            build_inventory_closing_value_record_registration(closing_value),
            build_inventory_inspect_registration(inspect),
            build_inventory_evidence_add_registration(evidence),
            build_inventory_options_registration(options),
            *(build_inventory_ledger_change_registration(definition) for definition in changes),
        ),
    )


def compose_bienes_inversion_registered_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose bienes inversion registered operation."""
    from ..application.bienes_inversion.registered_operation import (
        build_bienes_inversion_declare_definition,
        build_bienes_inversion_declare_registration,
        build_bienes_inversion_list_definition,
        build_bienes_inversion_list_registration,
    )
    from .adapter_composition_ports import build_bienes_inversion_repository

    del inputs
    listing = build_bienes_inversion_list_definition(build_bienes_inversion_repository)
    declare = build_bienes_inversion_declare_definition(build_bienes_inversion_repository)
    return built(
        (listing, declare),
        (build_bienes_inversion_list_registration(listing), build_bienes_inversion_declare_registration(declare)),
    )


def compose_prorrata_register_registered_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose prorrata register registered operations."""
    from ..application.prorrata_register.registered_operations import (
        build_prorrata_declare_sector_definition,
        build_prorrata_elect_especial_definition,
        build_prorrata_elect_general_definition,
        build_prorrata_list_definition,
        build_prorrata_list_registration,
        build_prorrata_mutation_registration,
        build_prorrata_revoke_especial_definition,
        build_prorrata_seed_definition,
        build_prorrata_seed_sector_definition,
        build_prorrata_settle_sector_definition,
    )
    from .adapter_composition_ports import build_prorrata_register_repository

    repository = build_prorrata_register_repository
    listing = build_prorrata_list_definition(repository)
    mutations = (
        build_prorrata_declare_sector_definition(repository),
        build_prorrata_elect_especial_definition(repository),
        build_prorrata_elect_general_definition(repository),
        build_prorrata_revoke_especial_definition(repository),
        build_prorrata_seed_definition(repository, inputs.calculation_actions()),
        build_prorrata_seed_sector_definition(repository),
        build_prorrata_settle_sector_definition(repository),
    )
    return built(
        (listing, *mutations),
        (
            build_prorrata_list_registration(listing),
            *(build_prorrata_mutation_registration(definition) for definition in mutations),
        ),
    )


# -- user profile ------------------------------------------------------------------------------------------------------


def compose_user_profile_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile operations."""
    from ..application.user_profile.operations import (
        build_user_profile_operation_definitions,
        build_user_profile_operation_registrations,
    )

    del inputs
    definitions = build_user_profile_operation_definitions()
    return built(definitions, build_user_profile_operation_registrations(definitions))


def compose_user_profile_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile history operation."""
    from ..application.user_profile.history_operation import (
        build_profile_history_definition,
        build_profile_history_registration,
        build_profile_history_timeline_definition,
        build_profile_history_timeline_registration,
    )

    del inputs
    history = build_profile_history_definition(build_profile_history_read_ports)
    timeline = build_profile_history_timeline_definition(build_profile_history_read_ports)
    return built(
        (history, timeline),
        (build_profile_history_registration(history), build_profile_history_timeline_registration(timeline)),
    )


def compose_user_profile_google_configuration_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile google configuration operation."""
    from ..application.user_profile.google_configuration_operation import (
        build_google_configuration_definitions,
        build_google_configuration_registration,
    )
    from .google_configuration_operation_composition import build_google_configuration_operation_ports

    del inputs
    definitions = build_google_configuration_definitions(build_google_configuration_operation_ports)
    return built(definitions, (build_google_configuration_registration(definition) for definition in definitions))


def compose_user_profile_archive_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile archive operation."""
    from ..application.user_profile.archive_operation import (
        build_profile_archive_operation_definitions,
        build_profile_archive_operation_registrations,
    )
    from .profile_archive_operation_composition import build_profile_archive_operation_ports

    del inputs
    definitions = build_profile_archive_operation_definitions(build_profile_archive_operation_ports)
    return built(definitions, build_profile_archive_operation_registrations(definitions))


def compose_user_profile_recovery_status_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile recovery status operation."""
    from ..application.user_profile.recovery_status_operation import (
        build_recovery_status_definition,
        build_recovery_status_registration,
    )

    del inputs
    definition = build_recovery_status_definition()
    return built((definition,), (build_recovery_status_registration(definition),))


def compose_user_profile_recovery_revoke_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile recovery revoke operation."""
    from ..application.user_profile.recovery_revoke_operation import recovery_revoke_operation

    del inputs
    definition, registration = recovery_revoke_operation()
    return built((definition,), (registration,))


def compose_user_profile_automation_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile automation operations."""
    from ..application.user_profile.automation_operations import (
        build_automation_operation_definitions,
        build_automation_operation_registrations,
    )

    definitions = build_automation_operation_definitions(
        inputs.automation_administration_factory, inventory_reader=inputs.automation_inventory_reader
    )
    return built(definitions, build_automation_operation_registrations(definitions))


def compose_user_profile_censal_certificate_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile censal certificate operation."""
    from ..adapters.inbound.censo.parser import parse_certificado_censal_bytes
    from ..application.user_profile.censal_certificate_operation import censal_certificate_operation

    del inputs
    definition, registration = censal_certificate_operation(parse_certificado_censal_bytes)
    return built((definition,), (registration,))


def compose_user_profile_censal_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile censal operation."""
    from ..application.user_profile.censal_operation import (
        build_censal_operation_definition,
        build_censal_operation_registration,
    )

    if inputs.censal_definition is not None:
        definition = inputs.censal_definition
    else:
        from ..adapters.outbound.aeat.browser.factory import default_browser_session_factory
        from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
        from .adapter_composition_ports import build_censal_fetch_port
        from .live_state_composition import preflight_filed_history_provider

        definition = build_censal_operation_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=inputs.scope,
            censal_fetch_port=build_censal_fetch_port(),
            provider_preflight=preflight_filed_history_provider,
        )
    return built((definition,), (build_censal_operation_registration(definition),))


def compose_user_profile_censal_prepare_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile censal prepare operation."""
    from ..application.user_profile.censal_prepare_operation import (
        build_censal_prepare_operation_definition,
        build_censal_prepare_operation_registration,
    )
    from .censal_readback_composition import read_stored_censal_observation

    del inputs
    definition = build_censal_prepare_operation_definition(read_stored_censal_observation)
    return built((definition,), (build_censal_prepare_operation_registration(definition),))


def compose_user_profile_censal_file_import_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile censal file import operation."""
    from ..application.user_profile.censal_file_import_operation import (
        build_censal_file_import_operation_definition,
        build_censal_file_import_operation_registration,
    )

    del inputs
    definition = build_censal_file_import_operation_definition()
    return built((definition,), (build_censal_file_import_operation_registration(definition),))


def compose_user_profile_censal_preview_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose user profile censal preview operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.user_profile.censal_preview_operation import (
        build_censal_preview_operation_definition,
        build_censal_preview_operation_registration,
    )
    from .adapter_composition_ports import build_censal_fetch_port
    from .live_state_composition import preflight_filed_history_provider

    definition = build_censal_preview_operation_definition(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=inputs.scope,
        censal_fetch_port=build_censal_fetch_port(),
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=preflight_filed_history_provider,
    )
    return built((definition,), (build_censal_preview_operation_registration(definition),))


# -- exports -----------------------------------------------------------------------------------------------------------


def compose_export_google_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose export google operation."""
    from ..application.export.google_operation import (
        build_google_sheets_export_operation_definition,
        build_google_sheets_export_operation_registration,
    )

    if inputs.google_export_definition is not None:
        definition = inputs.google_export_definition
    else:
        from .google_export_operation_composition import build_google_sheets_export_prepare_port

        definition = build_google_sheets_export_operation_definition(
            prepare_port=build_google_sheets_export_prepare_port()
        )
    return built((definition,), (build_google_sheets_export_operation_registration(definition),))


def compose_export_google_review_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose export google review operation."""
    from ..application.export.google_review_operation import (
        build_google_review_operation_definition,
        build_google_review_operation_registration,
    )
    from .google_review_operation_composition import build_google_review_ports

    del inputs
    definition = build_google_review_operation_definition(build_google_review_ports)
    return built((definition,), (build_google_review_operation_registration(definition),))


def compose_export_calculation_review_xlsx_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose export calculation review xlsx operation."""
    from ..application.export.calculation_review_xlsx_operation import (
        build_calculation_review_xlsx_definition,
        build_calculation_review_xlsx_registration,
    )
    from .calculation_review_xlsx_operation_composition import build_calculation_review_xlsx_ports

    del inputs
    definition = build_calculation_review_xlsx_definition(build_calculation_review_xlsx_ports)
    return built((definition,), (build_calculation_review_xlsx_registration(definition),))
