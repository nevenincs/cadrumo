"""The profile overview: what the operator's profile actually contains.

This is the projection behind the profile manager's landing page. It
answers "what do I know about this taxpayer, and what is still blank" by
walking the schema and pairing every declared field with its recorded
value — so a field the operator has not filled in is a visible empty row
rather than an absence they have to infer.

That inversion is the point. The surface this replaces enumerated the
*steps of a setup wizard*: a list of questions with a status glyph, which
told the operator where they were in a process but never what their
profile held. A profile is data, not a process, and the operator should
be looking at the data.

Completeness rides along as a count rather than a gate. Every field is
editable at any time; ``missing_required`` names what filing will
eventually need, so the surface can show progress without ever refusing
to display a profile that is not finished.

Secret-classed values never leave this module in the clear: a masked
field carries :data:`MASKED_PLACEHOLDER` as its value and reports
``masked``, so no caller can render a secret by accident.

See Also:
    :class:`~cadrumo.application.user_profile.ProfilePreflightService`
        Per-modelo requirements; this module reports schema-level
        completeness, which is the broader "is the profile filled in"
        question rather than "can I file THIS modelo".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from ...core.classification import SensitivityClass

# ``UserProfileStatus`` is a pydantic FIELD type below, so it must resolve at
# runtime; deferring it to TYPE_CHECKING leaves the model undefined and every
# construction raises. The rest of the domain surface is annotation-only.
from ...domain.user_profile import UserProfileStatus, load_user_profile_schema

if TYPE_CHECKING:
    from ...domain.user_profile import (
        ProfileSchemaDefinition,
        UserProfileRecord,
    )


MASKED_PLACEHOLDER: Final[str] = "••••••••"
"""Rendered in place of a secret-classed value.

A fixed-width glyph run rather than the value's own length, so the mask
does not leak how long the secret is.
"""

_MASK_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"password", "passphrase", "secret", "token", "key", "credential"},
)
"""Substrings that mark a field secret-shaped even when the schema does
not class it ``SECRET``. Defence in depth: a field added without the
right sensitivity still masks if it is named like a credential."""


class ProfileFieldView(BaseModel):
    """One schema field paired with whatever the profile records for it."""

    model_config = ConfigDict(frozen=True)

    path: str
    label: str
    value: str | None
    masked: bool
    required: bool

    @property
    def present(self) -> bool:
        """Whether the operator has supplied a value for this field."""
        return self.value is not None and self.value != ""


class ProfileSectionView(BaseModel):
    """One schema section and its fields, in declaration order."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    fields: tuple[ProfileFieldView, ...]

    @property
    def present_count(self) -> int:
        return sum(1 for field in self.fields if field.present)

    @property
    def total_count(self) -> int:
        return len(self.fields)


class ProfileOverview(BaseModel):
    """Everything the manager's landing page renders for one profile."""

    model_config = ConfigDict(frozen=True)

    profile_id: str
    label: str
    status: UserProfileStatus
    sections: tuple[ProfileSectionView, ...]
    missing_required: tuple[str, ...] = Field(default=())

    @property
    def present_count(self) -> int:
        return sum(section.present_count for section in self.sections)

    @property
    def total_count(self) -> int:
        return sum(section.total_count for section in self.sections)

    @property
    def complete(self) -> bool:
        """Whether every schema-required field now carries a value.

        Deliberately not "every field": optional detail staying blank is a
        finished profile, not an unfinished one.
        """
        return not self.missing_required


def _mask_field(*, path: str, label: str, sensitivity: SensitivityClass | None) -> bool:
    """Decide whether a value must be masked before it reaches a surface."""
    if sensitivity is SensitivityClass.SECRET:
        return True
    haystack = f"{path} {label}".casefold()
    return any(keyword in haystack for keyword in _MASK_KEYWORDS)


def build_profile_overview(
    record: UserProfileRecord,
    *,
    label: str | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> ProfileOverview:
    """Project ``record`` into the manager's landing-page view.

    The walk is driven by the SCHEMA, not by the record's facts: every
    declared field yields a row whether or not the profile has a value for
    it. A fact-driven walk would render only what is already filled in,
    which is precisely the information the operator does not need — they
    need to see the blanks.

    Args:
        record: The profile whose values populate the view.
        label: Operator-facing display name; falls back to the record's own.
        schema: Optional schema override; the canonical schema when omitted.

    Returns:
        A :class:`ProfileOverview` covering every declared section and field.
    """
    from ._projections import record_to_path_values

    resolved_schema = schema if schema is not None else load_user_profile_schema()
    values = record_to_path_values(record)

    sections: list[ProfileSectionView] = []
    missing_required: list[str] = []
    for section in resolved_schema.sections:
        field_views: list[ProfileFieldView] = []
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            raw = values.get(path)
            masked = _mask_field(path=path, label=field.description, sensitivity=field.sensitivity)
            present = raw is not None and raw != ""
            if field.required and not present:
                missing_required.append(path)
            field_views.append(
                ProfileFieldView(
                    path=path,
                    label=field.description or path,
                    # Mask only a value that exists; masking a blank would
                    # render dots for a field the operator has not filled in
                    # and read as "something is set here".
                    value=MASKED_PLACEHOLDER if (masked and present) else raw,
                    masked=masked,
                    required=field.required,
                ),
            )
        sections.append(
            ProfileSectionView(key=section.key, title=section.title, fields=tuple(field_views)),
        )

    return ProfileOverview(
        profile_id=record.profile_id,
        label=label if label is not None else record.display_name,
        status=record.status,
        sections=tuple(sections),
        missing_required=tuple(missing_required),
    )


__all__ = [
    "MASKED_PLACEHOLDER",
    "ProfileFieldView",
    "ProfileOverview",
    "ProfileSectionView",
    "build_profile_overview",
]
