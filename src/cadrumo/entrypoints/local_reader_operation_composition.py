"""Compose the operations that provision and report on what the machine holds for local reading.

The four operations share one subject family, the machine's own runtime and
browser build, and the same outbound adapters: the model runtime's installer,
the text reader's fitness probe and the browser installer.

The one port whose binding depends on the process is the start of the runtime's
server. A profile worker is contained, so a server it started itself would end
with it. The worker therefore binds a start that asks the runtime that owns it,
the runtime binds :func:`start_owned_runtime_server` to answer, and every
process that may own the server binds the adapter that starts it directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters.outbound.browser_runtime.installer import run_browser_installer
from ..adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
from ..adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
from ..application.browser_runtime_operation import (
    build_browser_runtime_operation_definition,
    build_browser_runtime_operation_registration,
)
from ..application.local_reader_operation import (
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from ..application.local_reader_provisioning import RuntimeServerOwnerStart
from ..application.local_reader_report import (
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from ..application.local_reader_status_operation import (
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
from ..application.provisioning_host import launch_runtime_server

__all__ = ["LocalReaderOperations", "build_local_reader_operations", "start_owned_runtime_server"]


@dataclass(frozen=True, slots=True)
class LocalReaderOperations:
    """The definitions and public registrations of the reader and browser provisioning family."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def start_owned_runtime_server() -> int | None:
    """Start the machine's model runtime server from this process, for a worker that may not own one.

    The program and its environment are resolved here, from this process's own
    settings. Returns the server's process id, or ``None`` when nothing was
    started.
    """
    return launch_runtime_server(spawn=spawn_runtime_server)


def build_local_reader_operations(*, owner_start: RuntimeServerOwnerStart | None = None) -> LocalReaderOperations:
    """Bind the outbound adapters to the three ``local-reader`` operations and ``browser-runtime.provision``.

    ``owner_start`` is bound by a process that is contained and so asks its
    owner to start the runtime's server. Without it the server is started from
    the executing process.
    """
    provision = build_local_reader_operation_definition(
        spawn=spawn_runtime_server if owner_start is None else owner_start,
        run_installer=run_runtime_installer,
        text_probe=probe_text_extraction_fitness,
    )
    status = build_local_reader_status_definition(text_probe=probe_text_extraction_fitness)
    report = build_local_reader_report_definition()
    browser = build_browser_runtime_operation_definition(run_installer=run_browser_installer)
    return LocalReaderOperations(
        definitions=(provision, status, report, browser),
        registrations=(
            build_local_reader_operation_registration(provision),
            build_local_reader_status_registration(status),
            build_local_reader_report_registration(report),
            build_browser_runtime_operation_registration(browser),
        ),
    )
