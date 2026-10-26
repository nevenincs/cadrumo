"""Bind installed income-tax operation controls to the canonical public lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .tui_contracts import InstalledTuiContract, TuiJourneyError, TuiOperationBinding
from .tui_selectors import _REVIEW_APPLY, WORKBENCH_AT_RISK_PROCEED, WORKBENCH_LIST, WORKBENCH_NOTICE

if TYPE_CHECKING:
    pass


def installed_lifecycle_contract(
    *,
    profile_selection_id: str | None = None,
    ledger_capture_id: str | None = None,
    invoice_link_id: str | None = None,
    work_create_id: str | None = None,
) -> InstalledTuiContract:
    """Return the current public lifecycle controls plus unresolved entry controls.

    The caller must still supply actual profile, ledger, and calendar controls.
    Leaving them absent causes a blocked receipt, which prevents lifecycle
    wiring from being misreported as a complete TUI-only journey.

    Every lifecycle action runs in the declaration's workbench, opened from
    the Declarations list: ``c`` calculates, ``F8`` runs the verification or
    the recording of the filing the next-step line offers (recording through
    its confirmation dialog), the export dialog opened with ``e`` submits the
    export, and the review opened with ``R`` applies staged changes.
    """
    modal_terminal = "#operation-modal-status"
    return InstalledTuiContract(
        profile_selection_id=profile_selection_id,
        ledger_capture_id=ledger_capture_id,
        invoice_link_id=invoice_link_id,
        work_create_id=work_create_id,
        work_open_id="#declarations-list",
        calculate=TuiOperationBinding(
            "modelo.work.calculate",
            activation_key="c",
            at_risk_proceed_id=WORKBENCH_AT_RISK_PROCEED,
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        verify=TuiOperationBinding(
            "modelo.work.verify",
            activation_key="f8",
            offered_step="verify",
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        local_file=TuiOperationBinding(
            "modelo.work.file",
            activation_key="f8",
            offered_step="record",
            confirmation_id="#btn-confirm-accept",
            confirmation_required=True,
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        export=TuiOperationBinding(
            "modelo.export",
            activation_id="#export-submit",
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        apply=TuiOperationBinding(
            "modelo.edit.apply",
            activation_id=_REVIEW_APPLY,
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
    )


def _require_operation_binding(binding: TuiOperationBinding) -> None:
    """Refuse to drive an incomplete or ambiguous public control contract."""
    missing = binding.missing(label=binding.operation_id)
    if missing:
        raise TuiJourneyError(f"installed TUI operation contract is incomplete: {', '.join(missing)}")
    if binding.activation_key is not None and binding.activation_id is not None:
        raise TuiJourneyError(f"{binding.operation_id} names both a key and a control to activate it")
