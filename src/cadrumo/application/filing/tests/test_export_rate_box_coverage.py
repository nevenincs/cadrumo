"""Export refuses a rate breakdown that does not reach its own declared total.

A rate-specific official box asserts a rate, so a ledger row that records a
cuota without recording the rate charged reaches the rate-blind total layer and
no box. The return keeps the money; what it loses is the property that the parts
sum to the whole, and AEAT reconciles those boxes against that total. The
application never files, so the artefact leaves the write door for a human to
submit with nothing behind it.

These tests drive the real ``export_draft`` against the real Modelo 390 registry
and the real partitions its subview projects -- no constructed partition, no
substituted subview, except in the one case that is ABOUT the absence of
partitions. Everything before this file was proved on revisions built to the
split shape; this is where the gate meets registry data it did not choose.

Why this file exists in the shape it does
------------------------------------------

The shared Modelo 390 export fixture had to be updated when the split landed: it
populated the tier totals and left every rate box empty, which post-split is
exactly the refusal condition. That is the shape most likely to be a test quietly
relaxed to match new behaviour, so the update is defended here rather than left
to intent. :func:`test_blanking_one_rate_box_refuses_and_names_it` and
:func:`test_boxes_short_of_their_total_refuse_by_the_exact_shortfall` are the
assertions that make the fixture change safe: if the fixture had been made to
pass rather than made correct, both would be green with the gate doing nothing.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.filing import FilingExportError, ModeloDraft, ModeloValueKind
from .._export import export_draft
from ..runtime import RegistrySchemaAccessor
from ._export_support import (
    _approved_modelo_390_registry_draft,
    _modelo_390_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _cid(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="test.rate_box.casilla")


#: The rate-blind total layer: fed by bindings that do not discriminate on rate,
#: so they keep every row including those whose rate was never recorded. These
#: casillas file no official box.
_REDUCIDO_TOTAL = _cid("iva.anual.repercutido.reducido")
#: Two of the reducido tier's three boxes, the ones the shared fixture populates.
_BOX_10 = _cid("iva.anual.repercutido.tipo-10.cuota")
_BOX_5 = _cid("iva.anual.repercutido.tipo-5.cuota")


def _real_provider() -> RegistrySchemaAccessor:
    """Build the real Modelo 390 provider for the annual period.

    Called with its arguments named rather than splatted from a shared dict:
    the dict inferred every value as the union of all of them, so the call
    checked nothing and needed a suppression ty does not read to reach the
    function at all.
    """
    return _schema_provider(filing_year=2025, period="0A", modelos=("390",))


def _provider_without_partitions() -> RegistrySchemaAccessor:
    """A real Modelo 390 provider with its partition projection emptied.

    The one substitution in this file, and it is the subject of its own test
    rather than a convenience: every revision in the tree that has not split a
    tier casilla is in this state, and none of them may acquire a new refusal.
    """
    provider = _real_provider()
    subview = provider.get_subview("390")
    return RegistrySchemaAccessor(
        collections=provider.collections,
        subviews={**provider.subviews, "390": replace(subview, rate_box_partitions=())},
        source_root=provider.source_root,
        sources=provider.sources,
    )


def _with_values(draft: ModeloDraft, values: dict[CasillaId, Decimal | None]) -> ModeloDraft:
    """Return ``draft`` with the named casillas set, ``None`` demoting to EMPTY.

    EMPTY is the real production shape for "nothing here": ``build_draft`` emits
    a row for every declared casilla, so a blanked box keeps its id and loses
    only its value. Every named casilla is asserted present first, because a
    typo'd id would otherwise leave the fixture's own value in place and quietly
    test a different return than the test name claims.
    """
    present = {value.casilla_id for value in draft.values}
    missing = sorted(casilla_id for casilla_id in values if casilla_id not in present)
    assert not missing, f"draft does not declare {missing}"
    updated = tuple(
        value.model_copy(
            update=(
                {"value": None, "kind": ModeloValueKind.EMPTY}
                if values[value.casilla_id] is None
                else {"value": values[value.casilla_id], "kind": ModeloValueKind.COMPUTED}
            ),
        )
        if value.casilla_id in values
        else value
        for value in draft.values
    )
    return draft.model_copy(update={"values": updated})


def test_the_real_registry_projects_the_partitions_this_file_relies_on() -> None:
    """Anchor: every assertion below is vacuous if the split is not declared.

    The partitions this file draws on come off the live subview, and the reducido
    cuota tier carries the boxes the shortfall cases below use. Without this, a
    registry change that dropped the split would make the refusal tests pass by
    never reaching the gate at all.

    Asserted by NAME rather than by count. A total of six was pinned here once,
    which made adding the zero tier's missing total layer look like a regression
    while the property the anchor exists for -- the reducido tier is projected
    with its boxes -- was never in question. A count also cannot say WHICH
    partition vanished, which is the only thing a reader of this failure needs.
    """
    partitions = _real_provider().get_subview("390").rate_box_partitions

    by_total = {part.total_casilla_id: part for part in partitions}
    assert _REDUCIDO_TOTAL in by_total, f"the reducido cuota partition is gone; projected: {sorted(by_total)}"
    reducido = by_total[_REDUCIDO_TOTAL]
    assert set(reducido.box_casilla_ids) >= {_BOX_10, _BOX_5}
    assert reducido.rate_kinds == ("reduced",)


def test_the_populated_fixture_exports_against_the_real_partitions(tmp_path: Path) -> None:
    """Every tier's boxes reach its total, so the breakdown accounts for the whole.

    The direction a refusal that fired unconditionally would fail, now measured
    against registry data rather than a constructed partition. Without this the
    suite could not tell a correct gate from one that blocks every Modelo 390
    export ever attempted.
    """
    output = tmp_path / "modelo-390.txt"

    receipt = export_draft(
        _approved_modelo_390_registry_draft(),
        output_path=output,
        headers=_modelo_390_export_headers(),
        schema_provider=_real_provider(),
    )

    assert output.exists()
    assert receipt.file_sha256


def test_blanking_one_rate_box_refuses_and_names_it(tmp_path: Path) -> None:
    """The assertion that makes the fixture update safe rather than convenient.

    The shared fixture was changed to populate the box layer BECAUSE this gate
    reddened it. If that change had made the fixture pass rather than made it
    correct, this test would be green with the gate doing nothing: blanking the
    5 % box drops 500.00 out of a 2100.50 tier, and the refusal must fire and
    name the tier it fired on.
    """
    draft = _with_values(_approved_modelo_390_registry_draft(), {_BOX_5: None})
    output = tmp_path / "modelo-390.txt"

    with pytest.raises(FilingExportError) as excinfo:
        export_draft(
            draft,
            output_path=output,
            headers=_modelo_390_export_headers(),
            schema_provider=_real_provider(),
        )

    message = str(excinfo.value)
    assert _REDUCIDO_TOTAL in message
    assert "500.00" in message
    assert _BOX_5 in message
    assert not output.exists()


def test_boxes_short_of_their_total_refuse_by_the_exact_shortfall(tmp_path: Path) -> None:
    """Genuinely short, not empty: the arithmetic, not merely the presence.

    The gate's stated purpose is refusing a return whose rate boxes sum BELOW its
    declared total, so a case where every box carries a value and the sum still
    falls short is the one that exercises the subtraction. 1600.50 + 250.00
    against a 2100.50 tier leaves 250.00 unaccounted, and that figure must appear
    rather than a rounded or restated one.
    """
    draft = _with_values(_approved_modelo_390_registry_draft(), {_BOX_5: Decimal("250.00")})
    output = tmp_path / "modelo-390.txt"

    with pytest.raises(FilingExportError) as excinfo:
        export_draft(
            draft,
            output_path=output,
            headers=_modelo_390_export_headers(),
            schema_provider=_real_provider(),
        )

    message = str(excinfo.value)
    assert "leaving 250.00 unaccounted" in message
    assert not output.exists()


def test_boxes_exceeding_their_total_are_not_this_gate_s_condition(tmp_path: Path) -> None:
    """Exact equality is not the invariant, and must not be read as one.

    Boxes summing ABOVE their tier total is a different defect -- rate boxes
    whose declared rates overlap, so one row lands in two -- and this gate
    deliberately does not claim to detect it. Refusing here would name the wrong
    condition and send the operator to a ledger repair that would not fix it. The
    test exists so a later reader does not tighten the comparison to equality and
    believe they are strengthening the gate.
    """
    draft = _with_values(_approved_modelo_390_registry_draft(), {_BOX_5: Decimal("900.00")})
    output = tmp_path / "modelo-390.txt"

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_390_export_headers(),
        schema_provider=_real_provider(),
    )

    assert output.exists()
    assert receipt.file_sha256


def test_a_revision_declaring_no_partition_is_untouched(tmp_path: Path) -> None:
    """The gate is a no-op wherever the two-layer shape is not declared.

    Every revision that has not split a tier casilla is in this state, so this is
    the case that must not acquire a new refusal. The draft here is a genuinely
    short one -- the 5 % box blanked -- so the pass is the absence of partitions
    doing the work, not the absence of a shortfall.
    """
    draft = _with_values(_approved_modelo_390_registry_draft(), {_BOX_5: None})
    output = tmp_path / "modelo-390.txt"

    receipt = export_draft(
        draft,
        output_path=output,
        headers=_modelo_390_export_headers(),
        schema_provider=_provider_without_partitions(),
    )

    assert output.exists()
    assert receipt.file_sha256
