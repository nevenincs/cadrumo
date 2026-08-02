"""Immutable snapshot creation for registry-backed calculations.

Validates a :class:`ModeloDefinition` and selects the matching
:class:`ModeloRevision` for a filing context, then assembles the immutable
:class:`RegistrySnapshot` that downstream consumers (formula engine, export
resolver, coverage auditor) depend on.

This module only has the supplied modelo and catalogues. Cross-model relation
closure needs the full registry tree and is enforced by
:class:`ValidatedRegistryAuthority` / :meth:`RegistryValidator.validate_registry`
before production snapshots are served.
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

from ._errors import RegistryValidationError
from ._export import derive_export_layouts_from_bindings
from ._period_selector_match import registry_period_for_request
from ._schema import (
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    filing_period_from_scope,
)
from ._temporal import select_revision
from ._validate import RegistryValidator
from ._validate_orden_aplicabilidad import validate_orden_aplicabilidad
from ._validate_references import check_all_id_references
from ._validate_revision_identity import revision_reference_identity_failures

_SnapshotCacheKey = tuple[int, int, str, int, str, date | None, str | None]
_SnapshotCacheValue = tuple[ModeloDefinition, RegistryCatalogues, RegistrySnapshot]
_ValidationCacheKey = tuple[int, int, str]
_ValidationCacheValue = tuple[ModeloDefinition, RegistryCatalogues]

_SNAPSHOT_CACHE: dict[_SnapshotCacheKey, _SnapshotCacheValue] = {}
_VALIDATION_CACHE: dict[_ValidationCacheKey, _ValidationCacheValue] = {}

# Peer-domain modules that register a ``CrossDomainSnapshotCheck`` with the
# registry validator as an import side effect. Each module calls
# ``register_cross_domain_snapshot_check`` at import time; the registry never
# imports the peer statically (that would reverse the hexagonal dependency
# direction). The registry only owns this *list of
# names* -- the dependency-inversion contract the ``CrossDomainSnapshotCheck``
# Protocol declares. ``_install_cross_domain_snapshot_checks`` imports them by
# name so the registration is deterministic at snapshot build, independent of
# whatever else the importing process happened to load first.
# Each entry names a peer package's PUBLIC top-level facade, never one of its
# private submodules: a runtime-built import target carries the same ownership
# rule as a static import, and the AST import scanner cannot see these strings.
# The facade's own ``__init__`` imports the check module that registers, so
# importing the package is what runs the registration.
_CROSS_DOMAIN_CHECK_MODULES: tuple[str, ...] = ("cadrumo.domain.renta",)

_cross_domain_checks_installed = False


def _install_cross_domain_snapshot_checks() -> None:
    """Import every peer-domain check module so its registration runs.

    Idempotent: the import side effect (``register_cross_domain_snapshot_check``)
    is itself idempotent and the module cache makes a second ``import_module``
    a no-op, but the module-level flag short-circuits the common path. Called
    at the start of every snapshot build so a Modelo 100 snapshot validated on
    an import path that never imported ``cadrumo.domain.renta`` still has the
    renta first-slice routing referential-integrity gate registered. This
    removes the import-order dependency: registration no longer relies on a
    composition root happening to import ``renta`` before the first M100
    snapshot.
    """
    global _cross_domain_checks_installed
    if _cross_domain_checks_installed:
        return
    for module_name in _CROSS_DOMAIN_CHECK_MODULES:
        # Module names are controlled by the hard-coded tuple above.
        importlib.import_module(module_name)  # nosemgrep
    _cross_domain_checks_installed = True


def build_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Validate ``modelo`` and return the selected immutable snapshot.

    This helper performs model-local validation and snapshot-local reference
    checks. It cannot validate cross-model relation closure because it does not
    receive the full modelo tree; production callers should request snapshots
    through :class:`ValidatedRegistryAuthority`.

    Args:
        modelo: The :class:`ModeloDefinition` to validate and snapshot.
        catalogues: Legal and source catalogues for validation.
        source_root: Filesystem root for resolving source artefacts.
        filing_year: The filing year to select a revision for.
        period: The filing period to select a revision for.
        on: Optional reference date for revision selection.
        revision_id: Optional explicit revision identifier to select.

    Returns:
        The validated :class:`RegistrySnapshot` for the requested filing context.
    """
    source_root_key = str(source_root.expanduser().resolve())
    key = (id(modelo), id(catalogues), source_root_key, filing_year, period, on, revision_id)
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None and cached[0] is modelo and cached[1] is catalogues:
        return cached[2]

    _validate_modelo_once(modelo, catalogues, source_root_key)
    snapshot = _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
    )
    _SNAPSHOT_CACHE[key] = (modelo, catalogues, snapshot)
    return snapshot


def _validate_modelo_once(modelo: ModeloDefinition, catalogues: RegistryCatalogues, source_root_key: str) -> None:
    """Validate one immutable modelo/catalogue pair once per process."""
    key = (id(modelo), id(catalogues), source_root_key)
    cached = _VALIDATION_CACHE.get(key)
    if cached is not None and cached[0] is modelo and cached[1] is catalogues:
        return
    RegistryValidator(catalogues, source_root=Path(source_root_key)).validate_modelo(modelo)
    _VALIDATION_CACHE[key] = (modelo, catalogues)


def _build_validated_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Return a selected snapshot after the caller has validated ``modelo``."""
    _install_cross_domain_snapshot_checks()
    revision = select_revision(modelo, filing_year=filing_year, period=period, on=on, revision_id=revision_id)
    legal_applicability_failures = validate_orden_aplicabilidad(
        f"snapshot modelo {modelo.id} revision {revision.id}",
        modelo.id,
        revision,
        catalogues.legal,
    )
    if legal_applicability_failures:
        raise RegistryValidationError(
            "registry snapshot legal applicability validation failed:\n"
            + "\n".join(f" - {failure}" for failure in legal_applicability_failures),
        )
    identity_failures = revision_reference_identity_failures(
        f"snapshot modelo {modelo.id} revision {revision.id}",
        revision,
    )
    if identity_failures:
        raise RegistryValidationError(
            "registry snapshot revision identity is ambiguous:\n"
            + "\n".join(f" - {failure}" for failure in identity_failures),
        )
    # select_revision matches period selectors case-insensitively but returns
    # the caller's token verbatim. Storing that raw token made the snapshot
    # disagree with itself -- filing_period normalises through Period while
    # .period did not -- and every consumer that tests exact membership against
    # a relation's target_periods (relation_source_requirements, _active_relations,
    # the Sheets pull) then silently activated nothing for a valid lower-case
    # token such as "0a". Normalise once here, at the single snapshot
    # construction site, through the same resolver the query service uses; it
    # returns the declared selector token and preserves a concrete EVENT-n scope
    # rather than collapsing it to the symbolic EVENT-N selector.
    period = registry_period_for_request(revision.period_selector.periods, period) or period
    revision = revision.model_copy(update={"export_layouts": derive_export_layouts_from_bindings(revision)})
    legal_ids, source_ids = _collect_snapshot_ref_ids(modelo, revision)
    _check_revision_scoped_source_windows(modelo, revision, catalogues)
    snapshot = RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_period=filing_period_from_scope(filing_year, period),
        filing_year=filing_year,
        period=period,
        legal={ref: catalogues.legal[ref] for ref in sorted(legal_ids)},
        sources={ref: catalogues.sources[ref] for ref in sorted(source_ids)},
        extraction_profiles={profile.id: profile for profile in revision.extraction_profiles},
        live_cross_references={
            cross_reference.id: cross_reference for cross_reference in revision.live_cross_references
        },
        workbook_parity_refs={workbook.id: workbook for workbook in revision.workbook_parity_refs},
        verification_expectations={expectation.id: expectation for expectation in revision.verification_expectations},
        application_links={link.id: link for link in revision.application_links},
        deadline_windows={window.id: window for window in revision.deadline_windows},
        filing_schedules={schedule.id: schedule for schedule in revision.filing_schedules},
        support_removal_decisions={decision.id: decision for decision in revision.support_removal_decisions},
        constructs={construct.id: construct for construct in revision.constructs},
        dependency_classifications={
            classification.id: classification for classification in revision.dependency_classifications
        },
        convenio=catalogues.convenio,
    )
    check_all_id_references(snapshot)
    return snapshot


def build_validated_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Return a selected :class:`RegistrySnapshot` for an already validated modelo.

    The precondition is model-local. Callers that need cross-model relation
    closure must validate the full registry tree first, normally by using
    :class:`ValidatedRegistryAuthority`.

    Args:
        modelo: The validated :class:`ModeloDefinition` whose revision is selected.
        catalogues: Legal and source catalogues used to populate the snapshot.
        filing_year: The filing year to select a revision for.
        period: The filing period to select a revision for.
        on: Optional reference date for revision selection.
        revision_id: Optional explicit revision identifier to select.

    Returns:
        The selected :class:`RegistrySnapshot`.
    """
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
    )


def _check_revision_scoped_source_windows(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
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
        modelo: The modelo owning the revision, named in the failure message.
        revision: The selected revision whose scoped source refs are checked.
        catalogues: Catalogues supplying the referenced source records.

    Raises:
        RegistryValidationError: If any revision-scoped source window fails to
            overlap the revision's own validity window.
    """
    _revision_legal_ids, revision_source_ids = _collect_snapshot_ref_ids(modelo, revision)
    scoped_source_ids = revision_source_ids - set(modelo.source_refs)
    failures: list[str] = []
    for source_id in sorted(scoped_source_ids):
        source = catalogues.sources.get(source_id)
        if source is None:
            continue
        if source.applies_to is not None and source.applies_to < revision.valid_from:
            failures.append(
                f"source {source_id!r} applies_to {source.applies_to.isoformat()} is before "
                f"revision valid_from {revision.valid_from.isoformat()}",
            )
        elif (
            source.applies_from is not None
            and revision.valid_to is not None
            and source.applies_from > revision.valid_to
        ):
            failures.append(
                f"source {source_id!r} applies_from {source.applies_from.isoformat()} is after "
                f"revision valid_to {revision.valid_to.isoformat()}",
            )
    if failures:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} cites sources outside their applicability window:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )


def _collect_snapshot_ref_ids(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> tuple[set[str], set[str]]:
    """Walk every record kind and return its (legal_ids, source_ids) pair.

    The snapshot's ``legal`` / ``sources`` mappings carry only the
    refs actually exercised by the slice — this helper aggregates the
    every-record-kind union the calculation-grounding rule mandates
    (legal_refs + source_refs preserved through every domain
    boundary). Flat records share one walk; nesting record
    kinds carry
    their own explicit blocks because they nest inner records that
    also carry refs.
    """
    legal_ids = set(modelo.legal_refs).union(revision.legal_refs)
    source_ids = set(modelo.source_refs).union(revision.source_refs)
    if revision.completeness_manifest is not None:
        legal_ids.update(revision.completeness_manifest.legal_refs)
        source_ids.update(revision.completeness_manifest.source_refs)
    for evolution in revision.casilla_continuidad_evolutions:
        legal_ids.update(evolution.legal_refs)
        source_ids.update(evolution.source_refs)
    for predicate in revision.verification_predicates:
        legal_ids.update(predicate.legal_refs)
    flat_records = (
        revision.casillas,
        revision.formulas,
        revision.parameters,
        revision.bindings,
        revision.relations,
        revision.algorithm_providers,
        revision.algorithm_bindings,
        revision.extraction_profiles,
        revision.live_cross_references,
        revision.workbook_parity_refs,
        revision.verification_expectations,
        revision.application_links,
        revision.support_removal_decisions,
        revision.constructs,
        revision.dependency_classifications,
    )
    for kind_records in flat_records:
        for record in kind_records:
            legal_ids.update(record.legal_refs)
            source_ids.update(record.source_refs)
            if isinstance(record, CasillaDefinition):
                if record.constraints is not None:
                    legal_ids.update(record.constraints.legal_refs)
                    source_ids.update(record.constraints.source_refs)
                for alias in record.aliases:
                    legal_ids.update(alias.legal_refs)
                    source_ids.update(alias.source_refs)
    # Cross-reference applicability predicates carry their own legal/source
    # evidence for the profile fact that gates the official/live surface.
    for cross_reference in revision.live_cross_references:
        for predicate in cross_reference.applicability_predicates:
            legal_ids.update(predicate.legal_refs)
            source_ids.update(predicate.source_refs)
    # Export layouts carry refs on the layout itself plus on every
    # field inside every record. Walk both axes explicitly so a future
    # binding-aware field gate still sees every nested ref.
    for layout in revision.export_layouts:
        legal_ids.update(layout.legal_refs)
        source_ids.update(layout.source_refs)
        for export_record in layout.records:
            for field in export_record.fields:
                legal_ids.update(field.legal_refs)
                source_ids.update(field.source_refs)
    # Deadline windows + filing schedules each nest applicability /
    # profile conditions that carry their own refs.
    for window in revision.deadline_windows:
        legal_ids.update(window.legal_refs)
        source_ids.update(window.source_refs)
        for condition in window.applicability_conditions:
            legal_ids.update(condition.legal_refs)
            source_ids.update(condition.source_refs)
    for schedule in revision.filing_schedules:
        legal_ids.update(schedule.legal_refs)
        source_ids.update(schedule.source_refs)
        for condition in schedule.profile_conditions:
            legal_ids.update(condition.legal_refs)
            source_ids.update(condition.source_refs)
    return legal_ids, source_ids
