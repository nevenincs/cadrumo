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
    """Materialise every artifact the publisher requires.

    ``index.html`` references the bundles this fixture writes, because that is
    what a real build emits and what validation now checks. The earlier version
    wrote the placeholder ``"x"`` for every artifact, so the page referenced no
    bundles at all and the reference check had nothing to compare -- a complete
    build fixture that was complete only by the weaker definition.
    """
    for artifact in _REQUIRED_ARTIFACTS:
        (root / artifact).write_text("x", encoding="utf-8")
    (root / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="/assets/index-abc123.css">'
        '<script type="module" src="/assets/index-abc123.js"></script></head><body></body></html>',
        encoding="utf-8",
    )
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


def test_validate_refuses_a_page_referencing_a_bundle_that_was_never_written(tmp_path: Path) -> None:
    """A present-but-wrong asset set is refused, not waved through.

    "Some .js and some .css exist" is satisfied by leftovers from an earlier
    build while ``index.html`` points at a bundle that was never written. The
    browser requests what the page names, so the page's own references are what
    must resolve; the count of files in ``assets/`` is not the property.
    """
    _complete_build(tmp_path)
    (tmp_path / "index.html").write_text(
        '<html><head><script src="/assets/index-NEVER-WRITTEN.js"></script></head><body></body></html>',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        _validate_site_artifacts(tmp_path)

    message = str(excinfo.value)
    assert "index-NEVER-WRITTEN.js" in message
    # The old check still passes on this build, which is why it could not catch it.
    assets = tmp_path / "assets"
    assert any(assets.glob("*.js")) and any(assets.glob("*.css"))


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


def test_validate_refuses_a_landing_page_without_bundle_references(tmp_path: Path) -> None:
    """A complete artifact set cannot publish a blank page that loads none of its bundles."""
    _complete_build(tmp_path)
    (tmp_path / "index.html").write_text("<html><body>blank</body></html>", encoding="utf-8")

    with pytest.raises(SystemExit, match="references no bundled assets"):
        _validate_site_artifacts(tmp_path)


def test_hashed_assets_are_immutable_and_never_invalidated() -> None:
    """Content-hashed assets carry a forever cache and skip invalidation."""
    from dev.deploy.frontend_static_site import _ASSET_CACHE_CONTROL, _INVALIDATION_PATHS

    assert "immutable" in _ASSET_CACHE_CONTROL
    assert "/assets/*" not in _INVALIDATION_PATHS
