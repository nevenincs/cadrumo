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
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import create_profile_via_cli
from .envelope_helpers import unwrap_schema_envelope

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
    switched = _invoke(("config", "switch", "main"))
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

    assert _invoke(("config", "switch", "main")).exit_code == 0
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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "prune"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_prune_removes_every_sandbox_and_leaves_real_profile_intact() -> None:
    """A confirmed ``prune`` discards every sandbox while leaving ``main`` (and its facts) untouched."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "delta", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "epsilon", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0

    archived = _invoke(("config", "profile", "sandbox", "archive", "sleeper", "--yes"))
    assert archived.exit_code == 0, archived.output
    assert "label\tsandbox:sleeper" in archived.output

    # Off the live surface...
    assert read_profile_bucket("sandbox:sleeper") is None
    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:sleeper" not in listing.output

    # ...but still resolvable by id, and the directory/manifest survive.
    from ....adapters.persistence.storage.bucket import BucketLifecycleStatus, bucket_paths, manifest_path
    from ....core.config import load_settings

    pointer = read_profile_bucket_by_id(bucket_id)
    assert pointer is not None
    assert pointer.status is BucketLifecycleStatus.TOMBSTONED
    paths = bucket_paths(load_settings().aeat_local_storage_root, bucket_id)
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
    assert _invoke(("config", "switch", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "restore", "never-dormant"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_restore_brings_an_archived_sandbox_back_with_data_intact() -> None:
    """``restore`` reverses ``archive``: the sandbox reappears on the live surface with its data intact."""
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "roundtrip", "--from-profile", "main")).exit_code == 0
    edited = _invoke(("config", "profile", "edit", "sandbox:roundtrip", "--quiet", "--activity", "archived-experiment"))
    assert edited.exit_code == 0, edited.output
    assert _invoke(("config", "switch", "main")).exit_code == 0

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

    assert _invoke(("config", "switch", "sandbox:roundtrip")).exit_code == 0
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
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "create", "usage-b", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "switch", "main")).exit_code == 0

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
    assert _invoke(("config", "switch", "main")).exit_code == 0
    assert _invoke(("config", "profile", "sandbox", "archive", "dormant", "--yes")).exit_code == 0

    report = _invoke(("config", "profile", "sandbox", "usage", "dormant"))
    assert report.exit_code == 0, report.output
    assert "sandbox:dormant" in report.output

    # Still archived: the usage report is read-only and did not reactivate it.
    from ....application.workflow import read_profile_bucket

    assert read_profile_bucket("sandbox:dormant") is None
    assert read_profile_bucket("sandbox:dormant", include_tombstoned=True) is not None
    assert read_profile_bucket("sandbox:one-way") is None
