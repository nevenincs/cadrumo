"""Security-guardrail regression tests for the shared path helpers.

Pinned regression coverage for the path-handling boundary exposed by
:mod:`cadrumo.core.paths`. Each guardrail must pass against the canonical
shape (a nested forward-slash subpath) AND fail closed against every known
bypass shape (parent traversal, absolute-looking inputs,
backslash-as-separator on Windows).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..config_state_root import StateRootInputs, platform_user_data_root
from ..paths import (
    effective_storage_root,
    is_windows_long_path_error,
    resolve_project_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ----------------------------------------------------------------- #
# resolve_project_path — relative-path anchoring (no run-mode branch)  #
# ----------------------------------------------------------------- #


def _inputs_under(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build a deterministic context whose platform base is ``base``.

    Carries no project-root candidate: production no longer has one. The
    per-platform environment variable points at ``base`` — a host-absolute
    ``tmp_path`` — so the resolver's absolute-path acceptance holds on any host.
    """
    if platform == "win32":
        environ = {"LOCALAPPDATA": str(base)}
    elif platform == "linux":
        environ = {"XDG_DATA_HOME": str(base)}
    else:
        environ = {}
    return StateRootInputs(platform=platform, environ=environ, home=base / "home")


def test_a_relative_override_anchors_under_the_platform_user_data_root(tmp_path: Path) -> None:
    """A relative override anchors under the platform user-data root, always.

    This closes two defects in sequence. The first was anchoring every
    relative override at a naive repo-root walk, so an installed
    distribution's relative ``CADRUMO_LOCAL_STORAGE_ROOT`` could resolve
    inside a virtualenv or an ephemeral package cache. The second was the
    fix's own shape: it branched on whether the process ran from a source
    checkout, which made a source-layout guess decide where operator data
    was written. There is now no branch to take.
    """
    inputs = _inputs_under(tmp_path)

    resolved = resolve_project_path("some-relative-dir", state_root_inputs=inputs)

    expected_base = platform_user_data_root(inputs)
    assert resolved == (expected_base / "some-relative-dir").resolve()
    assert "site-packages" not in resolved.parts


def test_the_anchor_does_not_change_beside_repository_markers(tmp_path: Path) -> None:
    """A ``pyproject.toml`` and ``.git`` beside the process change nothing.

    The discriminating case. The retired implementation classified a context
    carrying these two markers as a checkout and anchored somewhere else
    entirely; production must now be blind to them. Creating them and
    observing an unchanged answer is what proves the detection is gone
    rather than merely unused on this host.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    inputs = _inputs_under(tmp_path)

    resolved = resolve_project_path("some-relative-dir", state_root_inputs=inputs)

    assert resolved == (platform_user_data_root(inputs) / "some-relative-dir").resolve()


def test_an_absolute_override_resolves_unchanged(tmp_path: Path) -> None:
    """An absolute override is returned resolved as-is; only relatives anchor."""
    absolute = tmp_path / "explicit-storage"
    inputs = _inputs_under(tmp_path)

    assert resolve_project_path(absolute) == absolute.resolve()
    assert resolve_project_path(absolute, state_root_inputs=inputs) == absolute.resolve()


# ----------------------------------------------------------------- #
# effective_storage_root — the shared override-or-settings-default   #
# accessor six call sites each re-implemented inline                 #
# ----------------------------------------------------------------- #


def test_effective_storage_root_relative_override_anchors_under_platform_user_data_root(tmp_path: Path) -> None:
    """A relative override anchors under the platform user-data root, one level above ``storage/``.

    This is the property the six duplicated inline copies got wrong in two
    different ways: one resolved a relative override against the process
    current working directory (``Path.resolve()`` with no anchor), the other
    four returned it completely unnormalised. Neither anchors under the
    platform user-data root the way every other relative operator path in
    this codebase does; this accessor is the single place that does.
    """
    inputs = _inputs_under(tmp_path)

    resolved = effective_storage_root(Path("some-relative-dir"), state_root_inputs=inputs)

    expected_base = platform_user_data_root(inputs)
    assert resolved == (expected_base / "some-relative-dir").resolve()
    # Never nested under the settings storage root itself (one level below
    # the anchor) -- the defect a bare Path.resolve() on the cwd could
    # otherwise mask if the test happened to run from inside a storage tree.
    assert resolved != (expected_base / "storage" / "some-relative-dir").resolve()


def test_effective_storage_root_absolute_override_resolves_unchanged() -> None:
    """An absolute override is returned resolved as-is."""
    from ..config import override_settings

    with override_settings() as settings:
        absolute = settings.cadrumo_local_storage_root.parent / "explicit-override"
        assert effective_storage_root(absolute) == absolute.resolve()


def test_effective_storage_root_falls_back_to_the_settings_default_when_no_override_is_given() -> None:
    """``root=None`` resolves ``Settings.cadrumo_local_storage_root``, not a fresh anchor."""
    from ..config import override_settings

    with override_settings(cadrumo_local_storage_root=Path("configured-root")) as settings:
        assert effective_storage_root() == settings.cadrumo_local_storage_root
        assert effective_storage_root(None) == settings.cadrumo_local_storage_root


def test_effective_storage_root_prefers_an_explicit_settings_object_over_reloading() -> None:
    """A caller-supplied ``settings=`` is read directly rather than triggering ``load_settings()`` again.

    Every one of the six converged call sites in ``config_reset_repository.py``
    and ``_bundle_export_operation.py`` already holds a resolved ``Settings``
    instance when it has one, and must not pay for a second load just to
    resolve the fallback root.
    """
    from ..config import override_settings

    with (
        override_settings(cadrumo_local_storage_root=Path("caller-held-root")) as held_settings,
        override_settings(cadrumo_local_storage_root=Path("ambient-root")),
    ):
        assert effective_storage_root(settings=held_settings) == held_settings.cadrumo_local_storage_root


def test_effective_storage_root_override_wins_over_a_supplied_settings_object() -> None:
    """An explicit ``root`` always wins, even when ``settings=`` is also supplied."""
    from ..config import override_settings

    with override_settings() as settings:
        override_root = settings.cadrumo_local_storage_root.parent / "override-wins"
        assert effective_storage_root(override_root, settings=settings) == override_root.resolve()


# ----------------------------------------------------------------- #
# Windows MAX_PATH (long-path) hardening                             #
# ----------------------------------------------------------------- #


def test_is_windows_long_path_error_classifies_known_winerrors_for_current_platform() -> None:
    """WinError 3 (path not found) and 206 (filename too long) both classify as long-path failures.

    These are the two concrete Windows API error codes CPython's ``OSError``
    carries (as ``.winerror``) when a resolved path walks past ``MAX_PATH``
    on a legacy (non long-path-aware) configuration. Off Windows, the helper
    short-circuits to ``False`` for the same concrete error payload.
    """
    expected = sys.platform == "win32"
    for winerror in (3, 206):
        exc = OSError(0, "boom")
        # winerror is a real attribute only on the win32 OSError; set it through
        # setattr so the classifier sees the same payload it reads off a live
        # Windows error without the test naming an attribute that does not exist
        # when the tree is analysed for another platform.
        setattr(exc, "winerror", winerror)  # noqa: B010
        assert is_windows_long_path_error(exc) is expected


def test_is_windows_long_path_error_rejects_non_long_path_errors() -> None:
    """Plain ``OSError`` and unrelated WinError payloads do not classify as long-path."""
    assert is_windows_long_path_error(OSError("generic failure")) is False

    exc = OSError(0, "boom")
    setattr(exc, "winerror", 5)  # noqa: B010  # real ERROR_ACCESS_DENIED payload
    assert is_windows_long_path_error(exc) is False
