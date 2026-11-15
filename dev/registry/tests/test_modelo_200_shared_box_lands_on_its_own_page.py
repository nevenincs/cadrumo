"""A Modelo 200 box printed on several pages exports only into its own page's cell.

The record designs print one box number on several pages with a different meaning
on each: ``[00009]`` is "Entidad dominante de grupo fiscal" on DP200001 and also a
bases imponibles negativas cohort on DP200015; ``[00017]`` is "Cooperativa
protegida" on DP200001 and also a cooperativas cuota-compensation cohort on
DP200022; ``[00088]``, ``[00089]`` and ``[00090]`` are identification flags on
DP200001 and also the three cells of the Festival Porta Ferrada deduction row on
the deducciones page. A value the taxpayer states for the DP200001 flag must reach
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

# Each flag's continuity identity, the record sheet whose design prints it as that
# flag, and the byte the design gives a selected flag (DP200001, type Num, length 1).
_FLAGS = (
    pytest.param("is-entidad-dominante-de-grupo-fiscal", "DP200001", id="00009-entidad-dominante"),
    pytest.param(
        "is-participe-de-agrupacion-de-interes-economico-o-de-union-temporal-de-empresas",
        "DP200001",
        id="00089-participe-aie-ute",
    ),
    pytest.param("is-opcion-art-39-3-lis", "DP200001", id="00090-opcion-art-39-3"),
)
# The Festival Porta Ferrada deduction row, whose three boxes repeat the identification
# page's [00088], [00089] and [00090]. Only the editions with an export layout are
# exercised here, and their designs print the row on DP200018; the 2023 design prints it
# on DP200018B, which that edition declares under its own ids.
_PORTA_FERRADA = (
    pytest.param("is-deduccion-porta-ferrada-pendiente-generada", "DP200018", id="00088-porta-ferrada-pendiente"),
    pytest.param("is-deduccion-porta-ferrada-aplicado-periodo", "DP200018", id="00089-porta-ferrada-aplicado"),
    pytest.param("is-deduccion-porta-ferrada-pendiente-futuro", "DP200018", id="00090-porta-ferrada-futuro"),
)
_PORTA_FERRADA_AMOUNT = Decimal("1234.56")
_COOPERATIVA_PROTEGIDA = "is-cooperativa-protegida"
# The liquidación boxes a protected cooperative's unsupported cuota leaves unrendered.
_UNSUPPORTED_COOPERATIVE_CUOTA = (
    "DP200014:00562",
    "DP200014:00582",
    "DP200014B:00592",
    "DP200014B:00599",
    "DP200014B:00611",
)
_SELECTED = Decimal("1")


class _PayloadSink:
    payload: bytes | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _filing_grade_years() -> tuple[int, ...]:
    """Every supported year the published authority serves Modelo 200 at filing grade with an export layout."""
    years: list[int] = []
    with bundled_indexed_authority().operation() as operation:
        for year in operation.supported_filing_years().years:
            try:
                snapshot = operation.snapshot(_M200, filing_year=year, period="0A", grade=RegistryAuthorityGrade.FILING)
            except RegistryError:
                continue
            if canonical_export_layout(snapshot.revision.export_layouts) is not None:
                years.append(year)
    return tuple(years)


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


_YEARS = _filing_grade_years()


def test_a_filing_grade_modelo_200_edition_exists() -> None:
    assert _YEARS, "no supported year serves Modelo 200 at filing grade, so these checks prove nothing"


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(("continuidad_id", "sheet"), _FLAGS)
def test_a_stated_flag_lands_only_in_its_own_page_cell(year: int, continuidad_id: str, sheet: str) -> None:
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


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(("continuidad_id", "sheet"), _PORTA_FERRADA)
def test_a_stated_porta_ferrada_amount_lands_in_its_own_cell_and_not_in_the_flag_of_the_same_number(
    year: int, continuidad_id: str, sheet: str
) -> None:
    absent, revision = _export(year, {})
    casilla_id = _casilla_id(revision, continuidad_id)
    (cell,) = _cells(revision, casilla_id)
    assert f".{sheet.lower()}." in str(cell.id)
    assert cell.offset is not None and cell.length == 17
    # The identification flag the same printed number names on page one.
    number = str(next(casilla for casilla in revision.casillas if str(casilla.id) == casilla_id).number)
    (flag_cell,) = _cells(revision, f"DP200001:{number}")
    assert flag_cell.offset is not None and flag_cell.length == 1

    stated, _ = _export(year, {casilla_id: _PORTA_FERRADA_AMOUNT})

    assert len(stated) == len(absent)
    start, _line = _record_line(stated, revision, sheet)
    position = start + cell.offset - 1
    assert absent[position : position + cell.length] == b"00000000000000000"
    assert stated[position : position + cell.length] == b"00000000000123456"
    flag_start, _flag_line = _record_line(stated, revision, "DP200001")
    flag_position = flag_start + flag_cell.offset - 1
    assert stated[flag_position : flag_position + flag_cell.length] == absent[flag_position : flag_position + 1]
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
    assert tuple(item["casilla_id"] for item in context["missing_casillas"]) == _UNSUPPORTED_COOPERATIVE_CUOTA
