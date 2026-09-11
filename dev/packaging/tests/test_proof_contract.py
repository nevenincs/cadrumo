"""Static and behavioural gates for the derived proof-manifest mechanism.

The manifest's ``checks`` used to be a hand-written literal, which is
unfalsifiable by construction: the split form claimed a corpus-binary shedding
check and a companion size cap that its ``main()`` never ran. Claims are now
DERIVED from a ledger each assertion writes as it executes, and each form
DECLARES the contract it must satisfy. These gates hold both halves.

The static half was itself blind to the class it screens for. It asked whether
a ``record_proof`` call naming a claim EXISTS in the module's AST, never
whether that call can run, so four recordings sitting after a ``return`` in
``smoke_dev`` counted as backing the four claims the lane declares. The gate
whose whole subject is "a claim with no assertion behind it" could not see an
assertion that cannot execute. Unreachable statements are excluded now, and the
teeth for that are below.

Its population had the same shape of hole. The corpus was globbed
``smoke_*.py``, which does not match ``all_extra_smoke.py`` -- a lane that
declares claims through its own ``declared_claims`` helper -- so the one lane
whose name and whose declaration spelling both sit outside the convention was
checked by neither the parametrize nor the declaration reader.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import iter_directory

from ..lane_verification_core import write_smoke_manifest
from ..proof_ledger import (
    ProofContractError,
    record_proof,
    recorded_proofs,
    reset_proof_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PACKAGING = Path(__file__).resolve().parents[1]
# Modules that record proofs on behalf of the forms that call them.
_RECORDING_SUPPORT = ("lane_verification_core.py", "python_cohort.py")


def _unreachable_nodes(tree: ast.AST) -> set[int]:
    """Return the ids of every node the interpreter can never reach.

    A statement list stops executing at its first ``return``, ``raise``,
    ``continue`` or ``break``; everything after that in the SAME list is dead,
    along with everything nested inside it. That is the whole rule, and it is
    deliberately no wider: a conditional early return does not kill the
    statements after the ``if``, and claiming otherwise would report live
    recordings as dead.
    """
    dead: set[int] = set()
    terminators = (ast.Return, ast.Raise, ast.Continue, ast.Break)
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            terminated = False
            for statement in block:
                if terminated:
                    dead |= {id(child) for child in ast.walk(statement)}
                elif isinstance(statement, terminators):
                    terminated = True
    return dead


def _recorded_claims(tree: ast.AST) -> set[str]:
    """Return every claim string a REACHABLE ``record_proof`` call can emit.

    Reachability is the load-bearing word, and its absence is how this gate
    passed over ``smoke_dev``: four ``record_proof`` calls stood after the
    function's ``return``, the AST held all four strings, and the module's
    declared claims all looked backed. A call that cannot run records nothing,
    so counting it here is the same over-claim the gate exists to refuse, made
    by the gate.
    """
    dead = _unreachable_nodes(tree)
    return {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "record_proof"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and id(node) not in dead
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
        # A lane may build its contract in a helper instead of at the call
        # site. ``all_extra_smoke`` does, and reading only the two spellings
        # above made its whole declaration invisible -- the lane passed this
        # gate by declaring nothing the gate could see.
        is_declared_helper = isinstance(node, ast.FunctionDef) and node.name == "declared_claims"
        if is_declared_assign or is_declared_kwarg or is_declared_extend or is_declared_helper:
            # A helper's own docstring is prose about the contract, not a
            # claim in it. Excluded by NODE identity rather than by value, so
            # a docstring that happens to quote a real claim still leaves that
            # claim declared wherever it is genuinely listed.
            leading = node.body[0] if isinstance(node, ast.FunctionDef) and node.body else None
            skip = (
                {id(leading.value)}
                if isinstance(leading, ast.Expr) and isinstance(leading.value, ast.Constant)
                else set()
            )
            declared |= {
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in skip
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


#: Both name orders a lane module in this package uses. ``smoke_*.py`` alone
#: held eight of the nine and dropped ``all_extra_smoke``.
_LANE_PATTERNS = ("smoke_*.py", "*_smoke.py")


def _lane_modules() -> list[str]:
    """Return every packaging smoke-lane module name, in both name orders."""
    return sorted({path.name for pattern in _LANE_PATTERNS for path in iter_directory(_PACKAGING, pattern=pattern)})


#: Below this the smoke-lane discovery has stopped finding its subject. A
#: floor, not a pinned count: nine lanes ship today.
_MINIMUM_SMOKE_LANES = 4


def test_the_smoke_lane_corpus_is_discovered() -> None:
    """An empty parametrize does not fail the gate below - it DELETES it.

    The corpus is a glob over the lane naming convention. A lane renamed out
    of that shape does not become a failing case; it becomes a case pytest
    never generates, so the run is quietly one test shorter and no result says
    which lane stopped being checked. That is worse than an empty walk, which
    at least reports a passing test.

    That is not hypothetical: it is what happened to ``all_extra_smoke``, whose
    name puts the word last. Both orders are globbed now, and the case below
    pins the lane rather than a tally.

    The gate it protects is the static half of the proof contract: a form may
    not promise a proof no assertion records. With the parametrize empty, every
    form could over-claim freely.
    """
    lanes = _lane_modules()

    assert "all_extra_smoke.py" in lanes, (
        f"the lane corpus {lanes} omits `all_extra_smoke.py`, a campaign-registered lane that "
        "declares nine claims. A corpus defined by the majority name order silently excuses the "
        "minority one from the contract gate entirely."
    )
    assert len(lanes) >= _MINIMUM_SMOKE_LANES, (
        f"only {len(lanes)} smoke lane(s) were discovered under {_PACKAGING}; below this the "
        "claim gate parametrises over nothing and silently stops existing"
    )


@pytest.mark.parametrize("module", _lane_modules())
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


def test_a_recording_after_a_return_does_not_back_a_claim() -> None:
    """Teeth for the reachability rule, on the exact shape that defeated it.

    ``smoke_dev._sync_dev_environment`` carried four ``record_proof`` calls
    below its ``return``. The module's AST held all four claim strings, so the
    gate read them as backed and the lane -- which declares them and would
    therefore have raised ``ProofContractError`` at the end of a full
    environment build -- passed the author-time check that exists to catch
    exactly that.
    """
    source = (
        "def build():\n"
        "    run()\n"
        "    return venv\n"
        '    record_proof("dead claim")\n'
        '\ndef live():\n    record_proof("live claim")\n'
    )

    assert _recorded_claims(ast.parse(source)) == {"live claim"}


def test_a_recording_after_a_conditional_return_still_backs_its_claim() -> None:
    """The rule must not be wider than reachability, or it reports live code dead.

    A guard clause returning early is the most common shape in this package. If
    the walk treated everything after an ``if``-nested ``return`` as dead, every
    lane's real recordings would vanish and the gate would fail the whole tree.
    """
    source = 'def build():\n    if bad:\n        return None\n    record_proof("live claim")\n'

    assert _recorded_claims(ast.parse(source)) == {"live claim"}


def test_a_contract_built_in_a_helper_is_read_as_a_declaration() -> None:
    """``all_extra_smoke`` declares through a helper, and was invisible.

    Reading only ``declared = ...`` and ``declared=...`` meant a lane that
    assembles its contract in a named function declared nothing this gate could
    see, so it satisfied the over-claim check by being unreadable rather than by
    being correct.
    """
    source = (
        "def declared_claims(*, skip):\n"
        '    """Prose naming no claim."""\n'
        '    claims = ["wheel payload"]\n'
        "    if not skip:\n"
        '        claims.append("export closure")\n'
        "    return tuple(claims)\n"
    )

    assert _declared_claims(ast.parse(source)) == {"wheel payload", "export closure"}


def test_a_helper_docstring_is_prose_rather_than_a_declared_claim() -> None:
    """Otherwise every sentence in the helper's docstring becomes a promise.

    The exclusion is by node identity, so a docstring is dropped where it
    stands without also dropping the same string where it is genuinely listed.
    """
    source = 'def declared_claims():\n    """wheel payload"""\n    return ("export closure",)\n'

    assert _declared_claims(ast.parse(source)) == {"export closure"}
