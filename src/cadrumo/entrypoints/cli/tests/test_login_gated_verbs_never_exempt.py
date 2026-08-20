"""Gate: a verb whose output leaves the encrypted store stays login-gated.

**The principle.** A verb whose OUTPUT leaves the encrypted store must stay
login-gated, because a target-scoped unlock does not establish recency. The
login gate demands a session whose idle and absolute deadlines have not
elapsed. A verb that names its own target and unlocks that bucket itself
satisfies every mechanical test the target-scoped exemptions are admitted on,
and still establishes nothing about how recently the operator authenticated.
What distinguishes these verbs is their OUTPUT, not their plumbing.

**Why it is a gate and not a comment.** It was a comment. The comment justified
itself by citing ``test_archive_export_must_stay_login_gated``; an unrelated
sweep deleted that test, and a later cleanup deleted the comment along with the
block it sat in. The principle then survived nowhere in the tree, while the
mechanical admission rule that would readmit the verb survived intact. An
exemption list records what is let through; without a companion record of what
is deliberately held back, the next author who re-derives the admission rule
readmits the exception, because the exception was never expressible in that
rule.

**What this gate does not do.** It binds to declared verb paths. A rename that
the operator-surface contract carries is caught below, because each refusal is
required to name a command the contract declares; a rename that never reaches
the contract is not. That residue is the same hand-sweep discipline every verb
rename in this tree already owes the exemption list.
"""

from __future__ import annotations

import pytest

from ....application.operator_surface import MOUNTED_COMMAND_FAMILIES
from .._bootstrap_exempt import (
    BOOTSTRAP_EXEMPT_VERB_PATHS,
    LOGIN_GATED_VERB_PATHS,
    LoginGatedVerb,
    is_bootstrap_exempt,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("gated", LOGIN_GATED_VERB_PATHS, ids=lambda g: g.verb_path)
def test_a_login_gated_verb_is_never_bootstrap_exempt(gated: LoginGatedVerb) -> None:
    """The refusal holds whether or not the verb is registered yet.

    Binding to the path rather than to a live command is deliberate: the
    profile restore and export surface is being rebuilt, and the refusal has to
    be in force the moment the verb lands, not filed afterwards.
    """
    assert not is_bootstrap_exempt(gated.verb_path), (
        f"{gated.verb_path!r} was granted a bootstrap exemption. It must stay login-gated: "
        f"{gated.reason} A target-scoped unlock does not establish recency."
    )


@pytest.mark.parametrize("gated", LOGIN_GATED_VERB_PATHS, ids=lambda g: g.verb_path)
def test_no_exempt_prefix_reaches_a_login_gated_verb(gated: LoginGatedVerb) -> None:
    """A group exemption must not swallow a login-gated leaf.

    ``is_bootstrap_exempt`` matches by prefix, so exempting ``config profile``
    would carry every profile verb with it. Checking the leaf alone would miss
    that; this asserts no exempt entry is a prefix of the refused path.
    """
    swallowing = [
        exempt
        for exempt in BOOTSTRAP_EXEMPT_VERB_PATHS
        if gated.verb_path == exempt or gated.verb_path.startswith(f"{exempt} ")
    ]
    assert not swallowing, (
        f"the exempt prefix(es) {swallowing} reach {gated.verb_path!r}, which must stay login-gated. {gated.reason}"
    )


@pytest.mark.parametrize("gated", LOGIN_GATED_VERB_PATHS, ids=lambda g: g.verb_path)
def test_a_login_gated_verb_names_a_family_the_contract_declares(gated: LoginGatedVerb) -> None:
    """The refusal must track the surface it governs, not drift off it.

    A refusal hung off a family the operator-surface contract does not declare
    is inert: whatever the surface is really called, this record no longer
    governs it. Anchoring to the declared family turns a family rename into a
    red gate that names the refusal to re-derive.

    The anchor stops at the family. A family deliberately declares no command
    inventory — which verbs it contains is established solely by the live
    command tree — so a refusal naming a verb that has not been built yet, which
    is the case this registry exists to cover, cannot be anchored any deeper.
    A rename of the leaf itself is therefore still the hand sweep every verb
    rename in this tree already owes the exemption list.
    """
    tokens = gated.verb_path.split()
    assert len(tokens) >= 3, f"a login-gated path must name a root, a family and a command: {gated.verb_path!r}"
    root, child = tokens[0], tokens[1]
    family = next(
        (fam for fam in MOUNTED_COMMAND_FAMILIES if fam.root.value == root and fam.child == child),
        None,
    )
    assert family is not None, (
        f"{gated.verb_path!r} names no operator-surface family {root}.{child}. Re-derive the refusal "
        f"against the surface as it is now named: {gated.reason}"
    )


def test_every_refusal_states_its_grounds() -> None:
    """A refusal without grounds is the shape that got deleted as noise."""
    assert LOGIN_GATED_VERB_PATHS, "the refusal registry must not be empty"
    for gated in LOGIN_GATED_VERB_PATHS:
        assert gated.reason.strip(), f"{gated.verb_path!r} refuses without stating why"
        assert len(gated.reason.split()) >= 15, (
            f"{gated.verb_path!r} states grounds too thin to survive a re-derivation pass: {gated.reason!r}"
        )


#: Login-gated paths whose verb the tree does not register YET, with why.
#:
#: The registry deliberately admits these: "the refusal is what governs the
#: surface when it lands". They are recorded rather than merely tolerated so
#: that the leaf-resolution check below can hold every OTHER entry to existing,
#: and so a path that is never mounted cannot sit here unnoticed forever.
_NOT_YET_MOUNTED: dict[str, str] = {
    "config profile export": (
        "The profile export/import surface is mid-rebuild: it carries a registered result schema "
        "and no Click command. Another owner is mounting these verbs. When it lands, this entry "
        "must be removed -- the staleness check below is what forces that."
    ),
}


def _live_verb_paths() -> frozenset[str]:
    """Return every command path the materialised CLI exposes, groups included."""
    from typer._click.core import Command as ClickCommand
    from typer._click.core import Context as ClickContext
    from typer.main import get_command as typer_get_command

    from .. import app as cli_app

    root = typer_get_command(cli_app)
    found: set[str] = set()

    def walk(command: ClickCommand, context: ClickContext, path: tuple[str, ...]) -> None:
        if path:
            found.add(" ".join(path))
        lister = getattr(command, "list_commands", None)
        getter = getattr(command, "get_command", None)
        if not callable(lister) or not callable(getter):
            return
        for name in (str(child) for child in lister(context)):
            child_command = getter(context, name)
            if child_command is not None:
                walk(child_command, ClickContext(child_command, parent=context, info_name=name), (*path, name))

    walk(root, ClickContext(root, info_name=str(root.name)), ())
    return frozenset(found)


def test_the_live_walk_sees_the_real_cli() -> None:
    """ANTI-VACUITY: an empty walk would make every entry look not-yet-mounted."""
    paths = _live_verb_paths()

    assert len(paths) > 100, f"the Click walk found only {len(paths)} paths; it is not seeing the real CLI"
    assert "config profile delete" in paths, "the walk is not reaching known nested verbs"


def test_a_mounted_login_gated_verb_keeps_its_exact_leaf() -> None:
    """Close the leaf-rename residue the module docstring hands to a hand sweep.

    The family anchor above stops at ``config profile`` by design, because a
    family declares no command inventory. That leaves the leaf: rename
    ``config profile delete`` and the refusal still names a declared family,
    every assertion stays green, and the record now governs a verb path nobody
    can type -- while the mechanical admission rule is free to exempt whatever
    the verb is called now.

    That is the worst entry to lose. Its own reason says the absence of an
    exemption IS the protection, and that a wrongly-granted one costs a taxpayer
    their encrypted financial history rather than a redundant copy of it.

    Entries that name an unmounted verb are exempted BY NAME rather than by
    rule, because "does not resolve" is indistinguishable from "was renamed"
    without someone stating which.
    """
    live = _live_verb_paths()
    vanished = sorted(
        gated.verb_path
        for gated in LOGIN_GATED_VERB_PATHS
        if gated.verb_path not in live and gated.verb_path not in _NOT_YET_MOUNTED
    )

    assert not vanished, (
        f"these login-gated verbs name no live command and are not recorded as unmounted: "
        f"{vanished}. If the verb was renamed, re-point the refusal -- it currently governs a path "
        "nobody can type, leaving the mechanical exemption rule free to readmit the real one. If "
        "the verb is genuinely not built yet, record it in _NOT_YET_MOUNTED with its reason."
    )


def test_no_unmounted_record_outlives_the_verb_landing() -> None:
    """The half that rots: a record kept after its verb was mounted.

    Once the verb exists, the exemption must go, or that entry is permanently
    excused from the leaf check above -- which is precisely how the protection
    would be lost quietly on the surface currently being rebuilt.
    """
    live = _live_verb_paths()
    landed = sorted(path for path in _NOT_YET_MOUNTED if path in live)

    assert not landed, (
        f"these verbs are now mounted and must be removed from _NOT_YET_MOUNTED: {landed}. Leaving "
        "them excuses a live verb from the leaf-rename check for good."
    )


def test_every_unmounted_record_still_names_a_login_gated_verb() -> None:
    """An exemption for a path no longer in the registry excuses nothing."""
    gated_paths = {gated.verb_path for gated in LOGIN_GATED_VERB_PATHS}
    orphaned = sorted(path for path in _NOT_YET_MOUNTED if path not in gated_paths)

    assert not orphaned, f"these unmounted records name no login-gated verb: {orphaned}"
