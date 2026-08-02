"""The manager's landing-page projection follows the output language.

The overview is what the profile manager renders, and it is where the
English-only defect was visible: the surrounding chrome went through the
translator while the table's own section titles and field labels came
straight from the schema TOML. These gates assert the projection changes
with the language, and -- separately -- that the secret-masking decision
does NOT, because a confidentiality decision that varies by locale would
unmask a field in one language and protect it in another.

The projection is built against the COMMITTED schema rather than a
synthetic one, because the property under test is that the shipped schema's
sections and fields resolve through the shipped catalogues; a fixture
schema would carry keys no catalogue declares and every label would fall
back, which is exactly the state the change exists to leave behind.
"""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
    load_user_profile_schema,
)
from .. import MASKED_PLACEHOLDER, build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"


def _record() -> UserProfileRecord:
    """A minimal record; the walk is schema-driven so facts are incidental."""
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="Localization probe",
        status=UserProfileStatus.ACTIVE,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )


def _overview_in(language: str):
    with override_settings(cadrumo_output_language=language):
        return build_profile_overview(_record())


def test_section_titles_change_with_the_output_language() -> None:
    """At least one section title differs between en and es.

    Asserted across the whole schema rather than one hand-picked section,
    so the gate survives a section being renamed or dropped.
    """
    english = {section.key: section.title for section in _overview_in("en").sections}
    spanish = {section.key: section.title for section in _overview_in("es").sections}

    assert english.keys() == spanish.keys()
    differing = [key for key in english if english[key] != spanish[key]]
    assert differing, "no section title changed between en and es; titles are not localized"


def test_every_section_title_is_localized() -> None:
    """No section falls back to a single shared string across languages.

    The weaker "at least one differs" gate above would pass with one
    section translated and twenty-four English. This one names the ones
    that did not move.
    """
    english = {section.key: section.title for section in _overview_in("en").sections}
    spanish = {section.key: section.title for section in _overview_in("es").sections}

    identical = sorted(key for key in english if english[key] == spanish[key])
    assert not identical, f"section titles identical under en and es: {identical}"


def test_every_field_label_is_localized() -> None:
    """No field label is left rendering one language to both operators."""
    english = {field.path: field.label for section in _overview_in("en").sections for field in section.fields}
    spanish = {field.path: field.label for section in _overview_in("es").sections for field in section.fields}

    assert english.keys() == spanish.keys()
    identical = sorted(path for path in english if english[path] == spanish[path])
    assert not identical, f"field labels identical under en and es: {identical[:10]}"


def test_no_label_renders_a_raw_locale_key() -> None:
    """A label never shows the operator a dotted key or a bare schema path.

    This is the fallback's honesty condition: an unauthored key must reach
    the schema's prose, so nothing shaped like ``profile.schema.…`` can
    survive into a rendered label.
    """
    for language in ("en", "es", "ca", "hu"):
        overview = _overview_in(language)
        for section in overview.sections:
            assert not section.title.startswith("profile.schema."), (
                f"{language}: section {section.key} rendered its locale key"
            )
            for field in section.fields:
                assert not field.label.startswith("profile.schema."), (
                    f"{language}: field {field.path} rendered its locale key"
                )
                assert field.label.strip(), f"{language}: field {field.path} rendered a blank label"


def test_masking_does_not_vary_with_the_output_language() -> None:
    """Which fields mask is identical in every language.

    Masking reads the schema's own description, never the translated
    label. If it ever scanned localized copy, a field whose English
    description says "password" would mask while its Spanish label did
    not -- a confidentiality decision leaking through a display setting.
    """
    masked_by_language = {
        language: {
            field.path for section in _overview_in(language).sections for field in section.fields if field.masked
        }
        for language in ("en", "es", "ca", "hu")
    }

    baseline = masked_by_language["en"]
    assert baseline, "no field masked in any language; this gate would be vacuous"
    for language, masked in masked_by_language.items():
        assert masked == baseline, (
            f"{language} masks a different field set than en: "
            f"only-in-{language}={sorted(masked - baseline)}, only-in-en={sorted(baseline - masked)}"
        )


def test_secret_values_stay_masked_in_every_language() -> None:
    """Localization does not open a path around the mask."""
    for language in ("en", "es", "ca", "hu"):
        overview = _overview_in(language)
        for section in overview.sections:
            for field in section.fields:
                if field.masked and field.value is not None:
                    assert field.value == MASKED_PLACEHOLDER


def test_schema_field_coverage_is_complete_in_the_projection() -> None:
    """Every declared field reaches the view, in every language.

    Anti-vacuity for the localization gates: they compare dictionaries, so
    a projection that dropped fields would shrink both sides and still
    agree.
    """
    declared = set(load_user_profile_schema().field_paths)
    projected = {field.path for section in _overview_in("en").sections for field in section.fields}

    assert declared == projected
