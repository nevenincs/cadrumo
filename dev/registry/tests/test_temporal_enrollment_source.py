"""Literal revision enumerations are recognised and judged against the compiled registry."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from ..analysis.temporal_enrollment_findings import declaration_finding
from ..analysis.temporal_enrollment_models import (
    LiteralEnrollmentDeclaration,
    RegistryRevisionSubject,
    TemporalEnrollmentExclusionPin,
)
from ..analysis.temporal_enrollment_source import literal_enrollment_declarations, subject_is_declared
from ..compiler.authority import compiled_bundled_authority
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PATH = "dev/registry/tests/literal_fixture.py"
_FIRST_ID, _SECOND_ID = (str(revision.id) for revision in authored_revisions("390")[-3:-1])
_DECLARED_FIRST = RegistryRevisionSubject("390", _FIRST_ID)
_DECLARED_SECOND = RegistryRevisionSubject("390", _SECOND_ID)
_RETIRED = RegistryRevisionSubject("390", "1999")


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _declaration(*subjects: RegistryRevisionSubject) -> LiteralEnrollmentDeclaration:
    return LiteralEnrollmentDeclaration(_PATH, "_REVISIONS", subjects)


def _pin(subject: RegistryRevisionSubject, *, source_sha256: str = "0" * 64) -> TemporalEnrollmentExclusionPin:
    return TemporalEnrollmentExclusionPin(
        path=_PATH,
        symbol="_REVISIONS",
        modelo=subject.modelo,
        revision=subject.revision,
        source_ref="aeat-manual",
        source_sha256=source_sha256,
        reason="planted exclusion",
        reconsideration_condition="never",
    )


def test_a_declared_revision_is_recognised_and_an_undeclared_one_is_not(
    authority: ValidatedRegistryAuthority,
) -> None:
    assert subject_is_declared(_DECLARED_FIRST, authority=authority)
    assert not subject_is_declared(_RETIRED, authority=authority)


def test_a_collection_naming_a_declared_revision_is_an_enrolment(authority: ValidatedRegistryAuthority) -> None:
    source = f'_REVISIONS = (("390", "{_FIRST_ID}"), ("390", "1999"))\n_OTHER = 3\n'

    (declaration,) = literal_enrollment_declarations(source, path=_PATH, authority=authority)

    assert declaration.symbol == "_REVISIONS"
    assert declaration.subjects == (_DECLARED_FIRST, _RETIRED)


@pytest.mark.parametrize(
    "source",
    [
        # Shape alone is not enough: no row names a revision the registry declares.
        '_REVISIONS = (("390", "1999"), ("390", "1998"))\n',
        # A modelo keyed to a design filename is not a revision.
        '_DESIGNS = {("390", "design.pdf"): 1}\n',
        # A computed value is not a literal enumeration.
        "_REVISIONS = tuple(range(3))\n",
    ],
)
def test_a_collection_that_names_no_declared_revision_is_not_an_enrolment(
    source: str, authority: ValidatedRegistryAuthority
) -> None:
    assert literal_enrollment_declarations(source, path=_PATH, authority=authority) == ()


def test_a_collection_matching_its_denominator_has_no_finding(authority: ValidatedRegistryAuthority) -> None:
    finding = declaration_finding(
        _declaration(_DECLARED_FIRST, _DECLARED_SECOND),
        expected=frozenset({_DECLARED_FIRST, _DECLARED_SECOND}),
        authority=authority,
        pins=(),
    )

    assert finding is None


def test_missing_extra_duplicate_and_retired_rows_are_each_reported(authority: ValidatedRegistryAuthority) -> None:
    finding = declaration_finding(
        _declaration(_DECLARED_FIRST, _DECLARED_FIRST, _RETIRED),
        expected=frozenset({_DECLARED_FIRST, _DECLARED_SECOND}),
        authority=authority,
        pins=(),
    )

    assert finding is not None
    assert finding.missing == (_DECLARED_SECOND,)
    assert finding.extra == (_RETIRED,)
    assert finding.duplicates == (_DECLARED_FIRST,)
    assert finding.absent == (_RETIRED,)


def test_a_pin_whose_source_no_longer_matches_is_dormant(authority: ValidatedRegistryAuthority) -> None:
    finding = declaration_finding(
        _declaration(_DECLARED_FIRST),
        expected=frozenset({_DECLARED_FIRST}),
        authority=authority,
        pins=(_pin(_DECLARED_SECOND), _pin(_DECLARED_SECOND)),
    )

    assert finding is not None
    assert finding.dormant_pins == (_DECLARED_SECOND, _DECLARED_SECOND)
    assert finding.duplicate_pins == (_DECLARED_SECOND,)
    assert finding.missing == ()
