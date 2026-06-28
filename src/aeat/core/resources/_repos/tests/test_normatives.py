"""Real-behaviour tests for NormativeRepository.

These tests exercise the Repository surface contract —
construction, root override, cache clearing — and the
parse-error-surfacing path. The parse-error test points the
repository at a deliberately schema-invalid catalogue so the
failure mode is genuinely exercised rather than relying on the
bundled corpus being malformed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..normatives import NormativeRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_normative_repository_constructs_without_root() -> None:
    repo = NormativeRepository()

    assert repo._root is None
    assert repo._cache == {}


def test_normative_repository_constructs_with_root_override(tmp_path) -> None:
    repo = NormativeRepository(root=tmp_path)

    assert repo._root == tmp_path


def test_normative_repository_clear_cache_is_safe_on_empty_cache() -> None:
    repo = NormativeRepository()

    repo.clear_cache()

    assert repo._cache == {}


def test_normative_repository_get_surfaces_parse_error_on_bad_catalogue(tmp_path: Path) -> None:
    """A schema-invalid normative file surfaces NormativeParseError.

    Construct a catalogue directory holding one structurally
    malformed normative JSON file and point a
    :class:`NormativeRepository` at it via the root override. The
    loader must reject the file and raise
    :class:`NormativeParseError` rather than silently producing a
    partial catalogue.
    """
    bad_normative = tmp_path / "ley-bad.json"
    # Valid JSON, but the payload omits every required field of
    # NormativeReference, so strict pydantic validation rejects it.
    bad_normative.write_text('{"id": "ley-bad"}', encoding="utf-8")

    repo = NormativeRepository(root=tmp_path)

    from .....domain.normatives._errors import NormativeParseError

    with pytest.raises(NormativeParseError):
        _ = repo.singleton
