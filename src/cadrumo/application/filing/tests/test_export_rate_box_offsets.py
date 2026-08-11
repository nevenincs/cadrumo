"""Each Modelo 390 rate box reaches the byte offset the Diseño de Registro fixes.

The annual resumen used to export one casilla per rate TIER, and a tier is not a
rate: on 2024 dates the reducido tier legitimately carried 10 %, 7,5 % and 5 %
and the super-reducido tier carried 4 % and 2 %, because RDL 4/2024 art. 1 put
temporary rates on part of each tier's supplies. One tier figure written to box
[04] therefore declared three different rates as 10 %, and boxes [670], [703],
[668] and [701] stayed empty. The record was wrong where it is read, not merely
in the calculation.

What is under test here is the ALLOCATION, so the assertions are byte-level. A
casilla holding the right number while the record writes it to a neighbouring
box is exactly the defect class, and a casilla-value assertion cannot see it.

Non-tautology, and the reason this module does not use ``_field_slice``: the
offsets below are literals transcribed from the bundled 2024 Diseño de Registro
(``disenos_registro/modelo_390/files/16-390-ejercicio-2024-actualizado-18-12-24``,
página 2, campos 6-19, apartado 5 "Operaciones Reg. Gral. - Base Imponible y
cuota - Reg. ordin."). Deriving them from the export layout under test would
make every assertion true for whatever offset that layout happened to declare.
Only the record's own start position is read from the layout, because record
ordering is not what these tests pin.

The values are driven end to end: real :class:`IvaLedgerObservation` rows through
the real ``ledger_iva_aggregation`` resolver, mapped onto casillas through the
revision's own ``binding`` field, then through the real ``export_draft``. Nothing
is hand-placed into an observation the system under test is supposed to decide.

Real-behaviour: the committed Modelo 390 revision through the real registry
authority and the real export writer. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core import CasillaId
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    ExportLayoutDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    ValidatedRegistryAuthority,
    resolve_ledger_iva_aggregation_binding_values,
)
from ....domain.filing import FilingExportError, ModeloDraft, ModeloValueKind
from ....domain.iva import IvaCategory, IvaFlowDirection, IvaRateKind
from .._export import export_draft
from ._export_support import (
    _approved_modelo_390_registry_draft,
    _modelo_390_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PAGE_02_RECORD = "modelo-390-page-02"

# casilla id -> (official box, 1-based position within the page-02 record).
# Transcribed from the bundled 2024 Diseño de Registro, página 2, campos 6-19.
_DESIGN = {
    "iva.anual.repercutido.tipo-0.base": ("700", 13),
    "iva.anual.repercutido.tipo-0.cuota": ("701", 30),
    "iva.anual.repercutido.tipo-2.base": ("667", 47),
    "iva.anual.repercutido.tipo-2.cuota": ("668", 64),
    "iva.anual.repercutido.tipo-4.base": ("01", 81),
    "iva.anual.repercutido.tipo-4.cuota": ("02", 98),
    "iva.anual.repercutido.tipo-5.base": ("702", 115),
    "iva.anual.repercutido.tipo-5.cuota": ("703", 132),
    "iva.anual.repercutido.tipo-7-5.base": ("669", 149),
    "iva.anual.repercutido.tipo-7-5.cuota": ("670", 166),
    "iva.anual.repercutido.tipo-10.base": ("03", 183),
    "iva.anual.repercutido.tipo-10.cuota": ("04", 200),
    "iva.anual.repercutido.tipo-21.base": ("05", 217),
    "iva.anual.repercutido.tipo-21.cuota": ("06", 234),
}
_FIELD_LENGTH = 17

# Every base and every cuota is a distinct amount, and no cuota is its base times
# its rate. A renderer that swapped two boxes, or derived a cuota from a base,
# lands on a number that appears nowhere else in the record.
_ROWS = (
    ("0", IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO, date(2024, 3, 4), "5000.00", "0.00", "0.00"),
    ("2", IvaCategory.DOMESTIC_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED, date(2024, 11, 5), "3500.00", "71.00", "0.02"),
    ("4", IvaCategory.DOMESTIC_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED, date(2024, 3, 6), "1500.00", "63.00", "0.04"),
    ("5", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 8, 7), "8000.00", "407.00", "0.05"),
    ("7-5", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 11, 8), "4000.00", "311.00", "0.075"),
    ("10", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 3, 9), "2000.00", "205.00", "0.10"),
    ("21", IvaCategory.DOMESTIC_GENERAL, IvaRateKind.GENERAL, date(2024, 3, 10), "1000.00", "217.00", "0.21"),
)

# A real reducido sale carrying a real cuota whose RATE the ledger never captured.
# It must reach the rate-blind tier total and no rate-specific box.
_UNRATED_BASE = Decimal("9000.00")
_UNRATED_CUOTA = Decimal("113.00")

_REDUCIDO_TOTAL_CASILLA = "iva.anual.repercutido.reducido"


@cache
def _m390_revision() -> ModeloRevision:
    """The committed Modelo 390 revision, through the real registry authority."""
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    return authority.snapshot("390", filing_year=2025, period="0A").revision


def _observation(
    *,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    on: date,
    base: Decimal,
    cuota: Decimal,
    applied_rate: Decimal | None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="ledger-m390-rate-box-offsets",
        transaction_date=on,
        category=category,
        exemption_article=None,
        rate_kind=rate_kind,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=base,
        iva_amount=cuota,
        recargo_amount=Decimal("0"),
        applied_rate=applied_rate,
    )


def _rated_rows() -> tuple[IvaLedgerObservation, ...]:
    return tuple(
        _observation(
            category=category,
            rate_kind=rate_kind,
            on=on,
            base=Decimal(base),
            cuota=Decimal(cuota),
            applied_rate=Decimal(applied_rate),
        )
        for _, category, rate_kind, on, base, cuota, applied_rate in _ROWS
    )


def _unrated_row() -> IvaLedgerObservation:
    return _observation(
        category=IvaCategory.DOMESTIC_REDUCED,
        rate_kind=IvaRateKind.REDUCED,
        on=date(2024, 6, 1),
        base=_UNRATED_BASE,
        cuota=_UNRATED_CUOTA,
        applied_rate=None,
    )


def _casilla_values(revision: ModeloRevision, rows: tuple[IvaLedgerObservation, ...]) -> dict[CasillaId, Decimal]:
    """Resolve ``rows`` and key the result by casilla through the revision's bindings.

    The binding-to-casilla step reads ``casilla.binding`` off the revision rather
    than restating a mapping here, so a registry rewiring surfaces as a changed
    value in these tests instead of being masked by a stale local table.
    """
    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, rows))
    return {
        casilla.id: resolved[casilla.binding]
        for casilla in revision.casillas
        if casilla.binding is not None and casilla.binding in resolved
    }


def _draft_with(values: dict[CasillaId, Decimal]) -> ModeloDraft:
    draft = _approved_modelo_390_registry_draft()
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


def _page_02_start(layout: ExportLayoutDefinition) -> int:
    """Byte index where the page-02 record begins, from record ORDER only.

    Record sequencing is not what this module pins, so reading it from the layout
    is not circular; the field positions WITHIN the record are design literals.
    """
    cursor = 0
    for record in sorted(layout.records, key=lambda item: item.order):
        if record.id == _PAGE_02_RECORD:
            return cursor
        cursor += max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
        if record.line_ending == "crlf":
            cursor += 2
        elif record.line_ending == "lf":
            cursor += 1
    raise AssertionError(f"export record {_PAGE_02_RECORD!r} not found")


def _rendered_money(payload: bytes, start: int, position: int) -> Decimal:
    """Decode the signed 17-byte money field at the design ``position``."""
    begin = start + position - 1
    raw = payload[begin : begin + _FIELD_LENGTH].decode("latin-1")
    assert len(raw) == _FIELD_LENGTH, f"payload too short for position {position}"
    sign, digits = raw[0], raw[1:]
    assert digits.isdigit(), f"position {position} rendered non-numeric {raw!r}"
    magnitude = Decimal(digits) / Decimal(100)
    return -magnitude if sign == "N" else magnitude


def test_every_rate_box_lands_at_its_design_offset(tmp_path: Path) -> None:
    """Seven rates, seven distinct pairs, each at the position the Diseño fixes.

    The direction that would fail before the export fields were moved onto the
    box layer: the super-reducido tier total 134.00 (4 % plus 2 %) stood at
    position 98, where the Diseño publishes box [02], "Tipo 4 % - Cuota" alone.
    """
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("390",))
    values = _casilla_values(_m390_revision(), _rated_rows())
    output = tmp_path / "modelo-390.txt"

    export_draft(
        _draft_with(values),
        output_path=output,
        headers=_modelo_390_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    start = _page_02_start(provider.get_subview("390").export_layouts[0])
    for suffix, _, _, _, base, cuota, _ in _ROWS:
        for role, expected in (("base", Decimal(base)), ("cuota", Decimal(cuota))):
            casilla_id = f"iva.anual.repercutido.tipo-{suffix}.{role}"
            box, position = _DESIGN[casilla_id]
            assert _rendered_money(payload, start, position) == expected, (
                f"box [{box}] ({casilla_id}) at position {position}"
            )


def test_the_merged_tier_no_longer_writes_a_rate_specific_box(tmp_path: Path) -> None:
    """Position 98 carries the 4 % cuota alone, not the whole super-reducido tier.

    The regression this whole change exists for, stated as the one number that
    moved: the tier sums 63.00 + 71.00 = 134.00, and box [02] must carry 63.00.
    """
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("390",))
    values = _casilla_values(_m390_revision(), _rated_rows())
    output = tmp_path / "modelo-390.txt"

    export_draft(
        _draft_with(values),
        output_path=output,
        headers=_modelo_390_export_headers(),
        schema_provider=provider,
    )

    payload = output.read_bytes()
    start = _page_02_start(provider.get_subview("390").export_layouts[0])
    tier_total = values["iva.anual.repercutido.super-reducido"]
    assert tier_total == Decimal("134.00")
    assert _rendered_money(payload, start, 98) == Decimal("63.00")
    assert _rendered_money(payload, start, 64) == Decimal("71.00")


def test_a_rate_unrecorded_row_stays_in_the_total_and_refuses_the_export(tmp_path: Path) -> None:
    """The row survives into the tier total, reaches no box, and blocks the write.

    Both halves matter. If the 113.00 vanished from the total the change would
    have deleted money from the return, which is graver than the mis-allocation
    it repairs. If it reached a box, the record would assert a rate the operator
    never stated. It does neither, so the parts no longer sum to the whole, and
    the export refuses rather than handing a human an artefact AEAT will bounce.
    """
    provider = _schema_provider(filing_year=2025, period="0A", modelos=("390",))
    values = _casilla_values(_m390_revision(), (*_rated_rows(), _unrated_row()))
    output = tmp_path / "modelo-390.txt"

    boxes = sum(values[f"iva.anual.repercutido.tipo-{suffix}.cuota"] for suffix in ("10", "7-5", "5"))
    assert values[_REDUCIDO_TOTAL_CASILLA] - boxes == _UNRATED_CUOTA

    with pytest.raises(FilingExportError) as excinfo:
        export_draft(
            _draft_with(values),
            output_path=output,
            headers=_modelo_390_export_headers(),
            schema_provider=provider,
        )

    message = str(excinfo.value)
    assert _REDUCIDO_TOTAL_CASILLA in message
    assert str(_UNRATED_CUOTA) in message
    assert not output.exists()
