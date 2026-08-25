"""CI gate: a module that reads the value projection and writes facts must declare why.

``record_to_path_values`` filters out clearing facts, so a path the operator
DELIBERATELY CLEARED and a path they NEVER SET are indistinguishable in it —
both are simply absent. Reading that ambiguity is harmless: every consumer that
merely reads treats absent as "cannot conclude" or "not filled", which is the
safe direction. It only bites a module that goes on to WRITE a value at a path
it found absent, because that silently re-populates a deliberate deletion.

That was the censal reconciliation's defect, and it was the only instance across
31 read sites. The property is therefore a conjunction — read the projection AND
write a fact — and this gate enumerates the modules where both occur, requiring
each to record why its writes are safe on absence.

The check is deliberately MODULE-level rather than dataflow-level. Whether a
particular write is reached from a particular absence test is a dataflow
question, and an AST gate chasing it would miss indirection while looking
authoritative. Enumerating the intersection instead makes adding such a module a
conscious act: it fails until an author states the reason, which is the same
shape as the modelo-literal gate and the lazy-import ratchet, both of which work
by making the author declare rather than making the tool infer.

Enrolment is not an exemption. Every entry carries the reason its writes cannot
re-populate a cleared path, established by the consumer triage.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The ``src/cadrumo`` package root, which the declared keys are relative to.
_SRC_ROOT = Path(__file__).resolve().parents[3]

#: The value projection whose clear/never-set ambiguity this gate is about.
_PROJECTION = "record_to_path_values"
#: The fact constructor whose non-``None`` value is a write.
_FACT = "UserProfileFact"

#: Modules that BOTH read the projection AND construct profile facts, each with
#: the reason its writes cannot silently re-populate a deliberately cleared path.
_DECLARED_WRITERS: dict[str, str] = {
    "application/user_profile/_censo_sync.py": (
        "Reads the EFFECTIVE-FACT projection for its adoption decision, not the value "
        "projection, so a cleared path is visible as value=None and is reported as a "
        "divergence instead of adopted. Its one value-projection read is the unrelated "
        "home-office afectacion ratio, which only reads."
    ),
    "application/user_profile/_cotejo_apply.py": (
        "Writes clearing facts only for divergence paths PRESENT in the projection "
        "(namespace-replace on re-cotejo). An already-cleared row is absent, so it is "
        "not re-cleared, and no value is ever written at an absent path."
    ),
    "application/wizard/_checkpoint_store.py": (
        "Two reads, both safe. The descendant namespace-shrink clears only paths "
        "PRESENT in the projection. The resume-answer seed treats an absent path as "
        "unanswered and re-asks it, which is what clearing an answer should cause."
    ),
    "application/wizard/_persistence.py": (
        "Writes operator-supplied wizard answers, which are unconditional on what the "
        "projection holds. Its projection read is a descendant-list scan that only reads."
    ),
    "application/user_profile/_section_rows.py": (
        "Reads the projection only to choose the next repeatable-row index. Every fact "
        "comes from values the operator explicitly supplied for the new row, so absence "
        "never causes a cleared value to be re-adopted."
    ),
    "application/wizard/_commands.py": (
        "The command reads the projection only to preserve the filing baseline before "
        "its CAS command. Every resulting fact comes from an explicit wizard answer or "
        "flag, never from an absent projected value, so a cleared path is not adopted."
    ),
}


def _module_symbols(path: Path) -> tuple[bool, bool]:
    """Return whether a module reads the projection and constructs a fact."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    reads = False
    writes = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == _PROJECTION:
                reads = True
            elif name == _FACT:
                writes = True
    return reads, writes


def _intersection(root: Path) -> dict[str, tuple[bool, bool]]:
    """Return every production module under ``root`` that both reads and writes.

    Paths are keyed relative to ``root`` so the same detector runs against the
    real package and against a planted tree in the anti-tautology proof.
    """
    found: dict[str, tuple[bool, bool]] = {}
    for path in scan_directory(root, pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        reads, writes = _module_symbols(path)
        if reads and writes:
            found[path.relative_to(root).as_posix()] = (reads, writes)
    return found


def test_every_projection_reading_fact_writer_declares_why_it_is_clear_safe() -> None:
    """A module that reads the projection and writes facts must be enrolled with a reason."""
    found = set(_intersection(_SRC_ROOT))
    declared = set(_DECLARED_WRITERS)
    undeclared = sorted(found - declared)
    assert not undeclared, (
        "these modules read the value projection AND construct profile facts, so they can "
        "write a value at a path they cannot tell was deliberately cleared. Establish why "
        "each is safe and record the reason in _DECLARED_WRITERS, or read "
        f"record_to_effective_facts instead: {undeclared}"
    )
    stale = sorted(declared - found)
    assert not stale, f"declared writers that no longer read-and-write; drop them: {stale}"


def test_every_declared_reason_is_substantive() -> None:
    """An entry without a real reason is an allowlist used as a mute button."""
    for module, reason in _DECLARED_WRITERS.items():
        assert len(reason.strip()) >= 80, f"{module}: reason is too thin to be a justification"


def test_the_gate_fails_on_a_planted_adopt_on_absence_writer(tmp_path: Path) -> None:
    """Anti-tautology: an enumeration asserted empty proves nothing until it can fire.

    Plants a module with the exact defect shape — read the value projection,
    then construct a fact at a path it found absent — and asserts the detector
    reports it. Without this, the gate would pass identically if its AST walk
    silently matched nothing.
    """
    planted = tmp_path / "application" / "planted"
    planted.mkdir(parents=True)
    (planted / "_adopts_on_absence.py").write_text(
        "from cadrumo.application.user_profile import record_to_path_values\n"
        "from cadrumo.domain.user_profile import UserProfileFact\n"
        "\n"
        "def adopt(record, path, value):\n"
        "    existing = record_to_path_values(record)\n"
        "    if existing.get(path) is None:\n"
        "        return UserProfileFact(path=path, value=value)\n"
        "    return None\n",
        encoding="utf-8",
    )
    detected = _intersection(tmp_path)
    assert detected, "the detector found nothing in a tree containing a planted adopt-on-absence writer"
    assert any("_adopts_on_absence.py" in module for module in detected)


def test_the_detector_ignores_a_module_that_only_reads(tmp_path: Path) -> None:
    """The converse control: reading alone must not be flagged, or the gate is noise."""
    reader = tmp_path / "application" / "reader"
    reader.mkdir(parents=True)
    (reader / "_only_reads.py").write_text(
        "from cadrumo.application.user_profile import record_to_path_values\n"
        "\n"
        "def summarise(record):\n"
        "    return sorted(record_to_path_values(record))\n",
        encoding="utf-8",
    )
    assert _intersection(tmp_path) == {}
