"""Development-only derivation of normative-corpus provenance from source bytes."""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Final

from cadrumo.core.hashing import blake2b_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance
from dev.registry.compiler.corpus_source_location import PACKAGED_DATA_ROOT

__all__ = [
    "classify_normative_corpus_bytes",
    "classify_normative_corpus_provenance",
    "corpus_content_digest",
    "corpus_digest_pass",
    "resolve_normative_corpus_path",
]

_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_EXCERPT_HEADER: Final = b"Official BOE consolidated source excerpt"
_BOE_DOCUMENT_ID: Final = re.compile(rb"\bBOE-A-\d{4}-\d+\b")
_BOE_STRUCTURAL_MARKUP: Final = re.compile(
    rb"\bclass\s*=\s*['\"][^'\"]*\b(?:articulo|parrafo)\b[^'\"]*['\"]", re.IGNORECASE
)


@lru_cache(maxsize=32)
def _normative_roots(source_root: Path) -> tuple[Path, Path, Path, bool]:
    """Resolve one source root's normative tree roots once; every reference under it shares them."""
    root = source_root.resolve()
    direct_normatives = (root / "corpus" / "normatives").resolve()
    packaged_data_root = (root / PACKAGED_DATA_ROOT).resolve()
    packaged_normatives = (packaged_data_root / "corpus" / "normatives").resolve()
    contained = (
        root in direct_normatives.parents
        and (packaged_data_root == root or root in packaged_data_root.parents)
        and packaged_data_root in packaged_normatives.parents
    )
    return root, direct_normatives, packaged_normatives, contained


def resolve_normative_corpus_path(source_root: Path, corpus_ref: str) -> Path | None:
    """Resolve one normative authoring input without allowing root escape."""
    corpus_path = corpus_ref.partition("#")[0]
    if not corpus_path.startswith(_NORMATIVES_TREE_PREFIX):
        return None
    root, direct_normatives, packaged_normatives, contained = _normative_roots(source_root)
    direct = (root / corpus_path).resolve()
    packaged = (root / PACKAGED_DATA_ROOT / corpus_path).resolve()
    if not (contained and direct_normatives in direct.parents and packaged_normatives in packaged.parents):
        raise RegistryValidationError(f"normative corpus target {corpus_ref!r} escapes the normative corpus tree")
    path = direct if direct.is_file() else packaged
    if not path.is_file():
        raise RegistryValidationError(f"normative corpus target {corpus_ref!r} missing corpus file {corpus_path!r}")
    return path


def classify_normative_corpus_provenance(source_root: Path, corpus_ref: str) -> NormativeCorpusProvenance:
    """Classify source evidence while development tooling still owns the root."""
    path = resolve_normative_corpus_path(source_root, corpus_ref)
    if path is None:
        return NormativeCorpusProvenance.OUT_OF_SCOPE
    provenance = _PROVENANCE_BY_CONTENT.get(corpus_content_digest(path))
    if provenance is None:
        payload = path.read_bytes()
        provenance = classify_normative_corpus_bytes(payload)
        _PROVENANCE_BY_CONTENT[blake2b_hex(payload)] = provenance
    return provenance


_PROVENANCE_BY_CONTENT: dict[str, NormativeCorpusProvenance] = {}
"""Each classified corpus payload's provenance, keyed on the payload's content digest.

Provenance is decided by the file's bytes but asked per legal REFERENCE, and
references cite one file at many anchors: 732 declarations resolve to 388
files, and re-reading per reference scanned 415 MB of a 36.8 MB corpus. The
verdict is stored under the digest of the very bytes it was decided from, so a
rewrite that preserves size and mtime still reclassifies.
"""

_PASS_DIGESTS: ContextVar[dict[str, str] | None] = ContextVar("corpus_pass_digests", default=None)


@contextmanager
def corpus_digest_pass() -> Generator[None]:
    """Hash each corpus file at most once for the duration of one verification pass.

    Inside the pass a file is read and hashed on first use and its digest is
    reused by every later reference that cites it; the observations end with
    the pass, so no pass inherits another's view of the corpus. Outside a pass
    every call hashes the file's current bytes.
    """
    token = _PASS_DIGESTS.set({})
    try:
        yield
    finally:
        _PASS_DIGESTS.reset(token)


def corpus_content_digest(path: Path) -> str:
    """Return the content digest of one corpus file's bytes, never of its stat identity."""
    observed = _PASS_DIGESTS.get()
    key = str(path)
    if observed is not None and (digest := observed.get(key)) is not None:
        return digest
    digest = blake2b_hex(path.read_bytes())
    if observed is not None:
        observed[key] = digest
    return digest


def classify_normative_corpus_bytes(payload: bytes) -> NormativeCorpusProvenance:
    """Classify an authored corpus payload for a published authority projection."""
    if _EXCERPT_HEADER in payload or _BOE_DOCUMENT_ID.search(payload):
        return NormativeCorpusProvenance.BOE_ATTESTED
    if _BOE_STRUCTURAL_MARKUP.search(payload):
        return NormativeCorpusProvenance.BOE_PRESUMPTIVE
    return NormativeCorpusProvenance.AUTHORED
