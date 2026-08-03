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

from ...tests import REPO_ROOT
from .._config_state_root import RunMode, StateRootInputs, detect_run_mode, platform_user_data_root
from ..paths import (
    WINDOWS_MAX_PATH,
    WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH,
    is_windows_long_path_error,
    resolve_project_path,
    resolve_relative_subpath,
    windows_long_paths_enabled,
    windows_storage_root_long_path_margin,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Return a freshly-created records root."""
    root_dir = tmp_path / "records"
    root_dir.mkdir()
    return root_dir


# ----------------------------------------------------------------- #
# resolve_relative_subpath                                           #
# ----------------------------------------------------------------- #


def test_resolve_relative_subpath_rejects_unsafe_paths(root: Path) -> None:
    """Unsafe relative-path shapes fail closed before callers can escape the root."""
    for subpath, error_match in (
        (r"sub\dir\file.txt", r"forward slashes only"),
        ("../escape", r"stay within the owning root"),
        ("/abs/path", r"stay within the owning root"),
    ):
        with pytest.raises(ValueError, match=error_match):
            resolve_relative_subpath(root, subpath, context="path")


def test_resolve_relative_subpath_accepts_nested_path(root: Path) -> None:
    """A normal nested forward-slash path resolves under root."""
    resolved = resolve_relative_subpath(root, "sub/dir/file.txt", context="path")
    assert resolved.is_relative_to(root.resolve())
    assert resolved.name == "file.txt"


# ----------------------------------------------------------------- #
# resolve_project_path — RunMode-aware relative-path anchoring       #
# ----------------------------------------------------------------- #


def _installed_state_root_inputs(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build an ``installed`` context whose platform base is ``base``.

    Mirrors ``_installed_inputs_under`` in ``test_config_state_root.py``: the
    project-root candidate is a marker-free directory (no ``pyproject.toml``
    / ``.git``) so :func:`~cadrumo.core._config_state_root.detect_run_mode`
    classifies it installed, and the per-platform environment variable points
    at ``base`` — a host-absolute ``tmp_path`` — so the resolver's
    absolute-path acceptance holds on any host.
    """
    candidate = base / "site-packages" / "cadrumo" / "core"
    if platform == "win32":
        environ = {"LOCALAPPDATA": str(base)}
    elif platform == "linux":
        environ = {"XDG_DATA_HOME": str(base)}
    else:
        environ = {}
    return StateRootInputs(
        project_root_candidate=candidate,
        platform=platform,
        environ=environ,
        home=base / "home",
    )


def test_resolve_project_path_checkout_mode_anchors_under_project_root() -> None:
    """A checkout-mode relative override anchors under ``PROJECT_ROOT``.

    Uses the real live process inputs (this test always runs from a real
    checkout carrying ``pyproject.toml`` and ``.git``), proving the checkout
    branch stays byte-identical to the historical unconditional
    ``PROJECT_ROOT``-anchoring behaviour — no injected seam needed.
    """
    resolved = resolve_project_path("some-relative-dir")
    assert resolved == (REPO_ROOT / "some-relative-dir").resolve()


def test_resolve_project_path_installed_mode_anchors_under_platform_user_data_root(
    tmp_path: Path,
) -> None:
    """An installed-mode relative override anchors under the platform user-data root.

    This is the defect this change closes: before the fix,
    ``resolve_project_path`` anchored every relative override at the naive
    ``PROJECT_ROOT`` checkout-root walk regardless of run mode, so an
    installed distribution's relative ``CADRUMO_LOCAL_STORAGE_ROOT`` (or any
    other relative operator override) could resolve inside a virtualenv or
    an ephemeral package cache. Driven through the injectable
    ``StateRootInputs`` seam (no installed wheel is available in this
    environment) so resolution is deterministic and the ambient process is
    never mutated.
    """
    inputs = _installed_state_root_inputs(tmp_path)
    assert detect_run_mode(inputs) is RunMode.INSTALLED

    resolved = resolve_project_path("some-relative-dir", state_root_inputs=inputs)

    expected_base = platform_user_data_root(inputs)
    assert resolved == (expected_base / "some-relative-dir").resolve()
    assert REPO_ROOT not in resolved.parents
    assert "site-packages" not in resolved.parts


def test_resolve_project_path_absolute_value_ignores_run_mode(tmp_path: Path) -> None:
    """An absolute override resolves unchanged regardless of run mode.

    Only relative overrides are anchor-sensitive; an absolute path is
    returned resolved as-is in both checkout and installed contexts.
    """
    absolute = tmp_path / "explicit-storage"
    inputs = _installed_state_root_inputs(tmp_path)

    assert resolve_project_path(absolute) == absolute.resolve()
    assert resolve_project_path(absolute, state_root_inputs=inputs) == absolute.resolve()


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
        # winerror is a real attribute only on the win32 OSError; set it dynamically
        # so the classifier sees the same payload it reads off a live Windows error.
        setattr(exc, "winerror", winerror)  # noqa: B010
        assert is_windows_long_path_error(exc) is expected


def test_is_windows_long_path_error_rejects_non_long_path_errors() -> None:
    """Plain ``OSError`` and unrelated WinError payloads do not classify as long-path."""
    assert is_windows_long_path_error(OSError("generic failure")) is False

    exc = OSError(0, "boom")
    setattr(exc, "winerror", 5)  # real ERROR_ACCESS_DENIED payload  # noqa: B010
    assert is_windows_long_path_error(exc) is False


def test_windows_long_paths_enabled_returns_current_platform_contract() -> None:
    """The registry probe returns a real bool on Windows and ``None`` off Windows."""
    result = windows_long_paths_enabled()
    if sys.platform == "win32":
        assert isinstance(result, bool)
    else:
        assert result is None


def test_windows_storage_root_long_path_margin_shrinks_with_deeper_roots(tmp_path: Path) -> None:
    """A deeper, longer resolved root yields a strictly smaller margin than a shallow one."""
    shallow = tmp_path / "s"
    deep = tmp_path / ("segment-" + "x" * 60) / ("segment-" + "y" * 60)

    shallow_margin = windows_storage_root_long_path_margin(shallow)
    deep_margin = windows_storage_root_long_path_margin(deep)

    assert deep_margin < shallow_margin


def test_windows_storage_root_long_path_margin_matches_the_explicit_formula(tmp_path: Path) -> None:
    """The margin is exactly MAX_PATH minus the resolved root length minus the worst-case suffix."""
    root = tmp_path / "storage"
    expected = WINDOWS_MAX_PATH - len(str(root.resolve())) - WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH
    assert windows_storage_root_long_path_margin(root) == expected


def test_windows_worst_case_suffix_covers_the_real_bucket_layout_shape() -> None:
    """The worst-case suffix constant matches the real bucket blob-sidecar filename shape.

    Anti-tautology guard: recomputes the suffix from the real
    :mod:`cadrumo.adapters.persistence.storage` namespace constants and the
    real :mod:`cadrumo.adapters.outbound.storage._local` filename-building
    rules (HMAC prefix 8, label capped at 64 chars, ``.meta.json``
    sidecar extension) so a change to either shape is caught here instead
    of silently under-counting the margin.
    """
    from ...adapters.outbound.storage._local import _SIDECAR_EXTENSION
    from ...adapters.outbound.storage._object_name import _HMAC_PREFIX_LENGTH, sanitize_provider_object_label
    from ...adapters.persistence.storage import (
        BUCKET_BLOBS_DIRNAME,
        BUCKETS_DIRNAME,
    )
    from ...domain.user_profile import new_profile_id

    worst_label = sanitize_provider_object_label("x" * 200)  # clamps to 64 chars
    recomputed = (
        "\\"
        + BUCKETS_DIRNAME
        + "\\"
        + new_profile_id()  # canonical UUIDv4 string, always 36 chars
        + "\\"
        + BUCKET_BLOBS_DIRNAME
        + "\\"
        + ("a" * _HMAC_PREFIX_LENGTH)
        + "--"
        + worst_label
        + _SIDECAR_EXTENSION
    )
    assert len(recomputed) == WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH
