"""Refuse a refusal union whose members production can never emit.

A discriminated union advertises the outcomes a caller must handle. When a
member has no production construction, the contract promises an outcome the
assembler cannot produce: every consumer writes a branch that never runs, and
a reader inspecting the type sees a capability the system does not have.

WHY GREEN TESTS DID NOT CATCH IT. Both dead members ARE constructed -- by
hand, in test modules, which then assert on them and pass. A reachability
defect hides most reliably behind tests that construct their own subject,
because passing tests over a type read as evidence the type is live. Counting
constructions therefore has to exclude the test tree, or it measures the
tests rather than the system.

This gate does not decide what to do about a dead member; that adjudication
is per-member and cannot be mechanised. It requires only that the answer be
WRITTEN DOWN, so an unreachable member is a recorded decision rather than an
unnoticed one.

See Also:
    :mod:`cadrumo.tests._lost_test_hook`
        The other reporter in this family, for a run whose verdict covers
        less than it appears to.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from ..workspace_models import ModeloWorkspaceEvidenceFactValueV1, ModeloWorkspaceRefusalV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]

_ADJUDICATED_UNREACHABLE: dict[str, str] = {
    "ModeloWorkspaceCountFactValueV1": (
        "Case (a) SUSPECTED, not established -- and the distinction is the ruling. "
        "Adjudicated 2026-08-31 by searching for the decision that introduced the "
        "three-member fact-value discriminator: no ADR mandates a count fact, no "
        "consumer dispatches on fact kind, and the type arrived in a broad "
        "feat(application) commit rather than a decision. The one fact production "
        "emits is a TextFactValue carrying a work_unit_id. That is a thorough "
        "NEGATIVE, which is weaker than the positive mandates behind the refusal "
        "members above: it points to speculative generality and therefore to "
        "deletion, but absence of a decision is not a decision to delete. The owner "
        "rules; this entry records that the question was asked and what was found."
    ),
    "ModeloWorkspaceFlagFactValueV1": (
        "Case (a) SUSPECTED, not established -- identical evidence and identical "
        "reasoning to ModeloWorkspaceCountFactValueV1, with which it must be ruled "
        "as a pair: they are the two unproduced arms of one three-member "
        "discriminator, and deleting one alone would leave a two-member union that "
        "is no more grounded than the three-member one."
    ),
    "ModeloWorkspaceVersionRefusalV1": (
        "Case (a), the check was intended and never written. Every contract_version "
        "field on the Workspace models is pinned to Literal[1], so a version mismatch "
        "cannot currently be REPRESENTED, let alone detected and refused. That is a gap "
        "on a versioned contract rather than dead weight: the type is correct and "
        "waiting for the second version that gives it something to refuse. Deleting it "
        "would remove the only declared handling for the first real version bump."
    ),
    "ModeloWorkspaceRevisionMismatchRefusalV1": (
        "Case (a), same shape, measured 2026-08-31. resolve_modelo_workspace_revision_axes "
        "COMPUTES the mismatch -- it fills a MISMATCHED disposition for the requested and "
        "stored sources against the law-selected revision -- and its docstring names this "
        "type as what the assembly layer carries it into. The assembler never constructs "
        "it, and no production code reads either assertion's disposition: every consumer "
        "of requested_revision_assertion and stored_revision_assertion is a test. So a "
        "divergence between a stored revision and the law-selected one is computed, "
        "attached to the resolved target as typed data, and read by nobody. Do not delete "
        "the type on that evidence; the missing piece is the emit, not the contract."
    ),
}
"""Union members with no production construction, and the ruling on each.

NOT an allowlist and NOT a permanent exemption. An entry records that someone
asked the three-way question the reachability finding demands -- the check was
intended and never written, the refusal is unreachable by construction, or it
is reachable by a different path -- and wrote the answer down. Removing an
entry once its member becomes reachable is the intended lifecycle; adding one
to silence a newly-dead member without answering the question is not.
"""


_GOVERNED_UNIONS = (ModeloWorkspaceRefusalV1, ModeloWorkspaceEvidenceFactValueV1)
"""Every discriminated union this gate holds to reachability.

Both advertise outcomes a caller must branch on, so both carry the same defect
when a member has no producer. Held in ONE gate rather than a second one per
union: a per-union copy would need its own ruling register, and two registers
for one question is how a member ends up adjudicated in the place nobody reads.
"""


def _union_member_names() -> tuple[str, ...]:
    """Return every governed union's arms, read from the aliases rather than restated.

    Each is a PEP 695 alias wrapping an ``Annotated`` discriminated union, so
    reaching the arms means unwrapping twice. Read rather than listed, because
    a literal copy would be a second definition that agrees with the union only
    until someone adds a member -- and a member added to the union but not to
    the copy is exactly the unreachable arm this gate exists to notice.
    """
    names: list[str] = []
    for alias in _GOVERNED_UNIONS:
        annotated = getattr(alias, "__value__", alias)
        union = get_args(annotated)[0]
        names.extend(arm.__name__ for arm in get_args(union))
    return tuple(dict.fromkeys(names))


def _production_construction_counts() -> dict[str, int]:
    """Count constructions of each union member outside the test tree."""
    members = dict.fromkeys(_union_member_names(), 0)
    for path in _PACKAGE_ROOT.rglob("*.py"):
        parts = path.as_posix()
        if "/tests/" in parts or path.name.startswith("test_") or path.name == "conftest.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):  # pragma: no cover - a peer's in-flight edit
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in members:
                members[node.func.id] += 1
    return members


def test_every_refusal_union_member_is_either_emitted_or_adjudicated() -> None:
    """A member production never builds must carry a written ruling.

    Asserted in BOTH directions, because a one-way check degrades into
    decoration: a member that becomes dead must fail, and an adjudication
    that outlives the deadness it explains must fail too. Without the second
    direction the ruling set only ever grows, and a stale entry silently
    exempts a member that has since become reachable.
    """
    counts = _production_construction_counts()
    assert counts, "no union members were resolved; this gate would pass vacuously"

    unadjudicated = sorted(
        name for name, count in counts.items() if count == 0 and name not in _ADJUDICATED_UNREACHABLE
    )
    assert not unadjudicated, (
        "refusal union member(s) have no production construction and no ruling. The union "
        "advertises an outcome the assembler cannot emit, so every consumer's branch for it is "
        "dead. Answer the three-way question -- intended-but-unwritten, unreachable by "
        "construction, or reachable by another path -- and record it:\n  " + "\n  ".join(unadjudicated)
    )

    stale = sorted(name for name in _ADJUDICATED_UNREACHABLE if counts.get(name, 0) > 0)
    assert not stale, (
        "member(s) are recorded as unreachable but production now constructs them. Remove the "
        "ruling rather than leaving it to exempt a member it no longer describes:\n  " + "\n  ".join(stale)
    )


def test_the_reachability_count_ignores_the_tests_that_hid_the_defect() -> None:
    """The counter must not be satisfied by a test constructing its own subject.

    This is the anti-tautology proof for the gate above. Both dead members are
    constructed in test modules and asserted on, which is exactly why they read
    as live for as long as they did. If the counter ever included the test tree,
    every member would count as reachable and the gate above would pass while
    measuring nothing.
    """
    counts = _production_construction_counts()

    assert counts["ModeloWorkspaceDomainRefusalV1"] > 0, (
        "the one genuinely emitted member counts as zero, so the counter is not seeing production"
    )
    for member in _ADJUDICATED_UNREACHABLE:
        assert counts[member] == 0, (
            f"{member} counts as constructed, but its only constructions are in test modules; "
            "the counter has started including the test tree and no longer measures reachability"
        )
