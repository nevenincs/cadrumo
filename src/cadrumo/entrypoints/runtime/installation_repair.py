"""The installation acts that diagnose and repair an installation with no profile open.

``repair_report``, ``repair_logs`` and ``repair_profile`` do the work of
``config repair``, ``config repair logs`` and ``config repair profile``. Each
handler calls the application function the command calls, over the storage
root this runtime owns, and opens no profile: what it reports is what a
process holding no profile session can see.

Each reply is the document its command prints, with the real identifier of
every profile it names, so a frontend shows the reply and renders nothing of
its own. The command line alone hides those identifiers, where it prints.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...application.diagnostics import build_config_repair_report
from ...application.diagnostics_repair import read_log_tail
from ...application.diagnostics_repair_documents import (
    PreconditionActionResolver,
    printed,
    profile_pointer_repair_document,
    profile_record_document,
    repair_report_document,
)
from ...application.operator_surface.action_targets import resolve_recorded_precondition_action
from ...application.runtime.installation_requests import (
    RuntimeInstallationCompleted,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeRepairProfileReply,
    RuntimeRepairProfileRequest,
    RuntimeRepairReportReply,
    RuntimeRepairReportRequest,
)
from ...core.bucket_pointer import corrupt_pointer_reads_as_unselected
from ..adapter_composition import build_diagnostics_ports
from ..diagnostics_repair_composition import read_session_profile_record

if TYPE_CHECKING:
    from pydantic import BaseModel

    from .installation_composition import InstallationActRegistry
    from .installation_door import InstallationActExchange

__all__ = ["register_repair_acts"]


@contextmanager
def _served_root(exchange: InstallationActExchange, *, repairs_pointer: bool = False) -> Generator[None]:
    """Resolve settings over the storage root this runtime serves, for the length of one act.

    Composing settings reads the active-profile pointer, so a corrupt pointer
    refuses the act as it refuses a command at startup. Only the act that
    repairs the pointer reads a corrupt record as no selection, so that it can
    reach the record it repairs.
    """
    with ExitStack() as scope:
        if repairs_pointer:
            scope.enter_context(corrupt_pointer_reads_as_unselected())
        scope.enter_context(exchange.served_settings())
        yield


@contextmanager
def _profile_stores(exchange: InstallationActExchange, *, repairs_pointer: bool = False) -> Generator[None]:
    """Add the composed profile persistence the health and repair reads resolve their ports from."""
    with (
        _served_root(exchange, repairs_pointer=repairs_pointer),
        composed_profile_persistence_ports(automation_secrets_store=exchange.secret_store()),
    ):
        yield


def _reply_with[ReplyT: RuntimeInstallationCompleted](
    exchange: InstallationActExchange, reply_type: type[ReplyT], document: BaseModel
) -> ReplyT:
    """Reply with ``document`` as its command writes it out when identifiers are revealed."""
    return exchange.reply(reply_type, **dict(printed(document)))


class _RepairActs:
    """The three repair handlers, bound to the resolver of the actions their verdicts recommend."""

    def __init__(self, resolve_action: PreconditionActionResolver) -> None:
        self._resolve_action = resolve_action

    def report(
        self, request: RuntimeRepairReportRequest, exchange: InstallationActExchange, /
    ) -> RuntimeRepairReportReply:
        """Diagnose local configuration, profile, sign-in and log state, changing nothing."""
        del request
        with _profile_stores(exchange):
            report = build_config_repair_report(ports=build_diagnostics_ports())
            document = repair_report_document(report, resolve_action=self._resolve_action)
        return _reply_with(exchange, RuntimeRepairReportReply, document)

    def logs(self, request: RuntimeRepairLogsRequest, exchange: InstallationActExchange, /) -> RuntimeRepairLogsReply:
        """Return the configured log file's path and its most recent lines."""
        with _served_root(exchange):
            tail = read_log_tail(request.lines)
        return _reply_with(exchange, RuntimeRepairLogsReply, tail)

    def profile(
        self, request: RuntimeRepairProfileRequest, exchange: InstallationActExchange, /
    ) -> RuntimeRepairProfileReply:
        """Inspect one named profile's record, or assess and repair the active-profile pointer.

        A pointer repair that names a profile other than the active one, and
        a request to clear the pointer without confirming it, are refused with
        the refusal the command gives. A confirmed clear runs only after the
        login is reobserved; a request that asks for no clear reports the
        pointer's health and changes nothing.
        """
        from ...application.workflow.profile_health import repair_active_profile_pointer
        from ...application.workflow.profile_repair import (
            inspect_profile_record,
            pointer_repair_refusal,
            resolve_repair_profile,
        )
        from ...domain.calculations.registry.authority import bundled_indexed_authority

        with _profile_stores(exchange, repairs_pointer=True):
            pointer = None if request.profile is None else resolve_repair_profile(request.profile)
            if pointer is not None and not request.clear_active:
                inspection = inspect_profile_record(pointer, read_profile_record=read_session_profile_record)
                document = profile_record_document(inspection, resolve_action=self._resolve_action)
                return _reply_with(exchange, RuntimeRepairProfileReply, document)
            named = None if request.profile is None or pointer is None else (request.profile, pointer)
            refusal = pointer_repair_refusal(named, clear_active=request.clear_active, confirmed=request.confirmed)
            if refusal is not None:
                raise refusal.recorded()
            if request.clear_active:
                exchange.require_login()
                exchange.changes_begin()
            with bundled_indexed_authority().operation() as operation:
                result = repair_active_profile_pointer(
                    clear_active=request.clear_active, confirmed=request.confirmed, operation=operation
                )
            document = profile_pointer_repair_document(result, resolve_action=self._resolve_action)
        return _reply_with(exchange, RuntimeRepairProfileReply, document)


def register_repair_acts(
    registry: InstallationActRegistry,
    *,
    resolve_action: PreconditionActionResolver = resolve_recorded_precondition_action,
) -> None:
    """Serve the three repair acts from ``registry``.

    ``resolve_action`` names the command a verdict's recovery action targets.
    The runtime holds no command graph, so it resolves against the recorded
    action targets, which name the command the command line names.
    """
    acts = _RepairActs(resolve_action)
    registry.register(RuntimeRepairReportRequest, acts.report)
    registry.register(RuntimeRepairLogsRequest, acts.logs)
    registry.register(RuntimeRepairProfileRequest, acts.profile)
