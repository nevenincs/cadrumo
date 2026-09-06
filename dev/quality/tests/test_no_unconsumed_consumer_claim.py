"""Gate: a symbol nothing consumes must not name a consumer in its own prose.

A sentence like "used by the cross-period carry path" or "for the scaffold
gate" reads as evidence that a symbol is wired. Four times in this tree it was
not: the locale-key manifests written for a scaffold gate no gate reads, a
routing accessor whose named integrity gate takes its input as a parameter, a
KDF warmup constant whose loop performs no warmup, and a refund-disposition
wrapper whose carry path calls the underlying predicate directly.

The claim is worse than silence, because it answers the question a reader would
otherwise ask. This refuses a symbol that makes one while production consumes it
nowhere -- unless the ledger already names it, which is where a claim known to
be false is recorded with its evidence.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: Prose that asserts a consumer rather than describing behaviour.
_CONSUMER_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"\b(used by|read by|consulted by|consumed by|for the [a-z-]+ gate)\b", re.IGNORECASE
)


def _adjudicated() -> set[str]:
    """Return every symbol a classification cluster names."""
    data = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    names: set[str] = set()
    for cluster in data.get("symbol_cluster", ()):
        names.update(cluster.get("symbols", ()))
    return names


def _shipped_sources() -> dict[Path, str]:
    """Return every shipped non-test module source, read once."""
    sources: dict[Path, str] = {}
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            sources[path] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return sources


def claiming_symbols_without_consumers(sources: dict[Path, str]) -> list[tuple[str, str]]:
    """Return ``(name, claim)`` for definitions that assert an absent consumer."""
    offenders: list[tuple[str, str]] = []
    for path, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            claim = _CONSUMER_CLAIM.search(ast.get_docstring(node) or "")
            if claim is None:
                continue
            pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(node.name)}(?![A-Za-z0-9_])")
            uses = sum(len(pattern.findall(other)) for other_path, other in sources.items() if other_path != path)
            own = len(pattern.findall(text))
            if uses == 0 and own <= 1:
                offenders.append((node.name, claim.group(0)))
    return offenders


def test_the_scanned_population_is_not_empty() -> None:
    """An empty population would make the assertion below vacuous."""
    assert len(_shipped_sources()) > 500


def test_the_gate_still_recognises_consumer_claims() -> None:
    """A population floor is not a matches floor.

    If the claim pattern stopped matching, every symbol would pass this
    silently at once and the empty offender list would read as green.
    Counting the claims examined distinguishes nothing-is-wrong from
    nothing-was-looked-at.
    """
    seen = 0
    for text in _shipped_sources().values():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        seen += sum(
            1
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and _CONSUMER_CLAIM.search(ast.get_docstring(node) or "")
        )
    assert seen > 120, (
        f"the reader recognised only {seen} consumer claim(s); below this the "
        "pattern has drifted and this gate is inert rather than satisfied"
    )


def test_no_unconsumed_symbol_claims_a_consumer() -> None:
    """The direction the gate exists for."""
    adjudicated = _adjudicated()
    offenders = [
        f"{name} (claims {claim!r})"
        for name, claim in claiming_symbols_without_consumers(_shipped_sources())
        if name not in adjudicated
    ]
    assert not offenders, (
        "these symbols assert a consumer in their own prose and production consumes "
        "them nowhere; wire them, correct the sentence, or record the false claim in "
        f"dev/audit/reachability_classification.toml: {offenders}"
    )


def test_the_gate_catches_a_planted_false_claim(tmp_path: Path) -> None:
    """Detector teeth: prose asserting a consumer the tree does not have."""
    module = tmp_path / "subject.py"
    module.write_text(
        'def orphan() -> int:\n    """Used by the nightly reconciliation job."""\n    return 1\n',
        encoding="utf-8",
    )
    found = claiming_symbols_without_consumers({module: module.read_text(encoding="utf-8")})

    assert [name for name, _ in found] == ["orphan"]


def test_a_claim_backed_by_a_real_consumer_is_left_alone(tmp_path: Path) -> None:
    """The guard: a true sentence must not be reported."""
    module = tmp_path / "subject.py"
    module.write_text('def helper() -> int:\n    """Used by the caller beside it."""\n    return 1\n', encoding="utf-8")
    caller = tmp_path / "caller.py"
    caller.write_text("from .subject import helper\n\nVALUE = helper()\n", encoding="utf-8")
    sources = {p: p.read_text(encoding="utf-8") for p in (module, caller)}

    assert claiming_symbols_without_consumers(sources) == []


def test_a_symbol_making_no_claim_is_left_alone(tmp_path: Path) -> None:
    """Silence is not the defect; the false assertion is."""
    module = tmp_path / "subject.py"
    module.write_text('def quiet() -> int:\n    """Return one."""\n    return 1\n', encoding="utf-8")

    assert claiming_symbols_without_consumers({module: module.read_text(encoding="utf-8")}) == []
