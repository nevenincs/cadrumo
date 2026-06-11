"""Real-behaviour tests for ManualRepository.

The bundled Manual corpus carries `manifest.json` and `source.pdf`
files for each year but the structure/chapters/sections tree
that :func:`load_manual` requires is currently extracted only
for a subset of variants. Tests verify the Repository contract
shape against what the bundle actually provides.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..manuals import ManualKey, ManualRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_manual_key_is_frozen_and_hashable() -> None:
    a = ManualKey(manual_id="iva", year=2025, part="single")
    b = ManualKey(manual_id="iva", year=2025, part="single")

    assert a == b
    assert hash(a) == hash(b)


def test_manual_key_distinct_fields_yield_distinct_hashes() -> None:
    iva = ManualKey(manual_id="iva", year=2025, part="single")
    renta = ManualKey(manual_id="renta", year=2025, part="part1")

    assert iva != renta
    assert hash(iva) != hash(renta)


def test_manual_repository_constructs_with_no_root_override() -> None:
    repo = ManualRepository()

    assert repo._root is None
    assert repo._cache == {}


def test_manual_repository_constructs_with_root_override(tmp_path) -> None:
    repo = ManualRepository(root=tmp_path)

    assert repo._root == tmp_path


def test_manual_repository_get_raises_for_unextracted_manual(tmp_path: Path) -> None:
    """Manuals that ship without a structure/ tree raise the domain error.

    The bundled corpus carries manifest + source.pdf for every
    tracked year but the chapter/section structure has only been
    extracted for a subset. Calling :meth:`get` on an unextracted
    manual surfaces the existing ``ManualNotFoundError``, which the
    error hierarchy lets the caller catch via either the domain-
    specific class or the resource-level base.
    """
    from .....domain.manuals._errors import ManualNotFoundError

    # The bundled corpus is now fully extracted, so this contract is exercised
    # against a synthetic unextracted manual (manifest + source.pdf present, no
    # structure/ tree) rather than a real corpus part whose extraction state can
    # change. load_manual requires structure/manual.json and raises when absent.
    part_root = tmp_path / "iva" / "2025"
    part_root.mkdir(parents=True)
    (part_root / "source.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (part_root / "manifest.json").write_text(
        json.dumps(
            {
                "manual_id": "iva",
                "year": 2025,
                "part": "single",
                "sha256": "0" * 64,
                "source_pdf_url": "https://example.invalid/manual.pdf",
                "relative_pdf_path": "source.pdf",
                "content_length": 12,
                "fetched_at": "2026-01-01T00:00:00Z",
                "synthetic": True,
            },
        ),
        encoding="utf-8",
    )
    repo = ManualRepository(root=tmp_path)
    key = ManualKey(manual_id="iva", year=2025, part="single")

    with pytest.raises(ManualNotFoundError):
        repo.get(key)


def test_manual_repository_clear_cache_empties_identity_map() -> None:
    repo = ManualRepository()

    repo.clear_cache()  # safe on empty cache

    assert repo._cache == {}
