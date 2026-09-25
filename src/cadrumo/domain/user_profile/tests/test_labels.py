"""The profile schema's section titles and field labels are language-bound.

The defect these gates pin: the profile manager rendered its chrome through
the translator while every section title and field label came straight from
the schema TOML, so switching the output language re-rendered the frame
around an English table. A gate that only asserted "a label is returned"
would have passed against that defect, so each assertion here turns on the
label CHANGING with the language, or on the fallback being the schema's own
prose rather than a key.
"""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....core.i18n.render import tr
from ..labels import (
    PROFILE_CODED_CHOICE_PATHS,
    PROFILE_ELSEWHERE_LABELLED_CHOICE_PATHS,
    PROFILE_FIELD_HELP_PARTS,
    PROFILE_FIELD_HELP_PATHS,
    profile_choice_is_worded,
    profile_choice_label,
    profile_choice_label_key,
    profile_field_help_key,
    profile_field_label,
    profile_field_label_key,
    profile_schema_locale_keys,
    profile_section_title,
    profile_section_title_key,
)
from ._schema_loader_fixtures import module_scoped_schema

__all__ = ["module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# A section and a field that both exist in the committed schema. Resolved
# through the loader in the fixtures below rather than reconstructed, so a
# rename in the TOML fails these tests loudly instead of silently testing a
# path the schema no longer declares.
_SECTION_KEY = "identity"
_FIELD_KEY = "tax_id"


@pytest.fixture(scope="module")
def section(schema):
    return schema.section(_SECTION_KEY)


@pytest.fixture(scope="module")
def field(section):
    return next(candidate for candidate in section.fields if candidate.key == _FIELD_KEY)


def test_section_title_differs_between_output_languages(section) -> None:
    """A section title rendered under en and es is not the same string.

    This is the defect gate. Before the change the title was
    ``section.title`` verbatim, so both languages returned one English
    string and this assertion fails.
    """
    with override_settings(cadrumo_output_language="en"):
        english = profile_section_title(section)
    with override_settings(cadrumo_output_language="es"):
        spanish = profile_section_title(section)

    assert english != spanish, (
        f"section {section.key!r} rendered {english!r} under both en and es; "
        "the title is not reaching the locale catalogue"
    )


def test_field_label_differs_between_output_languages(field) -> None:
    """A field label rendered under en and es is not the same string."""
    with override_settings(cadrumo_output_language="en"):
        english = profile_field_label(_SECTION_KEY, field)
    with override_settings(cadrumo_output_language="es"):
        spanish = profile_field_label(_SECTION_KEY, field)

    assert english != spanish, (
        f"field {_SECTION_KEY}.{field.key!r} rendered {english!r} under both en and es; "
        "the label is not reaching the locale catalogue"
    )


def test_field_label_is_not_the_schema_description_when_translated(field) -> None:
    """A translated label replaces the schema prose rather than echoing it.

    Anti-vacuity for the two gates above: they would also pass if the
    catalogue happened to carry the description verbatim in one language.
    """
    with override_settings(cadrumo_output_language="es"):
        spanish = profile_field_label(_SECTION_KEY, field)

    assert spanish != field.description


def test_untranslated_field_label_falls_back_to_the_schema_description(field) -> None:
    """A key no catalogue carries renders the schema prose, never the key.

    Exercised through the real renderer against a key that genuinely does
    not exist, which is what an operator meets for a field added to the
    schema before its labels are authored.
    """
    absent_key = profile_field_label_key("__no_such_section__", "__no_such_field__")

    rendered = tr(absent_key, locale="en", default=field.description)

    assert rendered == field.description
    assert absent_key not in rendered, "the dotted key leaked into operator-facing copy"


def test_scaffold_placeholder_falls_back_like_an_absent_key() -> None:
    """A key whose value echoes itself is a miss, not a translation.

    ``scaffold`` writes a missing key as its own dotted path. If the
    renderer treated that as a hit, a freshly scaffolded field would show
    the operator ``profile.schema.field.x.y.label``. The fallback must
    behave exactly as it does for an absent key.
    """
    echoing_key = "profile.schema.field.__echo__.__echo__.label"

    rendered = tr(echoing_key, locale="en", default="declared prose")

    assert rendered == "declared prose"


def test_section_and_field_key_families_cannot_collide() -> None:
    """A field named ``title`` cannot claim its own section's title key.

    Without the ``section``/``field`` infix, section ``x`` would key
    ``profile.schema.x.title`` while its field ``title`` keyed
    ``profile.schema.x.title.label`` -- one catalogue path used as both a
    leaf and a mapping, which YAML cannot hold. This pins the separation
    rather than trusting that no one ever names a field ``title``.
    """
    section_title = profile_section_title_key("x")
    colliding_field = profile_field_label_key("x", "title")

    assert not colliding_field.startswith(f"{section_title}.")
    assert section_title != colliding_field


def test_every_worded_choice_is_enrolled_and_every_coded_choice_is_not(schema) -> None:
    """Parity demands copy for each worded enumeration choice, and never for an official code."""
    enrolled = profile_schema_locale_keys(schema)
    enumerations = [
        (section.key, field) for section in schema.sections for field in section.fields if field.enum_values
    ]
    assert any(profile_choice_is_worded(key, field.key) for key, field in enumerations)
    assert any(f"{key}.{field.key}" in PROFILE_CODED_CHOICE_PATHS for key, field in enumerations)
    for section_key, field in enumerations:
        keys = {profile_choice_label_key(section_key, field.key, token) for token in field.enum_values}
        if profile_choice_is_worded(section_key, field.key):
            assert keys <= enrolled, f"{section_key}.{field.key} choices are not enrolled for translation"
        else:
            assert not keys & enrolled, f"{section_key}.{field.key} is coded or labelled elsewhere"


def test_an_undeclared_enumeration_defaults_to_needing_copy() -> None:
    """A new enumeration is labelled unless it is explicitly declared as codes.

    This is what turns a forgotten translation into a parity failure instead
    of a question offering its raw storage tokens.
    """
    assert profile_choice_is_worded("__new_section__", "__new_enum__")
    for path in PROFILE_CODED_CHOICE_PATHS | PROFILE_ELSEWHERE_LABELLED_CHOICE_PATHS:
        section_key, field_key = path.split(".", 1)
        assert not profile_choice_is_worded(section_key, field_key)


def test_a_worded_choice_reads_as_language_and_a_coded_choice_as_its_code() -> None:
    """The IVA regime reads as words in each language; a socio clave stays the AEAT code."""
    with override_settings(cadrumo_output_language="en"):
        english = profile_choice_label("iva", "regime", "RECARGO_EQUIVALENCIA")
    with override_settings(cadrumo_output_language="es"):
        spanish = profile_choice_label("iva", "regime", "RECARGO_EQUIVALENCIA")
    assert english != spanish
    assert "RECARGO_EQUIVALENCIA" not in (english, spanish)
    assert profile_choice_label("attribution_entity_socios", "clave", "A") == "A"


def test_every_question_setup_can_ask_carries_its_three_part_help(schema) -> None:
    """A schema-required field, or one the IVA block obliges, is never asked unexplained."""
    from ...deadlines.profiles import MODELO_IVA_BLOCK_REQUIRED_PATHS

    setup_paths = {
        f"{section.key}.{field.key}"
        for section in schema.sections
        if not section.repeatable
        for field in section.fields
        if field.required
    } | set(MODELO_IVA_BLOCK_REQUIRED_PATHS)
    assert setup_paths, "the schema must declare setup questions, or this proves nothing"
    assert setup_paths <= PROFILE_FIELD_HELP_PATHS, sorted(setup_paths - PROFILE_FIELD_HELP_PATHS)


def test_help_is_enrolled_only_for_declared_fields_that_exist(schema) -> None:
    """Each help path names a real field, and parity demands all three parts of it."""
    declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
    assert declared >= PROFILE_FIELD_HELP_PATHS, sorted(PROFILE_FIELD_HELP_PATHS - declared)
    enrolled = profile_schema_locale_keys(schema)
    for path in PROFILE_FIELD_HELP_PATHS:
        section_key, field_key = path.split(".", 1)
        for part in PROFILE_FIELD_HELP_PARTS:
            key = profile_field_help_key(section_key, field_key, part)
            assert key in enrolled
            assert tr(key, locale="es") != tr(key, locale="en"), key
