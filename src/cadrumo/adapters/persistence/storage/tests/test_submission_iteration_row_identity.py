"""``iter_submissions`` will not yield a filing attempt under another's key.

``SubmissionRepository`` derives its object key from
``ModeloPresentado.submission_id``, so the key and the payload are two encodings
of one fact. ``load`` now compares them through the shared secure-bound
repository, but ``iter_submissions`` is a CUSTOM scan that does not route
through it, so the check did not reach enumeration: a valid filing attempt B
stored under A's row key was yielded as an ordinary submission, corrupting
audit-history identity.

The scan is deliberately resilient about UNREADABLE rows -- classification and
schema-version failures are logged and skipped so one bad row cannot hide the
rest of the history. An identity mismatch is not that: the row is perfectly
readable and simply filed under a key it does not describe, so skipping it would
both hide the inconsistency and shorten the history being audited.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted SQL
backend, and the repository's own secure-object writer to plant the row. Nothing
is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....core.period import Period
from .....domain.submission._models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id
from ...profile.submission import SubmissionRepository
from ...tests.runtime_profile_fixture import _runtime_profile
from ..errors import SecureObjectRowIdentityError
from ..sql.secure_objects import SecureObjectRepository

__all__ = ["_runtime_profile"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PERIOD = Period.from_year_and_code(2026, "1T")
_SUBMITTED_AT = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)


def _filing(draft_id: str) -> ModeloPresentado:
    submission_id = make_submission_id(draft_id, 1)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="130",
        period=_PERIOD,
        profile_tax_id="00000000T",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT,
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def _plant_under_foreign_key(repo: SubmissionRepository, payload: ModeloPresentado, *, row_key: str) -> None:
    """Write ``payload``'s valid envelope under a DIFFERENT submission's row key.

    Built from the repository's own envelope class and namespace metadata, so
    the planted row is valid at every layer beneath the identity check.
    """
    envelope = repo._envelope_cls()(
        schema_version=repo.schema_version,
        written_at=_SUBMITTED_AT,
        classification=repo.sensitivity,
        payload=payload,
    )
    SecureObjectRepository().save(
        namespace=repo.namespace,
        object_key=row_key,
        classification=repo.sensitivity,
        schema_version=repo.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def test_honestly_filed_submissions_still_enumerate() -> None:
    """POSITIVE CONTROL: ordinary filing history is unaffected.

    Without this, the refusal below is equally satisfied by an enumeration that
    raises on every row, which would take the whole audit history offline.
    """
    repo = SubmissionRepository()
    first = _filing("d-1")
    second = _filing("d-2")
    repo.save(first)
    repo.save(second)

    assert [item.submission_id for item in repo.iter_submissions()] == sorted(
        [first.submission_id, second.submission_id],
    )


def test_enumeration_refuses_a_filing_attempt_filed_under_another_key() -> None:
    """DISCRIMINATING: the foreign row used to be yielded as an ordinary entry.

    ``load`` already refused it; enumeration did not, because it does not route
    through ``load``. Asserting on the scan specifically is what pins that the
    custom path carries the check rather than inheriting it in name only.
    """
    repo = SubmissionRepository()
    own = _filing("d-1")
    repo.save(own)
    _plant_under_foreign_key(repo, _filing("d-2"), row_key=own.submission_id)

    with pytest.raises(SecureObjectRowIdentityError) as excinfo:
        list(repo.iter_submissions())

    assert excinfo.value.expected_identifier == _filing("d-2").submission_id
    assert excinfo.value.namespace == repo.namespace
