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
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.application.filing.draft_construction import (
    build_draft,
    draft_input_channels,
    filing_period_date,
    load_registry_snapshot,
)
from cadrumo.application.filing.errors import ModeloApplicationError
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.filing.protocols import CasillaSchemaProvider, ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import modelo_fact_scope
from ..compiler.record_design import extract_record_design
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS
from ..edition_export_scenarios import m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID, EditionExportScenario
from ..pipeline.semantic_map import SemanticMap, load_semantic_map
from .authored_edition_support import authored_revisions
from .filing_reach_support import with_filing_reach

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_MAPPINGS = Path("dev/registry/mappings/modelo_200")
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")
_TIPO_GRAVAMEN: CasillaId = validated_casilla_id("DP200014:00558", surface="M200 tipo de gravamen")
# Caracteres de la declaración whose régimen this registry does not author, so a
# declaration marking one has no tipo de gravamen and refuses: the 1 per cent
# instituciones (00004) and the empresa emergente (00083).
_REFUSED_REGIME_FLAGS = frozenset({"DP200001:00004", "DP200001:00083"})

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


def _selected_revision(filing_year: int) -> ModeloRevision:
    """The edition the registry selects for a year, read at the lowest grade so no grade gate decides it."""
    return (
        compiled_bundled_authority()
        .snapshot(_MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
        .revision
    )


def _export_years() -> tuple[int, ...]:
    """The supported years whose selected edition carries an export layout, whatever grade it declares."""
    return tuple(year for year in _supported_years() if _selected_revision(year).export_layouts)


_EXPORT_YEARS = _export_years()
assert _EXPORT_YEARS, "no supported year selects an edition with an export layout, so the export checks prove nothing"


@contextmanager
def _writer_scope(period: Period) -> Iterator[tuple[ModeloRevision, CasillaSchemaProvider]]:
    """Yield the edition selected for ``period`` and a schema provider the export writer accepts.

    The writer serves filing-grade snapshots only, and no Modelo 200 edition
    declares filing grade, so these checks of which box a value lands in lift the
    selected edition to filing reach in an in-memory copy of the authority, for
    the export alone. The registry's declared grade is neither read as earned
    nor changed: a real export at this grade still refuses.
    """
    authority = compiled_bundled_authority()
    revision_id = str(_selected_revision(period.filing_year).id)
    staged = with_filing_reach(authority, _MODELO, revision_id)
    with (
        modelo_fact_scope(bundled_path("registry", "aeat", "modelos", _MODELO)),
        validating_governed_facts(staged),
    ):
        revision = staged.snapshot(_MODELO, filing_year=period.filing_year, period=period.code).revision
        assert str(revision.id) == revision_id
        provider = schema_provider_from_authority(
            staged, modelos=(_MODELO,), filing_year=period.filing_year, period=period
        )
        yield revision, provider


def test_every_edition_with_an_export_layout_has_a_semantic_map() -> None:
    mapped = {str(revision.id) for revision in _mapped_revisions()}
    exporting = {str(revision.id) for revision in authored_revisions(_MODELO) if revision.export_layouts}
    assert exporting, "no edition exports, so this check proves nothing"
    assert exporting <= mapped


@pytest.mark.parametrize("revision", _mapped_revisions(), ids=lambda revision: str(revision.id))
def test_every_cross_sheet_mapping_is_a_declared_echo(revision: ModeloRevision) -> None:
    semantic_map = _semantic_map(str(_design_source(revision).record_design_epoch))
    expected = MODELO_200_ECHO_CELLS
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
        (casilla.segmento, str(casilla.number)): str(casilla.id)
        for casilla in revision.casillas
        if (casilla.segmento is not None and casilla.segmento)
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
    revision = _selected_revision(max(_EXPORT_YEARS))
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

    assert set(found) - MODELO_200_ECHO_CELLS == {("DP200042", "DP200014:00547")}
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

    assert set(found) - MODELO_200_ECHO_CELLS == {("DP200014B", "DP200001:00031")}
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
            (casilla.segmento is not None and casilla.segmento)
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


@pytest.fixture(scope="module", params=_EXPORT_YEARS)
def rendered_edition(request: pytest.FixtureRequest):
    """Render the exporting edition twice, each time supplying one half of every same-number group.

    Within a group the casillas alternate between the two renders, so in each
    render every absent cell shares its number with at least one supplied box,
    and every supplied cell sits beside a differently valued one.
    """
    period = Period.from_year_and_code(request.param, "0A")
    scenario = m200_export_scenario(period)
    with _writer_scope(period) as (revision, provider):
        groups = _shared_number_slots(revision)
        members = sorted({slot[3] for slots in groups.values() for slot in slots})
        values = {casilla: Decimal(100 + index) + Decimal("0.37") for index, casilla in enumerate(members)}
        halves: tuple[set[str], set[str]] = (set(), set())
        for slots in groups.values():
            for index, casilla in enumerate(sorted({slot[3] for slot in slots})):
                halves[index % 2].add(casilla)
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
        "DP200008:00301",
        "DP200008:00302",
        "DP200008:00303",
        "DP200008:00304",
        "DP200012:00301",
        "DP200012:00302",
        "DP200012:00303",
        "DP200012:00304",
        "DP200033:00301",
        "DP200033:00302",
        "DP200033:00303",
        "DP200033:00304",
        "DP200039:00301",
        "DP200039:00302",
        "DP200039:00303",
        "DP200039:00304",
        "DP200048:00301",
        "DP200048:00302",
        "DP200048:00303",
        "DP200053:00301",
        "DP200053:00302",
        "DP200054:00303",
        "DP200054:00304",
        "DP200008:00305",
        "DP200008:00306",
        "DP200008:00307",
        "DP200008:00308",
        "DP200012:00305",
        "DP200012:00306",
        "DP200012:00307",
        "DP200012:00308",
        "DP200032:00305",
        "DP200032:00306",
        "DP200032:00307",
        "DP200032:00308",
        "DP200039:00305",
        "DP200039:00306",
        "DP200039:00307",
        "DP200039:00308",
        "DP200053:00307",
        "DP200053:00308",
        "DP200054:00305",
        "DP200054:00306",
        "DP200008:00309",
        "DP200008:00310",
        "DP200008:00311",
        "DP200008:00312",
        "DP200008:00313",
        "DP200008:00314",
        "DP200008:00315",
        "DP200008:00316",
        "DP200012:00309",
        "DP200012:00310",
        "DP200013:00311",
        "DP200013:00312",
        "DP200013:00313",
        "DP200013:00314",
        "DP200018:00315",
        "DP200018:00316",
        "DP200018B:00315",
        "DP200018B:00316",
        "DP200032:00309",
        "DP200032:00310",
        "DP200033:00311",
        "DP200033:00312",
        "DP200033:00313",
        "DP200033:00314",
        "DP200033:00315",
        "DP200033:00316",
        "DP200039:00309",
        "DP200039:00310",
        "DP200039:00311",
        "DP200039:00312",
        "DP200039:00313",
        "DP200039:00314",
        "DP200039:00315",
        "DP200039:00316",
        "DP200053:00309",
        "DP200053:00310",
        "DP200053:00311",
        "DP200054:00312",
        "DP200054:00313",
        "DP200054:00314",
        "DP200054:00315",
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


@pytest.mark.parametrize("filing_year", _supported_years())
def test_aggregate_free_amortization_keeps_the_designs_da17_scope(filing_year: int) -> None:
    """The aggregate adds DA17 where its official caption cites the paired dispositions."""
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        ).revision
        source = _design_source(revision)
        (sheet,) = [
            sheet
            for sheet in extract_record_design(bundled_path() / source.corpus_path).require_complete()
            if sheet.name.strip() == "DP200012"
        ]
        casillas = _casillas(revision)
        for number in ("00309", "00310"):
            (field,) = [field for field in sheet.fields if number in _PRINTED_BOX.findall(field.description)]
            refs = set(map(str, casillas[f"DP200012:{number}"].legal_refs))
            assert {"ley-27-2014:art-12-3-a", "ley-27-2014:art-12-3-d", "ley-27-2014:da-16"} <= refs
            assert ("ley-27-2014:da-17" in refs) == ("17ª" in field.description)


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


@pytest.mark.parametrize("filing_year", _EXPORT_YEARS)
@pytest.mark.parametrize("supply_adjustments", [False, True])
def test_entity_flags_and_tax_adjustments_export_independently(filing_year: int, supply_adjustments: bool) -> None:
    """A one-byte entity flag cannot populate an unrelated seventeen-byte adjustment."""
    period = Period.from_year_and_code(filing_year, "0A")
    scenario = m200_export_scenario(period)
    numbers = ("00004", "00005", "00006")
    adjustments = {f"DP200012:{number}": Decimal(123 + index) + Decimal("0.45") for index, number in enumerate(numbers)}
    with _writer_scope(period) as (revision, provider):
        marked = {f"DP200001:{number}" for number in numbers} - _REFUSED_REGIME_FLAGS
        for flag_id in sorted({f"DP200001:{number}" for number in numbers} & _REFUSED_REGIME_FLAGS):
            _assert_marked_regime_refuses(provider, period, scenario, flag_id)
            _assert_flag_cell_stands_alone(revision, flag_id, f"DP200012:{flag_id.split(':')[1]}")
        inputs: ModeloInputs = {
            **scenario.inputs,
            **(
                {key: value for key, value in adjustments.items()}
                if supply_adjustments
                else dict.fromkeys(marked, Decimal("1"))
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
                    if cid in marked and not supply_adjustments
                    else b"0" * field.length
                )
                assert _slot(sink.payload, _record_tag(revision, sheet), field.offset, field.length) == expected


def _export(
    provider: CasillaSchemaProvider, period: Period, scenario: EditionExportScenario, inputs: ModeloInputs
) -> bytes:
    """Calculate a draft from ``inputs`` and return the payload its export writes."""
    identity = scenario.product_software_identity_factory
    assert identity is not None
    draft = build_draft(
        modelo=_MODELO,
        period=period,
        profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 reused box"),
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


def _assert_marked_regime_refuses(
    provider: CasillaSchemaProvider, period: Period, scenario: EditionExportScenario, flag_id: str
) -> None:
    """Marking an unauthored régimen leaves 00558 under its typed reason, and the export refuses."""
    inputs: ModeloInputs = {**scenario.inputs, flag_id: Decimal("1")}
    snapshot = load_registry_snapshot(modelo=_MODELO, period=period, schema_provider=provider)
    channels = draft_input_channels(snapshot, inputs)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=channels.casilla_inputs,
        date_context={"filing_period": filing_period_date(period)},
        binding_values=channels.binding_inputs,
        enum_binding_values=channels.enum_binding_inputs or None,
        relation_values=channels.relation_inputs or None,
        date_binding_values=channels.date_binding_inputs or None,
        boolean_binding_values=channels.boolean_binding_inputs or None,
        text_inputs=channels.text_casilla_inputs or None,
    )
    reasons = {outcome.casilla_id: outcome.reason for outcome in result.unresolved_outcomes}
    assert reasons.get(_TIPO_GRAVAMEN) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED
    with pytest.raises(ModeloApplicationError) as refused:
        _export(provider, period, scenario, inputs)
    assert refused.value.translated_message == "application.filing.export_parity.errors.required_casillas_omitted"
    context = refused.value.context
    assert context is not None
    missing = {str(item["casilla_id"]) for item in context["missing_casillas"]}
    assert str(_TIPO_GRAVAMEN) in missing


def _layout_field_and_record(revision: ModeloRevision, casilla_id: str):
    """Return the one export-layout field bound to ``casilla_id`` and the record that holds it."""
    (found,) = [
        (field, record)
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and str(field.casilla_id) == casilla_id
    ]
    return found


def _assert_flag_cell_stands_alone(revision: ModeloRevision, flag_id: str, amount_id: str) -> None:
    """A marked flag writes its own cell; the amount sharing its printed number stays at its absent slot.

    This proves the two concepts at the export-cell level for a régimen whose
    full calculated export refuses: the cells sit in different records, the
    flag renders the mark it is given and the amount, given nothing, renders
    the zeros a full export writes for it.
    """
    flag_field, flag_record = _layout_field_and_record(revision, flag_id)
    amount_field, amount_record = _layout_field_and_record(revision, amount_id)
    assert flag_record.id != amount_record.id
    assert flag_field.length is not None and amount_field.length is not None
    flag = render_fixed_width_export_field(flag_field, Decimal("1"), record=flag_record).encode(flag_record.encoding)
    amount = render_fixed_width_export_field(amount_field, None, record=amount_record).encode(amount_record.encoding)
    assert flag == b"1".rjust(flag_field.length, b"0")
    assert amount == b"0" * amount_field.length


def _printed_box_design_fields(revision: ModeloRevision, number: str, money_label, flag_label):
    """Return the DP200014B amount and DP200001 flag design fields printed under one box number."""
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
    return money_design_field, flag_design_field


def _layout_box_fields(revision: ModeloRevision, number: str):
    """Return the export-layout amount and flag fields declared for one reused box number."""
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
    return money_field, flag_field


def _assert_box_fields_match_the_design(
    money_field,
    flag_field,
    money_design_field,
    flag_design_field,
    *,
    money_label: tuple[str, ...],
    flag_label: tuple[str, ...],
    money_type_code: str,
    money_signed: bool,
) -> None:
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


def _reused_box_renderer(provider: CasillaSchemaProvider, period: Period, scenario: EditionExportScenario, number: str):
    """Return a renderer that exports the scenario with only the given reused-box inputs supplied."""
    identity = scenario.product_software_identity_factory
    assert identity is not None
    target_ids = {f"DP200001:{number}", f"DP200014B:{number}"}
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

    return render


def _assert_money_and_flag_slots(
    payload: bytes,
    revision: ModeloRevision,
    money_design_field,
    flag_design_field,
    *,
    money: bytes,
    flag: bytes,
) -> None:
    assert (
        _slot(
            payload,
            _record_tag(revision, "DP200014B"),
            money_design_field.offset,
            money_design_field.length,
        )
        == money
    )
    assert (
        _slot(
            payload,
            _record_tag(revision, "DP200001"),
            flag_design_field.offset,
            flag_design_field.length,
        )
        == flag
    )


@pytest.mark.parametrize("filing_year", _EXPORT_YEARS)
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
    with _writer_scope(period) as (revision, provider):
        money_design_field, flag_design_field = _printed_box_design_fields(revision, number, money_label, flag_label)
        money_field, flag_field = _layout_box_fields(revision, number)
        _assert_box_fields_match_the_design(
            money_field,
            flag_field,
            money_design_field,
            flag_design_field,
            money_label=money_label,
            flag_label=flag_label,
            money_type_code=money_type_code,
            money_signed=money_signed,
        )
        render = _reused_box_renderer(provider, period, scenario, number)
        amount_only = render((f"DP200014B:{number}", amount))
        expected_amount = (
            b"N" + _wire(abs(amount), money_design_field.length - 1)
            if amount < 0
            else _wire(amount, money_design_field.length)
        )
        zero_money = b"0" * money_design_field.length
        zero_flag = b"0" * flag_design_field.length
        flag_id = f"DP200001:{number}"
        if flag_id in _REFUSED_REGIME_FLAGS:
            _assert_marked_regime_refuses(provider, period, scenario, flag_id)
            _assert_flag_cell_stands_alone(revision, flag_id, f"DP200014B:{number}")
        else:
            _assert_money_and_flag_slots(
                render((flag_id, Decimal("1"))),
                revision,
                money_design_field,
                flag_design_field,
                money=zero_money,
                flag=b"1".rjust(flag_design_field.length, b"0"),
            )
        _assert_money_and_flag_slots(
            amount_only,
            revision,
            money_design_field,
            flag_design_field,
            money=expected_amount,
            flag=zero_flag,
        )
        if number == "00083":
            _assert_money_and_flag_slots(
                render(),
                revision,
                money_design_field,
                flag_design_field,
                money=zero_money,
                flag=zero_flag,
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
