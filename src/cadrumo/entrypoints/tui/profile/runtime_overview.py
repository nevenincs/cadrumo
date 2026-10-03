"""Rebuild the TUI profile overview from one complete native runtime view."""

from __future__ import annotations

from dataclasses import dataclass, field

from ....adapters.local_runtime.frontend_client import ProfileViewCollection, RuntimeFrontendClient
from ....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from ....application.user_profile.view_operation import (
    ProfileViewFieldItem,
    ProfileViewItem,
    ProfileViewMissingItem,
    ProfileViewNoticeItem,
    ProfileViewOperationProjection,
    ProfileViewPageKind,
    ProfileViewSectionItem,
)
from ....core.external_constants import OutputLanguage
from ....core.json_contract import Notice


def _collection_items(collection: ProfileViewCollection) -> list[ProfileViewItem]:
    if collection.page_kinds != (ProfileViewPageKind.OVERVIEW,):
        raise ValueError("a complete overview stream is required")
    pages = collection.pages
    if not pages:
        raise ValueError("overview stream has no pages")
    cursor = 0
    total_items = pages[0].total_items
    items: list[ProfileViewItem] = []
    for page in pages:
        if not _page_matches(page, collection, cursor, total_items):
            raise ValueError("overview page does not match its collected stream")
        items.extend(page.items)
        cursor += len(page.items)
        if page.next_cursor != (cursor if cursor < total_items else None):
            raise ValueError("overview page has a broken continuation")
    if cursor != total_items:
        raise ValueError("overview stream is incomplete")
    return items


def _page_matches(
    page: ProfileViewOperationProjection,
    collection: ProfileViewCollection,
    cursor: int,
    total_items: int,
) -> bool:
    same_collection = (
        page.page_kind is ProfileViewPageKind.OVERVIEW
        and page.outcome == "page"
        and page.profile_id == collection.profile_id
        and page.record_revision == collection.record_revision
        and page.content_digest == collection.content_digest
        and page.setup_state is collection.setup_state
        and page.schema_version == collection.schema_version
        and page.valid == collection.valid
    )
    return same_collection and page.cursor == cursor and page.total_items == total_items


@dataclass
class _OverviewAccumulator:
    sections: list[ProfileSectionView] = field(default_factory=list)
    current: ProfileViewSectionItem | None = None
    fields: list[ProfileFieldView] = field(default_factory=list)
    paths: set[str] = field(default_factory=set)
    section_keys: set[str] = field(default_factory=set)
    missing: list[str] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)
    phase: str = "sections"

    def consume(self, item: ProfileViewItem) -> None:
        if isinstance(item, ProfileViewSectionItem):
            self._section(item)
        elif isinstance(item, ProfileViewFieldItem):
            self._field(item)
        elif isinstance(item, ProfileViewMissingItem):
            self._missing(item)
        elif isinstance(item, ProfileViewNoticeItem):
            self._notice(item)
        else:
            raise ValueError("overview stream contains another item kind")

    def finish(self) -> tuple[tuple[ProfileSectionView, ...], tuple[str, ...], tuple[Notice, ...]]:
        self._append_section()
        if not self.sections or any(path not in self.paths for path in self.missing):
            raise ValueError("overview is missing a section or required field path")
        return tuple(self.sections), tuple(self.missing), tuple(self.notices)

    def _append_section(self) -> None:
        if self.current is None:
            return
        self.sections.append(
            ProfileSectionView(
                key=self.current.key,
                title=self.current.title,
                summary=self.current.summary,
                repeatable=self.current.repeatable,
                fields=tuple(self.fields),
            )
        )

    def _section(self, item: ProfileViewSectionItem) -> None:
        if self.phase != "sections" or item.key in self.section_keys:
            raise ValueError("overview section order or identity is invalid")
        self._append_section()
        self.current = item
        self.fields = []
        self.section_keys.add(item.key)

    def _field(self, item: ProfileViewFieldItem) -> None:
        if (
            self.phase != "sections"
            or self.current is None
            or item.section_key != self.current.key
            or not item.field.path.startswith(f"{self.current.key}.")
            or item.field.path in self.paths
        ):
            raise ValueError("overview field is outside its section or repeated")
        self.fields.append(item.field)
        self.paths.add(item.field.path)

    def _missing(self, item: ProfileViewMissingItem) -> None:
        if self.current is None or self.phase == "notices" or item.path in self.missing:
            raise ValueError("overview missing-path order or identity is invalid")
        self.phase = "missing"
        self.missing.append(item.path)

    def _notice(self, item: ProfileViewNoticeItem) -> None:
        if self.current is None:
            raise ValueError("overview notice precedes every section")
        self.phase = "notices"
        context = None if item.context is None else {entry.key: entry.value for entry in item.context}
        if item.context is not None and context is not None and len(context) != len(item.context):
            raise ValueError("overview notice context repeats a key")
        self.notices.append(Notice(severity=item.severity, code=item.code, message=item.message, context=context))


def _profile_sections(
    items: list[ProfileViewItem],
) -> tuple[tuple[ProfileSectionView, ...], tuple[str, ...], tuple[Notice, ...]]:
    overview = _OverviewAccumulator()
    for item in items:
        overview.consume(item)
    return overview.finish()


def profile_overview_from_runtime_view(collection: ProfileViewCollection, *, profile_label: str) -> ProfileOverview:
    """Reassemble the canonical overview stream without consulting local custody."""
    items = _collection_items(collection)
    sections, missing, notices = _profile_sections(items)
    return ProfileOverview(
        profile_id=str(collection.profile_id),
        record_revision=collection.record_revision,
        content_digest=collection.content_digest,
        label=profile_label,
        setup_state=collection.setup_state,
        sections=tuple(sections),
        missing_required=tuple(missing),
        notices=tuple(notices),
    )


def read_runtime_profile_overview(
    client: RuntimeFrontendClient,
    *,
    profile_label: str,
    output_language: OutputLanguage,
    timeout: float = 60,
) -> ProfileOverview:
    """Read only the native overview stream for this already admitted client."""
    collection = client.read_profile_view(
        (ProfileViewPageKind.OVERVIEW,), output_language=output_language, timeout=timeout
    )
    return profile_overview_from_runtime_view(collection, profile_label=profile_label)


__all__ = ["profile_overview_from_runtime_view", "read_runtime_profile_overview"]
