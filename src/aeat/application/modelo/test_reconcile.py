"""Real-behavior tests for ``modelo_reconcile``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.domain.modelos._codes import ModeloCode
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from aeat.domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from aeat.tests import FIXTURES_DIR

from ._reconcile import (
    ModeloReconciliationCommand,
    ModeloReconciliationSourceKind,
    ModeloReconciliationVerdict,
    ReconciliationCrossBucketRefusedError,
    ReconciliationDeclaracionSourceUnsupportedError,
    ReconciliationEvidenceInvalidError,
    WorkUnitNotFoundError,
    modelo_reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'reconcile.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
            yield
        finally:
            dispose_engine()


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_modelo_reconcile_matches_when_modelo_and_year_align() -> None:
    """The modelo_130 fixture is modelo=130, ejercicio=2026, period=1T.
    A work unit with matching modelo+filing_year yields MATCHES."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.diffs == ()
    assert report.work_unit_id == work_unit_id


def test_modelo_reconcile_mismatches_when_modelo_differs() -> None:
    """A modelo=303 work unit reconciled against the modelo_130
    fixture produces a MISMATCHES verdict with the modelo diff."""

    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="Q1")

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    modelo_diffs = [diff for diff in report.diffs if diff.field_name == "modelo"]
    assert modelo_diffs
    assert modelo_diffs[0].work_unit_value == "303"
    assert modelo_diffs[0].evidence_value == "130"


def test_modelo_reconcile_emits_modelo_reconciled_event() -> None:
    """A successful reconcile appends a typed MODELO_RECONCILED event
    to the bucket-event-history catalogue. The payload records the
    verdict so downstream auditors can replay the reconciliation
    timeline without re-parsing the evidence."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.MODELO_RECONCILED
        and event.object_id == work_unit_id
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["verdict"] == ModeloReconciliationVerdict.MATCHES.value
    assert matching[-1].payload["source_kind"] == "justificante"


def test_modelo_reconcile_refuses_declaration_source_until_parser_lands() -> None:
    """The declaration-PDF parser has not shipped; the service refuses
    cleanly per the app-modelo-shape ADR's two-source requirement so
    operators get a typed error rather than a silent-degraded path."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError, match=r"justificante"):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationSourceKind.DECLARATION,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_refuses_unknown_work_unit() -> None:
    """An addressed work unit that is not in the active bucket's
    catalogue surfaces as ``WorkUnitNotFoundError``."""

    with pytest.raises(WorkUnitNotFoundError, match=r"not found"):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id="0" * 64,
                source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_refuses_cross_bucket_work_unit(tmp_path: Path) -> None:
    """A work unit whose bucket_id differs from the active profile bucket
    is refused. Bucket events must scope to the active bucket; allowing
    the service to emit into a foreign bucket would let any caller
    pollute another operator's history. Locks the safety gate from
    the bucket-event-history ADR §implementation."""

    foreign_bucket_id = "other-bucket-7" * 4
    revision_id = "r" + "1" * 63
    foreign_unit_id = derive_work_unit_id(
        bucket_id=foreign_bucket_id,
        modelo="130",
        filing_year=2026,
        period="Q1",
        revision_id=revision_id,
    )
    foreign_unit = WorkUnit(
        work_unit_id=foreign_unit_id,
        bucket_id=foreign_bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period="Q1",
        revision_id=revision_id,
        name="foreign-130",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), foreign_unit))

    with pytest.raises(ReconciliationCrossBucketRefusedError, match=r"active profile bucket"):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=foreign_unit_id,
                source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_refuses_malformed_evidence(tmp_path: Path) -> None:
    """A path that is not a valid AEAT justificante surfaces as
    ``ReconciliationEvidenceInvalidError``. Locks the contract from
    the complementaria-external-filing-path ADR 2026-05-15 amendment."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")
    not_a_justificante = tmp_path / "garbage.pdf"
    not_a_justificante.write_bytes(b"%PDF-1.4\n%not a real justificante\n")

    with pytest.raises(ReconciliationEvidenceInvalidError):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
                source_path=not_a_justificante,
            ),
        )
