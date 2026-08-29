"""Every published layout must RENDER, not merely validate.

The generator's own validation is structural: exact anchor bijection, exhaustive
render-profile coverage, digit budgets against slot widths. None of it puts a
value through the codec, and a whole class of defect lives in that gap. When AEAT
prints one quantity as a subdivided pair -- a printed ``Parte entera`` row and a
printed ``Parte decimal`` row -- the export IR descends to those leaves, so the
layout carries two fields for one casilla while the export path resolves values
per CASILLA and hands BOTH leaves the identical whole value. Declaring the plain
unsigned-integer policy on each half passed every structural gate and refused
every real amount.

These gates ask the question the structural ones cannot: given a value a taxpayer
could actually file, does the record carry it?
"""

from __future__ import annotations

import collections
from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from .....core.resources import bundled_path
from ..errors import RegistryValidationError
from ..export_value_policy import ExportValuePolicy
from ..fixed_width_codec import render_fixed_width_export_field
from ..loader import load_modelo_source
from ..loader_cache import discover_modelo_sources
from ..schema_exports import ExportFieldDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The policies that cut ONE value across the parts AEAT prints, in the order
#: the parts occupy the record.
_AMOUNT_PART_POLICIES = (ExportValuePolicy.INTEGER_PART, ExportValuePolicy.FRACTIONAL_DIGITS)
_DATE_PART_POLICIES = (
    ExportValuePolicy.FOUR_DIGIT_YEAR,
    ExportValuePolicy.TWO_DIGIT_MONTH,
    ExportValuePolicy.TWO_DIGIT_DAY,
)

#: Casillas a published layout writes into more than one slot of one record
#: WITHOUT declaring a part policy, each with the reason it is not yet decided.
#: A repeated slot and a split value are indistinguishable from the layout alone
#: -- both are several fields naming one casilla -- so an entry here is a
#: standing question, not an exemption, and the gate below fails if one goes
#: stale. Deciding these needs the page design read, which is a separate job.
_UNADJUDICATED_REPEATED_SLOTS: dict[tuple[str, str, str], str] = {
    ("390", "modelo-390-page-06", "iva.anual.iva-importacion-diferimiento"): (
        "two 17-position slots carrying one annual figure; may be a legitimate page layout "
        "showing the amount twice, or a map that repeated itself"
    ),
    ("390", "modelo-390-page-06", "iva.anual.regularizacion-cuotas-art-80-cinco-5"): (
        "two 17-position slots carrying one annual figure; same open question as its page siblings"
    ),
    ("390", "modelo-390-page-06", "iva.anual.suma-resultados"): (
        "two 17-position slots carrying one annual figure; same open question as its page siblings"
    ),
}

# MODELO 200 CARRIED TWO ENTRIES HERE AND NO LONGER DOES, WHICH IS NOT THE SAME
# AS THE QUESTIONS BEING ANSWERED. Both revisions ('2024' and
# '2025-y-siguientes') now declare ZERO export layouts -- the premature filing
# layout was withdrawn rather than repaired -- so there are no repeated slots for
# this gate to see, and the liveness check below correctly demanded the entries
# go. They are recorded here rather than deleted because re-authoring the Modelo
# 200 layout brings both questions straight back, and neither has a part policy
# available to it: a part policy declares which PART of one value a slot carries,
# while AEAT prints one casilla number against slots holding SEPARATE figures in
# both cases. Read from the design's own labels, not inferred from the offsets.
#
#   ('200', 'm200-page-045', '00199') -- two adjacent 17-position slots the
#   design labels 'Perdidas fiscales a compensar [00199] Aplicable a IIC
#   financieras' and '... Aplicable a IIC inmobiliarias': distinct figures for
#   distinct institution types sharing one printed number, not two parts of one
#   value. Needs a casilla per institution type in the generator's semantic map,
#   a filing-grade modelling change to a generator-owned tree.
#
#   ('200', 'm200-page-015b', '00103') -- three 7-position 'Tipo de gravamen
#   2025' slots the design attaches to three separate deduction blocks:
#   'Deducciones doble imposicion interna', the same 'DT 23.1 LIS' variant, and
#   'Deducciones doble imposicion internacional RDLeg. 4/2004'. Whether one
#   entity can carry three different rates across those blocks is a tax review,
#   and the same generator-owned-tree constraint applies.


def _published_multi_field_groups():
    """Yield every (modelo, record, casilla, fields) a layout writes more than once."""
    root = bundled_path("registry", "aeat", "modelos")
    groups = []
    for source in sorted(discover_modelo_sources(root), key=lambda item: item.modelo_id):
        modelo = load_modelo_source(source)
        for revision in modelo.revisions.values():
            for layout in getattr(revision, "export_layouts", ()) or ():
                for record in layout.records:
                    by_casilla = collections.defaultdict(list)
                    for field in record.fields:
                        casilla_id = getattr(field, "casilla_id", None)
                        if casilla_id is not None:
                            by_casilla[str(casilla_id)].append(field)
                    for casilla_id, fields in sorted(by_casilla.items()):
                        if len(fields) > 1:
                            groups.append(
                                (str(modelo.id), str(record.id), casilla_id, sorted(fields, key=lambda f: f.offset)),
                            )
    return groups


_GROUPS = _published_multi_field_groups()


def _policies(fields: list[ExportFieldDefinition]) -> tuple[ExportValuePolicy | None, ...]:
    return tuple(field.value_policy for field in fields)


def _is_contiguous(fields) -> bool:
    return all(first.offset + first.length == second.offset for first, second in pairwise(fields))


def _amount_samples(fields) -> tuple[Decimal, ...]:
    """Quantities drawn from the pair's own declared geometry.

    Widths come from the LAYOUT rather than from the code under test, so the
    expectation below is computed independently of the renderer that produces it.
    """
    integer_digits, decimal_digits = fields[0].length, fields[1].length
    return (
        Decimal(0),
        Decimal(f"7.{'0' * (decimal_digits - 1)}5") if decimal_digits > 1 else Decimal("7.5"),
        Decimal(f"{'9' * integer_digits}.{'9' * decimal_digits}"),
    )


def test_the_published_corpus_still_contains_multi_field_casillas() -> None:
    """A fixture anchor: these gates are vacuous if the shape stops existing."""
    assert _GROUPS, "no published layout writes one casilla into several fields"
    split = [group for group in _GROUPS if set(_policies(group[3])) & set(_AMOUNT_PART_POLICIES)]
    assert split, "no published layout declares a split amount, so the reconstruction gate is vacuous"


@pytest.mark.parametrize(
    "modelo_id,record_id,casilla_id,fields",
    _GROUPS,
    ids=[f"{m}-{r}-{c}" for m, r, c, _ in _GROUPS],
)
def test_a_multi_field_casilla_either_splits_one_value_or_is_declared_unadjudicated(
    modelo_id: str,
    record_id: str,
    casilla_id: str,
    fields,
) -> None:
    """Several fields naming one casilla must be a declared split, or a named question.

    Silence is the failure mode this gate exists to remove: before the part
    policies existed, a split pair and a duplicated mapping looked identical in
    the tree and neither announced itself.
    """
    policies = _policies(fields)
    if set(policies) & (set(_AMOUNT_PART_POLICIES) | set(_DATE_PART_POLICIES)):
        assert _is_contiguous(fields), (
            f"{modelo_id}/{record_id}/{casilla_id} declares part policies but its fields do not tile: "
            f"{[(f.offset, f.length) for f in fields]}"
        )
        return
    key = (modelo_id, record_id, casilla_id)
    assert key in _UNADJUDICATED_REPEATED_SLOTS, (
        f"{modelo_id}/{record_id}/{casilla_id} writes one casilla into {len(fields)} slots without declaring "
        "which part each carries. Author the part policies, or record it in _UNADJUDICATED_REPEATED_SLOTS "
        "with the reason it cannot be decided yet."
    )


def test_no_unadjudicated_entry_is_stale() -> None:
    """An entry that no longer names a real repeated slot must be removed.

    Without this the allowlist quietly outlives the question it records, which is
    how an allowlist stops being judgement and becomes furniture.
    """
    live = {
        (modelo_id, record_id, casilla_id)
        for modelo_id, record_id, casilla_id, fields in _GROUPS
        if not set(_policies(fields)) & (set(_AMOUNT_PART_POLICIES) | set(_DATE_PART_POLICIES))
    }
    stale = sorted(set(_UNADJUDICATED_REPEATED_SLOTS) - live)
    assert stale == [], f"_UNADJUDICATED_REPEATED_SLOTS names slots that no longer exist: {stale}"


_SPLIT_AMOUNTS = [group for group in _GROUPS if _policies(group[3]) == _AMOUNT_PART_POLICIES]


@pytest.mark.parametrize(
    "modelo_id,record_id,casilla_id,fields",
    _SPLIT_AMOUNTS,
    ids=[f"{m}-{r}-{c}" for m, r, c, _ in _SPLIT_AMOUNTS],
)
def test_a_split_amount_reproduces_the_undivided_quantity(
    modelo_id: str,
    record_id: str,
    casilla_id: str,
    fields,
) -> None:
    """The parts concatenated must be the digits the whole quantity would occupy.

    The expectation is scaled here from the value and the declared widths, never
    read back from the renderer, so a renderer that agrees with itself but not
    with the quantity still fails.
    """
    decimal_digits = fields[1].length
    total = fields[0].length + decimal_digits
    for value in _amount_samples(fields):
        rendered = "".join(render_fixed_width_export_field(field, value) for field in fields)
        expected = str(int(value.scaleb(decimal_digits))).rjust(total, "0")
        assert rendered == expected, (
            f"{modelo_id}/{record_id}/{casilla_id} rendered {value} as {rendered!r}, expected {expected!r}"
        )


_SPLIT_DATES = [group for group in _GROUPS if _policies(group[3]) == _DATE_PART_POLICIES]


@pytest.mark.parametrize(
    "modelo_id,record_id,casilla_id,fields",
    _SPLIT_DATES,
    ids=[f"{m}-{r}-{c}" for m, r, c, _ in _SPLIT_DATES],
)
def test_a_split_date_reproduces_the_undivided_date(
    modelo_id: str,
    record_id: str,
    casilla_id: str,
    fields,
) -> None:
    """Year, month and day slots concatenate to the same eight digits as one date field."""
    for value in (date(2025, 3, 14), date(1999, 12, 31), date(2000, 1, 1)):
        rendered = "".join(render_fixed_width_export_field(field, value) for field in fields)
        assert rendered == value.strftime("%Y%m%d"), (
            f"{modelo_id}/{record_id}/{casilla_id} rendered {value} as {rendered!r}"
        )


def test_an_absent_optional_split_slot_fills_with_zeros() -> None:
    """An optional casilla the taxpayer lacks still has to occupy its bytes.

    Every projector refuses ``None`` -- the right answer to "is this a quantity?"
    and the wrong one to "is this slot empty?" -- so absence is settled before
    projection. A record cannot be short a field because a figure is legitimately
    missing.
    """
    optional = [group for group in _SPLIT_AMOUNTS if not any(field.required for field in group[3])]
    assert optional, "no optional split amount to assert on"
    modelo_id, record_id, casilla_id, fields = optional[0]
    rendered = "".join(render_fixed_width_export_field(field, None) for field in fields)
    assert rendered == "0" * sum(field.length for field in fields), (
        f"{modelo_id}/{record_id}/{casilla_id} rendered an absent value as {rendered!r}"
    )


def test_reverting_a_split_part_to_a_whole_value_policy_reds_this_gate() -> None:
    """Break it on purpose: the shape these gates forbid must actually fail.

    Restores exactly the declaration every split half carried before the part
    policies existed -- the plain unsigned integer -- on a copy of a real
    published pair, and requires the render to refuse. If this ever passes, the
    reconstruction gates above are asserting nothing.
    """
    assert _SPLIT_AMOUNTS, "no split amount to mutate"
    _, _, _, fields = _SPLIT_AMOUNTS[0]
    reverted = [field.model_copy(update={"value_policy": ExportValuePolicy.UNSIGNED_INTEGER}) for field in fields]
    value = Decimal("1234.56")
    with pytest.raises(RegistryValidationError):
        for field in reverted:
            render_fixed_width_export_field(field, value)
