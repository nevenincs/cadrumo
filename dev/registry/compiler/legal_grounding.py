"""Development-only verification of authored legal corpus evidence.

The shipped authority artifact contains typed legal references and their review
claims.  Reading, resolving, and grading the mutable corpus that produced
those claims is publisher work and therefore lives here, outside ``src``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.corpus_text import (
    CorpusAnchorResolutionError,
    corpus_redaction_marks,
    extracted_unit_count,
    normalise_corpus_text,
    resolve_anchored_extracted_unit,
)
from cadrumo.core.hashing import blake2b_hex
from cadrumo.domain.calculations.registry.corpus_provenance import (
    NormativeCorpusProvenance,
    classify_normative_corpus_provenance,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import CorpusTier
from cadrumo.domain.calculations.registry.schema_references import LegalReference

__all__ = [
    "PROVISION_SUFFIXED_FILENAME",
    "legal_reference_quotes_corpus",
    "published_legal_evidence_text",
    "verify_legal_catalogue",
    "verify_legal_catalogue_grounding",
    "verify_legal_reference_grounding",
]

_DISPOSITIVE_KINDS = frozenset(
    {
        "ley",
        "real_decreto",
        "real_decreto_legislativo",
        "real_decreto_ley",
        "orden",
        "reglamento",
        "acuerdo_internacional",
        "directiva",
    }
)
_DISPOSITIVE_CONTENT_SIGNAL = re.compile(
    r"articulo\\s+(?:\\d+|primero|segundo|tercero|cuarto|quinto|sexto|septimo|octavo|noveno|decimo|unico)\\.|disposicion\\s+(?:transitoria|final|adicional|derogatoria)\\s+\\w+\\."
)
_MODELO_ANCHOR = re.compile(r"^modelo-\\d+$")
_FULL_CONSOLIDATED_SIZE_FLOOR: Final = 5000
PROVISION_SUFFIXED_FILENAME = re.compile(r"-(art|apartado|anexo|da|dt|df|se|pr|ar|redacciones)[-.]")


@dataclass(frozen=True, slots=True)
class _PresumptiveNormativeCorpusException:
    reason: str
    reviewed_reference: str
    reviewed_by: str
    reviewed_at: str


def _exception(reference: str, reviewer: str, reviewed_at: str) -> _PresumptiveNormativeCorpusException:
    return _PresumptiveNormativeCorpusException(
        reason="BOE structural markup is present but the file has no direct BOE attribution marker.",
        reviewed_reference=reference,
        reviewed_by=reviewer,
        reviewed_at=reviewed_at,
    )


_REVIEWED_PRESUMPTIVE_NORMATIVE_CORPUS: Final = {
    **{
        f"corpus/normatives/html/ley-37-1992-art-{article}.html": _exception(
            f"ley-37-1992:art-{article}", "operator", "2026-05-21"
        )
        for article in ("122", "123", "124", "94", "95")
    },
    **{
        f"corpus/normatives/html/orden-eha-789-2010-art-{article}.html": _exception(
            f"orden-eha-789-2010:art-{article}", "operator", "2026-05-06"
        )
        for article in ("1", "4")
    },
    **{
        f"corpus/normatives/html/orden-hap-2250-2015-art-{article}.html": _exception(
            f"orden-hap-2250-2015:art-{article}", "operator", "2026-05-06"
        )
        for article in ("2", "3", "4", "5")
    },
    **{
        f"corpus/normatives/html/rd-1624-1992-art-{article}.html": _exception(
            f"rd-1624-1992:art-{article}", "agent-review", "2026-05-19"
        )
        for article in ("29", "30")
    },
}


def verify_legal_reference_grounding(reference: LegalReference, *, source_root: Path) -> None:
    """Prove one authored legal reference against its source corpus."""
    if reference.kind == "manual":
        _validate_manual_legal_reference(reference, source_root)
    _validate_legal_corpus_provenance(reference, source_root)
    if reference.required_text or reference.forbidden_text:
        _validate_legal_corpus_clauses(reference, source_root)
    _validate_dispositive_content(reference, source_root)
    _validate_corpus_tier_declaration(reference, source_root)


def verify_legal_reference(reference: LegalReference, *, source_root: Path) -> None:
    """Prove source grounding and filing eligibility before publication."""
    from cadrumo.domain.calculations.registry.legal import verify_legal_reference as verify_runtime_eligibility

    verify_runtime_eligibility(reference)
    verify_legal_reference_grounding(reference, source_root=source_root)


def verify_legal_catalogue_grounding(legal: Mapping[str, LegalReference], *, source_root: Path) -> None:
    _verify_catalogue(legal, source_root=source_root, include_review=False)


def verify_legal_catalogue(legal: Mapping[str, LegalReference], *, source_root: Path) -> None:
    _verify_catalogue(legal, source_root=source_root, include_review=True)


def _verify_catalogue(legal: Mapping[str, LegalReference], *, source_root: Path, include_review: bool) -> None:
    failures: list[str] = []
    for ref_id, reference in legal.items():
        if ref_id != reference.id:
            failures.append(f"legal catalogue key {ref_id!r} does not match reference id {reference.id!r}")
        try:
            if include_review:
                verify_legal_reference(reference)
            verify_legal_reference_grounding(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        prefix = (
            "legal catalogue validation failed" if include_review else "legal catalogue grounding validation failed"
        )
        raise RegistryValidationError(prefix + ":\\n" + "\\n".join(f" - {failure}" for failure in failures))


def legal_reference_quotes_corpus(reference: LegalReference, quotation: str, *, source_root: Path) -> bool:
    return bool(quotation.strip()) and normalise_corpus_text(quotation) in _legal_corpus_text(source_root, reference)


def published_legal_evidence_text(reference: LegalReference, *, source_root: Path) -> str:
    """Project one already-validated anchor into the signed runtime artifact.

    The caller must have completed full compiler validation first.  This helper
    intentionally remains development-only because it reads the mutable corpus
    and extracted sidecar.
    """
    return _legal_corpus_text(source_root, reference)


def _validate_manual_legal_reference(reference: LegalReference, source_root: Path) -> None:
    path = (source_root / reference.corpus_ref.split("#", 1)[0]).resolve()
    if not path.is_file():
        return
    try:
        from cadrumo.domain.manuals.schema import Section

        Section.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} manual section JSON validation failed: {exc}"
        ) from exc


def _validate_legal_corpus_clauses(reference: LegalReference, source_root: Path) -> None:
    corpus_text = _legal_corpus_text(source_root, reference)
    for required in reference.required_text:
        if normalise_corpus_text(required) not in corpus_text:
            raise RegistryValidationError(
                f"legal reference {reference.id!r} corpus text missing required text {required!r}"
            )
    for forbidden in reference.forbidden_text:
        if normalise_corpus_text(forbidden) in corpus_text:
            raise RegistryValidationError(
                f"legal reference {reference.id!r} corpus text contains forbidden text {forbidden!r}"
            )


def _validate_legal_corpus_provenance(reference: LegalReference, source_root: Path) -> None:
    provenance = classify_normative_corpus_provenance(source_root, reference.corpus_ref)
    if provenance is NormativeCorpusProvenance.AUTHORED:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} cites authored normative corpus text; filing-grade legal authority requires BOE-attested evidence."
        )
    if (
        provenance is NormativeCorpusProvenance.BOE_PRESUMPTIVE
        and reference.corpus_ref.partition("#")[0] not in _REVIEWED_PRESUMPTIVE_NORMATIVE_CORPUS
    ):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} cites BOE-presumptive normative corpus text with no reviewed per-file exception."
        )


def _validate_dispositive_content(reference: LegalReference, source_root: Path) -> None:
    if (
        reference.kind in _DISPOSITIVE_KINDS
        and _MODELO_ANCHOR.match(reference.corpus_ref.partition("#")[2])
        and not _DISPOSITIVE_CONTENT_SIGNAL.search(_legal_corpus_text(source_root, reference))
    ):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} cites corpus text with no dispositive article or disposición of its own"
        )


def _validate_corpus_tier_declaration(reference: LegalReference, source_root: Path) -> None:
    if reference.corpus_tier is None:
        return
    path = (source_root / reference.corpus_ref.split("#", 1)[0]).resolve()
    if not path.is_file():
        return
    provision_suffixed = bool(PROVISION_SUFFIXED_FILENAME.search(path.name))
    if reference.corpus_tier is CorpusTier.FULL_CONSOLIDATED and (
        provision_suffixed or path.stat().st_size < _FULL_CONSOLIDATED_SIZE_FLOOR
    ):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} declares corpus_tier='full_consolidated' but {path.name!r} is not a full consolidated text"
        )
    if (
        reference.corpus_tier is CorpusTier.PROVISION_EXCERPT
        and not provision_suffixed
        and not _DISPOSITIVE_CONTENT_SIGNAL.search(_legal_corpus_text(source_root, reference))
    ):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} declares corpus_tier='provision_excerpt' but its corpus text carries no dispositive article or disposición of its own"
        )


_LEGAL_CORPUS_CACHE: dict[tuple[str, int, int, str, str, tuple[str, ...]], str] = {}


def _legal_corpus_text(source_root: Path, reference: LegalReference) -> str:
    path_text, _, anchor = reference.corpus_ref.partition("#")
    root = source_root.resolve()
    path = (root / path_text).resolve()
    if root not in path.parents and path != root:
        raise RegistryValidationError(f"legal reference {reference.id!r} escapes repository root")
    sidecar = path.with_name(path.name + ".extracted.json").resolve()
    if root not in sidecar.parents and sidecar != root:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar escapes repository root"
        )
    if not sidecar.is_file():
        raise RegistryValidationError(
            f"legal reference {reference.id!r} missing extracted corpus sidecar {path_text!r}"
        )
    _assert_redactions_are_not_fused(path, sidecar, reference, path_text)
    stat = sidecar.stat()
    try:
        digest = blake2b_hex(sidecar.read_bytes())
    except OSError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar could not be fingerprinted: {exc}"
        ) from exc
    key = (str(sidecar), stat.st_size, stat.st_mtime_ns, digest, anchor, reference.required_text)
    if key not in _LEGAL_CORPUS_CACHE:
        try:
            _LEGAL_CORPUS_CACHE[key] = normalise_corpus_text(
                resolve_anchored_extracted_unit(
                    sidecar, anchor=anchor, required_text=reference.required_text, include_title=True
                )
            )
        except CorpusAnchorResolutionError as exc:
            raise RegistryValidationError(
                f"legal reference {reference.id!r} cannot resolve one corpus unit for anchor {anchor!r}"
            ) from exc
    return _LEGAL_CORPUS_CACHE[key]


def _assert_redactions_are_not_fused(document: Path, sidecar: Path, reference: LegalReference, path_text: str) -> None:
    if not document.is_file():
        return
    try:
        marks = corpus_redaction_marks(document.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} corpus document {path_text!r} could not be read: {exc}"
        ) from exc
    if len(marks) < 2:
        return
    try:
        units = extracted_unit_count(sidecar)
    except CorpusAnchorResolutionError as exc:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} extracted corpus sidecar could not be counted: {exc}"
        ) from exc
    raise RegistryValidationError(
        f"legal reference {reference.id!r} cites {path_text!r}, which declares {len(marks)} dated redactions collapsed into {units} extracted unit(s)"
        "; cite a consolidated current-text document instead, or reduce the capture to the redaction in force"
    )
