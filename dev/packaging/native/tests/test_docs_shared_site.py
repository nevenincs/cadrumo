"""One built documentation site serves every build configuration of a checkout.

The documentation reads the sources, the registry authority and the declared
languages; it does not read the platform or the directory a configuration builds
in. These tests build a small real site on disk through the same reuse path the
package build takes, and count how often it had to be produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..action_cache import completed, current, fingerprint
from ..docs_build import shared_site_identity, take_shared_site

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LANGUAGES = ("en", "es")


class _Site:
    """Writes a two-language site, and remembers how many times it was asked to."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.produced = 0

    def __call__(self, destination: Path) -> None:
        self.produced += 1
        for language in _LANGUAGES:
            page = destination / "html" / language / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(f"{self.text} {language}", encoding="utf-8")


def _pages(build_root: Path) -> dict[str, str]:
    return {
        path.relative_to(build_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(build_root.rglob("*"))
        if path.is_file()
    }


def test_a_second_configuration_copies_the_site_the_first_one_built(tmp_path: Path) -> None:
    """Two platform presets with the same inputs cost one documentation build."""
    site = _Site("one")
    shared = tmp_path / "cache" / "user-docs"
    first, second = tmp_path / "linux-x86-64" / "docs", tmp_path / "linux-aarch64" / "docs"

    assert take_shared_site(first, shared, "identity", site, validate_inputs=lambda: None) is True
    assert take_shared_site(second, shared, "identity", site, validate_inputs=lambda: None) is False

    assert site.produced == 1
    assert _pages(second) == {"html/en/index.html": "one en", "html/es/index.html": "one es"}
    assert _pages(second) == _pages(first)


def test_a_copied_site_carries_no_completion_marker_of_the_cache(tmp_path: Path) -> None:
    """A configuration completes its own directory against its own identity."""
    shared = tmp_path / "cache" / "user-docs"
    build_root = tmp_path / "build" / "docs"
    take_shared_site(tmp_path / "first" / "docs", shared, "identity", _Site("one"), validate_inputs=lambda: None)

    take_shared_site(build_root, shared, "identity", _Site("one"), validate_inputs=lambda: None)

    assert (shared / "ready").is_file()
    assert not (build_root / "ready").exists()
    completed(build_root, "the configuration's own identity")
    assert current(build_root, "the configuration's own identity")


def test_changed_inputs_replace_the_one_shared_site(tmp_path: Path) -> None:
    """The cache holds one site, so a checkout's cache does not grow with its history."""
    shared = tmp_path / "cache" / "user-docs"
    take_shared_site(tmp_path / "a" / "docs", shared, "before", _Site("old"), validate_inputs=lambda: None)
    changed = _Site("new")

    assert take_shared_site(tmp_path / "b" / "docs", shared, "after", changed, validate_inputs=lambda: None) is True

    assert changed.produced == 1
    kept = _pages(shared)
    del kept["ready"]
    assert kept == {"html/en/index.html": "new en", "html/es/index.html": "new es"}
    assert current(shared, "after")
    assert not current(shared, "before")


def test_a_shared_site_altered_after_it_was_kept_is_built_again(tmp_path: Path) -> None:
    """Reuse is bound to the kept bytes, not to the marker beside them."""
    shared = tmp_path / "cache" / "user-docs"
    take_shared_site(tmp_path / "a" / "docs", shared, "identity", _Site("one"), validate_inputs=lambda: None)
    (shared / "html" / "es" / "index.html").write_text("tampered", encoding="utf-8")
    again = _Site("one")

    assert take_shared_site(tmp_path / "b" / "docs", shared, "identity", again, validate_inputs=lambda: None) is True

    assert again.produced == 1
    assert _pages(tmp_path / "b" / "docs")["html/es/index.html"] == "one es"


def test_a_stale_site_in_the_configuration_is_replaced_by_the_copy(tmp_path: Path) -> None:
    """What a configuration built from older inputs does not survive beside the copy."""
    shared = tmp_path / "cache" / "user-docs"
    build_root = tmp_path / "build" / "docs"
    stale = build_root / "html" / "hu" / "index.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("left over", encoding="utf-8")
    take_shared_site(tmp_path / "first" / "docs", shared, "identity", _Site("one"), validate_inputs=lambda: None)

    take_shared_site(build_root, shared, "identity", _Site("one"), validate_inputs=lambda: None)

    assert not stale.exists()


def test_the_shared_identity_ignores_what_a_configuration_keeps_in_its_own_directory(tmp_path: Path) -> None:
    """The same sources name the same site from two build directories, and changed sources do not."""
    source = tmp_path / "docs" / "index.md"
    source.parent.mkdir()
    source.write_text("page", encoding="utf-8")

    def configuration(name: str) -> tuple[Path, Path]:
        build = tmp_path / "build" / name
        build.mkdir(parents=True)
        (build / "build-paths.json").write_text(f'{{"preset": "{name}"}}', encoding="utf-8")
        listing = build / "inputs-user-docs.txt"
        listing.write_text(f"{source}\n{build / 'build-paths.json'}\n", encoding="utf-8")
        return build, listing

    (x86, x86_inputs), (arm, arm_inputs) = configuration("linux-x86-64"), configuration("linux-aarch64")

    assert fingerprint(x86_inputs) != fingerprint(arm_inputs)
    same = shared_site_identity(fingerprint(x86_inputs, outside=x86), _LANGUAGES)
    assert same == shared_site_identity(fingerprint(arm_inputs, outside=arm), _LANGUAGES)
    assert same != shared_site_identity(fingerprint(x86_inputs, outside=x86), (*_LANGUAGES, "ca"))

    source.write_text("page, edited", encoding="utf-8")
    assert same != shared_site_identity(fingerprint(x86_inputs, outside=x86), _LANGUAGES)
