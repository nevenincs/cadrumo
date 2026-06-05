"""Real-behaviour tests for the packaged-data resource locator."""

from __future__ import annotations

from importlib.resources.abc import Traversable
from pathlib import Path

import pytest

from ..resources import as_path, packaged_data

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_packaged_data_root_is_a_directory() -> None:
    """Calling :func:`packaged_data` with no parts returns the bundled root."""

    root = packaged_data()

    assert isinstance(root, Traversable)
    assert root.is_dir()


def test_corpus_root_is_a_directory() -> None:
    """The corpus subtree resolves to a directory."""

    assert packaged_data("corpus").is_dir()


def test_registry_root_is_a_directory() -> None:
    """The registry subtree resolves to a directory."""

    assert packaged_data("registry").is_dir()


@pytest.mark.parametrize(
    "parts",
    [
        ("corpus", "manuals", "iva", "2025", "manifest.json"),
        ("corpus", "manuals", "renta", "2025", "part1", "source.pdf"),
        ("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json"),
        ("corpus", "normatives", "html", "ley-27-2014-art-100.html"),
        ("registry", "aeat", "modelos", "036", "manifest.toml"),
        ("registry", "aeat", "modelos", "100", "manifest.toml"),
        ("registry", "aeat", "legal", "iva-flow.toml"),
        ("registry", "aeat", "iva", "rates.toml"),
        ("registry", "aeat", "calendars", "festivos-2025.toml"),
        ("registry", "aeat", "user_profile", "schema.toml"),
    ],
)
def test_representative_leaves_are_files(parts: tuple[str, ...]) -> None:
    """Every representative leaf across every top-level subtree resolves to a real file."""

    node = packaged_data(*parts)

    assert node.is_file(), f"missing bundled file: {'/'.join(parts)}"


@pytest.mark.parametrize(
    "parts",
    [
        ("corpus", "parity_replays", "renta_web_open"),
        ("registry", "aeat", "topics"),
    ],
)
def test_representative_subtrees_are_directories(parts: tuple[str, ...]) -> None:
    """Top-level subtree containers resolve to real directories."""

    node = packaged_data(*parts)

    assert node.is_dir(), f"missing bundled directory: {'/'.join(parts)}"


def test_joinpath_composition_matches_variadic_call() -> None:
    """Variadic ``packaged_data`` composition matches Traversable.joinpath chaining."""

    variadic = packaged_data("registry", "aeat", "modelos", "036", "manifest.toml")
    chained = packaged_data("registry").joinpath("aeat", "modelos", "036", "manifest.toml")

    assert variadic.is_file()
    assert chained.is_file()


def test_as_path_yields_a_real_pathlib_path() -> None:
    """:func:`as_path` materialises a Traversable as a usable on-disk path."""

    node = packaged_data("registry", "aeat", "modelos", "036", "manifest.toml")

    with as_path(node) as p:
        assert isinstance(p, Path)
        assert p.is_file()
        payload = p.read_bytes()

    assert len(payload) > 0
    # The Modelo 036 manifest is a TOML file; it must contain at least one section header.
    assert b"[" in payload


def test_read_bytes_from_traversable_directly() -> None:
    """A Traversable supports ``read_bytes`` without materialising a temp path."""

    node = packaged_data("registry", "aeat", "modelos", "036", "manifest.toml")

    payload = node.read_bytes()

    assert len(payload) > 0
