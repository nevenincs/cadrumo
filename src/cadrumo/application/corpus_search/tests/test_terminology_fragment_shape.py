"""Real-behavior tests for the shipped Handbook reader's structural refusals.

The unshipped authoring compiler validates
every concept fragment against a strict, frozen, ``extra="forbid"`` schema
before it can ever be curated. This lean, shipped product reader walks the
same TOML by hand for a small locale/search projection and historically
tolerated shapes the authoring schema refuses outright -- a malformed
``concept_id``, a fragment with no ``[language.*]`` section at all -- by
silently synthesizing an empty, near-useless search hit rather than
refusing. These tests bind the shared refusal in both directions: the
canonical ``concept_id`` shape lives in this package
(:data:`~cadrumo.application.corpus_search.CONCEPT_ID_PATTERN`) and the
dev-only schema imports it, so a malformed id is refused identically on
both sides of the shipping boundary.
"""

from __future__ import annotations

import re
import tomllib

import pytest

from ..errors import CorpusSearchInputError
from ..terminology import CONCEPT_ID_MAX_LENGTH, CONCEPT_ID_MIN_LENGTH, CONCEPT_ID_PATTERN, _project_concept

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A well-formed concept_id but no [language.*] section at all -- isolates
# the missing-language refusal from the concept_id-shape refusal below.
_MISSING_LANGUAGE_FRAGMENT = """
[concept]
concept_id = "prorrata-especial"
domain = "not-a-domain"
lifecycle = "approved"
"""

_MALFORMED_CONCEPT_ID_FRAGMENT = """
[concept]
concept_id = "A"
domain = "concepto"
lifecycle = "approved"

[language.es]
short_description = "Placeholder."

[[language.es.term]]
label = "placeholder"
term_status = "preferred"
"""

# The exact combined-defect shape the audit demonstrated: a malformed
# concept_id, an unrecognised domain, an unrecognised term_status, and no
# [language.*] section reachable for the requested locale (the section is
# entirely absent). Before the fix this produced a searchable hit with
# preferred_label "A" and empty text; it must now be refused outright.
_AUDIT_DEMONSTRATED_MALFORMED_FRAGMENT = """
[concept]
concept_id = "A"
domain = "not-a-domain"
lifecycle = "approved"
smuggled_field = true
"""

_WELL_FORMED_FRAGMENT = """
[concept]
concept_id = "prorrata-especial"
domain = "concepto"
lifecycle = "approved"

[language.es]
short_description = "Regla de deducción parcial del IVA soportado."

[[language.es.term]]
label = "prorrata especial"
term_status = "preferred"
"""


def test_concept_id_pattern_matches_the_canonical_kebab_case_shape() -> None:
    """The shared pattern accepts a real bundled concept_id shape."""
    assert CONCEPT_ID_MIN_LENGTH == 2
    assert CONCEPT_ID_MAX_LENGTH == 64
    assert re.fullmatch(CONCEPT_ID_PATTERN, "prorrata-especial")
    assert not re.fullmatch(CONCEPT_ID_PATTERN, "A")


def test_a_fragment_with_no_language_section_is_refused() -> None:
    """A fragment with no [language.*] table at all is refused, not fabricated.

    Before the fix this produced a searchable hit whose preferred_label
    fell back to its own concept_id and whose text was entirely empty --
    real, demonstrated search-index pollution.
    """
    payload = tomllib.loads(_MISSING_LANGUAGE_FRAGMENT)
    with pytest.raises(CorpusSearchInputError) as raised:
        _project_concept(payload, locale="es")

    assert raised.value.reason == "concept_declares_no_language_sections"


def test_a_malformed_concept_id_is_refused() -> None:
    """A concept_id outside the canonical kebab-case shape is refused."""
    payload = tomllib.loads(_MALFORMED_CONCEPT_ID_FRAGMENT)
    with pytest.raises(CorpusSearchInputError) as excinfo:
        _project_concept(payload, locale="es")
    assert excinfo.value.context is not None
    assert excinfo.value.context["concept_id"] == "A"


def test_the_audit_demonstrated_malformed_fragment_is_refused_not_fabricated() -> None:
    """The exact multi-defect shape from the audit finding is refused outright.

    Reproduces the audit's own probe: previously this produced a
    "searchable product concept with fallback label 'A' and empty text"
    despite the dev authoring compiler raising seven schema errors on the
    identical shape. It must now refuse rather than fabricate.
    """
    payload = tomllib.loads(_AUDIT_DEMONSTRATED_MALFORMED_FRAGMENT)

    with pytest.raises(CorpusSearchInputError):
        _project_concept(payload, locale="es")


def test_a_well_formed_fragment_still_projects_cleanly() -> None:
    """The tightened validation does not reject a genuinely well-formed concept."""
    payload = tomllib.loads(_WELL_FORMED_FRAGMENT)

    projected = _project_concept(payload, locale="es")

    assert projected is not None
    assert projected.concept_id == "prorrata-especial"
    assert projected.preferred_label == "prorrata especial"
