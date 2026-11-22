"""A Modelo 200 box printed on several pages exports only into its own page's cell.

The record designs print one box number on several pages with a different meaning
on each: ``[00009]`` is "Entidad dominante de grupo fiscal" on DP200001 and also a
bases imponibles negativas cohort on DP200015; ``[00017]`` is "Cooperativa
protegida" on DP200001 and also a cooperativas cuota-compensation cohort on
DP200022; ``[00088]``, ``[00089]`` and ``[00090]`` are the three cells of the
Festival Porta Ferrada deduction row on a deducciones page, and a design that also
prints an identification flag of the same number on DP200001 gives it another
meaning there. An edition that does not declare a box is not asked about it: each
case pairs a filing year with a box that year's edition declares, and every box
must be exercised by at least one filing year. A value the taxpayer states for the DP200001 flag must reach
the DP200001 cell and nothing else, and a stated deduction amount must reach its own
deduction cell and leave the flag of the same number alone, although it does feed
the deduction totals the design derives from it. These tests run the real
``build_draft`` then
``export_draft`` path for every year a filing-grade Modelo 200 edition serves, and
compare the fichero against the one exported with the box never supplied: the only
bytes that may change are the flag's own cell.

The remaining limit is the cooperativa protegida flag: stating it no longer trips the
shared-box refusal, but the export still refuses because the protected cooperative's
cuota is unsupported, so the required liquidación boxes it feeds stay omitted.

The casilla is found by its continuity identity rather than by its id, so the test
holds whether the box is named by its bare number or by its page-qualified id.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.errors import ModeloApplicationError
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.export_shared_owner import canonical_export_layout
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..edition_export_scenarios import m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"

# Each flag's continuity identity and its case label. The design prints every one on
# DP200001 as a selected-flag byte (type Num, length 1).
_FLAG_SHEET = "DP200001"
_FLAGS = (
    ("is-entidad-dominante-de-grupo-fiscal", "00009-entidad-dominante"),
    (
        "is-participe-de-agrupacion-de-interes-economico-o-de-union-temporal-de-empresas",
        "00089-participe-aie-ute",
    ),
    ("is-opcion-art-39-3-lis", "00090-opcion-art-39-3"),
)
# The Festival Porta Ferrada deduction row. Each edition prints it on its own deducciones
# page, so the sheet is read from the page the edition declares the casilla on.
_PORTA_FERRADA = (
    ("is-deduccion-porta-ferrada-pendiente-generada", "00088-porta-ferrada-pendiente"),
    ("is-deduccion-porta-ferrada-aplicado-periodo", "00089-porta-ferrada-aplicado"),
    ("is-deduccion-porta-ferrada-pendiente-futuro", "00090-porta-ferrada-futuro"),
)
_PORTA_FERRADA_AMOUNT = Decimal("1234.56")
_COOPERATIVA_PROTEGIDA = "is-cooperativa-protegida"
# The liquidación boxes a protected cooperative's unsupported cuota leaves unrendered,
# [00562], [00582], [00592], [00599] and [00611] in page order. The editions print them on
# different sheets, so each box is read from the page the edition declares it on.
_UNSUPPORTED_COOPERATIVE_CUOTA = (
    "is-liquidacion-iii-cuota-integra",
    "is-liquidacion-iii-cuota-integra-ajustada-positiva",
    "is-cuota-liquida",
    "is-resultado-ingresar-o-devolver",
    "is-liquidacion-iv-cuota-diferencial",
)
_SELECTED = Decimal("1")


class _PayloadSink:
    payload: bytes | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _filing_grade_chains() -> dict[int, frozenset[str]]:
    """Map every year served at filing grade with an export layout to the continuity ids its edition declares."""
    chains: dict[int, frozenset[str]] = {}
    with bundled_indexed_authority().operation() as operation:
        for year in operation.supported_filing_years().years:
            try:
                snapshot = operation.snapshot(_M200, filing_year=year, period="0A", grade=RegistryAuthorityGrade.FILING)
            except RegistryError:
                continue
            if canonical_export_layout(snapshot.revision.export_layouts) is not None:
                chains[year] = frozenset(str(casilla.continuidad_id) for casilla in snapshot.revision.casillas)
    return chains


def _export(year: int, supplied: ModeloInputs) -> tuple[bytes, ModeloRevision]:
    period = Period.from_year_and_code(year, "0A")
    scenario = m200_export_scenario(period)
    with bundled_indexed_authority().operation() as operation:
        provider = build_runtime_schema_provider(operation=operation, modelos=(_M200,), filing_year=year, period=period)
        revision = provider.get_snapshot(_M200).revision
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Shared box"),
            inputs={**scenario.inputs, **supplied},
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        identity = scenario.product_software_identity_factory
        sink = _PayloadSink()
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=scenario.producer_snapshot(),
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=None if identity is None else identity(),
            schema_provider=provider,
        )
    assert sink.payload is not None
    return sink.payload, revision


def _casilla_id(revision: ModeloRevision, continuidad_id: str) -> str:
    (casilla,) = [casilla for casilla in revision.casillas if str(casilla.continuidad_id) == continuidad_id]
    return str(casilla.id)


def _declared_sheet(casilla_id: str) -> str:
    """Return the record sheet a page-qualified casilla id names."""
    sheet, separator, _number = casilla_id.partition(":")
    assert separator, f"{casilla_id} is not page qualified"
    return sheet


def _cells(revision: ModeloRevision, casilla_id: str) -> tuple[ExportFieldDefinition, ...]:
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    return tuple(
        field
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and str(field.casilla_id) == casilla_id
    )


def _record_line(payload: bytes, revision: ModeloRevision, sheet: str) -> tuple[int, bytes]:
    """Return the start of the record line whose opening literals name ``sheet``, and the line."""
    marker = f".{sheet.lower()}."
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    tags = set()
    for record in layout.records:
        literal: list[str] = []
        for field in sorted(
            (field for field in record.fields if marker in str(field.id) and field.offset is not None),
            key=lambda field: field.offset or 0,
        ):
            if field.kind is not CasillaFieldKind.LITERAL or field.literal is None:
                break
            literal.append(field.literal)
        if literal:
            tags.add("".join(literal))
    (tag,) = tags
    encoded = tag.encode("ascii")
    (start,) = [index for index in range(len(payload)) if payload.startswith(encoded, index)]
    end = payload.find(b"\r\n", start)
    return start, payload[start : len(payload) if end == -1 else end]


_CHAINS = _filing_grade_chains()
_YEARS = tuple(_CHAINS)


def _declared_cases(chains: tuple[tuple[str, str], ...]) -> list[object]:
    """Pair each filing-grade year with every one of ``chains`` its edition declares."""
    return [
        pytest.param(year, continuidad_id, id=f"{label}-{year}")
        for continuidad_id, label in chains
        for year, declared in _CHAINS.items()
        if continuidad_id in declared
    ]


def test_a_filing_grade_modelo_200_edition_exists() -> None:
    assert _YEARS, "no supported year serves Modelo 200 at filing grade, so these checks prove nothing"


@pytest.mark.parametrize(("continuidad_id", "label"), (*_FLAGS, *_PORTA_FERRADA))
def test_every_shared_box_is_exercised_by_some_filing_grade_year(continuidad_id: str, label: str) -> None:
    assert any(continuidad_id in declared for declared in _CHAINS.values()), (
        f"no filing-grade Modelo 200 edition declares {label}, so its case proves nothing"
    )


@pytest.mark.parametrize(("year", "continuidad_id"), _declared_cases(_FLAGS))
def test_a_stated_flag_lands_only_in_its_own_page_cell(year: int, continuidad_id: str) -> None:
    sheet = _FLAG_SHEET
    absent, revision = _export(year, {})
    casilla_id = _casilla_id(revision, continuidad_id)

    stated, _ = _export(year, {casilla_id: _SELECTED})

    (cell,) = _cells(revision, casilla_id)
    assert f".{sheet.lower()}." in str(cell.id)
    assert cell.offset is not None and cell.length == 1
    start, _line = _record_line(stated, revision, sheet)
    position = start + cell.offset - 1
    assert stated[position : position + cell.length] == b"1"
    assert len(stated) == len(absent)
    changed = [index for index, (left, right) in enumerate(zip(absent, stated, strict=True)) if left != right]
    assert changed == [position]


@pytest.mark.parametrize(("year", "continuidad_id"), _declared_cases(_PORTA_FERRADA))
def test_a_stated_porta_ferrada_amount_lands_in_its_own_cell_and_not_in_the_flag_of_the_same_number(
    year: int, continuidad_id: str
) -> None:
    absent, revision = _export(year, {})
    casilla_id = _casilla_id(revision, continuidad_id)
    sheet = _declared_sheet(casilla_id)
    assert sheet != _FLAG_SHEET
    (cell,) = _cells(revision, casilla_id)
    assert f".{sheet.lower()}." in str(cell.id)
    assert cell.offset is not None and cell.length == 17
    # The identification flag the same printed number names on page one, where the
    # edition's design prints one.
    number = str(next(casilla for casilla in revision.casillas if str(casilla.id) == casilla_id).number)
    flag_id = f"{_FLAG_SHEET}:{number}"
    flag_cells = _cells(revision, flag_id)
    if any(str(casilla.id) == flag_id for casilla in revision.casillas):
        (flag_cell,) = flag_cells
        assert flag_cell.offset is not None and flag_cell.length == 1
    else:
        assert flag_cells == ()

    stated, _ = _export(year, {casilla_id: _PORTA_FERRADA_AMOUNT})

    assert len(stated) == len(absent)
    start, _line = _record_line(stated, revision, sheet)
    position = start + cell.offset - 1
    assert absent[position : position + cell.length] == b"00000000000000000"
    assert stated[position : position + cell.length] == b"00000000000123456"
    # Page one, with any flag of the same number on it, is left byte for byte as it was.
    flag_start, stated_page_one = _record_line(stated, revision, _FLAG_SHEET)
    assert _record_line(absent, revision, _FLAG_SHEET) == (flag_start, stated_page_one)
    for flag_cell in flag_cells:
        assert flag_cell.offset is not None
        flag_position = flag_start + flag_cell.offset - 1
        changed = {index for index, (left, right) in enumerate(zip(absent, stated, strict=True)) if left != right}
        assert flag_position not in changed


@pytest.mark.parametrize("year", _YEARS)
def test_a_stated_cooperativa_protegida_flag_is_refused_only_for_its_unsupported_cuota(year: int) -> None:
    _absent, revision = _export(year, {})
    casilla_id = _casilla_id(revision, _COOPERATIVA_PROTEGIDA)
    (cell,) = _cells(revision, casilla_id)
    assert ".dp200001." in str(cell.id)

    with pytest.raises(ModeloApplicationError) as refusal:
        _export(year, {casilla_id: _SELECTED})

    assert refusal.value.translated_message == "application.filing.export_parity.errors.required_casillas_omitted"
    context = refusal.value.context
    assert context is not None
    missing_items = context["missing_casillas"]
    assert isinstance(missing_items, list | tuple)
    assert tuple(item["casilla_id"] for item in missing_items) == tuple(
        _casilla_id(revision, continuidad_id) for continuidad_id in _UNSUPPORTED_COOPERATIVE_CUOTA
    )
