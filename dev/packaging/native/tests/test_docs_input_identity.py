"""Documentation reuse is portable only for the same enrolled source and authority."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .. import docs_build
from ..docs_build import shared_site_identity
from ..docs_input_identity import shared_docs_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _checkout(root: Path) -> tuple[Path, Path, tuple[Path, Path]]:
    root.mkdir()
    (root / "docs").mkdir()
    (root / "docs/page.md").write_bytes(b"same page\n")
    build = root / "build"
    build.mkdir()
    (build / "paths.json").write_text(str(build), encoding="utf-8")
    descriptor, database = root / "authority.json", root / "authority.sqlite3"
    descriptor.write_bytes(b"descriptor")
    database.write_bytes(b"database")
    inputs = build / "inputs.txt"
    inputs.write_text(f"{root / 'docs/page.md'}\n{build / 'paths.json'}\n", encoding="utf-8")
    return build, inputs, (descriptor, database)


def _identity(root: Path, build: Path, inputs: Path, authority: tuple[Path, Path]) -> str:
    return shared_site_identity(shared_docs_inputs(inputs, authority, source=root, build=build), ("en", "es"))


def test_separate_checkouts_reuse_identical_enrollment(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    a = _checkout(first)
    b = _checkout(second)
    assert _identity(first, *a) == _identity(second, *b)


def test_docs_owner_reuses_portable_site_and_rebuilds_changed_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "cache/docs"
    produced: list[Path] = []

    def produce(destination: Path, _work: Path, _languages: tuple[str, ...]) -> None:
        produced.append(destination)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "index.html").write_text("compiled site", encoding="utf-8")

    monkeypatch.setattr(docs_build, "_compile_roots", produce)
    monkeypatch.setattr(docs_build, "_index_site", lambda *_args: None)
    monkeypatch.setattr(docs_build, "dev_cache_dir", lambda _name: shared)
    for name in ("first", "second"):
        source = tmp_path / name
        build, inputs, authority = _checkout(source)
        (build / "build-paths.json").write_text(
            json.dumps({"paths": {"user_docs_build": "docs", "user_docs_work": "work"}}), encoding="utf-8"
        )
        monkeypatch.setattr(docs_build, "REPO_ROOT", source)
        monkeypatch.setattr(docs_build, "selected_published_authority", lambda _root, selected=authority: selected)
        docs_build.build_roots(build, inputs, target="windows-x86-64")
        assert (build / "docs/index.html").read_text() == "compiled site"
        assert (build / "docs/ready").is_file()
    assert len(produced) == 1
    (source / "docs/page.md").write_text("changed checkout", encoding="utf-8")
    docs_build.build_roots(build, inputs, target="windows-x86-64")
    assert len(produced) == 2


@pytest.mark.parametrize("change", ["content", "name", "add", "remove", "descriptor", "database", "language"])
def test_every_semantic_input_changes_identity(tmp_path: Path, change: str) -> None:
    root = tmp_path / "source"
    build, inputs, authority = _checkout(root)
    initial = _identity(root, build, inputs, authority)
    if change == "content":
        (root / "docs/page.md").write_bytes(b"changed page")
    elif change == "name":
        (root / "docs/page.md").rename(root / "docs/renamed.md")
        inputs.write_text(str(root / "docs/renamed.md") + "\n", encoding="utf-8")
    elif change == "add":
        extra = root / "docs/new.md"
        extra.write_bytes(b"same page\n")
        inputs.write_text(inputs.read_text() + str(extra) + "\n", encoding="utf-8")
    elif change == "remove":
        inputs.write_text(str(build / "paths.json") + "\n", encoding="utf-8")
    elif change in {"descriptor", "database"}:
        authority[int(change == "database")].write_bytes(b"new authority")
    elif change == "language":
        assert initial != shared_site_identity(
            shared_docs_inputs(inputs, authority, source=root, build=build), ("en", "es", "ca")
        )
        return
    assert _identity(root, build, inputs, authority) != initial


@pytest.mark.parametrize("alias", ["outside", "duplicate", "parent", "hardlink", "case"])
def test_external_and_ambiguous_source_inputs_are_refused(tmp_path: Path, alias: str) -> None:
    root = tmp_path / "source"
    build, inputs, authority = _checkout(root)
    page = root / "docs/page.md"
    if alias == "outside":
        extra = tmp_path / "unknown.md"
        extra.write_bytes(b"unowned input")
    elif alias == "duplicate":
        extra = page
    elif alias == "parent":
        extra = root / "docs/../docs/page.md"
    elif alias == "hardlink":
        extra = root / "docs/alias.md"
        os.link(page, extra)
    else:
        extra = root / "docs/PAGE.md"
        if not extra.exists():
            extra.write_bytes(b"different case collision")
    inputs.write_text(inputs.read_text() + str(extra) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        _identity(root, build, inputs, authority)


def test_source_symlink_is_not_a_second_name(tmp_path: Path) -> None:
    root = tmp_path / "source"
    build, inputs, authority = _checkout(root)
    link = root / "docs/link.md"
    try:
        link.symlink_to(root / "docs/page.md")
    except OSError:
        pytest.skip("Host cannot create symlinks")
    inputs.write_text(str(link) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="aliases"):
        _identity(root, build, inputs, authority)


def test_authority_roles_remain_distinct(tmp_path: Path) -> None:
    root = tmp_path / "source"
    build, inputs, authority = _checkout(root)
    with pytest.raises(ValueError, match="alias"):
        _identity(root, build, inputs, (authority[0], authority[0]))
