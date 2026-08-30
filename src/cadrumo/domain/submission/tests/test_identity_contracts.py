"""Persisted submission records carry canonical identities, not shape-only strings.

``ModeloPresentado`` is a durable filing identity that the listing engine
filters by raw equality, and its ``submission_id`` / ``attempt_id`` fields are
documented coordinates (a content-derived digest, and a parent-plus-ordinal
pair). All three were length-only strings, so an unknown modelo code, a
whitespace-spelled known one, and an arbitrary identifier all became historical
filing records that no canonical lookup would ever match.

Real model construction and a real encrypted repository round-trip, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.submission import SubmissionRepository
from ....core.modelo import Modelo
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile
from .._models import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_SUBMITTED_AT = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
_DRAFT_ID = "d" * 64


def _filing(
    *,
    modelo: object = Modelo.M303,
    submission_id: str | None = None,
    attempt_id: str | None = None,
) -> ModeloPresentado:
    """Build a valid presented filing, with the identity axes steerable."""
    resolved_submission_id = submission_id if submission_id is not None else make_submission_id(_DRAFT_ID, 1)
    return ModeloPresentado(
        submission_id=resolved_submission_id,
        draft_id=_DRAFT_ID,
        modelo=modelo,
        period=_PERIOD,
        profile_tax_id="12345678Z",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id=attempt_id if attempt_id is not None else f"{resolved_submission_id}.1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT + timedelta(seconds=30),
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


@pytest.mark.parametrize(
    "malformed_modelo",
    ("999", " 303 ", "303 ", "", "3030"),
    ids=("unknown-code", "padded-both", "trailing-space", "empty", "four-digit"),
)
def test_persisted_filing_refuses_non_canonical_modelo_identities(malformed_modelo: str) -> None:
    """A filing identity must name a modelo the rest of the system can look up."""
    with pytest.raises(ValidationError):
        _filing(modelo=malformed_modelo)


def test_canonical_modelo_identity_is_stored_as_the_enum_member() -> None:
    """The record carries the closed identity, so equality holds against Modelo."""
    filing = _filing(modelo="303")

    assert filing.modelo is Modelo.M303
    assert filing.modelo == "303"


def test_canonical_modelo_identity_survives_encrypted_storage(tmp_path: Path) -> None:
    """Valid parity: the canonical identity round-trips through the real repository."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _filing(modelo=Modelo.M130)
        repository = SubmissionRepository()
        repository.save(original)
        loaded = repository.load(original.submission_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.modelo is Modelo.M130


@pytest.mark.parametrize(
    "malformed_submission_id",
    ("not-a-submission-id", " ", "ABCDEF0123456789", "0123456789abcde", "0123456789abcdef0"),
    ids=("free-text", "blank", "uppercase-hex", "fifteen-chars", "seventeen-chars"),
)
def test_submission_id_must_be_the_derived_content_coordinate(malformed_submission_id: str) -> None:
    """The stored identity must be a value ``make_submission_id`` could have produced."""
    with pytest.raises(ValidationError):
        _filing(submission_id=malformed_submission_id, attempt_id=f"{malformed_submission_id}.1")


@pytest.mark.parametrize(
    "malformed_attempt_id",
    ("junk", "wrong.99", "0123456789abcdef.0", "0123456789abcdef.01", "0123456789abcdef"),
    ids=("free-text", "foreign-parent", "zero-ordinal", "padded-ordinal", "no-ordinal"),
)
def test_attempt_id_must_be_the_parent_plus_ordinal_coordinate(malformed_attempt_id: str) -> None:
    """An attempt coordinate names its own parent submission and its own position."""
    with pytest.raises(ValidationError):
        _filing(attempt_id=malformed_attempt_id)


def test_attempt_ordinals_must_follow_their_tuple_position() -> None:
    """The tuple index and the identifier ordinal are two spellings of one fact."""
    submission_id = make_submission_id(_DRAFT_ID, 1)

    def _attempt(ordinal: int, started_at: datetime) -> SubmissionAttempt:
        return SubmissionAttempt(
            attempt_id=f"{submission_id}.{ordinal}",
            started_at=started_at,
            ended_at=started_at + timedelta(seconds=30),
            status=SubmissionStatus.FALLIDA,
        )

    with pytest.raises(ValidationError, match="attempt 2 is"):
        ModeloPresentado(
            submission_id=submission_id,
            draft_id=_DRAFT_ID,
            modelo=Modelo.M303,
            period=_PERIOD,
            profile_tax_id="12345678Z",
            status=SubmissionStatus.FALLIDA,
            submitted_at=_SUBMITTED_AT,
            attempts=(
                _attempt(1, _SUBMITTED_AT),
                _attempt(3, _SUBMITTED_AT + timedelta(minutes=5)),
            ),
        )


def _aggregate(
    *,
    status: SubmissionStatus,
    attempt_statuses: tuple[SubmissionStatus, ...],
    starts: tuple[datetime, ...] | None = None,
    submitted_at: datetime | None = None,
    justificante_csv: str | None = None,
    justificante_pdf_path: Path | None = None,
    acknowledged_at: datetime | None = None,
) -> ModeloPresentado:
    """Build a multi-attempt filing whose aggregate coherence axes are steerable."""
    submission_id = make_submission_id(_DRAFT_ID, 1)
    resolved_starts = starts or tuple(
        _SUBMITTED_AT + timedelta(minutes=5 * index) for index in range(len(attempt_statuses))
    )
    attempts = tuple(
        SubmissionAttempt(
            attempt_id=f"{submission_id}.{index}",
            started_at=start,
            ended_at=start + timedelta(seconds=30),
            status=attempt_status,
        )
        for index, (attempt_status, start) in enumerate(zip(attempt_statuses, resolved_starts, strict=True), start=1)
    )
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=_DRAFT_ID,
        modelo=Modelo.M303,
        period=_PERIOD,
        profile_tax_id="12345678Z",
        status=status,
        justificante_csv=justificante_csv,
        justificante_pdf_path=justificante_pdf_path,
        submitted_at=submitted_at if submitted_at is not None else resolved_starts[0],
        acknowledged_at=acknowledged_at,
        attempts=attempts,
    )


def test_accepted_filing_whose_only_attempt_failed_is_refused() -> None:
    """AEAT cannot have accepted a filing that was never presented."""
    with pytest.raises(ValidationError, match="not coherent with a terminal"):
        _aggregate(
            status=SubmissionStatus.ACEPTADA,
            attempt_statuses=(SubmissionStatus.FALLIDA,),
            justificante_csv="ABCD12345678EFGH",
            justificante_pdf_path=Path("justificantes/303-2025Q1-ABCD.pdf"),
            acknowledged_at=_SUBMITTED_AT + timedelta(minutes=1),
        )


def test_presented_filing_whose_only_attempt_was_accepted_is_refused() -> None:
    """An attempt that already recorded AEAT acceptance fixes the filing verdict."""
    with pytest.raises(ValidationError, match="not coherent with a terminal"):
        _aggregate(
            status=SubmissionStatus.PRESENTADA,
            attempt_statuses=(SubmissionStatus.ACEPTADA,),
        )


def test_out_of_order_attempt_chronology_is_refused() -> None:
    """The attempts tuple is the filing history, so it reads forwards."""
    later = _SUBMITTED_AT + timedelta(minutes=30)
    with pytest.raises(ValidationError, match="before the preceding attempt"):
        _aggregate(
            status=SubmissionStatus.FALLIDA,
            attempt_statuses=(SubmissionStatus.FALLIDA, SubmissionStatus.FALLIDA),
            starts=(later, _SUBMITTED_AT),
        )


def test_submitted_at_must_be_the_first_attempt_start() -> None:
    """``submitted_at`` is documented as the first attempt start, not a free field."""
    with pytest.raises(ValidationError, match="must be the first attempt"):
        _aggregate(
            status=SubmissionStatus.FALLIDA,
            attempt_statuses=(SubmissionStatus.FALLIDA,),
            submitted_at=_SUBMITTED_AT - timedelta(hours=1),
        )


def test_coherent_presentation_then_acceptance_is_accepted() -> None:
    """Valid parity: an AEAT verdict landing after a completed presentation."""
    acknowledged_at = _SUBMITTED_AT + timedelta(minutes=20)
    filing = _aggregate(
        status=SubmissionStatus.ACEPTADA,
        attempt_statuses=(SubmissionStatus.FALLIDA, SubmissionStatus.PRESENTADA),
        justificante_csv="ABCD12345678EFGH",
        justificante_pdf_path=Path("justificantes/303-2025Q1-ABCD.pdf"),
        acknowledged_at=acknowledged_at,
    )

    assert filing.status is SubmissionStatus.ACEPTADA
    assert filing.attempts[-1].status is SubmissionStatus.PRESENTADA
    assert filing.submitted_at == filing.attempts[0].started_at


@pytest.mark.parametrize(
    "malformed_csv",
    ("A", "ABCDEFG", "X" * 33, "ABCD-1234-EFGH"),
    ids=("one-char", "seven-chars", "thirty-three-chars", "hyphenated"),
)
def test_justificante_csv_outside_the_receipt_domain_bounds_is_refused(malformed_csv: str) -> None:
    """A submission record cannot hold a CSV the receipt domain would reject.

    Case is deliberately NOT a refusal axis. A lowercase CSV is a real AEAT
    identifier written in a different case, not a malformed one, so it is
    normalised rather than rejected -- covered positively by
    :func:`test_a_lowercase_csv_is_normalised_rather_than_refused`.
    """
    with pytest.raises(ValidationError):
        _aggregate(
            status=SubmissionStatus.PRESENTADA,
            attempt_statuses=(SubmissionStatus.PRESENTADA,),
            justificante_csv=malformed_csv,
        )


def test_a_lowercase_csv_is_normalised_rather_than_refused() -> None:
    """A lowercase CSV is stored in canonical form, not refused.

    This is the capability the retired receipt-domain alias was about to
    delete. Case-insensitive matching of one CSV against another is a named,
    tested behaviour of the calendar evidence surface -- two case-equivalent
    values are the SAME identifier and are expected to conflict as one. A
    pattern-only alias would have refused the lowercase side at the model
    boundary and removed that behaviour silently.

    The normalisation runs BEFORE the constraint rather than after it, which
    is the whole reason it works: a trailing uppercase transform would run
    after the pattern check and still refuse the value it was added to accept.
    """
    filing = _aggregate(
        status=SubmissionStatus.PRESENTADA,
        attempt_statuses=(SubmissionStatus.PRESENTADA,),
        justificante_csv="csvlive3031t2025",
    )

    assert filing.justificante_csv == "CSVLIVE3031T2025"


def test_justificante_csv_within_the_receipt_domain_bounds_is_accepted() -> None:
    """Valid parity: the shared bound admits exactly what the receipt admits.

    The parity claim is the point and it survives the bound moving. Both fields
    now carry the canonical AEAT CSV type rather than a receipt-domain alias
    with its own wider bound, so the values exercising the boundary changed
    from four-and-sixty-four to eight-and-thirty-two.

    Case did NOT become significant, and saying so here matters because the
    first version of this docstring claimed it did. A lowercase CSV is
    normalised to canonical form and accepted, not refused -- so parity is a
    claim about two axes, admission AND normal form, and the assertion below
    covers both.

    What did not change is what this test is for: a submission record must not
    be able to store a receipt identifier the receipt domain would refuse to
    parse.
    """
    from pydantic import TypeAdapter

    from ....core.identity import AeatCsv

    receipt_bound = TypeAdapter(AeatCsv)

    for csv in ("ABCD1234", "Z" * 32):
        filing = _aggregate(
            status=SubmissionStatus.PRESENTADA,
            attempt_statuses=(SubmissionStatus.PRESENTADA,),
            justificante_csv=csv,
        )
        assert filing.justificante_csv == csv
        # Behavioural parity, not shape comparison: the same value the receipt
        # domain admits is the value the submission record stores.
        assert receipt_bound.validate_python(csv) == csv

    for rejected in ("ABCDEFG", "X" * 33):
        with pytest.raises(ValidationError):
            receipt_bound.validate_python(rejected)

    # Parity extends to the normalisation, not only to accept-versus-refuse:
    # a lowercase value is admitted by BOTH sides and admitted as the SAME
    # canonical form, so the two surfaces cannot key one identifier two ways.
    assert receipt_bound.validate_python("abcd1234") == "ABCD1234"
