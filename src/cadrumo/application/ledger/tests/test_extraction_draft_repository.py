"""Extraction repository composition retains its context and refusal rules."""

from __future__ import annotations

from contextvars import Context
from typing import TYPE_CHECKING

import pytest

from ....core.config import load_settings
from ....core.errors.hierarchy import InternalInvariantError
from ..extraction_draft_repository import (
    bind_extraction_draft_repository_factory,
    extraction_draft_repository,
)

if TYPE_CHECKING:
    from ....core.config import Settings
    from ..extraction_draft_store import ExtractionDraftDocument

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Repository:
    def load(self, identifier: str) -> ExtractionDraftDocument | None:
        return None

    def save(self, payload: ExtractionDraftDocument) -> None:
        raise AssertionError("binding fixtures do not persist records")


class _Factory:
    def __init__(self) -> None:
        self.repository = _Repository()
        self.calls: list[tuple[str, Settings]] = []

    def __call__(self, *, bucket_id: str, settings: Settings) -> _Repository:
        self.calls.append((bucket_id, settings))
        return self.repository


def test_repository_resolves_the_bound_factory_with_exact_arguments() -> None:
    factory = _Factory()
    settings = load_settings()

    with bind_extraction_draft_repository_factory(factory) as bound:
        assert bound is factory
        assert extraction_draft_repository("bucket-a", settings) is factory.repository
        assert extraction_draft_repository("bucket-b", settings) is factory.repository

    assert factory.calls == [("bucket-a", settings), ("bucket-b", settings)]
    assert factory.calls[0][1] is settings


@pytest.mark.parametrize("raise_inside", [False, True])
def test_nested_repository_binding_restores_the_outer_factory(raise_inside: bool) -> None:
    settings = load_settings()
    outer = _Factory()
    inner = _Factory()
    with bind_extraction_draft_repository_factory(outer):
        try:
            with bind_extraction_draft_repository_factory(inner):
                assert extraction_draft_repository("inner", settings) is inner.repository
                if raise_inside:
                    raise ValueError("fixture: nested composition failed")
        except ValueError:
            assert raise_inside
        assert extraction_draft_repository("outer", settings) is outer.repository

    assert inner.calls == [("inner", settings)]
    assert outer.calls == [("outer", settings)]


def test_missing_repository_binding_refuses_and_is_restored_after_scope() -> None:
    settings = load_settings()

    def isolated_scope() -> None:
        with pytest.raises(InternalInvariantError, match=r"^extraction-draft persistence has not been composed$"):
            extraction_draft_repository("bucket", settings)
        factory = _Factory()
        with bind_extraction_draft_repository_factory(factory):
            assert extraction_draft_repository("bucket", settings) is factory.repository
        with pytest.raises(InternalInvariantError, match=r"^extraction-draft persistence has not been composed$"):
            extraction_draft_repository("bucket", settings)

    Context().run(isolated_scope)
