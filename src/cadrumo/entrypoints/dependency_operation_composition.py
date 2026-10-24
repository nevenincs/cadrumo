"""Compose the setup registry and the ``dependencies.*`` operations.

Acquiring the browser and the local AI belongs to the native component engine.
The registry composed here only reads what is already on this computer: each
item's effect ports refuse, and each item is withdrawn, so a status still
names what is missing while a setup refuses as not in this build before
anything is planned or downloaded. The registry holds software only; the
profile's Google sign-in is not one of its items.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..application.dependency_network import dependency_hosts
from ..application.dependency_receipts import DependencyReceiptStore, dependency_receipts_root
from ..application.dependency_registry import DependencyRegistry
from ..application.dependency_setup_operation import (
    DependencyRegistryFactory,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ..application.dependency_transfer import dependency_retry_delay
from ..application.dependency_withdrawal import (
    WithdrawnSetupItem,
    refused_browser_install,
    refused_browser_launch,
    refused_build_removal,
    refused_runtime_install,
    refused_runtime_spawn,
)
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


def build_dependency_registry_factory() -> DependencyRegistryFactory:
    """Return the per-invocation registry factory of withdrawn, read-only items."""

    def build(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
        del identity, loop
        # Acquisition belongs to the native component engine: these items only
        # read what is on this computer, and every effect port refuses.
        browser = PlaywrightBrowserItem(
            install=refused_browser_install,
            launch=refused_browser_launch,
            remove_builds=refused_build_removal,
            receipts=DependencyReceiptStore(dependency_receipts_root()),
        )
        local_ai = local_ai_setup_item(
            runtime_hosts=dependency_hosts("model_runtime"),
            model_hosts=dependency_hosts("model_registry"),
            run_installer=refused_runtime_install,
            spawn=refused_runtime_spawn,
            retry_delay=dependency_retry_delay,
        )
        return DependencyRegistry((WithdrawnSetupItem(browser), WithdrawnSetupItem(local_ai)))

    return build


def build_dependency_operations() -> DependencyOperations:
    """Bind the item adapters to ``dependencies.status``, ``dependencies.setup`` and ``dependencies.verify``."""
    definitions = build_dependency_operation_definitions(build_dependency_registry_factory())
    return DependencyOperations(
        definitions=definitions, registrations=build_dependency_operation_registrations(definitions)
    )
