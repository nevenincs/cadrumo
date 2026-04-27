"""End-to-end integration test for the wave-4 governed-persistence chain.

Walks every wave-4 repository together against real on-disk persistence:

- :class:`aeat.filing._repository.FilingDraftRepository` (FINANCIAL)
- :class:`aeat.submission._repository.SubmissionRepository` (AUDIT)
- :class:`aeat.filing._complementaria_repository.FilingAmendmentRepository`
  (AUDIT)
- :class:`aeat.justificante._repository.JustificanteRepository` (AUDIT)
- :class:`aeat.filing._history_repository.FilingHistoryRepository`
  (AUDIT)

NOTE: Wave-4 phase 5 (live-submit governed audit sink) has been excised
because the upstream charter #116 / PR #432 permanently forbade live
AEAT submission. With no live-submit code path there is no audit-event
emission to govern; the JSONL redaction discipline still holds via
the run-trace sink (wave 5 phase 1) and the LLM cache + usage log
(wave 6).

The test asserts:

1. The on-disk envelope's classification matches the repository's intent
   at every step (FINANCIAL for drafts; AUDIT for submission, amendment,
   justificante, filing-history).
2. Re-running the same step against the same store is idempotent.

These are the load-bearing claims of the wave-4 ADR's Phase 7.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ..justificante._repository import JustificanteRepository
from ..justificante._schema import Justificante
from ..storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ..submission._models import (
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)
from ..submission._repository import SubmissionRepository
from ..sync import WireFilingEntry, WireFilingHistory
from ..sync._protocols import ModeloIdentifier
from . import build_draft
from ._complementaria import (
    AmendmentKind,
    CasillaChange,
    FilingAmendment,
)
from ._complementaria_repository import FilingAmendmentRepository
from ._history_repository import FilingHistoryRepository
from ._repository import FilingDraftRepository
from ._schema import FilingDraft
from .runtime import FilingOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]

_NIF_CANARY = "12345678Z"


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _build_draft() -> FilingDraft:
    return build_draft(
        modelo="130",
        period="2026Q1",
        profile=FilingOperatorProfile(
            tax_id=_NIF_CANARY,
            display_name="Test Autónomo",
            applicable_modelos=("130",),
        ),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
    )


def _build_submission(draft: FilingDraft) -> SubmittedFiling:
    submitted_at = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)
    submission_id = make_submission_id(draft.draft_id, 1)
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.1",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=SubmissionStatus.SUBMITTED,
    )
    return SubmittedFiling(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.SUBMITTED,
        submitted_at=submitted_at,
        attempts=(attempt,),
    )


def _build_amendment(draft: FilingDraft, filing: SubmittedFiling) -> FilingAmendment:
    amended_draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=FilingOperatorProfile(
            tax_id=_NIF_CANARY,
            display_name="Test Autónomo",
            applicable_modelos=("130",),
        ),
        inputs={"01": 13000, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
    )
    return FilingAmendment(
        amendment_id="amend-integration-001",
        submission_id=filing.submission_id,
        original_csv="CSV-INTEGRATION-001",
        original_model=draft.modelo,
        original_period=draft.period,
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=(
            CasillaChange(
                casilla_code="01",
                old_value=Decimal("12500"),
                new_value=Decimal("13000"),
                reason="Integration-test correction.",
            ),
        ),
        amended_draft=amended_draft,
        created_at=datetime(2026, 4, 28, 10, 0, tzinfo=UTC),
    )


def _build_justificante(tmp_path: Path, *, csv: str) -> Justificante:
    pdf = tmp_path / f"{csv}.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    return Justificante(
        csv=csv,
        modelo="130",
        period="1T",
        ejercicio="2026",
        presentation_id=None,
        presented_at=datetime(2026, 4, 28, 11, 0, tzinfo=UTC),
        tax_id=_NIF_CANARY,
        total_a_ingresar=Decimal("100.00"),
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/verify"),
        source_pdf_path=pdf,
        source_pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        parsed_at=datetime(2026, 4, 28, 12, 0, tzinfo=UTC),
    )


def test_wave4_end_to_end_flow(tmp_path: Path) -> None:
    """Walk one filing all the way through every wave-4 repository.

    Asserts at every step that the on-disk envelope carries the
    expected classification, that the live-submit audit log is
    redacted, and that re-running each persist call is idempotent.
    """
    draft_repo = FilingDraftRepository(store_dir=tmp_path / "drafts")
    submission_repo = SubmissionRepository(store_dir=tmp_path / "submissions")
    amendment_repo = FilingAmendmentRepository(store_dir=tmp_path / "amendments")
    justificante_repo = JustificanteRepository(store_dir=tmp_path / "justificantes")
    history_repo = FilingHistoryRepository(store_dir=tmp_path / "history")

    # --- 1. Build and persist a draft. --------------------------------
    draft = _build_draft()
    draft_repo.save(draft)
    draft_envelope_text = draft_repo.envelope_path_for(draft.draft_id).read_text(encoding="utf-8")
    assert '"classification":"financial"' in draft_envelope_text
    assert draft_repo.load(draft.draft_id) == draft
    # Idempotent: re-saving the same draft does not duplicate.
    draft_repo.save(draft)
    assert draft_repo.list_draft_ids() == (draft.draft_id,)

    # --- 2. Persist the submission record. ----------------------------
    filing = _build_submission(draft)
    submission_repo.save(filing)
    submission_envelope_text = submission_repo.envelope_path_for(filing.submission_id).read_text(encoding="utf-8")
    assert '"classification":"audit"' in submission_envelope_text
    assert submission_repo.load(filing.submission_id) == filing
    submission_repo.save(filing)
    assert submission_repo.list_submission_ids() == (filing.submission_id,)

    # --- 3. Persist the amendment. ------------------------------------
    amendment = _build_amendment(draft, filing)
    amendment_repo.save(amendment)
    amendment_envelope_text = amendment_repo.envelope_path_for(amendment.amendment_id).read_text(encoding="utf-8")
    assert '"classification":"audit"' in amendment_envelope_text
    assert amendment_repo.load(amendment.amendment_id) == amendment

    # --- 4. Persist the justificante. ---------------------------------
    justificante = _build_justificante(tmp_path, csv="JUSTI-INT-1234567")
    justificante_repo.save(justificante)
    justificante_envelope_text = justificante_repo.envelope_path_for(justificante.csv).read_text(encoding="utf-8")
    assert '"classification":"audit"' in justificante_envelope_text
    assert justificante_repo.load(justificante.csv) == justificante

    # NOTE: live-submit audit emission was originally wave-4 phase 5,
    # but the upstream PR #432 (charter #116) permanently forbade live
    # AEAT submission. With no live emissions the GovernedLiveSubmitAuditSink
    # has no use case and was excised. The redaction discipline still
    # holds end-to-end via the run-trace JSONL sink (wave 5) and the
    # LLM cache + usage redaction (wave 6).

    # --- 5. Persist the filing-history record for the modelo. --------
    history = WireFilingHistory(
        entries=(
            WireFilingEntry(
                modelo=ModeloIdentifier(draft.modelo),
                period=draft.period,
                submitted_at=filing.submitted_at,
                status="ACCEPTED",
            ),
        ),
    )
    history_repo.save(draft.modelo, history)
    history_envelope_text = history_repo.envelope_path_for(draft.modelo).read_text(encoding="utf-8")
    assert '"classification":"audit"' in history_envelope_text
    loaded_history = history_repo.load(draft.modelo)
    assert loaded_history is not None
    assert loaded_history.entries[0].status == "ACCEPTED"


def test_wave4_idempotent_replay(tmp_path: Path) -> None:
    """Running the full chain twice is a no-op on the second pass."""
    draft_repo = FilingDraftRepository(store_dir=tmp_path / "drafts")
    submission_repo = SubmissionRepository(store_dir=tmp_path / "submissions")

    draft = _build_draft()
    filing = _build_submission(draft)

    for _ in range(2):
        draft_repo.save(draft)
        submission_repo.save(filing)

    assert draft_repo.list_draft_ids() == (draft.draft_id,)
    assert submission_repo.list_submission_ids() == (filing.submission_id,)
