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
exports its own value when supplied and the design's zero fill when not.
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
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compile_validated_authority, compiled_bundled_authority
from ..compiler.loader import modelo_fact_scope
from ..compiler.record_design import extract_record_design
from ..edition_export_scenarios import M200_SCENARIO_PERIODS, m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID
from ..pipeline.semantic_map import SemanticMap, load_semantic_map
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_MAPPINGS = Path("dev/registry/mappings/modelo_200")
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")

type Cell = tuple[str, str]
"""A mapped cell as (record sheet, casilla id it is mapped to)."""

# Cells that print another sheet's box number because they repeat that box's
# amount. Each design line names the echo itself: a detail sheet's total
# "aplicado en esta liquidación" (or "importe aplicado", "reducción B.I.
# aplicada", "importe adicionado"), the nivelación detail's current-generation minoración, the DID summary's
# "Liquidación - Base imponible / Cuota íntegra", and the AIE/UTE datos
# económicos base imponible before and after nivelación.
_ECHOES: frozenset[Cell] = frozenset(
    {
        ("DP200015", "DP200014:00547"),
        ("DP200015B", "DP200014:00570"),
        ("DP200015B", "DP200014:00572"),
        ("DP200015B", "01280"),
        ("DP200015B", "01344"),
        ("DP200016", "DP200014:00571"),
        ("DP200016", "00573"),
        ("DP200016", "DP200014B:00584"),
        ("DP200016", "DP200014B:00585"),
        ("DP200016B", "DP200014B:00590"),
        ("DP200018B", "01039"),
        ("DP200018B", "02314"),
        ("DP200018B", "02315"),
        ("DP200018C", "DP200014B:00565"),
        ("DP200019", "DP200014B:00082"),
        ("DP200019", "01040"),
        ("DP200019", "01041"),
        ("DP200020B", "DP200013:00417"),
        ("DP200020B", "DP200013:00418"),
        ("DP200020B", "01032"),
        ("DP200020B", "DP200014:01033"),
        ("DP200020B", "DP200014:01034"),
        ("DP200024", "DP200014:00552"),
        ("DP200024", "DP200014:01330"),
        ("DP200DID", "DP200014:00552"),
        ("DP200DID", "DP200014:00562"),
    }
)

# Cells that still carry another sheet's concept. Each needs its own casilla, but
# the box it would share a number with is declared under the bare id ``00501``
# (DP200012 resultado contable) or ``00573`` (DP200014 doble imposición
# internacional), and the registry refuses a second casilla with that number
# while the bare id stands. Declaring them waits on those ids becoming
# segment-qualified. Listed so the gap stays visible and the list fails the
# moment either id is qualified and the cells are declared.
_AWAITING_SEGMENT_QUALIFIED_IDS: frozenset[Cell] = frozenset(
    {
        ("DP200032", "00501"),
        ("DP200043", "00501"),
        ("DP200042", "00573"),
    }
)


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


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
def test_every_cross_sheet_mapping_is_a_declared_echo(revision: ModeloRevision) -> None:
    semantic_map = _semantic_map(str(_design_source(revision).record_design_epoch))
    expected = _ECHOES | _AWAITING_SEGMENT_QUALIFIED_IDS
    assert set(foreign_sheet_cells(_semantic_map_cells(semantic_map), _casillas(revision))) == expected
    if revision.export_layouts:
        assert set(foreign_sheet_cells(_layout_cells(revision), _casillas(revision))) == expected


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
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
    (revision,) = [revision for revision in authored_revisions(_MODELO) if revision.export_layouts]
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

    assert set(found) - _ECHOES - _AWAITING_SEGMENT_QUALIFIED_IDS == {("DP200042", "DP200014:00547")}
    assert found[("DP200042", "DP200014:00547")] == [str(entry.export_field_id)]


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


@pytest.fixture(scope="module")
def rendered_edition():
    """Render the filing-grade edition twice, each time supplying one half of every same-number group.

    Within a group the casillas alternate between the two renders, so in each
    render every absent cell shares its number with at least one supplied box,
    and every supplied cell sits beside a differently valued one.
    """
    period = M200_SCENARIO_PERIODS["2025-y-siguientes"]
    scenario = m200_export_scenario(period)
    registry_root = bundled_path("registry", "aeat")
    with modelo_fact_scope(registry_root / "modelos" / _MODELO):
        authority = compile_validated_authority(registry_root, bundled_path())
        with validating_governed_facts(authority):
            revision = authority.modelo(_MODELO).revisions["2025-y-siguientes"]
            groups = _shared_number_slots(revision)
            members = sorted({slot[3] for slots in groups.values() for slot in slots})
            values = {casilla: Decimal(100 + index) + Decimal("0.37") for index, casilla in enumerate(members)}
            halves: tuple[set[str], set[str]] = (set(), set())
            for slots in groups.values():
                for index, casilla in enumerate(sorted({slot[3] for slot in slots})):
                    halves[index % 2].add(casilla)
            provider = schema_provider_from_authority(
                authority, modelos=(_MODELO,), filing_year=period.filing_year, period=period
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
    (record,) = [record for record in payload.split(b"\r\n") if record.startswith(tag.encode("ascii"))]
    return record[offset - 1 : offset - 1 + length]


def _wire(amount: Decimal, length: int) -> bytes:
    return str(int(amount * 100)).rjust(length, "0").encode("ascii")


def test_the_render_covers_the_insurer_and_bank_of_spain_equity_cells(rendered_edition) -> None:
    groups, _values, renders = rendered_edition
    covered = {slot[3] for slots in groups.values() for slot in slots}
    assert {"DP200042:00547", "DP200014:00547", "DP200010:00592", "DP200011:00599", "DP200033:00568"} <= covered
    assert all(half for half, _payload in renders)


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
