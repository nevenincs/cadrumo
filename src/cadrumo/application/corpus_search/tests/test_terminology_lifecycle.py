"""Real-behavior tests for the concept-lifecycle boundary of the Handbook reader.

The stored ``lifecycle`` token is a closed value set with a home in ``core``;
these tests bind that hydration in both directions — every token the bundled
fragments actually carry resolves to a member, and a token outside the set is
refused rather than silently dropped from every search result.
"""

from __future__ import annotations

import tomllib

import pytest

from ....core import ConceptLifecycle, scan_directory
from ....core.external_constants import UTF_8_ENCODING
from ..errors import CorpusSearchInputError
from .._terminology import (
    _project_concept,
    _terminology_root,
    load_terminology_concepts,
    lookup_terminology,
    search_terminology,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNKNOWN_LIFECYCLE_FRAGMENT = """
[concept]
concept_id = "prorrata-especial"
domain = "concepto"
lifecycle = "aprobado"

[language.es]
short_description = "Regla de deducción parcial del IVA soportado."

[[language.es.term]]
label = "prorrata especial"
term_status = "preferred"
"""

_KNOWN_LIFECYCLE_FRAGMENT = """
[concept]
concept_id = "prorrata-especial"
domain = "concepto"
lifecycle = "deprecated"

[language.es]
short_description = "Regla de deducción parcial del IVA soportado."

[[language.es.term]]
label = "prorrata especial"
term_status = "preferred"
"""


def test_bundled_fragment_token_hydrates_to_its_member() -> None:
    concepts = load_terminology_concepts("es")
    assert concepts, "the bundled Handbook must ship concept fragments"
    for concept in concepts:
        assert isinstance(concept.lifecycle, ConceptLifecycle)


def test_every_stored_token_in_the_tree_is_a_declared_member() -> None:
    # Read the fragments directly, not through the projected models: this is the
    # drift gate between the authored tree and the core-declared value set, so
    # it must see the raw token rather than an already-hydrated member.
    stored: set[str] = set()
    for path in scan_directory(_terminology_root(), pattern="*.toml"):
        payload = tomllib.loads(path.read_text(encoding=UTF_8_ENCODING))
        concept = payload.get("concept")
        assert isinstance(concept, dict), path.name
        token = concept.get("lifecycle")
        assert isinstance(token, str), path.name
        stored.add(token)
    assert stored, "the bundled Handbook must declare lifecycle tokens"
    assert stored <= {member.value for member in ConceptLifecycle}


def test_known_token_projects_to_the_matching_member() -> None:
    payload = tomllib.loads(_KNOWN_LIFECYCLE_FRAGMENT)
    projected = _project_concept(payload, locale="es")
    assert projected is not None
    assert projected.lifecycle is ConceptLifecycle.DEPRECATED


def test_unknown_token_is_refused_with_the_accepted_set() -> None:
    payload = tomllib.loads(_UNKNOWN_LIFECYCLE_FRAGMENT)
    with pytest.raises(CorpusSearchInputError) as excinfo:
        _project_concept(payload, locale="es")
    context = excinfo.value.context
    assert context is not None
    assert context["lifecycle"] == "aprobado"
    assert context["concept_id"] == "prorrata-especial"
    accepted = context["accepted"]
    assert isinstance(accepted, tuple)
    assert {ConceptLifecycle(str(value)) for value in accepted} == set(ConceptLifecycle)


def test_search_default_surfaces_only_approved_concepts() -> None:
    approved = {
        concept.concept_id
        for concept in load_terminology_concepts("es")
        if concept.lifecycle is ConceptLifecycle.APPROVED
    }
    non_approved = {
        concept.concept_id
        for concept in load_terminology_concepts("es")
        if concept.lifecycle is not ConceptLifecycle.APPROVED
    }
    assert approved and non_approved, "the tree must carry both sides for this gate to bite"
    for concept_id in sorted(non_approved):
        # The concept resolves by exact id, so an id-shaped query would match it
        # if the default lifecycle filter were not applied.
        hits = search_terminology(concept_id, locale="es")
        assert concept_id not in {hit.concept_id for hit in hits}
        assert lookup_terminology(concept_id, locale="es").concept_id == concept_id


def test_search_widened_to_a_member_surfaces_that_lifecycle() -> None:
    deprecated = sorted(
        concept.concept_id
        for concept in load_terminology_concepts("es")
        if concept.lifecycle is ConceptLifecycle.DEPRECATED
    )
    assert deprecated, "the tree must carry deprecated internal-machinery concepts"
    concept_id = deprecated[0]
    hits = search_terminology(concept_id, locale="es", lifecycles=(ConceptLifecycle.DEPRECATED,))
    assert concept_id in {hit.concept_id for hit in hits}
