"""Modelo 390 unmodelled regimen blocks have no rate-blind total layer.

The bundled 2024 AEAT Diseño gives intragrupo, criterio de caja, bienes usados,
and agencias de viajes their own rate boxes.  That does NOT by itself permit
the two-layer rate-box shape: its second layer must be a rate-blind total for
the SAME block, rather than a formula that sums the box casillas.  Otherwise
each rated row reaches the declared total twice.

The official record defines no such total for any of these four unmodelled
blocks.  Their only common total is box [34], which spans other devengada
blocks as well and cannot be a sibling of any one of them.  Until a source
establishes a block-specific total and the registry models it, none may enter
the two-layer partition set.

Real behaviour: read the bundled AEAT design and the committed Modelo 390
revision through the real authority, then ask the production partition
derivation which casillas currently form the two-layer shape.  No mocks,
stubs, skips, or xfail.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path, resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.rate_box_partition import derive_rate_box_partitions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_DESIGN_PARTS = (
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_390",
    "files",
    "16-390-ejercicio-2024-actualizado-18-12-24-544-kb-xlsx.xlsx.extracted.md",
)
_DEVENGADA_SEGMENT = "5. Operaciones Reg. Gral. - Base Imponible y cuota"
_RATE_ROW = re.compile(r"Tipo ([\d,]+)% - (Base imponible|Cuota) \[(\d+)\]")

# These are the four blocks the registry leaves unmodelled for rate boxes.  The
# labels and rate sets are asserted against the AEAT design, not transcribed
# into the registry as a second authority.
_UNMODELLED_BLOCKS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("intragrupo", "operaciones intragrupo", frozenset({"0", "2", "4", "5", "7,5", "10", "21"})),
    ("criterio de caja", "regimen especial criterio caja", frozenset({"0", "2", "4", "5", "7,5", "10", "21"})),
    ("bienes usados", "Reg. espec. bienes usados", frozenset({"0", "2", "4", "5", "7,5", "10", "21"})),
    ("agencias de viajes", "Reg. espec. agencias viajes", frozenset({"21"})),
)


def _m390_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("390", filing_year=2024, period="0A").revision


def _design_text() -> str:
    return bundled_path(*_DESIGN_PARTS).read_text(encoding="utf-8")


def _block_devengada_lines(label: str) -> tuple[str, ...]:
    normalized_label = label.casefold()
    normalized_segment = _DEVENGADA_SEGMENT.casefold()
    return tuple(
        line
        for line in _design_text().splitlines()
        if normalized_segment in line.casefold() and normalized_label in line.casefold()
    )


def _block_rate_rows(label: str) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for line in _block_devengada_lines(label):
        matched = _RATE_ROW.search(line)
        if matched is not None:
            rows.append((matched.group(1), matched.group(2), matched.group(3)))
    return tuple(rows)


def _candidate_box_numbers() -> frozenset[str]:
    return frozenset(
        box_number
        for _block, label, _rates in _UNMODELLED_BLOCKS
        for _rate, _kind, box_number in _block_rate_rows(label)
    )


def _partition_box_numbers(revision: ModeloRevision) -> frozenset[str]:
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    return frozenset(
        str(casillas[casilla_id].number)
        for partition in derive_rate_box_partitions(revision)
        for casilla_id in partition.box_casilla_ids
        if casillas[casilla_id].number is not None
    )


@pytest.mark.parametrize(("block", "label", "expected_rates"), _UNMODELLED_BLOCKS)
def test_each_unmodelled_block_has_rate_boxes_but_no_block_specific_total(
    block: str,
    label: str,
    expected_rates: frozenset[str],
) -> None:
    """Measure the precondition from the official design for every block.

    A parser yielding no rows would make "no total" trivially true, so each
    block first proves its rate rows are present and paired before proving none
    describes a total for that same block.  Box [34] is deliberately outside
    this block-scoped scan: it totals multiple devengada blocks and cannot be a
    rate-blind sibling of any one candidate.
    """
    lines = _block_devengada_lines(label)
    rows = _block_rate_rows(label)

    assert rows, f"{block}: no rate rows were parsed from the official design"
    assert {rate for rate, _kind, _box in rows} == expected_rates, block
    assert {kind for _rate, kind, _box in rows} == {"Base imponible", "Cuota"}, block
    assert len(rows) == len(expected_rates) * 2, block
    assert not any("Total" in line for line in lines), (
        f"{block}: the design now states a block-specific total; establish whether it is rate-blind "
        "before admitting this block to the two-layer shape"
    )


def test_no_unmodelled_block_rate_box_is_registered_as_a_two_layer_partition() -> None:
    """The partition derivation stays limited to blocks with a proven total layer."""
    candidate_boxes = _candidate_box_numbers()
    partition_boxes = _partition_box_numbers(_m390_revision())

    assert candidate_boxes, "the official design yielded no candidate rate boxes"
    assert partition_boxes, "Modelo 390 declared no existing two-layer rate boxes"
    assert not candidate_boxes & partition_boxes, (
        "a block with no measured rate-blind total entered the two-layer partition set: "
        f"{sorted(candidate_boxes & partition_boxes)}"
    )


def test_mutation_assigning_a_candidate_box_to_a_live_partition_is_detected() -> None:
    """The admission guard reddens if a candidate box is made partitioned.

    This is an in-memory mutation of the loaded, strict registry model; the
    production ``derive_rate_box_partitions`` function still derives the set.
    It proves the guard does not pass merely because the current partition
    population happens to omit every unmodelled block.
    """
    revision = _m390_revision()
    candidate_box = min(_candidate_box_numbers())
    live_box_id = next(
        casilla_id for partition in derive_rate_box_partitions(revision) for casilla_id in partition.box_casilla_ids
    )
    mutated = revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"number": candidate_box}) if casilla.id == live_box_id else casilla
                for casilla in revision.casillas
            ),
        },
    )

    assert candidate_box not in _partition_box_numbers(revision)
    assert candidate_box in _partition_box_numbers(mutated)
