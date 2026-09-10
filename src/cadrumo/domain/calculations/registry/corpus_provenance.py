"""Derived provenance for bundled normative-corpus text.

The classification is deliberately a property of the corpus bytes, not a
registry declaration.  It distinguishes a BOE attribution carried by the
file itself from BOE-shaped markup, which is useful evidence but remains
authorable, and from text carrying neither signal.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Final

from .errors import RegistryValidationError

__all__ = [
    "NormativeCorpusProvenance",
    "classify_normative_corpus_provenance",
    "resolve_normative_corpus_path",
]


class NormativeCorpusProvenance(StrEnum):
    """The strongest provenance evidence derivable from a corpus target."""

    BOE_ATTESTED = "boe_attested"
    """The bytes name BOE directly through an excerpt header or document id."""

    BOE_PRESUMPTIVE = "boe_presumptive"
    """The bytes carry BOE structural markup but no direct BOE attribution."""

    AUTHORED = "authored"
    """The bytes carry neither direct attribution nor BOE structural markup."""

    OUT_OF_SCOPE = "out_of_scope"
    """The target is not in the normative corpus, so it is not classified here."""


_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_PACKAGED_DATA_ROOT: Final = Path("src") / "cadrumo" / "_data"
_EXCERPT_HEADER: Final = b"Official BOE consolidated source excerpt"
_BOE_DOCUMENT_ID: Final = re.compile(rb"\bBOE-A-\d{4}-\d+\b")
_BOE_STRUCTURAL_MARKUP: Final = re.compile(
    rb"\bclass\s*=\s*['\"][^'\"]*\b(?:articulo|parrafo)\b[^'\"]*['\"]",
    re.IGNORECASE,
)


def resolve_normative_corpus_path(source_root: Path, corpus_ref: str) -> Path | None:
    """Resolve a normative corpus target beneath ``source_root``.

    ``corpus_ref`` may include a legal-reference anchor; classification is a
    file property, so the anchor is intentionally ignored.  A target outside
    ``corpus/normatives/`` is returned as ``None`` rather than being read by
    this classifier.  A normative target must resolve to a regular file below
    the supplied source root (or its packaged-data location), otherwise the
    caller receives the same registry validation failure shape as other corpus
    readers.
    """
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
    """Classify provenance derived from one normative corpus file's bytes.

    Direct BOE attribution wins over the weaker structural signal.  The
    ``boe_presumptive`` result intentionally does not claim that markup alone
    proves provenance; callers that need filing-grade authority must apply the
    stricter policy at their owning validation boundary.
    """
    path = resolve_normative_corpus_path(source_root, corpus_ref)
    if path is None:
        return NormativeCorpusProvenance.OUT_OF_SCOPE

    payload = path.read_bytes()
    if _EXCERPT_HEADER in payload or _BOE_DOCUMENT_ID.search(payload):
        return NormativeCorpusProvenance.BOE_ATTESTED
    if _BOE_STRUCTURAL_MARKUP.search(payload):
        return NormativeCorpusProvenance.BOE_PRESUMPTIVE
    return NormativeCorpusProvenance.AUTHORED
