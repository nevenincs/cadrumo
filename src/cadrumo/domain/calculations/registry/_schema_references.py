"""Registry reference, source, and temporal coordinate schema models."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, AnyHttpUrl, Field, TypeAdapter, field_validator, model_validator

from ....core import (
    RECORD_DESIGN_EPOCH_RE,
    REVIEWED_LEGAL_STATUSES,
    LegalReviewStatus,
    RegistryPeriodCode,
    RegistrySelectorPeriodCode,
)
from ....core.external_constants import (
    PDF_EXTENSION,
    XLS_EXTENSION,
    XLSM_EXTENSION,
    XLSX_EXTENSION,
)
from ....core.identity import ContentDigest
from ._errors import RegistryValidationError
from ._ids import LegalRefId, ModeloId, ParameterId, RevisionId, SourceRefId
from ._schema_base import DateAxis, EvidenceTier, LegalRefs, LegalReviewStatusField, RegistryModel, ReviewStatus

__all__ = [
    "LegalParameter",
    "LegalReference",
    "PeriodSelector",
    "RegistryExternalLink",
    "RegistrySnapshotRef",
    "SourceReference",
    "TemporalApplicability",
]


_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _validate_registry_external_link(value: str) -> str:
    """Validate one authoritative link while retaining registry string semantics."""
    parsed = _HTTP_URL_ADAPTER.validate_python(value)
    if parsed.scheme != "https":
        raise RegistryValidationError(f"registry external link scheme must be https, got {parsed.scheme!r}")
    return str(parsed)


RegistryExternalLink = Annotated[str, AfterValidator(_validate_registry_external_link)]
"""Canonical fragment-preserving HTTPS link used by registry evidence records."""


def _validate_legal_text_entries(
    entries: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if any(not item.strip() for item in entries):
        raise RegistryValidationError(f"legal reference {field_name} entries must be non-empty")
    if len(set(entries)) != len(entries):
        raise RegistryValidationError(f"legal reference {field_name} entries must be unique")


def _validate_legal_corpus_ref(reference_id: LegalRefId, corpus_ref: str) -> None:
    if "#" not in corpus_ref:
        raise RegistryValidationError(
            f"legal reference {reference_id!r} corpus_ref must be of the form 'path#anchor' (got {corpus_ref!r})",
        )
    path_part, _, anchor_part = corpus_ref.partition("#")
    if not path_part or not anchor_part:
        raise RegistryValidationError(
            f"legal reference {reference_id!r} corpus_ref must have non-empty path and anchor"
        )


def _validate_legal_review_metadata(
    review_status: LegalReviewStatus,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> None:
    has_reviewer = reviewed_by is not None
    has_review_date = reviewed_at is not None
    if review_status is LegalReviewStatus.PENDING_REVIEW:
        if has_reviewer or has_review_date:
            raise RegistryValidationError("pending legal reference must not declare reviewed_by or reviewed_at")
    elif review_status in REVIEWED_LEGAL_STATUSES and not (has_reviewer and has_review_date):
        raise RegistryValidationError(f"{review_status.value} legal reference requires reviewed_by and reviewed_at")


def _validate_legal_reference_text(
    reference_id: LegalRefId, required: tuple[str, ...], forbidden: tuple[str, ...]
) -> None:
    _validate_legal_text_entries(required, field_name="required_text")
    _validate_legal_text_entries(forbidden, field_name="forbidden_text")
    overlap = set(required) & set(forbidden)
    if overlap:
        raise RegistryValidationError(
            f"legal reference {reference_id!r} required_text and forbidden_text must not overlap: {sorted(overlap)!r}",
        )


class RegistrySnapshotRef(RegistryModel):
    """Typed coordinates that identify a registry snapshot."""

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: int = Field(ge=2000, le=2099)
    period: RegistryPeriodCode


class PeriodSelector(RegistryModel):
    years: tuple[int, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    periods: tuple[RegistrySelectorPeriodCode, ...] = Field(min_length=1)

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
    """Legal-authority citation row carried by registry definitions."""

    id: LegalRefId
    evidence_tier: Literal["legal_authority"]
    authority: Literal["boe", "aeat", "eu", "autonomous_community", "other"]
    kind: Literal[
        "ley",
        "real_decreto",
        "real_decreto_legislativo",
        "real_decreto_ley",
        "orden",
        "reglamento",
        "acuerdo_internacional",
        "directiva",
        "manual",
        "instruction",
    ]
    corpus_ref: str
    document_id: str
    article: str | None = None
    section: str | None = None
    permalink: RegistryExternalLink
    published_at: date | None = None
    effective_from: date
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: LegalReviewStatusField
    reviewed_at: date | None = None
    reviewed_by: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    required_text: tuple[str, ...] = Field(min_length=1)
    forbidden_text: tuple[str, ...] = ()
    corpus_tier: Literal["full_consolidated", "provision_excerpt"] | None = None
    """Which kind of corpus evidence ``corpus_ref`` resolves to, when declared.

    Deliberately optional and deliberately two-valued. Optional: nothing in
    the committed catalogue declares it today, so adding the field cannot
    itself introduce a new refusal -- authoring it is opt-in, verified only
    when present. Two-valued: a paraphrase with no operative text of its own
    must never become a *declarable* tier (a stub calling itself an
    excerpt would pass silently); that shape stays a build-time refusal via
    the dispositive-content check, never a legal state this field can assert.
    Verified against the bundled corpus file, not merely typed, by
    ``_legal.py``'s grounding check -- this field states a claim; the
    verifier is what makes the claim mean something.
    """
    """Phrases the cited corpus document must NOT contain.

    ``required_text`` alone cannot express "this repealed clause must be
    absent" — no set of must-be-present phrases states a negative. This is
    the entry's optional negative clause: a corpus excerpt grounding current
    law names the repealed text it must not carry, and a deliberately
    historical excerpt names the later text that must not have crept in,
    which pins its vintage forward as well as backward.
    """

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        _validate_legal_review_metadata(self.review_status, self.reviewed_by, self.reviewed_at)
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise RegistryValidationError("legal reference effective_to must be on or after effective_from")
        _validate_legal_reference_text(self.id, self.required_text, self.forbidden_text)
        _validate_legal_corpus_ref(self.id, self.corpus_ref)
        return self


#: The canonical epoch shape, imported rather than restated. A second copy is how
#: the registry boundary and the filing-evidence boundary drift apart -- and that
#: drift is what let a value the registry would refuse reach a filed artefact.
_RECORD_DESIGN_EPOCH: Final = RECORD_DESIGN_EPOCH_RE


class SourceReference(RegistryModel):
    """Official-source evidence row with bundled-corpus integrity metadata."""

    id: SourceRefId
    evidence_tier: EvidenceTier
    authority: Literal["aeat", "boe", "eu", "autonomous_community", "other"]
    kind: Literal[
        "record_design",
        "manual_pdf",
        "instructions",
        "xsd",
        "dictionary",
        "form_spec",
        "suppression_notice",
    ]
    corpus_path: str
    sha256: ContentDigest
    bytes: int = Field(gt=0)
    retrieved_at: date
    published_at: date | None = None
    applies_from: date | None = None
    applies_to: date | None = None
    record_design_epoch: str | None = Field(default=None, min_length=1, max_length=128)
    source_url: RegistryExternalLink
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _validate_source_reference(self) -> SourceReference:
        if self.applies_to is not None and self.applies_from is not None and self.applies_to < self.applies_from:
            raise RegistryValidationError("source reference applies_to must be on or after applies_from")
        if "\\" in self.corpus_path or self.corpus_path.startswith(("/", ".")):
            raise RegistryValidationError("source reference corpus_path must be repository-relative POSIX style")
        if self.kind == "record_design":
            allowed_record_design_suffixes = (
                PDF_EXTENSION,
                XLS_EXTENSION,
                XLSX_EXTENSION,
                XLSM_EXTENSION,
            )
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
        elif self.record_design_epoch is not None:
            raise RegistryValidationError("record_design_epoch is only valid for kind='record_design'")
        if self.record_design_epoch is not None and not self.record_design_epoch.strip():
            raise RegistryValidationError("record_design_epoch must contain non-whitespace text")
        if self.record_design_epoch is not None and not _RECORD_DESIGN_EPOCH.fullmatch(self.record_design_epoch):
            raise RegistryValidationError(
                f"source reference {self.id!r} declares record_design_epoch "
                f"{self.record_design_epoch!r}, which is not a design EPOCH. An epoch names the "
                "filing period a design governs -- a four-digit ejercicio, optionally with a "
                "lower-case sub-year label where AEAT re-laid the form out mid-ejercicio "
                "('2024-early', '2024-late'). It is NOT the document's version: "
                "'aeat-dr-111-2019-v18' is epoch '2019', because v18 is which revision of the "
                "PDF AEAT published and says nothing about which filings it governs. Two "
                "designs differing only by version are the same epoch and must not both claim "
                "one; two designs governing different periods are different epochs",
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
    """Versioned legal parameter value cited by registry formulas."""

    id: ParameterId
    evidence_tier: Literal["legal_authority"]
    value: str
    unit: str
    applies_to: str
    legal_refs: LegalRefs
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
