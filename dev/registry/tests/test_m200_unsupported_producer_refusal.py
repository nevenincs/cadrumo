"""Modelo 200 unsupported producer fields: a stated value refuses, an absent one keeps its blank fill.

The DP200DID "Período Impositivo inicio - Año" and "fin - Año" fields are Num
of length 2 with an empty Contenido cell in every edition, so no official text
says which digits they carry. The export therefore refuses, with a typed
terminal refusal and no byte written, whenever it would have to write one, and
writes the slot's declared blank fill when the fact is absent and the layout
lets the slot stay empty.

Page 1 field 26, "Autoliquidación rectificativa - ... solicito dar de baja la
domiciliación efectuada", is the contrast: sheet DP200014B Nota 1 of its design
states that the field "tiene valor 1 (opción SÍ)", so a stated statement is
written as 1.

Each case runs the real ``build_draft`` and ``export_draft`` path for every
Modelo 200 edition with a committed generated export. The slots are located by
the design's own field positions, read from the committed design extraction,
not by the layout under test.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_producer_supply import (
    UNSUPPORTED_PRODUCER_KEYS,
    require_supplied_producers,
    unsupported_producer_keys,
)
from cadrumo.application.filing.export_refusal_doors import ExportRefusalReason, export_design_terminal
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.producer_snapshot import FilingProducerSnapshot
from cadrumo.application.filing.producer_snapshot_m200 import Modelo200ProfileFacts
from cadrumo.application.filing.runtime import (
    ModeloOperatorProfile,
    RegistrySchemaAccessor,
    build_runtime_schema_provider,
    collection_from_snapshot,
    subview_from_snapshot,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureCondition,
    RegistrySnapshotError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..edition_export_scenarios import m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID
from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_M200 = "200"
_PROVENANCE = "_generation.provenance.json"
_DESIGN_ROW = re.compile(r"^(\d+) \| (\d+) \| (\d+) \| (\w+) \| (.*?)\s*(?:\|.*)?$")
_INICIO = FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_ANO
_FIN = FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_ANO
_BAJA = FilingProducerKey.M200_COMO_CONSECUENCIA_DE_LA_PRESENTACION_DE_LA_A
_BAJA_STATEMENT = "solicito dar de baja la domiciliación efectuada"


@dataclass(frozen=True, slots=True)
class _Edition:
    revision: str
    source_ref: str
    filing_year: int


@dataclass(frozen=True, slots=True)
class _DesignSlot:
    offset: int
    length: int
    design_type: str


@dataclass(frozen=True, slots=True)
class _Family:
    """One kind of Modelo 200 field: its design sheet, record tag, row test and producer keys."""

    sheet: str
    record_tag: bytes
    keys: frozenset[FilingProducerKey]

    def is_row(self, description: str) -> bool:
        if self.sheet == "DP200DID":
            return description.startswith("Período Impositivo") and description.rstrip(" |").endswith("Año")
        return _BAJA_STATEMENT in description


_DID_YEARS = _Family("DP200DID", b"<T200DID00>", frozenset({_INICIO, _FIN}))
_BAJA_DOMICILIACION = _Family("DP200001", b"<T20001000>", frozenset({_BAJA}))
_FAMILIES = (_DID_YEARS,)


def _editions() -> tuple[_Edition, ...]:
    """Every Modelo 200 edition with a committed generated export, at the first year it governs."""
    authority = compiled_bundled_authority()
    found: list[_Edition] = []
    for manifest in sorted(
        bundled_path("registry", "aeat", "modelos", _M200).glob(f"revisions/*/export/{_PROVENANCE}")
    ):
        revision_id = manifest.parent.parent.name
        receipt = load_export_fragment_provenance_manifest(manifest.read_bytes())
        revision = authority.modelo(_M200).revisions[revision_id]
        found.append(_Edition(revision_id, str(receipt.source_ref), revision.valid_from.year))
    assert found, "Modelo 200 has no committed generated export"
    return tuple(found)


def _design_slots(source_ref: str, family: _Family) -> tuple[_DesignSlot, ...]:
    """The family's fields as the official design prints them: position, length and type."""
    source = compiled_bundled_authority().catalogues.sources[source_ref]
    text = bundled_path(f"{source.corpus_path}.extracted.md").read_text(encoding="utf-8")
    sheet = ""
    slots: list[_DesignSlot] = []
    for line in text.splitlines():
        if line.startswith("# "):
            sheet = line[2:].strip()
            continue
        match = _DESIGN_ROW.match(line.strip())
        if sheet == family.sheet and match is not None and family.is_row(match.group(5)):
            slots.append(_DesignSlot(int(match.group(2)), int(match.group(3)), match.group(4)))
    return tuple(slots)


def _cases() -> Iterator[object]:
    """Each edition paired with each family its design prints."""
    for edition in _editions():
        for family in _FAMILIES:
            if _design_slots(edition.source_ref, family):
                yield pytest.param(edition, family, id=f"{edition.revision}-{family.sheet}")


class _PayloadSink:
    payload: bytes | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _schema_provider(operation: PinnedAuthorityOperation, period: Period) -> RegistrySchemaAccessor:
    """The filing provider, or the calculation snapshot of an edition held below filing grade."""
    try:
        return build_runtime_schema_provider(
            operation=operation, modelos=(_M200,), filing_year=period.filing_year, period=period
        )
    except (RegistrySnapshotError, RegistryValidationError) as refused:
        failure = refused.registry_failure
        if failure is None or failure.condition is not RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT:
            raise
    snapshot = operation.snapshot(
        _M200, filing_year=period.filing_year, period=period.registry_token, grade=RegistryAuthorityGrade.CALCULATION
    )
    return RegistrySchemaAccessor(
        collections={_M200: collection_from_snapshot(snapshot)},
        subviews={_M200: subview_from_snapshot(snapshot)},
        snapshots={_M200: snapshot},
        sources=snapshot.sources,
    )


def _with_facts(snapshot: FilingProducerSnapshot, **facts: str) -> FilingProducerSnapshot:
    profile = snapshot.model_profile
    assert isinstance(profile, Modelo200ProfileFacts)
    return snapshot.model_copy(update={"model_profile": profile.model_copy(update=facts)})


def _export(filing_year: int, sink: _PayloadSink, **facts: str) -> ModeloRevision:
    scenario = m200_export_scenario(Period.from_year_and_code(filing_year, "0A"))
    with bundled_indexed_authority().operation() as operation:
        provider = _schema_provider(operation, scenario.period)
        revision = provider.get_snapshot(_M200).revision
        draft = build_draft(
            modelo=_M200,
            period=scenario.period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Unsupported field"),
            inputs=scenario.inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        identity = scenario.product_software_identity_factory
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=_with_facts(scenario.producer_snapshot(), **facts),
            prior_domiciliation_election=scenario.prior_domiciliation_election,
            product_software_identity=None if identity is None else identity(),
            schema_provider=provider,
        )
    return revision


def _cited_fields(revision: ModeloRevision, keys: frozenset[FilingProducerKey]) -> tuple[ExportFieldDefinition, ...]:
    return tuple(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.producer_key in keys
    )


def _unsupported_layout(revision: ModeloRevision) -> ExportLayoutDefinition:
    (layout,) = (
        layout
        for layout in revision.export_layouts
        if any(field.producer_key in UNSUPPORTED_PRODUCER_KEYS for record in layout.records for field in record.fields)
    )
    return layout


def _fact_name(key: FilingProducerKey) -> str:
    return key.value.removeprefix("m200.")


@pytest.mark.parametrize(("edition", "family"), tuple(_cases()))
def test_the_layout_cites_each_design_slot_of_the_family_as_unsupported(edition: _Edition, family: _Family) -> None:
    slots = _design_slots(edition.source_ref, family)
    revision = compiled_bundled_authority().modelo(_M200).revisions[edition.revision]
    cited = {(field.offset, field.length): field.producer_key for field in _cited_fields(revision, family.keys)}

    assert len(slots) == len(family.keys), f"the design no longer prints the {family.sheet} fields: {slots}"
    assert all(slot.design_type == "Num" for slot in slots)
    assert set(cited) == {(slot.offset, slot.length) for slot in slots}
    assert set(cited.values()) == family.keys
    assert family.keys <= UNSUPPORTED_PRODUCER_KEYS


@pytest.mark.parametrize(("edition", "family"), tuple(_cases()))
def test_an_absent_unsupported_fact_keeps_the_blank_fill_of_its_slot(edition: _Edition, family: _Family) -> None:
    sink = _PayloadSink()
    revision = _export(edition.filing_year, sink)

    assert sink.payload is not None
    (line,) = [line for line in sink.payload.split(b"\r\n") if family.record_tag in line]
    record = line[line.index(family.record_tag) :]
    fields = _cited_fields(revision, family.keys)
    for slot in _design_slots(edition.source_ref, family):
        written = record[slot.offset - 1 : slot.offset - 1 + slot.length]
        (field,) = [field for field in fields if field.offset == slot.offset]
        assert not field.required
        fill = b" " if field.absent_fill == "spaces" else b"0"
        assert written == fill * slot.length, (slot, written)


def _stated_cases() -> Iterator[object]:
    """Every stated value an unsupported slot could be asked to carry, each a refusal."""
    for edition in _editions():
        year = str(edition.filing_year)
        if _design_slots(edition.source_ref, _DID_YEARS):
            for name, stated in (
                ("inicio", {_INICIO: year}),
                ("fin", {_FIN: year[-2:]}),
                ("both", {_INICIO: year[-2:], _FIN: year}),
            ):
                yield pytest.param(edition, stated, id=f"{edition.revision}-did-{name}")


@pytest.mark.parametrize(("edition", "stated"), tuple(_stated_cases()))
def test_a_stated_unsupported_fact_refuses_the_export_terminally_and_writes_nothing(
    edition: _Edition, stated: dict[FilingProducerKey, str]
) -> None:
    """Every stated token refuses, whichever representation it would claim."""
    sink = _PayloadSink()
    with pytest.raises(FilingExportValidationError) as refusal:
        _export(edition.filing_year, sink, **{_fact_name(key): value for key, value in stated.items()})

    context = refusal.value.context or {}
    assert sink.payload is None
    assert refusal.value.translated_message == "application.filing.export.errors.producer_facts_unsupplied"
    assert set(str(context["unsupported_producer_keys"]).split(",")) == {key.value for key in stated}
    assert context["missing_producer_keys"] == ""
    assert refusal.value.terminal_precondition_verdict == export_design_terminal(
        ExportRefusalReason.PRODUCER_FACT_UNSUPPLIED
    )


@pytest.mark.parametrize(("edition", "family"), tuple(_cases()))
def test_a_planted_required_unsupported_slot_refuses_even_without_a_value(edition: _Edition, family: _Family) -> None:
    revision = compiled_bundled_authority().modelo(_M200).revisions[edition.revision]
    layout = _unsupported_layout(revision)
    planted_key = min(family.keys, key=lambda key: key.value)
    planted = layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(
                    update={
                        "fields": tuple(
                            field.model_copy(update={"required": True}) if field.producer_key == planted_key else field
                            for field in record.fields
                        )
                    }
                )
                for record in layout.records
            )
        }
    )
    headers: dict[FilingProducerKey, object] = {
        field.producer_key: None
        for record in layout.records
        for field in record.fields
        if field.producer_key is not None
    }

    assert unsupported_producer_keys(layout, headers) == ()
    assert unsupported_producer_keys(planted, headers) == (planted_key,)
    with pytest.raises(FilingExportValidationError):
        require_supplied_producers(planted, headers, modelo=_M200)


def _baja_editions() -> tuple[object, ...]:
    return tuple(
        pytest.param(edition, id=edition.revision)
        for edition in _editions()
        if _design_slots(edition.source_ref, _BAJA_DOMICILIACION)
    )


@pytest.mark.parametrize("edition", _baja_editions())
def test_a_stated_baja_de_domiciliacion_exports_1_at_its_design_slot(edition: _Edition) -> None:
    """The statement made is written as the design note's 'valor 1 (opción SÍ)', and the export succeeds."""
    (slot,) = _design_slots(edition.source_ref, _BAJA_DOMICILIACION)
    sink = _PayloadSink()
    revision = _export(edition.filing_year, sink, **{_fact_name(_BAJA): "1"})

    assert sink.payload is not None
    (line,) = [line for line in sink.payload.split(b"\r\n") if _BAJA_DOMICILIACION.record_tag in line]
    record = line[line.index(_BAJA_DOMICILIACION.record_tag) :]
    assert (slot.length, slot.design_type) == (1, "Num")
    assert record[slot.offset - 1 : slot.offset - 1 + slot.length] == b"1"
    assert _BAJA not in UNSUPPORTED_PRODUCER_KEYS
    assert [field.offset for field in _cited_fields(revision, _BAJA_DOMICILIACION.keys)] == [slot.offset]
