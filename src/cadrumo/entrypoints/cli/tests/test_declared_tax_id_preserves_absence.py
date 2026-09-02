"""The declared-identity read must preserve absence where the projection fabricates.

contract: ``declared_tax_id`` returns the empty string for a profile that
declares no ``identity.tax_id``, while ``projection_for_taxpayer`` substitutes a
synthetic placeholder NIF for the same record. The divergence is the point: the
filing-record import path compares the operator's identity against stored AEAT
justificante metadata, and its refusal for a missing identity
(``application.modelo.errors.external_import_tax_id_missing``) fires only on a
falsy value. Routed through the projection that refusal was unreachable, because
the placeholder is never falsy.

These drive the real helper over real ``UserProfileRecord`` values and the real
projection; nothing is stubbed.
"""

from __future__ import annotations

import pytest

from ....application.user_profile.projections import projection_for_taxpayer
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._common import declared_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: A fixed, valid profile UUID4. The record model enforces the UUID grammar, so
#: the value is pinned here rather than generated: these assertions are about the
#: identity fact, and a random id would add a moving part they do not need.
_PROFILE_ID = "3f2a9c14-8b7d-4e21-9f60-5c1a7d3e8b42"


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=facts,
    )


def test_declared_tax_id_returns_the_declared_value() -> None:
    """A declared identity is returned verbatim."""
    record = _record(UserProfileFact(path="identity.tax_id", value="12345678Z"))
    assert declared_tax_id(record) == "12345678Z"


def test_declared_tax_id_is_empty_when_the_fact_is_absent() -> None:
    """An undeclared identity surfaces as absence, not as a substituted value."""
    assert declared_tax_id(_record()) == ""


def test_declared_tax_id_is_empty_for_no_record_at_all() -> None:
    """No active profile is absence too, and must not raise."""
    assert declared_tax_id(None) == ""


def test_projection_fabricates_where_the_declared_read_preserves_absence() -> None:
    """The two reads disagree for an undeclared identity, and that is the defect being fixed.

    Asserted against the real projection rather than a copy of its default, so a
    change to the placeholder keeps this test honest: what matters is that the
    projection yields a truthy NIF nobody declared while the declared read does
    not, whatever that NIF happens to be.
    """
    empty = _record()

    projected = projection_for_taxpayer(empty).tax_id
    declared = declared_tax_id(empty)

    assert projected, "the projection is expected to substitute a placeholder NIF"
    assert declared == "", "the declared read must not substitute anything"
    assert projected != declared, "the projection and the declared read must diverge on absence"

    # The refusal under repair keys on falsiness, so state that consequence directly.
    assert not declared.strip(), "the declared read must reach the import guard as falsy"
    assert projected.strip(), "the projection would have reached that guard as truthy, skipping it"


def test_declared_tax_id_strips_surrounding_whitespace() -> None:
    """A whitespace-only identity is absence, not a declared value."""
    assert declared_tax_id(_record(UserProfileFact(path="identity.tax_id", value="   "))) == ""
    assert declared_tax_id(_record(UserProfileFact(path="identity.tax_id", value=" 12345678Z "))) == "12345678Z"
