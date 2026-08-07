"""Export refuses a rate breakdown that does not reach its own declared total.

A rate-specific official box asserts a rate, so a ledger row that records a
cuota without recording the rate charged reaches the rate-blind total layer and
no box. The return keeps the money; what it loses is the property that the parts
sum to the whole, and AEAT reconciles those boxes against that total. The
application never files, so the artefact leaves the write door for a human to
submit with nothing behind it.

These tests drive the real ``export_draft`` against a real Modelo 390 registry
draft. The partition is supplied on the subview exactly as the runtime
projection supplies it, and its three casillas stand in for a split tier: the
registry half that declares real box-layer casillas lands separately, and the
gate must be provably correct BEFORE it can refuse anything. What is under test
here is the gate's behaviour given a partition, not which partitions Modelo 390
declares -- that derivation is pinned in
``domain/calculations/registry/tests/test_rate_box_partition.py``.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import CasillaId, RateBoxPartition, validated_casilla_id
from ....domain.filing import FilingExportError, ModeloDraft, ModeloValueKind
from .._export import export_draft
from ..runtime import RegistrySchemaAccessor
from ._export_support import (
    _approved_modelo_390_registry_draft,
    _modelo_390_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.repercutido.general",
    surface="test.rate_box.total",
)
_BOX_A: CasillaId = validated_casilla_id("iva.anual.repercutido.reducido", surface="test.rate_box.box")
_BOX_B: CasillaId = validated_casilla_id("iva.anual.repercutido.super-reducido", surface="test.rate_box.box")

_PARTITION = RateBoxPartition(
    total_casilla_id=_TOTAL_CASILLA,
    box_casilla_ids=(_BOX_A, _BOX_B),
    rate_kinds=("general",),
    fact="iva_amount_sum",
)


def _provider_with_partition(*, partitions: tuple[RateBoxPartition, ...]) -> RegistrySchemaAccessor:
    """A real Modelo 390 provider carrying ``partitions`` on its subview.

    ``replace`` on the projected subview is how this suite already substitutes a
    registry projection (see ``_provider_without_export_layout``); the field is
    the same one ``_subview_from_snapshot`` fills.
    """
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("390",))
    subview = provider.get_subview("390")
    return RegistrySchemaAccessor(
        collections=provider.collections,
        subviews={**provider.subviews, "390": replace(subview, rate_box_partitions=partitions)},
        source_root=provider.source_root,
        sources=provider.sources,
    )


def _with_values(draft: ModeloDraft, values: dict[CasillaId, Decimal]) -> ModeloDraft:
    """Return ``draft`` with the named casillas carrying ``values``.

    Every named casilla is asserted present first: a typo'd id would otherwise
    leave the draft's real value in place and quietly test a different return
    than the one the test name claims.
    """
    present = {value.casilla_id for value in draft.values}
    missing = sorted(casilla_id for casilla_id in values if casilla_id not in present)
    assert not missing, f"draft does not declare {missing}"
    updated = tuple(
        value.model_copy(update={"value": values[value.casilla_id], "kind": ModeloValueKind.COMPUTED})
        if value.casilla_id in values
        else value
        for value in draft.values
    )
    return draft.model_copy(update={"values": updated})


def test_a_breakdown_reaching_its_total_exports(tmp_path: Path) -> None:
    """Every row carried a rate, so the boxes account for the whole total.

    The direction a refusal that fired unconditionally would fail. Without this
    the suite could not tell a correct gate from one that blocks every Modelo
    390 export ever attempted.
    """
    provider = _provider_with_partition(partitions=(_PARTITION,))
    draft = _with_values(
        _approved_modelo_390_registry_draft(),
        {_TOTAL_CASILLA: Decimal("2520.50"), _BOX_A: Decimal("2100.50"), _BOX_B: Decimal("420.00")},
    )
    output = tmp_path / "modelo-390.txt"

    receipt = export_draft(draft, output_path=output, headers=_modelo_390_export_headers(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256


def test_a_breakdown_short_of_its_total_is_refused_before_any_bytes(tmp_path: Path) -> None:
    """The unaccounted 79.50 refuses the export, and no file is written.

    The refusal must precede the write for the same reason the completeness gate
    does: an operator handed a file believes they hold a filing artefact, and a
    valid digest over structurally inconsistent bytes proves only that the bytes
    are the bytes.
    """
    provider = _provider_with_partition(partitions=(_PARTITION,))
    draft = _with_values(
        _approved_modelo_390_registry_draft(),
        {_TOTAL_CASILLA: Decimal("2600.00"), _BOX_A: Decimal("2100.50"), _BOX_B: Decimal("420.00")},
    )
    output = tmp_path / "modelo-390.txt"

    with pytest.raises(FilingExportError) as excinfo:
        export_draft(draft, output_path=output, headers=_modelo_390_export_headers(), schema_provider=provider)

    message = str(excinfo.value)
    assert "79.50" in message
    assert _TOTAL_CASILLA in message
    assert not output.exists()


def test_a_revision_declaring_no_partition_is_untouched(tmp_path: Path) -> None:
    """The gate is a no-op wherever the two-layer shape is not declared.

    Every revision in the tree is in this state until a modelo splits a tier
    casilla, so this is the case that must not acquire a new refusal.
    """
    provider = _provider_with_partition(partitions=())
    draft = _with_values(
        _approved_modelo_390_registry_draft(),
        {_TOTAL_CASILLA: Decimal("2600.00"), _BOX_A: Decimal("2100.50"), _BOX_B: Decimal("420.00")},
    )
    output = tmp_path / "modelo-390.txt"

    receipt = export_draft(draft, output_path=output, headers=_modelo_390_export_headers(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256
