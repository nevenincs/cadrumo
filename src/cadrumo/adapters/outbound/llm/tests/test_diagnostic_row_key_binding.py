"""A diagnostic record must derive the row it is stored in.

Both recorders persist a natural key containing a per-append UUID, then
reconstruct that key from the decrypted record while scanning — but neither
compared the reconstruction with the row it came out of. A valid record
substituted under another row's key was therefore returned as that row AND
made pruning miss: the prune issues its delete for the key reconstructed from
the foreign payload, so the stored row survives every retention pass and the
record the operator reads is not the record on disk. The read is wrong and the
retention is wrong, in opposite directions, from one unchecked step.

Each tamper re-encrypts a GENUINE payload under another row's associated data,
so the AAD, schema version, sensitivity class and logical partition all still
agree and only the key binding can refuse it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....llm.errors import LLMCacheError
from .....llm.models import LLMProvider, UsageRecord
from ..run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ..usage import UsageRecorder
from ._engine_binding_fixtures import _ENGINE_HOLDER, _bind_engine  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RECENT = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_OLD = _RECENT - timedelta(days=400)


def _usage(request_id: str, created_at: datetime) -> UsageRecord:
    return UsageRecord(
        prompt_id="translation_v1",
        caller="cli",
        text="respuesta",
        provider=LLMProvider.ANTHROPIC,
        model="claude-opus-4-7",
        input_tokens=11,
        output_tokens=7,
        cost_estimate_usd=Decimal("0.0031"),
        cache_hit=False,
        created_at=created_at,
        request_id=request_id,
    )


def _run(run_id: str, started_at: datetime) -> LLMRunRecord:
    return LLMRunRecord(
        run_id=run_id,
        caller="cli",
        provider="claude",
        model="claude-opus-4-7",
        duration_ms=1234,
        succeeded=True,
        started_at=started_at,
    )


def _substitute(namespace: str, *, victim_marker: str, donor_marker: str) -> None:
    """Re-encrypt the donor row's genuine plaintext under the victim row's identity.

    Rows are told apart by a marker inside their decrypted payload rather than
    by a predicate on ``object_key``: that column is a hashed-lookup type, so
    its stored bytes are a digest and a raw-bytes WHERE clause is not a
    narrower query but a different one.
    """
    from sqlalchemy import select

    from ....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope

    engine = _ENGINE_HOLDER[0]
    with session_scope(engine) as session:
        rows = list(session.execute(select(SecureObjectRow).where(SecureObjectRow.namespace == namespace)).scalars())
        decoded = []
        for row in rows:
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            decoded.append((row, aad, decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)))
        donor = next(plain for _, _, plain in decoded if donor_marker in plain.decode("utf-8"))
        victim, victim_aad, _ = next(item for item in decoded if victim_marker in item[2].decode("utf-8"))
        victim.payload = encrypt_secure_object_payload(donor, associated_data=victim_aad)


def test_a_substituted_usage_row_is_refused_on_read(tmp_path: Path) -> None:
    """The read refuses instead of reporting the foreign record."""
    from ..usage import _USAGE_NAMESPACE

    recorder = UsageRecorder(root_dir=tmp_path / "usage")
    recorder.record(_usage("recent-request", _RECENT))
    recorder.record(_usage("old-request", _OLD))
    _substitute(_USAGE_NAMESPACE, victim_marker="recent-request", donor_marker="old-request")

    with pytest.raises(LLMCacheError):
        recorder.load_records()


def test_a_substituted_usage_row_is_refused_on_prune(tmp_path: Path) -> None:
    """Pruning refuses too, rather than silently missing the stored row.

    This is the half that would otherwise be invisible: the prune deletes the
    key it reconstructed from the foreign payload, reports a removal count that
    looks plausible, and leaves the actual row in place forever.
    """
    from ..usage import _USAGE_NAMESPACE

    recorder = UsageRecorder(root_dir=tmp_path / "usage")
    recorder.record(_usage("recent-request", _RECENT))
    recorder.record(_usage("old-request", _OLD))
    _substitute(_USAGE_NAMESPACE, victim_marker="recent-request", donor_marker="old-request")

    with pytest.raises(LLMCacheError):
        recorder.prune(retention_days=0, max_records=0)


def test_a_substituted_run_telemetry_row_is_refused(tmp_path: Path) -> None:
    """The run-telemetry recorder carries the same binding on both paths."""
    from ..run_telemetry import _RUN_TELEMETRY_NAMESPACE

    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    recorder.record(_run("recent-run", _RECENT))
    recorder.record(_run("old-run", _OLD))
    _substitute(_RUN_TELEMETRY_NAMESPACE, victim_marker="recent-run", donor_marker="old-run")

    with pytest.raises(LLMCacheError):
        recorder.load_records()
    with pytest.raises(LLMCacheError):
        recorder.prune(retention_days=0, max_records=0)


def test_the_substitution_lands_a_valid_foreign_payload(tmp_path: Path) -> None:
    """The tamper's positive control.

    Without it the refusals above could be earned by a corrupted payload
    failing to parse, proving the pre-existing UUID and partition guards
    rather than the new key binding. Here both rows decode to the SAME
    record — the victim row no longer holds its own.
    """
    from sqlalchemy import select

    from ....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope
    from ..usage import _USAGE_NAMESPACE

    recorder = UsageRecorder(root_dir=tmp_path / "usage")
    recorder.record(_usage("recent-request", _RECENT))
    recorder.record(_usage("old-request", _OLD))
    _substitute(_USAGE_NAMESPACE, victim_marker="recent-request", donor_marker="old-request")

    with session_scope(_ENGINE_HOLDER[0]) as session:
        request_ids = []
        for row in session.execute(
            select(SecureObjectRow).where(SecureObjectRow.namespace == _USAGE_NAMESPACE),
        ).scalars():
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
            payload = json.loads(plain.decode("utf-8"))
            assert payload["object_key_uuid"]
            request_ids.append(payload["record"]["request_id"])

    assert sorted(request_ids) == ["old-request", "old-request"]


def test_untampered_records_still_read_and_prune(tmp_path: Path) -> None:
    """The binding must not turn every legitimate read into a refusal.

    Both recorders redact or re-serialise before persisting, so this also
    proves nothing in that path rewrites a key-bearing field — which would
    file every row under a key nothing could re-derive and make the store
    permanently unreadable.
    """
    usage = UsageRecorder(root_dir=tmp_path / "usage")
    usage.record(_usage("recent-request", _RECENT))
    usage.record(_usage("old-request", _OLD))

    telemetry = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    telemetry.record(_run("recent-run", _RECENT))
    telemetry.record(_run("old-run", _OLD))

    assert [item.request_id for item in usage.load_records()] == ["old-request", "recent-request"]
    assert [item.run_id for item in telemetry.load_records()] == ["old-run", "recent-run"]
    assert usage.prune(retention_days=0, max_records=0) == 2
    assert telemetry.prune(retention_days=0, max_records=0) == 2
    assert usage.load_records() == ()
    assert telemetry.load_records() == ()
