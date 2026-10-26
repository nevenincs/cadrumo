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

The label is resolved through :func:`~cadrumo.core.i18n.render.tr` with the schema
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

from ...core.i18n.render import tr

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
_CHOICES_INFIX = "choices"

PROFILE_CODED_CHOICE_PATHS: frozenset[str] = frozenset(
    {
        "censo.elected_withholding_pct",
        "attribution_entity_socios.participe_clave",
        "attribution_entity_socios.clave",
        "attribution_entity_socios.subclave",
        "attribution_entity_socios.codigo_provincia",
        "attribution_entity_socios.naturaleza_inmueble",
        "attribution_entity_socios.situacion_inmueble",
        "attribution_entity_socios.clave_declarado",
        "renta_taxpayer.marital_status",
    }
)
"""Enumerations whose stored tokens are the official AEAT codes themselves.

The operator reads these codes on the AEAT form and its instructions, so the
code is the label; a catalogue gloss would be a second, ungrounded claim about
what each code means."""

PROFILE_FIELD_HELP_PATHS: frozenset[str] = frozenset(
    {
        "identity.tax_id",
        "tax_residence.jurisdiction_scope",
        "iva.regime",
        "iva.m303_regime_composition",
        "iva.redeme_enrolled",
        "iva.cash_accounting_regime_enrolled",
        "iva.voluntary_sii_enrolled",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
    }
)
"""Fields whose catalogue help says what they are, why they are asked, and where to find them.

Every other field is explained by its schema description instead."""

PROFILE_FIELD_HELP_PARTS: tuple[str, ...] = ("what", "why", "where")
"""The three questions a field's help answers, in the order they are shown."""

PROFILE_ELSEWHERE_LABELLED_CHOICE_PATHS: frozenset[str] = frozenset(
    {"preferences.output_language", "auth.provider", "auth.clave_movil_route"}
)
"""Enumerations whose choices already carry canonical copy under another key family."""


def profile_section_title_key(section_key: str) -> str:
    """Return the locale key carrying one section's operator-facing title.

    Args:
        section_key: Canonical section key, e.g. ``identity``.

    Returns:
        The dotted locale key, e.g. ``profile.schema.section.identity.title``.
    """
    return f"{_KEY_ROOT}.{_SECTION_INFIX}.{section_key}.title"


def profile_section_summary_key(section_key: str) -> str:
    """Return the locale key carrying one section's one-sentence explanation.

    The title names a section; the summary tells the operator what it is
    for, so a page that folds sections away can still say what each one
    holds before it is opened.

    Args:
        section_key: Canonical section key, e.g. ``identity``.

    Returns:
        The dotted locale key, e.g. ``profile.schema.section.identity.summary``.
    """
    return f"{_KEY_ROOT}.{_SECTION_INFIX}.{section_key}.summary"


def profile_choice_label_key(section_key: str, field_key: str, token: str) -> str:
    """Return the locale key carrying one enumeration choice's operator-facing label.

    Args:
        section_key: Canonical section key, e.g. ``iva``.
        field_key: Canonical field key within that section, e.g. ``regime``.
        token: The stored enumeration token, e.g. ``GENERAL``.

    Returns:
        The dotted locale key, e.g. ``profile.schema.field.iva.regime.choices.GENERAL``.
    """
    return f"{_KEY_ROOT}.{_FIELD_INFIX}.{section_key}.{field_key}.{_CHOICES_INFIX}.{token}"


def profile_choice_is_worded(section_key: str, field_key: str) -> bool:
    """Whether an enumeration's choices are labelled from the profile schema key family.

    Every enumeration is, unless it is declared as official codes or as
    labelled under another family. Defaulting to labelled is what makes a new
    enumeration without copy a parity failure rather than a list of raw tokens.
    """
    path = f"{section_key}.{field_key}"
    return path not in PROFILE_CODED_CHOICE_PATHS and path not in PROFILE_ELSEWHERE_LABELLED_CHOICE_PATHS


def profile_choice_label(section_key: str, field_key: str, token: str, *, locale: str | None = None) -> str:
    """Return one enumeration choice's label, or the token itself for an official code.

    Args:
        section_key: Canonical section key.
        field_key: Canonical field key within that section.
        token: The stored enumeration token.
        locale: Language code; the active output language when ``None``.

    Returns:
        The catalogue label for a worded choice, or ``token`` for a coded one.
    """
    if not profile_choice_is_worded(section_key, field_key):
        return token
    return tr(profile_choice_label_key(section_key, field_key, token), locale=locale)


def profile_field_help_key(section_key: str, field_key: str, part: str) -> str:
    """Return the locale key for one part of a field's help.

    Args:
        section_key: Canonical section key, e.g. ``identity``.
        field_key: Canonical field key within that section, e.g. ``tax_id``.
        part: One of :data:`PROFILE_FIELD_HELP_PARTS`.

    Returns:
        The dotted locale key, e.g. ``profile.schema.field.identity.tax_id.help.why``.
    """
    return f"{_KEY_ROOT}.{_FIELD_INFIX}.{section_key}.{field_key}.help.{part}"


def profile_field_help(section_key: str, field_key: str, *, locale: str | None = None) -> tuple[str, ...] | None:
    """Return a field's help, one sentence per part, or ``None`` when it carries none.

    Args:
        section_key: Canonical section key.
        field_key: Canonical field key within that section.
        locale: Language code; the active output language when ``None``.

    Returns:
        What the field is, why it is asked and where to find it, in that
        order, or ``None`` for a field outside :data:`PROFILE_FIELD_HELP_PATHS`.
    """
    if f"{section_key}.{field_key}" not in PROFILE_FIELD_HELP_PATHS:
        return None
    return tuple(
        tr(profile_field_help_key(section_key, field_key, part), locale=locale) for part in PROFILE_FIELD_HELP_PARTS
    )


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
    return tr(
        profile_section_title_key(section.key),
        locale=locale,
    )


def profile_section_summary(section: ProfileSectionDefinition, *, locale: str | None = None) -> str:
    """Return one section's explanation in ``locale``.

    Args:
        section: The declared section.
        locale: Language code; the active output language when ``None``.

    Returns:
        The catalogue summary for the section.
    """
    return tr(profile_section_summary_key(section.key), locale=locale)


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
    )


def profile_schema_locale_keys(schema: ProfileSchemaDefinition) -> set[str]:
    """Return every locale key the schema's sections and fields declare.

    This is the enrolment surface the locale scaffolder and the parity gate
    read, so a field added to the schema TOML without a catalogue entry
    fails parity instead of silently rendering its description.

    Args:
        schema: The loaded schema to enumerate.

    Returns:
        Every section-title, section-summary, field-label and worded
        enumeration-choice key declared by ``schema``.
    """
    keys: set[str] = set()
    for section in schema.sections:
        keys.add(profile_section_title_key(section.key))
        keys.add(profile_section_summary_key(section.key))
        for field in section.fields:
            keys.add(profile_field_label_key(section.key, field.key))
            if f"{section.key}.{field.key}" in PROFILE_FIELD_HELP_PATHS:
                keys.update(profile_field_help_key(section.key, field.key, part) for part in PROFILE_FIELD_HELP_PARTS)
            if field.enum_values and profile_choice_is_worded(section.key, field.key):
                keys.update(profile_choice_label_key(section.key, field.key, token) for token in field.enum_values)
    return keys


__all__ = [
    "PROFILE_CODED_CHOICE_PATHS",
    "PROFILE_ELSEWHERE_LABELLED_CHOICE_PATHS",
    "PROFILE_FIELD_HELP_PARTS",
    "PROFILE_FIELD_HELP_PATHS",
    "profile_choice_is_worded",
    "profile_choice_label",
    "profile_choice_label_key",
    "profile_field_help",
    "profile_field_help_key",
    "profile_field_label",
    "profile_field_label_key",
    "profile_schema_locale_keys",
    "profile_section_summary",
    "profile_section_summary_key",
    "profile_section_title",
    "profile_section_title_key",
]
