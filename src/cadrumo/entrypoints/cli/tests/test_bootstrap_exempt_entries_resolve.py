"""Gate: every bootstrap exemption, and every claim it makes, holds against the tree.

An exemption is matched by command chain, so an entry naming a verb that does
not exist is not merely dead. It is armed: register a verb under that name
later and it silently inherits an exemption from the active-profile session
gate that nobody consciously granted. Six such entries accumulated once, and
the one that mattered was profile deletion.

Nothing detected them, because an exemption list is data that only participates
when a matching verb is dispatched — an entry for an absent verb is never
consulted and therefore never wrong at runtime.

The companion failure is that an entry can be correct while its stated REASON
has gone false, and a reader then inherits the reason instead of re-deriving
it. Three instances are on record: a reason citing a deleted test, a reason
asserting a plaintext manifest read that had stopped happening, and a reason
describing a "pair" of catalogue verbs after one of the two was deleted. The
registry now carries those claims as fields rather than prose, and this module
checks them:

- the entry's own verb resolves, by the same walk dispatch performs;
- every verb the reason cites resolves;
- every test the reason cites exists;
- a PREFIX entry's live subtree equals the subtree it declares, so a verb added
  under an exempt prefix cannot inherit the exemption silently;
- a read-only claim about the operator-surface contract matches the contract.

What is still NOT checked here is the judgement in each record's ``note``. That
residue is prose and is marked as unverified where it lives. The first
membership criterion — runs on a fresh root with no session — is behavioural
rather than structural; ``test_repair_bootstrap_exempt.py`` executes it for the
recovery family, and generalising it needs a signal that distinguishes a
session refusal from an unrelated failure.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import click
import pytest
from click import Context as ClickContext
from typer.main import get_command

from ....application.operator_surface.contract import MOUNTED_COMMAND_FAMILIES
from ....application.operator_surface.models import OperatorMutability
from .. import app
from .._bootstrap_exempt import BOOTSTRAP_EXEMPTIONS, BootstrapExemption, is_bootstrap_exempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE_ROOT = Path(__file__).resolve().parents[4]
_TEST_DEF = re.compile(r"^\s*def (test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)

_PREFIX_ENTRIES = tuple(exemption for exemption in BOOTSTRAP_EXEMPTIONS if exemption.subtree)
_CITING_ENTRIES = tuple(
    exemption for exemption in BOOTSTRAP_EXEMPTIONS if exemption.cites_verbs or exemption.cites_tests
)
_READ_ONLY_CLAIMS = tuple(exemption for exemption in BOOTSTRAP_EXEMPTIONS if exemption.asserts_family_read_only)


def _root_command() -> click.Command:
    """The live command tree, typed as upstream click.

    Typer vendors its own Click fork, so ``typer.main.get_command`` is declared
    to return ``typer._click.core.Command``; it is the same object family at
    runtime as the ``click.Command`` this module walks. The cast bridges the
    static vendored/upstream duality only, as the shared CLI runner does.
    """
    return cast(click.Command, get_command(app))


def _child_of(command: click.Command, context: ClickContext, token: str) -> click.Command | None:
    """Return ``command``'s ``token`` subcommand, materialising a lazy group.

    Duck-typed rather than gated on ``isinstance(command, click.Group)``: Typer
    vendors its own Click fork, so an ``isinstance`` test against the upstream
    class silently matches nothing and would report every group as a leaf.
    """
    getter = getattr(command, "get_command", None)
    if getter is None:
        return None
    return cast("click.Command | None", getter(context, token))


def _subcommand_names(command: click.Command, context: ClickContext) -> list[str]:
    """Return ``command``'s subcommand names, empty when it is a leaf."""
    lister = getattr(command, "list_commands", None)
    if lister is None:
        return []
    return sorted(cast("list[str]", lister(context)))


def _walk(verb_path: str) -> tuple[click.Command | None, ClickContext | None]:
    """Resolve ``verb_path`` exactly as dispatch does, token by token from the root.

    Threads a fresh child context at each level so lazily-loaded subcommand
    groups materialise the way they do under a real invocation. No token is
    inferred or rewritten: the path checked is the path
    :func:`is_bootstrap_exempt` matches against, which is the operator-typed
    subcommand chain. A resolver that supplies a missing root segment would
    pass an entry that no operator can reach and that the gate can never fire
    on — the exact shape that let a dead entry survive a re-derivation pass.
    """
    command = _root_command()
    context = ClickContext(command, info_name=str(command.name))
    for token in verb_path.split():
        child = _child_of(command, context, token)
        if child is None:
            return None, None
        context = ClickContext(child, info_name=token, parent=context)
        command = child
    return command, context


def _resolves(verb_path: str) -> bool:
    """Return whether the live command tree dispatches ``verb_path``."""
    command, _context = _walk(verb_path)
    return command is not None


def _live_subtree(verb_path: str) -> tuple[str, ...]:
    """Return the leaf paths under ``verb_path``, relative to it."""
    command, context = _walk(verb_path)
    assert command is not None and context is not None, verb_path

    def _leaves(node: click.Command, ctx: ClickContext, prefix: str) -> list[str]:
        names = _subcommand_names(node, ctx)
        if not names:
            return [prefix]
        collected: list[str] = []
        for name in names:
            child = _child_of(node, ctx, name)
            if child is None:
                continue
            child_ctx = ClickContext(child, info_name=name, parent=ctx)
            collected.extend(_leaves(child, child_ctx, f"{prefix} {name}".strip()))
        return collected

    return tuple(_leaves(command, context, ""))


def _declared_test_names() -> frozenset[str]:
    """Every test function name defined anywhere under the package's test tree."""
    names: set[str] = set()
    for path in _SOURCE_ROOT.rglob("test_*.py"):
        names.update(_TEST_DEF.findall(path.read_text(encoding="utf-8")))
    return frozenset(names)


@pytest.mark.parametrize("exemption", BOOTSTRAP_EXEMPTIONS, ids=lambda e: e.verb_path)
def test_every_exemption_names_a_registered_verb(exemption: BootstrapExemption) -> None:
    """A retired verb must take its exemption with it, or the entry lies in wait."""
    assert _resolves(exemption.verb_path), (
        f"bootstrap exemption {exemption.verb_path!r} names no registered verb. Remove it with the verb: "
        "left standing, it grants a future verb of that name an unreviewed exemption from the "
        "active-profile session gate."
    )


@pytest.mark.parametrize("exemption", _CITING_ENTRIES, ids=lambda e: e.verb_path)
def test_every_cited_verb_still_resolves(exemption: BootstrapExemption) -> None:
    """A justification leaning on another verb fails when that verb is retired.

    A reason once described a "pair" of catalogue verbs months after one of the
    two had been deleted, and nothing noticed because the claim was prose.
    """
    for cited in exemption.cites_verbs:
        assert _resolves(cited), (
            f"exemption {exemption.verb_path!r} justifies itself by reference to {cited!r}, "
            "which no longer resolves. Re-derive the reason rather than inheriting it."
        )


@pytest.mark.parametrize("exemption", _CITING_ENTRIES, ids=lambda e: e.verb_path)
def test_every_cited_test_exists(exemption: BootstrapExemption) -> None:
    """A justification citing a test fails when that test is deleted.

    This is the failure that lost a security principle: a comment pointed at
    ``test_archive_export_must_stay_login_gated``, an unrelated sweep deleted
    the test, and the citation kept asserting coverage that was gone.
    """
    if not exemption.cites_tests:
        return
    declared = _declared_test_names()
    for cited in exemption.cites_tests:
        assert cited in declared, (
            f"exemption {exemption.verb_path!r} cites test {cited!r}, which does not exist. "
            "A citation that outlives what it cites states coverage the tree does not have."
        )


@pytest.mark.parametrize("exemption", _PREFIX_ENTRIES, ids=lambda e: e.verb_path)
def test_a_prefix_exemption_carries_exactly_the_subtree_it_declares(exemption: BootstrapExemption) -> None:
    """A verb added under an exempt prefix must not inherit the exemption silently.

    Prefix matching means a new leaf under an exempt group is exempt the moment
    it is registered, with no review. Pinning the declared subtree turns that
    into a red gate naming the new verb, so admitting it becomes a decision.
    """
    live = _live_subtree(exemption.verb_path)
    declared = tuple(exemption.subtree)
    assert live == declared, (
        f"the exempt prefix {exemption.verb_path!r} now carries {sorted(set(live) - set(declared))} "
        f"beyond what it declares, and no longer carries {sorted(set(declared) - set(live))}. "
        "Every leaf under an exempt prefix runs with no active-profile session: re-derive "
        "whether each still qualifies, then update the declared subtree."
    )


@pytest.mark.parametrize("exemption", _READ_ONLY_CLAIMS, ids=lambda e: e.verb_path)
def test_a_read_only_claim_matches_the_operator_surface_contract(exemption: BootstrapExemption) -> None:
    """An entry claiming its family is declared read-only must be right about that."""
    root, child = exemption.verb_path.split()[:2]
    family = next(
        (fam for fam in MOUNTED_COMMAND_FAMILIES if fam.root.value == root and fam.child == child),
        None,
    )
    assert family is not None, f"exemption {exemption.verb_path!r} names no operator-surface family"
    assert family.mutability is OperatorMutability.READ_ONLY, (
        f"exemption {exemption.verb_path!r} rests on the family being declared read-only, but the "
        f"operator-surface contract now declares it {family.mutability.value}."
    )


def test_the_gate_would_catch_an_exemption_for_an_absent_verb() -> None:
    """Anti-tautology: the check above is only evidence if a bad entry fails it.

    Every real entry passing proves nothing on its own — a resolver that
    returned ``True`` unconditionally would look identical. The bare-root case
    is the one that matters most: a resolver that infers a missing ``app``
    segment reports a root-level entry as live when no operator can type it.
    """
    assert not _resolves("config profile invented-verb")
    assert not _resolves("app modelo invented-verb")
    assert not _resolves("diagnostics")
    assert not _resolves("ledger categories")


def test_matching_stays_prefix_based_so_a_leaf_entry_does_not_carry_its_siblings() -> None:
    """A leaf exemption must not exempt the group, which is why leaves are used.

    ``app diagnostics telemetry status`` is deliberately a leaf so its sibling
    stays gated. If matching ever widened to the group, that sibling would be
    exempted silently and this pins the boundary.
    """
    assert is_bootstrap_exempt("app diagnostics telemetry status")
    assert is_bootstrap_exempt("app diagnostics telemetry status --json")
    assert not is_bootstrap_exempt("app diagnostics telemetry flush")
    assert not is_bootstrap_exempt("app diagnostics telemetry")


def test_the_matched_paths_are_derived_from_the_records() -> None:
    """The root callback and these gates must read one source of truth.

    A second hand-maintained tuple would let the checked data and the matched
    data drift, which is how an exemption escapes review.
    """
    from .._bootstrap_exempt import BOOTSTRAP_EXEMPT_VERB_PATHS

    assert tuple(exemption.verb_path for exemption in BOOTSTRAP_EXEMPTIONS) == BOOTSTRAP_EXEMPT_VERB_PATHS
    assert len(set(BOOTSTRAP_EXEMPT_VERB_PATHS)) == len(BOOTSTRAP_EXEMPT_VERB_PATHS)
