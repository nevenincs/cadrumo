"""Real-behaviour tests for the packaged-data resource locator."""

from __future__ import annotations

from importlib.resources.abc import Traversable
from pathlib import Path

import pytest

from ..resources._boundary import as_path, packaged_data

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_packaged_data_directories_exist() -> None:
    """The bundled root and top-level subtrees resolve to directories."""

    cases: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("packaged-root", ()),
        ("corpus-root", ("corpus",)),
        ("registry-root", ("registry",)),
    )

    for case_id, parts in cases:
        root = packaged_data(*parts)

        assert isinstance(root, Traversable), case_id
        assert root.is_dir(), case_id


def test_representative_leaves_are_files() -> None:
    """Every representative leaf across every top-level subtree resolves to a real file."""

    cases: tuple[tuple[str, ...], ...] = (
        ("corpus", "manuals", "iva", "2025", "manifest.json"),
        ("corpus", "manuals", "renta", "2025", "part1", "source.pdf"),
        ("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json"),
        ("corpus", "normatives", "html", "ley-27-2014-art-100.html"),
        ("registry", "aeat", "modelos", "036", "manifest.toml"),
        ("registry", "aeat", "modelos", "100", "manifest.toml"),
        ("registry", "aeat", "legal", "iva-flow.toml"),
        ("registry", "aeat", "iva", "rates.toml"),
        ("registry", "aeat", "calendars", "festivos-2025.toml"),
        ("registry", "cadrumo", "user_profile", "schema.toml"),
    )

    for parts in cases:
        node = packaged_data(*parts)

        assert node.is_file(), f"missing bundled file: {'/'.join(parts)}"


def test_representative_subtrees_are_directories() -> None:
    """Top-level subtree containers resolve to real directories."""

    cases: tuple[tuple[str, ...], ...] = (
        ("corpus", "parity_replays", "renta_web_open"),
        ("registry", "aeat", "topics"),
    )

    for parts in cases:
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
