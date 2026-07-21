"""Secure-object schema-version refusal policy."""

from __future__ import annotations

import pytest

from .._schema_version import ensure_schema_version_supported
from ..errors import EnvelopeVersionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.schema-version"


def test_current_schema_version_is_accepted() -> None:
    ensure_schema_version_supported(
        namespace=_NAMESPACE,
        schema_version=3,
        current_version=3,
    )


def test_future_schema_version_is_refused_as_from_future() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_supported(
            namespace=_NAMESPACE,
            schema_version=4,
            current_version=3,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_version_from_future"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 4,
        "expected": 3,
    }


def test_pre_current_schema_version_is_refused_without_migration() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_supported(
            namespace=_NAMESPACE,
            schema_version=2,
            current_version=3,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_version_unsupported"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 2,
        "expected": 3,
    }
