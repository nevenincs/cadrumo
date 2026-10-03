"""Reject replaced native archives before discarding prior acceptance evidence."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from dev.packaging.native.artifact_verify import check
from dev.packaging.native.hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_replaced_archive_preserves_previous_acceptance(tmp_path: Path) -> None:
    """A same-name replacement must not inherit the original package's identity."""
    archive = tmp_path / "product.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/content.txt", "original")
    locator = {"archive": str(archive), "archive_sha256": digest(archive)}
    (tmp_path / "artifacts-Release.json").write_text(json.dumps(locator), encoding="utf-8")
    previous = tmp_path / "verification/Release/result.json"
    previous.parent.mkdir(parents=True)
    previous.write_text("previous evidence", encoding="utf-8")
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/content.txt", "replaced")

    with pytest.raises(AssertionError, match="ZIP differs from the packaged artifact locator"):
        check(tmp_path, "Release")

    assert previous.read_text(encoding="utf-8") == "previous evidence"
