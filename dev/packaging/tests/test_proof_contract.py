"""Static and behavioural gates for the derived proof-manifest mechanism.

The manifest's ``checks`` used to be a hand-written literal, which is
unfalsifiable by construction: the split form claimed a corpus-binary shedding
check and a companion size cap that its ``main()`` never ran. Claims are now
DERIVED from a ledger each assertion writes as it executes, and each form
DECLARES the contract it must satisfy. These gates hold both halves.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import iter_directory

from .._proof_ledger import (
    ProofContractError,
    record_proof,
    recorded_proofs,
    reset_proof_ledger,
)
from .._smoke_common import write_smoke_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PACKAGING = Path(__file__).resolve().parents[1]
# Modules that record proofs on behalf of the forms that call them.
_RECORDING_SUPPORT = ("_smoke_common.py", "python_cohort.py")


def _recorded_claims(tree: ast.AST) -> set[str]:
    """Return every claim string a ``record_proof`` call in this tree can emit."""
    return {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "record_proof"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }


def _declared_claims(tree: ast.AST) -> set[str]:
    """Return every claim string a form declares as its contract."""
    declared: set[str] = set()
    for node in ast.walk(tree):
        targets = getattr(node, "targets", [])
        is_declared_assign = isinstance(node, ast.Assign) and any(
            getattr(target, "id", "") == "declared" for target in targets
        )
        is_declared_kwarg = isinstance(node, ast.keyword) and node.arg == "declared"
        is_declared_extend = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"insert", "extend"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "declared"
        )
        if is_declared_assign or is_declared_kwarg or is_declared_extend:
            declared |= {
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            }
    return declared


def _support_claims() -> set[str]:
    """Return every claim the shared recording helpers can emit.

    Deliberately a GLOBAL allowlist, not per-form reachability: it does not ask
    whether a given form actually calls the helper that records a claim. So this
    static gate is a weaker author-time net than its name suggests — a form
    declaring ten claims and recording none in-module passes here purely on
    support. The runtime contract check is what catches a form that stops
    calling a helper it depends on; this gate catches a claim NOTHING anywhere
    can record, which is the over-claim class that started this work.
    """
    claims: set[str] = set()
    for name in _RECORDING_SUPPORT:
        claims |= _recorded_claims(ast.parse((_PACKAGING / name).read_text(encoding="utf-8")))
    return claims


#: Below this the smoke-lane discovery has stopped finding its subject. A
#: floor, not a pinned count: eight lanes ship today.
_MINIMUM_SMOKE_LANES = 4


def test_the_smoke_lane_corpus_is_discovered() -> None:
    """An empty parametrize does not fail the gate below - it DELETES it.

    The corpus is a glob pinning the ``smoke_`` prefix. A lane renamed out of
    that shape does not become a failing case; it becomes a case pytest never
    generates, so the run is quietly one test shorter and no result says which
    lane stopped being checked. That is worse than an empty walk, which at
    least reports a passing test.

    The gate it protects is the static half of the proof contract: a form may
    not promise a proof no assertion records. With the parametrize empty, every
    form could over-claim freely.
    """
    lanes = sorted(path.name for path in iter_directory(_PACKAGING, pattern="smoke_*.py"))

    assert len(lanes) >= _MINIMUM_SMOKE_LANES, (
        f"only {len(lanes)} smoke lane(s) were discovered under {_PACKAGING}; below this the "
        "claim gate parametrises over nothing and silently stops existing"
    )


@pytest.mark.parametrize("module", sorted(path.name for path in iter_directory(_PACKAGING, pattern="smoke_*.py")))
def test_every_declared_claim_has_an_assertion_that_records_it(module: str) -> None:
    """A form may not promise a proof no assertion anywhere can record.

    This is the static half. It catches the over-claim at author time, before
    a lane is ever built: the removed browser claim (a tracked shipped-data
    payload check that form never performed) fails here.
    """
    tree = ast.parse((_PACKAGING / module).read_text(encoding="utf-8"))
    unbacked = sorted(_declared_claims(tree) - _recorded_claims(tree) - _support_claims())
    assert not unbacked, f"{module} declares claims nothing records: {unbacked}"


def test_manifest_checks_come_from_the_ledger_not_the_declaration(tmp_path: Path) -> None:
    """The written claims are what RAN, so an unrecorded claim cannot appear."""
    reset_proof_ledger()
    record_proof("stdlib venv creation")
    manifest_path = write_smoke_manifest(tmp_path, lane="probe", artifacts={}, declared=("stdlib venv creation",))
    assert '"stdlib venv creation"' in manifest_path.read_text(encoding="utf-8")
    reset_proof_ledger()


def test_a_declared_proof_that_never_ran_refuses_the_run(tmp_path: Path) -> None:
    """The declared half: a form that silently stops proving something fails loudly.

    Deriving alone would let this pass with a shorter, still-truthful manifest,
    which is why both halves are required.
    """
    reset_proof_ledger()
    record_proof("stdlib venv creation")
    with pytest.raises(ProofContractError, match="never executed"):
        write_smoke_manifest(
            tmp_path,
            lane="probe",
            artifacts={},
            declared=("stdlib venv creation", "a proof no assertion ran"),
        )
    assert not (tmp_path / "packaging-smoke-manifest.json").exists(), "nothing is written on refusal"
    reset_proof_ledger()


def test_the_ledger_is_order_preserving_and_deduplicated() -> None:
    """Claims read back in execution order; a repeated assertion records once."""
    reset_proof_ledger()
    record_proof("second")
    record_proof("first")
    record_proof("second")
    assert recorded_proofs() == ("second", "first")
    reset_proof_ledger()
    assert recorded_proofs() == ()
