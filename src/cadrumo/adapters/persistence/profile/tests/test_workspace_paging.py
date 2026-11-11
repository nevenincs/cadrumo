"""Cursor paging, capture and admission tests for the workspace schema inspection."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    capture_modelo_workspace_target_captures,
    contributors_still_current,
    modelo_work_selector_request_for_target,
)
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceScalarMaterializationV1,
    ModeloWorkspaceStaticInspectionResultV1,
)
from cadrumo.application.modelo.workspace_producers import ModeloWorkspaceWorkPortV1
from cadrumo.application.modelo.workspace_schema import (
    ModeloWorkspaceStaleCursorError,
    paginate_modelo_workspace_facet,
    resolve_static_inspection_result,
    static_inspection_casilla_schema_records,
)
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_serving_period

from .published_authority_support import published_authority_operation
from .workspace_support import (
    FILING_YEAR,
    LAW_SELECTED_REVISION_ID,
    T0,
    assemble_static_inspection_pieces,
    counted_catalogue_reads,
    real_303_inspection,
    seed_work_unit,
    visible_target,
)
from .workspace_support import (
    workspace_repos as workspace_repos,
)

_REVISION_303_ID = revision_serving_period("303", FILING_YEAR, "1T").id

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_a_caller_can_spend_the_cursor_the_schema_facet_mints(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    """The public resolver accepts the cursor it mints and returns the NEXT page.

    The paginator could always page; no public entry point could. Both read
    resolvers took ``page_size`` and no cursor, so a facet returned a valid
    ``next_cursor`` that no caller could redeem, and paging is the normal case
    on the provenance destination where one source ref fans out per casilla.

    Re-resolving is not a workaround and is not what this proves: a fresh
    capture invalidates the held cursor by construction, which is the exact
    property the cursor exists to certify. This drives the SAME entry point
    twice, spending page one's cursor on the second call.
    """
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    authority = published_authority_operation()

    def _resolve(cursor=None):
        return resolve_static_inspection_result(
            visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            output_language=OutputLanguage.ES,
            page_size=5,
            cursor=cursor,
        )

    first = _resolve().projection.schema_facet
    assert first.has_more, "the paging proof needs a schema facet past the page size"
    assert first.next_cursor is not None

    second = _resolve(first.next_cursor).projection.schema_facet

    # The cursor must advance, not restart. Comparing the record identities
    # rather than the counts: a second call that silently returned page one
    # again would match on length and on has_more, and only the contents
    # distinguish "continued" from "started over".
    first_refs = tuple(str(record.reference) for record in first.records)
    second_refs = tuple(str(record.reference) for record in second.records)
    assert second_refs, "spending the cursor returned an empty page"
    assert not set(first_refs) & set(second_refs), "the cursor restarted instead of continuing"


def test_a_cursor_naming_a_facet_the_resolver_does_not_paginate_refuses(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    """A cursor for another facet must refuse, never silently return page one.

    Static inspection assembles only the schema facet. Accepting a
    provenance cursor and ignoring it would hand back the first page while
    the caller believed it was continuing, which is the failure the cursor
    exists to make impossible.
    """
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    authority = published_authority_operation()

    first_page = resolve_static_inspection_result(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        output_language=OutputLanguage.ES,
        page_size=5,
    )
    assert isinstance(first_page, ModeloWorkspaceStaticInspectionResultV1)
    minted = first_page.projection.schema_facet.next_cursor
    assert minted is not None

    foreign = minted.model_copy(update={"facet": ModeloWorkspaceFacetName.PROVENANCE})
    with pytest.raises(ModeloWorkspaceStaleCursorError):
        resolve_static_inspection_result(
            visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            output_language=OutputLanguage.ES,
            page_size=5,
            cursor=foreign,
        )


def test_resolve_static_inspection_result_assembles_a_complete_valid_projection(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    authority = published_authority_operation()

    result = resolve_static_inspection_result(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceStaticInspectionResultV1)
    projection = result.projection
    assert projection.target.modelo == "130"
    assert projection.target.law_selected_revision_id == LAW_SELECTED_REVISION_ID
    assert projection.schema_facet.records  # a real, non-empty schema facet
    assert projection.work_review is STATIC_INSPECTION_WORK_REVIEW_FACET
    assert len(projection.capabilities) == len(ModeloWorkspaceCapabilityName)
    assert projection.materialization_facet is None
    assert projection.provenance_facet is None

    # Round-trip through JSON must reproduce the identical result.

    reloaded = ModeloWorkspaceStaticInspectionResultV1.model_validate_json(result.model_dump_json())
    assert reloaded == result


def test_resolve_static_inspection_result_reads_the_work_catalogue_once_to_capture_and_once_to_confirm(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A single encrypted-SQL work-catalogue read backs the entire assembled result.

    The one other read is the currentness pass, which observes the same
    catalogue to prove no write landed between the capture and the baseline;
    nothing is built from it. A third read would mean a contributor re-read
    what it had already captured.
    """
    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    authority = published_authority_operation()

    from cadrumo.core.external_constants import OutputLanguage

    reads = counted_catalogue_reads(monkeypatch)
    result = resolve_static_inspection_result(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceStaticInspectionResultV1)
    assert result.projection.target.modelo == "130"
    assert len(reads) == 2


def test_capture_with_a_grade_admits_a_registry_snapshot_reading_work_and_registry_exactly_once(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Capture core: passing a grade switches REGISTRY's admission, not the read count or ordering."""
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    authority = published_authority_operation()

    reads = counted_catalogue_reads(monkeypatch)
    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        grade=RegistryAuthorityGrade.CALCULATION,
    )

    assert work_capture.projection.work_unit is not None
    assert registry_capture.projection.snapshot is not None
    assert isinstance(registry_capture.projection.snapshot, RegistrySnapshot)
    assert registry_capture.projection.inspection is None
    assert axes.law_selected_revision_id == LAW_SELECTED_REVISION_ID

    assert len(reads) == 1


def _real_calculation_revision_with_row_materialization():
    """Build a real CalculationRevision carrying both a scalar and a repeated row.

    Mirrors the construction pattern in
    ``test_source_mesh_revision_roundtrip.py`` -- the only existing site that
    builds one of these with row materialization, confirming this shape is
    the real one rather than an invented fixture.
    """
    from decimal import Decimal

    from cadrumo.core.casilla_id import validated_casilla_id
    from cadrumo.domain.calculations.registry.bindings import CasillaObservation
    from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
    from cadrumo.domain.calculations.row_casilla import DirectRowMaterializationProvenance
    from cadrumo.domain.calculations.row_source_identity import RowSourceIdentity
    from cadrumo.domain.modelos.calculation_revision import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )
    from cadrumo.domain.modelos.work_unit import derive_work_unit_id

    bucket_id = "30330300-0000-4000-8000-000000000601"
    scalar_casilla = validated_casilla_id("00501")
    row_casilla = validated_casilla_id("00181")
    now = datetime(FILING_YEAR, 7, 4, 14, 0, tzinfo=UTC)

    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "1T"),
        revision_id=_REVISION_303_ID,
    )
    row_identity = RowSourceIdentity(
        source_kind=BindingSourceKind.INVENTORY,
        source_row_identity="materialization-facet-canary",
        fingerprint="7" * 64,
    )
    row_binding_values = {"inventory-operation-0181": {"1": "120.00"}}
    row_source_identities = {("inventory-operation-0181", 1): row_identity}
    row_casilla_values = {(row_casilla, 1): Decimal("120.00")}
    row_casilla_provenance = {
        (row_casilla, 1): DirectRowMaterializationProvenance(
            source_binding_id="inventory-operation-0181",
            source_row_index=1,
            source_identity=row_identity,
            materialization_rule_id="inventory-operation-0181",
            materialization_rule_version=_REVISION_303_ID,
        )
    }
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={scalar_casilla: "140000.00"},
        binding_overrides={},
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        casilla_values={scalar_casilla: Decimal("140000.00")},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=_REVISION_303_ID,
            modelo_year=FILING_YEAR,
            period="1T",
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={scalar_casilla: "140000.00"},
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        casilla_values={scalar_casilla: Decimal("140000.00")},
        observations=(
            CasillaObservation(
                casilla_id=scalar_casilla,
                value=Decimal("140000.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("boe-modelo-303-2025-form",),
            ),
        ),
        source_provenance=(),
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
    )


def _production_default_page_size() -> int:
    """Return a bounded page size for paginator-focused test fixtures."""
    return 200


def _real_303_casilla_ids() -> tuple[str, ...]:
    """Return every casilla id the bundled M303 revision for the horizon year's first quarter declares.

    The bundled registry drives the count: this revision declares more
    casillas than the graded assembly's own page size, which is what makes
    it the honest anchor for a paging proof. The overflow is the shipped
    registry's shape, not a number these tests chose.
    """
    return tuple(real_303_inspection().casilla_ids)


def _paging_coordinate(bucket_id: str, repository: WorkUnitCatalogueRepository):
    """Return the (target, schema_identity, baseline, contributors) paging pins.

    Reuses the real-capture static assembly because the paginator is
    admission-agnostic: it pins a baseline coordinate and mints a cursor
    against it, and never inspects which admission produced that baseline.
    Admission-versus-facet coherence is :class:`ModeloWorkspaceProjectionV1`'s
    invariant, proven separately, not this helper's.
    """
    _inspection, target, schema_identity, baseline, contributors = assemble_static_inspection_pieces(
        bucket_id, repository
    )
    return target, schema_identity, baseline, contributors


def _drain_pages(facet_type, records, *, facet, target, schema_identity, baseline, contributors, page_size):
    """Page the whole sequence through the real paginator, returning every page."""
    pages = []
    cursor = None
    while True:
        page = paginate_modelo_workspace_facet(
            facet_type,
            records,
            facet=facet,
            target=target,
            schema_identity=schema_identity,
            baseline=baseline,
            contributors=contributors,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=page_size,
            cursor=cursor,
        )
        pages.append(page)
        if page.next_cursor is None:
            return tuple(pages)
        cursor = page.next_cursor


def test_materialization_facet_pages_a_real_revision_that_exceeds_the_page_size(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    """A real M303 revision overflows one page and paginates instead of refusing.

    Before the shared paginator, the graded assembly truncated to
    ``page_size`` and set ``has_more`` without minting the matching cursor,
    so ``ModeloWorkspaceBoundedFacetV1`` refused the facet outright and took
    the whole projection down. This modelo's own casilla set is past the
    page size, so the failure was reachable with shipped registry data.
    """
    from decimal import Decimal

    from cadrumo.core.casilla_id import validated_casilla_id

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    target, schema_identity, baseline, contributors = _paging_coordinate(bucket_id, repository)
    page_size = _production_default_page_size()

    casilla_ids = _real_303_casilla_ids()
    assert len(casilla_ids) > page_size, "the paging proof needs a real revision past the production page size"

    records = tuple(
        ModeloWorkspaceScalarMaterializationRecordV1(
            scalar=ModeloWorkspaceScalarMaterializationV1(
                casilla_id=validated_casilla_id(casilla_id), value=Decimal("1.00")
            )
        )
        for casilla_id in casilla_ids
    )

    pages = _drain_pages(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        target=target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        page_size=page_size,
    )

    assert len(pages) > 1
    assert pages[0].has_more is True
    assert pages[0].next_cursor is not None
    assert pages[0].next_cursor.facet is ModeloWorkspaceFacetName.MATERIALIZATION
    assert len(pages[0].records) == page_size
    assert pages[-1].has_more is False
    assert pages[-1].next_cursor is None
    collected = tuple(record for page in pages for record in page.records)
    assert collected == records


def test_an_overflowing_facet_built_without_a_cursor_still_refuses(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    """Anti-tautology: the invariant the paginator satisfies still bites when violated.

    Two proofs, so the paging tests above cannot pass vacuously. First the
    pre-fix construction shape -- truncate to ``page_size``, declare
    ``has_more``, mint no cursor -- is rejected, which is exactly the live
    defect and shows those tests target something real. Second a genuine
    paginated page has its cursor stripped and is rejected too, so the
    agreement is enforced on the model rather than merely produced by the
    helper.
    """
    from decimal import Decimal

    from pydantic import ValidationError

    from cadrumo.core.casilla_id import validated_casilla_id

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    target, schema_identity, baseline, contributors = _paging_coordinate(bucket_id, repository)
    page_size = _production_default_page_size()

    records = tuple(
        ModeloWorkspaceScalarMaterializationRecordV1(
            scalar=ModeloWorkspaceScalarMaterializationV1(
                casilla_id=validated_casilla_id(casilla_id), value=Decimal("1.00")
            )
        )
        for casilla_id in _real_303_casilla_ids()
    )
    assert len(records) > page_size

    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1](
            selected_revision_id=target.law_selected_revision_id,
            schema_identity=schema_identity,
            baseline=baseline,
            contributor_epoch_digest=baseline.contributor_epoch_digest,
            contributors=contributors,
            facet=ModeloWorkspaceFacetName.MATERIALIZATION,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            records=records[:page_size],
            page_size=page_size,
            has_more=len(records) > page_size,
        )

    page = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        target=target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )
    assert page.next_cursor is not None
    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1].model_validate(
            {**page.model_dump(), "next_cursor": None}
        )


def _resolved_target_with_work_unit(*, work_unit_id: str, revision_id: str = _REVISION_303_ID):
    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceResolvedTargetV1,
        ModeloWorkspaceRevisionAssertionV1,
    )
    from cadrumo.core.revision_review import RevisionReviewStatus
    from cadrumo.domain.modelos.work_unit import WorkUnitState

    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="303",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "1T"),
        law_selected_revision_id=revision_id,
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        work_unit_id=work_unit_id,
        work_state=WorkUnitState.BORRADOR,
    )


def _minimal_calculation_revision(*, work_unit_id: str, state):
    from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
    from cadrumo.domain.modelos.calculation_revision import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )

    now = datetime(FILING_YEAR, 7, 4, 14, 0, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    verified_at = now if state is CalculationRevisionState.VERIFICADO_COMPLETO else None
    verified_by = "test-operator" if state is CalculationRevisionState.VERIFICADO_COMPLETO else None
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=_REVISION_303_ID,
            modelo_year=FILING_YEAR,
            period="1T",
        ),
        state=state,
        casilla_values={},
        observations=(),
        source_provenance=(),
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
        verified_at=verified_at,
        verified_by=verified_by,
    )


def test_static_inspection_labels_equal_per_key_resolution_in_every_language() -> None:
    """Batching the casilla labels changes neither a value, a disposition nor a catalogue coordinate."""
    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceCasillaReferenceV1,
        ModeloWorkspaceLocaleDisposition,
        ModeloWorkspaceLocalizedTextV1,
        ModeloWorkspaceResolvedTargetV1,
        ModeloWorkspaceRevisionAssertionV1,
    )
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.core.i18n.locale_catalogue import capture_locale_catalogue
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    inspection = (
        published_authority_operation()
        .capture_law_selected_projection("130", filing_year=FILING_YEAR, period="1T")
        .projection
    )
    assert isinstance(inspection, RegistryRevisionInspection)
    not_present = ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT
    target = ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="130",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "1T"),
        law_selected_revision_id=LAW_SELECTED_REVISION_ID,
        review_status=inspection.review_status,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED, disposition=not_present, asserted_revision_id=None
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED, disposition=not_present, asserted_revision_id=None
        ),
    )

    for language in (OutputLanguage.ES, OutputLanguage.EN):
        records = static_inspection_casilla_schema_records(inspection, target, output_language=language)
        assert records
        for record in records:
            label = record.label
            assert isinstance(label, ModeloWorkspaceLocalizedTextV1)
            assert isinstance(record.reference, ModeloWorkspaceCasillaReferenceV1)
            own = capture_locale_catalogue(label.locale_key, locale=language.value)
            if own.value is not None:
                expected = (own.value, ModeloWorkspaceLocaleDisposition.EXACT, own.catalogue_digest)
            else:
                spanish = capture_locale_catalogue(label.locale_key, locale=OutputLanguage.ES.value)
                disposition = (
                    ModeloWorkspaceLocaleDisposition.SPANISH_FALLBACK
                    if spanish.value is not None and language is not OutputLanguage.ES
                    else ModeloWorkspaceLocaleDisposition.SUPPRESSED
                )
                expected = (spanish.value, disposition, spanish.catalogue_digest)
            resolved_value = expected[0] if expected[0] is not None else record.reference.casilla_id
            assert (label.value, label.locale.disposition, label.locale.catalogue_digest) == (
                resolved_value,
                expected[1],
                expected[2],
            )


class _RepublishedAfterCapture:
    """The real pinned operation, whose publication advances once a projection is captured.

    Stands in for a republication landing between an admission's registry
    capture and its currentness pass. The capture itself is the real
    operation's; only the coordinate read after it reports a later generation.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._operation = operation
        self._captured = False

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        capture = self._operation.capture_law_selected_projection(
            modelo_id, filing_year=filing_year, period=period, on=on, grade=grade
        )
        self._captured = True
        return capture

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        current = self._operation.read_current_coordinate()
        if not self._captured:
            return current
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=current.comparison_domain,
            generation=current.generation + 1,
        )


def test_a_work_capture_stays_current_until_its_catalogue_is_written(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    port = ModeloWorkspaceWorkPortV1(
        request=modelo_work_selector_request_for_target(visible_target(bucket_id), bucket_id=bucket_id),
        catalogue_repository=repository,
    )
    captured = port.capture_projection_with_epoch()

    assert contributors_still_current(((port, captured.epoch),))

    create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "2T"),
        revision_id=LAW_SELECTED_REVISION_ID,
        ports=WorkLifecyclePorts(
            work_unit_repository=repository, bucket_event_repository=BucketEventHistoryRepository()
        ),
        clock=T0,
        operation=operation,
    )

    assert not contributors_still_current(((port, captured.epoch),))


def test_static_admission_refuses_as_changed_when_the_registry_moves_before_its_second_pass(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)

    result = resolve_static_inspection_result(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=_RepublishedAfterCapture(published_authority_operation()),
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceRefusedResultV1)
    assert result.refusal.code is ModeloWorkspaceRefusalCode.WORKSPACE_CHANGED
    assert result.refusal.selected_target is not None
    assert result.refusal.selected_target.modelo == "130"
