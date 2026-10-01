"""Modelo 200 cells that reuse another sheet's box number carry their own concept.

AEAT's Modelo 200 record design prints the same five-digit box number on
several sheets. Sometimes the second printing is an echo of the same amount --
a detail sheet's "Total - Aplicado en esta liquidación" row repeats the
liquidación box it feeds, and the DID and AIE summaries repeat the base
imponible and cuota íntegra. More often it is a different concept that merely
shares the number: the insurer and Banco de España equity statements
(DP200032/33, DP200041-43) reuse the liquidación numbers 00547, 00592, 00599
and others for their own columns, and the ordinary equity statement prints
00592 and 00599 for business-combination rows.

A cell of the second kind must map to a casilla declared for its own sheet; if
it maps to the liquidación casilla, the export writes that box's amount into a
cell meaning something else. These tests hold each edition's semantic map and
generated layout to that, and render the published edition to prove the cell
exports its own value when supplied and the design's zero fill when not. In
particular, DP200014B's monetary boxes 00031, 00032 and 00083 are distinct
from DP200001's integer entity characters sharing those printed numbers.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable, Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..compiler.record_design import extract_record_design
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS as _ECHOES
from ..edition_export_scenarios import m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID
from ..pipeline.semantic_map import SemanticMap, load_semantic_map
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_MAPPINGS = Path("dev/registry/mappings/modelo_200")
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")

type Cell = tuple[str, str]
"""A mapped cell as (record sheet, casilla id it is mapped to)."""


def foreign_sheet_cells(
    cells: Iterable[tuple[str, str, str]], casillas: Mapping[str, CasillaDefinition]
) -> dict[Cell, list[str]]:
    """Return mapped cells whose casilla belongs to another record sheet, with the fields that map them.

    ``cells`` yields ``(export field id, record sheet, casilla id)``. A casilla
    without a sheet makes no claim about where it belongs and is not judged, and
    neither is an id the edition does not declare: the generator refuses that
    on its own when it resolves the map against the edition.
    """
    found: dict[Cell, list[str]] = {}
    for field_id, sheet, casilla_id in cells:
        casilla = casillas.get(casilla_id)
        if casilla is None:
            continue
        segmento = casilla.segmento
        if segmento is not None and segmento != sheet:
            found.setdefault((sheet, casilla_id), []).append(field_id)
    return found


def _semantic_map_cells(semantic_map: SemanticMap) -> list[tuple[str, str, str]]:
    return [
        (str(entry.export_field_id), entry.anchor.sheet, str(entry.casilla_id))
        for entry in semantic_map.entries
        if entry.kind is CasillaFieldKind.CASILLA and entry.casilla_id is not None
    ]


def _layout_cells(revision: ModeloRevision) -> list[tuple[str, str, str]]:
    return [
        (str(field.id), str(field.id).split(".")[1].upper(), str(field.casilla_id))
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
    ]


def _design_source(revision: ModeloRevision):
    sources = compiled_bundled_authority().catalogues.sources
    (design,) = [sources[ref] for ref in revision.source_refs if sources[ref].kind == "record_design"]
    return design


@cache
def _semantic_map(epoch: str) -> SemanticMap:
    return load_semantic_map(_MAPPINGS / epoch)


def _casillas(revision: ModeloRevision) -> dict[str, CasillaDefinition]:
    return {str(casilla.id): casilla for casilla in revision.casillas}


def _mapped_revisions() -> tuple[ModeloRevision, ...]:
    """The editions whose record-design epoch has a semantic map: only those map design cells to casillas."""
    return tuple(
        revision
        for revision in authored_revisions(_MODELO)
        if (_MAPPINGS / str(_design_source(revision).record_design_epoch)).is_dir()
    )


def _supported_years() -> tuple[int, ...]:
    return compiled_bundled_authority().supported_filing_years().years


def _signed_note_fields(revision: ModeloRevision):
    design = _design_source(revision)
    return tuple(
        field
        for sheet in extract_record_design(bundled_path() / design.corpus_path).require_complete()
        if sheet.name.strip() == "DP200014B"
        for field in sheet.fields
        if field.type_code == "N" and field.content is not None and field.content.startswith("Nota")
    )


def _filing_years() -> tuple[int, ...]:
    authority = compiled_bundled_authority()
    return tuple(
        year
        for year in _supported_years()
        if authority.snapshot(
            _MODELO, filing_year=year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        ).revision.authority_grade
        is RegistryAuthorityGrade.FILING
    )


def test_every_edition_with_an_export_layout_has_a_semantic_map() -> None:
    mapped = {str(revision.id) for revision in _mapped_revisions()}
    exporting = {str(revision.id) for revision in authored_revisions(_MODELO) if revision.export_layouts}
    assert exporting, "no edition exports, so this check proves nothing"
    assert exporting <= mapped


@pytest.mark.parametrize("revision", _mapped_revisions(), ids=lambda revision: str(revision.id))
def test_every_cross_sheet_mapping_is_a_declared_echo(revision: ModeloRevision) -> None:
    semantic_map = _semantic_map(str(_design_source(revision).record_design_epoch))
    expected = _ECHOES
    assert set(foreign_sheet_cells(_semantic_map_cells(semantic_map), _casillas(revision))) == expected
    if revision.export_layouts:
        assert set(foreign_sheet_cells(_layout_cells(revision), _casillas(revision))) == expected


@pytest.mark.parametrize("revision", _mapped_revisions(), ids=lambda revision: str(revision.id))
def test_a_box_declared_for_its_own_sheet_is_where_that_sheet_maps(revision: ModeloRevision) -> None:
    """Every design cell whose sheet has its own casilla for the printed number maps to that casilla."""
    design = _design_source(revision)
    printed = {
        (sheet.name.strip(), field.row): _PRINTED_BOX.findall(field.description)
        for sheet in extract_record_design(bundled_path() / design.corpus_path).require_complete()
        for field in sheet.fields
    }
    own = {
        (casilla.segmento, str(casilla.number)): str(casilla.id) for casilla in revision.casillas if casilla.segmento
    }
    semantic_map = _semantic_map(str(design.record_design_epoch))
    misplaced = []
    checked = 0
    for entry in semantic_map.entries:
        if entry.kind is not CasillaFieldKind.CASILLA:
            continue
        for number in printed.get((entry.anchor.sheet, entry.anchor.source_row), ()):
            expected = own.get((entry.anchor.sheet, number))
            if expected is None:
                continue
            checked += 1
            if str(entry.casilla_id) != expected:
                misplaced.append((str(entry.export_field_id), str(entry.casilla_id), expected))
    assert checked, "no design cell has a sheet-scoped casilla, so this check proves nothing"
    assert misplaced == []


def test_a_cell_remapped_to_the_liquidacion_box_is_caught(tmp_path: Path) -> None:
    """Teeth: point one insurer equity cell back at the liquidación box in an isolated mapping copy."""
    revision = compiled_bundled_authority().snapshot(_MODELO, filing_year=max(_filing_years()), period="0A").revision
    epoch = str(_design_source(revision).record_design_epoch)
    copy = tmp_path / epoch
    shutil.copytree(_MAPPINGS / epoch, copy)
    casillas = _casillas(revision)
    entry = next(
        entry
        for entry in _semantic_map(epoch).entries
        if entry.anchor.sheet == "DP200042" and str(entry.casilla_id) == "DP200042:00547"
    )
    fragment = next(copy.glob("*-dp200042.toml"))
    text = fragment.read_text(encoding="utf-8")
    block_start = text.index(f'export_field_id = "{entry.export_field_id}"')
    block_end = block_start + text[block_start:].index("[entries.anchor]")
    block = text[block_start:block_end]
    assert block.count('casilla_id = "DP200042:00547"') == 1
    fragment.write_text(
        text[:block_start] + block.replace('"DP200042:00547"', '"DP200014:00547"') + text[block_end:],
        encoding="utf-8",
    )

    found = foreign_sheet_cells(_semantic_map_cells(load_semantic_map(copy)), casillas)

    assert set(found) - _ECHOES == {("DP200042", "DP200014:00547")}
    assert found[("DP200042", "DP200014:00547")] == [str(entry.export_field_id)]


@pytest.mark.parametrize(
    "revision",
    [revision for revision in _mapped_revisions() if {"DP200014B:00031", "DP200001:00031"} <= set(_casillas(revision))],
    ids=lambda revision: str(revision.id),
)
def test_dp200014b_box_remapped_to_the_capital_risk_flag_is_caught(revision: ModeloRevision, tmp_path: Path) -> None:
    """Teeth: DP200001:00031 cannot own DP200014B's separate money cell."""
    epoch = str(_design_source(revision).record_design_epoch)
    copy = tmp_path / epoch
    shutil.copytree(_MAPPINGS / epoch, copy)
    casillas = _casillas(revision)
    entry = next(
        entry
        for entry in _semantic_map(epoch).entries
        if entry.anchor.sheet == "DP200014B" and str(entry.casilla_id) == "DP200014B:00031"
    )
    fragment = next(copy.glob("*-dp200014b.toml"))
    text = fragment.read_text(encoding="utf-8")
    block_start = text.index(f'export_field_id = "{entry.export_field_id}"')
    block_end = block_start + text[block_start:].index("[entries.anchor]")
    block = text[block_start:block_end]
    assert block.count('casilla_id = "DP200014B:00031"') == 1
    fragment.write_text(
        text[:block_start] + block.replace('"DP200014B:00031"', '"DP200001:00031"') + text[block_end:],
        encoding="utf-8",
    )

    found = foreign_sheet_cells(_semantic_map_cells(load_semantic_map(copy)), casillas)

    assert set(found) - _ECHOES == {("DP200014B", "DP200001:00031")}
    assert found[("DP200014B", "DP200001:00031")] == [str(entry.export_field_id)]


class _PayloadSink:
    """Keeps the validated payload in memory; no plaintext export touches disk."""

    payload: bytes = b""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


type Slot = tuple[str, int, int, str]
"""One rendered cell as (record tag, offset, length, the casilla it is mapped to)."""


def _amount_fields(revision: ModeloRevision) -> dict[str, bool]:
    """Map each exported casilla to whether every slot it fills is a plain amount in cents."""
    amounts: dict[str, bool] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None:
                    cents = field.data_type == "money" or (field.data_type == "decimal" and field.decimals == 2)
                    plain = cents and field.value_policy is None
                    amounts[str(field.casilla_id)] = amounts.get(str(field.casilla_id), True) and plain
    return amounts


def _shared_number_slots(revision: ModeloRevision) -> dict[str, list[Slot]]:
    """Group by printed number the cells mapped to a casilla of their own sheet, where several sheets have one.

    Only manually entered plain amounts take part, so a draft can supply any value for them.
    """
    casillas = _casillas(revision)
    amounts = _amount_fields(revision)
    sheets_by_number: dict[str, set[str]] = {}
    for casilla in revision.casillas:
        if (
            casilla.segmento
            and casilla.input_kind is InputKind.MANUAL
            and casilla.data_type is CasillaDataType.MONEY
            and amounts.get(str(casilla.id), False)
        ):
            sheets_by_number.setdefault(str(casilla.number), set()).add(casilla.segmento)
    groups: dict[str, list[Slot]] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.kind is not CasillaFieldKind.CASILLA or field.casilla_id is None:
                    continue
                own = casillas[str(field.casilla_id)]
                sheet = str(field.id).split(".")[1].upper()
                number = str(own.number)
                if own.segmento != sheet or own.segmento not in sheets_by_number.get(number, set()):
                    continue
                if len(sheets_by_number[number]) < 2:
                    continue
                assert field.offset is not None and field.length is not None
                groups.setdefault(number, []).append(
                    (_record_tag(revision, sheet), field.offset, field.length, str(own.id))
                )
    return groups


@pytest.fixture(scope="module", params=_filing_years())
def rendered_edition(request: pytest.FixtureRequest):
    """Render the filing-grade edition twice, each time supplying one half of every same-number group.

    Within a group the casillas alternate between the two renders, so in each
    render every absent cell shares its number with at least one supplied box,
    and every supplied cell sits beside a differently valued one.
    """
    period = Period.from_year_and_code(request.param, "0A")
    scenario = m200_export_scenario(period)
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(_MODELO, filing_year=period.filing_year, period=period.code).revision
        groups = _shared_number_slots(revision)
        members = sorted({slot[3] for slots in groups.values() for slot in slots})
        values = {casilla: Decimal(100 + index) + Decimal("0.37") for index, casilla in enumerate(members)}
        halves: tuple[set[str], set[str]] = (set(), set())
        for slots in groups.values():
            for index, casilla in enumerate(sorted({slot[3] for slot in slots})):
                halves[index % 2].add(casilla)
        provider = build_runtime_schema_provider(
            operation=operation, modelos=(_MODELO,), filing_year=period.filing_year, period=period
        )
        identity = scenario.product_software_identity_factory
        assert identity is not None

        def render(supplied: set[str]) -> bytes:
            inputs: ModeloInputs = {**scenario.inputs, **{casilla: values[casilla] for casilla in supplied}}
            draft = build_draft(
                modelo=_MODELO,
                period=period,
                profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 reused numbers"),
                inputs=inputs,
                schema_provider=provider,
            ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
            sink = _PayloadSink()
            export_draft(
                draft,
                payload_consumer=sink,
                producer_snapshot=scenario.producer_snapshot(),
                prior_domiciliation_election=scenario.prior_domiciliation_election,
                product_software_identity=identity(),
                schema_provider=provider,
            )
            return sink.payload

        renders = tuple((half, render(half)) for half in halves)
    return groups, values, renders


def _record_tag(revision: ModeloRevision, sheet: str) -> str:
    """Return the literal prefix the layout opens the sheet's record with, e.g. ``<T20042000>``."""
    prefix = f".{sheet.lower()}."
    tags = set()
    for layout in revision.export_layouts:
        for record in layout.records:
            fields = sorted(
                (field for field in record.fields if prefix in str(field.id) and field.offset is not None),
                key=lambda field: field.offset or 0,
            )
            literal = []
            for field in fields:
                if field.kind is not CasillaFieldKind.LITERAL or field.literal is None:
                    break
                literal.append(field.literal)
            if literal:
                tags.add("".join(literal))
    (tag,) = tags
    return tag


def _slot(payload: bytes, tag: str, offset: int, length: int) -> bytes:
    encoded = tag.encode("ascii")
    (record,) = [record for record in payload.split(b"\r\n") if encoded in record]
    assert record.count(encoded) == 1
    # The first substantive record shares its line with the filing envelope.
    start = record.index(encoded) + offset - 1
    return record[start : start + length]


def _wire(amount: Decimal, length: int) -> bytes:
    return str(int(amount * 100)).rjust(length, "0").encode("ascii")


def test_the_render_covers_the_insurer_and_bank_of_spain_equity_cells(rendered_edition) -> None:
    groups, _values, renders = rendered_edition
    covered = {slot[3] for slots in groups.values() for slot in slots}
    assert {
        "DP200042:00547",
        "DP200014:00547",
        "DP200010:00592",
        "DP200011:00599",
        "DP200033:00568",
        "DP200012:00501",
        "DP200032:00501",
        "DP200043:00501",
        "DP200014:00573",
        "DP200042:00573",
    } <= covered
    assert all(half for half, _payload in renders)


@pytest.mark.parametrize("filing_year", _supported_years())
def test_the_new_concepts_follow_the_selected_design(filing_year: int) -> None:
    """Baseline, deltas and projected years match the design selected by temporal authority."""
    concepts = {
        "DP200032:00501",
        "DP200043:00501",
        "DP200042:00573",
        "DP200012:00004",
        "DP200012:00005",
        "DP200012:00006",
        "DP200001:00032",
        "DP200014B:00031",
        "DP200014B:00032",
        "DP200014B:00083",
    }
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )
        revision = snapshot.revision
        design = _design_source(revision)
        printed = {
            (sheet.name.strip(), number)
            for sheet in extract_record_design(bundled_path() / design.corpus_path).require_complete()
            for field in sheet.fields
            for number in _PRINTED_BOX.findall(field.description)
        }
        ids = {str(c.id) for c in revision.casillas}
        for concept in concepts:
            sheet, number = concept.split(":")
            assert (concept in ids) == ((sheet, number) in printed)


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
def test_reused_amount_boxes_follow_the_first_held_design_appearance(revision: ModeloRevision) -> None:
    """Hydrated amount concepts begin exactly where their own official sheet first prints them."""
    design = _design_source(revision)
    sheets = extract_record_design(bundled_path() / design.corpus_path).require_complete()
    casilla_ids = {str(casilla.id) for casilla in revision.casillas}
    amount_boxes = {
        "DP200014B:00032": ("discrepancia de criterio administrativo", "estado"),
        "DP200014B:00083": ("abono deducciones i+d+i por insuficiencia de cuota", "estado"),
    }
    for casilla_id, label_parts in amount_boxes.items():
        sheet_name, number = casilla_id.split(":")
        fields = [
            field
            for sheet in sheets
            if sheet.name.strip() == sheet_name
            for field in sheet.fields
            if number in _PRINTED_BOX.findall(field.description)
        ]
        assert (casilla_id in casilla_ids) == bool(fields), (revision.id, casilla_id)
        assert all(all(part in field.description.casefold() for part in label_parts) for field in fields), (
            revision.id,
            casilla_id,
            [field.description for field in fields],
        )


@pytest.mark.parametrize(
    "revision",
    [r for r in _mapped_revisions() if r.export_layouts and _signed_note_fields(r)],
    ids=lambda r: str(r.id),
)
def test_rectificativa_notes_preserve_signed_cents(revision: ModeloRevision) -> None:
    """The note conditions a monetary amount; it does not turn it into an unsigned integer."""
    with bundled_indexed_authority().operation() as operation:
        published = operation.revision_with_export_layouts(_MODELO, str(revision.id))
        fields = {
            field.offset: field
            for layout in published.export_layouts
            for record in layout.records
            for field in record.fields
            if str(field.id).split(".")[1].upper() == "DP200014B"
        }
        for source_field in _signed_note_fields(revision):
            field = fields[source_field.offset]
            assert field.data_type == "money"
            assert field.signed
            assert field.length == source_field.length


@pytest.mark.parametrize("filing_year", _filing_years())
@pytest.mark.parametrize("supply_adjustments", [False, True])
def test_entity_flags_and_tax_adjustments_export_independently(filing_year: int, supply_adjustments: bool) -> None:
    """A one-byte entity flag cannot populate an unrelated seventeen-byte adjustment."""
    period = Period.from_year_and_code(filing_year, "0A")
    scenario = m200_export_scenario(period)
    numbers = ("00004", "00005", "00006")
    adjustments = {f"DP200012:{number}": Decimal(123 + index) + Decimal("0.45") for index, number in enumerate(numbers)}
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(_MODELO, filing_year=period.filing_year, period=period.code).revision
        provider = build_runtime_schema_provider(
            operation=operation, modelos=(_MODELO,), filing_year=period.filing_year, period=period
        )
        inputs: ModeloInputs = {
            **scenario.inputs,
            **(
                {key: value for key, value in adjustments.items()}
                if supply_adjustments
                else {f"DP200001:{number}": Decimal("1") for number in numbers}
            ),
        }
        draft = build_draft(
            modelo=_MODELO,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 flags and adjustments"),
            inputs=inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        sink = _PayloadSink()
        identity = scenario.product_software_identity_factory
        assert identity is not None
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=scenario.producer_snapshot(),
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=identity(),
            schema_provider=provider,
        )
        fields = {
            str(field.casilla_id): field
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
        }
        for number in numbers:
            for sheet in ("DP200001", "DP200012"):
                cid = f"{sheet}:{number}"
                field = fields[cid]
                assert field.offset is not None and field.length is not None
                expected = (
                    _wire(adjustments[cid], field.length)
                    if sheet == "DP200012" and supply_adjustments
                    else b"1"
                    if sheet == "DP200001" and not supply_adjustments
                    else b"0" * field.length
                )
                assert _slot(sink.payload, _record_tag(revision, sheet), field.offset, field.length) == expected


@pytest.mark.parametrize("filing_year", _filing_years())
@pytest.mark.parametrize(
    ("number", "flag_label", "money_label", "money_type_code", "money_signed", "amount"),
    [
        pytest.param(
            "00031",
            ("entidades", "capital-riesgo"),
            ("discrepancia", "total"),
            "N",
            True,
            Decimal("123.45"),
            id="00031-positive",
        ),
        pytest.param(
            "00031",
            ("entidades", "capital-riesgo"),
            ("discrepancia", "total"),
            "N",
            True,
            Decimal("-123.45"),
            id="00031-negative",
        ),
        pytest.param(
            "00032",
            ("sociedades desarrollo industrial regional",),
            ("discrepancia de criterio administrativo", "estado"),
            "N",
            True,
            Decimal("123.45"),
            id="00032-positive",
        ),
        pytest.param(
            "00032",
            ("sociedades desarrollo industrial regional",),
            ("discrepancia de criterio administrativo", "estado"),
            "N",
            True,
            Decimal("-123.45"),
            id="00032-negative",
        ),
        pytest.param(
            "00083",
            ("tipo gravamen reducido", "empresa emergente"),
            ("abono deducciones i+d+i por insuficiencia de cuota", "estado"),
            "Num",
            False,
            Decimal("123.45"),
            id="00083-positive",
        ),
    ],
)
def test_reused_flag_and_money_export_independently(
    filing_year: int,
    number: str,
    flag_label: tuple[str, ...],
    money_label: tuple[str, ...],
    money_type_code: str,
    money_signed: bool,
    amount: Decimal,
) -> None:
    """Each DP200001 integer character and DP200014B amount keeps its own cell and wire value."""
    period = Period.from_year_and_code(filing_year, "0A")
    scenario = m200_export_scenario(period)
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(_MODELO, filing_year=period.filing_year, period=period.code).revision
        design = _design_source(revision)
        sheets = extract_record_design(bundled_path() / design.corpus_path).require_complete()
        printed_box = [
            (sheet.name.strip(), field)
            for sheet in sheets
            for field in sheet.fields
            if number in _PRINTED_BOX.findall(field.description)
        ]
        (money_design_field,) = [
            field
            for sheet, field in printed_box
            if sheet == "DP200014B" and all(part in field.description.casefold() for part in money_label)
        ]
        (flag_design_field,) = [
            field
            for sheet, field in printed_box
            if sheet == "DP200001" and all(part in field.description.casefold() for part in flag_label)
        ]
        layout_fields = [
            field
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
        ]
        (money_field,) = [
            field
            for field in layout_fields
            if str(field.id).split(".")[1].upper() == "DP200014B" and str(field.casilla_id) == f"DP200014B:{number}"
        ]
        (flag_field,) = [
            field
            for field in layout_fields
            if str(field.id).split(".")[1].upper() == "DP200001" and str(field.casilla_id) == f"DP200001:{number}"
        ]

        assert all(part in money_design_field.description.casefold() for part in money_label)
        assert all(part in flag_design_field.description.casefold() for part in flag_label)
        assert money_design_field.type_code == money_type_code
        assert flag_design_field.type_code == "Num"
        assert money_field.data_type in {CasillaDataType.MONEY, CasillaDataType.DECIMAL}
        if money_field.data_type is CasillaDataType.DECIMAL:
            assert money_field.decimals == 2
        assert money_field.signed is money_signed
        assert flag_field.data_type == "integer" and not flag_field.signed
        assert (money_field.offset, money_field.length) == (
            money_design_field.offset,
            money_design_field.length,
        )
        assert (flag_field.offset, flag_field.length) == (
            flag_design_field.offset,
            flag_design_field.length,
        )

        provider = build_runtime_schema_provider(
            operation=operation,
            modelos=(_MODELO,),
            filing_year=period.filing_year,
            period=period,
        )
        identity = scenario.product_software_identity_factory
        assert identity is not None
        flag_id = f"DP200001:{number}"
        money_id = f"DP200014B:{number}"
        target_ids = {flag_id, money_id}
        base_inputs: ModeloInputs = {key: value for key, value in scenario.inputs.items() if key not in target_ids}

        def render(target_input: tuple[str, Decimal] | None = None) -> bytes:
            inputs = base_inputs
            if target_input is not None:
                casilla_id, value = target_input
                inputs = {**base_inputs, casilla_id: value}
            draft = build_draft(
                modelo=_MODELO,
                period=period,
                profile=ModeloOperatorProfile(
                    tax_id=SYNTHETIC_TAX_ID,
                    display_name=f"Modelo 200 reused box {number}",
                ),
                inputs=inputs,
                schema_provider=provider,
            ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
            sink = _PayloadSink()
            export_draft(
                draft,
                payload_consumer=sink,
                producer_snapshot=scenario.producer_snapshot(),
                prior_domiciliation_election=scenario.prior_domiciliation_election,
                product_software_identity=identity(),
                schema_provider=provider,
            )
            return sink.payload

        flag_only = render((flag_id, Decimal("1")))
        amount_only = render((money_id, amount))
        expected_amount = (
            b"N" + _wire(abs(amount), money_design_field.length - 1)
            if amount < 0
            else _wire(amount, money_design_field.length)
        )

        assert (
            _slot(
                flag_only,
                _record_tag(revision, "DP200014B"),
                money_design_field.offset,
                money_design_field.length,
            )
            == b"0" * money_design_field.length
        )
        assert _slot(
            flag_only,
            _record_tag(revision, "DP200001"),
            flag_design_field.offset,
            flag_design_field.length,
        ) == b"1".rjust(flag_design_field.length, b"0")
        assert (
            _slot(
                amount_only,
                _record_tag(revision, "DP200014B"),
                money_design_field.offset,
                money_design_field.length,
            )
            == expected_amount
        )
        assert (
            _slot(
                amount_only,
                _record_tag(revision, "DP200001"),
                flag_design_field.offset,
                flag_design_field.length,
            )
            == b"0" * flag_design_field.length
        )
        if number == "00083":
            empty = render()
            assert (
                _slot(
                    empty,
                    _record_tag(revision, "DP200014B"),
                    money_design_field.offset,
                    money_design_field.length,
                )
                == b"0" * money_design_field.length
            )
            assert (
                _slot(
                    empty,
                    _record_tag(revision, "DP200001"),
                    flag_design_field.offset,
                    flag_design_field.length,
                )
                == b"0" * flag_design_field.length
            )


def test_an_absent_cell_does_not_borrow_the_box_sharing_its_number(rendered_edition) -> None:
    groups, _values, renders = rendered_edition
    borrowed = [
        (casilla, _slot(payload, tag, offset, length))
        for supplied, payload in renders
        for slots in groups.values()
        for tag, offset, length, casilla in slots
        if casilla not in supplied and _slot(payload, tag, offset, length) != b"0" * length
    ]
    assert borrowed == []


def test_a_supplied_cell_exports_its_own_amount(rendered_edition) -> None:
    groups, values, renders = rendered_edition
    wrong = [
        (casilla, _slot(payload, tag, offset, length))
        for supplied, payload in renders
        for slots in groups.values()
        for tag, offset, length, casilla in slots
        if casilla in supplied and _slot(payload, tag, offset, length) != _wire(values[casilla], length)
    ]
    assert wrong == []
