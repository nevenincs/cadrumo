import pytest

from .. import bindings as bindings_mod

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_counterpart_source_kind_canonical_in_domain() -> None:
    assert hasattr(bindings_mod, "CounterpartSourceKind")
