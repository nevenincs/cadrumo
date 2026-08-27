import pytest

from ....core import aggregation as aggregation_mod

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_counterpart_source_kind_canonical_in_domain() -> None:
    """``CounterpartSourceKind`` is canonically defined in ``core.aggregation``.

    Previously pinned reachable through ``bindings.py``, which re-exported it
    from ``core.aggregation`` with no internal use of its own -- a pure
    facade re-export the S259 relocation retired (bindings.py never
    re-exports per-family or core symbols it does not itself consume). The
    canonical defining module was always ``core.aggregation``; this test now
    pins that directly rather than through a since-removed facade.
    """
    assert hasattr(aggregation_mod, "CounterpartSourceKind")
