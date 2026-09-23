"""The ``modelo.workspace.overview`` read destination.

The frame for one admitted session: which workspace this is, what state it
is in, and what the producers say can be done with it. Everything shown is
copied from the projection; this screen resolves nothing and classifies
nothing.

Everything on the page leads with the operator's words: dispositions,
assertions, review status and work state are named, never shown as their
transport tokens. Producer attribution and raw identifiers -- the work unit,
the law-selected revision, each capability's ``owner.producer`` -- stay
reachable in a collapsed technical-details group, because they answer
"which code said so", not "what does this mean for me".

Two disclosures carry the destination's honesty and are worth stating
plainly, because both are places where rendering the obvious thing would
assert something untrue.

The REVISION block shows coordinates, never a chronology. Workspace V1
exposes one law-selected revision plus two independently evaluated point
assertions; it has no sequence over time, so a screen presenting a timeline
would author a temporal claim no producer made.

The ACTIONS line says in one plain sentence that this page suggests no
next steps yet, rather than rendering an empty list. An empty actions panel reads as "there is nothing
you can do"; the truth is "this producer does not say what you can do".
Those are different claims, and only the second is true --
:class:`ModeloWorkspaceCapabilityV1` and the refusal types declare
``recovery_action`` and no producer populates it, while the surrounding
application layer attaches ``ActionReference`` to comparable verdicts
routinely. So the silence here is an omission upstream, not an absence of
actions in the system, and the screen must not convert one into the other.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.modelo.edit_models import (
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.operations import OperationTerminalCondition
from .....core.payment_election import PaymentElection
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from ...components.account_chrome import AccountChromeScreen
from ...components.app_access import TypedAppAccess
from ...components.dialogs import ConfirmScreen
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from ...operations.controller import OperationController
from ...operations.refusal_explanation import public_refusal_explanation
from ..m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission
from .controller import ModeloWorkspaceReadSession
from .models import (
    assertion_label,
    capability_label,
    capability_row,
    disposition_label,
    review_status_label,
    work_state_label,
)
from .technical_details import TechnicalDetailRowV1, mount_technical_details, producer_row

if TYPE_CHECKING:
    from .....application.modelo.operation_definitions import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2
    from .models import ModeloWorkspaceDestinationIdV1

_ADDRESS_ROW_KEYS: tuple[str, ...] = ("modelo", "filing_year", "period", "work_state")
_REVISION_ROW_KEYS: tuple[str, ...] = ("requested_assertion", "stored_assertion", "review_status")
_CAPABILITY_COLUMN_KEYS: tuple[str, ...] = ("capability", "disposition")
_OTHER_DESTINATIONS: tuple[str, ...] = ("inputs", "results", "verification", "provenance", "filing")

#: The Modelo 303 export elections, each rendered in the operator's words and
#: pre-set to the same neutral default the command line applies when omitted.
REFUND_ELECTION_LOCALE_KEYS: dict[RefundElection, str] = {
    RefundElection.COMPENSAR: "tui.modelo.export.refund_election.compensar",
    RefundElection.DEVOLVER: "tui.modelo.export.refund_election.devolver",
}
PAYMENT_ELECTION_LOCALE_KEYS: dict[PaymentElection, str] = {
    PaymentElection.INGRESO: "tui.modelo.export.payment_election.ingreso",
    PaymentElection.DOMICILIACION: "tui.modelo.export.payment_election.domiciliacion",
    PaymentElection.CUENTA_CORRIENTE: "tui.modelo.export.payment_election.cuenta_corriente",
}
PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS: dict[PriorDomiciliationElection, str] = {
    PriorDomiciliationElection.KEEP: "tui.modelo.export.prior_domiciliation_election.keep",
    PriorDomiciliationElection.CANCEL_OR_MODIFY: "tui.modelo.export.prior_domiciliation_election.cancel_or_modify",
}


def edit_control_id(kind: str, key: str) -> str:
    """Encode one registry edit key as a Textual widget id, one-to-one.

    Semantic casilla ids such as ``iva.prorrata-volumen-con-derecho`` contain
    characters a widget id may not, and one invalid id stops the whole screen
    from composing. ASCII letters, digits and ``-`` pass through unchanged, so
    numeric and hyphenated ids keep their spelling. Every other character,
    including ``_`` itself, becomes ``_<hex>_``; because a literal ``_`` is
    always escaped, every ``_`` in the result opens or closes an escape and
    distinct keys can never produce the same id.
    """
    encoded = "".join(
        character if (character.isascii() and character.isalnum()) or character == "-" else f"_{ord(character):x}_"
        for character in key
    )
    return f"modelo-edit-{kind}-{encoded}"


class ModeloWorkspaceOverviewScreen(TypedAppAccess, AccountChromeScreen):
    """Address, revision coordinates, status, and the capability denominator."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_overview", ""),
        Binding("escape", "quit_overview", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination frames."""
        super().__init__(id=id)
        self._session = session
        self._action_in_flight = False

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-overview-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-overview-body", classes="cadrumo-scroll"):
            yield Static(
                tr("tui.modelo.destination.heading"),
                classes="cadrumo-heading cadrumo-heading-lead",
                markup=False,
            )
            yield ContentDataTable[str](id="workspace-overview-destinations", cursor_type="row", zebra_stripes=True)
            yield Static(id="workspace-overview-actions")
            yield Static(id="modelo-lifecycle-notice")
            if self._session.lifecycle_actions is not None:
                edit_baseline = getattr(self._session.lifecycle_actions, "edit_baseline", None)
                if edit_baseline is not None:
                    for entry in edit_baseline.permitted_surface:
                        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1):
                            yield Input(
                                placeholder=tr("tui.modelo.edit.scalar", casilla=entry.casilla_id),
                                id=edit_control_id("scalar", str(entry.casilla_id)),
                                classes="modelo-edit-value",
                            )
                        elif isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
                            yield Input(
                                placeholder=tr("tui.modelo.edit.binding", binding=entry.binding_id),
                                id=edit_control_id("binding", str(entry.binding_id)),
                                classes="modelo-edit-value",
                            )
                    yield Button(tr("tui.modelo.edit.apply"), id="modelo-edit-apply")
                yield Button(tr("application.modelo.lifecycle.calculate"), id="modelo-lifecycle-calculate")
                yield Button(tr("application.modelo.lifecycle.verify"), id="modelo-lifecycle-verify")
                yield Button(tr("application.modelo.lifecycle.file"), id="modelo-lifecycle-file")
                yield Input(
                    placeholder=tr("application.modelo.lifecycle.export_destination_placeholder"),
                    id="modelo-lifecycle-export-path",
                )
                if self._is_m303_calculation():
                    yield from self._compose_export_elections()
                yield Button(tr("application.modelo.lifecycle.export"), id="modelo-lifecycle-export")

    def _compose_export_elections(self) -> ComposeResult:
        """Offer each declaration-shaping export election, pre-set to its neutral default and never blank."""
        for control_id, label_key, keys, default in (
            (
                "modelo-lifecycle-export-refund-election",
                "tui.modelo.export.refund_election.label",
                REFUND_ELECTION_LOCALE_KEYS,
                RefundElection.COMPENSAR,
            ),
            (
                "modelo-lifecycle-export-payment-election",
                "tui.modelo.export.payment_election.label",
                PAYMENT_ELECTION_LOCALE_KEYS,
                PaymentElection.INGRESO,
            ),
            (
                "modelo-lifecycle-export-prior-domiciliation-election",
                "tui.modelo.export.prior_domiciliation_election.label",
                PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS,
                PriorDomiciliationElection.KEEP,
            ),
        ):
            yield Static(tr(label_key), markup=False)
            yield Select[str](
                tuple((tr(key), member.value) for member, key in keys.items()),
                value=default.value,
                allow_blank=False,
                id=control_id,
            )

    def on_mount(self) -> None:
        """Populate the header, the destination list, the disclosure groups, and the action notice."""
        target = self._session.projection.target
        self.query_one("#workspace-overview-header", Static).update(
            tr("flows.modelo_workspace_overview.title", modelo=target.modelo)
        )
        self._mount_destinations()
        self._mount_address()
        self._mount_revision()
        self._mount_capabilities()
        self._mount_actions_disclosure()
        self._mount_technical_details()

    def _mount_destinations(self) -> None:
        """List the declaration's other read pages; this page is the way into them.

        The pages had routes but nothing on screen led to them, so a
        declaration opened on its overview and went no further.
        """
        table = self.query_one("#workspace-overview-destinations", ContentDataTable)
        table.add_column(tr("tui.modelo.destination.column"), key="destination")
        for destination in _OTHER_DESTINATIONS:
            table.add_row(tr(f"tui.modelo.destination.{destination}"), key=f"modelo.workspace.{destination}")
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected page over this one; leaving it returns here."""
        if event.data_table.id != "workspace-overview-destinations" or event.row_key.value is None:
            return
        # Imported here: the route table imports this module for its own page.
        from ..routes import resolve_destination

        destination = cast("ModeloWorkspaceDestinationIdV1", str(event.row_key.value))
        self.app.push_screen(resolve_destination(destination)(self._session))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Run the selected lifecycle operation once through the shared modal."""
        actions = self._session.lifecycle_actions
        if actions is None:
            return
        if event.button.id == "modelo-lifecycle-calculate" and self._is_m303_calculation():
            self._collect_ordinary_m303_evidence()
            return
        method_name = {
            "modelo-edit-apply": "apply_edits",
            "modelo-lifecycle-calculate": "calculate",
            "modelo-lifecycle-verify": "verify",
            "modelo-lifecycle-export": "export",
        }.get(str(event.button.id))
        if event.button.id == "modelo-lifecycle-file":
            self._confirm_local_filing()
            return
        if method_name is None:
            return
        output_path = None
        keyword_arguments: dict[str, object] = {}
        if method_name == "apply_edits":
            baseline = getattr(actions, "edit_baseline", None)
            if baseline is None:
                return
            scalar_values: dict[str, str] = {}
            binding_values: dict[str, str] = {}
            for entry in baseline.permitted_surface:
                if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1):
                    value = self.query_one(f"#{edit_control_id('scalar', str(entry.casilla_id))}", Input).value.strip()
                    if value:
                        scalar_values[str(entry.casilla_id)] = value
                elif isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
                    value = self.query_one(f"#{edit_control_id('binding', str(entry.binding_id))}", Input).value.strip()
                    if value:
                        binding_values[str(entry.binding_id)] = value
            keyword_arguments = {"scalar_values": scalar_values, "binding_values": binding_values}
        if method_name == "export":
            output_path = self.query_one("#modelo-lifecycle-export-path", Input).value.strip()
            if not output_path:
                self._notice(tr("application.modelo.lifecycle.refusal.export_destination_required"))
                return
            keyword_arguments = self._export_elections()
        submit = getattr(actions, method_name, None)
        if submit is None:
            return
        if output_path is not None:
            keyword_arguments["output_path"] = output_path
        self._start_lifecycle_action(submit, keyword_arguments=keyword_arguments)

    def _export_elections(self) -> dict[str, object]:
        """Read the operator's export elections; a modelo that offers none submits the neutral defaults."""
        if not self._is_m303_calculation():
            return {
                "refund_election": RefundElection.COMPENSAR,
                "payment_election": PaymentElection.INGRESO,
                "prior_domiciliation_election": PriorDomiciliationElection.KEEP,
            }
        return {
            "refund_election": RefundElection(
                str(self.query_one("#modelo-lifecycle-export-refund-election", Select).value)
            ),
            "payment_election": PaymentElection(
                str(self.query_one("#modelo-lifecycle-export-payment-election", Select).value)
            ),
            "prior_domiciliation_election": PriorDomiciliationElection(
                str(self.query_one("#modelo-lifecycle-export-prior-domiciliation-election", Select).value)
            ),
        }

    def _is_m303_calculation(self) -> bool:
        """Return whether Calculate must collect the ordinary Modelo 303 evidence form."""
        return str(self._session.projection.target.modelo) == "303"

    def _collect_ordinary_m303_evidence(self) -> None:
        """Open one evidence form bound to the work unit selected on this immutable session."""
        work_unit_id = self._session.projection.target.work_unit_id
        asks_modelo_390 = getattr(self._session.lifecycle_actions, "asks_modelo_390", None)
        if work_unit_id is None:
            return
        if not isinstance(asks_modelo_390, bool):
            self._notice(tr("tui.modelo.m303_evidence.admission_unavailable"))
            return
        self.app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id=str(work_unit_id), asks_modelo_390=asks_modelo_390),
            self._calculate_with_ordinary_m303_evidence,
        )

    def _calculate_with_ordinary_m303_evidence(self, submission: OrdinaryM303FilingEvidenceSubmission | None) -> None:
        """Submit only evidence returned for the same selected work unit, never a stale screen result.

        Cancelling, a changed selection and a missing admission door each end
        with a visible notice and no request: none of them may fall through to
        a calculation that the operator did not complete.
        """
        if submission is None:
            self._notice(tr("tui.modelo.m303_evidence.cancelled"))
            return
        actions = self._session.lifecycle_actions
        target_work_unit_id = self._session.projection.target.work_unit_id
        action_work_unit_id = None if actions is None else getattr(actions, "work_unit_id", None)
        if (
            target_work_unit_id is None
            or str(target_work_unit_id) != submission.work_unit_id
            or str(action_work_unit_id) != submission.work_unit_id
        ):
            self._notice(tr("tui.modelo.m303_evidence.stale_context"))
            return
        calculate = getattr(actions, "calculate", None)
        author = getattr(actions, "author_ordinary_m303_filing_evidence", None)
        existing_evidence = submission.existing_evidence
        observed_at = submission.observed_at
        if not isinstance(calculate, Callable) or (
            existing_evidence is None and (observed_at is None or not isinstance(author, Callable))
        ):
            self._notice(tr("tui.modelo.m303_evidence.admission_unavailable"))
            return
        submit_calculation = cast("Callable[..., Awaitable[OperationController]]", calculate)
        admit_evidence = cast("Callable[..., Awaitable[ModeloWorkCalculateOrdinaryM303EvidenceRequestV2]]", author)

        async def submit() -> OperationController:
            evidence = existing_evidence
            if evidence is None:
                evidence = await admit_evidence(
                    joint_return_elected=submission.joint_return_elected,
                    observed_at=observed_at,
                )
            return await submit_calculation(ordinary_m303_filing_evidence=evidence)

        self._start_lifecycle_action(submit)

    def _confirm_local_filing(self) -> None:
        """Require an explicit acknowledgement before recording a local filing."""

        def closed(confirmed: bool | None) -> None:
            if confirmed:
                actions = self._session.lifecycle_actions
                submit = None if actions is None else getattr(actions, "file", None)
                if isinstance(submit, Callable):
                    self._start_lifecycle_action(cast("Callable[..., Awaitable[OperationController]]", submit))
            else:
                self._notice(tr("application.modelo.lifecycle.file_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("application.modelo.lifecycle.file_confirm_title"),
                message=tr("application.modelo.lifecycle.file_confirm_message"),
                confirm_label=tr("application.modelo.lifecycle.file_confirm_accept"),
                cancel_label=tr("application.modelo.lifecycle.file_confirm_cancel"),
            ),
            closed,
        )

    def _start_lifecycle_action(
        self,
        submit: Callable[..., Awaitable[OperationController]],
        *,
        keyword_arguments: dict[str, object] | None = None,
    ) -> None:
        """Start one action in the exclusive lane so repeated activation cannot submit twice."""
        if self._action_in_flight:
            return
        self._action_in_flight = True
        self.run_worker(
            self._open_lifecycle_modal(submit, keyword_arguments=keyword_arguments or {}),
            group="modelo-lifecycle-action",
            exclusive=True,
        )

    async def _open_lifecycle_modal(
        self,
        submit: Callable[..., Awaitable[OperationController]],
        *,
        keyword_arguments: dict[str, object],
    ) -> None:
        """Submit one public action and expose its exact terminal result in the operation modal."""
        from ...operations.modal import OperationModal

        try:
            controller = await submit(**keyword_arguments)
        except CadrumoError as refusal:
            self._action_in_flight = False
            self._notice(resolve_error_message(refusal))
            return
        except Exception:
            self._action_in_flight = False
            raise
        self.app.push_screen(OperationModal(controller), self._on_lifecycle_operation_settled)

    def _on_lifecycle_operation_settled(self, outcome: object) -> None:
        """Publish the terminal result and refresh only after success."""
        from ...operations.modal import OperationModalSettledOutcomeV1

        self._action_in_flight = False
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        condition = outcome.view_model.projection.terminal_condition
        terminal_copy = (
            None
            if condition is None
            else {
                OperationTerminalCondition.SUCCEEDED: tr("operation.modal.terminal.succeeded"),
                OperationTerminalCondition.REFUSED: tr("operation.modal.terminal.refused"),
                OperationTerminalCondition.FAILED: tr("operation.modal.terminal.failed"),
                OperationTerminalCondition.CANCELLED: tr("operation.modal.terminal.cancelled"),
                OperationTerminalCondition.TIMED_OUT: tr("operation.modal.terminal.timed_out"),
                OperationTerminalCondition.INTERRUPTED: tr("operation.modal.terminal.interrupted"),
            }.get(condition)
        )
        explanation = (
            public_refusal_explanation(outcome.view_model.receipt_ref)
            if outcome.view_model.receipt_kind == "refusal"
            else None
        )
        if terminal_copy is not None:
            self._notice(terminal_copy if explanation is None else f"{terminal_copy}: {explanation}")
        if condition is not OperationTerminalCondition.SUCCEEDED:
            return
        actions = self._session.lifecycle_actions
        refresh = None if actions is None else getattr(actions, "refresh_after_success", None)
        if isinstance(refresh, Callable):
            self.run_worker(self._refresh_after_success(refresh), group="modelo-lifecycle-refresh", exclusive=True)

    async def _refresh_after_success(self, refresh: Callable[[], object]) -> None:
        """Capture one new generation, then return so reopening resolves its persisted state."""
        try:
            await asyncio.to_thread(refresh)
        except CadrumoError as refusal:
            self._notice(resolve_error_message(refusal))
            return
        self.dismiss(None)

    def _notice(self, message: str) -> None:
        """Retain a typed pre-submission refusal on the workspace surface."""
        self.query_one("#modelo-lifecycle-notice", Static).update(message)

    def _mount_address(self) -> None:
        """Disclose the natural coordinate and the work state.

        The work state is optional on the resolved target, so an absent work
        unit renders its own explicit value rather than an empty cell. The
        exact work identity is a raw identifier and sits in the technical
        details.
        """
        target = self._session.projection.target
        absent = tr("flows.modelo_workspace_overview.value.no_work_unit")
        values = {
            "modelo": str(target.modelo),
            "filing_year": str(target.filing_year),
            "period": target.period.registry_token,
            "work_state": absent if target.work_state is None else work_state_label(target.work_state),
        }
        self._mount_label_table("address", _ADDRESS_ROW_KEYS, values)

    def _mount_revision(self) -> None:
        """Disclose the revision COORDINATES, never a chronology.

        The two assertions are shown by their own disposition rather than by
        their value: ``NOT_PRESENT`` is a real answer meaning nobody asserted
        a revision, and showing it as a blank would read as a missing value
        instead of an absent claim.
        """
        target = self._session.projection.target
        values = {
            "requested_assertion": assertion_label(target.requested_revision_assertion.disposition),
            "stored_assertion": assertion_label(target.stored_revision_assertion.disposition),
            "review_status": review_status_label(target.review_status),
        }
        self._mount_label_table("revision", _REVISION_ROW_KEYS, values)

    def _mount_label_table(self, group: str, row_keys: tuple[str, ...], values: dict[str, str]) -> None:
        """Mount one two-column label/value table inside its own disclosure group."""
        body = self.query_one("#workspace-overview-body", ContentScroll)
        table = ContentDataTable[str](id=f"workspace-overview-{group}-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr(f"flows.modelo_workspace_overview.section.{group}"), collapsed=False)
        )
        table.add_column(tr("flows.modelo_workspace_overview.column.field"), key="field")
        table.add_column(tr("flows.modelo_workspace_overview.column.value"), key="value")
        for row_key in row_keys:
            table.add_row(tr(f"flows.modelo_workspace_overview.label.{row_key}"), values[row_key], key=row_key)

    def _mount_capabilities(self) -> None:
        """Mount the complete capability denominator, each row with its own glyph.

        Every capability appears exactly once because the projection
        guarantees it; the screen does not filter to the interesting ones. A
        capability omitted from the display would be indistinguishable from
        one the producer never answered.
        """
        body = self.query_one("#workspace-overview-body", ContentScroll)
        table = ContentDataTable[str](id="workspace-overview-capability-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_overview.section.capabilities"), collapsed=False)
        )
        for column_key in _CAPABILITY_COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_overview.column.{column_key}"), key=column_key)
        for capability in self._session.projection.capabilities:
            row = capability_row(capability)
            table.add_row(
                capability_label(row.capability), disposition_label(row.disposition), key=row.capability.value
            )

    def _mount_actions_disclosure(self) -> None:
        """Say plainly that this page suggests no next steps yet."""
        self.query_one("#workspace-overview-actions", Static).update(
            tr("flows.modelo_workspace_overview.actions_not_carried")
        )

    def _mount_technical_details(self) -> None:
        """Keep the raw identities and producer attribution, collapsed.

        Each capability's producer is listed under the capability's own name,
        so the attribution the table above no longer shows is one key away.
        """
        target = self._session.projection.target
        rows: list[TechnicalDetailRowV1] = [
            (
                "work_unit",
                tr("flows.modelo_workspace_overview.label.work_unit"),
                tr("flows.modelo_workspace_overview.value.no_work_unit")
                if target.work_unit_id is None
                else str(target.work_unit_id),
            ),
            (
                "law_selected",
                tr("flows.modelo_workspace_overview.label.law_selected"),
                str(target.law_selected_revision_id),
            ),
        ]
        rows.extend(producer_row(capability_row(capability)) for capability in self._session.projection.capabilities)
        mount_technical_details(
            self.query_one("#workspace-overview-body", ContentScroll), rows, id="workspace-overview-technical-table"
        )

    def action_quit_overview(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceOverviewScreen", "edit_control_id"]
