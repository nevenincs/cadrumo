"""Regression: row-producer detection must honour the per-family ROWS default.

A detail-record binding may omit an explicit ``aggregation`` and rely on its
``source`` family's default operator. For the detail-record families
(related-party, foreign-asset, atribución, refund) that default is
``BindingAggregationOp.ROWS``. The row-producer detection in
``_row_field_lookup`` previously short-circuited on ``aggregation is None``
and treated such a binding as a non-row producer, silently dropping its
``row_field`` from the lookup. Routing the test through the centralised
``binding_aggregation_op`` accessor fixes the mis-detection.

If this test stops detecting a ``aggregation=None`` rows-default binding as a
row producer, the BIND-01 regression has returned.
"""

from __future__ import annotations

import pytest

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition

from ....core import BindingSourceKind
from ....core.aggregation import BindingAggregation
from ....domain.calculations.registry.authority import bundled_authority
from .._row_set_assembly import _row_field_lookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _rows_default_detail_binding() -> DataBindingDefinition:
    """A foreign-asset detail binding with no explicit aggregation.

    ``foreign_asset`` is a ROWS-default source family, so the binding must be
    detected as a row producer even though ``aggregation`` is ``None``.
    """

    return DataBindingDefinition.model_validate(
        {
            "id": "synthetic-detail-row",
            "source": BindingSourceKind.FOREIGN_ASSET,
            "selector": {"fact": "row_field", "grouping": "per_foreign_asset", "row_field": "valuation_amount"},
            "aggregation": None,
            "legal_refs": ("ley-7-2012:dt-18",),
            "source_refs": ("aeat-modelo-720",),
        },
    )


def test_rows_default_family_resolves_to_rows_op() -> None:
    """The accessor returns ROWS for a None-aggregation rows-default binding."""

    binding = _rows_default_detail_binding()
    assert binding.aggregation is None
    assert binding_aggregation_op(binding) == BindingAggregationOp.ROWS


def test_row_field_lookup_detects_none_aggregation_rows_default_binding() -> None:
    """A rows-default detail binding with aggregation=None is NOT dropped.

    The previous detection (``aggregation is None or op != "rows"``) dropped
    this binding before the row_field could be read; the accessor-routed
    detection keeps it.
    """

    revision = bundled_authority().modelo("720").revisions["2013-y-siguientes"]
    revision_with_default = revision.model_copy(update={"bindings": (_rows_default_detail_binding(),)})

    lookup = _row_field_lookup(revision_with_default)

    assert lookup == {"synthetic-detail-row": "valuation_amount"}


def test_row_field_lookup_rejects_rows_binding_without_row_set_projection() -> None:
    revision = bundled_authority().modelo("720").revisions["2013-y-siguientes"]
    malformed_row_binding = DataBindingDefinition.model_validate(
        {
            "id": "synthetic-row-without-grouping",
            "source": BindingSourceKind.FOREIGN_ASSET,
            "selector": {"fact": "row_field", "row_field": "valuation_amount"},
            "aggregation": BindingAggregation(op=BindingAggregationOp.ROWS),
            "legal_refs": ("ley-7-2012:dt-18",),
            "source_refs": ("aeat-modelo-720",),
        },
    )
    revision_with_malformed_row = revision.model_copy(update={"bindings": (malformed_row_binding,)})

    with pytest.raises(RegistryValidationError, match="missing grouping"):
        _row_field_lookup(revision_with_malformed_row)
