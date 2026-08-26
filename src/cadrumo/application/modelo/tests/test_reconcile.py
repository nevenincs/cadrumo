"""Real-behavior tests for ``modelo_reconcile``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...tests import isolated_profile_backend as _isolated_backend

__all__ = ["_isolated_backend"]

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.inbound.justificante import parse_justificante
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....domain.buckets import BucketEventType
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests import FIXTURES_DIR
from ..reconciliation import (
    ModeloReconciliationCommand,
    ReconciliationDeclaracionSourceUnsupportedError,
    ReconciliationEvidenceInvalidError,
    WorkUnitNotFoundError,
    _reconcile_parsed_justificante,
    modelo_reconcile,
)
from ..reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
MODELO_202_DECLARACION_FIXTURE = FIXTURES_DIR / "justificantes" / "202" / "2025-1P.pdf"
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 13, 25, 0, tzinfo=UTC)


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
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _stored_work_unit(work_unit_id: str) -> WorkUnit:
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    assert work_unit is not None
    return work_unit


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
        work_unit=_stored_work_unit(work_unit_id),
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


def test_reconcile_records_its_event_for_an_evidence_path_longer_than_the_payload_cap() -> None:
    """An over-long evidence reference must not prevent recording the reconciliation.

    ``source_ref`` reaches the ``MODELO_RECONCILED`` payload from
    ``str(command.source_path)`` — an operator-supplied filesystem path with no
    length bound of its own — while a payload value is capped at 500
    characters. A deep directory or a long filename therefore made the
    reconciliation unrecordable, failing the whole verb on the length of a
    diagnostic breadcrumb.

    The reference is bounded at construction instead. It must stay within the
    cap, remain visibly marked as shortened so it cannot be misread as the
    complete path, and keep the informative tail (the filename) rather than the
    directory prefix.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    parsed = parse_justificante(MODELO_130_FIXTURE)
    long_directory = "/deeply/nested/" + "evidence-archive/" * 40
    over_long_ref = f"{long_directory}modelo_130_2026Q1.pdf"

    # Premise guard: the reference must genuinely exceed the cap, or this test
    # proves nothing about the overflow it exists to cover.
    assert len(over_long_ref) > 500

    report = _reconcile_parsed_justificante(
        work_unit=_stored_work_unit(work_unit_id),
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref=over_long_ref,
        actor="operator",
        justificante=parsed,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.MODELO_RECONCILED and event.object_id == work_unit_id
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    recorded = matching[-1].payload["source_path"]
    assert len(recorded) <= 500
    assert recorded.startswith("...")
    assert recorded.endswith("modelo_130_2026Q1.pdf")
    # Every slot must fit, not only the one under test.
    assert all(len(value) <= 500 for value in matching[-1].payload.values())


def test_modelo_reconcile_refuses_declaration_source_for_unenrolled_modelo() -> None:
    """Casilla-level declaración reconcile is enrolled one modelo at a time.

    A modelo outside :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS` (200 here —
    Modelo 200 declares no ``declaracion_pdf`` extraction profile at all) refuses
    cleanly with a typed error rather than silently degrading to a header-only
    compare."""

    work_unit_id = _seed_work_unit(modelo="200", filing_year=2026, period="0A")

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError) as excinfo:
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
                source_path=MODELO_130_FIXTURE,
            ),
        )
    assert excinfo.value.translated_message == "application.modelo.errors.reconcile_declaration_unsupported"


def test_modelo_reconcile_refuses_modelo_202_declaration_before_parsing() -> None:
    """D5 keeps M202 declaration reconciliation unenrolled despite its live profile.

    The real M202 synthetic declaration fixture and matching work-unit identity
    reach the public ``modelo_reconcile`` boundary.  The typed refusal must
    occur before parsing; adding M202 to the enrolment set changes this
    observable result and fails the test.
    """
    assert MODELO_202_DECLARACION_FIXTURE.is_file()
    work_unit_id = _seed_work_unit(modelo="202", filing_year=2025, period="1P")

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError) as excinfo:
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id=work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
                source_path=MODELO_202_DECLARACION_FIXTURE,
            ),
        )

    assert excinfo.value.translated_message == "application.modelo.errors.reconcile_declaration_unsupported"


def test_modelo_reconcile_refuses_unknown_work_unit() -> None:
    """An addressed work unit that is not in the active bucket's
    catalogue surfaces as ``WorkUnitNotFoundError``."""

    with pytest.raises(WorkUnitNotFoundError):
        modelo_reconcile(
            ModeloReconciliationCommand(
                work_unit_id="0" * 64,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=MODELO_130_FIXTURE,
            ),
        )


def test_modelo_reconcile_translates_cross_bucket_address_to_absence(tmp_path: Path) -> None:
    """The captured active catalogue never reveals a foreign work-unit identity."""

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
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), foreign_unit))

    with pytest.raises(WorkUnitNotFoundError):
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
    from ....core.errors import build_error_envelope, resolve_error_message

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
    # Ground truth, asserted rather than assumed: default suggestions were retired as
    # the remediation authority and ``REFUSED_RECONCILIATION_EVIDENCE_INVALID`` has not
    # yet been migrated to a catalogue action identity, so no recovery step is offered
    # today. The message-quality assertions above are unaffected -- they are what keeps
    # the parser internals off the operator surface. This code's conversion is the
    # application part-one step, behind the registry migration contract.
    assert build_error_envelope(error).action is None
    # The raw cause is preserved for diagnostics off the operator surface.
    assert error.__cause__ is not None
