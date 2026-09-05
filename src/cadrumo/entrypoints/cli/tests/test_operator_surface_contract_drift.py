"""Live-tree drift gate for the backend-owned ``OperatorSurfaceContract``.

Schema registration proves each CLI leaf can emit a declared shape. This
gate proves the other half: that the
:class:`~cadrumo.application.operator_surface.OperatorSurfaceContract` — the source
external command inventories are built from —
declares *exactly* the mounted command families and their sub-verbs.

Without this gate the contract is self-referential: the sibling
``test_required_children_match_mounted_command_families`` checks the contract
against itself, and the manifest tests check it against the same
contract. Neither resolves the real Typer tree, so a whole family
(``config google``, ``config check``, ``config reset``) or a sub-verb (every
``app live`` child but ``filed``) could be — and was — absent from the manifest
while the CLI mounted it, handing an agent an authoritative-looking tool map with
holes.

The gate forces every lazily-registered subtree to materialise, walks the two
pinned roots two levels deep, and computes the symmetric difference between the
live ``root -> family -> sub-verb`` surface and the contract's declaration. The
difference must be empty. There is no allowlist: a new family or sub-verb that
lands without a contract update reds this gate (and is therefore co-committed
with the contract by construction).
"""

from __future__ import annotations

from typing import TypeGuard, cast

import click
import pytest
from typer.main import get_command as _typer_get_command

from ....application.operator_surface.contract import get_operator_surface_contract
from ..command_suggestions import materialise_lazy_subcommands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PINNED_ROOTS: frozenset[str] = frozenset({"config", "app"})


def _is_command_group(command: click.Command) -> TypeGuard[click.Group]:
    """Return True when ``command`` is a Click group / multi-command.

    Typer vendors its own Click, so commands returned by
    :func:`typer.main.get_command` are not instances of the imported
    ``click.Group``; duck-typing on the group interface is vendor-robust.
    """
    return callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))


def _direct_children(command: click.Command) -> dict[str, click.Command]:
    """Return the directly-mounted child commands of ``command`` (empty for a leaf).

    Materialises the synthetic context so a lazy ``get_command`` resolves every
    registered subcommand, including those behind a lazy loader.
    """
    children: dict[str, click.Command] = {}
    if not _is_command_group(command):
        return children
    with click.Context(command, info_name=command.name or None) as ctx:
        for child_name in command.list_commands(ctx):
            child = command.get_command(ctx, child_name)
            if child is not None:
                children[str(child_name)] = child
    return children


def _resolve_live_surface() -> dict[str, dict[str, frozenset[str]]]:
    """Resolve ``{root: {family-child: frozenset(sub-verb)}}`` from the live tree.

    For a family whose child is a group with sub-commands, the sub-verb set is its
    direct child names. For a family whose child is a leaf command (or an
    ``invoke_without_command`` group with no registered leaf, e.g. ``app quickfile``),
    the sub-verb set is the degenerate self-reference ``{child}`` — matching the
    contract's convention of summarising such a verb as ``commands=(child,)``.
    """
    from .. import app as live_app

    materialise_lazy_subcommands(live_app)
    root = _typer_get_command(live_app)
    root.name = live_app.info.name or "cadrumo"

    surface: dict[str, dict[str, frozenset[str]]] = {}
    for root_name, root_cmd in _direct_children(cast(click.Command, root)).items():
        if root_name not in _PINNED_ROOTS:
            continue
        families: dict[str, frozenset[str]] = {}
        for child_name, child_cmd in _direct_children(root_cmd).items():
            sub_verbs = frozenset(_direct_children(child_cmd))
            families[child_name] = sub_verbs or frozenset({child_name})
        surface[root_name] = families
    return surface


def _declared_families() -> dict[str, frozenset[str]]:
    """Resolve ``{root: frozenset(family-child)}`` from the contract."""
    declared: dict[str, set[str]] = {}
    for family in get_operator_surface_contract().command_families:
        declared.setdefault(family.root.value, set()).add(family.child)
    return {root: frozenset(children) for root, children in declared.items()}


def test_operator_surface_contract_covers_the_live_tree() -> None:
    """The contract declares exactly the mounted families.

    Symmetric difference, no allowlist: a ``root -> child`` group/leaf mounted
    by the CLI but absent from ``command_families`` (the agent's manifest would
    omit it), or a contract family with no live mount (a dead manifest entry).

    The sub-verb half of this gate is gone because its subject is gone. A family
    no longer declares a command tuple to compare against — membership is derived
    from the live tree — so there is nothing left that can drift, and asserting
    a derivation against the thing it derives from would be tautological. That
    half caught real drift in both directions while it existed, which is the
    argument for deriving rather than declaring, not for keeping the assertion.

    The diagnostic names every drifted family so a regression run states the
    exact contract edit without further investigation.
    """
    live = _resolve_live_surface()
    declared = _declared_families()

    # Anti-vacuity floor. A symmetric-difference assertion over two empty maps
    # passes while checking nothing, and the lazy-Typer tree is a documented
    # false-green vector: an isinstance-gated or unmaterialised walk yields a
    # single leaf (or none) and terminates silently. Pin the resolved surface
    # against its known shape so a collapsed walk reds here rather than passing
    # a mirror of two empty inventories. The floors sit comfortably below the
    # live counts (2 roots, 23 families, 151 sub-verbs) yet far above the
    # single-leaf blind-walk failure.
    live_family_total = sum(len(families) for families in live.values())
    live_sub_verb_total = sum(len(sub) for families in live.values() for sub in families.values())
    assert set(live) == _PINNED_ROOTS, f"live surface did not resolve both pinned roots: {sorted(live)}"
    assert live_family_total >= 20, (
        f"live tree resolved only {live_family_total} families; the lazy walk likely collapsed"
    )
    assert live_sub_verb_total >= 120, (
        f"live tree resolved only {live_sub_verb_total} sub-verbs; the lazy walk likely collapsed"
    )
    assert declared, "the operator-surface contract declared no families, so this gate would check nothing"

    lines: list[str] = []
    for root in sorted(set(live) | set(declared)):
        live_families = frozenset(live.get(root, {}))
        declared_families = declared.get(root, frozenset())

        families_missing = sorted(live_families - declared_families)
        families_orphan = sorted(declared_families - live_families)
        if families_missing:
            lines.append(f"[{root}] families mounted by the CLI but ABSENT from the contract: {families_missing}")
        if families_orphan:
            lines.append(f"[{root}] contract families with NO live CLI mount: {families_orphan}")

    assert not lines, "OperatorSurfaceContract drifted from the live CLI tree:\n" + "\n".join(lines)
