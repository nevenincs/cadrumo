"""Bucket-safety contracts of the landing-page publisher."""

from __future__ import annotations

from pathlib import Path

import pytest
from dev.deploy.frontend_static_site import (
    _PROTECTED_PREFIX_EXCLUDES,
    _REQUIRED_ARTIFACTS,
    _validate_site_artifacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _complete_build(root: Path) -> None:
    """Materialise every artifact the publisher requires."""
    for artifact in _REQUIRED_ARTIFACTS:
        (root / artifact).write_text("x", encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("x", encoding="utf-8")
    (assets / "index-abc123.css").write_text("x", encoding="utf-8")


def test_docs_prefix_is_always_excluded_from_the_root_sync() -> None:
    """The shared bucket's documentation prefix must never be sync targets."""
    assert "docs/*" in _PROTECTED_PREFIX_EXCLUDES


def test_validate_accepts_a_complete_build(tmp_path: Path) -> None:
    """A build carrying every required artifact passes validation."""
    _complete_build(tmp_path)
    _validate_site_artifacts(tmp_path)


@pytest.mark.parametrize("missing", sorted(_REQUIRED_ARTIFACTS))
def test_validate_refuses_a_build_missing_a_required_artifact(
    tmp_path: Path,
    missing: str,
) -> None:
    """Each required artifact's absence refuses the publish."""
    _complete_build(tmp_path)
    (tmp_path / missing).unlink()
    with pytest.raises(SystemExit, match=missing.replace(".", "\\.")):
        _validate_site_artifacts(tmp_path)


def test_validate_refuses_a_build_without_bundled_assets(tmp_path: Path) -> None:
    """An empty assets directory refuses the publish."""
    _complete_build(tmp_path)
    for bundle in (tmp_path / "assets").iterdir():
        bundle.unlink()
    with pytest.raises(SystemExit, match="bundled assets"):
        _validate_site_artifacts(tmp_path)
