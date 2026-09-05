"""Governance-corpus isolation gate: ``dev/`` does not consume the harness.

The decision corpus ``.vault/`` and the agent harness ``.vaultspec/`` are
removable scaffolding external to the codebase, used solely for tracking.
``dev/`` is legitimate project tooling that aids development under ``src/``.
By operator ruling the tooling tree does not read, validate or depend on the
harness: a checkout stripped of both trees must leave every ``dev/`` gate
working, and a gate that asserts something about a plan, an execution record
or a campaign index is doing the harness's job in the wrong tree.

Why this gate carries an exemption table and its ``src/`` sibling does not
---------------------------------------------------------------------------
``test_governance_corpus_isolation`` states the rule for ``src/`` with no
allowlist, and is right to: no file under ``src/`` has any reason to name the
scaffolding. Under ``dev/`` exactly one reason is legitimate, and it is not a
judgement call -- a tool that must SKIP a tree has to name it to skip it, and
the detector that enforces this very boundary has to name it to detect it.
Naming a tree in order to exclude or detect it is the opposite of depending
on it. Every other form -- reading a document, importing ``vaultspec_core``,
asserting on campaign state -- is the coupling this gate refuses.

The table is therefore shrink-only and reasoned, not an escape hatch: an entry
must say which of the two legitimate forms it is, and a file that stops
needing its entry must lose it, so the exemption set cannot quietly outlive
the exclusions that justified it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from .._paths import REPO_ROOT
from ..quality.governance_corpus_scan import (
    find_governance_path_violations,
    find_governance_prose_violations,
    live_governance_roots,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT: Final[Path] = REPO_ROOT / "dev"

#: Files permitted to name a governance tree, each with the legitimate form it
#: takes. "excludes" -- the file names the tree in order to skip it. "detects"
#: -- the file is part of the machinery enforcing this boundary. No other
#: reason is admissible; a file needing one is a file whose logic belongs in
#: the harness.
_EXEMPT: Final[dict[str, str]] = {
    "ci/tests/test_change_class_tiers.py": "excludes: the trees carry no CI change tier",
    "identity/_tree_scan.py": "excludes: the identifier scan skips generated harness data",
    "packaging/tests/test_container_base_image_singularity.py": "excludes: the trees are not packaged",
    "packaging/tests/test_packaging_quick_workflow.py": "excludes: the trees are not packaged",
    "quality/governance_corpus_scan.py": "detects: the shared boundary detector itself",
    "quality/import_hygiene_scan.py": "excludes: the tree is skipped when walking the repository",
    "quality/tests/test_doc_privacy.py": "excludes: the privacy lint scans committed text without them",
    "registry/tests/test_declaration_invariant_gates.py": "detects: refuses a vault citation in a declaration",
    "tests/_marker_metadata_patterns.py": "detects: the citation patterns the marker gate matches on",
    "tests/test_dev_governance_isolation.py": "detects: this gate, which must name what it refuses",
    "tests/test_governance_corpus_isolation.py": "detects: the sibling gate for the src/ boundary",
    "tests/test_tracked_content_excludes_transient_trees.py": "detects: refuses a transient tree in tracked content",
}


def _modules() -> list[Path]:
    """Return every scannable module under the tooling tree."""
    return [p for p in sorted(_DEV_ROOT.rglob("*.py")) if "__pycache__" not in p.parts]


def _offending_modules() -> set[str]:
    """Return the tooling modules that name a governance tree, by relative path."""
    modules = _modules()
    hits = find_governance_path_violations(modules, src_root=_DEV_ROOT)
    hits += find_governance_prose_violations(modules, src_root=_DEV_ROOT)  # ty: ignore[invalid-assignment]
    return {violation.module_path for violation in hits}


def test_the_governance_trees_are_live() -> None:
    """A gate naming trees that were renamed away would pass by vacuity."""
    assert live_governance_roots() == {".vault", ".vaultspec"}


def test_the_scanned_population_is_not_empty() -> None:
    """An empty population would make every assertion below vacuously true."""
    assert len(_modules()) > 500


def test_no_unexempted_tooling_module_names_a_governance_tree() -> None:
    """The direction the gate exists for: new coupling into the harness."""
    unexpected = sorted(_offending_modules() - set(_EXEMPT))
    assert not unexpected, (
        "dev/ must not read, validate or depend on the harness trees. "
        "If the module names a tree only to SKIP it, add it to _EXEMPT with "
        f"its reason; otherwise the logic belongs in the harness: {unexpected}"
    )


def test_no_exemption_outlives_the_exclusion_that_earned_it() -> None:
    """A spent entry would silently re-admit the file it once described."""
    spent = sorted(set(_EXEMPT) - _offending_modules())
    assert not spent, f"these entries no longer name a governance tree; remove them: {spent}"


def test_every_exemption_names_a_file_that_exists() -> None:
    """A stale path would hold an entry open for a file nothing scans."""
    missing = sorted(name for name in _EXEMPT if not (_DEV_ROOT / name).is_file())
    assert not missing, f"these exemptions name files that are gone: {missing}"


def test_every_exemption_declares_a_legitimate_form() -> None:
    """The two admissible forms are the whole content of the ruling."""
    malformed = sorted(name for name, reason in _EXEMPT.items() if not reason.startswith(("excludes:", "detects:")))
    assert not malformed, f"an exemption must declare 'excludes:' or 'detects:': {malformed}"


def test_the_gate_catches_a_planted_dependency(tmp_path: Path) -> None:
    """Detector teeth: a tooling module reading a vault document is caught."""
    planted = tmp_path / "harness_reader.py"
    planted.write_text(
        'from pathlib import Path\n\nPLAN = Path(".vault") / "plan" / "some-plan.md"\n',
        encoding="utf-8",
    )
    hits = find_governance_path_violations([planted], src_root=tmp_path)
    assert {h.module_path for h in hits} == {"harness_reader.py"}
