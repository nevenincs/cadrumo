"""Every Modelo 200 fixed-width layout stands where its own AEAT design puts it, and its bytes read back.

Two independent halves, run for each Modelo 200 revision the registry authors
with a fixed-width export layout (selected by the layout, so no year is named):

Geometry against the design. The design workbook the layout cites
(``source_refs``) is read here from its committed extraction, one sheet per
record ("Nº | Posic. | Lon | ..."). The generator's own provenance is not
consulted. Every design row of every page sheet must be a layout field at the
design's position and length, every layout field must be a design row, and the
records must follow the design's sheet order ("deben respetar el orden de las
páginas indicado", sheet DP200000 of each design).

Bytes against typed values. The canonical Modelo 200 export scenario for the
revision's first supported period renders through the canonical writer, and the
payload is parsed back through the registry fixed-width codec with the same
layout. The records must come back in layout order and each amount the draft
carries must parse back to the same typed value. The writer only serves a
filing-grade snapshot, so a revision whose declared grade is lower is given a
filing reach in an in-memory copy of the authority for this half alone; the
registry's declared grade is neither read as earned nor changed by it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_indexed_authority
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.submission.models import ModeloDraftStatus
from dev.registry.compiler.loader import modelo_fact_scope
from dev.registry.edition_export_scenarios import m200_export_scenario
from dev.registry.edition_round_trip import SYNTHETIC_TAX_ID

from .authored_edition_support import authored_revisions_where
from .filing_reach_support import with_filing_reach

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"

# A layout field id names its design sheet and the sheet's row number ("Nº").
_FIELD_DESIGN_ROW = re.compile(r"\.(?P<sheet>dp200\w+)\.f(?P<ordinal>\d+)$")

_LAYOUT_REVISIONS = tuple(
    str(revision.id)
    for revision in authored_revisions_where(
        _M200,
        lambda revision: any(layout.format is ExportLayoutFormat.FIXED_WIDTH for layout in revision.export_layouts),
    )
)
assert _LAYOUT_REVISIONS, "the registry authors no Modelo 200 revision with a fixed-width layout"


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


def _fixed_width_layout(revision: ModeloRevision) -> ExportLayoutDefinition:
    (layout,) = (layout for layout in revision.export_layouts if layout.format is ExportLayoutFormat.FIXED_WIDTH)
    return layout


def _design_sheets(
    authority: ValidatedRegistryAuthority, layout: ExportLayoutDefinition
) -> dict[str, dict[int, tuple[int, int]]]:
    """Read every sheet of the layout's design: row number -> (position, length), in workbook order."""
    (source_ref,) = layout.source_refs
    source = authority.catalogues.sources[source_ref]
    extraction = bundled_path(*f"{source.corpus_path}.extracted.json".split("/"))
    units = json.loads(extraction.read_text(encoding="utf-8"))["units"]
    sheets: dict[str, dict[int, tuple[int, int]]] = {}
    for unit in units:
        rows: dict[int, tuple[int, int]] = {}
        for line in unit["text"].splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) >= 3 and all(cell.isdigit() for cell in cells[:3]):
                rows[int(cells[0])] = (int(cells[1]), int(cells[2]))
        sheets[unit["title"].strip()] = rows
    return sheets


@pytest.mark.parametrize("revision_id", _LAYOUT_REVISIONS)
def test_modelo_200_layout_matches_its_design_geometry_and_page_order(registry_authority, revision_id: str) -> None:
    layout = _fixed_width_layout(registry_authority.modelo(_M200).revisions[revision_id])
    sheets = _design_sheets(registry_authority, layout)
    envelope_sheet = layout.filing_envelope.record_identity if layout.filing_envelope is not None else None
    page_sheets = [sheet for sheet in sheets if sheet != envelope_sheet]

    record_sheets: list[str] = []
    layout_rows: set[tuple[str, int]] = set()
    for record in sorted(layout.records, key=lambda record: record.order):
        sheets_of_record = set()
        for field in record.fields:
            match = _FIELD_DESIGN_ROW.search(str(field.id))
            assert match is not None, f"{field.id} names no design row"
            sheet, ordinal = match["sheet"].upper(), int(match["ordinal"])
            assert sheets[sheet][ordinal] == (field.offset, field.length), (
                f"{field.id}: layout ({field.offset}, {field.length}) vs design {sheets[sheet][ordinal]}"
            )
            sheets_of_record.add(sheet)
            layout_rows.add((sheet, ordinal))
        (record_sheet,) = sheets_of_record
        if not record_sheets or record_sheets[-1] != record_sheet:
            record_sheets.append(record_sheet)

    assert record_sheets == page_sheets
    assert layout_rows == {(sheet, ordinal) for sheet in page_sheets for ordinal in sheets[sheet]}


def _first_supported_annual_period(authority: ValidatedRegistryAuthority, revision: ModeloRevision) -> Period:
    envelope = authority.supported_filing_years()
    year = next(year for year in envelope.years if revision.period_selector.includes_year(year))
    (period,) = tuple(str(token) for token in revision.period_selector.periods_for_year(year))
    return Period.from_year_and_code(year, period)


class _PayloadSink:
    """Keeps the validated payload in memory; no plaintext export touches disk."""

    payload: bytes = b""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _render(
    authority: ValidatedRegistryAuthority, revision_id: str
) -> tuple[bytes, ModeloDraft, Mapping[str, object], Mapping[str, bytes]]:
    period = _first_supported_annual_period(authority, authority.modelo(_M200).revisions[revision_id])
    scenario = m200_export_scenario(period)
    staged = with_filing_reach(authority, _M200, revision_id)
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", _M200)), validating_governed_facts(staged):
        provider = schema_provider_from_authority(
            staged, modelos=(_M200,), filing_year=period.filing_year, period=period
        )
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 design round trip"),
            inputs=scenario.inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        assert str(draft.snapshot_ref.revision_id) == revision_id
        sink = _PayloadSink()
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=scenario.producer_snapshot(),
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=scenario.product_software_identity_factory(),
            schema_provider=provider,
        )
    return sink.payload, draft, provider.sources, provider.source_payloads


@pytest.mark.parametrize("revision_id", _LAYOUT_REVISIONS)
def test_modelo_200_export_parses_back_to_its_typed_values(registry_authority, revision_id: str) -> None:
    layout = _fixed_width_layout(registry_authority.modelo(_M200).revisions[revision_id])
    payload, draft, sources, source_payloads = _render(registry_authority, revision_id)

    parsed = parse_export_payload(layout, payload, sources=sources, source_payloads=source_payloads)

    record_order = {record.id: record.order for record in layout.records}
    parsed_orders = [record_order[value.record_id] for value in parsed.fields]
    assert parsed_orders == sorted(parsed_orders)
    assert {value.record_id for value in parsed.fields} >= {record.id for record in layout.records if record.required}

    parsed_by_casilla = {value.casilla_id: value.value for value in parsed.casillas if value.casilla_id is not None}
    stated = {value.casilla_id: value.value for value in draft.values if isinstance(value.value, Decimal)}
    compared = {casilla_id for casilla_id in stated if casilla_id in parsed_by_casilla}
    assert any(stated[casilla_id] != 0 for casilla_id in compared), "the scenario must carry a nonzero exported amount"
    for casilla_id in compared:
        assert parsed_by_casilla[casilla_id] == stated[casilla_id], casilla_id
