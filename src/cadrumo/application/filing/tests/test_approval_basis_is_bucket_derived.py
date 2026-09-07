"""A durable approval basis is stamped from the bucket, never from an override.

:func:`~cadrumo.application.filing.draft_review.compute_current_approval_basis`
takes optional overrides for five of its eight axes. Each one exists for a test
approving against a sentinel bucket, and each one is a trap for production code,
because the recomputation that later decides whether an approval has aged out
self-loads every axis from the bucket. An override supplied at approval time and
absent at refresh time makes that axis disagree by construction, and the
disagreement does not surface until a draft is stored and read back.

That is not hypothetical. The filing workflow gate stamped the basis against a
transient empty ``TransactionCatalogue``; once approved drafts were persisted and
the review queue began recomputing their verdict, every stored draft in a bucket
with a ledger reported an aged-out approval on its first read -- a permanent
high-severity row that is always wrong. Nothing failed while either half stood
alone, which is why the invariant belongs to the pair rather than to either
function.

The rule is therefore symmetric and absolute for production: no shipped call to
the approval or staleness entry points may pass a basis override. Both sides then
derive the same axes the same way, and a difference between them means the bucket
really did move.

Passing the keyword at all is the offence, ``=None`` included. Spelling an
override out says the caller believes it controls that axis, and the value a
caller passes today is the one it stops passing tomorrow; the honest way to
self-load is to omit the argument.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Keyword arguments that replace an axis the refresh always self-loads.
_BASIS_OVERRIDES = frozenset(
    {
        "transaction_catalogue",
        "invoice_catalogue",
        "prior_filing_observations_fingerprint",
        "profile_activity_fingerprint",
        "category_profiles",
    },
)

#: The entry points whose basis must be comparable across a store and a reload.
_BASIS_CALLERS = frozenset(
    {
        "approve_draft",
        "refresh_review_status",
        "approval_stale_reasons",
        "compute_current_approval_basis",
    },
)

_SOURCE_ROOT = Path(__file__).resolve().parents[3]


def _overrides_in(source: str, module: str) -> list[str]:
    """Return one entry per basis override passed to a basis entry point."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if called not in _BASIS_CALLERS:
            continue
        for keyword in node.keywords:
            if keyword.arg in _BASIS_OVERRIDES:
                found.append(f"{module}:{node.lineno} {called}({keyword.arg}=...)")
    return found


def _shipped_modules() -> list[Path]:
    return [
        path
        for path in sorted(_SOURCE_ROOT.rglob("*.py"))
        if "tests" not in path.parts and "__pycache__" not in path.parts and not path.name.startswith("test_")
    ]


def test_no_shipped_module_stamps_a_basis_from_an_override() -> None:
    offenders: list[str] = []
    for path in _shipped_modules():
        # the defining module declares the parameters and forwards them; it is
        # the boundary the rule protects, not a caller that can violate it
        if path.name == "draft_review.py":
            continue
        offenders.extend(_overrides_in(path.read_text(encoding="utf-8"), path.name))
    assert offenders == []


def test_the_scan_reaches_the_real_approval_call_sites() -> None:
    """Without this a silent pass could mean the scan matched nothing at all."""
    seen = 0
    for path in _shipped_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            called = getattr(getattr(node, "func", None), "id", None)
            if isinstance(node, ast.Call) and called == "approve_draft":
                seen += 1
    assert seen >= 2


@pytest.mark.parametrize("override", sorted(_BASIS_OVERRIDES))
def test_a_planted_override_is_detected(override: str) -> None:
    planted = f"def go():\n    approve_draft(draft, bucket_id=b, {override}=X())\n"
    assert _overrides_in(planted, "planted.py")


def test_an_approval_without_overrides_is_not_reported() -> None:
    """The control: the shape production is required to use must stay silent."""
    clean = "def go():\n    approve_draft(draft, bucket_id=b, approved_by=a, schema_provider=s)\n"
    assert _overrides_in(clean, "clean.py") == []
