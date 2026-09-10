"""Operator-facing labels for the user-profile schema, in the active language.

The schema TOML declares a ``title`` per section and a ``description`` per
field. Neither is a label. ``description`` is long-form authority prose --
often several sentences (``auth.provider`` runs to four) -- and it is
deliberately mixed-language, because the fields whose meaning is fixed by
Spanish tax law are written in Spanish (``tax_residence.ccaa``,
``renta_taxpayer.sex``, ``provenance.source``). Rendering it as a table
label gave the operator a paragraph in a column, in whichever language the
schema author happened to use.

So the two strings are separated by job, and each has exactly one home:

- The schema TOML owns the long-form prose. It stays the authority the
  wizard's copy resolver reads and the masking heuristic scans.
- The locale catalogues own the short operator-facing label, keyed per
  section and per field.

The label is resolved through :func:`~cadrumo.core.i18n.tr` with the schema
prose as the ``default``, which makes the fallback truthful rather than
decorative: a field whose key no catalogue carries renders its declared
description -- true, if verbose -- instead of a raw dotted path or a
missing-key marker. The renderer already treats a value equal to its own
key as a miss, so a scaffold placeholder falls back the same way an absent
key does; a key can therefore be declared before it is translated without
ever showing the operator a placeholder.

Keys are derived from the schema rather than declared beside it, so the
schema stays the single structural authority: adding a field to the TOML
creates its key by construction. :func:`profile_schema_locale_keys` is what
the locale scaffolder reads, which is what makes a newly-declared field
without labels a loud parity failure rather than a silent English row.

See Also:
    :class:`ProfileSchemaDefinition`
        The schema whose sections and fields these keys are derived from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.i18n import tr

if TYPE_CHECKING:
    from .schema import ProfileFieldDefinition, ProfileSchemaDefinition, ProfileSectionDefinition

_KEY_ROOT = "profile.schema"

# The two key families are separated by an explicit ``section``/``field``
# infix rather than nested directly under the section key. Without it a
# field named ``title`` would build ``profile.schema.<section>.title.label``
# while its own section built ``profile.schema.<section>.title`` -- the same
# catalogue path as both a mapping and a leaf, which YAML cannot represent.
# The infix makes the collision structurally impossible instead of relying
# on no one ever naming a field ``title``.
_SECTION_INFIX = "section"
_FIELD_INFIX = "field"


def profile_section_title_key(section_key: str) -> str:
    """Return the locale key carrying one section's operator-facing title.

    Args:
        section_key: Canonical section key, e.g. ``identity``.

    Returns:
        The dotted locale key, e.g. ``profile.schema.section.identity.title``.
    """
    return f"{_KEY_ROOT}.{_SECTION_INFIX}.{section_key}.title"


def profile_field_label_key(section_key: str, field_key: str) -> str:
    """Return the locale key carrying one field's operator-facing label.

    Args:
        section_key: Canonical section key, e.g. ``identity``.
        field_key: Canonical field key within that section, e.g. ``tax_id``.

    Returns:
        The dotted locale key, e.g.
        ``profile.schema.field.identity.tax_id.label``.
    """
    return f"{_KEY_ROOT}.{_FIELD_INFIX}.{section_key}.{field_key}.label"


def profile_section_title(section: ProfileSectionDefinition, *, locale: str | None = None) -> str:
    """Return one section's title in ``locale``, falling back to the schema.

    Args:
        section: The declared section.
        locale: Language code; the active output language when ``None``.

    Returns:
        The catalogue title, or the schema's declared ``title`` when the
        catalogue does not carry one.
    """
    return tr(profile_section_title_key(section.key), locale=locale, default=section.title)


def profile_field_label(
    section_key: str,
    field: ProfileFieldDefinition,
    *,
    locale: str | None = None,
) -> str:
    """Return one field's label in ``locale``, falling back to the schema.

    Args:
        section_key: Canonical key of the section declaring ``field``.
        field: The declared field.
        locale: Language code; the active output language when ``None``.

    Returns:
        The catalogue label, or the field's declared ``description`` when
        the catalogue does not carry one.
    """
    return tr(
        profile_field_label_key(section_key, field.key),
        locale=locale,
        default=field.description,
    )


def profile_schema_locale_keys(schema: ProfileSchemaDefinition) -> set[str]:
    """Return every locale key the schema's sections and fields declare.

    This is the enrolment surface the locale scaffolder and the parity gate
    read, so a field added to the schema TOML without a catalogue entry
    fails parity instead of silently rendering its description.

    Args:
        schema: The loaded schema to enumerate.

    Returns:
        Every section-title and field-label key declared by ``schema``.
    """
    keys: set[str] = set()
    for section in schema.sections:
        keys.add(profile_section_title_key(section.key))
        for field in section.fields:
            keys.add(profile_field_label_key(section.key, field.key))
    return keys


__all__ = [
    "profile_field_label",
    "profile_field_label_key",
    "profile_schema_locale_keys",
    "profile_section_title",
    "profile_section_title_key",
]
