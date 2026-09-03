"""Registry reference, source, and temporal coordinate schema models."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, AnyHttpUrl, BeforeValidator, Field, TypeAdapter, field_validator, model_validator

from ....core.external_constants import (
    PDF_EXTENSION,
    XLS_EXTENSION,
    XLSM_EXTENSION,
    XLSX_EXTENSION,
)
from ....core.filing_year import FilingYear
from ....core.identity import ContentDigest
from ....core.period import RegistryPeriodCode, RegistrySelectorPeriodCode
from ....core.record_design_epoch import RECORD_DESIGN_EPOCH_RE
from ....core.revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from .errors import RegistryValidationError
from .ids import LegalRefId, ModeloId, ParameterId, RevisionId, SourceRefId
from .schema_base import (
    CorpusTierField,
    DateAxisField,
    DesignAuthority,
    EvidenceTier,
    EvidenceTierField,
    LegalRefs,
    PublishingAuthorityField,
    RegistryModel,
    RegistrySourceKind,
    RegistrySourceKindField,
    RevisionReviewStatusField,
    coerce_enum_member,
)

__all__ = [
    "LegalParameter",
    "LegalReference",
    "PeriodSelector",
    "RegistryExternalLink",
    "RegistrySnapshotRef",
    "SourceReference",
    "TemporalApplicability",
    "source_window_applies_across",
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
    review_status: RevisionReviewStatus,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> None:
    has_reviewer = reviewed_by is not None
    has_review_date = reviewed_at is not None
    if review_status is RevisionReviewStatus.PENDING_REVIEW:
        if has_reviewer or has_review_date:
            raise RegistryValidationError("pending legal reference must not declare reviewed_by or reviewed_at")
    elif review_status in REVIEWED_REVISION_REVIEW_STATUSES and not (has_reviewer and has_review_date):
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


class LegalReferenceKind(StrEnum):
    """The kind of instrument a legal reference cites.

    Spanish instrument names are kept as AEAT and the BOE use them; the meanings belong
    to those sources and are not paraphrased here.
    """

    LEY = "ley"
    REAL_DECRETO = "real_decreto"
    REAL_DECRETO_LEGISLATIVO = "real_decreto_legislativo"
    REAL_DECRETO_LEY = "real_decreto_ley"
    ORDEN = "orden"
    REGLAMENTO = "reglamento"
    ACUERDO_INTERNACIONAL = "acuerdo_internacional"
    DIRECTIVA = "directiva"
    MANUAL = "manual"
    INSTRUCTION = "instruction"


LegalReferenceKindField = Annotated[LegalReferenceKind, BeforeValidator(coerce_enum_member(LegalReferenceKind))]
"""Registry token hydrated into a LegalReferenceKind member."""


class DictionaryCasillaIdGrammar(StrEnum):
    """The casilla-id grammar a dictionary source publishes."""

    NUMERIC = "numeric"
    NUMERIC_OR_SINGLE_UPPERCASE_LETTER = "numeric_or_single_uppercase_letter"


DictionaryCasillaIdGrammarField = Annotated[
    DictionaryCasillaIdGrammar, BeforeValidator(coerce_enum_member(DictionaryCasillaIdGrammar))
]
"""Registry token hydrated into a DictionaryCasillaIdGrammar member."""


class RegistrySnapshotRef(RegistryModel):
    """Typed coordinates that identify a registry snapshot."""

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: FilingYear
    period: RegistryPeriodCode


class PeriodSelector(RegistryModel):
    """Select filing years and periods using explicit years or an inclusive range."""

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
    """Describe the date axis and optional period selector for a valid window."""

    date_axis: DateAxisField
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> TemporalApplicability:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("valid_to must be on or after valid_from")
        return self


def _validate_legal_governed_periods(
    legal_id: str,
    *,
    governs_periods_from: date | None,
    governs_periods_to: date | None,
    effective_from: date,
) -> None:
    """Refuse a governed-period declaration that is not a retroactive reach."""
    if governs_periods_to is not None and governs_periods_from is None:
        raise RegistryValidationError(
            f"legal reference {legal_id!r} declares governs_periods_to without governs_periods_from",
        )
    if governs_periods_from is None:
        return
    if governs_periods_from >= effective_from:
        raise RegistryValidationError(
            f"legal reference {legal_id!r} declares governs_periods_from "
            f"{governs_periods_from.isoformat()} on or after effective_from "
            f"{effective_from.isoformat()}: the field declares RETROACTIVE reach only, and a "
            f"forward value would let a stale citation ground a period its norm never governed",
        )
    if governs_periods_to is not None and governs_periods_to < governs_periods_from:
        raise RegistryValidationError(
            f"legal reference {legal_id!r} governs_periods_to must be on or after governs_periods_from",
        )


class LegalReference(RegistryModel):
    """Legal-authority citation row carried by registry definitions."""

    id: LegalRefId
    evidence_tier: Annotated[Literal[EvidenceTier.LEGAL_AUTHORITY], BeforeValidator(coerce_enum_member(EvidenceTier))]
    authority: PublishingAuthorityField
    kind: LegalReferenceKindField
    corpus_ref: str
    document_id: str
    article: str | None = None
    section: str | None = None
    permalink: RegistryExternalLink
    published_at: date | None = None
    effective_from: date
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: RevisionReviewStatusField
    reviewed_at: date | None = None
    reviewed_by: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    required_text: tuple[str, ...] = Field(min_length=1)
    forbidden_text: tuple[str, ...] = ()
    corpus_tier: CorpusTierField | None = None
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

    governs_periods_from: date | None = None
    """Earliest devengo this provision governs, when it reaches back before force.

    ``effective_from`` / ``effective_to`` record when a norm entered and left
    FORCE. A retroactive provision governs tax periods that closed before it
    existed: RDL 13/2025, in force from 2025-11-27, extends the La Palma
    deduction "durante los periodos impositivos 2022, 2023, 2024 y 2025" in its
    own operative text. Checking such a citation against the in-force window
    rejects a correct grounding, and the cheapest way to silence that refusal is
    to backdate ``effective_from`` -- which misstates when the norm came into
    force and corrupts every other consumer of that field.

    So reach is declared here, separately, and only ever by an author who has
    read the clause that states it. Absent, the governed span IS the in-force
    span, so adding this field relaxes no existing citation. The declaration is
    deliberately retroactive-only: it must precede ``effective_from``, because a
    forward-reaching value would let a stale citation ground a period its norm
    never governed.
    """
    governs_periods_to: date | None = None
    """Latest devengo this provision governs; ``None`` leaves the reach open.

    Only meaningful alongside :attr:`governs_periods_from`, which the validator
    requires.
    """

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        _validate_legal_review_metadata(self.review_status, self.reviewed_by, self.reviewed_at)
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise RegistryValidationError("legal reference effective_to must be on or after effective_from")
        _validate_legal_governed_periods(
            self.id,
            governs_periods_from=self.governs_periods_from,
            governs_periods_to=self.governs_periods_to,
            effective_from=self.effective_from,
        )
        _validate_legal_reference_text(self.id, self.required_text, self.forbidden_text)
        _validate_legal_corpus_ref(self.id, self.corpus_ref)
        return self


#: The canonical epoch shape, imported rather than restated. A second copy is how
#: the registry boundary and the filing-evidence boundary drift apart -- and that
#: drift is what let a value the registry would refuse reach a filed artefact.
_RECORD_DESIGN_EPOCH: Final = RECORD_DESIGN_EPOCH_RE


def source_window_applies_across(
    *,
    applies_from: date | None,
    applies_to: date | None,
    span_from: date,
    span_to: date | None,
) -> bool:
    """Report whether a source applicability window overlaps one date span.

    The ONE definition of the overlap rule, shared by every carrier of an
    applicability window so that a diagnostic copy of a source cannot answer
    the question differently from the source itself. An open bound means the
    window is open in that direction, never that it is unknown; deciding
    whether an absent bound is admissible belongs to the caller, before it asks.
    """
    if applies_to is not None and applies_to < span_from:
        return False
    return not (applies_from is not None and span_to is not None and applies_from > span_to)


class SourceReference(RegistryModel):
    """Official-source evidence row with bundled-corpus integrity metadata."""

    id: SourceRefId
    evidence_tier: EvidenceTierField
    authority: PublishingAuthorityField
    kind: RegistrySourceKindField
    corpus_path: str
    sha256: ContentDigest
    bytes: int = Field(gt=0)
    retrieved_at: date
    published_at: date | None = None
    applies_from: date | None = None
    applies_to: date | None = None
    dictionary_casilla_id_grammar: DictionaryCasillaIdGrammarField = DictionaryCasillaIdGrammar.NUMERIC
    """Exact casilla-id grammar published by a dictionary source.

    The default accepts the numbered ids used by every ordinary AEAT dictionary.
    The extension is an evidence claim tied to the hash-pinned source row, not a
    parser-side modelo, source-id, or year exception: when a reviewed dictionary
    publishes its one-letter annex boxes, that source declares the wider grammar.
    Its ``applies_from`` / ``applies_to`` window remains the temporal authority
    for the source itself.
    """
    record_design_epoch: str | None = Field(default=None, min_length=1, max_length=128)
    design_authority: DesignAuthority = "authoritative"
    source_url: RegistryExternalLink
    review_status: RevisionReviewStatusField
    period_selector: PeriodSelector | None = None
    """Disambiguates two designs that share one ``applies_from``/``applies_to`` window.

    Deliberately optional and deliberately reuses :class:`PeriodSelector` --
    the registry's one period-selector shape, already carrying the AEAT-token
    vocabulary (:data:`RegistrySelectorPeriodCode`) -- rather than inventing a
    second grammar. ``applies_from``/``applies_to`` alone cannot express two
    real AEAT designs published for the SAME year that govern different
    PERIODS within it: M303 published one whole-year 2018 record design and a
    second covering every period except the last (quarter 4 / month 12), and
    a 2021 pair split at period 07 (one design "hasta periodo 06", the
    successor "desde periodo 07"). Both members of each pair carry an
    identical nominal date window, so nothing before this field could tell
    :func:`resolve_record_design_binary`'s caller which one to pick for a
    given filing period. Declare it only for a design whose own filename or
    published text states the period boundary; leave it undeclared rather
    than infer one.
    """
    corpus_tier: CorpusTierField | None = None
    """Mirrors :attr:`LegalReference.corpus_tier` in philosophy, recalibrated here.

    Same two-valued, verified-not-merely-typed contract: optional so adding
    the field cannot itself introduce a refusal, and deliberately two-valued
    so a paraphrase can never become a *declarable* tier -- that shape stays
    a build-time refusal, never a state this field can assert. The
    calibration is NOT reused from :attr:`LegalReference.corpus_tier`: this
    model's ``corpus_path`` is a bare repository-relative path with no
    ``#anchor`` convention (``LegalReference.corpus_ref`` is ``path#anchor``),
    so a resolved-anchor read does not apply here, and the size floor is
    calibrated against THIS model's own observed population, not
    ``LegalReference``'s. The excerpt/full-text duality only exists for
    ``corpus_path`` entries under ``corpus/normatives/`` -- the same BOE/AEAT
    norm-text tree ``LegalReference.corpus_ref`` resolves into, which is why a
    ``form_spec`` source can legitimately point at the exact file a
    ``LegalReference`` entry also cites. A design workbook, manual PDF, XSD or
    data dictionary under ``corpus/aeat_official/`` has no such duality --
    verified by ``_corpus_catalogue.py``'s check, which refuses the field
    outside ``corpus/normatives/`` rather than silently accepting a claim the
    concept does not apply to.
    """

    def applies_across(self, span_from: date, span_to: date | None) -> bool:
        """Report whether this source's applicability window overlaps one date span.

        Delegates to :func:`source_window_applies_across`, which is the one
        definition of the overlap rule. Callers keep their own policy on whether
        a missing bound is admissible -- a record-design binary must declare
        ``applies_from``, an evidence-backed source cell must declare both --
        and apply it before asking this question.
        """
        return source_window_applies_across(
            applies_from=self.applies_from,
            applies_to=self.applies_to,
            span_from=span_from,
            span_to=span_to,
        )

    @model_validator(mode="after")
    def _validate_source_reference(self) -> SourceReference:
        if self.applies_to is not None and self.applies_from is not None and self.applies_to < self.applies_from:
            raise RegistryValidationError("source reference applies_to must be on or after applies_from")
        if self.kind is not RegistrySourceKind.DICTIONARY and self.dictionary_casilla_id_grammar != "numeric":
            raise RegistryValidationError(
                "dictionary_casilla_id_grammar other than 'numeric' is only valid for kind='dictionary'",
            )
        if self.period_selector is not None and self.applies_from is not None:
            if not self.period_selector.includes_year(self.applies_from.year):
                raise RegistryValidationError(
                    f"source reference {self.id!r} declares period_selector that does not cover "
                    f"applies_from's year {self.applies_from.year}",
                )
            if self.applies_to is not None and not self.period_selector.includes_year(self.applies_to.year):
                raise RegistryValidationError(
                    f"source reference {self.id!r} declares period_selector that does not cover "
                    f"applies_to's year {self.applies_to.year}",
                )
        if "\\" in self.corpus_path or self.corpus_path.startswith(("/", ".")):
            raise RegistryValidationError("source reference corpus_path must be repository-relative POSIX style")
        if self.kind is RegistrySourceKind.RECORD_DESIGN:
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

    @property
    def supports_single_uppercase_letter_casilla_ids(self) -> bool:
        """Whether this exact reviewed dictionary declares the annex-id grammar."""
        return self.dictionary_casilla_id_grammar == "numeric_or_single_uppercase_letter"

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
    evidence_tier: Annotated[Literal[EvidenceTier.LEGAL_AUTHORITY], BeforeValidator(coerce_enum_member(EvidenceTier))]
    value: str
    unit: str
    applies_to: str
    legal_refs: LegalRefs
    review_status: RevisionReviewStatusField
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None


def governed_period_span(reference: LegalReference) -> tuple[date, date | None]:
    """Return the devengo span ``reference`` governs, which may precede its force.

    Defaults to the in-force window, so a reference that declares nothing is
    tested exactly as before -- the retroactive fields cannot relax a citation
    by existing. A reference that DOES declare reach is tested against the
    declared span, because that is the axis its citation defends: RDL 13/2025 is
    in force only from 2025-11-27 yet governs periods 2022 through 2025 by its
    own operative text, so the 2024 devengo it grounds is inside its reach and
    outside its force.

    The declaration is validated retroactive-only at the model boundary, so this
    can widen a span backwards but never forwards.
    """
    if reference.governs_periods_from is None:
        return reference.effective_from, reference.effective_to
    return reference.governs_periods_from, reference.governs_periods_to
