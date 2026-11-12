"""Modelo 200 page 002 places each family's rows in the numbered slots of one page.

The export design addresses the administradores, socios and the other page 002
relations as numbered slots inside one fixed page: every projection field of the
layout names its kind, its slot and the row member it prints, and the record does
not repeat. For every Modelo 200 revision whose fixed-width layout carries those
slots (selected by the layout, so no year is named), two rows of a family must be
written into slots 1 and 2 of a single page and parse back through the registry
codec to the typed values; one row keeps its single page; and a family with more
rows than the page has slots refuses instead of losing the excess.

The sociedad limitada persona's page 002 relations (its sole administradora, who is
also its sole socia and its representante legal) are then carried from a stored
profile through the canonical profile mapper into pages 002 and 002b, and each
value parses back to the typed value the profile states. All data is synthetic.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.m200_projection import (
    build_m200_filing_projection_plan,
    m200_projection_families,
    m200_projection_slot_limits,
)
from cadrumo.application.filing.producer_snapshot_m200 import (
    Modelo200AdministradorRow,
    Modelo200ParticipacionSocioRow,
    Modelo200ProjectionRows,
)
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.application.modelo.m200_page_002_profile import modelo_200_profile_facts
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.governed_fact_scope import GovernedFactSource, validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from cadrumo.domain.filing.errors import FilingExportValueOverflowError
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from cadrumo.domain.submission.models import ModeloDraftStatus
from cadrumo.domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileFactValue,
    create_user_profile_record,
)
from dev.registry.compiler.loader import modelo_fact_scope
from dev.registry.edition_export_scenarios import m200_export_scenario, m200_one_row_per_family
from dev.registry.edition_round_trip import SYNTHETIC_TAX_ID

from .authored_edition_support import authored_revisions_where
from .filing_reach_support import with_filing_reach

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"
_ADMINISTRADORES = (
    Modelo200AdministradorRow(nif="B00010082", apellidos_nombre_razon_social="ADMINISTRADORA UNO"),
    Modelo200AdministradorRow(nif="B00020081", apellidos_nombre_razon_social="ADMINISTRADOR DOS"),
)
_SOCIOS = (
    Modelo200ParticipacionSocioRow(nif="B00030080", apellidos_nombre_razon_social="SOCIA UNO"),
    Modelo200ParticipacionSocioRow(nif="B00040089", apellidos_nombre_razon_social="SOCIO DOS"),
)


def _fixed_width_layout(revision: ModeloRevision) -> ExportLayoutDefinition:
    (layout,) = (layout for layout in revision.export_layouts if layout.format is ExportLayoutFormat.FIXED_WIDTH)
    return layout


def _has_projection_slots(revision: ModeloRevision) -> bool:
    return any(
        field.projection_ref is not None
        for layout in revision.export_layouts
        if layout.format is ExportLayoutFormat.FIXED_WIDTH
        for record in layout.records
        for field in record.fields
    )


_SLOT_REVISIONS = tuple(str(revision.id) for revision in authored_revisions_where(_M200, _has_projection_slots))
assert _SLOT_REVISIONS, "the registry authors no Modelo 200 revision whose layout carries projection slots"


@pytest.fixture(autouse=True)
def pinned_authority() -> Iterator[PinnedAuthorityOperation]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


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


def _kinds_of(authority: GovernedFactSource, period_end: date) -> Mapping[str, str]:
    """Return the projection kind the registry routes to each typed row family."""
    return {family: kind for kind, family in m200_projection_families(period_end, authority=authority).items()}


@dataclass(frozen=True, slots=True)
class _Exported:
    """One exported payload, its layout, the registry's kind per family and each field read back.

    ``planned`` holds the occurrences the canonical projection plan gives each record id.
    """

    payload: bytes
    layout: ExportLayoutDefinition
    kinds: Mapping[str, str]
    parsed: Mapping[str, str]
    typed: Mapping[str, object]
    planned: Mapping[str, tuple[int, ...]]


def _export(authority: ValidatedRegistryAuthority, revision_id: str, rows: Modelo200ProjectionRows) -> _Exported:
    """Export the canonical Modelo 200 scenario with ``rows`` through the canonical writer, then parse it."""
    period = _first_supported_annual_period(authority, authority.modelo(_M200).revisions[revision_id])
    scenario = m200_export_scenario(period, projection_rows=rows)
    staged = with_filing_reach(authority, _M200, revision_id)
    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", _M200)), validating_governed_facts(staged):
        kinds = _kinds_of(staged, period.end_date)
        provider = schema_provider_from_authority(
            staged, modelos=(_M200,), filing_year=period.filing_year, period=period
        )
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 page 002 slots"),
            inputs=scenario.inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        producer_snapshot = scenario.producer_snapshot()
        registry_snapshot = provider.get_snapshot(_M200)
        layout = _fixed_width_layout(registry_snapshot.revision)
        plan = build_m200_filing_projection_plan(
            registry_snapshot=registry_snapshot, layout=layout, producer_snapshot=producer_snapshot
        )
        identity_factory = scenario.product_software_identity_factory
        assert identity_factory is not None
        sink = _PayloadSink()
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=producer_snapshot,
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=identity_factory(),
            schema_provider=provider,
        )
    planned: dict[str, tuple[int, ...]] = {}
    for context in plan.contexts:
        planned[str(context.record.id)] = (*planned.get(str(context.record.id), ()), context.occurrence)
    parsed = parse_export_payload(
        layout, sink.payload, sources=provider.sources, source_payloads=provider.source_payloads
    )
    return _Exported(
        payload=sink.payload,
        layout=layout,
        kinds=kinds,
        parsed={str(value.field_id): str(value.value) for value in parsed.fields},
        typed={str(value.field_id): value.value for value in parsed.fields},
        planned=planned,
    )


def _record_of(layout: ExportLayoutDefinition, kind: str) -> ExportRecordDefinition:
    (record,) = (
        record
        for record in layout.records
        if any(
            field.projection_ref is not None and field.projection_ref.projection_kind == kind for field in record.fields
        )
    )
    return record


def _slot_values(
    record: ExportRecordDefinition, kind: str, parsed: Mapping[str, object]
) -> dict[tuple[int, str], object]:
    """Read back every slot member of one kind: (slot, member) -> the value parsed for it."""
    values: dict[tuple[int, str], object] = {}
    for field in record.fields:
        ref = field.projection_ref
        if ref is None or ref.projection_kind != kind:
            continue
        slot: object = getattr(ref, "slot", None)
        member: object = getattr(ref, "field", None)
        assert isinstance(slot, int), f"{field.id} addresses no slot"
        assert isinstance(member, str), f"{field.id} names no row member"
        values[(slot, str(member))] = parsed[str(field.id)]
    return values


def _occurrences(payload: bytes, record: ExportRecordDefinition) -> int:
    """Count the pages of ``record`` in the payload by the literal fields it opens with, in layout order."""
    opening = b""
    for field in record.fields:
        if field.literal is None:
            break
        opening += field.literal.encode(record.encoding)
    assert opening, f"{record.id} opens with no literal"
    return payload.count(opening)


def _two_of_each() -> Modelo200ProjectionRows:
    return m200_one_row_per_family().model_copy(
        update={"administrador": _ADMINISTRADORES, "participacion_socio": _SOCIOS}
    )


@pytest.mark.parametrize("revision_id", _SLOT_REVISIONS)
def test_two_administradores_and_two_socios_fill_slots_one_and_two_of_one_page(
    registry_authority: ValidatedRegistryAuthority, revision_id: str
) -> None:
    exported = _export(registry_authority, revision_id, _two_of_each())
    administrador = exported.kinds["administrador"]
    socio = exported.kinds["participacion_socio"]
    page = _record_of(exported.layout, administrador)
    assert _record_of(exported.layout, socio) is page

    assert exported.planned[str(page.id)] == (1,)
    assert _occurrences(exported.payload, page) == 1
    for kind, rows in ((administrador, _ADMINISTRADORES), (socio, _SOCIOS)):
        slots = _slot_values(page, kind, exported.parsed)
        for slot, row in enumerate(rows, 1):
            assert slots[(slot, "nif")] == row.nif
            assert slots[(slot, "apellidos_nombre_razon_social")] == row.apellidos_nombre_razon_social
        assert all(
            value in {"", "None"} for (slot, member), value in slots.items() if slot > len(rows) and member == "nif"
        )


@pytest.mark.parametrize("revision_id", _SLOT_REVISIONS)
def test_one_administrador_still_writes_one_page_with_slot_one(
    registry_authority: ValidatedRegistryAuthority, revision_id: str
) -> None:
    rows = m200_one_row_per_family()
    exported = _export(registry_authority, revision_id, rows)
    administrador = exported.kinds["administrador"]
    page = _record_of(exported.layout, administrador)

    assert exported.planned[str(page.id)] == (1,)
    assert _occurrences(exported.payload, page) == 1
    slots = _slot_values(page, administrador, exported.parsed)
    (only,) = rows.administrador
    assert slots[(1, "nif")] == only.nif
    assert slots[(1, "apellidos_nombre_razon_social")] == only.apellidos_nombre_razon_social
    assert all(value in {"", "None"} for (slot, member), value in slots.items() if slot > 1 and member == "nif")


@pytest.mark.parametrize("revision_id", _SLOT_REVISIONS)
def test_more_administradores_than_the_page_has_slots_refuse(
    registry_authority: ValidatedRegistryAuthority, revision_id: str
) -> None:
    exported = _export(registry_authority, revision_id, m200_one_row_per_family())
    places = m200_projection_slot_limits(exported.layout)[exported.kinds["administrador"]]
    administradores = tuple(
        Modelo200AdministradorRow(nif=_ADMINISTRADORES[0].nif, apellidos_nombre_razon_social="ADMINISTRADORA")
        for _ in range(places + 1)
    )
    rows = m200_one_row_per_family().model_copy(update={"administrador": administradores})

    with pytest.raises(InternalInvariantError, match="slots"):
        _export(registry_authority, revision_id, rows)


# The sociedad limitada persona's synthetic page 002 relations: its sole administradora, a
# resident natural person identified by a NIE, is also its sole socia, holding the whole
# share capital, and its representante legal under the deed of incorporation.
_PERSONA_NIE = "Y0000000Z"
_PERSONA_NAME = "FERREIRA COSTA ANA"
# The notaria the persona fixture states; the design prints "Notaría/otros" in 12 characters.
_PERSONA_NOTARIA = "NOTARIA DE VALLADOLID, PROTOCOLO 101"
# The same notaria as the design's 12-character place can carry it.
_DESIGN_NOTARIA = "VALLADOLID"
_PERSONA_BUCKET = "5d0c7e1b-3a64-4f8e-b2a9-6c1d9e4f7a30"
_STATED_NONE = (
    "has_secretario_consejo",
    "has_participacion_directa",
    "has_establecimiento_permanente",
    "has_socio_sicav_disolucion",
)


def _persona_facts(poder: date, notaria: str) -> dict[str, UserProfileFactValue]:
    return {
        "taxpayer_type.entity_type": "legal_entity",
        "taxpayer_type.legal_entity_form": "sl",
        "taxpayer_type.fiscal_residency": "resident_irpf",
        "m200_administrador.0.nif": _PERSONA_NIE,
        "m200_administrador.0.apellidos_nombre_razon_social": _PERSONA_NAME,
        "m200_administrador.0.forma_juridica": "F",
        "m200_participacion_socio.0.nif": _PERSONA_NIE,
        "m200_participacion_socio.0.forma_juridica": "F",
        "m200_participacion_socio.0.apellidos_nombre_razon_social": _PERSONA_NAME,
        "m200_participacion_socio.0.codigo_provincia_pais": "47",
        "m200_participacion_socio.0.nominal": Decimal("3000.00"),
        "m200_participacion_socio.0.porcentaje_participacion": Decimal("100.00"),
        "m200_representante_legal.0.apellidos_y_nombre": _PERSONA_NAME,
        "m200_representante_legal.0.nif": _PERSONA_NIE,
        "m200_representante_legal.0.fecha_poder": poder,
        "m200_representante_legal.0.notaria_otros": notaria,
        "m200_relaciones.has_participacion_socio": True,
        "m200_relaciones.has_representante_legal": True,
        **{f"m200_relaciones.{answer}": False for answer in _STATED_NONE},
    }


def _persona_rows(
    operation: PinnedAuthorityOperation,
    revision_id: str,
    period: Period,
    layout: ExportLayoutDefinition,
    poder: date,
    notaria: str,
) -> Modelo200ProjectionRows:
    """Carry the persona's stored profile through the canonical page 002 profile mapper."""
    at = datetime.fromtimestamp(0, tz=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PERSONA_BUCKET,
            modelo=_M200,
            filing_year=period.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_PERSONA_BUCKET,
        modelo=_M200,
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name="Impuesto sobre Sociedades",
        created_at=at,
        updated_at=at,
        state=WorkUnitState.BORRADOR,
    )
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PERSONA_BUCKET,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in _persona_facts(poder, notaria).items()),
        context=operation.profile_create_context(),
    )
    facts = modelo_200_profile_facts(
        work_unit=work_unit, operation=operation, export_layout=layout, profile_record=record
    )
    return facts.projection_rows


def _typed(parsed: object, *, like: object) -> object:
    """Read a parsed design date (AAAAMMDD, which the codec returns as its text) as a date."""
    if isinstance(like, date) and isinstance(parsed, str):
        return datetime.strptime(parsed, "%Y%m%d").replace(tzinfo=UTC).date()
    return parsed


def _persona_poder(authority: ValidatedRegistryAuthority) -> date:
    """The deed of incorporation empowered her six years before the support horizon."""
    return date(authority.supported_filing_years().horizon - 6, 1, 10)


def _export_persona(
    authority: ValidatedRegistryAuthority,
    operation: PinnedAuthorityOperation,
    revision_id: str,
    notaria: str,
) -> _Exported:
    """Export the persona's page 002 relations, mapped from its stored profile."""
    revision = authority.modelo(_M200).revisions[revision_id]
    period = _first_supported_annual_period(authority, revision)
    rows = _persona_rows(
        operation, revision_id, period, _fixed_width_layout(revision), _persona_poder(authority), notaria
    )
    # The writer requires every projection-only page, so the scenario's placeholder rows fill
    # the pages the persona states nothing on; the persona's own families replace them.
    return _export(
        authority,
        revision_id,
        m200_one_row_per_family().model_copy(
            update={
                "administrador": rows.administrador,
                "participacion_socio": rows.participacion_socio,
                "representante_legal": rows.representante_legal,
            }
        ),
    )


@pytest.mark.parametrize("revision_id", _SLOT_REVISIONS)
def test_the_sociedad_persona_page_002_relations_parse_back_to_their_profile_values(
    registry_authority: ValidatedRegistryAuthority, pinned_authority: PinnedAuthorityOperation, revision_id: str
) -> None:
    exported = _export_persona(registry_authority, pinned_authority, revision_id, _DESIGN_NOTARIA)
    poder = _persona_poder(registry_authority)

    expected: dict[str, dict[str, object]] = {
        "administrador": {"nif": _PERSONA_NIE, "apellidos_nombre_razon_social": _PERSONA_NAME, "forma_juridica": "F"},
        "participacion_socio": {
            "nif": _PERSONA_NIE,
            "forma_juridica": "F",
            "apellidos_nombre_razon_social": _PERSONA_NAME,
            "codigo_provincia_pais": "47",
            "nominal": Decimal("3000.00"),
            "porcentaje_participacion": Decimal("100.00"),
        },
        "representante_legal": {
            "apellidos_y_nombre": _PERSONA_NAME,
            "nif": _PERSONA_NIE,
            "fecha_poder": poder,
            "notaria_otros": _DESIGN_NOTARIA,
        },
    }
    pages: set[str] = set()
    for family, members in expected.items():
        kind = exported.kinds[family]
        page = _record_of(exported.layout, kind)
        pages.add(str(page.id))
        assert exported.planned[str(page.id)] == (1,)
        assert _occurrences(exported.payload, page) == 1
        slots = _slot_values(page, kind, exported.typed)
        for member, value in members.items():
            assert _typed(slots[(1, member)], like=value) == value, (family, member, slots[(1, member)])
        assert all(not value for (slot, member), value in slots.items() if slot > 1 and member == "nif")
    assert len(pages) == 2, "the persona's relations span pages 002 and 002b"


@pytest.mark.parametrize("revision_id", _SLOT_REVISIONS)
def test_a_notaria_wider_than_its_design_place_refuses_on_that_place(
    registry_authority: ValidatedRegistryAuthority, pinned_authority: PinnedAuthorityOperation, revision_id: str
) -> None:
    layout = _fixed_width_layout(registry_authority.modelo(_M200).revisions[revision_id])
    kind = _kinds_of_layout_family(registry_authority, pinned_authority, revision_id, "representante_legal")
    (place,) = (
        field
        for field in _record_of(layout, kind).fields
        if field.projection_ref is not None
        and field.projection_ref.projection_kind == kind
        and getattr(field.projection_ref, "slot", None) == 1
        and getattr(field.projection_ref, "field", None) == "notaria_otros"
    )
    assert place.length is not None
    assert len(_PERSONA_NOTARIA) > place.length

    with pytest.raises(FilingExportValueOverflowError) as refused:
        _export_persona(registry_authority, pinned_authority, revision_id, _PERSONA_NOTARIA)

    assert refused.value.field_id == str(place.id)
    assert refused.value.field_length == place.length


def _kinds_of_layout_family(
    authority: ValidatedRegistryAuthority, operation: PinnedAuthorityOperation, revision_id: str, family: str
) -> str:
    period = _first_supported_annual_period(authority, authority.modelo(_M200).revisions[revision_id])
    return _kinds_of(operation, period.end_date)[family]
