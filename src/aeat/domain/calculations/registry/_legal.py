"""Legal catalogue helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from ._citation_blocklist import CitationSource, find_known_bad
from ._errors import RegistryValidationError
from ._schema import LegalReference
from ._text import normalise_corpus_text

_SOURCE_BY_KIND = cast(
    "Mapping[str, CitationSource]",
    {
        "ley": "ley",
        "real_decreto": "reglamento",
        "real_decreto_ley": "reglamento",
        "orden": "orden",
        "reglamento": "reglamento",
        "manual": "manual",
        "instruction": "instruction",
    },
)


def verify_legal_reference(reference: LegalReference, *, source_root: Path | None = None) -> None:
    """Verify one already parsed legal reference is filing-grade."""

    if reference.review_status != "reviewed":
        raise RegistryValidationError(f"legal reference {reference.id!r} is not reviewed")
    if reference.evidence_tier != "legal_authority":
        raise RegistryValidationError(f"legal reference {reference.id!r} is not legal authority")
    if reference.article is None:
        return
    source = _SOURCE_BY_KIND.get(reference.kind)
    if source is None:
        return
    role_text = " ".join(part for part in (reference.section, reference.notes) if part)
    if role_text and (known_bad := find_known_bad(source, reference.article, role_text)):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} matches known-bad citation: {known_bad.reason}"
        )
    if reference.required_text and source_root is not None:
        corpus_text = _legal_corpus_text(source_root, reference)
        for required in reference.required_text:
            if normalise_corpus_text(required) not in corpus_text:
                raise RegistryValidationError(
                    f"legal reference {reference.id!r} corpus text missing required text {required!r}"
                )


def verify_legal_catalogue(legal: Mapping[str, LegalReference], *, source_root: Path | None = None) -> None:
    """Verify every legal reference in a shared legal catalogue."""

    failures: list[str] = []
    for ref_id, reference in legal.items():
        if ref_id != reference.id:
            failures.append(f"legal catalogue key {ref_id!r} does not match reference id {reference.id!r}")
        try:
            verify_legal_reference(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        raise RegistryValidationError("legal catalogue validation failed:\n" + "\n".join(f" - {f}" for f in failures))


def _legal_corpus_text(source_root: Path, reference: LegalReference) -> str:
    path_text = reference.corpus_ref.split("#", 1)[0]
    path = (source_root / path_text).resolve()
    repo_root = source_root.resolve()
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"legal reference {reference.id!r} escapes repository root")
    if not path.is_file():
        raise RegistryValidationError(f"legal reference {reference.id!r} missing corpus file {path_text!r}")
    return normalise_corpus_text(path.read_text(encoding="utf-8", errors="replace"))
