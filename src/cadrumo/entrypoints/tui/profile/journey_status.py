"""Render-only summaries for the five-stage profile journey shell.

Every function here consumes only :class:`~cadrumo.application.user_profile
.presentation.ProfilePresentationV1` -- the settled D6 presentation
projection -- plus the domain's own public label authority
(:func:`~cadrumo.domain.user_profile.labels.profile_field_label`,
:func:`~cadrumo.domain.user_profile.labels.profile_section_title`), the same
resolver :mod:`overview` already uses. This module classifies nothing: every
requirement classification, source class, and readiness fact it renders was
already decided by :func:`~cadrumo.application.user_profile.presentation
.build_profile_presentation`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ....application.user_profile.presentation import (
    ProfileFieldClassification,
    ProfileFieldPresentationV1,
    ProfilePresentationV1,
)
from ....core.i18n._render import tr
from ....domain.user_profile.labels import profile_field_label, profile_section_title
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.schema import ProfileFieldDefinition, ProfileSectionDefinition
from ..components.widgets import DisclosureGroup, RequirementBadge, RequirementStatus

_CLASSIFICATION_STATUS: dict[ProfileFieldClassification, RequirementStatus] = {
    ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING: RequirementStatus.REQUIRED_MISSING,
    ProfileFieldClassification.NEEDS_APPLICABILITY: RequirementStatus.NEEDS_APPLICABILITY,
    ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT: RequirementStatus.REQUIRED_PRESENT,
    ProfileFieldClassification.OPTIONAL: RequirementStatus.OPTIONAL,
    ProfileFieldClassification.NOT_APPLICABLE: RequirementStatus.NOT_APPLICABLE,
}


def _field_label(path: str) -> str:
    """Resolve one field path to its schema-declared, localized label.

    Splits on the same dotted convention :func:`build_profile_presentation`
    emits: ``section.field`` for a static section, or
    ``section.index.field`` for one row of a repeatable section. Falls back
    to the raw path only if the schema does not (or no longer) declare it --
    a defensive floor, never the expected outcome for a valid projection.
    """
    schema = load_user_profile_schema()
    segments = path.split(".")
    section_key = segments[0]
    field_key = segments[-1]
    section: ProfileSectionDefinition | None = next(
        (candidate for candidate in schema.sections if candidate.key == section_key), None
    )
    if section is None:
        return path
    field: ProfileFieldDefinition | None = next(
        (candidate for candidate in section.fields if candidate.key == field_key), None
    )
    if field is None:
        return path
    return f"{profile_section_title(section)} \u2013 {profile_field_label(section_key, field)}"


def _badge(field: ProfileFieldPresentationV1, *, id_prefix: str, index: int) -> RequirementBadge:
    status = _CLASSIFICATION_STATUS[field.classification]
    return RequirementBadge(_field_label(field.path), status, id=f"{id_prefix}-{index}")


def overview_readiness_summary(presentation: ProfilePresentationV1) -> str:
    """Return the smallest next-action-carrying overview readiness line."""
    if presentation.ready:
        return f"{tr('profile.journey.ready.summary')}: \u2713"
    return tr("profile.journey.ready.blocked")


def compose_required_stage(presentation: ProfilePresentationV1) -> Iterator[DisclosureGroup | RequirementBadge]:
    """Yield the `Required` stage body: missing/unassessed expanded, the rest disclosed.

    Mirrors D6's classification table directly: applicable-required-missing
    and needs-applicability rows are expanded by default; present-required
    rows collapse into a completed group; optional and not-applicable rows
    each sit behind their own named disclosure, never silently show.
    """
    missing = presentation.fields_by_classification(ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING)
    needs_applicability = presentation.fields_by_classification(ProfileFieldClassification.NEEDS_APPLICABILITY)
    present = presentation.fields_by_classification(ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT)
    optional = presentation.fields_by_classification(ProfileFieldClassification.OPTIONAL)
    not_applicable = presentation.fields_by_classification(ProfileFieldClassification.NOT_APPLICABLE)

    for index, field in enumerate(needs_applicability):
        yield _badge(field, id_prefix="required-needs-applicability", index=index)
    for index, field in enumerate(missing):
        yield _badge(field, id_prefix="required-missing", index=index)
    if not missing and not needs_applicability:
        yield RequirementBadge(tr("profile.journey.required.none_missing"), RequirementStatus.REQUIRED_PRESENT)

    if present:
        yield DisclosureGroup(
            *(_badge(field, id_prefix="required-present", index=index) for index, field in enumerate(present)),
            title=tr("profile.journey.stage.required"),
            collapsed=True,
            id="required-completed-group",
        )
    if optional:
        yield DisclosureGroup(
            *(_badge(field, id_prefix="required-optional", index=index) for index, field in enumerate(optional)),
            title=tr("profile.journey.required.show_optional"),
            collapsed=True,
            id="required-optional-group",
        )
    if not_applicable:
        not_applicable_badges = (
            _badge(field, id_prefix="required-not-applicable", index=index)
            for index, field in enumerate(not_applicable)
        )
        yield DisclosureGroup(
            *not_applicable_badges,
            title=tr("profile.journey.required.show_not_applicable"),
            collapsed=True,
            id="required-not-applicable-group",
        )


class ReadyStageBody(Vertical, can_focus=False):
    """Render the `Ready` stage: true readiness plus every remaining blocker."""

    def __init__(self, presentation: ProfilePresentationV1, *, id: str | None = None) -> None:
        """Store the settled presentation projection this stage renders from."""
        super().__init__(id=id)
        self._presentation = presentation

    @override
    def compose(self) -> ComposeResult:
        """Render the readiness summary line, then every current blocker as a badge."""
        yield Static(overview_readiness_summary(self._presentation), id="ready-summary", markup=False)
        for index, field in enumerate(self._presentation.blocking_fields):
            yield _badge(field, id_prefix="ready-blocking", index=index)


__all__ = [
    "ReadyStageBody",
    "compose_required_stage",
    "overview_readiness_summary",
]
