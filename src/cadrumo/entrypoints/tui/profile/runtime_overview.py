"""Rebuild the TUI profile overview from one complete native runtime view."""

from __future__ import annotations

from ....adapters.local_runtime.frontend_client import ProfileViewCollection, RuntimeFrontendClient
from ....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from ....application.user_profile.view_operation import (
    ProfileViewFieldItem,
    ProfileViewItem,
    ProfileViewMissingItem,
    ProfileViewNoticeItem,
    ProfileViewPageKind,
    ProfileViewSectionItem,
)
from ....core.external_constants import OutputLanguage
from ....core.json_contract import Notice


def profile_overview_from_runtime_view(collection: ProfileViewCollection, *, profile_label: str) -> ProfileOverview:
    """Reassemble the canonical overview stream without consulting local custody."""
    if collection.page_kinds != (ProfileViewPageKind.OVERVIEW,):
        raise ValueError("a complete overview stream is required")
    pages = collection.pages
    if not pages:
        raise ValueError("overview stream has no pages")
    cursor = 0
    total_items = pages[0].total_items
    items: list[ProfileViewItem] = []
    for page in pages:
        if (
            page.page_kind is not ProfileViewPageKind.OVERVIEW
            or page.outcome != "page"
            or page.profile_id != collection.profile_id
            or page.record_revision != collection.record_revision
            or page.content_digest != collection.content_digest
            or page.setup_state is not collection.setup_state
            or page.schema_version != collection.schema_version
            or page.valid != collection.valid
            or page.cursor != cursor
            or page.total_items != total_items
        ):
            raise ValueError("overview page does not match its collected stream")
        items.extend(page.items)
        cursor += len(page.items)
        if page.next_cursor != (cursor if cursor < total_items else None):
            raise ValueError("overview page has a broken continuation")
    if cursor != total_items:
        raise ValueError("overview stream is incomplete")

    sections: list[ProfileSectionView] = []
    current: ProfileViewSectionItem | None = None
    fields: list[ProfileFieldView] = []
    paths: set[str] = set()
    section_keys: set[str] = set()
    missing: list[str] = []
    notices: list[Notice] = []
    phase = "sections"

    def append_section() -> None:
        if current is not None:
            sections.append(
                ProfileSectionView(
                    key=current.key,
                    title=current.title,
                    summary=current.summary,
                    repeatable=current.repeatable,
                    fields=tuple(fields),
                )
            )

    for item in items:
        if isinstance(item, ProfileViewSectionItem):
            if phase != "sections" or item.key in section_keys:
                raise ValueError("overview section order or identity is invalid")
            append_section()
            current = item
            fields = []
            section_keys.add(item.key)
        elif isinstance(item, ProfileViewFieldItem):
            if (
                phase != "sections"
                or current is None
                or item.section_key != current.key
                or not item.field.path.startswith(f"{current.key}.")
                or item.field.path in paths
            ):
                raise ValueError("overview field is outside its section or repeated")
            fields.append(item.field)
            paths.add(item.field.path)
        elif isinstance(item, ProfileViewMissingItem):
            if current is None or phase == "notices" or item.path in missing:
                raise ValueError("overview missing-path order or identity is invalid")
            phase = "missing"
            missing.append(item.path)
        elif isinstance(item, ProfileViewNoticeItem):
            if current is None:
                raise ValueError("overview notice precedes every section")
            phase = "notices"
            context = None if item.context is None else {entry.key: entry.value for entry in item.context}
            if item.context is not None and context is not None and len(context) != len(item.context):
                raise ValueError("overview notice context repeats a key")
            notices.append(Notice(severity=item.severity, code=item.code, message=item.message, context=context))
        else:
            raise ValueError("overview stream contains another item kind")
    append_section()
    if not sections or any(path not in paths for path in missing):
        raise ValueError("overview is missing a section or required field path")
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
