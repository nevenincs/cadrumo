"""Real-behaviour tests for NormativeRepository.

The bundled normatives catalogue currently contains records
that fail strict pydantic validation (a pre-existing data
curation issue unrelated to this migration). These tests focus
on the Repository surface contract — construction, root
override, cache clearing, and failure mode through the typed
error hierarchy — rather than the catalogue's content.
"""

from __future__ import annotations

import pytest

from aeat.core.resources._repos.normatives import NormativeRepository
from aeat.domain.normatives.errors import NormativeParseError

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


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


def test_normative_repository_get_surfaces_parse_error_on_bad_catalogue() -> None:
    """Schema-invalid entries in the bundled catalogue surface NormativeParseError.

    NormativeParseError is a domain-level error; after the
    error-hierarchy unification in P09 it becomes a subclass of
    ResourceValidationError. This test asserts the current
    behaviour holds.
    """
    repo = NormativeRepository()

    with pytest.raises(NormativeParseError):
        _ = repo.singleton
