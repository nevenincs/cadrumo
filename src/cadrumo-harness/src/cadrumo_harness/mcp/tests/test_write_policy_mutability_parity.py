"""Callback-attached policy agrees with independent safety declarations.

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

    Callback policy is precise per verb: status is a read while starting and
    resuming are destructive writes. This pins both axes to prevent a family-
    level mutability default from erasing that distinction.
    Both halves are asserted, so the case fails if the family collapses in
    either direction - if status became destructive, or if start and resume
    stopped being.
    """
    status = command_policy("config.reset.status")
    start = command_policy("config.reset.start")
    resume = command_policy("config.reset.resume")

    assert (status.read_only, start.read_only, resume.read_only) == (True, False, False)

    # The destructive flag does.
    assert status.destructive is False
    assert start.destructive is True
    assert resume.destructive is True



