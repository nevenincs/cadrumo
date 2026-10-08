"""Shared shape-adapter input policies."""

from __future__ import annotations

from types import MappingProxyType

import pytest
from pydantic import ValidationError

from ..type_adapters import STR_KEYED_MAPPING_ADAPTER, STRICT_STR_KEYED_MAPPING_ADAPTER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_strict_string_keyed_adapter_accepts_a_dictionary() -> None:
    payload: dict[str, object] = {"status": "ready", "detail": {"count": 2}}

    assert STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(payload) == payload


def test_strict_mapping_policy_refuses_proxy_and_byte_keys_while_lax_policy_accepts_them() -> None:
    proxy = MappingProxyType({"status": "ready"})
    byte_keyed = {b"status": "ready"}

    assert STR_KEYED_MAPPING_ADAPTER.validate_python(proxy) == {"status": "ready"}
    assert STR_KEYED_MAPPING_ADAPTER.validate_python(byte_keyed) == {"status": "ready"}

    with pytest.raises(ValidationError):
        STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(proxy)
    with pytest.raises(ValidationError):
        STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(byte_keyed)
