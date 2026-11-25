"""A Modelo 303 Tipo % slot the design defines by note, noted constant or printed list renders at two decimals.

The 2023 to 2026 designs print the transitional and recargo rate slots of
casillas 154, 17, 166 and 169 as a constant carrying a note (``Constante
"00500". Nota 7``), as a bare note pointer whose table lists the wire values
(``00500``, ``00750``, ``00050``, ``00062``, ``00100``), or as a printed list of
runs (``"00026", "00050"``). Every one of those values carries two implied
decimals. Read as unscaled integers, the generator emitted a five-percent rate
as ``00005``, refused the seven-and-a-half percent one and refused every
fractional recargo rate, so every return carrying one failed to export. These tests
drive the generator's own entry point over each hash-pinned design and its
shipped authored inputs, then render through the production codec, so the
bytes asserted are the bytes a filed return carries.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_serving_period

from ...compiler.loader import load_registry_tree
from ...form_layout.reconciliation import admit_note_governed_scale
from ...tests.authored_edition_support import source_reference
from ..export_fragment_provenance import ExportFieldDerivation
from ..export_tree import render_complete_export_tree
from ..render_check import build_revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RATE_CASILLAS: Final = frozenset({"154", "17", "166", "169"})


def _rate_slots(source_ref: str, tmp_path: Path) -> dict[str, ExportFieldDerivation]:
    """Render the design's whole export tree and keep its DP30301 rate-slot derivations."""
    applies_from = source_reference(source_ref).applies_from
    assert applies_from is not None
    period = f"{(applies_from.month - 1) // 3 + 1}T"
    revision = str(revision_serving_period("303", applies_from.year, period).id)
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    definition = next(item for item in modelos if str(item.id) == "303")
    inputs = build_revision_render_inputs(
        definition,
        catalogues,
        modelo="303",
        revision=revision,
        source_ref=source_ref,
        bootstrap_transport=None,
        filing_year=applies_from.year,
        period=period,
        source_root=bundled_path(),
    )
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=str(inputs.revision_id),
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    return {
        str(derivation.field.casilla_id): derivation
        for derivation in rendered.field_derivations
        if derivation.parser_field.sheet == "DP30301" and str(derivation.field.casilla_id) in _RATE_CASILLAS
    }


@pytest.fixture(
    scope="module",
    params=[
        "aeat-dr-303-2023",
        "aeat-dr-303-2024-early",
        "aeat-dr-303-2024-late",
        "aeat-dr-303-2025",
        "aeat-dr-303-2026",
    ],
)
def design(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[str, dict[str, ExportFieldDerivation]]:
    source_ref = str(request.param)
    return source_ref, _rate_slots(source_ref, Path(tmp_path_factory.mktemp(source_ref)))


#: Rate and wire value per design and casilla, each pair read from the design's
#: own constant, note table or printed list.
_CASES: Final[dict[str, dict[str, tuple[tuple[str, str], ...]]]] = {
    "aeat-dr-303-2023": {
        "154": (("5.00", "00500"),),
        "17": (("0", "00000"), ("0.50", "00050"), ("0.62", "00062")),
    },
    "aeat-dr-303-2024-early": {
        "154": (("5.00", "00500"),),
        "17": (("0", "00000"), ("0.50", "00050"), ("0.62", "00062")),
    },
    "aeat-dr-303-2024-late": {
        "154": (("5.00", "00500"), ("7.50", "00750")),
        "17": (("0", "00000"), ("0.50", "00050"), ("0.62", "00062"), ("1.00", "00100")),
        "166": (("2.00", "00200"),),
        "169": (("0.26", "00026"), ("0.50", "00050")),
    },
    "aeat-dr-303-2025": {"169": (("0.50", "00050"),)},
    "aeat-dr-303-2026": {"169": (("0.50", "00050"),)},
}

#: Slots whose cell names Nota 7, which lets a filer taxed only by a foral
#: administration print "00000"; every such slot must accept the zero rate.
_FORAL_ZERO: Final[dict[str, tuple[str, ...]]] = {
    "aeat-dr-303-2023": ("154",),
    "aeat-dr-303-2024-early": ("154",),
    "aeat-dr-303-2024-late": ("154", "17", "166", "169"),
    "aeat-dr-303-2025": ("169",),
    "aeat-dr-303-2026": ("169",),
}

#: Rates a closed slot must refuse: off its list, or the list read as whole percent.
_REFUSED: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    "aeat-dr-303-2023": {"17": ("0.51", "50")},
    "aeat-dr-303-2024-early": {"17": ("0.51", "50")},
    "aeat-dr-303-2024-late": {"17": ("0.51", "1.50"), "169": ("0.51", "26")},
    "aeat-dr-303-2025": {"169": ("0.26", "50")},
    "aeat-dr-303-2026": {"169": ("0.26", "50")},
}


def test_each_noted_rate_renders_the_wire_value_its_design_prints(
    design: tuple[str, dict[str, ExportFieldDerivation]],
) -> None:
    source_ref, slots = design
    for casilla, pairs in _CASES[source_ref].items():
        field = slots[casilla].field
        for rate, wire in pairs:
            assert render_fixed_width_export_field(field, Decimal(rate)) == wire, (source_ref, casilla, rate)


def test_each_nota_7_slot_accepts_the_foral_zero_rate(
    design: tuple[str, dict[str, ExportFieldDerivation]],
) -> None:
    source_ref, slots = design
    for casilla in _FORAL_ZERO[source_ref]:
        field = slots[casilla].field
        for zero in ("0", "0.00"):
            assert render_fixed_width_export_field(field, Decimal(zero)) == "00000", (source_ref, casilla)


def test_each_closed_rate_slot_refuses_a_rate_off_its_list(
    design: tuple[str, dict[str, ExportFieldDerivation]],
) -> None:
    source_ref, slots = design
    for casilla, rates in _REFUSED[source_ref].items():
        field = slots[casilla].field
        for rate in rates:
            with pytest.raises(RegistryValidationError, match="allowed_values"):
                render_fixed_width_export_field(field, Decimal(rate))


def test_each_noted_rate_slot_is_an_unsigned_three_and_two_percentage(
    design: tuple[str, dict[str, ExportFieldDerivation]],
) -> None:
    source_ref, slots = design
    for casilla in _CASES[source_ref]:
        field = slots[casilla].field
        assert slots[casilla].derivation_code == "numeric-note-governed-amount-v1", (source_ref, casilla)
        assert str(field.data_type) == "decimal"
        assert field.decimals == 2
        assert field.signed is False
        assert field.length == 5
        assert field.value_policy is None


_UNSCALED: Final[dict[str, object]] = {
    "data_type": "integer",
    "decimals": None,
    "signed": False,
    "value_policy": None,
    "allowed_values": None,
}
_SCALED: Final[dict[str, object]] = {
    "data_type": "decimal",
    "decimals": 2,
    "signed": False,
    "value_policy": None,
    "allowed_values": None,
}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (_UNSCALED, _SCALED),
        (
            {**_UNSCALED, "value_policy": "enumerated-digits", "allowed_values": ("26", "50")},
            {**_SCALED, "allowed_values": ("0", "26", "50")},
        ),
        (_UNSCALED, {**_SCALED, "allowed_values": ("0", "100", "50", "62")}),
    ],
    ids=["open", "printed-list-gains-the-foral-zero", "note-table-closes-a-pointer"],
)
def test_form_reconciliation_admits_a_rate_slot_gaining_its_noted_scale(
    old: dict[str, object], new: dict[str, object]
) -> None:
    held = dict(old)
    assert admit_note_governed_scale(held, new) == 1
    assert held == new


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ({**_UNSCALED, "value_policy": "implied-decimal"}, _SCALED),
        ({**_UNSCALED, "data_type": "decimal", "decimals": 2}, _SCALED),
        (_UNSCALED, {**_SCALED, "signed": True}),
        (_UNSCALED, {**_SCALED, "value_policy": "implied-decimal"}),
    ],
    ids=["another-policy", "already-scaled", "gains-a-sign", "gains-a-policy"],
)
def test_form_reconciliation_admits_no_other_shape_change(old: dict[str, object], new: dict[str, object]) -> None:
    held = dict(old)
    assert admit_note_governed_scale(held, new) == 0
    assert held == old
