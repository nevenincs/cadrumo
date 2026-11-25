"""Revision-scoped source applicability windows checked while building a registry snapshot.

A source cited by a revision must apply somewhere inside the span the revision covers. This module
holds the check and the continuity, succession and deadline-window reasoning behind it; the
snapshot builder runs it as one of its cross-domain stages.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .casilla_structural_succession import CasillaStructuralSuccession, endpoint_source_context_failures
from .errors import RegistryValidationError
from .ids import RevisionId
from .schema import ModeloDefinition, ModeloRevision
from .schema_catalogues import RegistryCatalogues
from .schema_references import SourceReference
from .schema_surfaces import CasillaContinuidadEvolutionDefinition
from .snapshot_references import collect_snapshot_ref_ids
from .temporal import ModeloRevisionDirectory, RevisionSelectionMetadata


def _deadline_window_source_spans(
    revision: ModeloRevision,
) -> dict[str, tuple[tuple[date, date], ...]]:
    """Map every deadline-window-cited source to the spans those windows cover.

    A period's filing deadline lawfully falls after the period itself ends: a
    fourth-quarter return is filed in the January of the following year, so the
    calendario that states its deadline is the FOLLOWING year's. Intersecting
    such a ref with the revision's own devengo window would reject the correct
    citation and push an author toward a calendario that does not state the
    deadline at all -- fabricated grounding in the name of a window check. The
    window's own ``opens_on``/``closes_on`` span is the axis that citation has
    to defend, so it is checked against that instead.

    Only a window's own ``source_refs`` earn the window span. Its
    ``applicability_conditions`` ground WHO must file rather than WHEN, so their
    refs stay on the revision span.
    """
    spans: dict[str, list[tuple[date, date]]] = {}
    for window in revision.deadline_windows:
        for source_id in window.source_refs:
            spans.setdefault(source_id, []).append((window.opens_on, window.closes_on))
    return {source_id: tuple(windows) for source_id, windows in spans.items()}


def _construct_source_ids_without_deadline_closure(revision: ModeloRevision) -> set[str]:
    """Return construct sources that are not inherited only from deadline members."""
    windows_by_id = {window.id: window for window in revision.deadline_windows}
    source_ids: set[str] = set()
    for construct in revision.constructs:
        deadline_source_ids = {
            source_id for window_id in construct.deadline_windows for source_id in windows_by_id[window_id].source_refs
        }
        source_ids.update(set(construct.source_refs) - deadline_source_ids)
    return source_ids


def check_revision_scoped_source_windows(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    revision_directory: ModeloRevisionDirectory | None = None,
) -> None:
    """Refuse a snapshot whose revision cites a source stale for that revision.

    ``SourceReference.applies_from`` / ``applies_to`` previously validated only
    that the two dates were internally ordered: nothing intersected the window
    with the revision it was cited by, so a source that had expired before the
    revision opened -- or that only began applying after it closed -- stayed
    authoritative evidence inside a successful snapshot.

    The check is deliberately scoped to the refs the *revision* owns, not the
    union the snapshot carries. A ``ModeloDefinition``'s own ``source_refs`` are
    the modelo's documentary corpus across every filing year (M100 lists each
    year's XSD and manual), so intersecting those with one revision's window
    would reject the shipped tree by design. A revision-scoped ref is the
    revision's own claim that this source grounds it, which is the claim a
    filing has to be able to defend.

    Args:
        modelo: The :class:`ModeloDefinition` owning the revision, named in the
            failure message.
        revision: The selected :class:`ModeloRevision` whose scoped source refs
            are checked.
        catalogues: Catalogues supplying the referenced source records.
        revision_directory: Complete endpoint metadata from the pinned directory,
            or ``None`` when the caller holds the complete in-memory modelo.

    Raises:
        RegistryValidationError: If any revision-scoped source window fails to
            overlap the revision's own validity window.
    """
    failures = revision_scoped_source_window_failures(modelo, revision, catalogues, revision_directory)
    if failures:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} cites sources outside their applicability window:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )


def revision_scoped_source_window_failures(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    revision_directory: ModeloRevisionDirectory | None = None,
) -> list[str]:
    """Report the revision-scoped source window failures for a modelo and its sources.

    ``modelo`` is a :class:`ModeloDefinition`; ``revision`` is a :class:`ModeloRevision`.
    """
    _revision_legal_ids, revision_source_ids = collect_snapshot_ref_ids(
        modelo,
        revision,
        include_historical_continuity=False,
    )
    _elsewhere_legal_ids, elsewhere_source_ids = collect_snapshot_ref_ids(
        modelo,
        revision,
        include_deadline_windows=False,
        include_constructs=False,
        include_historical_continuity=False,
    )
    elsewhere_source_ids.update(_construct_source_ids_without_deadline_closure(revision))
    scoped_source_ids = revision_source_ids - set(modelo.source_refs)
    deadline_spans = _deadline_window_source_spans(revision)
    endpoint_directory = revision_directory or ModeloRevisionDirectory.from_modelo(
        modelo,
        support=catalogues.supported_filing_years,
    )
    failures = _historical_continuity_source_window_failures(revision, catalogues, endpoint_directory)
    for source_id in sorted(scoped_source_ids):
        failure = _source_window_failure(
            source_id,
            catalogues.sources.get(source_id),
            revision=revision,
            elsewhere_source_ids=elsewhere_source_ids,
            deadline_spans=deadline_spans,
        )
        if failure is not None:
            failures.append(failure)
    return failures


def _historical_continuity_source_window_failures(
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    revision_directory: ModeloRevisionDirectory,
) -> list[str]:
    """Validate continuity evidence against its explicitly named endpoints."""
    endpoints_by_id: dict[RevisionId, RevisionSelectionMetadata] = {
        endpoint.id: endpoint for endpoint in revision_directory.revisions
    }
    failures: list[str] = []
    for evolution in revision.casilla_continuidad_evolutions:
        failures.extend(
            _continuity_evolution_source_failures(
                evolution,
                endpoints_by_id=endpoints_by_id,
                revision_directory=revision_directory,
                sources=catalogues.sources,
            ),
        )
    for relation in revision.casilla_structural_successions:
        failures.extend(
            _structural_succession_source_failures(
                relation,
                endpoints_by_id=endpoints_by_id,
                revision_directory=revision_directory,
                sources=catalogues.sources,
            ),
        )
    return failures


def _continuity_evolution_source_failures(
    evolution: CasillaContinuidadEvolutionDefinition,
    *,
    endpoints_by_id: Mapping[RevisionId, RevisionSelectionMetadata],
    revision_directory: ModeloRevisionDirectory,
    sources: Mapping[str, SourceReference],
) -> list[str]:
    prefix = f"casilla continuidad evolution {evolution.id!r}"
    endpoints = tuple(
        endpoint_id
        for endpoint_id in (evolution.from_revision, evolution.to_revision)
        if endpoint_id in endpoints_by_id
    )
    if len(endpoints) != 2:
        return [f"{prefix} names an endpoint revision the modelo does not declare"]
    return [
        failure
        for source_id in evolution.source_refs
        if (
            failure := _continuity_evolution_source_failure(
                evolution,
                source_id,
                prefix=prefix,
                endpoint_ids=endpoints,
                endpoints_by_id=endpoints_by_id,
                revision_directory=revision_directory,
                sources=sources,
            )
        )
        is not None
    ]


def _continuity_evolution_source_failure(
    evolution: CasillaContinuidadEvolutionDefinition,
    source_id: str,
    *,
    prefix: str,
    endpoint_ids: tuple[RevisionId, ...],
    endpoints_by_id: Mapping[RevisionId, RevisionSelectionMetadata],
    revision_directory: ModeloRevisionDirectory,
    sources: Mapping[str, SourceReference],
) -> str | None:
    if source_id not in sources:
        return f"{prefix} source {source_id!r} is not registered"
    endpoint_failures = tuple(
        endpoint_source_context_failures(
            prefix,
            endpoint=endpoints_by_id[endpoint_id],
            enrolled_source_ids=revision_directory.endpoint_source_ids(endpoint_id),
            source_ids=(source_id,),
            sources=sources,
        )
        for endpoint_id in endpoint_ids
    )
    if all(endpoint_failures):
        return (
            f"{prefix} source {source_id!r} does not match either declared endpoint "
            f"{evolution.from_revision!r}->{evolution.to_revision!r}"
        )
    return None


def _structural_succession_source_failures(
    relation: CasillaStructuralSuccession,
    *,
    endpoints_by_id: Mapping[RevisionId, RevisionSelectionMetadata],
    revision_directory: ModeloRevisionDirectory,
    sources: Mapping[str, SourceReference],
) -> list[str]:
    prefix = f"casilla structural succession {relation.id!r}"
    failures: list[str] = []
    for endpoint_id, source_ids in (
        (relation.from_revision, relation.from_source_refs),
        (relation.to_revision, relation.to_source_refs),
    ):
        failures.extend(
            _structural_endpoint_source_failures(
                prefix,
                endpoint_id=endpoint_id,
                source_ids=source_ids,
                endpoints_by_id=endpoints_by_id,
                revision_directory=revision_directory,
                sources=sources,
            ),
        )
    return failures


def _structural_endpoint_source_failures(
    prefix: str,
    *,
    endpoint_id: RevisionId,
    source_ids: tuple[str, ...],
    endpoints_by_id: Mapping[RevisionId, RevisionSelectionMetadata],
    revision_directory: ModeloRevisionDirectory,
    sources: Mapping[str, SourceReference],
) -> list[str]:
    if endpoint_id not in endpoints_by_id:
        return [f"{prefix} names unknown endpoint revision {endpoint_id!r}"]
    failures = [
        f"{prefix} endpoint {endpoint_id!r} source {source_id!r} is not registered"
        for source_id in source_ids
        if source_id not in sources
    ]
    failures.extend(
        endpoint_source_context_failures(
            prefix,
            endpoint=endpoints_by_id[endpoint_id],
            enrolled_source_ids=revision_directory.endpoint_source_ids(endpoint_id),
            source_ids=source_ids,
            sources=sources,
        ),
    )
    return failures


def _source_window_failure(
    source_id: str,
    source: SourceReference | None,
    *,
    revision: ModeloRevision,
    elsewhere_source_ids: set[str],
    deadline_spans: Mapping[str, tuple[tuple[date, date], ...]],
) -> str | None:
    if source is None:
        return None
    if source.applies_across(revision.valid_from, revision.valid_to):
        return None
    if source_id not in elsewhere_source_ids and any(
        source.applies_across(opens_on, closes_on) for opens_on, closes_on in deadline_spans.get(source_id, ())
    ):
        return None
    if source.applies_to is not None and source.applies_to < revision.valid_from:
        return (
            f"source {source_id!r} applies_to {source.applies_to.isoformat()} is before "
            f"revision valid_from {revision.valid_from.isoformat()}"
        )
    return (
        f"source {source_id!r} applies_from "
        f"{source.applies_from.isoformat() if source.applies_from else '-'} is after "
        f"revision valid_to "
        f"{revision.valid_to.isoformat() if revision.valid_to else '-'}"
    )


__all__ = ["check_revision_scoped_source_windows"]
