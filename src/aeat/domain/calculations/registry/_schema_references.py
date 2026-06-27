"""Registry reference, source, and temporal coordinate schema models."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._ids import LegalRefId, ModeloId, RevisionId, SourceRefId
from ._schema_base import DateAxis, EvidenceTier, LegalRefs, RegistryModel, ReviewStatus

__all__ = [
    "LegalParameter",
    "LegalReference",
    "PeriodSelector",
    "RegistrySnapshotRef",
    "SourceReference",
    "TemporalApplicability",
]


class RegistrySnapshotRef(RegistryModel):
    """Typed coordinates that identify a registry snapshot."""

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=32)


class PeriodSelector(RegistryModel):
    years: tuple[int, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    periods: tuple[str, ...] = Field(min_length=1)

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("period_selector periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_year_selector(self) -> PeriodSelector:
        if self.years and self.year_from is not None:
            raise RegistryValidationError("period_selector must use either years or year_from/year_to")
        if not self.years and self.year_from is None:
            raise RegistryValidationError("period_selector must declare years or year_from")
        if len(set(self.years)) != len(self.years):
            raise RegistryValidationError("period_selector years must be unique")
        if self.year_to is not None and self.year_from is None:
            raise RegistryValidationError("period_selector year_to requires year_from")
        if self.year_from is not None and self.year_to is not None and self.year_to < self.year_from:
            raise RegistryValidationError("period_selector year_to must be on or after year_from")
        return self

    def includes_year(self, year: int) -> bool:
        """Return whether the selector covers a filing year."""
        if self.years:
            return year in self.years
        if self.year_from is None:
            return False
        return year >= self.year_from and (self.year_to is None or year <= self.year_to)


class TemporalApplicability(RegistryModel):
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> TemporalApplicability:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("valid_to must be on or after valid_from")
        return self


class LegalReference(RegistryModel):
    id: LegalRefId
    evidence_tier: Literal["legal_authority"]
    authority: Literal["boe", "aeat", "eu", "autonomous_community", "other"]
    kind: Literal[
        "ley",
        "real_decreto",
        "real_decreto_ley",
        "orden",
        "reglamento",
        "directiva",
        "manual",
        "instruction",
    ]
    corpus_ref: str
    document_id: str
    article: str | None = None
    section: str | None = None
    permalink: str
    published_at: date | None = None
    effective_from: date
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    required_text: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise RegistryValidationError("legal reference effective_to must be on or after effective_from")
        if any(not item.strip() for item in self.required_text):
            raise RegistryValidationError("legal reference required_text entries must be non-empty")
        if len(set(self.required_text)) != len(self.required_text):
            raise RegistryValidationError("legal reference required_text entries must be unique")
        if "#" not in self.corpus_ref:
            raise RegistryValidationError(
                f"legal reference {self.id!r} corpus_ref must be of the form 'path#anchor' (got {self.corpus_ref!r})",
            )
        path_part, _, anchor_part = self.corpus_ref.partition("#")
        if not path_part or not anchor_part:
            raise RegistryValidationError(f"legal reference {self.id!r} corpus_ref must have non-empty path and anchor")
        return self


class SourceReference(RegistryModel):
    id: SourceRefId
    evidence_tier: EvidenceTier
    authority: Literal["aeat", "boe", "eu", "autonomous_community", "other"]
    kind: Literal["record_design", "manual_pdf", "instructions", "xsd", "dictionary", "form_spec"]
    corpus_path: str
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(gt=0)
    retrieved_at: date
    published_at: date | None = None
    applies_from: date | None = None
    applies_to: date | None = None
    source_url: str
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _validate_source_reference(self) -> SourceReference:
        if self.applies_to is not None and self.applies_from is not None and self.applies_to < self.applies_from:
            raise RegistryValidationError("source reference applies_to must be on or after applies_from")
        if "\\" in self.corpus_path or self.corpus_path.startswith(("/", ".")):
            raise RegistryValidationError("source reference corpus_path must be repository-relative POSIX style")
        if self.kind == "record_design":
            allowed_record_design_suffixes = (".pdf", ".xls", ".xlsx", ".xlsm")
            suffix = self.corpus_path.rsplit(".", 1)
            extension = "." + suffix[1].lower() if len(suffix) == 2 else ""
            if extension not in allowed_record_design_suffixes:
                raise RegistryValidationError(
                    f"source reference {self.id!r} declares kind='record_design' but corpus_path "
                    f"{self.corpus_path!r} has unsupported extension {extension!r}; the record-design "
                    f"extractor accepts only .pdf / .xls / .xlsx / .xlsm — reclassify the source "
                    f"(e.g. kind='form_spec' for an AEAT/BOE landing page HTML) or ingest the real "
                    f"Diseño workbook",
                )
        return self

    @field_validator("sha256")
    @classmethod
    def _sha256_lower_hex(cls, value: str) -> str:
        lowered = value.lower()
        if lowered != value or any(char not in "0123456789abcdef" for char in value):
            raise RegistryValidationError("sha256 must be lowercase hexadecimal")
        return value


class LegalParameter(RegistryModel):
    id: str
    evidence_tier: Literal["legal_authority"]
    value: str
    unit: str
    applies_to: str
    legal_refs: LegalRefs
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
