"""Development-only derivation of normative-corpus provenance from source bytes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance

__all__ = [
    "classify_normative_corpus_bytes",
    "classify_normative_corpus_provenance",
    "resolve_normative_corpus_path",
]

_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_PACKAGED_DATA_ROOT: Final = Path("src") / "cadrumo" / "_data"
_EXCERPT_HEADER: Final = b"Official BOE consolidated source excerpt"
_BOE_DOCUMENT_ID: Final = re.compile(rb"\bBOE-A-\d{4}-\d+\b")
_BOE_STRUCTURAL_MARKUP: Final = re.compile(
    rb"\bclass\s*=\s*['\"][^'\"]*\b(?:articulo|parrafo)\b[^'\"]*['\"]", re.IGNORECASE
)


def resolve_normative_corpus_path(source_root: Path, corpus_ref: str) -> Path | None:
    """Resolve one normative authoring input without allowing root escape."""
    corpus_path = corpus_ref.partition("#")[0]
    if not corpus_path.startswith(_NORMATIVES_TREE_PREFIX):
        return None
    root = source_root.resolve()
    direct_normatives = (root / "corpus" / "normatives").resolve()
    packaged_data_root = (root / _PACKAGED_DATA_ROOT).resolve()
    packaged_normatives = (packaged_data_root / "corpus" / "normatives").resolve()
    direct = (root / corpus_path).resolve()
    packaged = (root / _PACKAGED_DATA_ROOT / corpus_path).resolve()
    if not (
        root in direct_normatives.parents
        and (packaged_data_root == root or root in packaged_data_root.parents)
        and packaged_data_root in packaged_normatives.parents
        and direct_normatives in direct.parents
        and packaged_normatives in packaged.parents
    ):
        raise RegistryValidationError(f"normative corpus target {corpus_ref!r} escapes the normative corpus tree")
    path = direct if direct.is_file() else packaged
    if not path.is_file():
        raise RegistryValidationError(f"normative corpus target {corpus_ref!r} missing corpus file {corpus_path!r}")
    return path


def classify_normative_corpus_provenance(source_root: Path, corpus_ref: str) -> NormativeCorpusProvenance:
    """Classify source evidence while development tooling still owns the root."""
    path = resolve_normative_corpus_path(source_root, corpus_ref)
    return (
        NormativeCorpusProvenance.OUT_OF_SCOPE if path is None else classify_normative_corpus_bytes(path.read_bytes())
    )


def classify_normative_corpus_bytes(payload: bytes) -> NormativeCorpusProvenance:
    """Classify an authored corpus payload for a published authority projection."""
    if _EXCERPT_HEADER in payload or _BOE_DOCUMENT_ID.search(payload):
        return NormativeCorpusProvenance.BOE_ATTESTED
    if _BOE_STRUCTURAL_MARKUP.search(payload):
        return NormativeCorpusProvenance.BOE_PRESUMPTIVE
    return NormativeCorpusProvenance.AUTHORED
