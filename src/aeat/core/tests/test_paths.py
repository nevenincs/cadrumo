"""Security-guardrail regression tests for the shared path helpers.

Pinned regression coverage for the path-handling boundary exposed by
:mod:`aeat.core.paths`. Each guardrail must pass against the canonical
shapes (filename tokens, nested forward-slash subpaths) AND fail closed
against every known bypass shape (parent traversal, shell
metacharacters, absolute-looking inputs, dotfiles, overlong tokens,
backslash-as-separator on Windows).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..paths import resolve_record_json_path, resolve_relative_subpath

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
