"""The risk table agrees with the two independent risk declarations.

Two parity gates that catch a mis-declaration by cross-referencing surfaces that
declare risk-adjacent facts independently:

- The live-write tripwire: any exposed command whose leaf is ``submit`` /
  ``present`` / ``send`` MUST declare ``live_write`` - the never-live-submit axis
  is the one catastrophic-and-permanent mis-declaration, so it is cross-checked
  against the leaf as a TEST (not runtime code). Vacuously true today (no such
  verb is exposed), which is exactly the invariant it locks.
- The write-policy parity: every profile-bound WRITE verb in the runtime write
  guard (``PROFILE_BOUND_WRITE_VERB_PATHS``) maps to a command whose family is
  mutating, and no read-only-family command owns a write path - catching drift on
  BOTH the write guard and the manifest mutability (the write guard is itself
  fail-open on renames per ``cadrumo-pull-and-file-standard``).
"""

from __future__ import annotations

import pytest

from cadrumo.application.storage_write_policy import PROFILE_BOUND_WRITE_VERB_PATHS

from .._command_policy import command_policy
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIVE_WRITE_LEAVES = frozenset({"submit", "present", "send"})


def test_a_submit_present_send_leaf_must_declare_live_write() -> None:
    for descriptor in build_tool_descriptors():
        leaf = descriptor.command_key.rsplit(".", 1)[-1]
        if leaf in _LIVE_WRITE_LEAVES:
            policy = command_policy(descriptor.command_key)
            assert policy.live_write, (
                f"{descriptor.command_key} has a live-write leaf but does not declare live_write - "
                "the never-live-submit block would not fire"
            )


def test_the_destructive_axis_separates_a_status_verb_from_its_destructive_siblings() -> None:
    """Inside one mutating family, ``destructive`` is what distinguishes the verbs.

    Mutability is declared per FAMILY, so a status verb inside a mutating
    family is NOT read-only: ``config.reset.status`` reports
    ``read_only=False`` exactly as ``start`` and ``resume`` do. Reading the
    read-only flag as the separator therefore gets this family wrong, and an
    agent deciding whether to ask a human before running a reset verb needs
    the separation that does exist.

    That separation is the destructive axis, and this pins it: a status read
    is non-destructive while starting and resuming a reset are destructive.
    Both halves are asserted, so the case fails if the family collapses in
    either direction - if status became destructive, or if start and resume
    stopped being.
    """
    status = command_policy("config.reset.status")
    start = command_policy("config.reset.start")
    resume = command_policy("config.reset.resume")

    # The read-only flag does NOT separate them, which is why it must not be read as if it did.
    assert (status.read_only, start.read_only, resume.read_only) == (False, False, False)

    # The destructive flag does.
    assert status.destructive is False
    assert start.destructive is True
    assert resume.destructive is True



def _path_to_command_key(path: str) -> str:
    tokens = path.replace("-", "_").split()
    # ``app`` verbs drop the root in the command key; ``config`` verbs keep it.
    return ".".join(tokens[1:]) if tokens and tokens[0] == "app" else ".".join(tokens)


def test_every_write_policy_verb_is_in_a_mutating_family() -> None:
    # Anti-vacuity floor. The screen below collects write-policy catalogue entries
    # whose family classifies read-only and asserts the set is empty. An empty
    # catalogue -- or a screen that can never see a read-only classification --
    # produces exactly that same green while checking nothing, so pin the corpus
    # size and prove the screen discriminates before trusting its silence.
    assert len(PROFILE_BOUND_WRITE_VERB_PATHS) >= 40, (
        f"write-policy catalogue collapsed to {len(PROFILE_BOUND_WRITE_VERB_PATHS)} entries; a green "
        "result below would mean 'nothing was screened' rather than 'nothing is wrong'"
    )

    # Hostile-input probe: a genuinely read-only command placed under the same
    # screen IS flagged. `registry.inspect` reads bundled registry data and the
    # manifest classifies its family read-only, so were it mislabelled a write
    # verb this screen would surface it. This proves the screen is not vacuously
    # empty because nothing at all can classify read-only.
    assert command_policy("registry.inspect").read_only, (
        "registry.inspect no longer classifies read-only, so the discrimination probe below is void"
    )
    injected = sorted(
        key
        for path in (*PROFILE_BOUND_WRITE_VERB_PATHS, "app registry inspect")
        if command_policy(key := _path_to_command_key(path)).read_only
    )
    assert injected == ["registry.inspect"], (
        "the read-only screen failed to flag a read-only command injected into the write set, so it "
        f"could not flag a real read-only writer either: {injected}"
    )

    read_only_writers = sorted(
        key
        for path in PROFILE_BOUND_WRITE_VERB_PATHS
        if command_policy(key := _path_to_command_key(path)).read_only
    )
    assert read_only_writers == [], (
        f"commands the write guard treats as writes but the manifest classifies read-only: {read_only_writers}"
    )
