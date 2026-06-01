"""Behaviour tests for the shared TOML helpers in :mod:`aeat.core._toml`."""

from __future__ import annotations

import pytest

from ._toml import to_str_keyed_dict

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


class _SampleError(Exception):
    """Stand-in domain error for the error_factory contract."""


def test_to_str_keyed_dict_returns_str_keyed_copy() -> None:
    """A mapping with string keys is returned as a plain str-keyed dict."""
    result = to_str_keyed_dict({"a": 1, "b": [2, 3]}, error_factory=_SampleError)
    assert result == {"a": 1, "b": [2, 3]}


def test_to_str_keyed_dict_rejects_non_string_key_via_error_factory() -> None:
    """A non-string key raises the exception built by ``error_factory``."""
    with pytest.raises(_SampleError, match="TOML table keys must be strings"):
        to_str_keyed_dict({1: "x"}, error_factory=_SampleError)
