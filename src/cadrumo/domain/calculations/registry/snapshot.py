"""Registry snapshot construction and authority-boundary validation.

This module is the canonical home for building a validated snapshot and for
the small reference/review projections shared by registry authority consumers.
Implementation-only helpers remain private below those public boundaries.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import InternalInvariantError
from ....core.revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from .errors import RegistryFailureClassification, RegistryFailureCondition, RegistryValidationError
from .export import derive_export_layouts_from_bindings
from .ids import RevisionId
from .legal import verify_legal_reference
from .orden_applicability import RevisionLegalApplicabilityWindow, validate_orden_aplicabilidad
from .period_selector_match import registry_period_for_request
from .reference_checks import check_all_id_references
from .revision_context import records_by_id
from .schema import ModeloDefinition, ModeloRevision, RegistrySnapshot
from .schema_base import DateAxis, filing_period_from_scope
from .schema_catalogues import RegistryCatalogues
from .schema_references import (
    LegalReference,
    TemporalProjectionDirection,
    governed_period_span,
    reachable_authority_grade,
)
from .snapshot_proof import SnapshotCrossCheckProof, snapshot_proof_key
from .snapshot_references import collect_snapshot_ref_ids
from .snapshot_source_windows import check_revision_scoped_source_windows
from .temporal import (
    ModeloRevisionDirectory,
    revision_temporal_resolution,
    select_revision,
)
from .validate_revision_identity import revision_reference_identity_failures


def _catalogue_slice[RecordT](catalogue: Mapping[str, RecordT], record_ids: set[str]) -> dict[str, RecordT]:
    """Project the selected catalogue records in deterministic id order."""
    return {record_id: catalogue[record_id] for record_id in sorted(record_ids)}


# Peer-domain modules that register a ``CrossDomainSnapshotCheck`` with the
# registry validator as an import side effect. Each module calls
# ``register_cross_domain_snapshot_check`` at import time; the registry never
# imports the peer statically (that would reverse the hexagonal dependency
# direction). The registry only owns this *list of
# names* -- the dependency-inversion contract the ``CrossDomainSnapshotCheck``
# Protocol declares. ``_install_cross_domain_snapshot_checks`` imports them by
# name so the registration is deterministic at snapshot build, independent of
# whatever else the importing process happened to load first.
# Each entry names the public defining module that performs the registration.
# Runtime-built import targets carry the same ownership rule as static imports,
# while remaining invisible to an AST import scanner.
# Derived from the requirement declaration rather than restated beside it: the
# modules installed here and the checks the validator demands are the same set
# by construction, so neither can be moved without the other.
CROSS_DOMAIN_CHECK_MODULES: tuple[str, ...] = (
    "...renta.first_slice_routing_integrity",
    "...renta.retenciones_routing_integrity",
    "...modelos.perceptor_clave_scope",
)
_cross_domain_checks_installed = False


def cross_domain_check_modules() -> tuple[str, ...]:
    """Name the modules whose import installs the cross-domain checks the validator demands."""
    return CROSS_DOMAIN_CHECK_MODULES


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
    for module_name in CROSS_DOMAIN_CHECK_MODULES:
        # Module names are controlled by the hard-coded tuple above.
        importlib.import_module(module_name, package=__package__)  # nosemgrep
    _cross_domain_checks_installed = True


def validate_materialized_export_record_families(revision: ModeloRevision) -> None:
    """Refuse unresolved or mixed field families before a revision enters a snapshot.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    failures = [
        f"export record {record.id!r}: {failure}"
        for layout in revision.export_layouts
        for record in layout.records
        if (failure := record.repeat_field_family_failure(allow_unresolved_binding_record=False)) is not None
    ]
    if failures:
        raise RegistryValidationError(
            "materialized export record family validation failed:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )


def _validate_snapshot_authority_selection(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    *,
    grade: RegistryAuthorityGrade,
) -> None:
    check_snapshot_authority_grade(modelo, revision, requested_grade=grade)
    if grade is RegistryAuthorityGrade.FILING:
        _check_snapshot_revision_review_status(modelo, revision)
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


def _require_filing_snapshot_capability(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    grade: RegistryAuthorityGrade,
) -> None:
    if grade is RegistryAuthorityGrade.FILING:
        check_snapshot_filing_capability(modelo, revision)


def _require_snapshot_filing_review_tier(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    legal_ids: set[str],
    *,
    grade: RegistryAuthorityGrade,
    on: date | None,
    filing_year: int,
) -> None:
    if grade is RegistryAuthorityGrade.FILING:
        check_snapshot_filing_review_tier(
            modelo,
            revision,
            catalogues,
            legal_ids,
            filing_date=on or date(filing_year, 12, 31),
        )


class _SnapshotCheckStage(Enum):
    """The point of snapshot assembly at which a cross-check runs, in assembly order."""

    REQUEST = auto()
    SELECTED = auto()
    MATERIALIZED = auto()
    REFERENCED = auto()
    ASSEMBLED = auto()


@dataclass(slots=True)
class _SnapshotCheckContext:
    """The request and the assembly state the cross-checks read, filled in as assembly proceeds."""

    modelo: ModeloDefinition
    catalogues: RegistryCatalogues
    filing_year: int
    on: date | None
    grade: RegistryAuthorityGrade
    revision_directory: ModeloRevisionDirectory | None
    revision: ModeloRevision | None = None
    legal_ids: set[str] | None = None
    snapshot: RegistrySnapshot | None = None

    def selected_revision(self) -> ModeloRevision:
        if self.revision is None:
            raise InternalInvariantError("snapshot cross-check ran before revision selection")
        return self.revision

    def referenced_legal_ids(self) -> set[str]:
        if self.legal_ids is None:
            raise InternalInvariantError("snapshot cross-check ran before the reference closure was collected")
        return self.legal_ids

    def assembled_snapshot(self) -> RegistrySnapshot:
        if self.snapshot is None:
            raise InternalInvariantError("snapshot cross-check ran before the snapshot was assembled")
        return self.snapshot


@dataclass(frozen=True, slots=True)
class _SnapshotCrossCheck:
    """One cross-check of snapshot assembly and the stage it runs at."""

    stage: _SnapshotCheckStage
    run: Callable[[_SnapshotCheckContext], None]


def _install_cross_domain_checks_step(_context: _SnapshotCheckContext) -> None:
    _install_cross_domain_snapshot_checks()


def _authority_selection_step(context: _SnapshotCheckContext) -> None:
    _validate_snapshot_authority_selection(
        context.modelo, context.selected_revision(), context.catalogues, grade=context.grade
    )


def _export_record_families_step(context: _SnapshotCheckContext) -> None:
    validate_materialized_export_record_families(context.selected_revision())


def _filing_capability_step(context: _SnapshotCheckContext) -> None:
    _require_filing_snapshot_capability(context.modelo, context.selected_revision(), context.grade)


def _filing_review_tier_step(context: _SnapshotCheckContext) -> None:
    _require_snapshot_filing_review_tier(
        context.modelo,
        context.selected_revision(),
        context.catalogues,
        context.referenced_legal_ids(),
        grade=context.grade,
        on=context.on,
        filing_year=context.filing_year,
    )


def _legal_windows_step(context: _SnapshotCheckContext) -> None:
    check_revision_scoped_legal_windows(context.modelo, context.selected_revision(), context.catalogues)


def _source_windows_step(context: _SnapshotCheckContext) -> None:
    check_revision_scoped_source_windows(
        context.modelo,
        context.selected_revision(),
        context.catalogues,
        context.revision_directory
        or ModeloRevisionDirectory.from_modelo(context.modelo, support=context.catalogues.supported_filing_years),
    )


def _id_references_step(context: _SnapshotCheckContext) -> None:
    check_all_id_references(context.assembled_snapshot())


# Every check snapshot assembly runs, in the order it runs them. A publication
# proof replaces exactly this registry and nothing else: data steps (selection,
# temporal resolution, period normalisation, export-layout derivation, the
# reference closure and the snapshot model's own validators) are not here and
# always run. A check added to assembly belongs here, so the set a proof skips
# can never drift from the set a proof was made by.
SNAPSHOT_CROSS_CHECKS: tuple[_SnapshotCrossCheck, ...] = (
    _SnapshotCrossCheck(_SnapshotCheckStage.REQUEST, _install_cross_domain_checks_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.SELECTED, _authority_selection_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.MATERIALIZED, _export_record_families_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.MATERIALIZED, _filing_capability_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.REFERENCED, _filing_review_tier_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.REFERENCED, _legal_windows_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.REFERENCED, _source_windows_step),
    _SnapshotCrossCheck(_SnapshotCheckStage.ASSEMBLED, _id_references_step),
)


def _run_snapshot_cross_checks(
    stage: _SnapshotCheckStage,
    context: _SnapshotCheckContext,
    proof: SnapshotCrossCheckProof | None,
) -> None:
    if proof is not None:
        return
    for check in SNAPSHOT_CROSS_CHECKS:
        if check.stage is stage:
            check.run(context)


def build_validated_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    revision_directory: ModeloRevisionDirectory | None = None,
    proof: SnapshotCrossCheckProof | None = None,
) -> RegistrySnapshot:
    """Return a selected snapshot after the caller has validated ``modelo``.

    ``grade`` names the rung of authority the CALLER needs, and it defaults to the
    strictest one. That default is the point: it was a ``bool`` defaulting to
    ``False``, so a caller that said nothing silently skipped the revision-review,
    filing-capability and legal-review checks and received a filing-shaped snapshot
    it had not earned. Now a caller that says nothing gets the strict path, and a
    caller needing less must opt DOWN explicitly, in typed and greppable form.

    A lower rung is a narrower claim, never a weaker check of the same claim: a
    caller asking when a modelo is due is not making a filing assertion, and
    forcing it to would make a scheduling question unanswerable rather than safe.

    A filing year the selected revision does not author is carried across from
    the nearest authored edition. The two human gates were given to the edition,
    not to that year, so such a year reaches calculation grade at most and a
    filing request for it is refused, whatever a publication proof recorded.

    ``proof`` is publication's record that this exact request already passed
    every cross-check of this function under the same validator. It replaces
    the cross-check registry and nothing else: selection, temporal resolution,
    period normalisation, export-layout derivation, catalogue slicing and the
    snapshot model's own validators still run. A proof is refused unless the
    request names neither ``on`` nor ``revision_id`` and the proof's key and
    revision equal this request's canonical key and selected revision.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`.
    """
    if proof is not None and (on is not None or revision_id is not None):
        raise InternalInvariantError("a snapshot proof covers only requests without on or revision_id")
    context = _SnapshotCheckContext(
        modelo=modelo,
        catalogues=catalogues,
        filing_year=filing_year,
        on=on,
        grade=grade,
        revision_directory=revision_directory,
    )
    _run_snapshot_cross_checks(_SnapshotCheckStage.REQUEST, context, proof)
    revision = select_revision(
        modelo,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        support=catalogues.supported_filing_years,
    )
    temporal_resolution = revision_temporal_resolution(
        revision,
        filing_year=filing_year,
        period=period,
        support=catalogues.supported_filing_years,
    )
    # Selection data, not a cross-check: a publication proof covers the checks of
    # the request it recorded, and the year a revision authors is the one fact a
    # proof recorded for an earlier selection cannot vouch for.
    _require_authored_year_for_grade(
        modelo,
        revision,
        projection_direction=temporal_resolution.projection_direction,
        authored_filing_year=temporal_resolution.authored_filing_year,
        filing_year=filing_year,
        period=period,
        requested_grade=grade,
    )
    if proof is not None:
        _require_matching_proof(proof, modelo, revision, filing_year=filing_year, period=period, grade=grade)
    context.revision = revision
    _run_snapshot_cross_checks(_SnapshotCheckStage.SELECTED, context, proof)
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
    period = registry_period_for_request(revision.period_selector.declared_periods, period) or period
    revision = revision.model_copy(update={"export_layouts": derive_export_layouts_from_bindings(revision)})
    context.revision = revision
    _run_snapshot_cross_checks(_SnapshotCheckStage.MATERIALIZED, context, proof)
    legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
    context.legal_ids = legal_ids
    _run_snapshot_cross_checks(_SnapshotCheckStage.REFERENCED, context, proof)
    snapshot = RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_period=filing_period_from_scope(filing_year, period),
        filing_year=filing_year,
        authored_filing_year=temporal_resolution.authored_filing_year,
        supported_filing_years=catalogues.supported_filing_years,
        revision_projection_direction=temporal_resolution.projection_direction,
        period=period,
        legal=_catalogue_slice(catalogues.legal, legal_ids),
        sources=_catalogue_slice(catalogues.sources, source_ids),
        extraction_profiles=records_by_id(revision.extraction_profiles),
        live_cross_references=records_by_id(revision.live_cross_references),
        workbook_parity_refs=records_by_id(revision.workbook_parity_refs),
        verification_expectations=records_by_id(revision.verification_expectations),
        application_links=records_by_id(revision.application_links),
        deadline_windows=records_by_id(revision.deadline_windows),
        filing_schedules=records_by_id(revision.filing_schedules),
        constructs=records_by_id(revision.constructs),
        dependency_classifications=records_by_id(revision.dependency_classifications),
        convenio=catalogues.convenio,
        supplementary_ordenes=catalogues.supplementary_ordenes,
    )
    context.snapshot = snapshot
    _run_snapshot_cross_checks(_SnapshotCheckStage.ASSEMBLED, context, proof)
    return snapshot


def _require_matching_proof(
    proof: SnapshotCrossCheckProof,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade,
) -> None:
    expected = snapshot_proof_key(revision, modelo_id=modelo.id, filing_year=filing_year, period=period, grade=grade)
    if proof.key != expected or proof.revision_id != revision.id:
        raise InternalInvariantError(
            f"snapshot proof for {proof.key!r} revision {proof.revision_id!r} does not cover request "
            f"{expected!r} selecting revision {revision.id!r}",
        )


def check_snapshot_authority_grade(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    """Refuse a snapshot claim beyond the selected revision's declared reach.

    Enum declaration order is the canonical authority ladder: each later member
    includes the reach of every earlier member.  An absent declaration remains
    distinguishable from the applicability floor because absence is no claim at
    all and therefore cannot satisfy even an applicability-grade request.

    ``modelo`` is a :class:`ModeloDefinition`; ``revision`` is a :class:`ModeloRevision`.
    """
    if not revision.is_graded:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} declares no authority_grade, so it cannot satisfy "
            f"the requested {requested_grade.value!r} snapshot authority.",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
                facts={
                    "modelo": modelo.id,
                    "revision_id": revision.id,
                    "requested_authority_grade": requested_grade.value,
                    "authority_grade_declared": False,
                },
            ),
        )

    ladder = tuple(RegistryAuthorityGrade)
    declared_grade = revision.effective_authority_grade
    if ladder.index(declared_grade) >= ladder.index(requested_grade):
        return
    raise RegistryValidationError(
        f"modelo {modelo.id} revision {revision.id} declares {declared_grade.value!r} authority grade, "
        f"which cannot satisfy the requested {requested_grade.value!r} snapshot authority.",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
            facts={
                "modelo": modelo.id,
                "revision_id": revision.id,
                "requested_authority_grade": requested_grade.value,
                "declared_authority_grade": declared_grade.value,
                "authority_grade_declared": True,
            },
        ),
    )


def _require_authored_year_for_grade(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    projection_direction: TemporalProjectionDirection,
    authored_filing_year: int,
    filing_year: int,
    period: str,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    """Refuse a claim above calculation for a filing year the selected revision does not author.

    The registry carries the nearest authored edition across a year nobody
    authored, so calculation and preview keep working there. That carried
    design is not the reviewed design of the requested year, and the two human
    gates of a filing snapshot were given to the edition, not to the year, so
    the year reaches calculation grade at most. A revision whose own declaration
    is already below the request is left to the declared-grade check, which
    names the revision as the cause.
    """
    ladder = tuple(RegistryAuthorityGrade)
    declared = revision.effective_authority_grade
    reach = reachable_authority_grade(declared, projection_direction)
    if ladder.index(reach) >= ladder.index(requested_grade) or ladder.index(declared) < ladder.index(requested_grade):
        return
    raise RegistryValidationError(
        f"modelo {modelo.id} revision {revision.id} authors filing year {authored_filing_year}, not {filing_year}, "
        f"so the year reaches {reach.value!r} authority at most and cannot satisfy the requested "
        f"{requested_grade.value!r} snapshot authority.",
        translated_message="errors.snapshot.filing_year_projected",
        context={
            "modelo_id": modelo.id,
            "filing_year": filing_year,
            "period": period,
            "revision_id": revision.id,
            "authored_filing_year": authored_filing_year,
        },
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
            facts={
                "modelo": modelo.id,
                "revision_id": revision.id,
                "requested_authority_grade": requested_grade.value,
                "declared_authority_grade": reach.value,
                "authority_grade_declared": True,
                "filing_year": filing_year,
                "authored_filing_year": authored_filing_year,
                "projection_direction": projection_direction.value,
            },
        ),
    )


def _check_snapshot_revision_review_status(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> None:
    """Require a recorded review of the selected revision before legal checks.

    Admits any member of :data:`REVIEWED_REVISION_REVIEW_STATUSES` — automation or
    operator — rather than ``operator_reviewed`` specifically. Demanding that
    one status made a filing-grade snapshot unreachable by construction:
    nothing in this project may stamp ``operator_reviewed``, so no revision
    could satisfy the check and the gate refused every modelo rather than the
    unreviewed ones. A check no input can pass tests nothing.

    ``pending_review`` — the fail-closed default every ungraded revision reads
    as — still refuses, which is the tooth that matters. The set is the one
    already declared in ``core`` beside the enum, not a second vocabulary
    invented here.
    """
    if revision.review_status in REVIEWED_REVISION_REVIEW_STATUSES:
        return
    status = getattr(revision.review_status, "value", revision.review_status)
    raise RegistryValidationError(
        f"modelo {modelo.id} revision {revision.id} is {status!r}; filing-grade snapshot requires a reviewed revision",
    )


def check_snapshot_filing_capability(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> None:
    """Refuse a filing artifact from a revision that can emit nothing.

    A filing-grade snapshot is the entry to producing a draft and an export, so a
    revision declaring no export layout cannot honour the request no matter what
    else it carries. Refusing here rather than downstream keeps the absence from
    reading as an empty-but-valid result: the completeness gate in ``export_draft``
    checks that every required casilla carries a value, and over an absent layout it
    has nothing to check and passes.

    The check runs after layouts are derived from bindings, so a revision that
    declares none inline but derives one is capable and is not refused. There is no
    allowance, allowlist or per-modelo exemption: a modelo the application cannot
    file is a capability that has not been built yet, never a settled state.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`,
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if revision.export_layouts:
        return
    raise RegistryValidationError(
        f"modelo {modelo.id} revision {revision.id} declares no export layout, so no filing artifact "
        "can be produced from it.",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
            facts={
                "modelo": modelo.id,
                "revision": revision.id,
                "export_layout_declared": False,
                "filing_artifact_supported": False,
            },
        ),
    )


def _check_snapshot_legal_review_status(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    legal_ids: set[str],
    *,
    filing_date: date,
) -> None:
    """Require operator review only for the legal slice a snapshot consumes."""
    failures: list[str] = []
    for legal_id in sorted(legal_ids):
        reference = catalogues.legal.get(legal_id)
        if reference is None:
            continue
        try:
            verify_legal_reference(reference, filing_date=filing_date)
        except RegistryValidationError as exc:
            failures.append(str(exc))
    if failures:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} is not filing-grade:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )


def check_snapshot_filing_review_tier(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
    legal_ids: set[str],
    *,
    filing_date: date,
) -> RevisionReviewStatus:
    """Validate a filing snapshot's review boundary and return its weakest tier.

    Snapshot construction owns the review boundary. Consumers that need to
    classify a successful filing snapshot must call this check rather than
    repeat the revision and legal-reference status predicates.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`,
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    _check_snapshot_revision_review_status(modelo, revision)
    _check_snapshot_legal_review_status(modelo, revision, catalogues, legal_ids, filing_date=filing_date)
    known = set(RevisionReviewStatus)
    if revision.review_status not in known:
        return RevisionReviewStatus.PENDING_REVIEW
    if any(catalogues.legal[item].review_status not in known for item in legal_ids if item in catalogues.legal):
        return RevisionReviewStatus.PENDING_REVIEW
    if revision.review_status is RevisionReviewStatus.AUTOMATION_REVIEWED:
        return RevisionReviewStatus.AUTOMATION_REVIEWED
    if any(
        catalogues.legal[legal_id].review_status is RevisionReviewStatus.AUTOMATION_REVIEWED
        for legal_id in legal_ids
        if legal_id in catalogues.legal
    ):
        return RevisionReviewStatus.AUTOMATION_REVIEWED
    return RevisionReviewStatus.OPERATOR_REVIEWED


#: Legal-reference ``kind``s that carry substantive tax law -- rate scales,
#: deduction limits, thresholds -- as opposed to procedural/administrative
#: instruments. Substantive-law kinds are anchored to the tax period's own
#: devengo date (``revision.valid_to``), never the presentation-extended
#: window: see :func:`legal_window_covers_devengo`.
SUBSTANTIVE_LAW_KINDS = frozenset(
    {
        "ley",
        "real_decreto",
        "real_decreto_legislativo",
        "real_decreto_ley",
        "reglamento",
        "directiva",
        "acuerdo_internacional",
    },
)


def legal_window_covers_devengo(revision: ModeloRevision, reference: LegalReference) -> bool:
    """Return whether ``reference``'s effective window grounds ``revision``.

    A revision-scoped legal reference is a filing-specific grounding claim, so
    the temporal test applied to it depends on WHAT KIND of authority it is --
    this is the same "form approval is presentation-scoped, substantive law is
    devengo-scoped" distinction
    :func:`~cadrumo.domain.calculations.registry.orden_applicability.validate_orden_aplicabilidad.validate_orden_aplicabilidad`
    already draws for the ``orden_aplicabilidad`` field:

    - A substantive-law reference (``kind`` in :data:`SUBSTANTIVE_LAW_KINDS` --
      a rate scale, a deduction limit, a threshold) must be in force at some
      point of the revision's covered period (``revision.valid_from`` to
      ``revision.valid_to``, the devengo date the period closes on). An
      edition still partly inside the provision's window keeps it; the
      provision is removed at the first edition whose period starts after its
      ``effective_to``. A redaction that only starts after the period closes,
      while the return is still being filed, did NOT govern the tax period and
      must not ground it, even though it overlaps the presentation-extended
      window below.
    - Every other kind (``orden``, ``manual``, ``resolucion``,
      ``acuerdo_parlamentario`` -- procedural, interpretive or parliamentary
      instruments) keeps the existing presentation-window-tolerant
      overlap check via :class:`RevisionLegalApplicabilityWindow`: the orden
      ministerial approving a modelo form, or a manual's TFI-documentation
      annex, is legitimately published AFTER the tax year closes, during the
      presentation window, and rejecting those on a devengo-only test would
      reject every correctly-grounded citation in the tree (verified: 13 such
      pairs, 2026-08-02 severity probe).

    Do NOT widen :data:`SUBSTANTIVE_LAW_KINDS` to admit ``orden`` (or narrow
    it further) without re-running that severity probe -- a carve-out here is
    exactly where this gate can go quietly vacuous.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if reference.kind not in SUBSTANTIVE_LAW_KINDS:
        return RevisionLegalApplicabilityWindow.from_revision(revision).overlaps(reference)
    governs_from, governs_to = governed_period_span(reference)
    if governs_to is not None and governs_to < revision.valid_from:
        return False
    if revision.valid_to is None:
        # Open-ended (*-y-siguientes) revision: no fixed devengo date to
        # anchor to. Mirrors the orden gate's own open-ended carve-out.
        return True
    return governs_from <= revision.valid_to


def check_revision_scoped_legal_windows(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
) -> None:
    """Refuse legal authority outside the revision's applicability window.

    Modelo-level legal refs describe the modelo's cross-year authority corpus and
    remain exempt. A ref collected only because the selected revision or one of
    its nested records cites it is a filing-specific grounding claim, checked by
    :func:`legal_window_covers_devengo` -- devengo-anchored for substantive law,
    presentation-window-tolerant for procedural/administrative kinds.

    Args:
        modelo: The :class:`ModeloDefinition` whose own refs stay exempt.
        revision: The :class:`ModeloRevision` whose cited refs are checked.
        catalogues: The legal and source catalogues the refs resolve against.
    """
    revision_legal_ids, _revision_source_ids = collect_snapshot_ref_ids(modelo, revision)
    elsewhere_legal_ids, _elsewhere_source_ids = collect_snapshot_ref_ids(
        modelo,
        revision,
        include_parameters=False,
    )
    scoped_legal_ids = revision_legal_ids - set(modelo.legal_refs)
    applicability_window = RevisionLegalApplicabilityWindow.from_revision(revision)
    parameter_spans = _parameter_value_governed_spans(revision)
    failures: list[str] = []
    for legal_id in sorted(scoped_legal_ids):
        reference = catalogues.legal.get(legal_id)
        if reference is None:
            continue
        failure = _legal_window_failure(
            legal_id,
            reference,
            revision=revision,
            applicability_window=applicability_window,
            carried_spans=() if legal_id in elsewhere_legal_ids else parameter_spans.get(legal_id, ()),
        )
        if failure is not None:
            failures.append(failure)
    if failures:
        raise RegistryValidationError(
            f"modelo {modelo.id} revision {revision.id} cites legal references outside their effective window:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )


def historical_carrier_admits(
    reference: LegalReference,
    carried_spans: tuple[tuple[date, date | None, str], ...],
) -> bool:
    """Decide whether a parameter carrier defends this out-of-window citation.

    A revision carrying HISTORICAL values legitimately cites the provisions that
    governed those periods, because the citation defends the VALUE's window and
    not the revision's. This is the deadline-window axis of the accepted
    evidence-window decision, applied to the parameter carrier.

    The exemption is deliberately hard to earn, and every clause below is load
    bearing. CONTAINMENT rather than overlap, so a value cannot reach a provision
    it only partly sits inside. A CLOSED window, so the exemption cannot be
    bought by declaring an open-ended value -- an open window can never be
    contained in a closed governed span. And never ``submission_date``, because
    when a declaration was filed fixes no applicable law.

    Carrier EXCLUSIVITY is enforced by the caller, which passes no spans at all
    for a reference that any non-parameter record also cites.

    Returns:
        ``True`` when some carried value window is wholly inside the reference's
        governed span on a law-fixing axis.
    """
    if not carried_spans:
        return False
    governs_from, governs_to = governed_period_span(reference)
    for valid_from, valid_to, date_axis in carried_spans:
        if date_axis == DateAxis.SUBMISSION_DATE.value:
            continue
        if valid_to is None:
            continue
        if governs_from <= valid_from and (governs_to is None or valid_to <= governs_to):
            return True
    return False


def _legal_window_failure(
    legal_id: str,
    reference: LegalReference,
    *,
    revision: ModeloRevision,
    applicability_window: RevisionLegalApplicabilityWindow,
    carried_spans: tuple[tuple[date, date | None, str], ...] = (),
) -> str | None:
    """Return the existing refusal detail for one out-of-window legal ref."""
    if legal_window_covers_devengo(revision, reference):
        return None
    if reference.kind in SUBSTANTIVE_LAW_KINDS and historical_carrier_admits(reference, carried_spans):
        return None
    if reference.kind not in SUBSTANTIVE_LAW_KINDS:
        return _procedural_legal_window_failure(
            legal_id,
            reference,
            applicability_window=applicability_window,
        )
    return _substantive_legal_window_failure(legal_id, reference, revision=revision)


def _procedural_legal_window_failure(
    legal_id: str,
    reference: LegalReference,
    *,
    applicability_window: RevisionLegalApplicabilityWindow,
) -> str | None:
    if reference.effective_to is not None and reference.effective_to < applicability_window.starts_on:
        return (
            f"legal reference {legal_id!r} effective_to {reference.effective_to.isoformat()} is before "
            f"revision applicability starts_on {applicability_window.starts_on.isoformat()}"
        )
    if applicability_window.closes_on is not None:
        return (
            f"legal reference {legal_id!r} effective_from {reference.effective_from.isoformat()} is after "
            f"revision applicability closes_on {applicability_window.closes_on.isoformat()}"
        )
    return None


def _substantive_legal_window_failure(
    legal_id: str,
    reference: LegalReference,
    *,
    revision: ModeloRevision,
) -> str | None:
    if reference.effective_to is not None and reference.effective_to < revision.valid_from:
        return (
            f"legal reference {legal_id!r} effective_to {reference.effective_to.isoformat()} is before "
            f"revision applicability starts_on {revision.valid_from.isoformat()}"
        )
    if revision.valid_to is None:
        return None
    effective_to_text = f", effective_to {reference.effective_to.isoformat()}" if reference.effective_to else ""
    return (
        f"legal reference {legal_id!r} (kind {reference.kind!r}, effective_from "
        f"{reference.effective_from.isoformat()}{effective_to_text}) does not cover revision "
        f"{revision.id!r}'s covered period ending {revision.valid_to.isoformat()}"
    )


def _parameter_value_governed_spans(
    revision: ModeloRevision,
) -> dict[str, tuple[tuple[date, date | None, str], ...]]:
    """Map every parameter-cited legal ref to the windows its dated rows defend.

    The legal-side twin of :func:`_deadline_window_source_spans`, and it exists
    for the same reason. A revision that carries HISTORICAL values legitimately
    cites the provisions that governed those periods: modelo 303's 2022 revision
    can hold the pre-2015 prorrata especial margin, whose wording was repealed in
    2014. Intersecting that citation with the revision's own devengo window
    rejects a correct grounding, and the cheapest way to silence the refusal is
    to backdate the provision or to declare a forward reach it cannot state in
    its own text -- fabricated grounding in the name of a window check.

    A dated value's own ``valid_from``/``valid_to`` is the span that citation has
    to defend, because the resolver is fail-closed and exactly-one-match, so that
    window is precisely the set of axis dates on which the value can ever apply.

    ``DatedValue`` carries no ``legal_refs`` of its own; grounding is declared at
    parameter level, so every value of a parameter earns the parameter's refs.
    The axis travels with the window because not every axis fixes applicable law.

    A bracket row of a ``bracket_table`` is dated the same way: the resolver
    selects the rows live on the parameter's ``bracket_axis`` date, so a row's
    own window is exactly where it can apply. A scale whose top rate changed by
    year -- one provision per year's wording -- carries each wording's rows in
    the same revision, and each row window defends that wording's citation on
    the parameter's ``bracket_axis``. Keyed bracket rows declare no axis, so
    they carry no span and their citations stay on the revision window.

    Returns:
        Legal ref id mapped to its carried ``(valid_from, valid_to, date_axis)``
        triples.
    """
    spans: dict[str, list[tuple[date, date | None, str]]] = {}
    for parameter in revision.parameters:
        carried = tuple((value.valid_from, value.valid_to, str(value.date_axis)) for value in parameter.values)
        if parameter.bracket_axis is not None:
            bracket_axis = str(parameter.bracket_axis)
            carried += tuple((row.valid_from, row.valid_to, bracket_axis) for row in parameter.brackets)
        if not carried:
            continue
        for legal_id in parameter.legal_refs:
            spans.setdefault(legal_id, []).extend(carried)
    return {legal_id: tuple(windows) for legal_id, windows in spans.items()}


__all__ = [
    "SUBSTANTIVE_LAW_KINDS",
    "build_validated_snapshot",
    "check_revision_scoped_legal_windows",
    "check_snapshot_filing_capability",
    "check_snapshot_filing_review_tier",
    "legal_window_covers_devengo",
    "validate_materialized_export_record_families",
]
