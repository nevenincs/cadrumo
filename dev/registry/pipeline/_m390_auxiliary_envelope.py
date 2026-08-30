"""Typed Modelo 390 page-zero rendering from the official parser intermediate.

The source-selected parser output owns header coordinates and source literals.
This module supplies only draft-dependent values, the explicit product/software
identity, and the ordered already-rendered numbered-page payloads.  It does
not read registry layouts, fragment trees, or any historical output.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.application.filing import render_envelope_prefix_field
from cadrumo.core import Modelo
from cadrumo.core.period import Period, StandardPeriodCode
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.product_identity import AeatProductSoftwareIdentity
from cadrumo.domain.calculations.registry.corpus_catalogue import resolve_record_design_binary
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.record_design_schema import (
    AUXILIARY_ENVELOPE_HEADER_ORDINALS,
    AUXILIARY_ENVELOPE_HEADER_ROWS,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.filing.errors import FilingExportValidationError

from ._provenance_manifest import ExportFragmentTarget
from ._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateAuxiliaryEnvelopeHeader,
    RecordDesignIntermediateField,
    RecordDesignIntermediateSource,
)
from ._variable_envelope import AUXILIARY_TO_PREFIX_ROLE

__all__ = [
    "M390_AUXILIARY_ENVELOPE_TARGETS",
    "M390AuxiliaryEnvelopeBytes",
    "M390AuxiliaryEnvelopeGenerationInput",
    "M390AuxiliaryEnvelopeNumberedPage",
    "M390ProspectiveGenerationTarget",
    "render_m390_auxiliary_envelope_bytes",
    "validate_m390_auxiliary_envelope",
]


class _StrictModel(BaseModel):
    """Frozen development-only boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class M390ProspectiveGenerationTarget(_StrictModel):
    """One pre-authoring M390 source-bound target, not a live registry selection."""

    target: ExportFragmentTarget
    source_ref: str = Field(pattern=r"^aeat-dr-390-(2022|2023|2024|2025)$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    design_epoch: str = Field(pattern=r"^(2022|2023|2024|2025)$")
    filing_year_from: int = Field(ge=2022)
    filing_year_to: int | None = Field(default=None, ge=2022)

    @model_validator(mode="after")
    def _require_exact_source_epoch_and_window(self) -> M390ProspectiveGenerationTarget:
        if self.target.modelo != "390":
            raise ValueError("Modelo 390 prospective target must retain modelo 390")
        if self.target.design_epoch != self.design_epoch:
            raise ValueError("Modelo 390 prospective target must retain its exact design epoch")
        if self.source_ref != f"aeat-dr-390-{self.design_epoch}":
            raise ValueError("Modelo 390 source reference must name its exact design epoch")
        if self.filing_year_to is not None and self.filing_year_to < self.filing_year_from:
            raise ValueError("Modelo 390 filing-year window must be increasing")
        return self


M390_AUXILIARY_ENVELOPE_TARGETS: Final[tuple[M390ProspectiveGenerationTarget, ...]] = (
    M390ProspectiveGenerationTarget(
        target=ExportFragmentTarget(modelo="390", revision_id="2022", design_epoch="2022"),
        source_ref="aeat-dr-390-2022",
        source_sha256="7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe",
        design_epoch="2022",
        filing_year_from=2022,
        filing_year_to=2022,
    ),
    M390ProspectiveGenerationTarget(
        target=ExportFragmentTarget(modelo="390", revision_id="2023", design_epoch="2023"),
        source_ref="aeat-dr-390-2023",
        source_sha256="179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7",
        design_epoch="2023",
        filing_year_from=2023,
        filing_year_to=2023,
    ),
    M390ProspectiveGenerationTarget(
        target=ExportFragmentTarget(modelo="390", revision_id="2024", design_epoch="2024"),
        source_ref="aeat-dr-390-2024",
        source_sha256="8be79bacc86034c3c7951d2ea671c030800ed9a4cc3f52b9e5d407bc19bc03f0",
        design_epoch="2024",
        filing_year_from=2024,
        filing_year_to=2024,
    ),
    M390ProspectiveGenerationTarget(
        target=ExportFragmentTarget(modelo="390", revision_id="2025-y-siguientes", design_epoch="2025"),
        source_ref="aeat-dr-390-2025",
        source_sha256="6d33d8a4245976e55dc31ff85065b420f76d1588110dc1eb541a8039c5e3f252",
        design_epoch="2025",
        filing_year_from=2025,
    ),
)
"""Reviewed targets; they do not assert a current registry revision exists."""


class M390AuxiliaryEnvelopeNumberedPage(_StrictModel):
    """One already-rendered numbered source page in exact parser order."""

    record_identity: str = Field(min_length=1)
    payload: bytes = Field(min_length=1)


class M390AuxiliaryEnvelopeGenerationInput(_StrictModel):
    """Every non-source value required for one M390 header composition."""

    target: ExportFragmentTarget
    filing_period: Period
    product_software_identity: AeatProductSoftwareIdentity
    numbered_pages: tuple[M390AuxiliaryEnvelopeNumberedPage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_annual_period_and_unique_pages(self) -> M390AuxiliaryEnvelopeGenerationInput:
        if self.filing_period.standard_code is not StandardPeriodCode.ANNUAL:
            raise ValueError("Modelo 390 auxiliary header requires annual period 0A")
        identities = tuple(page.record_identity for page in self.numbered_pages)
        if len(set(identities)) != len(identities):
            raise ValueError("Modelo 390 numbered pages must be unique and ordered")
        return self


class M390AuxiliaryEnvelopeBytes(_StrictModel):
    """Measured page-zero header followed by its complete numbered-page payloads."""

    filing_period: Period
    header: bytes = Field(min_length=328, max_length=328)
    numbered_pages: tuple[M390AuxiliaryEnvelopeNumberedPage, ...] = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _require_exact_byte_composition(self) -> M390AuxiliaryEnvelopeBytes:
        if self.payload != self.header + b"".join(page.payload for page in self.numbered_pages):
            raise ValueError("Modelo 390 payload must exactly append ordered pages to its auxiliary header")
        if self.payload_sha256 != sha256_hex(self.payload):
            raise ValueError("Modelo 390 payload digest must be derived from emitted bytes")
        if self.header[-6:] != b"</AUX>":
            raise ValueError("Modelo 390 auxiliary header must end in its source closing marker")
        return self


def validate_m390_auxiliary_envelope(
    intermediate: RecordDesignIntermediate,
    generation_input: M390AuxiliaryEnvelopeGenerationInput,
    *,
    source_catalogue: Mapping[str, SourceReference],
    source_root: Path,
) -> RecordDesignIntermediateAuxiliaryEnvelopeHeader:
    """Prove source, prospective target, header anchors, and page order before bytes exist."""
    _require_exact_generation_target(
        intermediate.source,
        generation_input,
        source_catalogue=source_catalogue,
        source_root=source_root,
    )
    headers = intermediate.auxiliary_envelope_headers
    if len(headers) != 1:
        raise RegistryValidationError("Modelo 390 generation requires exactly one parser-owned auxiliary header")
    header = headers[0]
    _require_header_geometry_and_literals(header)
    expected_page_ids = tuple(sheet.record_identity for sheet in intermediate.sheets)
    actual_page_ids = tuple(page.record_identity for page in generation_input.numbered_pages)
    if actual_page_ids != expected_page_ids:
        raise RegistryValidationError(
            "Modelo 390 numbered pages must exactly match the parser-owned source order; "
            f"expected={expected_page_ids!r}, actual={actual_page_ids!r}",
        )
    return header


def render_m390_auxiliary_envelope_bytes(
    intermediate: RecordDesignIntermediate,
    generation_input: M390AuxiliaryEnvelopeGenerationInput,
    *,
    source_catalogue: Mapping[str, SourceReference],
    source_root: Path,
) -> M390AuxiliaryEnvelopeBytes:
    """Render page zero once, then append each already-rendered numbered page."""
    header = validate_m390_auxiliary_envelope(
        intermediate,
        generation_input,
        source_catalogue=source_catalogue,
        source_root=source_root,
    )
    header_bytes = b"".join(
        _render_header_field(
            item.role.value,
            item.parser_field,
            product_software_identity=generation_input.product_software_identity,
            filing_period=generation_input.filing_period,
        )
        for item in header.fields
    )
    if len(header_bytes) != header.emitted_extent:
        raise RegistryValidationError(
            f"Modelo 390 auxiliary header renders to {len(header_bytes)} bytes, expected {header.emitted_extent}",
        )
    payload = header_bytes + b"".join(page.payload for page in generation_input.numbered_pages)
    return M390AuxiliaryEnvelopeBytes(
        filing_period=generation_input.filing_period,
        header=header_bytes,
        numbered_pages=generation_input.numbered_pages,
        payload=payload,
        payload_sha256=sha256_hex(payload),
    )


def _require_exact_generation_target(
    source: RecordDesignIntermediateSource,
    generation_input: M390AuxiliaryEnvelopeGenerationInput,
    *,
    source_catalogue: Mapping[str, SourceReference],
    source_root: Path,
) -> None:
    matching = tuple(target for target in M390_AUXILIARY_ENVELOPE_TARGETS if target.target == generation_input.target)
    if len(matching) != 1:
        raise RegistryValidationError(
            f"Modelo 390 prospective target {generation_input.target!r} has no reviewed source binding",
        )
    (prospective_target,) = matching
    resolved = resolve_record_design_binary(
        source_root,
        source_catalogue,
        source_ref=prospective_target.source_ref,
        filing_year=generation_input.filing_period.filing_year,
        design_epoch=prospective_target.design_epoch,
    )
    if (resolved.source.id, resolved.source.sha256, resolved.source.record_design_epoch) != (
        prospective_target.source_ref,
        prospective_target.source_sha256,
        prospective_target.design_epoch,
    ):
        raise RegistryValidationError("Modelo 390 prospective target does not match its source catalogue authority")
    if (source.source_ref, source.source_sha256, source.design_epoch) != (
        prospective_target.source_ref,
        prospective_target.source_sha256,
        prospective_target.design_epoch,
    ):
        expected_source_identity = (
            prospective_target.source_ref,
            prospective_target.source_sha256,
            prospective_target.design_epoch,
        )
        actual_source_identity = (source.source_ref, source.source_sha256, source.design_epoch)
        raise RegistryValidationError(
            "Modelo 390 source identity does not match its reviewed prospective target; "
            f"expected={expected_source_identity!r}, actual={actual_source_identity!r}",
        )
    filing_year = generation_input.filing_period.filing_year
    if filing_year < prospective_target.filing_year_from or (
        prospective_target.filing_year_to is not None and filing_year > prospective_target.filing_year_to
    ):
        raise RegistryValidationError(
            f"Modelo 390 filing year {filing_year} is outside prospective target {prospective_target.target!r}",
        )


def _require_header_geometry_and_literals(header: RecordDesignIntermediateAuxiliaryEnvelopeHeader) -> None:
    expected_roles = (
        "opening_tag",
        "modelo",
        "discriminant",
        "filing_year",
        "annual_period",
        "record_type",
        "auxiliary_opening_tag",
        "pre_program_reserved",
        "program_identifier",
        "between_identities_reserved",
        "software_developer_tax_id",
        "post_developer_reserved",
        "auxiliary_closing_tag",
    )
    fields = header.source_fields
    if tuple(item.role.value for item in header.fields) != expected_roles or len(fields) != 13:
        raise RegistryValidationError("Modelo 390 auxiliary header requires its thirteen exact source roles")
    if any(field.offset + field.length != next_field.offset for field, next_field in pairwise(fields)):
        raise RegistryValidationError("Modelo 390 auxiliary header source anchors must be contiguous")
    if fields[0].offset != 1 or fields[-1].offset + fields[-1].length - 1 != 328:
        raise RegistryValidationError("Modelo 390 auxiliary header source anchors must occupy positions 1 through 328")
    if tuple(field.source_row for field in fields) != AUXILIARY_ENVELOPE_HEADER_ROWS:
        raise RegistryValidationError("Modelo 390 auxiliary header source rows must retain their exact anchors")
    if tuple(field.source_cell for field in fields) != tuple(f"A{row}" for row in AUXILIARY_ENVELOPE_HEADER_ROWS):
        raise RegistryValidationError("Modelo 390 auxiliary header source cells must retain their exact anchors")
    if tuple(field.ordinal for field in fields) != AUXILIARY_ENVELOPE_HEADER_ORDINALS:
        raise RegistryValidationError("Modelo 390 auxiliary header ordinals must retain their exact anchors")
    expected_contents = (
        'Constante "<T"',
        'Constante "390"',
        'Constante "0"',
        "Nota 2",
        '"0A"',
        '"0000>"',
        '"<AUX>"',
        "BLANCOS",
        "Nota 1",
        "BLANCOS",
        "Nota 1",
        "BLANCOS",
        '"</AUX>"',
    )
    if tuple(field.content for field in fields) != expected_contents:
        raise RegistryValidationError("Modelo 390 auxiliary header literals conflict with the official source anchors")


def _render_header_field(
    role: str,
    parser_field: RecordDesignIntermediateField,
    *,
    product_software_identity: AeatProductSoftwareIdentity,
    filing_period: Period,
) -> bytes:
    """Render one header role through the canonical prefix renderer.

    The auxiliary header and the filing-envelope prefix share one grammar, so
    the bytes come from the application filing renderer rather than a second
    literal table: the role names here are the parser's vocabulary and map
    onto the shared prefix roles.
    """
    try:
        prefix_role = AUXILIARY_TO_PREFIX_ROLE[RecordDesignAuxiliaryEnvelopeHeaderRole(role)]
    except ValueError as exc:
        raise RegistryValidationError(f"auxiliary header role {role!r} is not a recognised source role") from exc
    try:
        payload = render_envelope_prefix_field(
            prefix_role,
            length=parser_field.length,
            modelo=Modelo.M390,
            period=filing_period,
            product_software_identity=product_software_identity,
        )
    except FilingExportValidationError as exc:
        raise RegistryValidationError(f"auxiliary header role {role!r} is not renderable: {exc}") from exc
    return payload
