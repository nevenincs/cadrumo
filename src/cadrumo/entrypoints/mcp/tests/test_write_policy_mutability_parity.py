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

from ....application.operator_surface import command_classification, declared_risk
from ....application.storage_write_policy import PROFILE_BOUND_WRITE_VERB_PATHS
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIVE_WRITE_LEAVES = frozenset({"submit", "present", "send"})


def test_a_submit_present_send_leaf_must_declare_live_write() -> None:
    for descriptor in build_tool_descriptors():
        leaf = descriptor.command_key.rsplit(".", 1)[-1]
        if leaf in _LIVE_WRITE_LEAVES:
            row = declared_risk(descriptor.command_key)
            assert row is not None and row.live_write, (
                f"{descriptor.command_key} has a live-write leaf but does not declare live_write - "
                "the never-live-submit block would not fire"
            )


def _path_to_command_key(path: str) -> str:
    tokens = path.replace("-", "_").split()
    # ``app`` verbs drop the root in the command key; ``config`` verbs keep it.
    return ".".join(tokens[1:]) if tokens and tokens[0] == "app" else ".".join(tokens)


def test_every_write_policy_verb_is_in_a_mutating_family() -> None:
    read_only_writers = sorted(
        key
        for path in PROFILE_BOUND_WRITE_VERB_PATHS
        if command_classification(key := _path_to_command_key(path)).read_only
    )
    assert read_only_writers == [], (
        f"commands the write guard treats as writes but the manifest classifies read-only: {read_only_writers}"
    )
