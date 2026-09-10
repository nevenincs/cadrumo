"""The in-process repository enumeration, naming and copying.

Every case builds its own tree under ``tmp_path``, so each rule is proven on a
planted defect rather than on whatever the live repository happens to contain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..source_tree import content_digest, normalised_content, normalised_contents, repository_files, snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, relative: str, content: bytes | str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_bytes(content.encode("utf-8"))
    else:
        path.write_bytes(content)


def test_an_ignored_file_is_excluded_and_a_negation_brings_one_back(tmp_path: Path) -> None:
    _write(tmp_path, ".gitignore", "*.log\n!keep.log\n")
    _write(tmp_path, "noise.log", "x")
    _write(tmp_path, "keep.log", "x")
    _write(tmp_path, "source.py", "x")

    assert repository_files(tmp_path) == (".gitignore", "keep.log", "source.py")


def test_a_file_nobody_ignored_is_in_scope_whether_or_not_it_was_ever_committed(tmp_path: Path) -> None:
    """A new file is repository content; a checker that skipped it would pass it unread."""
    _write(tmp_path, "brand_new.py", "x")

    assert repository_files(tmp_path) == ("brand_new.py",)


def test_an_ignored_directory_is_never_entered(tmp_path: Path) -> None:
    """A rule cannot re-include a file whose parent directory is excluded, as in git."""
    _write(tmp_path, ".gitignore", "build/\n!build/wanted.py\n")
    _write(tmp_path, "build/wanted.py", "x")
    _write(tmp_path, "src/module.py", "x")

    assert repository_files(tmp_path) == (".gitignore", "src/module.py")


def test_a_nested_ignore_file_applies_below_its_own_directory_and_overrides_its_parent(tmp_path: Path) -> None:
    _write(tmp_path, ".gitignore", "*.tmp\n")
    _write(tmp_path, "pkg/.gitignore", "!kept.tmp\nlocal.txt\n")
    _write(tmp_path, "pkg/kept.tmp", "x")
    _write(tmp_path, "pkg/other.tmp", "x")
    _write(tmp_path, "pkg/local.txt", "x")
    _write(tmp_path, "local.txt", "x")

    assert repository_files(tmp_path) == (".gitignore", "local.txt", "pkg/.gitignore", "pkg/kept.tmp")


def test_the_version_control_entry_is_never_content_whether_directory_or_worktree_pointer(tmp_path: Path) -> None:
    _write(tmp_path, ".git/HEAD", "ref: refs/heads/main\n")
    _write(tmp_path, "linked/.git", "gitdir: elsewhere\n")
    _write(tmp_path, "linked/module.py", "x")

    assert repository_files(tmp_path) == ("linked/module.py",)


def test_under_narrows_to_the_named_paths_without_matching_a_mere_name_prefix(tmp_path: Path) -> None:
    _write(tmp_path, "src/a.py", "x")
    _write(tmp_path, "src_other/b.py", "x")
    _write(tmp_path, "top.py", "x")

    assert repository_files(tmp_path, under=("src", "top.py")) == ("src/a.py", "top.py")


def test_text_content_is_named_as_the_repository_records_it_on_every_platform(tmp_path: Path) -> None:
    """The same committed content has the same digest whatever line endings the checkout has."""
    windows = tmp_path / "windows"
    posix = tmp_path / "posix"
    for root, body in ((windows, b"a\r\nb\r\n"), (posix, b"a\nb\n")):
        _write(root, ".gitattributes", "* text=auto eol=lf\n")
        _write(root, "module.py", body)

    assert normalised_content(windows, "module.py") == b"a\nb\n"
    assert content_digest(windows, repository_files(windows)) == content_digest(posix, repository_files(posix))


def test_a_path_marked_binary_or_minus_text_keeps_every_byte(tmp_path: Path) -> None:
    """Corpus files are content-addressed evidence; a translated byte breaks their declared digest."""
    _write(tmp_path, ".gitattributes", "* text=auto eol=lf\ncorpus/** -text\n*.pdf binary\n")
    _write(tmp_path, "corpus/source.html", b"<p>\r\n</p>\r\n")
    _write(tmp_path, "form.pdf", b"%PDF\r\n")

    assert normalised_content(tmp_path, "corpus/source.html") == b"<p>\r\n</p>\r\n"
    assert normalised_content(tmp_path, "form.pdf") == b"%PDF\r\n"


def test_auto_detection_leaves_a_file_with_a_nul_byte_untouched(tmp_path: Path) -> None:
    _write(tmp_path, ".gitattributes", "* text=auto eol=lf\n")
    _write(tmp_path, "blob.dat", b"\x00\r\n")

    assert normalised_content(tmp_path, "blob.dat") == b"\x00\r\n"


def test_a_crlf_rule_writes_crlf_and_a_nested_attributes_file_overrides_its_parent(tmp_path: Path) -> None:
    _write(tmp_path, ".gitattributes", "* text=auto eol=lf\n*.bat text eol=crlf\ncorpus/** -text\n")
    _write(tmp_path, "corpus/.gitattributes", "*.txt text eol=lf\n")
    _write(tmp_path, "run.bat", b"echo\n")
    _write(tmp_path, "corpus/notes.txt", b"a\r\n")
    _write(tmp_path, "corpus/page.html", b"a\r\n")

    assert normalised_content(tmp_path, "run.bat") == b"echo\r\n"
    assert normalised_content(tmp_path, "corpus/notes.txt") == b"a\n"
    assert normalised_content(tmp_path, "corpus/page.html") == b"a\r\n"


def test_the_digest_changes_with_content_and_cannot_confuse_a_path_with_content(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write(first, "ab", "c")
    _write(second, "a", "bc")

    assert content_digest(first, ("ab",)) != content_digest(second, ("a",))
    before = content_digest(first, ("ab",))
    _write(first, "ab", "d")
    assert content_digest(first, ("ab",)) != before


def test_a_snapshot_copies_the_recorded_content_and_never_merges_into_an_existing_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write(source, ".gitattributes", "* text=auto eol=lf\n")
    _write(source, "pkg/module.py", b"a\r\n")
    files = repository_files(source)
    destination = tmp_path / "copy"

    snapshot(source, files, destination)

    assert (destination / "pkg" / "module.py").read_bytes() == b"a\n"
    assert repository_files(destination) == files
    with pytest.raises(FileExistsError):
        snapshot(source, files, destination)


def test_a_caller_naming_only_part_of_the_tree_still_gets_the_root_rules(tmp_path: Path) -> None:
    """Rules come from each path's ancestry, never from the list the caller happened to pass.

    Naming only files under one directory must not drop the root
    ``.gitattributes``: without it a byte-exact corpus file would be translated.
    """
    _write(tmp_path, ".gitattributes", "* text=auto eol=lf\ncorpus/** -text\n")
    _write(tmp_path, "corpus/source.html", b"<p>\r\n")
    _write(tmp_path, "src/module.py", b"a\r\n")
    subset = repository_files(tmp_path, under=("corpus", "src"))

    assert ".gitattributes" not in subset
    assert dict(normalised_contents(tmp_path, subset)) == {"corpus/source.html": b"<p>\r\n", "src/module.py": b"a\n"}


def test_under_applies_every_ancestor_rule_and_excludes_an_ignored_ancestor(tmp_path: Path) -> None:
    _write(tmp_path, ".gitignore", "vendor/\n*.log\n")
    _write(tmp_path, "pkg/.gitignore", "local/\n")
    _write(tmp_path, "vendor/lib/code.py", "x")
    _write(tmp_path, "pkg/local/secret.py", "x")
    _write(tmp_path, "pkg/sub/debug.log", "x")
    _write(tmp_path, "pkg/sub/kept.py", "x")

    assert repository_files(tmp_path, under=("vendor/lib",)) == ()
    assert repository_files(tmp_path, under=("pkg/local",)) == ()
    assert repository_files(tmp_path, under=("pkg/sub",)) == ("pkg/sub/kept.py",)
    assert repository_files(tmp_path, under=("pkg",)) == tuple(
        path for path in repository_files(tmp_path) if path.startswith("pkg/")
    )
