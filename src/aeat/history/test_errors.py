"""Unit tests for the filing-history error hierarchy."""

from __future__ import annotations

import pytest

from ..errors import AeatError
from . import (
    HistoryError,
    HistoryFetchError,
    HistoryParseError,
    HistoryUnsupportedModeloError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def test_history_error_subclasses_aeat_error() -> None:
    assert issubclass(HistoryError, AeatError)


def test_fetch_error_chain() -> None:
    assert issubclass(HistoryFetchError, HistoryError)
    assert issubclass(HistoryFetchError, AeatError)


def test_parse_error_chain() -> None:
    assert issubclass(HistoryParseError, HistoryError)
    assert issubclass(HistoryParseError, AeatError)


def test_unsupported_modelo_error_chain() -> None:
    assert issubclass(HistoryUnsupportedModeloError, HistoryError)
    assert issubclass(HistoryUnsupportedModeloError, AeatError)


def test_errors_preserve_cause() -> None:
    inner = RuntimeError("boom")
    try:
        raise HistoryFetchError("fetch failed") from inner
    except HistoryFetchError as exc:
        assert exc.__cause__ is inner
