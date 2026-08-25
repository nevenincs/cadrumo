"""Typed admission contract for externally hosted PDF layout candidates.

These fixtures are useful because their bytes were produced outside this
repository.  They are not, however, authenticated AEAT evidence.  The models
below keep that distinction structural and recompute every physical claim from
the committed PDF rather than trusting its sidecar or mutable DocInfo.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import pdfplumber
from pdfminer.pdftypes import resolve1
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from .. import RECOGNISED_FIXTURE_PROVENANCES

ExternalLayoutModelo = Literal["036", "130", "131", "303", "349"]
ExternalLayoutCandidateKind = Literal["plain", "fillable"]
ExternalLayoutSourceClassification = Literal["third_party_hosted_external_layout_candidate"]
ExternalLayoutArtifactAuthenticityVerdict = Literal["third_party_sample"]
ExternalLayoutOfficialBaseVerdict = Literal["verified_official_base_derivative"]
ExternalLayoutOfficialAuthority = Literal["aeat", "boe"]
ExternalLayoutOfficialComparisonMethod = Literal["pdf_text_geometry_and_normalized_render"]
ExternalLayoutPairComparisonMethod = Literal[
    "exact_96_dpi_render_match",
    "normalized_96_dpi_render_similarity",
]
ExternalLayoutRegistryApplicabilityVerdict = Literal[
    "current_authored_revision",
    "historical_authored_revision",
    "historical_layout_without_authored_revision",
]

EXTERNAL_LAYOUT_MODELOS: frozenset[str] = frozenset({"036", "130", "131", "303", "349"})
EXTERNAL_LAYOUT_CANDIDATE_KINDS: frozenset[str] = frozenset({"plain", "fillable"})
EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION = "third_party_hosted_external_layout_candidate"
AEAT_PUBLISHED_FACSIMILE_CLASSIFICATION = "aeat_published_facsimile"

_SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_NONEMPTY = Annotated[str, Field(min_length=1)]
_PDF_HEADER_RE = re.compile(rb"\A%PDF-(\d\.\d)")
_NIF_LIKE_RE = re.compile(r"\b(?:[XYZ]\d{7}[A-Z]|\d{8}[A-Z]|[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])\b", re.I)
_IBAN_LIKE_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}\b")
_EMAIL_LIKE_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


class _FrozenStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExternalLayoutSourceChain(_FrozenStrictModel):
    """Unauthenticated retrieval chain; never an authority declaration."""

    classification: ExternalLayoutSourceClassification
    host: Literal["fiscalbot.es"]


class ExternalLayoutArtifactAuthenticity(_FrozenStrictModel):
    """Identity of the committed candidate bytes, independent of form ancestry."""

    verdict: ExternalLayoutArtifactAuthenticityVerdict
    evidence_summary: _NONEMPTY


class ExternalLayoutOfficialPageMapping(_FrozenStrictModel):
    """One candidate page's one-based location in the pinned official source."""

    candidate_page: Annotated[int, Field(gt=0)]
    official_page: Annotated[int, Field(gt=0)]


class ExternalLayoutOfficialSourceEvidence(_FrozenStrictModel):
    """Offline-verifiable identity and page selection of an official publication."""

    authority: ExternalLayoutOfficialAuthority
    document_id: _NONEMPTY
    source_url: Annotated[str, Field(pattern=r"^https://")]
    sha256: _SHA256
    page_mapping: Annotated[tuple[ExternalLayoutOfficialPageMapping, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _candidate_pages_are_unique(self) -> ExternalLayoutOfficialSourceEvidence:
        candidate_pages = tuple(mapping.candidate_page for mapping in self.page_mapping)
        if len(candidate_pages) != len(set(candidate_pages)):
            raise ValueError("official page mapping must contain each candidate page once")
        expected_hosts = (
            frozenset({"sede.agenciatributaria.gob.es"})
            if self.authority == "aeat"
            else frozenset({"boe.es", "www.boe.es"})
        )
        if urlsplit(self.source_url).hostname not in expected_hosts:
            raise ValueError(f"{self.authority} official source URL must use an official host")
        return self


_EXPECTED_OFFICIAL_EVIDENCE_COORDINATES: Mapping[
    str,
    tuple[str, str, str, str, tuple[tuple[int, int], ...]],
] = {
    "036": (
        "boe",
        "BOE-A-2023-26632 Annex I",
        "https://www.boe.es/boe/dias/2023/12/29/pdfs/BOE-A-2023-26632.pdf",
        "97069814b634a6b87966e0b486956639b5a4dda36f0401c5c7f51fe12726cea3",
        ((1, 19), (2, 24), (3, 25), (4, 26)),
    ),
    "130": (
        "boe",
        "BOE-A-2015-1656 Annex I",
        "https://www.boe.es/boe/dias/2015/02/19/pdfs/BOE-A-2015-1656.pdf",
        "f62a61854eac561e96f689ebf11b8b2c75d418a6146a7f972e6e6a404a8063a0",
        ((1, 6),),
    ),
    "131": (
        "boe",
        "BOE-A-2015-1656 Annex II",
        "https://www.boe.es/boe/dias/2015/02/19/pdfs/BOE-A-2015-1656.pdf",
        "f62a61854eac561e96f689ebf11b8b2c75d418a6146a7f972e6e6a404a8063a0",
        ((1, 8),),
    ),
    "303": (
        "aeat",
        "AEAT IVA 2024 Manual, Chapter 9 Modelo 303 annex",
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/"
        "IVA_2024/Imagenes/Cap_9_303_es_es.pdf",
        "fd42e40bd4ddb6f737ce8007e6e72b101465292abcf76a9d2ba01c791539491d",
        ((1, 1), (2, 3), (3, 6)),
    ),
    "349": (
        "boe",
        "BOE-A-2010-5098 Annex I",
        "https://boe.es/boe/dias/2010/03/29/pdfs/BOE-A-2010-5098.pdf",
        "3e194f09e71174b115ccdd6627656259cbbfd2f18fd44147d9091527a3909c69",
        ((1, 13), (2, 15)),
    ),
}


class ExternalLayoutPairRenderEvidence(_FrozenStrictModel):
    """Digest-bound render relationship to the other member of a candidate pair."""

    counterpart_kind: ExternalLayoutCandidateKind
    counterpart_sha256: _SHA256
    comparison_method: ExternalLayoutPairComparisonMethod
    comparison_summary: _NONEMPTY


class ExternalLayoutOfficialBaseDerivation(_FrozenStrictModel):
    """Measured official-form ancestry without an official-byte authenticity claim."""

    verdict: ExternalLayoutOfficialBaseVerdict
    official_source: ExternalLayoutOfficialSourceEvidence
    comparison_method: ExternalLayoutOfficialComparisonMethod
    comparison_summary: _NONEMPTY
    pair_render: ExternalLayoutPairRenderEvidence


class ExternalLayoutRegistryApplicability(_FrozenStrictModel):
    """Whether the derived layout corresponds to an authored registry revision."""

    verdict: ExternalLayoutRegistryApplicabilityVerdict
    revision_id: _NONEMPTY | None

    @model_validator(mode="after")
    def _revision_matches_verdict(self) -> ExternalLayoutRegistryApplicability:
        has_authored_revision = self.verdict != "historical_layout_without_authored_revision"
        if has_authored_revision != (self.revision_id is not None):
            raise ValueError(
                "revision_id is required exactly when the applicability verdict names an authored revision"
            )
        return self


class ExternalLayoutAuthorityAdjudication(_FrozenStrictModel):
    """Independent artifact, official-base, and registry-applicability verdicts."""

    artifact_authenticity: ExternalLayoutArtifactAuthenticity
    official_base_derivation: ExternalLayoutOfficialBaseDerivation
    registry_applicability: ExternalLayoutRegistryApplicability


class ExternalLayoutContent(_FrozenStrictModel):
    """Content address of the exact downloaded byte stream."""

    sha256: _SHA256
    size_bytes: Annotated[int, Field(gt=0)]


class ObservedDocumentInfo(RootModel[Mapping[str, str]]):
    """DocInfo observed in the PDF, recorded as mutable metadata, not authority."""

    model_config = ConfigDict(frozen=True, strict=True)


class ExternalLayoutPdfProperties(_FrozenStrictModel):
    """Reproducible physical properties of a readable PDF."""

    version: Annotated[str, Field(pattern=r"^\d\.\d$")]
    header_version: Annotated[str, Field(pattern=r"^\d\.\d$")]
    page_count: Annotated[int, Field(gt=0)]
    page_sizes_points: tuple[tuple[float, float], ...]
    encrypted: bool
    acroform_top_level_field_count: Annotated[int, Field(ge=0)]
    acroform_nonempty_value_count: Annotated[int, Field(ge=0)]
    document_info: ObservedDocumentInfo

    @model_validator(mode="after")
    def _page_sizes_match_count(self) -> ExternalLayoutPdfProperties:
        if len(self.page_sizes_points) != self.page_count:
            raise ValueError("page_sizes_points length must equal page_count")
        if any(width <= 0 or height <= 0 for width, height in self.page_sizes_points):
            raise ValueError("every PDF page size must be positive")
        return self


class ExternalLayoutObservations(_FrozenStrictModel):
    """Identity and text observations derived from extracted PDF text."""

    text_layer_character_count: Annotated[int, Field(ge=0)]
    nif_like_match_count: Annotated[int, Field(ge=0)]
    iban_like_match_count: Annotated[int, Field(ge=0)]
    email_like_match_count: Annotated[int, Field(ge=0)]
    printed_placeholder_justificante_number_present: bool
    value_observation: _NONEMPTY


class ExternalLayoutCandidate(_FrozenStrictModel):
    """Strict sidecar for one external layout candidate."""

    modelo: ExternalLayoutModelo
    candidate_kind: ExternalLayoutCandidateKind
    source_page_url: _NONEMPTY
    source_pdf_url: _NONEMPTY
    retrieved_on: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    source_chain: ExternalLayoutSourceChain
    content: ExternalLayoutContent
    pdf: ExternalLayoutPdfProperties
    observations: ExternalLayoutObservations
    limitations: Annotated[tuple[_NONEMPTY, ...], Field(min_length=1)]
    authority_adjudication: ExternalLayoutAuthorityAdjudication

    @model_validator(mode="after")
    def _source_urls_and_limitations_are_bound_to_candidate(self) -> ExternalLayoutCandidate:
        expected_page = f"https://fiscalbot.es/modelos-tributarios/modelo-{self.modelo}/"
        suffix = "_rellenable" if self.candidate_kind == "fillable" else ""
        expected_pdf = f"https://fiscalbot.es/assets/pdf/Modelo{self.modelo}{suffix}.pdf?v=3"
        if self.source_page_url != expected_page:
            raise ValueError(f"source_page_url must be {expected_page!r}")
        if self.source_pdf_url != expected_pdf:
            raise ValueError(f"source_pdf_url must be {expected_pdf!r}")
        if not any("do not establish AEAT provenance" in item for item in self.limitations):
            raise ValueError("limitations must disclaim AEAT provenance")
        if not any(
            phrase in item
            for item in self.limitations
            for phrase in ("cannot ground populated-value placement", "does not ground populated-value placement")
        ):
            raise ValueError("limitations must retain the populated-value placement gap")
        derivation = self.authority_adjudication.official_base_derivation
        mapped_pages = frozenset(mapping.candidate_page for mapping in derivation.official_source.page_mapping)
        expected_pages = frozenset(range(1, self.pdf.page_count + 1))
        if mapped_pages != expected_pages:
            raise ValueError("official page mapping must cover every candidate page exactly once")
        official_source = derivation.official_source
        observed_coordinate = (
            official_source.authority,
            official_source.document_id,
            official_source.source_url,
            official_source.sha256,
            tuple((mapping.candidate_page, mapping.official_page) for mapping in official_source.page_mapping),
        )
        if observed_coordinate != _EXPECTED_OFFICIAL_EVIDENCE_COORDINATES[self.modelo]:
            raise ValueError(
                f"modelo {self.modelo} official source evidence must match its reviewed coordinate",
            )
        pair_render = derivation.pair_render
        expected_counterpart = "fillable" if self.candidate_kind == "plain" else "plain"
        if pair_render.counterpart_kind != expected_counterpart:
            raise ValueError(f"pair_render counterpart_kind must be {expected_counterpart!r}")
        return self


def load_external_layout_candidate(sidecar_path: Path) -> ExternalLayoutCandidate:
    """Load one sidecar and bind its modelo/kind to its physical location."""
    candidate = ExternalLayoutCandidate.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
    expected_sidecar_name = f"{candidate.candidate_kind}.json"
    if sidecar_path.name != expected_sidecar_name:
        raise ValueError(f"candidate kind {candidate.candidate_kind!r} requires {expected_sidecar_name!r}")
    if sidecar_path.parent.name != candidate.modelo:
        raise ValueError(
            f"sidecar modelo {candidate.modelo!r} does not match directory {sidecar_path.parent.name!r}",
        )
    pdf_path = sidecar_path.with_suffix(".pdf")
    if pdf_path.name != f"{candidate.candidate_kind}.pdf":
        raise ValueError(f"candidate kind {candidate.candidate_kind!r} requires a same-stem PDF")
    return candidate


def _pdf_version(catalog: Mapping[str, object], header_version: str) -> str:
    declared = catalog.get("Version")
    if declared is None:
        return header_version
    name = getattr(declared, "name", None)
    return str(name if name is not None else declared).removeprefix("/")


def _acroform_counts(catalog: Mapping[str, object]) -> tuple[int, int]:
    acroform_ref = catalog.get("AcroForm")
    if acroform_ref is None:
        return (0, 0)
    acroform = resolve1(acroform_ref)
    fields = resolve1(acroform.get("Fields", [])) if isinstance(acroform, dict) else []
    if not isinstance(fields, list):
        return (0, 0)

    def nonempty_value_count(field_refs: list[object]) -> int:
        count = 0
        for field_ref in field_refs:
            field = resolve1(field_ref)
            if not isinstance(field, dict):
                continue
            value = resolve1(field.get("V")) if field.get("V") is not None else None
            if isinstance(value, bytes):
                rendered = value.decode("utf-8", errors="replace")
            else:
                rendered = str(getattr(value, "name", value)) if value is not None else ""
            if rendered not in {"", "Off"}:
                count += 1
            children = resolve1(field.get("Kids", []))
            if isinstance(children, list):
                count += nonempty_value_count(children)
        return count

    return (len(fields), nonempty_value_count(fields))


def _document_info(document: pdfplumber.PDF) -> dict[str, str]:
    metadata = {str(key): str(value) for key, value in (document.metadata or {}).items()}
    raw_info = document.doc.info[0] if document.doc.info else {}
    for key, value in raw_info.items():
        if not isinstance(value, bytes):
            continue
        if value.startswith(b"\xff\xfe"):
            metadata[str(key)] = value.decode("utf-16-le").removeprefix("\ufeff")
        elif value.startswith(b"\xfe\xff"):
            metadata[str(key)] = value.decode("utf-16-be").removeprefix("\ufeff")
    return metadata


def observe_external_layout_candidate(
    pdf_path: Path,
) -> tuple[ExternalLayoutContent, ExternalLayoutPdfProperties, ExternalLayoutObservations]:
    """Measure the sidecar contract directly from one readable PDF."""
    data = pdf_path.read_bytes()
    header_match = _PDF_HEADER_RE.match(data)
    if header_match is None:
        raise ValueError(f"{pdf_path.name}: bytes do not begin with a PDF header")
    header_version = header_match.group(1).decode("ascii")

    with pdfplumber.open(str(pdf_path)) as document:
        pages = tuple((float(page.width), float(page.height)) for page in document.pages)
        text_layer = "\n".join(page.extract_text() or "" for page in document.pages)
        top_level_count, nonempty_count = _acroform_counts(document.doc.catalog)
        metadata = _document_info(document)
        pdf = ExternalLayoutPdfProperties(
            version=_pdf_version(document.doc.catalog, header_version),
            header_version=header_version,
            page_count=len(document.pages),
            page_sizes_points=pages,
            encrypted=getattr(document.doc, "encryption", None) is not None,
            acroform_top_level_field_count=top_level_count,
            acroform_nonempty_value_count=nonempty_count,
            document_info=ObservedDocumentInfo(metadata),
        )

    content = ExternalLayoutContent(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
    observations = ExternalLayoutObservations(
        text_layer_character_count=len(text_layer),
        nif_like_match_count=len(_NIF_LIKE_RE.findall(text_layer)),
        iban_like_match_count=len(_IBAN_LIKE_RE.findall(text_layer)),
        email_like_match_count=len(_EMAIL_LIKE_RE.findall(text_layer)),
        printed_placeholder_justificante_number_present="1234567890" in text_layer,
        value_observation="observed from committed PDF bytes",
    )
    return content, pdf, observations


def physical_candidate_mismatches(sidecar_path: Path) -> tuple[str, ...]:
    """Return every sidecar disagreement with its adjacent physical PDF."""
    candidate = load_external_layout_candidate(sidecar_path)
    content, pdf, observations = observe_external_layout_candidate(sidecar_path.with_suffix(".pdf"))
    mismatches: list[str] = []
    if content != candidate.content:
        mismatches.append("content digest or size")
    if pdf != candidate.pdf:
        mismatches.append("PDF physical properties or observed DocInfo")
    observed_counts = observations.model_dump(exclude={"value_observation"})
    declared_counts = candidate.observations.model_dump(exclude={"value_observation"})
    if observed_counts != declared_counts:
        mismatches.append("text or identity observations")
    pair_render = candidate.authority_adjudication.official_base_derivation.pair_render
    counterpart_path = sidecar_path.parent / f"{pair_render.counterpart_kind}.pdf"
    observed_counterpart_sha256 = hashlib.sha256(counterpart_path.read_bytes()).hexdigest()
    if observed_counterpart_sha256 != pair_render.counterpart_sha256:
        mismatches.append("counterpart content digest")
    return tuple(mismatches)


def external_layout_source_class_is_non_authoritative() -> bool:
    """State the non-enrolment invariant without extending provenance taxonomy."""
    return (
        EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION not in RECOGNISED_FIXTURE_PROVENANCES
        and EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION != AEAT_PUBLISHED_FACSIMILE_CLASSIFICATION
    )


__all__ = [
    "AEAT_PUBLISHED_FACSIMILE_CLASSIFICATION",
    "EXTERNAL_LAYOUT_CANDIDATE_KINDS",
    "EXTERNAL_LAYOUT_MODELOS",
    "EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION",
    "ExternalLayoutArtifactAuthenticity",
    "ExternalLayoutArtifactAuthenticityVerdict",
    "ExternalLayoutAuthorityAdjudication",
    "ExternalLayoutCandidate",
    "ExternalLayoutCandidateKind",
    "ExternalLayoutContent",
    "ExternalLayoutModelo",
    "ExternalLayoutObservations",
    "ExternalLayoutOfficialAuthority",
    "ExternalLayoutOfficialBaseDerivation",
    "ExternalLayoutOfficialBaseVerdict",
    "ExternalLayoutOfficialComparisonMethod",
    "ExternalLayoutOfficialPageMapping",
    "ExternalLayoutOfficialSourceEvidence",
    "ExternalLayoutPairComparisonMethod",
    "ExternalLayoutPairRenderEvidence",
    "ExternalLayoutPdfProperties",
    "ExternalLayoutRegistryApplicability",
    "ExternalLayoutRegistryApplicabilityVerdict",
    "ExternalLayoutSourceChain",
    "ObservedDocumentInfo",
    "external_layout_source_class_is_non_authoritative",
    "load_external_layout_candidate",
    "observe_external_layout_candidate",
    "physical_candidate_mismatches",
]
