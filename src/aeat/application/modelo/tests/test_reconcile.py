"""Real-behavior tests for ``modelo_reconcile``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.inbound.justificante import parse_justificante
from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .._reconcile import (
    ModeloReconciliationCommand,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
    ReconciliationCrossBucketRefusedError,
    ReconciliationDeclaracionSourceUnsupportedError,
    ReconciliationEvidenceInvalidError,
    WorkUnitNotFoundError,
    _reconcile_parsed_justificante,
    modelo_reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="11111111-1111-4111-8111-111111111111",
                overrides={"identity.tax_id": "00000000T"},
            ),
        )
        yield


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_modelo_reconcile_matches_when_modelo_and_year_align() -> None:
    """The modelo_130 fixture is modelo=130, ejercicio=2026, period=1T.
    A work unit with matching modelo+filing_year yields MATCHES."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.diffs == ()
    assert report.work_unit_id == work_unit_id


def test_modelo_reconcile_mismatches_when_modelo_differs() -> None:
    """A modelo=303 work unit reconciled against the modelo_130
    fixture produces a MISMATCHES verdict with the modelo diff."""

    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    modelo_diffs = [diff for diff in report.diffs if diff.field_name == "modelo"]
    assert modelo_diffs
    assert modelo_diffs[0].work_unit_value == "303"
    assert modelo_diffs[0].evidence_value == "130"


def test_modelo_reconcile_mismatches_when_period_differs() -> None:
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="2T")

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    period_diffs = [diff for diff in report.diffs if diff.field_name == "period"]
    assert period_diffs
    assert period_diffs[0].work_unit_value == "2T"
    assert period_diffs[0].evidence_value == "1T"


def test_modelo_reconcile_mismatches_when_profile_tax_id_differs() -> None:
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    parsed = parse_justificante(MODELO_130_FIXTURE)

    report = _reconcile_parsed_justificante(
        work_unit_id=work_unit_id,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref=str(MODELO_130_FIXTURE),
        actor="operator",
        justificante=parsed.model_copy(update={"tax_id": "12345678Z"}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    tax_id_diffs = [diff for diff in report.diffs if diff.field_name == "tax_id"]
    assert tax_id_diffs
    assert tax_id_diffs[0].work_unit_value == "00000000T"
    assert tax_id_diffs[0].evidence_value == "12345678Z"


def test_modelo_reconcile_emits_modelo_reconciled_event() -> None:
    """A successful reconcile appends a typed MODELO_RECONCILED event
    to the bucket-event-history catalogue. The payload records the
    verdict so downstream auditors can replay the reconciliation
    timeline without re-parsing the evidence."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
        ),
    )

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.MODELO_RECONCILED and event.object_id == work_unit_id
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["verdict"] == ModeloReconciliationVerdict.MATCHES.value
    assert matching[-1].payload["source_kind"] == "justificante"


def test_modelo_reconcile_refuses_declaration_source_until_parser_lands() -> None:
    """The declaration-PDF parser has not shipped; the service refuses
    cleanly per the app-modelo-shape contract's two-source requirement so
    operators get a typed error rather than a silent-degraded path."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError) as excinfo:
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
                source_path=MODELO_130_FIXTURE,
            ),
        )
    assert excinfo.value.translated_message == "application.modelo.errors.reconcile_declaration_unsupported"


def test_modelo_reconcile_refuses_unknown_work_unit() -> None:
    """An addressed work unit that is not in the active bucket's
    catalogue surfaces as ``WorkUnitNotFoundError``."""

    with pytest.raises(WorkUnitNotFoundError, match=r"not found"):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id="0" * 64,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_refuses_cross_bucket_work_unit(tmp_path: Path) -> None:
    """A work unit whose bucket_id differs from the active profile bucket
    is refused. Bucket events must scope to the active bucket; allowing
    the service to emit into a foreign bucket would let any caller
    pollute another operator's history. Locks the safety gate from
    the bucket-event-history contract §implementation."""

    foreign_bucket_id = "other-bucket-7" * 4
    revision_id = "r" + "1" * 63
    foreign_period = Period.from_year_and_code(2026, "1T")
    foreign_unit_id = derive_work_unit_id(
        bucket_id=foreign_bucket_id,
        modelo="130",
        filing_year=2026,
        period=foreign_period,
        revision_id=revision_id,
    )
    foreign_unit = WorkUnit(
        work_unit_id=foreign_unit_id,
        bucket_id=foreign_bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=foreign_period,
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
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_refuses_malformed_evidence(tmp_path: Path) -> None:
    """A path that is not a valid AEAT justificante surfaces as
    ``ReconciliationEvidenceInvalidError``. Locks the contract from
    the complementaria-external-filing-path contract amendment."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    not_a_justificante = tmp_path / "garbage.pdf"
    not_a_justificante.write_bytes(b"%PDF-1.4\n%not a real justificante\n")

    with pytest.raises(ReconciliationEvidenceInvalidError):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=not_a_justificante,
            ),
        )


def test_modelo_reconcile_malformed_evidence_refusal_is_clean_and_instructive(
    tmp_path: Path,
) -> None:
    """A malformed PDF surfaces a clean, instructive typed refusal.

    The operator-facing message must carry the documented ``evidence_invalid``
    "is this the right document?" guidance and a recovery suggestion, and must
    NOT leak the parser-internal exception class (``PdfminerException``), the
    ``pdfplumber`` backend name, or the ``<input-pdf>`` redaction placeholder.
    Regression for audit reconcile m11 / docs-hardening m16: before the fix the
    refusal echoed the raw parser message verbatim.
    """
    from ....core.errors._registry import (
        get_error_suggestion,
        resolve_error_message,
    )

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    not_a_justificante = tmp_path / "garbage.pdf"
    not_a_justificante.write_bytes(b"%PDF-1.4\nnot a real pdf body at all\n")

    with pytest.raises(ReconciliationEvidenceInvalidError) as caught:
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=not_a_justificante,
            ),
        )

    error = caught.value
    message = resolve_error_message(error)
    for leak in ("PdfminerException", "pdfplumber", "<input-pdf>", "Traceback"):
        assert leak not in message, f"parser-internal token leaked into refusal: {leak!r}"
    # The documented "wrong document" guidance is surfaced (es locale default).
    assert "justificante" in message.lower()
    assert "documento" in message.lower()
    assert get_error_suggestion(error) is not None
    # The raw cause is preserved for diagnostics off the operator surface.
    assert error.__cause__ is not None
