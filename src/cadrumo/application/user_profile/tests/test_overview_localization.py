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

import json
from pathlib import Path

import pytest

from cadrumo.application.user_profile.overview import MASKED_PLACEHOLDER, build_profile_overview

from ....core.config import override_settings
from ....domain.user_profile.schema import ProfileFieldType
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.labels import profile_field_label_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"

_ALLOWLIST_PATH = Path(__file__).resolve().parents[3] / "locales" / "_intentional_identical.json"


def _identical_by_nature(locale: str) -> frozenset[str]:
    """Return the field paths whose label is allowed to equal English.

    Read from the catalogues' own exemption file rather than restated here.
    A term like IBAN or SWIFT-BIC is an ISO code name that is identical in
    every language, so an equal label is correct rather than untranslated —
    but that judgement already has one home, and duplicating it as a literal
    here would let this gate and the translation-honesty ratchet drift apart.
    Anything NOT in that file must still differ, so an untranslated label
    cannot hide behind this exemption.
    """
    raw = json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = raw.get(locale, {}) if isinstance(raw, dict) else {}
    exempt_keys = {key for key in entries if not key.startswith("_")}
    schema = load_user_profile_schema()
    return frozenset(
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if profile_field_label_key(section.key, field.key) in exempt_keys
    )


def _record() -> UserProfileRecord:
    """A minimal record; the walk is schema-driven so facts are incidental."""
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
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
    """No field label is left rendering one language to both operators.

    Labels that are identical by nature -- ISO code names such as IBAN --
    are exempt, but only when the catalogues' own exemption file says so.
    An untranslated label therefore still fails here rather than passing on
    a blanket carve-out.
    """
    english = {field.path: field.label for section in _overview_in("en").sections for field in section.fields}
    spanish = {field.path: field.label for section in _overview_in("es").sections for field in section.fields}
    exempt = _identical_by_nature("es")

    assert english.keys() == spanish.keys()
    identical = sorted(path for path in english if english[path] == spanish[path] and path not in exempt)
    assert not identical, f"field labels identical under en and es without an exemption: {identical[:10]}"


def test_the_identical_by_nature_exemption_matches_current_labels() -> None:
    """The exemption names exactly the currently identical declared labels.

    A fully localized schema legitimately has no such labels. Conversely, a
    non-empty exemption must name only declared fields whose labels really
    remain identical; otherwise it is stale permission rather than a current
    catalogue declaration.
    """
    exempt = _identical_by_nature("es")
    declared = set(load_user_profile_schema().field_paths)
    english = {field.path: field.label for section in _overview_in("en").sections for field in section.fields}
    spanish = {field.path: field.label for section in _overview_in("es").sections for field in section.fields}
    identical = frozenset(path for path in english if english[path] == spanish[path])

    assert exempt <= declared, f"exemption names paths the schema does not declare: {sorted(exempt - declared)}"
    assert exempt == identical, (
        "identical-by-nature exemptions must match exactly the current identical labels: "
        f"missing={sorted(identical - exempt)}, stale={sorted(exempt - identical)}"
    )
    assert len(exempt) < len(declared) // 10, "the identical-by-nature carve-out has grown into a blanket bypass"


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

    A namespace field — an ``object`` or ``array``, whose instances live at
    ``field.INDEX.leaf`` — reaches the view as those instances rather than
    as itself, because nothing writes its bare path and a row offered there
    could only ever be blank. So the record carries one instance and both
    halves are asserted exactly: the ordinary fields as declared, plus the
    row that instance produced. Stated as one equality rather than as a
    subtraction, so the carve-out cannot quietly widen to cover a field
    that simply went missing.
    """
    schema = load_user_profile_schema()
    namespaces = {
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if field.type in {ProfileFieldType.OBJECT, ProfileFieldType.ARRAY}
    }
    assert namespaces, "no namespace field is declared, which would make the carve-out below vacuous"

    # A path the engine derives renders no row, because the write door refuses
    # it and a box the record then rejects is the disagreement that refusal
    # exists to prevent. There is no second carve-out term to subtract here: a
    # declared field and a derived-selector pattern are mutually exclusive by
    # construction, so no declared field path ever matches a pattern and the
    # equality below needs no such term.

    instance_path = "censo.divergencia.0.axis"
    record = _record().model_copy(
        update={"facts": (*_record().facts, UserProfileFact(path=instance_path, value="censo.iae_epigrafe"))},
    )
    with override_settings(cadrumo_output_language="en"):
        overview = build_profile_overview(record)
    projected = {field.path for section in overview.sections for field in section.fields}

    assert projected == (set(schema.field_paths) - namespaces) | {instance_path}
