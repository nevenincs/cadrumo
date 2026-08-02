"""Real-behavior tests for profile-bucket manifest scanning."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from .._profile_bucket_scan import list_profile_bucket_scan_issues, list_profile_buckets

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_profile_bucket_scan_reports_malformed_manifest_without_live_surface_leak(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bucket_dir = tmp_path / "buckets" / "operator"
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text("bucket_id = [\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.workflow._profile_bucket_scan"):
        pointers = list_profile_buckets(root=tmp_path)

    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert pointers == {}
    assert len(issues) == 1
    assert issues[0].bucket_id == "operator"
    assert issues[0].reason.startswith("TOMLDecodeError:")
    assert "skipping unreadable bucket manifest bucket_id=operator" in caplog.text


def _manifest_toml(*, bucket_id: str, label: str) -> str:
    """Render a structurally complete manifest carrying ``label`` verbatim.

    Written as raw TOML rather than through ``write_manifest`` so the test can
    place a label the manifest model now refuses: the scenario is a manifest
    that is ALREADY malformed on disk, which the write boundary can no longer
    produce but the read path must still survive.
    """
    return (
        f'bucket_id = "{bucket_id}"\n'
        f'label = "{label}"\n'
        "created_at = 2026-05-14T12:00:00+00:00\n"
        "last_unlocked_at = 2026-05-14T12:00:00+00:00\n"
        "recovery_enrolled = false\n"
        "schema_version = 2\n"
        'status = "active"\n'
        'key_schedule = "bucket-dek-v1"\n'
        "\n"
        "[kdf_params]\n"
        'algorithm = "argon2id"\n'
        "version = 19\n"
        "memory_cost = 65536\n"
        "time_cost = 3\n"
        "parallelism = 4\n"
        'salt = "AAECAwQFBgcICQoLDA0ODw=="\n'
        "output_length = 32\n"
    )


@pytest.mark.parametrize(
    ("case", "label"),
    [("empty", ""), ("whitespace_only", "   "), ("overlong", "x" * 161)],
)
def test_malformed_label_becomes_a_scan_issue_instead_of_crashing_enumeration(
    tmp_path: Path,
    case: str,
    label: str,
) -> None:
    """A manifest whose label breaks the pointer contract is reported, not raised.

    The manifest label was an unconstrained string while the pointer required
    a trimmed 1..160 value, so such a manifest enumerated straight into an
    uncaught pydantic ValidationError out of ``list_profile_buckets`` -- and
    ``list_profile_bucket_scan_issues`` reported nothing, leaving the operator
    with a crash and no diagnosis. Both fields now carry one shared core
    constraint, so the manifest fails to load and lands in the issue surface.
    """
    bucket_id = "44444444-4444-4444-8444-444444444444"
    bucket_dir = tmp_path / "buckets" / bucket_id
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text(
        _manifest_toml(bucket_id=bucket_id, label=label),
        encoding="utf-8",
    )

    pointers = list_profile_buckets(root=tmp_path)
    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert pointers == {}, f"{case} label must not enumerate"
    assert len(issues) == 1
    assert issues[0].bucket_id == bucket_id


def test_a_valid_label_still_enumerates_and_raises_no_scan_issue(tmp_path: Path) -> None:
    """Positive control for the refusals above.

    Without this, the parametrized test would pass just as well if every
    manifest had stopped loading.
    """
    bucket_id = "44444444-4444-4444-8444-444444444444"
    bucket_dir = tmp_path / "buckets" / bucket_id
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text(
        _manifest_toml(bucket_id=bucket_id, label="Operator Bucket"),
        encoding="utf-8",
    )

    pointers = list_profile_buckets(root=tmp_path)

    assert list(pointers) == [bucket_id]
    assert pointers[bucket_id].label == "Operator Bucket"
    assert list_profile_bucket_scan_issues(root=tmp_path) == ()


def test_one_malformed_manifest_does_not_hide_the_other_profiles(tmp_path: Path) -> None:
    """The severe half of the old failure: one bad row took the whole list down.

    An uncaught ValidationError aborted the entire scan loop, so a single
    malformed manifest removed every OTHER profile from the operator's
    surface too. Enumeration must degrade to skipping the one bad bucket.
    """
    good_id = "11111111-1111-4111-8111-111111111111"
    bad_id = "22222222-2222-4222-8222-222222222222"
    for bucket_id, label in ((good_id, "Good Bucket"), (bad_id, "")):
        bucket_dir = tmp_path / "buckets" / bucket_id
        bucket_dir.mkdir(parents=True)
        (bucket_dir / "manifest.toml").write_text(
            _manifest_toml(bucket_id=bucket_id, label=label),
            encoding="utf-8",
        )

    pointers = list_profile_buckets(root=tmp_path)
    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert list(pointers) == [good_id]
    assert [issue.bucket_id for issue in issues] == [bad_id]


def test_manifest_claiming_another_bucket_never_reaches_the_live_surface(tmp_path: Path) -> None:
    """A manifest may not rename its own container.

    The directory name IS the bucket's identity: the storage route, keystore,
    and every secure-object row are addressed by it. The manifest's own
    ``bucket_id`` was validated only for shape, so a manifest claiming a
    different bucket enumerated cleanly and the scan published the CLAIMED id
    — a pointer resolved by directory carried the wrong identity while a
    lookup by the claimed id found nothing at all.
    """
    directory_id = "11111111-1111-4111-8111-111111111111"
    claimed_id = "22222222-2222-4222-8222-222222222222"
    bucket_dir = tmp_path / "buckets" / directory_id
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text(
        _manifest_toml(bucket_id=claimed_id, label="Impostor"),
        encoding="utf-8",
    )

    pointers = list_profile_buckets(root=tmp_path)
    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert claimed_id not in pointers, "the scan must not publish the claimed identity"
    assert pointers == {}
    assert len(issues) == 1
    assert issues[0].bucket_id == directory_id


def test_a_manifest_naming_its_own_directory_still_enumerates(tmp_path: Path) -> None:
    """Anti-tautology: the refusal above discriminates rather than always-refusing."""
    directory_id = "11111111-1111-4111-8111-111111111111"
    bucket_dir = tmp_path / "buckets" / directory_id
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text(
        _manifest_toml(bucket_id=directory_id, label="Genuine"),
        encoding="utf-8",
    )

    pointers = list_profile_buckets(root=tmp_path)

    assert list(pointers) == [directory_id]
    assert pointers[directory_id].label == "Genuine"
    assert list_profile_bucket_scan_issues(root=tmp_path) == ()
