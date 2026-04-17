"""Unit tests ensuring the status-reader error hierarchy is consistent."""

from __future__ import annotations

import pytest

from ..errors import AeatError
from . import (
    StatusAuthError,
    StatusNotFoundError,
    StatusParseError,
    StatusReaderError,
)

pytestmark = pytest.mark.unit


def test_all_errors_inherit_from_aeat_error() -> None:
    for cls in (StatusReaderError, StatusAuthError, StatusParseError, StatusNotFoundError):
        assert issubclass(cls, AeatError)


def test_subclasses_inherit_from_reader_error() -> None:
    for cls in (StatusAuthError, StatusParseError, StatusNotFoundError):
        assert issubclass(cls, StatusReaderError)
