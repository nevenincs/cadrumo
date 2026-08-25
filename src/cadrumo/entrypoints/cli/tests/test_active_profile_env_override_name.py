"""Real-operator test: the active-profile override accepts the display label.

An operator addresses their profile by the display label they chose at
``profile create`` — the immutable UUIDv4 bucket id is never surfaced to them.
The in-process active-profile override (written by ``--profile``) is the
highest-precedence rung of the active-profile precedence chain, and the canonical
``core.config`` storage-route resolver keys directly on ``buckets/<value>``. Before
the entrypoint name→UUID normalization, a label-valued override made
every profile-bound command hard-miss with a "no registered bucket manifest"
refusal. This module pins the fixed behaviour by driving the REAL CLI root
callback (the normalization site) against a REAL profile created through the real
``config profile create`` flow: exactly the operator path that previously
broke. The fixed contract feeds a UUID into the single canonical route
resolver after normalizing the operator-facing display label.
"""

from __future__ import annotations

import json

import pytest

from ._modelo_empty_profile_fixture import _isolated_backend

__all__ = ["_isolated_backend"]

from ....core.config import override_settings
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli
from ....tests.profile_capsule import forge_colliding_capsule_label
from ....tests.user_profile import register_cli_profile
from .._common import cli_policy_refusal_projection
from .._errors import CliRefusedBoundaryError, error_boundary_under_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The display label the operator chooses at create — the only id they know.
_LABEL = "operator"


def _create_profile_and_resolve_uuid() -> str:
    """Create a real profile via the CLI and return its minted UUID bucket id.

    Mirrors a real operator's ``aeat config profile create <label>`` — it mints
    the UUIDv4 bucket directory + manifest and writes the active-profile pointer
    to that UUID (never the label).
    """
    register_cli_profile(
        label=_LABEL,
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Override",
            "activities.description": "design",
        },
    )
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    pointer = read_profile_bucket(_LABEL)
    assert pointer is not None, "the created profile must resolve by its label"
    return pointer.bucket_id


def test_env_override_by_display_label_resolves_the_profile_bucket() -> None:
    """``--profile <label>`` resolves the operator's bucket (the fixed bug).

    The real operator path: a fresh resolution whose active profile comes from
    the active-profile override set to the LABEL the operator chose.
    Before the entrypoint normalization this refused with "no registered bucket
    manifest at buckets/<label>"; the root callback now normalizes the label to
    its UUID via the single profile resolver, so a profile-bound command resolves.
    """
    uuid = _create_profile_and_resolve_uuid()
    assert uuid != _LABEL, "the bucket id must be a minted UUID, not the label"

    with override_settings(cadrumo_active_profile=_LABEL):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    # The command resolved the operator's bucket and rendered the (empty) ledger
    # read model rather than refusing on a missing manifest.
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output
    payload = json.loads(listed.output)
    assert "rows" in payload.get("result", payload)


def test_env_override_by_uuid_is_unchanged() -> None:
    """``--profile <uuid>`` resolves through the direct bucket-id route.

    The UUID fast path is current behavior: normalization only fires when the
    direct UUID-bucket lookup misses, so a UUID-valued override never reaches the
    operator-label fallback.
    """
    uuid = _create_profile_and_resolve_uuid()

    with override_settings(cadrumo_active_profile=uuid):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output


def _write_second_live_bucket_sharing_label(label: str) -> None:
    """Provision a SECOND live profile whose committed capsule label collides with ``label``.

    The CLI ``profile create`` enforces label uniqueness casefolded under the
    custody-root lock, so a real operator cannot mint two live profiles with
    the same name through the happy path. This registers a genuine second
    profile under a distinct placeholder label, then forges its committed
    custody capsule label onto ``label`` directly — the same corruption every
    label writer refuses — to reach the torn / repair state that makes
    ``label`` resolve ambiguously, exercising the ambiguity-refusal path
    through the entrypoint normalizer.
    """
    from uuid import UUID

    second_uuid = register_cli_profile(
        label=f"{label}-forged",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Duplicate",
            "activities.description": "design",
        },
    )
    forge_colliding_capsule_label(profile_id=UUID(second_uuid), label=label)


# English rendering of the DEDICATED ambiguity refusal key
# ``errors.refused.refused_profile_label_ambiguous`` (en.yml:3910). The fix
# routes BOTH entrypoint resolution sites (the env-override normalizer and the
# ``--profile`` override) to THIS message.
_DEDICATED_AMBIGUITY_FRAGMENT = "Use the profile UUID to disambiguate"

# English rendering of the GENERIC ``cli.config.profile.unknown_profile`` key
# (en.yml:2047). The profile is ambiguous, NOT unknown; the dedicated key must
# render and this generic phrasing must be absent.
_GENERIC_UNKNOWN_FRAGMENT = "Unknown profile"


def _combined_output(result: object) -> str:
    """Combine stdout, stderr, and any raised exception text for fragment checks."""
    output: object = getattr(result, "output", "")
    combined = output if isinstance(output, str) else ""
    stderr: object = getattr(result, "stderr", None)
    if isinstance(stderr, str) and stderr:
        combined = f"{combined}\n{stderr}"
    exc: object = getattr(result, "exception", None)
    if isinstance(exc, BaseException):
        combined = f"{combined}\n{exc}"
    return combined


def test_env_override_ambiguous_label_refuses_cleanly_not_traceback() -> None:
    """Two live buckets sharing the env-override label → CLEAN, DEDICATED refusal.

    The entrypoint normalizer resolves the label via resolve_profile_bucket, whose
    fallback raises ProfileLabelAmbiguousError (a WorkflowError, NOT a ValueError)
    when two live profiles share the name. The root-callback catch must convert
    that to a clean CLI refusal (non-zero exit, no Python traceback) AND render the
    DEDICATED ambiguity key — never the generic "Unknown profile" phrasing, which
    is honest only for a not-found / empty label, and never an arbitrary bucket
    pick.
    """
    _create_profile_and_resolve_uuid()  # bucket 1: label "operator"
    _write_second_live_bucket_sharing_label(_LABEL)  # bucket 2: same label

    with override_settings(cadrumo_active_profile=_LABEL):
        listed = invoke_cached_cli(["--language", "en", "app", "ledger", "list"])

    assert listed.exit_code != 0, listed.output
    combined = _combined_output(listed)
    # A clean operator-facing refusal, not an unhandled ProfileLabelAmbiguousError
    # traceback escaping the catch.
    assert "Traceback" not in combined, combined
    assert "ProfileLabelAmbiguousError" not in combined, combined
    # The DEDICATED ambiguity key must render (GREEN only after the key swap).
    assert _DEDICATED_AMBIGUITY_FRAGMENT in combined, combined
    # The GENERIC unknown-profile phrasing must NOT render — the profile is
    # ambiguous, not unknown (RED before the key swap).
    assert _GENERIC_UNKNOWN_FRAGMENT not in combined, combined

    with (
        override_settings(cadrumo_active_profile=_LABEL),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["app", "ledger", "list"],
            prog_name="aeat",
            standalone_mode=False,
        )
    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.precondition_action.failed_condition_id == "profile.selection.unambiguous"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.list"


def test_profile_flag_ambiguous_label_refuses_with_dedicated_key() -> None:
    """``--profile <ambiguous-label>`` refuses with the DEDICATED ambiguity key.

    The ``--profile`` override resolves through the same single application-layer
    resolver as the env-override normalizer; its ``except ProfileLabelAmbiguousError``
    arm must likewise render the dedicated ambiguity message, never the generic
    "Unknown profile" phrasing reserved for a not-found / empty label.
    """
    _create_profile_and_resolve_uuid()  # bucket 1: label "operator"
    _write_second_live_bucket_sharing_label(_LABEL)  # bucket 2: same label

    listed = invoke_cached_cli(["--language", "en", "--profile", _LABEL, "app", "ledger", "list"])

    assert listed.exit_code != 0, listed.output
    combined = _combined_output(listed)
    assert "Traceback" not in combined, combined
    assert "ProfileLabelAmbiguousError" not in combined, combined
    assert _DEDICATED_AMBIGUITY_FRAGMENT in combined, combined
    assert _GENERIC_UNKNOWN_FRAGMENT not in combined, combined

    with error_boundary_under_test(), pytest.raises(CliRefusedBoundaryError) as raised:
        cadrumo_click_command().main(
            args=["--profile", _LABEL, "app", "ledger", "list"],
            prog_name="aeat",
            standalone_mode=False,
        )
    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.precondition_action.failed_condition_id == "profile.selection.unambiguous"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.list"


def test_env_override_unknown_label_does_not_resolve() -> None:
    """An override label matching no live profile does not resolve.

    The normalization no-ops on an unknown label (neither a UUID bucket nor a live
    label); the per-command active-profile guard then refuses rather than silently
    inventing a bucket — never a false resolution.
    """
    _create_profile_and_resolve_uuid()

    with override_settings(cadrumo_active_profile="no-such-profile"):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code != 0, listed.output
