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

from functools import partial
from typing import TYPE_CHECKING

from ..application.operations.contract_manifest import (
    OperationGroupBuild,
)

if TYPE_CHECKING:
    from ..application.live.justificante_capture_operation import JustificanteCapturePorts
    from ..application.live.verify import VerifySurface
    from ..application.operations.operation_definition import OperationDefinition
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


from .operation_composition_inputs import (
    OperationCompositionInputs,
    acquire_registry_verify_observation,
    built,
    notification_document_service,
    notification_ports,
    verify_live_preflight,
    verify_persistence,
)


def compose_live_borrador_100_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live borrador 100 operation."""
    from ..application.live.borrador_100_operation import (
        build_borrador_100_operation_definitions,
        build_borrador_100_operation_registrations,
    )
    from .live_borrador_operation_composition import build_borrador_100_operation_ports

    del inputs
    definitions = build_borrador_100_operation_definitions(build_borrador_100_operation_ports)
    return built(definitions, build_borrador_100_operation_registrations(definitions))


def compose_live_filed_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live filed history operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
    from ..application.live.filed_history_operation import (
        bind_shared_filed_history_pull,
        build_filed_history_operation_definition,
        build_filed_history_operation_registration,
    )
    from .live_state_composition import (
        compose_live_state,
        preflight_filed_history_provider,
        pull_filed_history_with_shared_composition,
    )

    del inputs
    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=compose_live_state,
        browser_resources_factory=BrowserRuntimeResourceScope,
        pull=bind_shared_filed_history_pull(pull_filed_history_with_shared_composition),
        provider_preflight=preflight_filed_history_provider,
    )
    return built((definition,), (build_filed_history_operation_registration(definition),))


def compose_live_filed_single_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live filed single capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_single_capture_operation import (
        build_filed_single_capture_definition,
        build_filed_single_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_single_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_filed_single_capture_registration(definition),))


def compose_live_filed_bulk_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live filed bulk capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
    from ..application.live.filed_bulk_capture_operation import (
        build_filed_bulk_capture_definition,
        build_filed_bulk_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_bulk_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider, SyncRunRecordRepository
    )
    return built((definition,), (build_filed_bulk_capture_registration(definition),))


def compose_live_filed_source_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live filed source capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_source_capture_operation import (
        build_filed_source_capture_definition,
        build_filed_source_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_filed_source_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_filed_source_capture_registration(definition),))


def compose_live_filed_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live filed read operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.filed_read_operation import (
        build_filed_discover_definition,
        build_filed_discover_registration,
        build_filed_list_definition,
        build_filed_list_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    listing = build_filed_list_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    discover = build_filed_discover_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built(
        (listing, discover), (build_filed_list_registration(listing), build_filed_discover_registration(discover))
    )


def compose_live_iva_wallet_history_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live iva wallet history operation."""
    from ..application.live.iva_wallet_history_operation import (
        build_iva_wallet_history_definition,
        build_iva_wallet_history_registration,
    )
    from .live_state_composition import compose_live_state

    del inputs
    definition = build_iva_wallet_history_definition(
        lambda operation: compose_live_state(operation=operation).iva_remote_state_port
    )
    return built((definition,), (build_iva_wallet_history_registration(definition),))


def compose_live_iva_wallet_history_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live iva wallet history capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_wallet_history_capture_operation import (
        build_iva_wallet_history_capture_definition,
        build_iva_wallet_history_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_wallet_history_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_iva_wallet_history_capture_registration(definition),))


def compose_live_iva_wallet_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live iva wallet capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_wallet_capture_operation import (
        build_iva_wallet_capture_definition,
        build_iva_wallet_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_wallet_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_iva_wallet_capture_registration(definition),))


def compose_live_sede_view_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live sede view operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
    from ..adapters.outbound.aeat.browser.sede_view import open_sede_view
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.live.sede_view_operation import build_sede_view_definition, build_sede_view_registration
    from .live_state_composition import preflight_filed_history_provider

    definition = build_sede_view_definition(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=inputs.scope,
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=preflight_filed_history_provider,
        view_browser_factory=open_sede_view,
        stream_opener=inputs.sede_view_stream_opener,
    )
    return built((definition,), (build_sede_view_registration(definition),))


def compose_live_iva_remote_state_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live iva remote state capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.iva_remote_state_capture_operation import (
        build_iva_remote_state_capture_definition,
        build_iva_remote_state_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_iva_remote_state_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_iva_remote_state_capture_registration(definition),))


def compose_live_notifications_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live notifications capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.notifications_capture_operation import (
        build_notifications_capture_definition,
        build_notifications_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    del inputs
    definition = build_notifications_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_notifications_capture_registration(definition),))


def compose_live_notification_document_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live notification document capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.notification_document_capture_operation import (
        build_notification_document_capture_definition,
        build_notification_document_capture_registration,
    )
    from .live_state_composition import compose_live_state, preflight_filed_history_provider

    definition = build_notification_document_capture_definition(
        compose_live_state,
        partial(notification_document_service, inputs.resolved_settings),
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    return built((definition,), (build_notification_document_capture_registration(definition),))


def compose_live_notification_document_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live notification document read operation."""
    from ..application.live.notification_document_read_operation import (
        build_notification_document_history_definition,
        build_notification_document_history_registration,
        build_notification_document_view_definition,
        build_notification_document_view_registration,
    )

    service = partial(notification_document_service, inputs.resolved_settings)
    view = build_notification_document_view_definition(service)
    history = build_notification_document_history_definition(service)
    return built(
        (view, history),
        (
            build_notification_document_view_registration(view),
            build_notification_document_history_registration(history),
        ),
    )


def compose_live_notifications_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live notifications read operation."""
    from ..application.live.notifications_read_operation import (
        build_notifications_latest_definition,
        build_notifications_latest_registration,
        build_notifications_list_definition,
        build_notifications_list_registration,
        build_notifications_show_definition,
        build_notifications_show_registration,
    )

    ports = partial(notification_ports, inputs.resolved_settings)
    listing = build_notifications_list_definition(ports)
    show = build_notifications_show_definition(ports)
    latest = build_notifications_latest_definition(ports)
    return built(
        (listing, show, latest),
        (
            build_notifications_list_registration(listing),
            build_notifications_show_registration(show),
            build_notifications_latest_registration(latest),
        ),
    )


def compose_live_expedientes_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live expedientes read operation."""
    from ..application.live.expedientes_read_operation import (
        build_expedientes_latest_definition,
        build_expedientes_latest_registration,
        build_expedientes_list_definition,
        build_expedientes_list_registration,
        build_expedientes_show_definition,
        build_expedientes_show_registration,
    )
    from .adapter_composition_work_ports import build_expedientes_ports

    del inputs
    listing = build_expedientes_list_definition(build_expedientes_ports)
    show = build_expedientes_show_definition(build_expedientes_ports)
    latest = build_expedientes_latest_definition(build_expedientes_ports)
    return built(
        (listing, show, latest),
        (
            build_expedientes_list_registration(listing),
            build_expedientes_show_registration(show),
            build_expedientes_latest_registration(latest),
        ),
    )


def compose_live_expedientes_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live expedientes capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.live.expedientes_capture_operation import (
        build_expedientes_bulk_capture_definition,
        build_expedientes_bulk_capture_registration,
        build_expedientes_single_capture_definition,
        build_expedientes_single_capture_registration,
    )
    from .adapter_composition_work_ports import build_expedientes_ports
    from .live_state_composition import preflight_filed_history_provider

    single = build_expedientes_single_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        inputs.scope,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    bulk = build_expedientes_bulk_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        inputs.scope,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    return built(
        (single, bulk),
        (build_expedientes_single_capture_registration(single), build_expedientes_bulk_capture_registration(bulk)),
    )


def compose_live_verify_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live verify capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..application.live.verify import VerifySurface
    from ..application.live.verify_capture_operation import (
        build_verify_capture_definition,
        build_verify_capture_registration,
    )

    settings = inputs.resolved_settings

    def capture(surface: VerifySurface, injected: OperationDefinition | None) -> OperationDefinition:
        return injected or build_verify_capture_definition(
            surface,
            persistence_factory=partial(verify_persistence, settings),
            acquire=partial(acquire_registry_verify_observation, resolved_settings=settings),
            browser_resources_factory=BrowserRuntimeResourceScope,
            provider_preflight=partial(verify_live_preflight, settings),
        )

    nif_iva = capture(VerifySurface.NIF_IVA, inputs.verify_nif_iva_definition)
    tgvi = capture(VerifySurface.TGVI, inputs.verify_tgvi_definition)
    return built((nif_iva, tgvi), (build_verify_capture_registration(nif_iva), build_verify_capture_registration(tgvi)))


def compose_live_verify_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live verify read operation."""
    from ..application.live.verify_read_operation import (
        build_verify_latest_definition,
        build_verify_latest_registration,
        build_verify_list_definition,
        build_verify_list_registration,
        build_verify_view_definition,
        build_verify_view_registration,
    )

    persistence = partial(verify_persistence, inputs.resolved_settings)
    listing = build_verify_list_definition(persistence)
    view = build_verify_view_definition(persistence)
    latest = build_verify_latest_definition(persistence)
    return built(
        (listing, view, latest),
        (
            build_verify_list_registration(listing),
            build_verify_view_registration(view),
            build_verify_latest_registration(latest),
        ),
    )


def compose_live_justificante_capture_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live justificante capture operation."""
    from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
    from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
    from ..application.live.justificante_capture_operation import (
        JustificanteCapturePorts,
        build_justificante_capture_definition,
        build_justificante_capture_registration,
    )
    from .justificante_composition import (
        build_justificante_authenticity_verifier,
        build_justificante_capture_service,
        build_justificante_live_read_port,
        build_justificante_registration_ports,
    )
    from .live_state_composition import preflight_filed_history_provider

    scope = inputs.scope

    def capture_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> JustificanteCapturePorts:
        return JustificanteCapturePorts(
            service=build_justificante_capture_service(bucket_id),
            read_port=build_justificante_live_read_port(build_certificate_secret_backend, scope, operation),
            registration_ports=build_justificante_registration_ports(operation),
            verifier=build_justificante_authenticity_verifier(),
        )

    definition = build_justificante_capture_definition(
        capture_ports, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    return built((definition,), (build_justificante_capture_registration(definition),))


def compose_live_justificante_read_operation(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose live justificante read operation."""
    from ..application.live.justificante_read_operation import (
        build_justificante_list_definition,
        build_justificante_list_registration,
        build_justificante_show_definition,
        build_justificante_show_registration,
    )
    from .justificante_composition import build_justificante_capture_service

    del inputs
    listing = build_justificante_list_definition(build_justificante_capture_service)
    show = build_justificante_show_definition(build_justificante_capture_service)
    return built(
        (listing, show), (build_justificante_list_registration(listing), build_justificante_show_registration(show))
    )
