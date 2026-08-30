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
from pydantic import ValidationError

from .....domain.manuals.schema import ManualPart
from ...errors import ResourceValidationError
from ..manuals import ManualKey, ManualRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_manual_key_is_frozen_hashable_and_field_sensitive() -> None:
    a = ManualKey(manual_id="iva", year=2025, part="single")
    b = ManualKey(manual_id="iva", year=2025, part="single")
    c = ManualKey(manual_id="renta", year=2025, part="part1")

    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert hash(a) != hash(c)

    with pytest.raises(ValidationError):
        a.__setattr__("year", 2026)


def test_manual_repository_constructs_with_optional_root_and_clearable_cache(tmp_path: Path) -> None:
    default_repo = ManualRepository()
    rooted_repo = ManualRepository(root=tmp_path)

    assert default_repo._root is None
    assert default_repo._cache == {}
    assert rooted_repo._root == tmp_path

    default_repo.clear_cache()  # safe on empty cache
    assert default_repo._cache == {}


def test_manual_repository_get_raises_for_unextracted_manual(tmp_path: Path) -> None:
    """Manuals that ship without a structure/ tree raise the domain error.

    The bundled corpus carries manifest + source.pdf for every
    tracked year but the chapter/section structure has only been
    extracted for a subset. Calling :meth:`get` on an unextracted
    manual surfaces the existing ``ManualNotFoundError``, which the
    error hierarchy lets the caller catch via either the domain-
    specific class or the resource-level base.
    """
    from .....domain.manuals.errors import ManualNotFoundError

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


class TestManualPartVocabulary:
    """An unknown part fails closed instead of selecting a different authority.

    ``ManualRepository._load`` used to catch every ``ValueError`` from the
    canonical ``ManualPart`` enum and substitute ``SINGLE``. A typo'd or stale
    caller key therefore returned a valid but *different* authoritative manual
    aggregate — the one a reader would go on to quote regulatory text from —
    while the domain loader rejected the same value outright.
    """

    @pytest.mark.parametrize("bad", ["bogus", "SINGLE", "part9", "", " single "])
    def test_unknown_part_is_refused_at_key_construction(self, bad: str) -> None:
        """The refusal lands before any authority is selected."""
        with pytest.raises(ResourceValidationError):
            ManualKey(manual_id="iva", year=2025, part=bad)

    def test_refusal_names_the_accepted_vocabulary(self) -> None:
        """An operator must be able to recover from the message alone."""
        with pytest.raises(ResourceValidationError) as excinfo:
            ManualKey(manual_id="iva", year=2025, part="bogus")

        for part in ManualPart:
            assert part.value in str(excinfo.value)

    @pytest.mark.parametrize("part", [p.value for p in ManualPart])
    def test_every_declared_part_is_accepted(self, part: str) -> None:
        """The guard must accept exactly the canonical vocabulary, not less."""
        assert ManualKey(manual_id="renta", year=2025, part=part).part == part

    def test_default_part_is_the_single_volume(self) -> None:
        assert ManualKey(manual_id="iva", year=2025).part == ManualPart.SINGLE.value

    def test_a_bogus_part_no_longer_resolves_to_the_single_volume(self) -> None:
        """The exact substitution the fallback performed is now impossible.

        Before the fix ``part="bogus"`` and ``part="single"`` loaded the same
        aggregate and serialized identically, so the mis-key was undetectable.
        """
        single = ManualRepository().get(ManualKey(manual_id="iva", year=2025, part="single"))

        assert single is not None
        with pytest.raises(ResourceValidationError):
            ManualRepository().get(ManualKey(manual_id="iva", year=2025, part="bogus"))
