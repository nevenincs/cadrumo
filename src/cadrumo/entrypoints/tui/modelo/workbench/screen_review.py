"""Review and issue projection behavior for the Modelo workbench."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from .....application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormField,
    ModeloWorkForm,
    address_key,
    edit_address,
    section_fields,
)
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.logging import get_logger
from .casilla_list import AddressKey
from .ports import ModeloWorkbenchActionsV1, WorkbenchPreflight
from .review import EditReviewScreen, ReviewDecision, ReviewNote, UnattributedBoxes
from .session import Rebase

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchReviewMixin:
    """Own the review behavior for the modelo workbench."""

    def action_review(self: ModeloWorkbenchScreen) -> None:
        """Check every staged change with the application, then open their review."""
        if not self._session.dirty:
            self._notice(tr("tui.modelo.workbench.review.none"))
            return
        self.run_worker(self._open_review, group="workbench-review", exclusive=True)

    async def _open_review(self: ModeloWorkbenchScreen, *, rebased: bool = False) -> None:
        preflight = await self._review_preflight(self._actions)
        if preflight is None or await self._review_is_stale(preflight, rebased):
            return
        self._show_review(preflight)

    async def _review_preflight(
        self: ModeloWorkbenchScreen, actions: ModeloWorkbenchActionsV1 | None
    ) -> WorkbenchPreflight | None:
        if actions is None:
            return WorkbenchPreflight()
        try:
            return await actions.preflight(self._session.payload())
        except CadrumoError as refusal:
            self._notice(resolve_error_message(refusal))
            return None
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench could not check the staged changes: %s",
                type(failure).__qualname__,
                exc_info=True,
            )
            self._notice(tr("tui.modelo.workbench.review.check_failed"))
            return None

    async def _review_is_stale(self: ModeloWorkbenchScreen, preflight: WorkbenchPreflight, rebased: bool) -> bool:
        if preflight.stale:
            if rebased:
                self._notice(tr("tui.modelo.workbench.rebase.still_moving"))
                return True
            if await self._rebase() and self._session.dirty:
                await self._open_review(rebased=True)
            return True
        return False

    def _show_review(self: ModeloWorkbenchScreen, preflight: WorkbenchPreflight) -> None:
        form = self.form
        at_risk = None
        if form is not None and (preflight.operator_entries_unknown or self._entries_unknown(form)):
            staged = frozenset(change.key for change in self._session.changes)
            at_risk = self._unattributed_boxes(form, excluding=staged)
        notes = tuple(
            ReviewNote(box=self._box_of(finding.address), message=finding.message, blocking=finding.blocking)
            for finding in preflight.findings
        )
        self.app.push_screen(
            EditReviewScreen(self._session.changes, notes=notes, at_risk=at_risk, status_line=self._status_line()),
            self._review_closed,
        )

    @staticmethod
    def _entries_unknown(form: ModeloWorkForm) -> bool:
        """Whether the declaration holds a calculation that does not record which values the filer typed."""
        return form.calculation_revision_id is not None and not form.operator_entries_known

    def _unattributed_boxes(
        self: ModeloWorkbenchScreen, form: ModeloWorkForm, *, excluding: frozenset[AddressKey] = frozenset()
    ) -> UnattributedBoxes:
        """The boxes holding a value nobody is recorded as having typed, which a recalculation returns to source.

        Every such box is named, a zero in an optional box as much as an
        assumed value: the question is what applying changes, not what is to
        do. Each carries the heading of the section it sits in, for a list too
        long to name box by box.
        """
        sections = self._section_titles()
        chosen = self._unattributed_fields(form, excluding)
        return UnattributedBoxes(
            boxes=tuple(f"[{field.box}]" if field.box else field.label.text for field in chosen),
            sections=tuple(sections.get(address_key(field.address), "") for field in chosen),
        )

    def _section_titles(self: ModeloWorkbenchScreen) -> dict[AddressKey, str]:
        sections: dict[AddressKey, str] = {}
        for page in self._pages:
            for section in page.sections:
                for field in section_fields(section):
                    sections.setdefault(address_key(field.address), section.heading.text)
            for field in page.fields():
                sections.setdefault(address_key(field.address), page.heading.text)
        return sections

    @staticmethod
    def _unattributed_fields(form: ModeloWorkForm, excluding: frozenset[AddressKey]) -> list[ModeloFormField]:
        return [field for field in form.fields() if field.unattributed and address_key(field.address) not in excluding]

    def _box_of(self: ModeloWorkbenchScreen, address: ModeloFormAddressV1 | None) -> str | None:
        form = self.form
        if address is None or form is None:
            return None
        for field in form.fields():
            if field.address == address or edit_address(field) == address:
                return field.box or field.label.text
        return None

    async def _rebase(self: ModeloWorkbenchScreen) -> bool:
        """Read the declaration again and keep the staged changes that still apply, saying what moved."""
        try:
            load = await asyncio.to_thread(self._reader.load, self._language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench could not read its declaration again: %s", type(failure).__qualname__, exc_info=True
            )
            self._notice(tr("tui.modelo.workbench.read_failed"))
            return False
        outcome = self._session.rebase(load.form)
        self.show_load(load)
        self._notice(self._rebase_text(outcome))
        return True

    @staticmethod
    def _rebase_text(outcome: Rebase) -> str:
        parts = [tr("tui.modelo.workbench.rebase.moved")]
        if outcome.changed:
            parts.append(tr("tui.modelo.workbench.rebase.changed", count=len(outcome.changed)))
        if outcome.dropped:
            parts.append(tr("tui.modelo.workbench.rebase.dropped", count=len(outcome.dropped)))
        return " ".join(parts)

    def _review_closed(self: ModeloWorkbenchScreen, decision: ReviewDecision | None) -> None:
        actions = self._actions
        if decision is ReviewDecision.APPLY and actions is not None:
            self._session.acknowledge()
            changes = self._session.payload()
            self._run_operation(partial(actions.apply, changes), applies_changes=True)
        elif decision is ReviewDecision.DISCARD:
            self._session.discard()
            self._notice(tr("tui.modelo.workbench.review.discarded"))
            self._refresh_after_staging()
