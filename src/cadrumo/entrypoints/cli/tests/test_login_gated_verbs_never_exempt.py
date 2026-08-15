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
def test_a_login_gated_verb_names_a_command_the_contract_declares(gated: LoginGatedVerb) -> None:
    """The refusal must track the surface it governs, not drift off it.

    A refusal naming a command the operator-surface contract does not declare
    is inert: whatever the surface is really called, this record no longer
    governs it. Anchoring to the declared family turns a rename into a red gate
    that names the refusal to re-derive.
    """
    tokens = gated.verb_path.split()
    assert len(tokens) >= 3, f"a login-gated path must name a root, a family and a command: {gated.verb_path!r}"
    root, child, command = tokens[0], tokens[1], tokens[2]
    family = next(
        (fam for fam in MOUNTED_COMMAND_FAMILIES if fam.root.value == root and fam.child == child),
        None,
    )
    assert family is not None, (
        f"{gated.verb_path!r} names no operator-surface family {root}.{child}. Re-derive the refusal "
        "against the surface as it is now named."
    )
    assert command in family.commands, (
        f"{gated.verb_path!r} names {command!r}, which the {root}.{child} family no longer declares. "
        f"The refusal has drifted off the surface it governs: {gated.reason}"
    )


def test_every_refusal_states_its_grounds() -> None:
    """A refusal without grounds is the shape that got deleted as noise."""
    assert LOGIN_GATED_VERB_PATHS, "the refusal registry must not be empty"
    for gated in LOGIN_GATED_VERB_PATHS:
        assert gated.reason.strip(), f"{gated.verb_path!r} refuses without stating why"
        assert len(gated.reason.split()) >= 15, (
            f"{gated.verb_path!r} states grounds too thin to survive a re-derivation pass: {gated.reason!r}"
        )
