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

    with caplog.at_level(logging.DEBUG, logger="aeat.application.workflow._profile_bucket_scan"):
        pointers = list_profile_buckets(root=tmp_path)

    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert pointers == {}
    assert len(issues) == 1
    assert issues[0].bucket_id == "operator"
    assert issues[0].reason.startswith("TOMLDecodeError:")
    assert "skipping unreadable bucket manifest bucket_id=operator" in caplog.text
