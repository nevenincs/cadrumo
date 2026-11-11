"""An export never writes one casilla's value into cells of unconfirmed meaning.

Each cell reads its value by casilla id, so a box mapped to several cells puts
one figure into all of them. These tests run the real ``build_draft`` then
``export_draft`` path: the design's expected cells and wire bytes are stated here
rather than derived from the rule under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft, render_export_layout
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.export_shared_owner import (
    canonical_export_layout,
    unadjudicated_shared_owners,
    written_unadjudicated_shared_owners,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..analysis.m200_target_identity_worklist import load_bundled_m200_target_identity_worklists
from ..compiler.authority import compiled_bundled_authority
from ..edition_export_scenarios import edition_export_scenarios, m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID, EditionExportScenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"
_REFUSAL = "application.filing.export.errors.shared_casilla_cells_unadjudicated"
_TRIBUTOS_SHEETS = {"DP200007", "DP200022", "DP200031", "DP200038", "DP200047", "DP200053"}

# Repeats in revisions declaring no segment, each read against the official
# design: Modelo 390's section 8 reprints section 7's boxes [658], [84] and [659],
# and from the ejercicio-2026 design also [112],
# under the same captions, Modelo 349's operator and rectification records carry
# one substitute party, and Modelo 309's devengo period is its header period.
_SINGLE_SEGMENT_REPEATS: frozenset[tuple[str, str]] = frozenset(
    {
        ("309", "decl.periodo"),
        ("349", "sustituto.apellidos-razon-social"),
        ("349", "sustituto.nif"),
        ("390", "iva.anual.iva-importacion-diferimiento"),
        ("390", "iva.anual.pago-cuenta-carburantes-deposito-fiscal"),
        ("390", "iva.anual.regularizacion-cuotas-art-80-cinco-5"),
        ("390", "iva.anual.suma-resultados"),
    }
)


class _PayloadSink:
    """Keeps a validated payload in memory, recording whether anything was delivered."""

    payload: bytes | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _m200_filing_years() -> tuple[int, ...]:
    authority = compiled_bundled_authority()
    return tuple(
        year
        for year in authority.supported_filing_years().years
        if authority.snapshot(
            _M200, filing_year=year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        ).revision.authority_grade
        is RegistryAuthorityGrade.FILING
    )


@dataclass(frozen=True, slots=True)
class _Rendering:
    payload: bytes
    revision: ModeloRevision


def _export(
    modelo: str,
    scenario: EditionExportScenario,
    supplied: ModeloInputs,
    *,
    output_path: Path | None = None,
    sink: _PayloadSink | None = None,
) -> _Rendering:
    """Run the real path, raising whatever the export refuses with."""
    period = scenario.period
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(modelo, filing_year=period.filing_year, period=period.code).revision
        provider = build_runtime_schema_provider(
            operation=operation, modelos=(modelo,), filing_year=period.filing_year, period=period
        )
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Shared cells"),
            inputs={**scenario.inputs, **supplied},
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        identity = scenario.product_software_identity_factory
        software = None if identity is None else identity()
        if output_path is not None:
            export_draft(
                draft,
                output_path=output_path,
                producer_snapshot=scenario.producer_snapshot(),
                prior_domiciliation_election=scenario.prior_domiciliation_election,
                product_software_identity=software,
                schema_provider=provider,
            )
            return _Rendering(output_path.read_bytes(), revision)
        delivered = sink if sink is not None else _PayloadSink()
        export_draft(
            draft,
            payload_consumer=delivered,
            producer_snapshot=scenario.producer_snapshot(),
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=software,
            schema_provider=provider,
        )
    assert delivered.payload is not None
    return _Rendering(delivered.payload, revision)


def _m200_scenario(year: int) -> EditionExportScenario:
    return m200_export_scenario(Period.from_year_and_code(year, "0A"))


def _sheet(cell_id: str) -> str:
    return cell_id.split(".")[1].upper()


def _cells(revision: ModeloRevision, casilla_id: str) -> tuple[ExportFieldDefinition, ...]:
    return tuple(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and str(field.casilla_id) == casilla_id
    )


def _slot(payload: bytes, revision: ModeloRevision, cell: ExportFieldDefinition) -> bytes:
    """Read one cell's bytes out of the record line its sheet's opening tag identifies."""
    sheet = f".{_sheet(str(cell.id)).lower()}."
    assert cell.offset is not None and cell.length is not None
    tags = set()
    for layout in revision.export_layouts:
        for record in layout.records:
            fields = sorted(
                (field for field in record.fields if sheet in str(field.id) and field.offset is not None),
                key=lambda field: field.offset or 0,
            )
            literal: list[str] = []
            for field in fields:
                if field.kind is not CasillaFieldKind.LITERAL or field.literal is None:
                    break
                literal.append(field.literal)
            if literal:
                tags.add("".join(literal))
    (tag,) = tags
    encoded = tag.encode("ascii")
    (line,) = [line for line in payload.split(b"\r\n") if encoded in line]
    start = line.index(encoded) + cell.offset - 1
    return line[start : start + cell.length]


def _refusal(year: int, supplied: ModeloInputs) -> FilingExportValidationError:
    with pytest.raises(FilingExportValidationError) as caught:
        _export(_M200, _m200_scenario(year), supplied)
    assert caught.value.translated_message == _REFUSAL
    return caught.value


@pytest.mark.parametrize("year", _m200_filing_years())
def test_tributos_is_refused_naming_its_six_sheets_and_nothing_is_delivered(year: int) -> None:
    sink = _PayloadSink()
    with pytest.raises(FilingExportValidationError) as caught:
        _export(_M200, _m200_scenario(year), {"00281": Decimal("123.45")}, sink=sink)

    assert sink.payload is None
    assert caught.value.translated_message == _REFUSAL
    context = caught.value.context
    assert context is not None
    assert context["casilla_ids"] == "00281"
    target_cells = context["target_cells"]
    assert isinstance(target_cells, dict)
    assert {_sheet(cell) for cell in target_cells["00281"]} == _TRIBUTOS_SHEETS
    assert context["modelo"] == _M200


def test_a_dictionary_layout_holding_a_shared_box_is_refused_like_a_fixed_width_one() -> None:
    """No bundled dictionary layout declares records today, so one is planted to prove the branch still asks."""
    year = _m200_filing_years()[-1]
    period = Period.from_year_and_code(year, "0A")
    scenario = _m200_scenario(year)
    with bundled_indexed_authority().operation() as operation:
        provider = build_runtime_schema_provider(filing_year=year, period=period, modelos=(_M200,), operation=operation)
        registry_snapshot = provider.get_snapshot(_M200)
        planted = canonical_export_layout(registry_snapshot.revision.export_layouts)
        assert planted is not None
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Shared cells"),
            inputs={**scenario.inputs, "00281": Decimal("123.45")},
            schema_provider=provider,
        )
        with pytest.raises(FilingExportValidationError) as caught:
            render_export_layout(
                planted.model_copy(update={"format": ExportLayoutFormat.XML_DICTIONARY}),
                draft=draft,
                headers={},
                producer_snapshot=scenario.producer_snapshot(),
                dictionary_values=None,
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                product_software_identity=None,
                xml_aux_version="planted",
                schema_provider=provider,
                registry_snapshot=registry_snapshot,
            )

    assert caught.value.translated_message == _REFUSAL
    assert (caught.value.context or {})["casilla_ids"] == "00281"


@pytest.mark.parametrize("year", _m200_filing_years())
def test_a_refused_export_leaves_no_file(year: int, tmp_path: Path) -> None:
    output = tmp_path / "refused.boe"
    with pytest.raises(FilingExportValidationError) as caught:
        _export(_M200, _m200_scenario(year), {"00281": Decimal("123.45")}, output_path=output)
    assert caught.value.translated_message == _REFUSAL
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("year", _m200_filing_years())
def test_the_socimi_flag_is_refused_naming_the_reserve_deduction_cell(year: int) -> None:
    refusal = _refusal(year, {"00012": Decimal("1")})

    context = refusal.context
    assert context is not None
    target_cells = context["target_cells"]
    assert isinstance(target_cells, dict)
    assert {"DP200001", "DP200022"} <= {_sheet(cell) for cell in target_cells["00012"]}


@pytest.mark.parametrize("year", _m200_filing_years())
def test_every_written_box_is_named_at_once(year: int) -> None:
    refusal = _refusal(year, {"00281": Decimal("123.45"), "00012": Decimal("1")})

    context = refusal.context
    assert context is not None
    target_cells = context["target_cells"]
    assert isinstance(target_cells, dict)
    assert set(target_cells) == {"00281", "00012"}


@pytest.mark.parametrize("year", _m200_filing_years())
def test_a_declared_echo_writes_its_amount_into_both_its_cells(year: int) -> None:
    """DP200015's "aplicado en esta liquidación" total repeats the liquidación box it feeds."""
    rendered = _export(_M200, _m200_scenario(year), {"DP200014:00547": Decimal("123.45")})

    cells = _cells(rendered.revision, "DP200014:00547")
    assert {_sheet(str(cell.id)) for cell in cells} == {"DP200014", "DP200015"}
    for cell in cells:
        assert cell.length is not None
        assert _slot(rendered.payload, rendered.revision, cell) == b"12345".rjust(cell.length, b"0")


@pytest.mark.parametrize("year", _m200_filing_years())
def test_a_box_with_one_cell_exports_its_value(year: int) -> None:
    rendered = _export(_M200, _m200_scenario(year), {"DP200012:00004": Decimal("123.45")})

    (cell,) = _cells(rendered.revision, "DP200012:00004")
    assert cell.length is not None
    assert _slot(rendered.payload, rendered.revision, cell) == b"12345".rjust(cell.length, b"0")


@pytest.mark.parametrize("year", _m200_filing_years())
@pytest.mark.parametrize(
    ("casilla_id", "zero"),
    [
        pytest.param("00281", Decimal("0"), id="money-zero"),
        pytest.param("00281", Decimal("0.00"), id="money-zero-scale"),
        pytest.param("00012", Decimal("0"), id="flag-unselected"),
    ],
)
def test_a_zero_is_byte_identical_to_the_box_never_being_supplied(year: int, casilla_id: str, zero: Decimal) -> None:
    absent = _export(_M200, _m200_scenario(year), {})
    supplied = _export(_M200, _m200_scenario(year), {casilla_id: zero})

    assert supplied.payload == absent.payload


@pytest.mark.parametrize("year", _m200_filing_years())
def test_a_zero_in_every_rate_and_flag_owner_matches_absence_in_every_cell(year: int) -> None:
    """The zero rule is proved over the shared owners' real cell shapes, not assumed per kind."""
    revision = compiled_bundled_authority().snapshot(_M200, filing_year=year, period="0A").revision
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    owners = unadjudicated_shared_owners(layout, revision.casillas)
    shapes = {cell.data_type for owner in owners for cell in owner.target_cells}
    assert {"money", "decimal", "integer"} <= {str(getattr(shape, "value", shape)) for shape in shapes}
    numeric = [
        owner
        for owner in owners
        if all(str(getattr(cell.data_type, "value", cell.data_type)) != "text" for cell in owner.target_cells)
    ]
    assert numeric, "no numeric shared owner, so this check proves nothing"
    for zero in (Decimal("0"), Decimal("0.00")):
        values: dict[CasillaId, object] = {owner.casilla_id: zero for owner in numeric}
        assert written_unadjudicated_shared_owners(layout, revision.casillas, values) == ()


@pytest.mark.parametrize("year", _m200_filing_years())
def test_a_zero_or_digit_in_a_text_cell_is_a_written_value_and_refuses(year: int) -> None:
    """Box 00040 reaches a text cell, where a zero prints instead of leaving the design's blank."""
    revision = compiled_bundled_authority().snapshot(_M200, filing_year=year, period="0A").revision
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    (owner,) = [
        owner
        for owner in unadjudicated_shared_owners(layout, revision.casillas)
        if any(str(getattr(cell.data_type, "value", cell.data_type)) == "text" for cell in owner.target_cells)
    ]
    for value in (Decimal("0"), "0"):
        written = written_unadjudicated_shared_owners(layout, revision.casillas, {owner.casilla_id: value})
        assert [item.casilla_id for item in written] == [owner.casilla_id]
    for blank in (None, "", "   "):
        assert written_unadjudicated_shared_owners(layout, revision.casillas, {owner.casilla_id: blank}) == ()


@pytest.mark.parametrize("year", _m200_filing_years())
@pytest.mark.parametrize("amount", [Decimal("0.01"), Decimal("-0.01")], ids=["smallest-positive", "smallest-negative"])
def test_the_smallest_amount_either_side_of_zero_refuses(year: int, amount: Decimal) -> None:
    assert _refusal(year, {"00281": amount}).translated_message == _REFUSAL


def _all_layouts():
    for modelo in compiled_bundled_authority().modelos:
        for revision in modelo.revisions.values():
            layout = canonical_export_layout(revision.export_layouts)
            if layout is not None:
                yield str(modelo.id), revision, layout


def test_only_modelo_200_has_unadjudicated_owners_across_every_revision() -> None:
    affected = {
        modelo for modelo, revision, layout in _all_layouts() if unadjudicated_shared_owners(layout, revision.casillas)
    }
    assert affected == {_M200}


def test_the_rule_agrees_with_the_identity_worklist_on_modelo_200() -> None:
    """Two routes to one set: the layout rule and the worklist reading the map and the design."""
    worklists = load_bundled_m200_target_identity_worklists()
    assert worklists, "no worklist, so this check proves nothing"
    revisions = {str(revision.id): (revision, layout) for modelo, revision, layout in _all_layouts() if modelo == _M200}
    for worklist in worklists:
        revision, layout = revisions[worklist.revision]
        owners = unadjudicated_shared_owners(layout, revision.casillas)
        assert {str(owner.casilla_id) for owner in owners} == {row.casilla_id for row in worklist.shared_owners}
        assert sum(len(owner.target_cells) for owner in owners) == sum(len(row.cells) for row in worklist.shared_owners)


def test_every_repeat_in_a_single_segment_revision_has_been_read_against_its_design() -> None:
    """A newly authored repeat without a segment cannot pass unread: the rule would never see it."""
    found: set[tuple[str, str]] = set()
    for modelo, revision, layout in _all_layouts():
        if any(casilla.segmento is not None for casilla in revision.casillas):
            continue
        seen: dict[str, list[ExportFieldDefinition]] = {}
        for record in layout.records:
            for field in record.fields:
                if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None:
                    seen.setdefault(str(field.casilla_id), []).append(field)
        found |= {
            (modelo, casilla)
            for casilla, cells in seen.items()
            if len(cells) > 1 and any(cell.value_policy is None for cell in cells)
        }
    assert found == _SINGLE_SEGMENT_REPEATS


def test_a_repeated_box_in_a_single_segment_modelo_keeps_exporting() -> None:
    """Modelo 390's section 8 reprints section 7's box [659], and both carry the amount."""
    casilla = "iva.anual.iva-importacion-diferimiento"
    scenarios = edition_export_scenarios("390")
    assert scenarios, "no Modelo 390 scenario, so this check proves nothing"
    for scenario in scenarios.values():
        rendered = _export("390", scenario, {"modelo-390-prev-303-iva-importacion-aduana": Decimal("123.45")})
        cells = _cells(rendered.revision, casilla)
        assert len(cells) == 2
        wires = {_page_slot(rendered.payload, rendered.revision, cell) for cell in cells}
        assert len(wires) == 1
        (wire,) = wires
        assert wire.endswith(b"12345")


def _page_slot(payload: bytes, revision: ModeloRevision, cell: ExportFieldDefinition) -> bytes:
    """Read a cell of a positioned page from the page's own record bytes."""
    (layout,) = revision.export_layouts
    (record,) = [record for record in layout.records if any(field is cell for field in record.fields)]
    literal = "".join(
        field.literal or ""
        for field in sorted(record.fields, key=lambda field: field.offset or 0)[:3]
        if field.kind is CasillaFieldKind.LITERAL
    )
    assert literal, "the page declares no opening literal to find it by"
    encoded = literal.encode("ascii")
    start = payload.index(encoded)
    assert cell.offset is not None and cell.length is not None
    return payload[start + cell.offset - 1 : start + cell.offset - 1 + cell.length]


def test_a_segmented_repeat_in_another_modelo_keeps_its_relation() -> None:
    """Modelo 714's summary page repeats a segmented box, so a written value is not refused."""
    modelo = compiled_bundled_authority().modelo("714")
    repeats = 0
    for revision in modelo.revisions.values():
        layout = canonical_export_layout(revision.export_layouts)
        if layout is None:
            continue
        owner = validated_owner(revision, "declaracion-60")
        assert len(_cells(revision, owner)) == 2
        assert written_unadjudicated_shared_owners(layout, revision.casillas, {owner: Decimal("123.45")}) == ()
        repeats += 1
    assert repeats, "no Modelo 714 layout, so this check proves nothing"


def validated_owner(revision: ModeloRevision, casilla_id: str) -> CasillaId:
    return next(casilla.id for casilla in revision.casillas if str(casilla.id) == casilla_id)


def test_a_split_keeps_exporting_and_losing_its_policy_is_caught() -> None:
    """Teeth: a Modelo 193 split passes until its cells stop stating which part they write."""
    modelo = compiled_bundled_authority().modelo("193")
    revision = max(modelo.revisions.values(), key=lambda item: item.valid_from)
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    owner = validated_owner(revision, "decl.base-total")
    values: dict[CasillaId, object] = {owner: Decimal("123.45")}
    assert written_unadjudicated_shared_owners(layout, revision.casillas, values) == ()

    stripped = layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(
                    update={
                        "fields": tuple(
                            field.model_copy(update={"value_policy": None}) if field.casilla_id == owner else field
                            for field in record.fields
                        )
                    }
                )
                for record in layout.records
            )
        }
    )

    assert [item.casilla_id for item in written_unadjudicated_shared_owners(stripped, revision.casillas, values)] == [
        owner
    ]


def test_a_segmented_box_losing_its_segment_is_caught() -> None:
    """Teeth: the declared relation is the segment, so removing it makes the same cells refuse."""
    revision = max(compiled_bundled_authority().modelo(_M200).revisions.values(), key=lambda item: item.valid_from)
    layout = canonical_export_layout(revision.export_layouts)
    assert layout is not None
    owner = validated_owner(revision, "DP200014:00547")
    casillas = tuple(
        casilla.model_copy(update={"segmento": None}) if casilla.id == owner else casilla
        for casilla in revision.casillas
    )
    values: dict[CasillaId, object] = {owner: Decimal("123.45")}

    assert written_unadjudicated_shared_owners(layout, revision.casillas, values) == ()
    assert [item.casilla_id for item in written_unadjudicated_shared_owners(layout, casillas, values)] == [owner]
