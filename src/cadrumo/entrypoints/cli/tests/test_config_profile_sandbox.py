"""CLI tests for the ``aeat config profile sandbox`` experiment-workspace lifecycle.

Resolves #422: an operator (or an LLM agent driving the CLI) needs to run
experiments in an isolated bucket without polluting the main profile's
records, then discard the experiment cleanly. These tests drive the real
``aeat config profile sandbox`` verbs against real per-bucket encrypted
storage (no mocks, per the roundtrip-discipline rule) and prove:

- ``create --from-profile`` forks an isolated bucket seeded with the
  source's facts; the source bucket is never mutated.
- writes made while the sandbox is active never appear on the main profile
  after switching back.
- ``discard`` refuses the active bucket (mirroring
  ``BucketMaintenanceService.delete``'s existing contract), refuses without
  ``--yes``, and on success erases the sandbox from the live profile
  surface while leaving every other profile intact.
- ``discard --dry-run`` previews what a discard would remove without
  removing anything (the sandbox is still present and discardable
  afterwards).
- ``prune`` discards every sandbox in one operation, previews with
  ``--dry-run`` first, refuses without ``--yes``, and never touches a real
  (non-sandbox) profile.
- ``archive`` moves a sandbox into reversible dormancy (soft tombstone
  only, no directory removal): it refuses the active bucket, refuses
  without ``--yes``, previews with ``--dry-run``, and drops the sandbox
  off ``sandbox list`` while leaving its data intact and recoverable.
- ``restore`` reverses ``archive``: it brings the same sandbox back to
  the live surface with its data intact, and refuses a sandbox that was
  never archived.
- every command run while a sandbox is the active profile surfaces a
  persistent sandbox-active indicator (an info ``Notice`` in ``--json``,
  a ``SANDBOX`` banner line in text mode) naming the sandbox; a command
  run against a real (non-sandbox) profile carries neither.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import create_profile_via_cli
from .envelope_helpers import unwrap_envelope_notices, unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_sandbox_create_forks_isolated_bucket_seeded_from_source() -> None:
    """``sandbox create --from-profile`` copies facts without touching the source.

    The sandbox becomes the active profile and carries the seeded fact
    (``activities.description``); the source profile's own record is
    read through an unrelated bucket session and remains untouched.
    """
    create_profile_via_cli("main")

    created = _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main"))
    assert created.exit_code == 0, created.output
    assert "label\tsandbox:bakeoff" in created.output
    assert "seeded_from\tmain" in created.output

    # The sandbox is now active and carries the seeded fact.
    shown = _invoke(("config", "profile", "show"))
    assert shown.exit_code == 0, shown.output
    assert "display_name\tsandbox:bakeoff" in shown.output
    assert "activities.description\tdesign" in shown.output

    # The source profile is untouched: switching back shows the original label
    # and the same seeded fact value, never a value written while in the sandbox.
    switched = _invoke(("config", "login", "main"))
    assert switched.exit_code == 0, switched.output
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output


def test_sandbox_writes_never_appear_on_main_after_switching_back() -> None:
    """Editing a fact inside the sandbox must not leak into the main profile.

    This is the core isolation proof the issue asks for: an experiment
    (here, a profile-fact edit standing in for "imports, classifications,
    calculations") performed while the sandbox is active must be invisible
    on the main profile once the operator switches back.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "lab", "--from-profile", "main")).exit_code == 0

    edited = _invoke(
        ("config", "profile", "edit", "sandbox:lab", "--quiet", "--activity", "sandbox-experiment"),
    )
    assert edited.exit_code == 0, edited.output

    sandbox_shown = _invoke(("config", "profile", "show"))
    assert "activities.description\tsandbox-experiment" in sandbox_shown.output

    assert _invoke(("config", "login", "main")).exit_code == 0
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    # The main profile keeps its original value; the sandbox edit never landed here.
    assert "activities.description\tdesign" in main_shown.output
    assert "activities.description\tsandbox-experiment" not in main_shown.output


def test_sandbox_list_shows_only_sandbox_labelled_buckets() -> None:
    """``sandbox list`` filters to buckets carrying the reserved prefix."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "alpha", "--from-profile", "main")).exit_code == 0

    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:alpha" in listing.output
    assert "\tmain" not in listing.output

    full_listing = _invoke(("config", "profile", "list"))
    assert full_listing.exit_code == 0, full_listing.output
    assert "main" in full_listing.output
    assert "sandbox:alpha" in full_listing.output


def test_sandbox_discard_refuses_without_yes() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "temp", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "discard", "temp"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_discard_refuses_the_active_bucket() -> None:
    """Discarding the currently-active sandbox is refused; the operator switches first.

    Mirrors ``BucketMaintenanceService.delete``'s existing active-bucket
    refusal, applied through the sandbox composition.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "active-one", "--from-profile", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "discard", "active-one", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_discard_erases_sandbox_and_leaves_main_intact() -> None:
    """A confirmed discard of a non-active sandbox erases it from the live surface.

    Every other profile — in particular ``main`` — must remain fully
    intact and readable after the discard.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "throwaway", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    discarded = _invoke(("config", "profile", "sandbox", "discard", "throwaway", "--yes"))
    assert discarded.exit_code == 0, discarded.output
    assert "previous_label\tsandbox:throwaway" in discarded.output

    # The sandbox is gone from the live surface.
    assert read_profile_bucket("sandbox:throwaway") is None

    # main is unaffected: still resolvable, still active, still carries its facts.
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output

    listing = _invoke(("config", "profile", "list"))
    assert listing.exit_code == 0, listing.output
    assert "main" in listing.output
    assert "sandbox:throwaway" not in listing.output


def test_sandbox_discard_unknown_name_refuses() -> None:
    create_profile_via_cli("main")

    refused = _invoke(("config", "profile", "sandbox", "discard", "does-not-exist", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_create_without_from_profile_refuses_incomplete_schema() -> None:
    """``sandbox create`` with no ``--from-profile`` hits the same schema gate ``profile create`` does.

    A sandbox is a real profile bucket underneath, so an unseeded sandbox
    with zero facts fails the identical required-field validation
    ``config profile create`` enforces — there is no bypass. Operators
    seed a realistic sandbox with ``--from-profile`` (the documented
    success path); this refusal proves the sandbox surface does not
    quietly relax that contract.
    """
    refused = _invoke(("config", "profile", "sandbox", "create", "onboarding-demo"))
    assert refused.exit_code != 0, refused.output
    assert "required_field_missing" in refused.output


def test_sandbox_discard_dry_run_previews_without_removing() -> None:
    """``discard --dry-run`` reports the sandbox's contents but removes nothing.

    The sandbox must still be present, listed, and discardable after the
    preview — a dry-run is a read, never a partial or full erase.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "preview-me", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    previewed = _invoke(("config", "profile", "sandbox", "discard", "preview-me", "--dry-run"))
    assert previewed.exit_code == 0, previewed.output
    assert "dry_run\ttrue" in previewed.output
    assert "bucket_id\t" in previewed.output

    # Nothing was removed: the sandbox is still live and appears in list.
    assert read_profile_bucket("sandbox:preview-me") is not None
    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:preview-me" in listing.output

    # main is untouched by the preview.
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output

    # A real discard still works afterwards.
    discarded = _invoke(("config", "profile", "sandbox", "discard", "preview-me", "--yes"))
    assert discarded.exit_code == 0, discarded.output
    assert read_profile_bucket("sandbox:preview-me") is None


def test_sandbox_discard_dry_run_reports_the_active_sandbox_flag() -> None:
    """The preview reports whether the target is the currently active bucket.

    A dry-run against the active sandbox must not raise (it is read-only)
    even though a confirmed discard of it would be refused.
    """
    create_profile_via_cli("main")
    created = _invoke(("config", "profile", "sandbox", "create", "active-preview", "--from-profile", "main"))
    assert created.exit_code == 0, created.output

    previewed = _invoke(("config", "profile", "sandbox", "discard", "active-preview", "--dry-run"))
    assert previewed.exit_code == 0, previewed.output
    assert "would_discard_active\ttrue" in previewed.output


def test_sandbox_discard_dry_run_unknown_name_refuses() -> None:
    create_profile_via_cli("main")

    refused = _invoke(("config", "profile", "sandbox", "discard", "does-not-exist", "--dry-run"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_prune_dry_run_previews_without_removing() -> None:
    """``prune --dry-run`` lists every sandbox that would be discarded and removes nothing."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "alpha", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "beta", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    previewed = _invoke(("config", "profile", "sandbox", "prune", "--dry-run"))
    assert previewed.exit_code == 0, previewed.output
    assert "dry_run\ttrue" in previewed.output
    assert "would_discard\tsandbox:alpha" in previewed.output
    assert "would_discard\tsandbox:beta" in previewed.output

    # Nothing removed.
    assert read_profile_bucket("sandbox:alpha") is not None
    assert read_profile_bucket("sandbox:beta") is not None


def test_sandbox_prune_refuses_without_yes_or_dry_run() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "gamma", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "prune"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_prune_removes_every_sandbox_and_leaves_real_profile_intact() -> None:
    """A confirmed ``prune`` discards every sandbox while leaving ``main`` (and its facts) untouched."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "delta", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "epsilon", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    pruned = _invoke(("config", "profile", "sandbox", "prune", "--yes"))
    assert pruned.exit_code == 0, pruned.output
    assert "dry_run\tfalse" in pruned.output
    assert "discarded\tsandbox:delta" in pruned.output
    assert "discarded\tsandbox:epsilon" in pruned.output

    assert read_profile_bucket("sandbox:delta") is None
    assert read_profile_bucket("sandbox:epsilon") is None

    # main is fully intact.
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output

    listing = _invoke(("config", "profile", "list"))
    assert listing.exit_code == 0, listing.output
    assert "main" in listing.output
    assert "sandbox:delta" not in listing.output
    assert "sandbox:epsilon" not in listing.output


def test_sandbox_prune_skips_the_active_sandbox_with_advisory() -> None:
    """``prune`` never force-discards the active sandbox; it skips it with a notice.

    Every OTHER sandbox is still discarded in the same run.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "zeta", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "eta", "--from-profile", "main")).exit_code == 0
    # "eta" is now the active bucket (the most recently created sandbox).

    pruned = _invoke(("config", "profile", "sandbox", "prune", "--yes"))
    assert pruned.exit_code == 0, pruned.output
    assert "discarded\tsandbox:zeta" in pruned.output
    assert "discarded\tsandbox:eta" not in pruned.output

    # zeta is gone; eta (still active) survives the prune.
    assert read_profile_bucket("sandbox:zeta") is None
    assert read_profile_bucket("sandbox:eta") is not None


def test_sandbox_prune_never_touches_a_non_sandbox_profile() -> None:
    """``prune`` with no sandboxes leaves every real profile untouched."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    create_profile_via_cli("other")

    pruned = _invoke(("config", "profile", "sandbox", "prune", "--yes"))
    assert pruned.exit_code == 0, pruned.output
    assert "total\t0" in pruned.output

    assert read_profile_bucket("main") is not None
    assert read_profile_bucket("other") is not None


def test_sandbox_archive_refuses_without_yes() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "dormant", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "archive", "dormant"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_archive_refuses_the_active_bucket() -> None:
    """Archiving the currently-active sandbox is refused; the operator switches first.

    Mirrors ``BucketMaintenanceService.archive``'s active-bucket refusal
    (the same guarantee ``delete``/``discard`` provide).
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "active-two", "--from-profile", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "archive", "active-two", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_archive_unknown_name_refuses() -> None:
    create_profile_via_cli("main")

    refused = _invoke(("config", "profile", "sandbox", "archive", "does-not-exist", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_archive_dry_run_previews_without_moving_it_out_of_the_live_surface() -> None:
    """``archive --dry-run`` reports the target but leaves the sandbox live and listed."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    created = _invoke(("config", "profile", "sandbox", "create", "preview-archive", "--from-profile", "main"))
    assert created.exit_code == 0, created.output
    assert _invoke(("config", "login", "main")).exit_code == 0

    previewed = _invoke(("config", "profile", "sandbox", "archive", "preview-archive", "--dry-run"))
    assert previewed.exit_code == 0, previewed.output
    assert "dry_run\ttrue" in previewed.output
    assert "bucket_id\t" in previewed.output

    # Nothing changed: the sandbox is still live and appears in list.
    assert read_profile_bucket("sandbox:preview-archive") is not None
    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:preview-archive" in listing.output


def test_sandbox_archive_moves_sandbox_off_live_surface_but_data_survives() -> None:
    """A confirmed archive drops the sandbox off ``sandbox list`` / ``read_profile_bucket``.

    Unlike ``discard``, the bucket directory and manifest survive
    intact: ``read_profile_bucket_by_id`` (and, at the CLI layer,
    ``sandbox restore``) can still resolve it. ``main`` is unaffected.
    """
    from ....application.workflow import read_profile_bucket, read_profile_bucket_by_id

    create_profile_via_cli("main")
    created = _invoke(("config", "profile", "sandbox", "create", "sleeper", "--from-profile", "main"))
    assert created.exit_code == 0, created.output
    # The CLI text envelope redacts bucket_id to a fixed placeholder; read
    # the real UUID through the application-layer resolver instead of
    # parsing the redacted line.
    live_pointer = read_profile_bucket("sandbox:sleeper")
    assert live_pointer is not None
    bucket_id = live_pointer.bucket_id
    assert _invoke(("config", "login", "main")).exit_code == 0

    archived = _invoke(("config", "profile", "sandbox", "archive", "sleeper", "--yes"))
    assert archived.exit_code == 0, archived.output
    assert "label\tsandbox:sleeper" in archived.output

    # Off the live surface...
    assert read_profile_bucket("sandbox:sleeper") is None
    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:sleeper" not in listing.output

    # ...but still resolvable by id, and the directory/manifest survive.
    from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
    from ....core.config import load_settings
    from ....domain.user_profile import UserProfileStatus

    pointer = read_profile_bucket_by_id(bucket_id)
    assert pointer is not None
    assert pointer.status is UserProfileStatus.TOMBSTONED
    paths = bucket_paths(load_settings().cadrumo_local_storage_root, bucket_id)
    assert manifest_path(paths).is_file()

    # main is unaffected.
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output


def test_sandbox_restore_unknown_name_refuses() -> None:
    create_profile_via_cli("main")

    refused = _invoke(("config", "profile", "sandbox", "restore", "does-not-exist"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_restore_refuses_a_sandbox_that_was_never_archived() -> None:
    """``restore`` refuses a live (never-archived) sandbox."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "never-dormant", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "restore", "never-dormant"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_restore_brings_an_archived_sandbox_back_with_data_intact() -> None:
    """``restore`` reverses ``archive``: the sandbox reappears on the live surface with its data intact."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "roundtrip", "--from-profile", "main")).exit_code == 0
    edited = _invoke(("config", "profile", "edit", "sandbox:roundtrip", "--quiet", "--activity", "archived-experiment"))
    assert edited.exit_code == 0, edited.output
    assert _invoke(("config", "login", "main")).exit_code == 0

    archived = _invoke(("config", "profile", "sandbox", "archive", "roundtrip", "--yes"))
    assert archived.exit_code == 0, archived.output
    assert read_profile_bucket("sandbox:roundtrip") is None

    restored = _invoke(("config", "profile", "sandbox", "restore", "roundtrip"))
    assert restored.exit_code == 0, restored.output
    assert "label\tsandbox:roundtrip" in restored.output

    # Back on the live surface, with its edited fact intact.
    assert read_profile_bucket("sandbox:roundtrip") is not None
    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:roundtrip" in listing.output

    assert _invoke(("config", "login", "sandbox:roundtrip")).exit_code == 0
    restored_shown = _invoke(("config", "profile", "show"))
    assert restored_shown.exit_code == 0, restored_shown.output
    assert "activities.description\tarchived-experiment" in restored_shown.output


def test_sandbox_archive_then_discard_requires_restore_first() -> None:
    """``discard`` addresses only the live surface: an archived sandbox is no longer discardable by name.

    ``discard``'s label lookup excludes tombstoned buckets (the same
    live-surface resolver ``sandbox list`` uses), so a sandbox that was
    archived must be restored before it can be discarded outright. This
    documents the boundary rather than a bug: archive/restore and
    discard both operate on the same lifecycle status, and an archived
    sandbox simply is not addressable by its label until reactivated.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "one-way", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    assert _invoke(("config", "profile", "sandbox", "archive", "one-way", "--yes")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "discard", "one-way", "--yes"))
    assert refused.exit_code != 0, refused.output

    assert _invoke(("config", "profile", "sandbox", "restore", "one-way")).exit_code == 0
    from ....application.workflow import read_profile_bucket

    assert read_profile_bucket("sandbox:one-way") is not None
    discarded = _invoke(("config", "profile", "sandbox", "discard", "one-way", "--yes"))
    assert discarded.exit_code == 0, discarded.output


def test_sandbox_usage_reports_a_named_sandbox_footprint() -> None:
    """``sandbox usage <name>`` reports a real non-zero on-disk footprint for one sandbox."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "diskcheck", "--from-profile", "main")).exit_code == 0

    report = _invoke(("config", "profile", "sandbox", "usage", "diskcheck"))
    assert report.exit_code == 0, report.output
    assert "sandbox:diskcheck" in report.output
    assert "total_bytes\t" in report.output
    # A freshly-forked sandbox already has a real manifest + SQLite database
    # on disk (from the seeded facts), so its footprint must be non-zero.
    total_line = next(line for line in report.output.splitlines() if line.startswith("total_bytes\t"))
    assert int(total_line.split("\t", 1)[1]) > 0


def test_sandbox_usage_unknown_name_refuses() -> None:
    refused = _invoke(("config", "profile", "sandbox", "usage", "does-not-exist"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_usage_with_no_name_reports_every_sandbox_and_a_grand_total() -> None:
    """``sandbox usage`` with no name reports every sandbox and sums their totals."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "usage-a", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "usage-b", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    report = _invoke(("config", "profile", "sandbox", "usage"))
    assert report.exit_code == 0, report.output
    assert "sandbox:usage-a" in report.output
    assert "sandbox:usage-b" in report.output

    json_report = _invoke(("--format", "json", "config", "profile", "sandbox", "usage"))
    assert json_report.exit_code == 0, json_report.output
    result = unwrap_schema_envelope(json_report.output)
    labels = {row["label"] for row in result["sandboxes"]}
    assert labels == {"sandbox:usage-a", "sandbox:usage-b"}
    assert result["total_bytes"] == sum(row["total_bytes"] for row in result["sandboxes"])
    assert result["total_bytes"] > 0


def test_sandbox_usage_measures_an_archived_sandbox_without_reactivating_it() -> None:
    """``sandbox usage`` can measure an archived (dormant) sandbox by name.

    Mirrors ``restore``'s tombstone-inclusive label lookup: a disk-usage
    report is a read-only filesystem walk, so it must not require the
    operator to restore the sandbox first.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "dormant", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "archive", "dormant", "--yes")).exit_code == 0

    report = _invoke(("config", "profile", "sandbox", "usage", "dormant"))
    assert report.exit_code == 0, report.output
    assert "sandbox:dormant" in report.output

    # Still archived: the usage report is read-only and did not reactivate it.
    from ....application.workflow import read_profile_bucket

    assert read_profile_bucket("sandbox:dormant") is None
    assert read_profile_bucket("sandbox:dormant", include_tombstoned=True) is not None
    assert read_profile_bucket("sandbox:one-way") is None


def _add_ledger_transaction(*, description: str, amount: str = "42.00") -> str:
    added = _invoke(
        (
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-03-10",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
        ),
    )
    assert added.exit_code == 0, added.output
    payload = unwrap_schema_envelope(added.output)
    return str(payload["transaction"]["transaction_id"])


def test_sandbox_merge_ledger_promotes_rows_from_sandbox_into_main() -> None:
    """``sandbox merge --scope ledger`` copies sandbox ledger rows into the target profile.

    Real encrypted per-bucket storage: the sandbox and main profile each
    hold their own ``TransactionCatalogueRepository``, and the merge must
    make the sandbox row appear in main's catalogue without disturbing
    main's own pre-existing row.
    """
    create_profile_via_cli("main")
    main_transaction_id = _add_ledger_transaction(description="Main office rent")

    created = _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main"))
    assert created.exit_code == 0, created.output
    sandbox_transaction_id = _add_ledger_transaction(description="Sandbox experiment purchase")

    assert _invoke(("config", "login", "main")).exit_code == 0

    merged = _invoke(
        (
            "--format",
            "json",
            "config",
            "profile",
            "sandbox",
            "merge",
            "bakeoff",
            "--into",
            "main",
            "--scope",
            "ledger",
            "--yes",
        ),
    )
    assert merged.exit_code == 0, merged.output
    payload = unwrap_schema_envelope(merged.output)
    assert payload["scope"] == "ledger"
    assert payload["source_label"] == "sandbox:bakeoff"
    assert payload["target_label"] == "main"
    assert payload["merged_counts"]["ledger_transactions"] == 1

    listed = _invoke(("--format", "json", "app", "ledger", "list"))
    assert listed.exit_code == 0, listed.output
    listed_ids = {row["transaction_id"] for row in unwrap_schema_envelope(listed.output)["rows"]}
    assert main_transaction_id in listed_ids
    assert sandbox_transaction_id in listed_ids

    # The merge stamps a BUCKET_MERGED audit event into the target (main)
    # bucket's own event history, mirroring every other maintenance verb.
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....application.user_profile import profile_storage_session
    from ....application.workflow import read_profile_bucket
    from ....domain.buckets import BucketEventType

    main_pointer = read_profile_bucket("main")
    assert main_pointer is not None
    with profile_storage_session(main_pointer.bucket_id):
        catalogue = BucketEventHistoryRepository().load()
    merge_events = [event for event in catalogue.events.values() if event.event_type is BucketEventType.BUCKET_MERGED]
    assert len(merge_events) == 1
    assert merge_events[0].payload["scope"] == "ledger"
    assert merge_events[0].payload["source_label"] == "sandbox:bakeoff"


def test_sandbox_merge_ledger_is_idempotent_on_rerun() -> None:
    """Re-running the same merge does not duplicate the promoted rows.

    ``merge_sandbox`` upserts by the sandbox transaction's own
    content-addressed id, so promoting the same unchanged sandbox content
    twice must leave the target catalogue with the same row count.
    """
    create_profile_via_cli("main")
    _add_ledger_transaction(description="Main baseline row")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0
    _add_ledger_transaction(description="Sandbox row one")
    assert _invoke(("config", "login", "main")).exit_code == 0

    merge_args = (
        "config",
        "profile",
        "sandbox",
        "merge",
        "bakeoff",
        "--into",
        "main",
        "--scope",
        "ledger",
        "--yes",
    )
    first = _invoke(merge_args)
    assert first.exit_code == 0, first.output
    second = _invoke(merge_args)
    assert second.exit_code == 0, second.output

    listed = _invoke(("--format", "json", "app", "ledger", "list"))
    assert listed.exit_code == 0, listed.output
    rows = unwrap_schema_envelope(listed.output)["rows"]
    # Main's own row plus exactly one promoted sandbox row, never a duplicate
    # from the second merge run.
    assert len(rows) == 2


def test_sandbox_merge_refuses_without_yes() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    result = _invoke(("config", "profile", "sandbox", "merge", "bakeoff", "--into", "main", "--scope", "ledger"))
    assert result.exit_code != 0
    assert "--yes" in result.output


def test_sandbox_merge_unknown_sandbox_name_refuses() -> None:
    create_profile_via_cli("main")

    result = _invoke(
        ("config", "profile", "sandbox", "merge", "does-not-exist", "--into", "main", "--scope", "ledger", "--yes"),
    )
    assert result.exit_code != 0


def test_sandbox_merge_unknown_target_profile_refuses() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    result = _invoke(
        (
            "config",
            "profile",
            "sandbox",
            "merge",
            "bakeoff",
            "--into",
            "no-such-profile",
            "--scope",
            "ledger",
            "--yes",
        ),
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------
# Persistent sandbox-active indicator (#422 final slice)
# ---------------------------------------------------------------------


def test_sandbox_active_indicator_appears_in_json_notices_while_sandbox_is_active() -> None:
    """An unrelated ``--json`` command surfaces an info notice naming the active sandbox."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0

    shown = _invoke(("--format", "json", "config", "profile", "show"))
    assert shown.exit_code == 0, shown.output
    notices = unwrap_envelope_notices(shown.output)
    sandbox_notices = [n for n in notices if n["code"] == "config.profile.sandbox.active_indicator"]
    assert len(sandbox_notices) == 1, notices
    assert sandbox_notices[0]["severity"] == "info"
    assert "sandbox:bakeoff" in sandbox_notices[0]["message"]

    envelope = json.loads(shown.output)
    assert envelope["status"] == "success"


def test_sandbox_active_indicator_appears_as_text_banner_while_sandbox_is_active() -> None:
    """A text-mode command run against an active sandbox prints a ``SANDBOX`` banner line."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0

    shown = _invoke(("config", "profile", "show"))
    assert shown.exit_code == 0, shown.output
    assert "SANDBOX\t" in shown.output
    assert "sandbox:bakeoff" in shown.output


def test_sandbox_active_indicator_absent_for_a_real_profile() -> None:
    """A command run against a real (non-sandbox) profile carries no sandbox indicator."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    shown_json = _invoke(("--format", "json", "config", "profile", "show"))
    assert shown_json.exit_code == 0, shown_json.output
    notices = unwrap_envelope_notices(shown_json.output)
    assert all(n["code"] != "config.profile.sandbox.active_indicator" for n in notices)

    shown_text = _invoke(("config", "profile", "show"))
    assert shown_text.exit_code == 0, shown_text.output
    assert "SANDBOX\t" not in shown_text.output


def test_sandbox_active_indicator_absent_when_no_profile_is_active() -> None:
    """A cold-start command (no active profile at all) carries no sandbox indicator."""
    result = _invoke(("--format", "json", "config", "profile", "list"))
    assert result.exit_code == 0, result.output
    notices = unwrap_envelope_notices(result.output)
    assert all(n["code"] != "config.profile.sandbox.active_indicator" for n in notices)


def test_sandbox_active_indicator_names_the_currently_active_sandbox_after_switch() -> None:
    """Switching between two sandboxes updates the banner's named sandbox on the next command.

    ``switch`` is the single accepted selector: a sandbox is entered by its
    canonical ``sandbox:<name>`` label (the removed ``sandbox use`` door had
    no separate authority — it delegated to the same select-lifecycle-span
    primitive ``switch`` uses).
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "zeta", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "eta", "--from-profile", "main")).exit_code == 0
    # "eta" is now the active bucket (the most recently created sandbox).

    shown = _invoke(("config", "profile", "show"))
    assert shown.exit_code == 0, shown.output
    assert "sandbox:eta" in shown.output
    assert "sandbox:zeta" not in shown.output

    switched = _invoke(("config", "login", "sandbox:zeta"))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tsandbox:zeta" in switched.output
    shown_after_switch = _invoke(("config", "profile", "show"))
    assert shown_after_switch.exit_code == 0, shown_after_switch.output
    assert "sandbox:zeta" in shown_after_switch.output


def test_sandbox_use_command_is_absent() -> None:
    """``sandbox use`` was removed with no alias; only ``switch`` selects a sandbox.

    The grammar carries exactly one selection door: ``config profile sandbox
    use`` no longer exists, so invoking it fails as an unknown sub-command and
    ``switch`` remains the accepted selector — proven by the sibling
    ``..._after_switch`` test entering the sandbox by its canonical label.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "gone", "--from-profile", "main")).exit_code == 0

    used = _invoke(("config", "profile", "sandbox", "use", "gone"))
    assert used.exit_code != 0
    # The sandbox sub-app help lists its live verbs; `use` is not among them.
    help_result = _invoke(("config", "profile", "sandbox", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert "use" not in {line.split()[0] for line in help_result.output.splitlines() if line.strip()}


def test_switch_rejects_a_bare_sandbox_short_name() -> None:
    """A bare sandbox short name is not implicitly namespaced by ``switch``.

    ``switch`` accepts an unambiguous UUID or an exact operator label — a
    sandbox's canonical ``sandbox:<name>`` label. A bare ``<name>`` carries no
    ``sandbox:`` prefix, so it matches no sandbox bucket and is refused as an
    unknown profile: this preserves the sandbox namespace check the removed
    ``use`` door performed.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "bare", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    # The bare short name (no `sandbox:` prefix) does not resolve to the sandbox.
    bare = _invoke(("config", "login", "bare"))
    assert bare.exit_code != 0

    # The canonical label does resolve.
    canonical = _invoke(("config", "login", "sandbox:bare"))
    assert canonical.exit_code == 0, canonical.output
    assert "active_profile\tsandbox:bare" in canonical.output


def test_switch_accepts_a_sandbox_bucket_uuid() -> None:
    """``switch`` accepts the immutable bucket UUID a sandbox listing returns.

    ``switch NAME`` accepts exactly what a profile or sandbox listing returns:
    the unambiguous bucket UUID or the exact label.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "byid", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "login", "main")).exit_code == 0

    pointer = read_profile_bucket("sandbox:byid")
    assert pointer is not None
    switched = _invoke(("config", "login", pointer.bucket_id))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tsandbox:byid" in switched.output


def test_sandbox_active_indicator_helper_degrades_silently_on_a_corrupt_active_manifest() -> None:
    """The indicator helper itself must never raise on a corrupt active manifest.

    Exercises :func:`~cadrumo.entrypoints.cli._common._active_sandbox_notice`
    directly against a bucket whose manifest is torn/corrupt AND is the
    currently active bucket (``CADRUMO_ACTIVE_PROFILE`` points at it). This
    isolates the indicator's own defensive handling: the helper must
    return ``None`` rather than propagate the storage-validation failure,
    independent of how any particular CLI command's *other* pre-existing
    active-profile plumbing (the root callback's label normalisation,
    which is unrelated to this feature) happens to react to the same
    corruption.
    """
    from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
    from ....application.workflow import read_profile_bucket
    from ....core.config import load_settings, override_settings
    from .._common import _active_sandbox_notice

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "torn", "--from-profile", "main")).exit_code == 0

    live_pointer = read_profile_bucket("sandbox:torn")
    assert live_pointer is not None
    paths = bucket_paths(load_settings().cadrumo_local_storage_root, live_pointer.bucket_id)
    manifest_file = manifest_path(paths)
    manifest_file.write_text("not = [valid toml", encoding="utf-8")

    with override_settings(cadrumo_active_profile=live_pointer.bucket_id):
        assert _active_sandbox_notice() is None


def test_sandbox_active_indicator_absent_when_a_non_active_sandbox_manifest_is_corrupt() -> None:
    """A corrupt manifest on a non-active sandbox never breaks an unrelated command.

    ``config profile list`` tolerates a per-bucket manifest read failure by
    construction (``list_profile_buckets`` skips unreadable manifests); this
    proves the corruption of a bucket that is NOT the active profile never
    surfaces the sandbox indicator and never breaks the command.
    """
    from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
    from ....application.workflow import read_profile_bucket
    from ....core.config import load_settings

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "torn", "--from-profile", "main")).exit_code == 0
    live_pointer = read_profile_bucket("sandbox:torn")
    assert live_pointer is not None
    assert _invoke(("config", "login", "main")).exit_code == 0

    paths = bucket_paths(load_settings().cadrumo_local_storage_root, live_pointer.bucket_id)
    manifest_file = manifest_path(paths)
    manifest_file.write_text("not = [valid toml", encoding="utf-8")

    listed = _invoke(("config", "profile", "list"))
    assert listed.exit_code == 0, listed.output
    assert "SANDBOX\t" not in listed.output
