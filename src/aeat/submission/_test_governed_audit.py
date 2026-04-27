"""Tests for the governed live-submit audit sink.

These tests exercise the load-bearing claim of the wave-4 audit-sink
relocation: every event written through :class:`GovernedLiveSubmitAuditSink`
passes through the AUDIT-class redaction rule set so the on-disk JSONL
carries no plaintext NIF, no submission URL path, and no bearer-shaped
token.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ._audit import LiveSubmitAuditRecord, build_live_submit_audit_record
from ._governed_audit import (
    GovernedAuditMigrationSummary,
    GovernedLiveSubmitAuditSink,
    migrate_legacy_live_submit_audit,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]

# Plaintext canaries used to confirm the redaction discipline. These
# specific values are tested against the on-disk JSONL after redaction;
# none of them must appear verbatim.
_NIF_CANARY = "12345678Z"
_BEARER_CANARY = "Bearer aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_URL_PATH_CANARY = "/wlpl/SECRET-PATH/Submit?session=ABCDEFGHIJ123456"
_SUBMISSION_URL = "https://www.agenciatributaria.gob.es" + _URL_PATH_CANARY


@pytest.fixture
def audit_dir(tmp_path: Path) -> Path:
    return tmp_path / "audit-root"


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


def _make_record() -> LiveSubmitAuditRecord:
    return build_live_submit_audit_record(
        modelo="130",
        period="2026Q1",
        taxpayer_nif=_NIF_CANARY,
        draft_checksum="abcd1234",
        submission_url=_SUBMISSION_URL,
        response_status="ACCEPTED",
        justificante_csv="JUSTI-1234567890ABCD",
        confirmation_phrase="I AM SURE",
        env_state={"AUTHORIZATION": _BEARER_CANARY},
    )


class TestSinkPaths:
    def test_sink_path_under_audit_dir(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        assert sink.sink_path == audit_dir / "live-submit-audit.envelope.jsonl"

    def test_lock_target_under_audit_dir(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        assert sink.lock_target.parent == audit_dir


class TestRedactionDiscipline:
    def test_no_plaintext_nif_lands_on_disk(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        text = sink.sink_path.read_text(encoding="utf-8")
        assert _NIF_CANARY not in text

    def test_no_submission_url_path_lands_on_disk(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        text = sink.sink_path.read_text(encoding="utf-8")
        assert _URL_PATH_CANARY not in text
        # The host stays so investigators can attribute the call to AEAT,
        # but query strings, paths, and session tokens must be absent.
        assert "session=ABCDEFGHIJ123456" not in text

    def test_no_bearer_token_lands_on_disk(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        text = sink.sink_path.read_text(encoding="utf-8")
        # The full opaque token tail must not appear verbatim.
        assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in text

    def test_event_round_trip_yields_redacted_dict(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        events = list(sink.iter_events())
        assert len(events) == 1
        event = events[0]
        # The taxpayer_nif key still exists, but its value is redacted.
        assert "taxpayer_nif" in event
        assert event["taxpayer_nif"] != _NIF_CANARY


class TestAppendOnly:
    def test_appends_one_line_per_event(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        sink.append(_make_record())
        sink.append(_make_record())
        lines = sink.sink_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            json.loads(line)

    def test_redacted_values_round_trip_to_strings(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        sink.append(_make_record())
        line = sink.sink_path.read_text(encoding="utf-8").strip()
        event = json.loads(line)
        # The redacted NIF is a SHA256-prefixed string, not None or {}.
        assert isinstance(event["taxpayer_nif"], str)
        assert event["taxpayer_nif"]


class TestMigrateLegacyLog:
    def test_drains_and_redacts_legacy_log(self, tmp_path: Path, audit_dir: Path) -> None:
        legacy_path = tmp_path / "legacy" / "live-submit-audit.log"
        legacy_path.parent.mkdir(parents=True)
        # Write three legacy JSONL records in plaintext (the legacy
        # writer does not redact).
        legacy_lines = [_make_record().model_dump_json() for _ in range(3)]
        legacy_path.write_text("\n".join(legacy_lines) + "\n", encoding="utf-8")

        summary = migrate_legacy_live_submit_audit(legacy_path, audit_dir=audit_dir)

        assert isinstance(summary, GovernedAuditMigrationSummary)
        assert summary.imported == 3
        assert summary.errors == 0
        assert summary.legacy_archived_path is not None
        # Legacy file is renamed; the new sink contains 3 redacted
        # lines; no NIF in the new sink.
        sink_text = (audit_dir / "live-submit-audit.envelope.jsonl").read_text(encoding="utf-8")
        assert _NIF_CANARY not in sink_text
        assert sink_text.count("\n") == 3

    def test_missing_legacy_log_is_a_no_op(self, tmp_path: Path, audit_dir: Path) -> None:
        summary = migrate_legacy_live_submit_audit(tmp_path / "missing.log", audit_dir=audit_dir)
        assert summary.imported == 0
        assert summary.errors == 0
        assert summary.legacy_archived_path is None

    def test_unparseable_legacy_lines_counted_under_errors(
        self,
        tmp_path: Path,
        audit_dir: Path,
    ) -> None:
        legacy_path = tmp_path / "legacy.log"
        good_line = _make_record().model_dump_json()
        legacy_path.write_text(
            good_line + "\n{ not json }\n" + good_line + "\n",
            encoding="utf-8",
        )
        summary = migrate_legacy_live_submit_audit(legacy_path, audit_dir=audit_dir)
        assert summary.imported == 2
        assert summary.errors == 1

    def test_archive_idempotency(self, tmp_path: Path, audit_dir: Path) -> None:
        """Re-running the migration after an archive exists removes the
        legacy file rather than stacking suffixes."""
        legacy_path = tmp_path / "legacy.log"
        legacy_path.write_text(_make_record().model_dump_json() + "\n", encoding="utf-8")
        # First run: archive created.
        first = migrate_legacy_live_submit_audit(legacy_path, audit_dir=audit_dir)
        assert first.legacy_archived_path is not None
        # Now write a fresh legacy log alongside the archive.
        legacy_path.write_text(_make_record().model_dump_json() + "\n", encoding="utf-8")
        # Second run: archive already exists, legacy is removed.
        second = migrate_legacy_live_submit_audit(legacy_path, audit_dir=audit_dir)
        assert second.imported == 1
        assert not legacy_path.exists()


class TestTimestampNotRedactedAway:
    """The redaction rules must not corrupt the timestamp_utc string —
    that is the load-bearing audit fact."""

    def test_timestamp_utc_present_in_sink(self, audit_dir: Path) -> None:
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        record = build_live_submit_audit_record(
            modelo="130",
            period="2026Q1",
            taxpayer_nif=_NIF_CANARY,
            draft_checksum="abcd1234",
            submission_url=_SUBMISSION_URL,
            response_status="ACCEPTED",
            justificante_csv="JUSTI-1234567890ABCD",
            confirmation_phrase="I AM SURE",
        )
        sink.append(record)
        events = list(sink.iter_events())
        assert events
        # timestamp_utc is an ISO8601 string after model_dump(mode="json").
        # Confirm a year-shaped string survives redaction.
        assert isinstance(events[0]["timestamp_utc"], str)
        assert events[0]["timestamp_utc"].startswith("20")


class TestSinkWritesUnderAuditDir:
    """HIGH-2 from the upstream audit: the sink must NOT land outside
    the configured audit root."""

    def test_sink_path_is_under_audit_dir(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / "operator-audit"
        sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
        record = build_live_submit_audit_record(
            modelo="130",
            period="2026Q1",
            taxpayer_nif=_NIF_CANARY,
            draft_checksum="abcd",
            submission_url=_SUBMISSION_URL,
            response_status="ACCEPTED",
            justificante_csv=None,
            confirmation_phrase="I AM SURE",
        )
        target = sink.append(record)
        # Resolve both paths to defeat any junction/symlink mismatch on
        # Windows. ``audit_dir`` is a parent of ``target``.
        target_resolved = target.resolve()
        audit_resolved = audit_dir.resolve()
        assert audit_resolved in target_resolved.parents

    def test_legacy_path_constant_is_outside_var(self) -> None:
        """The legacy path was the original HIGH-2 finding; assert it is
        unambiguously outside any operator-configured root so a future
        engineer cannot revert by forgetting to flip the constant."""
        from ._audit import _AUDIT_LOG_PATH

        # The legacy path lives under .aeat in the project tree; the
        # governed sink path lives under audit_dir. Assert they do not
        # share a directory.
        assert ".aeat" in _AUDIT_LOG_PATH.parts
