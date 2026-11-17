"""Every sheet that prints a reused Modelo 200 box number gets its own value at its own official position.

The record design prints boxes such as [00524]-[00526] on several sheets with
different meanings. Besides the first reviewed rename, a sample of the later
reviewed rename covers every sheet family that prints a renamed amount box.
Each printed field must be bound to a casilla of its own, so a value
supplied for one sheet's box reaches that sheet's field and no other. The
expected positions are read here from the official design text itself (field
number, offset, length and type under the sheet's heading), not from the
generated layout under test, and the bytes are read back from the payload the
real ``build_draft`` and ``export_draft`` path produces.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import (
    ModeloOperatorProfile,
    RegistrySchemaAccessor,
    build_runtime_schema_provider,
    collection_from_snapshot,
    subview_from_snapshot,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureCondition,
    RegistrySnapshotError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..edition_export_scenarios import m200_export_scenario
from ..edition_round_trip import SYNTHETIC_TAX_ID
from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest
from ..pipeline.rename_set_static_repair import REVIEWED_RENAME_SETS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"
_PROVENANCE = "_generation.provenance.json"
_FIELD = re.compile(r"^(\d+) \| (\d+) \| (\d+) \| (\w+) \| .*\[(\d{5})\]\s*$")
_M200_RENAMES = tuple(reviewed.renamed_casilla_ids for reviewed in REVIEWED_RENAME_SETS if reviewed.modelo == _M200)
#: One renamed amount box per sheet family that prints such a box: each is printed
#: on several sheets as a 17-position amount and carries no formula or binding.
_LATER_RENAME_SAMPLE = frozenset(
    {
        "00101",
        "00150",
        "00153",
        "00185",
        "00195",
        "00231",
        "00263",
        "00297",
        "00336",
        "00387",
        "00466",
        "00515",
        "00579",
        "00866",
    }
)
_RENAMED = _M200_RENAMES[0] | _LATER_RENAME_SAMPLE


@dataclass(frozen=True, slots=True)
class _DesignField:
    """One field the official design prints for a reused box: its sheet, number and position."""

    sheet: str
    number: str
    field: int
    offset: int
    length: int
    design_type: str


@dataclass(frozen=True, slots=True)
class _PublishedEdition:
    revision: str
    source_ref: str
    filing_year: int


def _published_editions() -> tuple[_PublishedEdition, ...]:
    """Every Modelo 200 edition with a committed generated export, at the first year it governs."""
    authority = compiled_bundled_authority()
    found: list[_PublishedEdition] = []
    for manifest in sorted(
        bundled_path("registry", "aeat", "modelos", _M200).glob(f"revisions/*/export/{_PROVENANCE}")
    ):
        revision_id = manifest.parent.parent.name
        receipt = load_export_fragment_provenance_manifest(manifest.read_bytes())
        revision = authority.modelo(_M200).revisions[revision_id]
        found.append(_PublishedEdition(revision_id, str(receipt.source_ref), revision.valid_from.year))
    assert found, "Modelo 200 has no committed generated export"
    return tuple(found)


def _design_fields(source_ref: str) -> tuple[_DesignField, ...]:
    """Read every field of the official design that prints one of the reused boxes."""
    source = compiled_bundled_authority().catalogues.sources[source_ref]
    text = bundled_path(f"{source.corpus_path}.extracted.md").read_text(encoding="utf-8")
    sheet = ""
    found: list[_DesignField] = []
    for line in text.splitlines():
        if line.startswith("# "):
            sheet = line[2:].strip()
            continue
        match = _FIELD.match(line.strip())
        if match is not None and match.group(5) in _RENAMED:
            field, offset, length, design_type, number = match.groups()
            found.append(_DesignField(sheet, number, int(field), int(offset), int(length), design_type))
    return tuple(found)


def _layout_cell(revision: ModeloRevision, design: _DesignField) -> ExportFieldDefinition:
    """The layout cell whose page-qualified identity names this sheet and field number."""
    suffix = f".{design.sheet.lower()}.f{design.field:04d}"
    (cell,) = [
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if str(field.id).endswith(suffix)
    ]
    return cell


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


def _export(filing_year: int, supplied: dict[str, Decimal]) -> tuple[bytes, ModeloRevision]:
    scenario = m200_export_scenario(Period.from_year_and_code(filing_year, "0A"))
    with bundled_indexed_authority().operation() as operation:
        provider = _schema_provider(operation, scenario.period)
        revision = provider.get_snapshot(_M200).revision
        draft = build_draft(
            modelo=_M200,
            period=scenario.period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Reused boxes"),
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


def _sheet_line(payload: bytes, revision: ModeloRevision, sheet: str) -> bytes:
    """Return the payload record line the sheet's opening literal tag identifies."""
    marker = f".{sheet.lower()}."
    tags: set[str] = set()
    for layout in revision.export_layouts:
        for record in layout.records:
            fields = sorted(
                (field for field in record.fields if marker in str(field.id) and field.offset is not None),
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
    return line[line.index(encoded) :]


def _editions() -> Iterator[object]:
    for edition in _published_editions():
        yield pytest.param(edition, id=edition.revision)


@pytest.mark.parametrize("edition", _editions())
def test_each_printed_reused_box_has_its_own_casilla_at_its_official_position(edition: _PublishedEdition) -> None:
    designs = _design_fields(edition.source_ref)
    sheets = {design.sheet for design in designs}
    assert len(sheets) > 1, "the design no longer reuses these boxes across sheets; this check proves nothing"
    revision = compiled_bundled_authority().modelo(_M200).revisions[edition.revision]

    owners: dict[str, list[str]] = {}
    for design in designs:
        cell = _layout_cell(revision, design)
        assert (cell.offset, cell.length, cell.design_type) == (design.offset, design.length, design.design_type)
        assert cell.kind is CasillaFieldKind.CASILLA and cell.casilla_id is not None, cell.id
        owners.setdefault(str(cell.casilla_id), []).append(f"{design.sheet} field {design.field}")

    shared = {casilla_id: fields for casilla_id, fields in owners.items() if len(fields) > 1}
    assert not shared, f"one casilla bound on several sheets' printed boxes: {shared}"


@pytest.mark.parametrize("edition", _editions())
def test_a_value_supplied_for_each_sheet_box_reads_back_only_at_its_own_field(edition: _PublishedEdition) -> None:
    designs = _design_fields(edition.source_ref)
    revision = compiled_bundled_authority().modelo(_M200).revisions[edition.revision]
    cells = {design: _layout_cell(revision, design) for design in designs}
    values = {
        str(cell.casilla_id): Decimal(f"{index + 1}{index + 1}{index + 1}.{index + 11}")
        for index, cell in enumerate(cells.values())
    }

    payload, exported = _export(edition.filing_year, values)

    assert str(exported.id) == edition.revision
    for design, cell in cells.items():
        expected = values[str(cell.casilla_id)]
        line = _sheet_line(payload, exported, design.sheet)
        slot = line[design.offset - 1 : design.offset - 1 + design.length]
        assert slot == str(int(expected * 100)).rjust(design.length, "0").encode("ascii"), (design, slot)


def test_the_sample_is_drawn_from_a_later_reviewed_rename() -> None:
    later = frozenset().union(*_M200_RENAMES[1:])
    assert later >= _LATER_RENAME_SAMPLE, sorted(_LATER_RENAME_SAMPLE - later)
