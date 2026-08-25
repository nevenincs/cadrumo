"""Construct closure evidence validation.

The modelo validator must route
:class:`~domain.calculations.registry.ConstructDefinition` rows through the
same official-source evidence gate as the revision-closure dispatcher, so a
layout-only source cannot make a construct filing-grade.

See Also:
    :func:`~domain.calculations.registry._validate_constructs.validate_construct_closure`
        Construct grounding gate exercised through the public validator.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Modelo-level validator whose call path this regression pins.
"""

from __future__ import annotations

import pytest

from ..schema import ConstructDefinition
from ..validate import RegistryValidator
from .._validate_constructs import _CONSTRUCT_MEMBER_ATTRS, validate_construct_closure
from .._validate_evidence import EvidenceValidator
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    RegistryValidationError,
    minimal_casilla,
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_validation_rejects_construct_without_official_source_evidence() -> None:
    """The revision validator must route constructs through evidence-tier checks."""

    catalogues = minimal_catalogues()
    layout_only_source = catalogues.sources[REFERENCE_SOURCE_ID].model_copy(
        update={"evidence_tier": "layout_authority"}
    )
    casilla = minimal_casilla()
    construct = ConstructDefinition(
        id="construct.without-guidance",
        localization_key="test.schema.construct.without-guidance.title",
        casilla_ids=(casilla.id,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(casilla,), constructs=(construct,))

    with pytest.raises(
        RegistryValidationError,
        match=r"construct construct\.without-guidance requires official_source_guidance source evidence",
    ):
        RegistryValidator(
            catalogues.model_copy(update={"sources": {REFERENCE_SOURCE_ID: layout_only_source}}),
        ).validate_modelo(minimal_modelo(revision))


def test_a_construct_member_missing_legal_refs_is_refused_not_silently_skipped() -> None:
    """The bite proof: a member object that does not carry ``legal_refs`` /
    ``source_refs`` must be refused, not silently treated as requiring none.

    Every one of the fourteen construct-member kinds this validator recognises
    (``_CONSTRUCT_MEMBER_ATTRS``) declares both fields on its own schema class
    -- confirmed programmatically across casilla, formula, parameter, binding,
    relation, export layout, extraction profile,
    cross-reference, workbook parity reference, verification expectation,
    application link, deadline window, filing schedule, and dependency
    classification. Before the fix, ``getattr(member, "legal_refs", ())``
    treated a member object lacking the field as requiring NO legal grounding
    at all -- silently under-counting the construct's required refs, which is
    exactly the failure mode `no-silent-under-declaration` forbids. This
    stands in for a schema drift (a member class that dropped the field) with
    a plain object carrying neither attribute, and proves the fixed direct
    attribute read fails loud instead of silently passing.
    """

    class _DriftedMember:
        """Stands in for a member kind whose class dropped legal_refs/source_refs."""

    construct = ConstructDefinition(
        id="construct.drift-probe",
        localization_key="test.schema.construct.drift-probe.title",
        formulas=("f1",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(constructs=(construct,))
    catalogues = minimal_catalogues()
    member_objects: dict[str, dict[str, object]] = {kind: {} for kind in _CONSTRUCT_MEMBER_ATTRS}
    member_objects["formula"]["f1"] = _DriftedMember()
    evidence = EvidenceValidator(legal_refs=catalogues.legal, source_refs=catalogues.sources, source_root=None)

    with pytest.raises(AttributeError):
        validate_construct_closure(
            "test-scope",
            revision,
            member_objects=member_objects,
            legal_refs=catalogues.legal,
            source_refs=catalogues.sources,
            evidence=evidence,
        )


#: Identity and grounding fields on ``ConstructDefinition`` that are not
#: member-reference sections: ``id``/``localization_key`` name the construct
#: itself, ``legal_refs``/``source_refs`` are the construct's OWN grounding
#: declaration (what ``validate_construct_closure`` checks member refs
#: AGAINST), never a set of member ids to walk.
_NON_MEMBER_CONSTRUCT_FIELDS = frozenset({"id", "localization_key", "legal_refs", "source_refs"})


def test_construct_member_attrs_is_exactly_the_construct_definitions_member_sections() -> None:
    """``_CONSTRUCT_MEMBER_ATTRS`` must name every member-reference field and no other.

    Read live from :class:`ConstructDefinition` rather than restated, so a
    field added to or removed from the model is what this test measures, not
    a copy of the model that could itself drift.

    Containment alone would only catch a value that points at a field the
    model no longer has. What actually matters is completeness: a new
    section-bearing field on ``ConstructDefinition`` — a fifteenth member kind
    a future revision might declare — currently has nothing forcing a
    matching ``_CONSTRUCT_MEMBER_ATTRS`` entry, so
    ``validate_construct_closure`` would silently never walk it: construct
    members of that new kind would go unvalidated with no failure, no
    refusal, and no visible gap. Asserting both directions is what makes that
    addition fail loudly instead.
    """
    construct_member_sections = frozenset(ConstructDefinition.model_fields) - _NON_MEMBER_CONSTRUCT_FIELDS
    declared_attrs = frozenset(_CONSTRUCT_MEMBER_ATTRS.values())

    assert declared_attrs <= construct_member_sections, (
        f"_CONSTRUCT_MEMBER_ATTRS names {sorted(declared_attrs - construct_member_sections)!r}, which "
        "ConstructDefinition no longer declares as a member-reference field"
    )
    assert construct_member_sections <= declared_attrs, (
        f"ConstructDefinition declares member-reference field(s) "
        f"{sorted(construct_member_sections - declared_attrs)!r} that _CONSTRUCT_MEMBER_ATTRS does not "
        "walk -- construct members of this kind are never validated for legal/source ref inclusion"
    )


def test_construct_member_attrs_keys_are_unique_diagnostic_labels() -> None:
    """The prose ``kind`` labels can't be derived (there is no enum for them), but they
    must stay one-to-one with the member-reference fields: a duplicate or missing label
    would make ``member_objects[kind]`` ambiguous or unreachable for the field it names.
    """
    assert len(_CONSTRUCT_MEMBER_ATTRS) == len(set(_CONSTRUCT_MEMBER_ATTRS.values()))
