"""Registered-executor conformance scenarios for the Modelo 100 borrador family."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ...application.live.borrador_100 import Borrador100Snapshot, Borrador100SnapshotService
from ...application.live.borrador_100_contracts import (
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100QueryProjection,
    Borrador100QuerySummary,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
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
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionSurface
from ...domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...tests.fixtures.borrador import generate as borrador_fixtures
from ..adapter_composition import build_borrador_100_snapshot_repository
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_ANNUAL = "0A"
_SOURCE_URL = "file-import:sha256:" + "a" * 64
_FIRST_CAPTURED_AT = datetime(2026, 4, 1, 9, tzinfo=UTC)
_SECOND_CAPTURED_AT = datetime(2026, 4, 2, 9, tzinfo=UTC)
_FIRST_VALUES = {"casilla.0505": Decimal("100.00")}
_SECOND_VALUES = {"casilla.0505": Decimal("1234.56"), "casilla.0545": Decimal("0")}


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
                binding_count=2,
                state=SnapshotLifecycleState.ACTIVE,
                source_url=_SOURCE_URL,
                # Sorted by binding id (application/operations/public_scalar.py:44).
                binding_values=(
                    PublicNamedScalar(key="casilla.0505", value=PublicDecimal(decimal="1234.56")),
                    PublicNamedScalar(key="casilla.0545", value=PublicDecimal(decimal="0")),
                ),
            ),
        ),
    )


def _prepare_query(context: ConformanceFamilyContext) -> ConformancePreparation:
    year = _filing_year()
    active = _seed_superseded_pair(context, year)
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=Borrador100ReadRequest(profile_id=context.profile_id, kind="list"),
        expected_result=Borrador100QueryProjection(
            profile_id=context.profile_id,
            kind="list",
            # The default list filter keeps only the active capture
            # (application/live/borrador_100_contracts.py:36), and the agent
            # summary withholds the source URL.
            rows=(
                Borrador100QuerySummary(
                    snapshot_id=active.snapshot_id,
                    filing_year=year,
                    period=PublicPeriod(filing_year=year, code=_ANNUAL),
                    captured_at=_SECOND_CAPTURED_AT,
                    binding_count=2,
                    state=SnapshotLifecycleState.ACTIVE,
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
    printed = borrador_fixtures.corpus_casilla_values(year)
    expected_values = {"casilla." + target.casilla_id: printed[target.casilla_id] for target in profile.target_casillas}
    profile_id = context.profile_id

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(Borrador100ImportProjection)
        assert result.profile_id == profile_id
        assert result.extraction_profile_id == profile.id
        # The fixture prints every target casilla, so coverage is complete.
        assert Decimal(result.extraction_coverage.decimal) == Decimal(1)
        assert result.artefact_kind == "BORRADOR"
        assert result.source_pdf_sha256 == digest
        assert result.blank_casillas == ()
        summary = result.snapshot
        assert summary.filing_year == year
        assert summary.period == PublicPeriod(filing_year=year, code=_ANNUAL)
        assert summary.binding_count == len(expected_values)
        assert summary.state is SnapshotLifecycleState.ACTIVE
        # Provenance is the PDF digest, never the operator's path
        # (application/live/borrador_100_import.py:43).
        assert summary.source_url == "file-import:sha256:" + digest
        (persisted,) = _service(context).list_snapshots(operation=context.operation)
        assert persisted.snapshot_id == summary.snapshot_id
        assert dict(persisted.binding_values) == expected_values

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


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == BORRADOR_100_READ_OPERATION_DEFINITION_ID:
        return _prepare_read(context)
    if definition_id == BORRADOR_100_QUERY_OPERATION_DEFINITION_ID:
        return _prepare_query(context)
    if definition_id == BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID:
        return _prepare_import(context)
    raise AssertionError(f"no borrador conformance scenario for {definition_id}")


# Every definition is single-phase and publishes its own id
# (application/live/borrador_100_operation.py:142,233).
LIVE_BORRADOR_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Reads never write (borrador_100_operation.py:187).
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
        # A local PDF import with a confirmed snapshot save settles UPDATED
        # (borrador_100_operation.py:275-276).
        RegisteredExecutorConformanceCase(
            BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
