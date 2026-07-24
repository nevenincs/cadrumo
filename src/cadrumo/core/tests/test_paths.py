"""Security-guardrail regression tests for the shared path helpers.

Pinned regression coverage for the path-handling boundary exposed by
:mod:`cadrumo.core.paths`. Each guardrail must pass against the canonical
shapes (filename tokens, nested forward-slash subpaths) AND fail closed
against every known bypass shape (parent traversal, shell
metacharacters, absolute-looking inputs, dotfiles, overlong tokens,
backslash-as-separator on Windows).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..paths import (
    WINDOWS_MAX_PATH,
    WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH,
    is_windows_long_path_error,
    resolve_record_json_path,
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
# resolve_record_json_path — accepted shapes                         #
# ----------------------------------------------------------------- #


def test_resolve_record_json_path_accepts_canonical_record_ids(root: Path) -> None:
    """Canonical record IDs resolve under root with a `.json` suffix."""
    for record_id in (
        "abc",
        "abc123",
        "MODELO_130_2025Q4",
        "draft-abc.v1",
        "a" + ("b" * 127),  # 128 chars, the max length
    ):
        resolved = resolve_record_json_path(root, record_id, context="record id")
        assert resolved.parent == root.resolve()
        assert resolved.name == f"{record_id}.json"
        # Containment guarantee: the resolved path is under root.
        assert resolved.is_relative_to(root.resolve())


# ----------------------------------------------------------------- #
# resolve_record_json_path — rejected shapes                         #
# ----------------------------------------------------------------- #


def test_resolve_record_json_path_rejects_unsafe_record_ids(root: Path) -> None:
    """Path-traversal / shell-metacharacter / overlong / dotfile shapes raise."""
    for record_id in (
        "../escape",  # parent traversal
        "subdir/file",  # forward slash
        "subdir\\file",  # backslash
        ".dotfile",  # leading dot (would create a hidden file)
        "-dashfirst",  # leading dash (rejected by the SAFE_FILE_TOKEN regex's first-char class)
        "",  # empty
        "a b",  # space
        "a;b",  # semicolon (shell metacharacter)
        "a$b",  # dollar (shell metacharacter)
        "a*b",  # glob metacharacter
        "a\nb",  # newline
        "a\x00b",  # null byte
        "a:b",  # colon (Windows drive separator)
        "a" + ("b" * 128),  # 129 chars, one past the max
        ".",  # bare dot
        "..",  # parent
        "/abs",  # absolute-looking
    ):
        with pytest.raises(ValueError) as excinfo:
            resolve_record_json_path(root, record_id, context="record id")
        # The context label appears in the error so callers know which arg failed.
        assert "record id" in str(excinfo.value)


def test_resolve_record_json_path_context_label_propagates(root: Path) -> None:
    """The error message names the context the caller supplied."""
    with pytest.raises(ValueError, match=r"draft id must be a simple filename token"):
        resolve_record_json_path(root, "../escape", context="draft id")


def test_resolve_record_json_path_returns_under_root_even_with_relative_root(
    tmp_path: Path,
) -> None:
    """Containment holds when the root is supplied as a relative path."""
    relative_root = Path("records-relative")
    (tmp_path / relative_root).mkdir()
    # Resolve from the test working directory rather than passing a
    # pre-resolved path, mimicking how callers wire up their dirs.
    import os

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        resolved = resolve_record_json_path(relative_root, "abc", context="id")
    finally:
        os.chdir(cwd)
    assert resolved.is_relative_to((tmp_path / relative_root).resolve())


# ----------------------------------------------------------------- #
# resolve_relative_subpath — covered for completeness                #
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
    from ...adapters.outbound.storage._local import _HMAC_PREFIX_LEN, _SIDECAR_EXTENSION, _validate_label
    from ...adapters.persistence.storage import (
        BUCKET_BLOBS_DIRNAME,
        BUCKETS_DIRNAME,
    )
    from ...domain.user_profile import new_profile_id

    worst_label = _validate_label("x" * 200)  # clamps to 64 chars
    recomputed = (
        "\\"
        + BUCKETS_DIRNAME
        + "\\"
        + new_profile_id()  # canonical UUIDv4 string, always 36 chars
        + "\\"
        + BUCKET_BLOBS_DIRNAME
        + "\\"
        + ("a" * _HMAC_PREFIX_LEN)
        + "--"
        + worst_label
        + _SIDECAR_EXTENSION
    )
    assert len(recomputed) == WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH
