"""Compose the setup registry and the ``dependencies.*`` operations from the item adapters.

Each invocation gets its own registry, because a contained profile worker
starts the local AI program's server by asking the runtime that owns it, which
admits that request for the one operation it names. The local AI item is
therefore built per invocation with that operation's identity. The registry
holds software only; the profile's Google sign-in is not one of its items.

The network preflight of a full check runs once per host group in the
registry, so no item is bound to run its own.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..adapters.outbound.browser_runtime.installer import (
    measure_browser_downloads,
    remove_browser_builds,
    run_browser_install,
)
from ..adapters.outbound.browser_runtime.launch_check import launch_headless_browser
from ..adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
from ..adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
from ..application.dependency_network import dependency_host_reachability, dependency_hosts
from ..application.dependency_receipts import DependencyReceiptStore, dependency_receipts_root
from ..application.dependency_registry import DependencyRegistry
from ..application.dependency_setup_operation import (
    DependencyRegistryFactory,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ..application.dependency_transfer import dependency_retry_delay
from ..application.local_reader_provisioning import RuntimeServerOwnerStart, owner_started_spawner
from ..application.local_reader_setup_items import local_ai_setup_item
from ..application.operations.models import OperationIdentity
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
from ..application.provisioning_browser import PlaywrightBrowserItem

__all__ = ["DependencyOperations", "build_dependency_operations", "build_dependency_registry_factory"]


@dataclass(frozen=True, slots=True)
class DependencyOperations:
    """The definitions and public registrations of the status, setup and verify operations."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def build_dependency_registry_factory(
    *, owner_start: RuntimeServerOwnerStart | None = None
) -> DependencyRegistryFactory:
    """Return the per-invocation registry factory.

    ``owner_start`` is bound by a contained process, whose model program
    server must be started by its owner on behalf of the running operation.
    """

    def build(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
        spawn = spawn_runtime_server if owner_start is None else owner_started_spawner(owner_start, identity, loop)
        browser = PlaywrightBrowserItem(
            install=run_browser_install,
            measure=measure_browser_downloads,
            launch=launch_headless_browser,
            remove_builds=remove_browser_builds,
            receipts=DependencyReceiptStore(dependency_receipts_root()),
        )
        local_ai = local_ai_setup_item(
            runtime_hosts=dependency_hosts("model_runtime"),
            model_hosts=dependency_hosts("model_registry"),
            run_installer=run_runtime_installer,
            spawn=spawn,
            retry_delay=dependency_retry_delay,
            text_probe=probe_text_extraction_fitness,
        )
        return DependencyRegistry(
            (browser, local_ai),
            reachability=dependency_host_reachability,
            hosts_for=dependency_hosts,
        )

    return build


def build_dependency_operations(*, owner_start: RuntimeServerOwnerStart | None = None) -> DependencyOperations:
    """Bind the item adapters to ``dependencies.status``, ``dependencies.setup`` and ``dependencies.verify``."""
    definitions = build_dependency_operation_definitions(build_dependency_registry_factory(owner_start=owner_start))
    return DependencyOperations(
        definitions=definitions, registrations=build_dependency_operation_registrations(definitions)
    )
