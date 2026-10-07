"""Confirmation repository composition retains its context and refusal rules."""

from __future__ import annotations

from contextvars import Context
from typing import TYPE_CHECKING

import pytest

from ....core.config import load_settings
from ....core.errors.hierarchy import InternalInvariantError
from ..confirmation_record_repository import (
    bind_confirmation_record_repository_factory,
    confirmation_record_repository,
)

if TYPE_CHECKING:
    from ....core.config import Settings
    from ..confirmation_record import ConfirmationRecordDocument

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Repository:
    def load(self, identifier: str) -> ConfirmationRecordDocument | None:
        return None

    def save(self, payload: ConfirmationRecordDocument) -> None:
        raise AssertionError("binding fixtures do not persist records")


class _Factory:
    def __init__(self) -> None:
        self.repository = _Repository()
        self.calls: list[tuple[str, Settings | None]] = []

    def __call__(self, *, bucket_id: str, settings: Settings | None) -> _Repository:
        self.calls.append((bucket_id, settings))
        return self.repository


def test_repository_resolves_the_bound_factory_with_exact_arguments() -> None:
    factory = _Factory()
    settings = load_settings()

    with bind_confirmation_record_repository_factory(factory) as bound:
        assert bound is factory
        assert confirmation_record_repository("bucket-a", settings) is factory.repository
        assert confirmation_record_repository("bucket-b", None) is factory.repository

    assert factory.calls == [("bucket-a", settings), ("bucket-b", None)]
    assert factory.calls[0][1] is settings


@pytest.mark.parametrize("raise_inside", [False, True])
def test_nested_repository_binding_restores_the_outer_factory(raise_inside: bool) -> None:
    outer = _Factory()
    inner = _Factory()
    with bind_confirmation_record_repository_factory(outer):
        try:
            with bind_confirmation_record_repository_factory(inner):
                assert confirmation_record_repository("inner", None) is inner.repository
                if raise_inside:
                    raise ValueError("fixture: nested composition failed")
        except ValueError:
            assert raise_inside
        assert confirmation_record_repository("outer", None) is outer.repository

    assert inner.calls == [("inner", None)]
    assert outer.calls == [("outer", None)]


def test_missing_repository_binding_refuses_and_is_restored_after_scope() -> None:
    def isolated_scope() -> None:
        with pytest.raises(InternalInvariantError, match=r"^confirmation-record persistence has not been composed$"):
            confirmation_record_repository("bucket", None)
        factory = _Factory()
        with bind_confirmation_record_repository_factory(factory):
            assert confirmation_record_repository("bucket", None) is factory.repository
        with pytest.raises(InternalInvariantError, match=r"^confirmation-record persistence has not been composed$"):
            confirmation_record_repository("bucket", None)

    Context().run(isolated_scope)
