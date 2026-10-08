"""Profile schema tables and context rendering for the profile manager."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.dom import DOMNode
from textual.widgets import Button, DataTable, Static

from ....application.user_profile.acquisition_sources import (
    ProfileAcquisitionSourceKey,
    known_profile_acquisition_sources,
)
from ....application.user_profile.presentation import notice_presentation
from ....core.i18n.render import tr
from ....core.text_fold import fold_for_matching
from ....domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ..components.widgets import (
    ContentDataTable,
    CredentialRequirement,
    DisclosureGroup,
    NoticeBand,
    RequirementStatus,
    SourceActionCard,
    SourceActionDescriptor,
)
from .overview_contracts import (
    _ABSENT_GLYPH,
    _COMPLETE_SETUP_KEY,
    _DOCUMENT_READER_CARD_ID,
    _FIELD_COLUMN_WIDTH,
    _LANGUAGE_ACTION,
    _LANGUAGE_KEY,
    _PLANTILLA_MEDIA_BUTTON_ID,
    _PLANTILLA_MEDIA_SECTION,
    _PRESENT_GLYPH,
    _REQUIRED_MARK,
    _ROW_INDEX_SEPARATOR,
    _SOURCE_ACTION_LOCALE_KEYS,
    _SOURCE_DESCRIPTION_LOCALE_KEYS,
    _SOURCE_TITLE_LOCALE_KEYS,
)
from .setup_journey import ProfileSetupStage

if TYPE_CHECKING:
    from ....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
    from .overview import ProfileManagerScreen


class ProfileOverviewRenderingMixin:
    """Implement profile schema tables and context rendering for the profile manager."""

    def _source_cards(self: ProfileManagerScreen) -> list[SourceActionCard]:
        """Build one card per known source, worded in the page's current language."""
        return [
            SourceActionCard(
                SourceActionDescriptor(
                    title=tr(_SOURCE_TITLE_LOCALE_KEYS[source.key]),
                    description=tr(_SOURCE_DESCRIPTION_LOCALE_KEYS[source.key]),
                    action_label=tr(_SOURCE_ACTION_LOCALE_KEYS[source.key]),
                    credential_requirement=self._credential_requirement_badge(source.key),
                ),
                id=f"source-{source.key.value}",
            )
            for source in known_profile_acquisition_sources()
        ]

    def _credential_requirement_badge(
        self: ProfileManagerScreen, key: ProfileAcquisitionSourceKey
    ) -> CredentialRequirement | None:
        """Resolve one source's credential badge from its real posture, if supplied.

        Returns the label and status as ONE record so a caller cannot pass
        half of a requirement: the absence of a fact and a fact are the only
        two outcomes this can have.
        """
        posture = self._credential_postures.get(key)
        if posture is None or not posture.requires_aeat_authentication:
            return None
        if posture.credential_held:
            return CredentialRequirement(
                tr("profile.journey.source.credential_requirement.held"), RequirementStatus.REQUIRED_PRESENT
            )
        return CredentialRequirement(
            tr("profile.journey.source.credential_requirement.missing"), RequirementStatus.REQUIRED_MISSING
        )

    def _sync_source_actions(self: ProfileManagerScreen) -> None:
        """Hide a launch button with no door, and disable one whose credential is missing.

        With no door the button could only ever refuse, so it is not shown;
        the card stays, so the source is still named and described. A missing
        credential disables a wired button instead of hiding it: that is
        something the operator can fix, and the card's badge says what.
        """
        door_ready = self._launch_source is not None
        if self._onboarding and self._setup_stage is not ProfileSetupStage.GET_DATA:
            return
        for source in known_profile_acquisition_sources():
            posture = self._credential_postures.get(source.key)
            credential_ready = posture is None or not posture.requires_aeat_authentication or posture.credential_held
            button = self.query_one(f"#source-{source.key.value}", SourceActionCard).query_one(Button)
            button.display = door_ready
            button.disabled = not (door_ready and credential_ready)

    async def _redraw(self: ProfileManagerScreen) -> None:
        """Rebuild the profile context and every schema section table.

        This is the wholesale redraw: it destroys and remounts every table.
        It is what ``on_mount`` needs, and what an action returning a fresh
        overview needs, because either can hand the page a structurally
        different profile. A single-field edit goes through
        :meth:`_apply_overview` instead, which repaints only the cells whose
        content actually moved — the same page, at a fraction of the work.
        """
        async with self._render_lock:
            await self._redraw_now()

    async def _redraw_now(self: ProfileManagerScreen) -> None:
        """The wholesale redraw, for a caller already holding the render lock."""
        self._render_chrome()
        self.refresh_account_chrome()
        self._clear_notice()
        await self._render_profile_context()
        sources = self.query_one("#manager-sources", Vertical)
        await sources.remove_children()
        showing_sources = not self._onboarding or self._setup_stage is ProfileSetupStage.GET_DATA
        if showing_sources:
            await sources.mount_all(self._source_cards())
        if showing_sources and self._open_document_reader is not None:
            await sources.mount(
                SourceActionCard(
                    SourceActionDescriptor(
                        title=tr("tui.local_reader.card.title"),
                        description=tr("tui.local_reader.card.description"),
                        action_label=tr("tui.local_reader.card.action"),
                    ),
                    id=_DOCUMENT_READER_CARD_ID,
                )
            )
        self._sync_source_actions()
        await self._render_sections()
        self._render_onboarding()

    async def _render_sections(self: ProfileManagerScreen, *, disclose_matches: bool = False) -> None:
        """Rebuild each visible section while yielding between tables."""
        self._field_by_key.clear()
        self._table_by_section.clear()
        self._columns_by_section.clear()
        any_visible = False
        for section in self.overview.sections:
            # One section per loop turn keeps a complete profile responsive.
            await asyncio.sleep(0)
            any_visible = await _render_profile_section(self, section, disclose_matches) or any_visible
        _update_section_search_feedback(self, any_visible)

    def _required_now(self: ProfileManagerScreen, overview: ProfileOverview, field: ProfileFieldView) -> bool:
        """Whether setup requires this row now: missing, or answered and required.

        A repeatable section's template row is marked required but demands
        nothing until the operator adds a row, so it is not counted here;
        the overview's own missing list is the authority on what is owed.
        """
        return field.path in overview.missing_required or (field.required and field.present)

    def _visible_fields(
        self: ProfileManagerScreen, overview: ProfileOverview, section: ProfileSectionView
    ) -> tuple[ProfileFieldView, ...]:
        """The section's rows that the required-only switch and the search leave in view."""
        return _visible_profile_fields(self, overview, section)

    def _fold_title(self: ProfileManagerScreen, overview: ProfileOverview, section: ProfileSectionView) -> str:
        """Title a section's fold with how much setup still needs from it.

        A glyph as well as words, so the state reads without colour.
        """
        missing = sum(1 for field in section.fields if field.path in overview.missing_required)
        if missing:
            return tr("flows.manager.onboarding.section_pending", title=section.title, missing=missing)
        if any(self._required_now(overview, field) for field in section.fields):
            if self._onboarding:
                return f"✓ {section.title} · {tr('flows.manager.setup.required_complete')}"
            return tr(
                "flows.manager.onboarding.section_done",
                title=section.title,
                present=section.present_count,
                total=section.total_count,
            )
        return self._section_title(section)

    async def _apply_overview(self: ProfileManagerScreen, updated: ProfileOverview) -> None:
        """Show ``updated`` by repainting only what differs from the page on screen.

        Most edits leave the row SET alone: the overview is projected by
        walking the profile SCHEMA, so every declared field yields a row
        whether or not it holds a value. What such an edit CAN change is a
        row's rendered content — and not only the edited row's, since the
        write door normalises values and re-derives presence and
        completeness. So rather than assume the edited path is the only thing
        that moved, this diffs the old page against the new one and writes
        exactly the cells that differ: usually one row, occasionally a few,
        never all of them.

        Some edits DO move the row set, because how many rows a repeated
        fact stands for is the record's to say, not the schema's: clearing
        the last leaf of a censal divergence retires its rows, and filling a
        row of a repeatable section can add a group. The same holds for the
        rows the filters leave visible, since an answer can change what is
        required or what a search matches. The structural comparison is what
        makes that safe — the shapes stop matching and this falls back to the
        full rebuild rather than writing into coordinates the new page no
        longer has.
        """
        async with self._render_lock:
            previous = self.overview
            self.overview = updated
            if self._shape_of(previous) != self._shape_of(updated):
                await self._redraw_now()
                return

            self._render_chrome()
            self._clear_notice()
            await self._render_profile_context()
            for was, now in zip(previous.sections, updated.sections, strict=True):
                table = self._table_by_section.get(now.key)
                columns = self._columns_by_section.get(now.key)
                if table is None or columns is None:
                    # The page was never fully rendered, so there are no cells to
                    # address. Build it rather than silently dropping the update.
                    await self._redraw_now()
                    return
                self.query_one(f"#fold-{now.key}", DisclosureGroup).title = self._fold_title(updated, now)
                for after in now.fields:
                    self._field_by_key[after.path] = after
                for before, after in zip(
                    self._visible_fields(previous, was), self._visible_fields(updated, now), strict=True
                ):
                    old_cells = self._rendered_row(before)
                    new_cells = self._rendered_row(after)
                    if old_cells == new_cells:
                        continue
                    for column, old_cell, new_cell in zip(columns, old_cells, new_cells, strict=True):
                        if old_cell != new_cell:
                            # ``update_width`` defaults off, which would clip a value
                            # that grew past the column's current width — the full
                            # rebuild sizes columns as it adds rows, and this is the
                            # equivalent for a cell written in place.
                            table.update_cell(after.path, column, new_cell, update_width=True)
            self._render_onboarding()

    async def _render_profile_context(self: ProfileManagerScreen) -> None:
        """Render actionable profile context in the scrollable page body."""
        requirements = _profile_requirement_text(self)
        await _mount_profile_context(self, requirements)

    @staticmethod
    def _section_title(section: ProfileSectionView) -> str:
        """Render one section's border title with its filled-in count."""
        return tr(
            "flows.manager.section_title",
            title=section.title,
            present=section.present_count,
            total=section.total_count,
        )

    @staticmethod
    def _rendered_row(field: ProfileFieldView) -> tuple[str, str, str]:
        """The three cells a field occupies, as the single authority on both paths.

        The full rebuild and the incremental update must agree on what a row
        looks like, or an edited row would drift from its unedited siblings.
        Deriving both from here is what makes the diff comparison meaningful:
        it compares exactly the strings that get written.

        A row belonging to one instance of a repeated fact is named by that
        instance. The projection states which instance as data and leaves
        the presentation here, so the schema's translated label is never
        edited to carry it.
        """
        label = f"{field.label}{_REQUIRED_MARK}" if field.required else field.label
        if field.row_index is not None:
            label = f"{field.row_index}{_ROW_INDEX_SEPARATOR}{label}"
        value = field.value or ""
        if value and field.choices:
            value = next(
                (choice.label for choice in field.choices if choice.value == value),
                tr("flows.manager.choice_unavailable"),
            )
        return (
            _PRESENT_GLYPH if field.present else _ABSENT_GLYPH,
            label,
            value,
        )

    def _shape_of(self: ProfileManagerScreen, overview: ProfileOverview) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The page's row layout: section keys, each with its visible field paths in order.

        Two overviews sharing a shape address the same cells, which is the
        precondition for updating one in place from the other.
        """
        return tuple(
            (section.key, tuple(field.path for field in self._visible_fields(overview, section)))
            for section in overview.sections
        )

    def _render_chrome(self: ProfileManagerScreen) -> None:
        """Resolve all manager-owned chrome under the active output language."""
        title = tr("flows.manager.title", profile=self.overview.label)
        self.title = title
        self.sub_title = ""
        self.query_one("#manager-banner", Static).update(title)
        self._offer_language_in_footer()

    def _language_field(self: ProfileManagerScreen) -> ProfileFieldView | None:
        """The field holding the page's language, if the schema declares one.

        Read from the overview rather than the rendered row index because
        the chrome is written before the tables are rebuilt, and because
        the footer and the chooser must agree on whether there is anywhere
        to put an answer.
        """
        for section in self.overview.sections:
            for field in section.fields:
                if field.path == PROFILE_OUTPUT_LANGUAGE_PATH:
                    return field
        return None

    def _offer_language_in_footer(self: ProfileManagerScreen) -> None:
        """Name the language key in the footer, in the language now on screen.

        The binding declares itself shown, but Textual forces ``show`` off
        for a binding carrying no description, so the one key meant to be
        visible was bound and invisible — and an invisible key is exactly
        the reachability it exists to provide. The description cannot be
        declared beside the binding either: a class body runs once at
        import, so the footer would name the setting in whichever language
        the process started in, on a page the operator has just switched
        away from it.

        So the entry is composed here, from the field's own label, and
        recomposed by every render. The key is offered only while the
        schema declares somewhere to put the answer; advertising it
        otherwise would promise a chooser that could only refuse.

        The key's entry is replaced rather than added to, and replaced by
        assignment rather than edited in place. Textual's own ``bind`` and
        ``BindingsMap.merge`` both append, and this runs on every redraw,
        so either would show the key once more each time the page was
        rebuilt. The instance's binding table is a shallow copy of the
        class's, sharing the very lists it holds, so editing one in place
        would re-describe the key for every manager the process opens;
        putting a new list in this instance's table cannot.
        """
        field = self._language_field()
        # The short account name rather than the field's own label, so the
        # footer keeps every key on an eighty-column terminal.
        label = tr("tui.root.account_key.language") if field is not None else ""
        bindings = self._bindings.key_to_bindings.get(_LANGUAGE_KEY)
        if bindings is None:
            return
        self._bindings.key_to_bindings[_LANGUAGE_KEY] = [
            replace(binding, description=label, show=bool(label)) if binding.action == _LANGUAGE_ACTION else binding
            for binding in bindings
        ]
        self.refresh_bindings()

    def _section_table(self: ProfileManagerScreen, widget: DOMNode | None) -> DataTable[str] | None:
        """Resolve a table event to the typed section table this screen owns."""
        return next((table for table in self._table_by_section.values() if table is widget), None)


async def _render_profile_section(
    screen: ProfileManagerScreen, section: ProfileSectionView, disclose_matches: bool
) -> bool:
    """Refresh one section's fold and mount its visible rows and controls."""
    visible = screen._visible_fields(screen.overview, section)
    fold = screen.query_one(f"#fold-{section.key}", DisclosureGroup)
    fold.title = screen._fold_title(screen.overview, section)
    fold.display = bool(visible)
    if disclose_matches and visible:
        fold.collapsed = False
    screen.query_one(f"#summary-{section.key}", Static).update(section.summary)
    panel = screen.query_one(f"#section-{section.key}", Static)
    await panel.remove_children()
    for field in section.fields:
        screen._field_by_key[field.path] = field
    if not visible:
        return False
    await _mount_profile_section_table(screen, panel, section, visible)
    await _mount_profile_section_actions(screen, panel, section)
    return True


async def _mount_profile_section_table(
    screen: ProfileManagerScreen,
    panel: Static,
    section: ProfileSectionView,
    visible: tuple[ProfileFieldView, ...],
) -> None:
    """Mount one table with the same stable keys and cell widths as a full redraw."""
    table: DataTable[str] = ContentDataTable[str](cursor_type="row", zebra_stripes=True)
    await panel.mount(table)
    screen._table_by_section[section.key] = table
    screen._columns_by_section[section.key] = [
        table.add_column(tr("flows.manager.column.state")),
        table.add_column(tr("flows.manager.column.field"), width=_FIELD_COLUMN_WIDTH),
        table.add_column(tr("flows.manager.column.value")),
    ]
    for field in visible:
        # ``height=None`` wraps long labels in the capped field column instead
        # of pushing the value column outside the viewport.
        table.add_row(*screen._rendered_row(field), key=field.path, height=None)


async def _mount_profile_section_actions(
    screen: ProfileManagerScreen, panel: Static, section: ProfileSectionView
) -> None:
    """Mount only the actions declared for this repeatable or indexed section."""
    if section.repeatable:
        await panel.mount(Button(tr("flows.manager.rows.add"), id=f"manager-add-row-{section.key}", compact=True))
        if screen._has_existing_row(section):
            await panel.mount(
                Button(tr("flows.manager.rows.remove"), id=f"manager-remove-row-{section.key}", compact=True)
            )
    if section.key == _PLANTILLA_MEDIA_SECTION and screen._plantilla_media_offered:
        # Average-workforce years are indexed records, not repeatable section rows.
        await panel.mount(
            Button(
                tr("profile.schema.field.irpf.plantilla_media.label"),
                id=_PLANTILLA_MEDIA_BUTTON_ID,
                compact=True,
            )
        )


def _update_section_search_feedback(screen: ProfileManagerScreen, any_visible: bool) -> None:
    """Keep source actions and the empty-search explanation consistent with filters."""
    searching = bool(screen._query.strip())
    screen.query_one("#manager-sources-fold", DisclosureGroup).display = not searching and (
        not screen._onboarding or screen._setup_stage is ProfileSetupStage.GET_DATA
    )
    empty = screen.query_one("#manager-search-empty", Static)
    empty.display = searching and not any_visible
    if empty.display:
        empty.update(tr("flows.manager.onboarding.search_empty", query=screen._query.strip()))


def _visible_profile_fields(
    screen: ProfileManagerScreen, overview: ProfileOverview, section: ProfileSectionView
) -> tuple[ProfileFieldView, ...]:
    """Apply stage, required-only, then section-aware text filtering in the established order."""
    if screen._onboarding and screen._setup_stage not in {ProfileSetupStage.REQUIRED, ProfileSetupStage.REVIEW}:
        return ()
    fields = section.fields
    if screen._required_only:
        fields = tuple(field for field in fields if screen._required_now(overview, field))
    query = fold_for_matching(screen._query)
    if not query or _query_matches_section(query, section):
        return fields
    return tuple(field for field in fields if _query_matches_field(screen, query, field))


def _query_matches_section(query: str, section: ProfileSectionView) -> bool:
    """A section title or summary match keeps the section's full row set visible."""
    return query in fold_for_matching(section.title) or query in fold_for_matching(section.summary)


def _query_matches_field(screen: ProfileManagerScreen, query: str, field: ProfileFieldView) -> bool:
    """Match the normalized query against the path and rendered row wording."""
    return query in fold_for_matching(" ".join((field.path, *screen._rendered_row(field)[1:])))


def _profile_requirement_text(screen: ProfileManagerScreen) -> str:
    """Describe missing requirements that have no projected field row."""
    missing_fields = screen.overview.missing_required_fields
    resolved_paths = {field.path for field in missing_fields}
    missing_labels = [field.label for field in missing_fields]
    missing_labels.extend(
        tr("flows.manager.required_field_unavailable")
        for path in screen.overview.missing_required
        if path not in resolved_paths
    )
    return (
        tr(
            "flows.manager.profile_missing_fields",
            count=len(screen.overview.missing_required),
            fields=", ".join(missing_labels),
        )
        if screen.overview.missing_required and not screen._onboarding
        else ""
    )


async def _mount_profile_context(screen: ProfileManagerScreen, requirements: str) -> None:
    """Replace the profile context with requirements, completion, and notices."""
    context = screen.query_one("#manager-context", Vertical)
    await context.remove_children()
    if requirements:
        await context.mount(
            Static(requirements, id="manager-requirements", classes="cadrumo-note", markup=False),
        )
    if screen._completion_offered and not screen._onboarding:
        # Continue completes the setup walk itself, so it needs no duplicate button.
        await context.mount(
            Button(
                tr("flows.manager.complete_setup.button", key=_COMPLETE_SETUP_KEY.upper()),
                id="manager-complete-setup",
                compact=True,
            )
        )
    if screen.overview.notices:
        await context.mount(
            NoticeBand(
                tuple(notice_presentation(notice) for notice in screen.overview.notices),
                id="manager-notice-band",
            )
        )
