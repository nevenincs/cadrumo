"""Every gate that decides a deletion weighs the operator authorisation.

``ProfileCustodyHoldAssessment.permits_local_deletion`` is the RAW owner fact
and is deliberately override-blind: the evidence record must keep saying a
filing hold exists when one does, because an override is a decision about that
fact rather than a different fact.

That split is only safe while nothing gating a deletion reads the raw property.
A gate that did would silently refuse an authorisation the sibling gate honours
-- which is exactly the defect this design replaced, where the reset's own
backstop let a recorded override past and the custody transaction did not.

So the invariant is mechanical: the raw property has no production caller, and
every decision runs through :func:`hold_permits_local_deletion`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = Path(__file__).resolve().parents[3]
_OWNING_MODULE = "_custody_hold_models.py"


def _production_modules() -> list[Path]:
    return [path for path in _SRC_ROOT.rglob("*.py") if "tests" not in path.parts and path.name != _OWNING_MODULE]


def _reads_the_raw_property(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.Attribute) and node.attr == "permits_local_deletion" for node in ast.walk(tree))


def test_no_production_site_reads_the_raw_hold_property() -> None:
    """The raw fact is for recording, never for deciding.

    Scoped to production only: tests legitimately assert the owner fact
    directly, which is what makes it a fact worth attesting.

    Known limit, stated rather than discovered later: this reads attribute
    access, so a ``getattr(obj, "permits_local_deletion")`` built from a string
    is invisible to it. That is the same blind spot every AST scan in this tree
    carries, and closing it would mean matching on a name in arbitrary string
    literals -- noisier than the defect it would catch.
    """
    offenders = [
        str(path.relative_to(_SRC_ROOT))
        for path in _production_modules()
        if _reads_the_raw_property(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert offenders == [], (
        "these production sites read the override-blind hold property directly; "
        f"route them through hold_permits_local_deletion instead: {offenders}"
    )


def test_the_decision_function_refuses_a_legal_hold_regardless_of_authorisation() -> None:
    """A legal hold is absolute; a filing hold is what an override clears.

    Both halves asserted together on purpose. Split apart, a change that made
    the override clear everything would leave one of them green.
    """
    from datetime import UTC, datetime
    from uuid import UUID

    from .._custody_hold_models import (
        ProfileCustodyHoldAssessment,
        ProfileCustodyRetentionOverride,
        hold_permits_local_deletion,
    )

    def _assessment(*, legal: bool, filing: bool) -> ProfileCustodyHoldAssessment:
        return ProfileCustodyHoldAssessment(
            profile_id=UUID("41414141-4141-4141-8141-414141414141"),
            legal_hold=legal,
            filing_hold=filing,
            assessed_at=datetime.now(UTC),
            evidence_digest="sha256:" + "a" * 64,
        )

    override = ProfileCustodyRetentionOverride(
        reason="Court order requiring erasure before the statutory retention date.",
        approved_at=datetime.now(UTC),
        retained_record_count=1,
    )

    assert hold_permits_local_deletion(_assessment(legal=False, filing=True), retention_override=override) is True
    assert hold_permits_local_deletion(_assessment(legal=False, filing=True), retention_override=None) is False
    assert hold_permits_local_deletion(_assessment(legal=True, filing=False), retention_override=override) is False
    assert hold_permits_local_deletion(_assessment(legal=True, filing=True), retention_override=override) is False
