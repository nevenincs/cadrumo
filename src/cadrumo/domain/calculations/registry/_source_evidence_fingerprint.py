"""Filesystem fingerprints for registry source-evidence cache keys."""

from __future__ import annotations

from pathlib import Path

SourceEvidenceFingerprint = tuple[tuple[str, int, int], ...]


def collect_source_evidence_fingerprints(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None = None,
) -> SourceEvidenceFingerprint:
    """Return ``(path, size, mtime_ns)`` fingerprints for source evidence files."""
    roots = _source_evidence_roots(source_root, justificante_corpus_root=justificante_corpus_root)
    fingerprints: list[tuple[str, int, int]] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            stat = path.stat()
            fingerprints.append((str(path), stat.st_size, stat.st_mtime_ns))
    return tuple(fingerprints)


def _source_evidence_roots(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if source_root is not None:
        resolved = source_root.expanduser().resolve()
        candidates.extend((resolved / "corpus", resolved / "src" / "cadrumo" / "_data" / "corpus"))
        if resolved.parent != resolved:
            candidates.append(resolved.parents[0] / "tests" / "fixtures" / "justificantes")
    if justificante_corpus_root is not None:
        candidates.append(justificante_corpus_root.expanduser().resolve())

    seen: set[Path] = set()
    roots: list[Path] = []
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen or not resolved_candidate.is_dir():
            continue
        seen.add(resolved_candidate)
        roots.append(resolved_candidate)
    return tuple(roots)
