"""Filesystem fingerprints for registry source-evidence cache keys.

Also owns :func:`derive_justificante_corpus_candidate`, the single checkout-gated
derivation of the dev-only ``declaracion_pdf`` specimen corpus directory shared by
:mod:`cadrumo.domain.calculations.registry._validate` (the specimen/round-trip
gates) and this module's own fingerprint collection. A source checkout keeps the
historical co-located ``tests/fixtures/justificantes`` layout; an installed
distribution ships no ``tests/`` tree at all, so the derivation refuses to probe
that repo-shaped path outside a checkout rather than silently guessing at it. See
:class:`JustificanteCorpusUnavailableAdvisory` for the non-blocking signal this
produces when the corpus cannot be derived.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....core.paths import RunMode, StateRootInputs, detect_run_mode, live_state_root_inputs

SourceEvidenceFingerprint = tuple[tuple[str, int, int], ...]

__all__ = (
    "JustificanteCorpusUnavailableAdvisory",
    "SourceEvidenceFingerprint",
    "collect_source_evidence_fingerprints",
    "derive_justificante_corpus_candidate",
)


@dataclass(frozen=True, slots=True)
class JustificanteCorpusUnavailableAdvisory:
    """Non-blocking advisory: the declaracion_pdf specimen corpus could not be derived.

    :func:`derive_justificante_corpus_candidate` returns this instead of a silent
    ``None`` whenever the ``tests/fixtures/justificantes`` dev-fixture directory
    is not reachable. Nothing in this domain layer raises for this condition: the
    ``declaracion_pdf`` specimen and round-trip gates in
    ``_validate_extraction_profiles`` (dispatched from
    ``_validate_record_sections.validate_extraction_profile_section``, which only
    runs them when its ``corpus_root`` argument is not ``None``) simply do not
    execute for the affected validation pass. This record makes that fact
    introspectable — via
    :attr:`~cadrumo.domain.calculations.registry._validate.RegistryValidator.justificante_corpus_unavailable_advisory`
    — instead of an unexplained gap, so a caller (an operator-facing diagnostic, a
    repair report) can decide whether and how to surface it. It is not produced
    when a caller explicitly supplies ``justificante_corpus_root`` — that is a
    deliberate opt-out, not a silent derivation failure.

    Attributes:
        run_mode: Whether the process was classified as a source checkout or an
            installed distribution when derivation ran.
        probed_path: The dev-fixture directory that was checked and found absent,
            or ``None`` when no probe was attempted at all (an installed
            distribution ships no ``tests/`` tree to probe).
        reason: Human-readable explanation, safe to surface verbatim to an
            operator or in a diagnostic report.
    """

    run_mode: RunMode
    probed_path: Path | None
    reason: str


def collect_source_evidence_fingerprints(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None = None,
    state_root_inputs: StateRootInputs | None = None,
) -> SourceEvidenceFingerprint:
    """Return ``(path, size, mtime_ns)`` fingerprints for source evidence files."""
    roots = _source_evidence_roots(
        source_root,
        justificante_corpus_root=justificante_corpus_root,
        state_root_inputs=state_root_inputs,
    )
    fingerprints: list[tuple[str, int, int]] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            stat = path.stat()
            fingerprints.append((str(path), stat.st_size, stat.st_mtime_ns))
    return tuple(fingerprints)


def derive_justificante_corpus_candidate(
    source_root: Path,
    *,
    state_root_inputs: StateRootInputs | None = None,
) -> tuple[Path | None, JustificanteCorpusUnavailableAdvisory | None]:
    """Derive the dev-fixture specimen corpus directory, gated on :class:`RunMode`.

    Production callers pass ``source_root=bundled_path()``, which resolves to
    ``src/cadrumo/_data`` in a source checkout; the co-located
    ``tests/fixtures/justificantes`` directory is a legitimate dev-only specimen
    corpus there. An installed distribution ships no ``tests/`` tree at all, so
    probing that repo-shaped path outside a checkout is a guess, not a
    derivation — this function refuses to probe in that case rather than
    resolving a path that structurally cannot exist.

    Args:
        source_root: The source-data root to derive the corpus directory from
            (production callers pass ``bundled_path()``).
        state_root_inputs: Injectable :class:`~cadrumo.core.paths.StateRootInputs`
            seam. ``None`` (the live default) captures the running process's
            :class:`~cadrumo.core.paths.RunMode` via
            :func:`~cadrumo.core.paths.live_state_root_inputs`. Tests inject a
            deterministic ``installed`` or ``checkout`` context without
            mutating the ambient process.

    Returns:
        ``(candidate, None)`` when a real directory was resolved;
        ``(None, JustificanteCorpusUnavailableAdvisory(...))`` otherwise.
    """
    inputs = state_root_inputs if state_root_inputs is not None else live_state_root_inputs()
    run_mode = detect_run_mode(inputs)
    if run_mode is not RunMode.CHECKOUT:
        return None, JustificanteCorpusUnavailableAdvisory(
            run_mode=run_mode,
            probed_path=None,
            reason=(
                "run mode is installed, not checkout: an installed distribution ships no "
                "tests/ tree, so the declaracion_pdf specimen corpus is unavailable at runtime"
            ),
        )
    resolved = source_root.expanduser().resolve()
    if resolved.parent == resolved:
        return None, JustificanteCorpusUnavailableAdvisory(
            run_mode=run_mode,
            probed_path=None,
            reason=f"source_root {resolved} has no parent directory to derive a corpus root from",
        )
    candidate = resolved.parents[0] / "tests" / "fixtures" / "justificantes"
    if candidate.is_dir():
        return candidate, None
    return None, JustificanteCorpusUnavailableAdvisory(
        run_mode=run_mode,
        probed_path=candidate,
        reason=(
            f"source checkout detected but the dev-fixture specimen corpus directory "
            f"does not exist at {candidate}"
        ),
    )


def _source_evidence_roots(
    source_root: Path | None,
    *,
    justificante_corpus_root: Path | None,
    state_root_inputs: StateRootInputs | None = None,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if source_root is not None:
        resolved = source_root.expanduser().resolve()
        candidates.extend((resolved / "corpus", resolved / "src" / "cadrumo" / "_data" / "corpus"))
        derived_candidate, _advisory = derive_justificante_corpus_candidate(
            resolved,
            state_root_inputs=state_root_inputs,
        )
        if derived_candidate is not None:
            candidates.append(derived_candidate)
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
