"""Registered-executor conformance scenarios for the Modelo 100 borrador family."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ...application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRefusalReason,
    Borrador100SnapshotService,
    derive_borrador_100_snapshot_id,
)
from ...application.live.borrador_100_comparison import Borrador100ComparisonProjection, Borrador100ComparisonStatus
from ...application.live.borrador_100_comparison_operation import (
    BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
    Borrador100CompareRequest,
)
from ...application.live.borrador_100_contracts import (
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100QueryProjection,
    Borrador100QuerySummary,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
    Borrador100RefusedSnapshotSummary,
    Borrador100SnapshotDetail,
)
from ...application.live.borrador_100_operation import (
    BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
    BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
    BORRADOR_100_READ_OPERATION_DEFINITION_ID,
)
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import PublicDecimal, PublicNamedScalar
from ...core.external_constants import OutputLanguage
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionSurface
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...tests.fixtures.borrador import generate as borrador_fixtures
from ...tests.fixtures.borrador.generate import corpus_casilla_values, corpus_years
from ..adapter_composition_ports import build_borrador_100_snapshot_repository
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_YEAR = filing_year_envelope().horizon


_ANNUAL = "0A"
_SOURCE_URL = "file-import:sha256:" + "a" * 64
_FIRST_CAPTURED_AT = datetime(_YEAR, 4, 1, 9, tzinfo=UTC)
_SECOND_CAPTURED_AT = datetime(_YEAR, 4, 2, 9, tzinfo=UTC)
_CERTIFICATE = "renta-retencion-soportada-trabajo"
_FIRST_VALUES = {_CERTIFICATE: Decimal("100.00")}
_SECOND_VALUES = {_CERTIFICATE: Decimal("1234.56")}
# Every casilla the borrador profile prints is computed in the fixture revision,
# so no binding admitted to the borrador owns one: all are reported, none stored.
_PRINTED_CASILLAS = ("0505", "0545", "0546", "0585", "0586")


def _filing_year() -> int:
    """The latest committed borrador fixture year the published authority supports."""
    support = published_supported_filing_years()
    assert support is not None
    return max(year for year in borrador_fixtures.corpus_years() if year in support.years)


def _service(context: ConformanceFamilyContext) -> Borrador100SnapshotService:
    bucket_id = str(context.profile_id)
    return Borrador100SnapshotService(
        bucket_id=bucket_id, repository=build_borrador_100_snapshot_repository(bucket_id=bucket_id)
    )


def _seed_superseded_pair(context: ConformanceFamilyContext, year: int) -> Borrador100Snapshot:
    """Capture twice on one axis; the second supersedes the first and is returned."""
    service = _service(context)
    period = Period.from_year_and_code(year, _ANNUAL)
    for captured_at, values in ((_FIRST_CAPTURED_AT, _FIRST_VALUES), (_SECOND_CAPTURED_AT, _SECOND_VALUES)):
        active = service.capture(
            filing_year=year,
            period=period,
            captured_at=captured_at,
            source_url=_SOURCE_URL,
            binding_values=values,
            operation=context.operation,
        )
    return active


def _seed_legacy_snapshot(context: ConformanceFamilyContext, year: int) -> Borrador100Snapshot:
    """Store an active snapshot keyed by a free casilla id, as the earlier key contract wrote it."""
    period = Period.from_year_and_code(year, _ANNUAL)
    ref = context.operation.snapshot("100", filing_year=year, period=_ANNUAL).snapshot_ref
    values = {"casilla.0596": Decimal("15.25")}
    snapshot = Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=year, period=period, registry_snapshot_ref=ref, source_url=_SOURCE_URL, binding_values=values
        ),
        bucket_id=str(context.profile_id),
        modelo="100",
        filing_year=year,
        period=period,
        registry_snapshot_ref=ref,
        captured_at=_FIRST_CAPTURED_AT,
        source_url=_SOURCE_URL,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    build_borrador_100_snapshot_repository(bucket_id=str(context.profile_id)).save(snapshot)
    return snapshot


def _prepare_read(context: ConformanceFamilyContext) -> ConformancePreparation:
    year = _filing_year()
    active = _seed_superseded_pair(context, year)
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=Borrador100ReadRequest(profile_id=context.profile_id, kind="latest", filing_year=year),
        expected_result=Borrador100ReadProjection(
            profile_id=context.profile_id,
            kind="latest",
            filing_year=year,
            snapshot=Borrador100SnapshotDetail(
                snapshot_id=active.snapshot_id,
                filing_year=year,
                period=PublicPeriod(filing_year=year, code=_ANNUAL),
                captured_at=_SECOND_CAPTURED_AT,
                binding_count=1,
                state=SnapshotLifecycleState.ACTIVE,
                source_url=_SOURCE_URL,
                binding_values=(PublicNamedScalar(key=_CERTIFICATE, value=PublicDecimal(decimal="1234.56")),),
            ),
        ),
    )


def _prepare_query(context: ConformanceFamilyContext) -> ConformancePreparation:
    """List the active snapshots: the valid one is a row, the legacy one is named as refused."""
    year = _filing_year()
    active = _seed_superseded_pair(context, year)
    legacy = _seed_legacy_snapshot(context, year - 1)
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=Borrador100ReadRequest(profile_id=context.profile_id, kind="list"),
        expected_result=Borrador100QueryProjection(
            profile_id=context.profile_id,
            kind="list",
            rows=(
                Borrador100QuerySummary(
                    snapshot_id=active.snapshot_id,
                    filing_year=year,
                    period=PublicPeriod(filing_year=year, code=_ANNUAL),
                    captured_at=_SECOND_CAPTURED_AT,
                    binding_count=1,
                    state=SnapshotLifecycleState.ACTIVE,
                ),
            ),
            refused_snapshots=(
                Borrador100RefusedSnapshotSummary(
                    snapshot_id=legacy.snapshot_id,
                    filing_year=year - 1,
                    period=PublicPeriod(filing_year=year - 1, code=_ANNUAL),
                    captured_at=_FIRST_CAPTURED_AT,
                    state=SnapshotLifecycleState.ACTIVE,
                    reason=Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED,
                ),
            ),
        ),
    )


def _borrador_extraction_profile(operation: PinnedAuthorityOperation, year: int) -> ExtractionProfileDefinition:
    snapshot = operation.snapshot("100", filing_year=year, period=_ANNUAL)
    (profile,) = (row for row in snapshot.extraction_profiles.values() if row.surface == ExtractionSurface.BORRADOR_PDF)
    return profile


def _prepare_import(context: ConformanceFamilyContext) -> ConformancePreparation:
    year = _filing_year()
    fixture = Path(borrador_fixtures.__file__).with_name(f"modelo_100_{year}.pdf")
    source = context.input_root / "borrador.pdf"
    pdf_bytes = fixture.read_bytes()
    source.write_bytes(pdf_bytes)
    digest = sha256_hex(pdf_bytes)
    profile = _borrador_extraction_profile(context.operation, year)
    assert set(_PRINTED_CASILLAS) <= set(borrador_fixtures.corpus_casilla_values(year))
    assert tuple(sorted(target.casilla_id for target in profile.target_casillas)) == _PRINTED_CASILLAS
    profile_id = context.profile_id

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(Borrador100ImportProjection)
        assert result.profile_id == profile_id
        assert result.extraction_profile_id == profile.id
        assert Decimal(result.extraction_coverage.decimal) == Decimal(1)
        assert result.artefact_kind == "BORRADOR"
        assert result.source_pdf_sha256 == digest
        assert result.blank_casillas == ()
        assert result.observed_casillas == _PRINTED_CASILLAS
        assert result.unowned_casillas == ()
        summary = result.snapshot
        assert summary.filing_year == year
        assert summary.period == PublicPeriod(filing_year=year, code=_ANNUAL)
        assert summary.binding_count == 0
        assert summary.printed_observation_count == len(_PRINTED_CASILLAS)
        assert summary.state is SnapshotLifecycleState.ACTIVE
        assert summary.source_url == "file-import:sha256:" + digest
        (persisted,) = _service(context).list_snapshots(operation=context.operation)
        assert persisted.snapshot_id == summary.snapshot_id
        assert dict(persisted.binding_values) == {}
        assert tuple(row.casilla_id for row in persisted.printed_observations) == _PRINTED_CASILLAS

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=Borrador100ImportRequest(
            profile_id=profile_id,
            source_path=source,
            filing_year=year,
            period=PublicPeriod(filing_year=year, code=_ANNUAL),
        ),
        verify=verify,
    )


def _prepare_compare(context: ConformanceFamilyContext) -> ConformancePreparation:
    """An imported draft with no saved calculation is served as such, never as agreement."""
    year = _filing_year()
    active = _seed_superseded_pair(context, year)
    profile_id = context.profile_id

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(Borrador100ComparisonProjection)
        assert result.profile_id == profile_id and result.filing_year == year
        assert result.status.token == Borrador100ComparisonStatus.NO_CALCULATION and result.status.words
        assert result.capture is not None and result.capture.snapshot_id == active.snapshot_id
        assert result.calculation is None and result.rows == ()

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=Borrador100CompareRequest(profile_id=profile_id, filing_year=year, output_language=OutputLanguage.EN),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID:
        return _prepare_compare(context)
    if definition_id == BORRADOR_100_READ_OPERATION_DEFINITION_ID:
        return _prepare_read(context)
    if definition_id == BORRADOR_100_QUERY_OPERATION_DEFINITION_ID:
        return _prepare_query(context)
    if definition_id == BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID:
        return _prepare_import(context)
    raise AssertionError(f"no borrador conformance scenario for {definition_id}")


LIVE_BORRADOR_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (BORRADOR_100_COMPARE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            BORRADOR_100_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (BORRADOR_100_READ_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _retained_borrador_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    support = published_supported_filing_years()
    assert support is not None
    year = max(year for year in corpus_years() if year in support.years)
    period = Period.from_year_and_code(year, "0A")
    repository = build_borrador_100_snapshot_repository(bucket_id=profile)
    service = Borrador100SnapshotService(bucket_id=profile, repository=repository)
    if context.definition.definition_id == "live.borrador.100.import":
        source = context.input_root / "borrador.pdf"
        payload = (
            Path(__file__).parents[2] / "tests" / "fixtures" / "borrador" / f"modelo_100_{year}.pdf"
        ).read_bytes()
        source.write_bytes(payload)
        assert set(_PRINTED_CASILLAS) <= set(corpus_casilla_values(year))

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(Borrador100ImportProjection)
            assert result.profile_id == context.profile_id and result.source_pdf_sha256 == sha256_hex(payload)
            assert (
                Decimal(result.extraction_coverage.decimal) == 1
                and result.extraction_profile_id == "modelo-100-borrador-pdf"
            )
            assert (
                result.blank_casillas == ()
                and result.observed_casillas == _PRINTED_CASILLAS
                and result.unowned_casillas == ()
                and result.snapshot.source_url == f"file-import:sha256:{sha256_hex(payload)}"
            )
            stored = service.list_snapshots(operation=context.operation)
            assert len(stored) == 1 and stored[0].snapshot_id == result.snapshot.snapshot_id
            assert dict(stored[0].binding_values) == {} and str(source) not in stored[0].source_url

        return ConformancePreparation(
            profile_operation_subject(profile),
            Borrador100ImportRequest(
                profile_id=context.profile_id,
                source_path=source,
                filing_year=year,
                period=PublicPeriod.from_period(period),
            ),
            verify=verify,
        )
    bindings = {_CERTIFICATE: Decimal("1720.25")}
    captured = datetime(_YEAR, 4, 1, tzinfo=UTC)
    snapshot = service.capture(
        filing_year=year,
        period=period,
        captured_at=captured,
        source_url="https://example.invalid/synthetic-borrador",
        binding_values=bindings,
        operation=context.operation,
    )

    def verify(outcome: ConformanceOutcome) -> None:
        projection_type = (
            Borrador100QueryProjection
            if context.definition.definition_id.endswith("query")
            else Borrador100ReadProjection
        )
        result = outcome.resolve_result(projection_type)
        assert result.profile_id == context.profile_id and result.snapshot is not None and (result.rows == ())
        assert (
            result.snapshot.snapshot_id == snapshot.snapshot_id
            and result.snapshot.state is SnapshotLifecycleState.ACTIVE
        )
        assert result.snapshot.captured_at == captured and result.snapshot.binding_map() == bindings
        if isinstance(result, Borrador100ReadProjection):
            assert result.snapshot.source_url == snapshot.source_url
        else:
            assert "source_url" not in result.snapshot.model_dump()
        assert service.show(snapshot.snapshot_id, operation=context.operation) == snapshot

    return ConformancePreparation(
        profile_operation_subject(profile),
        Borrador100ReadRequest(profile_id=context.profile_id, kind="view", snapshot_id=snapshot.snapshot_id[:16]),
        verify=verify,
    )


BORRADOR_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            f"live.borrador.100.{verb}",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED if verb == "import" else OperationEffect.NONE,
            (f"live.borrador.100.{verb}",),
        )
        for verb in ("import", "query", "read")
    ),
    prepare=_retained_borrador_prepare,
)
