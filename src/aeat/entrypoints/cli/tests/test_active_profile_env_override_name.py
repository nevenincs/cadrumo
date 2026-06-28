"""Real-operator test: ``AEAT_ACTIVE_PROFILE`` accepts the display label.

An operator addresses their profile by the display label they chose at
``profile create`` — the immutable UUIDv4 bucket id is never surfaced to them.
The active-profile env override ``AEAT_ACTIVE_PROFILE`` is the highest-precedence
rung of the active-profile precedence chain, and the canonical ``core.config``
storage-route resolver keys directly on ``buckets/<value>``. Before the
entrypoint name→UUID normalization, a label-valued ``AEAT_ACTIVE_PROFILE`` made
every profile-bound command hard-miss with a "no registered bucket manifest"
refusal. This module pins the fixed behaviour by driving the REAL CLI root
callback (the normalization site) against a REAL profile created through the real
``config profile create`` flow: exactly the operator path the persona swarm
missed. The fixed contract feeds a UUID into the single canonical route
resolver after normalizing the operator-facing display label.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The display label the operator chooses at create — the only id they know.
_LABEL = "operator"


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path: Path) -> Iterator[None]:
    """Isolated storage root; no pre-opened span (each invoke is its own process surface)."""
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()


def _create_profile_and_resolve_uuid() -> str:
    """Create a real profile via the CLI and return its minted UUID bucket id.

    Mirrors a real operator's ``aeat config profile create <label>`` — it mints
    the UUIDv4 bucket directory + manifest and writes the active-profile pointer
    to that UUID (never the label).
    """
    created = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            _LABEL,
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Operator",
            "--surnames",
            "Override",
            "--activity",
            "design",
        ],
    )
    assert created.exit_code == 0, created.output
    from ....application.workflow import read_profile_bucket

    pointer = read_profile_bucket(_LABEL)
    assert pointer is not None, "the created profile must resolve by its label"
    return pointer.bucket_id


def test_env_override_by_display_label_resolves_the_profile_bucket() -> None:
    """``AEAT_ACTIVE_PROFILE=<label>`` resolves the operator's bucket (the fixed bug).

    The real operator path: a fresh resolution whose active profile comes from
    the ``AEAT_ACTIVE_PROFILE`` env override set to the LABEL the operator chose.
    Before the entrypoint normalization this refused with "no registered bucket
    manifest at buckets/<label>"; the root callback now normalizes the label to
    its UUID via the single profile resolver, so a profile-bound command resolves.
    """
    uuid = _create_profile_and_resolve_uuid()
    assert uuid != _LABEL, "the bucket id must be a minted UUID, not the label"

    with override_settings(aeat_active_profile=_LABEL):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    # The command resolved the operator's bucket and rendered the (empty) ledger
    # read model rather than refusing on a missing manifest.
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output
    payload = json.loads(listed.output)
    assert "rows" in payload.get("result", payload)


def test_env_override_by_uuid_is_unchanged() -> None:
    """``AEAT_ACTIVE_PROFILE=<uuid>`` resolves byte-identically (backward-compatible).

    The UUID fast path must be untouched: the normalization only fires when the
    direct UUID-bucket lookup misses, so a UUID-valued override never reaches the
    label fallback.
    """
    uuid = _create_profile_and_resolve_uuid()

    with override_settings(aeat_active_profile=uuid):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output


def _write_second_live_bucket_sharing_label(label: str) -> None:
    """Write a SECOND live bucket manifest carrying ``label`` (a torn-duplicate state).

    The CLI ``profile create`` enforces label uniqueness, so a real operator
    cannot mint two live profiles with the same name through the happy path; this
    helper writes the duplicate manifest directly to simulate the torn / repair
    state that makes a label resolve ambiguously, exercising the ambiguity-refusal
    path through the entrypoint normalizer.
    """
    from datetime import UTC, datetime

    from ....adapters.persistence.storage.bucket import (
        BucketLifecycleStatus,
        BucketManifest,
        bucket_paths,
        provision_bucket_directory,
        write_manifest,
    )
    from ....adapters.persistence.storage.master_key import KdfParams
    from ....core.config import load_settings

    root = load_settings().aeat_local_storage_root
    duplicate_uuid = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    now = datetime.now(UTC).replace(microsecond=0)
    provision_bucket_directory(root, duplicate_uuid)
    write_manifest(
        bucket_paths(root, duplicate_uuid),
        BucketManifest(
            bucket_id=duplicate_uuid,
            label=label,
            created_at=now,
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )


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
    combined = getattr(result, "output", "") or ""
    stderr = getattr(result, "stderr", None)
    if stderr:
        combined = f"{combined}\n{stderr}"
    exc = getattr(result, "exception", None)
    if exc:
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

    with override_settings(aeat_active_profile=_LABEL):
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


def test_env_override_unknown_label_does_not_resolve() -> None:
    """An ``AEAT_ACTIVE_PROFILE`` label matching no live profile does not resolve.

    The normalization no-ops on an unknown label (neither a UUID bucket nor a live
    label); the per-command active-profile guard then refuses rather than silently
    inventing a bucket — never a false resolution.
    """
    _create_profile_and_resolve_uuid()

    with override_settings(aeat_active_profile="no-such-profile"):
        listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code != 0, listed.output
