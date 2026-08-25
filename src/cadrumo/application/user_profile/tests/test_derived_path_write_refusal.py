"""The write door refuses a value at an engine-derived path, and only a value.

Two properties, and the second is why this module exists separately from the
end-to-end override proof.

The refusal itself: a path the schema declares derived is computed from source
facts the operator edits elsewhere, so a value written straight at it would
suppress the computation. That was demonstrated on the real calculate path
before this rule existed and is pinned there.

The exemption: a CLEAR is admitted, at a derived path and at a path the schema
does not declare at all. The validator judges the whole MERGED fact set on
every edit rather than the incoming delta, so a fact the schema no longer
accepts is re-judged on every later edit to any other field. Refusing the clear
as well leaves no way to remove it -- the profile can then not be edited,
cleared, or promoted at all, with no in-band remedy. A closing audit measured
that and this module pins the fix.

The exemption gives nothing back to the defect. The injectors compute always
and overwrite whatever the fact index holds, so a stored value at a derived
path is already inert for the calculation; both rules exist to stop a value
being written, and a clear writes none.

Assertions here read the ISSUE CODE, never merely the presence of a refusal.
Both properties above were once asserted through a helper filtered to the
derived-field code alone, and the clear was in fact being refused under a code
that filter discarded -- so the exemption's test passed over the exact state it
was written to prevent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.user_profile.validation import (
    DERIVED_FIELD_ISSUE_CODE,
    UNKNOWN_FIELD_ISSUE_CODE,
    ProfileValidationService,
)

from ....core.errors import BaseSeverity
from ....domain.user_profile.values import UserProfileFact
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"
_DERIVED_PATH = "renta_family.descendientes_minimos_aggregate_2024"
_OPERATOR_PATH = "renta_family.cotizaciones_ss_madre_2024"


def _service() -> ProfileValidationService:
    return ProfileValidationService(schema=load_user_profile_schema())


def _refusals(*facts: UserProfileFact) -> list[tuple[str, str]]:
    """Every blocking issue raised AT one of the paths under test, code and all.

    Deliberately not filtered to :data:`DERIVED_FIELD_ISSUE_CODE`. Filtering to
    the one code this module is about is what let the clear-exemption assertion
    below pass while the clear was in fact refused: the refusal arrived as
    ``unknown_field``, which the filter discarded, so the test asserted an empty
    list against a fact set that the write door was blocking. A gate that
    reports "not refused under the code I was looking for" cannot answer the
    question this module asks, which is whether the write is admitted at all.

    Scoped to the paths under test rather than to the whole report, because an
    otherwise-empty profile always carries its missing-required-field issues and
    those are a different rule, deferred in the incomplete state and pinned
    elsewhere. Severity is filtered to ERROR for the same reason: a WARNING does
    not block a write, and admitting one here would make an advisory read as a
    refusal.
    """
    report = _service().validate_facts(_PROFILE_ID, facts)
    subject_paths = {fact.path for fact in facts}
    refused: list[tuple[str, str]] = []
    for issue in report.issues:
        if issue.severity is not BaseSeverity.ERROR or issue.path not in subject_paths:
            continue
        # `path` is optional on the issue model; a refusal that named nothing
        # would be unactionable, so pin it rather than filter it.
        assert issue.path is not None, f"refusal carried no path: {issue}"
        refused.append((issue.path, issue.code))
    return refused


def test_a_value_written_at_a_derived_path_is_refused() -> None:
    """The rule's whole purpose: the law's figure cannot be displaced by a typed one.

    The CODE is asserted, not merely the refusal. The schema declares these
    namespaces as derived-selector patterns and nothing else, so an undeclared
    path refuses too -- under ``unknown_field``, which blocks equally but names
    no entry surface. Asserting only that the write was blocked would be
    satisfied by that weaker refusal.
    """
    assert _refusals(UserProfileFact(path=_DERIVED_PATH, value=Decimal("999"))) == [
        (_DERIVED_PATH, DERIVED_FIELD_ISSUE_CODE),
    ]


def test_the_refusal_names_the_surface_that_edits_the_real_facts() -> None:
    """An instructive refusal, not a bare rejection.

    The operator is being told they may not write here; without naming where the
    value actually comes from, the refusal leaves them with no next action.
    """
    report = _service().validate_facts(
        _PROFILE_ID,
        (UserProfileFact(path=_DERIVED_PATH, value=Decimal("999")),),
    )
    message = next(issue.message for issue in report.issues if issue.code == DERIVED_FIELD_ISSUE_CODE)
    assert "descendiente" in message


def test_clearing_a_derived_path_is_admitted() -> None:
    """The remedy. Without it a stale fact cannot be removed by any door.

    This is the exemption's reason for existing, and inverting it restores the
    state the closing audit measured: a profile bricked by a fact nobody can
    reach. The exemption was written on the derived branch alone and stopped
    working when the per-year field declarations were removed -- the clear then
    fell through to the field lookup and was refused as ``unknown_field``.
    """
    assert _refusals(UserProfileFact(path=_DERIVED_PATH, value=None)) == []


def test_clearing_a_path_the_schema_no_longer_declares_is_admitted() -> None:
    """The generalisation: a clear is admissible at every path, declared or not.

    A retired path reaches the same trap as a derived one and needs no rule to
    put it there. Retired declarations are deleted here rather than tolerated,
    so the first field removal against a live profile still holding a fact there
    would brick it: the merged set is judged whole on every edit, and a refusal
    of the clear leaves the fact unreachable by any door.

    Nothing the ``unknown_field`` rule protects is given back. It exists to stop
    an undeclared VALUE being stored, and a clear stores none.
    """
    assert _refusals(UserProfileFact(path="renta_family.retired_by_a_later_schema", value=None)) == []


def test_a_value_at_a_path_the_schema_does_not_declare_is_still_refused() -> None:
    """Anti-vacuity for the generalisation above: only the CLEAR is admitted.

    Admitting an undeclared clear must not become admitting undeclared writes.
    Without this, widening the exemption from ``value is None`` to the whole
    fact would leave every assertion in this module passing while the schema
    bound nothing at all.
    """
    assert _refusals(UserProfileFact(path="renta_family.retired_by_a_later_schema", value="1")) == [
        ("renta_family.retired_by_a_later_schema", UNKNOWN_FIELD_ISSUE_CODE),
    ]


def test_a_stale_valued_fact_still_blocks_an_unrelated_edit() -> None:
    """The hazard the exemption does NOT pretend to solve, pinned so it stays visible.

    The merged set is judged whole, so a stale VALUED fact refuses an edit the
    operator did not make. The recovery path is to clear it first, which the
    test above admits. Asserting this rather than leaving it undocumented is the
    difference between an accepted consequence and an unnoticed one.
    """
    assert _refusals(
        UserProfileFact(path=_DERIVED_PATH, value=Decimal("999")),
        UserProfileFact(path="identity.name", value="Ana"),
    ) == [(_DERIVED_PATH, DERIVED_FIELD_ISSUE_CODE)]


def test_a_kept_operator_field_in_the_same_section_is_untouched() -> None:
    """Anti-vacuity: the refusal must discriminate, not blanket the section.

    Two year-suffixed fields in this same section are genuine operator input and
    were deliberately not declared derived. If the pattern namespace ever widened
    to swallow them, every assertion above would still pass while a legitimate
    entry surface had been closed.
    """
    assert _refusals(UserProfileFact(path=_OPERATOR_PATH, value=Decimal("900"))) == []
