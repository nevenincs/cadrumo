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

from .._schema import ConstructDefinition
from .._validate import RegistryValidator
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

    Every one of the sixteen construct-member kinds this validator recognises
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
