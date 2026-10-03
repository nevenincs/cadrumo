"""Real PDF import and exact-profile Borrador reader conformance."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ...application.live.borrador_100 import Borrador100SnapshotService
from ...application.live.borrador_100_contracts import (
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100QueryProjection,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
)
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...application.operations.public_period import PublicPeriod
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...tests.fixtures.borrador.generate import corpus_casilla_values, corpus_years
from ..adapter_composition import build_borrador_100_snapshot_repository
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
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
        printed = corpus_casilla_values(year)
        expected = {
            f"casilla.{key}": value for key, value in printed.items() if key in {"0505", "0545", "0546", "0585", "0586"}
        }

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(Borrador100ImportProjection)
            assert result.profile_id == context.profile_id and result.source_pdf_sha256 == sha256_hex(payload)
            assert (
                Decimal(result.extraction_coverage.decimal) == 1
                and result.extraction_profile_id == "modelo-100-borrador-pdf"
            )
            assert (
                result.blank_casillas == ()
                and result.snapshot.source_url == f"file-import:sha256:{sha256_hex(payload)}"
            )
            stored = service.list_snapshots(operation=context.operation)
            assert len(stored) == 1 and stored[0].snapshot_id == result.snapshot.snapshot_id
            assert dict(stored[0].binding_values) == expected and str(source) not in stored[0].source_url

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
    bindings = {"casilla.0505": Decimal("23000.50"), "casilla.0545": Decimal("1720.25")}
    captured = datetime(2026, 4, 1, tzinfo=UTC)
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
        assert result.profile_id == context.profile_id and result.snapshot is not None and result.rows == ()
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


BORRADOR_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            f"live.borrador.100.{verb}",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED if verb == "import" else OperationEffect.NONE,
            (f"live.borrador.100.{verb}",),
        )
        for verb in ("import", "query", "read")
    ),
    prepare=_prepare,
)
