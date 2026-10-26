"""Concrete exact schema-version refusal behavior."""

from __future__ import annotations

import pytest

from ..errors import EnvelopeVersionError
from ..schema_lineage import ensure_schema_version_readable

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.lineage.policy"


def test_future_schema_version_is_refused_as_from_future() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=2,
            current_version=1,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_version_from_future"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 2,
        "expected": 1,
    }


def test_older_version_without_a_reader_is_refused() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=1,
            current_version=3,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_upgrade_path_missing"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 1,
        "expected": 3,
        "missing_from_version": 1,
    }
