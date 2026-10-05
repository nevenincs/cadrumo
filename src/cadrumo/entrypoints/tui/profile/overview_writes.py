"""Profile write lifecycle, worker settlement, and refusal display."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextvars import copy_context
from typing import TYPE_CHECKING, cast

from textual.worker import Worker, WorkerState

from ....core.i18n.render import tr
from ....domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ..components.status import PinnedStatusBar
from .runtime_errors import ProfileManagerCompletedViewUnavailableError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.user_profile.overview import ProfileFieldView, ProfileOverview
    from .overview import ProfileManagerScreen


class ProfileOverviewWriteMixin:
    """Implement profile write lifecycle, worker settlement, and refusal display."""

    def _validator_for(self: ProfileManagerScreen, field: ProfileFieldView) -> Callable[[str], str | None] | None:
        """Bind the injected judge to one field, or ``None`` when there is none.

        The dialog asks about a value; the door asks about a value AT A
        PATH, because what is acceptable is a property of the declaration
        rather than of the string. Binding the path here is what lets the
        dialog stay ignorant of which field it is showing.
        """
        if self._validate_field is None:
            return None
        path = field.path
        return lambda value: self._validate_field(path, value) if self._validate_field is not None else None

    def _apply_edit_for(self: ProfileManagerScreen, field: ProfileFieldView):
        """Build the dismissal callback that persists one field's new value."""
        baseline_revision = self.overview.record_revision
        baseline_digest = self.overview.content_digest

        def _apply(value: str | None) -> None:
            if value is None:
                return
            # A blank submission is a CLEAR downstream, so on a required
            # field it asks to remove something the schema says must be
            # there. Refuse at the box rather than letting the write door
            # raise: dismissing the dialog is how "leave this alone" is
            # expressed, and an empty box is not that.
            if field.required and not value.strip():
                self._refuse(tr("flows.manager.edit.required_blank", field=field.label))
                return
            section = self._section(field.path.split(".", 1)[0])
            if section is not None and section.repeatable:
                row_key = self._row_key_for_field(section, field)
                self._update_repeatable_row(
                    section.key,
                    row_key,
                    {field.path.rsplit(".", 1)[-1]: value.strip()} if value.strip() else {},
                    () if value.strip() else (field.path.rsplit(".", 1)[-1],),
                    baseline_revision,
                    baseline_digest,
                )
                return
            self._persist(field.path, value, baseline_revision, baseline_digest)

        return _apply

    def _persist(
        self: ProfileManagerScreen, path: str, value: str, expected_revision: int, expected_content_digest: str
    ) -> None:
        """Write one field through the injected door, off the event loop.

        The write reaches encrypted storage and takes long enough to be felt.
        Run inline it would block Textual's loop for its whole duration, so
        the page would stop repainting and stop answering keys — the operator
        reads that as a frozen application rather than a slow save. It
        therefore runs on a worker thread, and the page is updated from
        :meth:`on_worker_state_changed` once storage has spoken.

        The context is copied into the thread because the write door resolves
        the active profile bucket from a context variable; a bare thread would
        not see it and every write would fail to find a profile.

        A refusal is reported in the notice line rather than raised, for the
        same reason the action buttons catch: the operator is mid-page and an
        exception would take the whole screen down over one rejected value.
        Because the door now raises on a worker thread, ``exit_on_error`` is
        off so the failure is held on the worker for the UI task to read,
        rather than escaping into the thread and leaving the page silently
        unchanged.
        """
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        write_context = copy_context()

        def _write() -> ProfileOverview:
            written = cast(
                "ProfileOverview | None",
                write_context.run(self._persist_field, path, value, expected_revision, expected_content_digest),
            )
            if written is None:
                # The door declares it hands back the reloaded page, so this
                # is a broken contract rather than a refused value. Raised
                # here it lands on the worker's error and reaches the
                # operator as itself; returned, it would be reported as
                # "could not be saved" — which would be a lie about a write
                # that may well have landed.
                message = "the profile write door returned no overview to render"
                raise TypeError(message)
            return written

        self._pending_write_path = path
        self._pending_write = self.run_worker(
            _write,
            name="profile-field-write",
            group="profile-field-write",
            exit_on_error=False,
            thread=True,
        )

    def _add_repeatable_row(
        self: ProfileManagerScreen,
        section_key: str,
        values: Mapping[str, str] | None,
        expected_revision: int,
        expected_content_digest: str,
    ) -> None:
        """Publish one explicitly requested row against the opened baseline."""
        door = self._add_row
        if values is None or door is None:
            return
        self._run_row_write(
            f"{section_key}:add",
            lambda: door(section_key, values, expected_revision, expected_content_digest),
        )

    def _update_repeatable_row(
        self: ProfileManagerScreen,
        section_key: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        expected_revision: int,
        expected_content_digest: str,
    ) -> None:
        """Modify or explicitly clear the row that supplied the selected field."""
        door = self._update_row
        if door is None:
            return
        self._run_row_write(
            f"{section_key}:{row_key or 'base'}",
            lambda: door(section_key, row_key, values, clear_fields, expected_revision, expected_content_digest),
        )

    def _remove_repeatable_row(
        self: ProfileManagerScreen,
        section_key: str,
        row_key: str,
        expected_revision: int,
        expected_content_digest: str,
        confirmed: bool,
    ) -> None:
        """Clear an identified row only after the confirmation modal affirmed it."""
        door = self._remove_row
        if not confirmed or door is None:
            return
        self._run_row_write(
            f"{section_key}:{row_key or 'base'}",
            lambda: door(section_key, row_key, expected_revision, expected_content_digest),
        )

    def _run_row_write(self: ProfileManagerScreen, identity: str, write: Callable[[], ProfileOverview]) -> None:
        """Run a shared row door once; a duplicate activation cannot start another CAS write."""
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        write_context = copy_context()

        def _write() -> ProfileOverview:
            written = cast("ProfileOverview | None", write_context.run(write))
            if written is None:
                raise TypeError("the profile row write door returned no overview to render")
            return written

        self._pending_write_path = identity
        self._pending_write = self.run_worker(
            _write,
            name="profile-row-write",
            group="profile-field-write",
            exit_on_error=False,
            thread=True,
        )

    async def on_worker_state_changed(self: ProfileManagerScreen, event: Worker.StateChanged) -> None:
        """Land one finished worker back on Textual's UI task.

        Widgets are only safe to touch from this task, so every repaint
        waits until here rather than happening in the worker.
        """
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        event_worker = cast("object", event.worker)
        pending_write = self._pending_write
        if pending_write is not None and event_worker is pending_write:
            await self._settle_write(pending_write)
            return
        pending_completion = self._pending_completion
        if pending_completion is not None and event_worker is pending_completion:
            await self._settle_completion(pending_completion)
            return
        pending_listing = self._pending_listing
        if pending_listing is not None and event_worker is pending_listing:
            self._settle_listing(pending_listing)
            return

    async def _settle_write(self: ProfileManagerScreen, worker: Worker[ProfileOverview]) -> None:
        """Show what storage made of one finished field write."""
        self._pending_write = None
        written_path = self._pending_write_path
        self._pending_write_path = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            if worker.result.profile_id != self.overview.profile_id:
                # A completion for another profile must never repaint this
                # screen. Installed composition captures profile_id, and this
                # guard makes a broken host a refusal rather than a redirect.
                self._refuse(tr("flows.manager.edit.write_failed"))
                return
            if worker.result.record_revision < self.overview.record_revision or (
                worker.result.record_revision == self.overview.record_revision
                and worker.result.content_digest != self.overview.content_digest
            ):
                self._refuse(tr("flows.manager.edit.stale_result"))
                return
            changed = worker.result.record_revision > self.overview.record_revision
            if written_path == PROFILE_OUTPUT_LANGUAGE_PATH:
                # The page is now written in a different language, and the
                # incremental path cannot express that: it repaints the
                # cells whose content moved, while a language switch also
                # moves the column headers and section titles, which are
                # chrome rather than cells. Rebuilding is the only redraw
                # that reaches all of it.
                self.overview = worker.result
                await self._redraw()
                self.query_one("#manager-status", PinnedStatusBar).show_success(
                    tr("flows.manager.edit.saved" if changed else "flows.manager.edit.no_change")
                )
                self._carry_walk_on()
                return
            await self._apply_overview(worker.result)
            self.query_one("#manager-status", PinnedStatusBar).show_success(
                tr("flows.manager.edit.saved" if changed else "flows.manager.edit.no_change")
            )
            self._carry_walk_on()
            return
        self._walking = False
        # A refusal reaches the operator as itself. A cancelled or
        # result-less worker would otherwise leave the page looking as
        # though nothing had been asked of it.
        self._refuse_worker(worker.error, message_key="flows.manager.edit.write_failed")

    def _clear_notice(self: ProfileManagerScreen) -> None:
        """Reset the diagnostic line while preserving its pinned space."""
        self.query_one("#manager-status", PinnedStatusBar).clear_message()

    def _refuse(self: ProfileManagerScreen, message: str) -> None:
        """Show something the page would not do, and why."""
        self.query_one("#manager-status", PinnedStatusBar).show_error(message)

    def _refuse_worker(self: ProfileManagerScreen, error: BaseException | None, *, message_key: str) -> None:
        """Show what a finished worker failed with, never as a blank line.

        ``str(exc)`` is the empty string for any exception constructed
        without arguments, and Textual hands the settling handlers exactly
        that when a worker is cancelled: ``Worker._run`` stores the
        ``asyncio.CancelledError`` it caught, whose text is empty. Rendered
        as itself it reaches the operator as an error-styled line with
        nothing written on it, which says less than saying nothing.

        The fallback therefore turns on the rendered text being empty
        rather than on the exception's type, because no type owns that
        emptiness — a door that raises bare renders just as blank.
        """
        if isinstance(error, ProfileManagerCompletedViewUnavailableError):
            self._refuse(tr("flows.manager.edit.completed_refresh_unavailable"))
            return
        if error is None:
            rendered = ""
        else:
            from ....application.user_profile.capsule_record import ProfileRecordConflictError
            from ....core.errors.error_codes import resolve_error_message
            from ....core.errors.hierarchy import CadrumoError

            if isinstance(error, ProfileRecordConflictError):
                rendered = tr("errors.fail.fail_storage_secure_object_revision_conflict")
            else:
                rendered = resolve_error_message(error) if isinstance(error, CadrumoError) else ""
        self._refuse(rendered or tr(message_key))
