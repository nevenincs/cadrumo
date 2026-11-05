"""Shared invocation and run seeding for the native ``app diagnostics`` CLI tests."""

from __future__ import annotations

from datetime import UTC, datetime

from click.testing import Result

from cadrumo.adapters.persistence.llm.run_records import LLMRunRecord, LLMRunRecorder

from ...native_commands.diagnostics_native_support import invoke_diagnostics_cli
from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture
from .cli_runner import invoke_unbound_cli


def invoke_diagnostics(args: list[str], profile: NativeCliProfileFixture) -> Result:
    if profile.label is None:
        raise AssertionError("native diagnostics profile was not registered")
    return invoke_diagnostics_cli(args, profile=profile, invoke_cli=invoke_unbound_cli)


def seed_claude_and_codex_runs() -> None:
    """Write three real run-timing records: two claude (one failed), one codex."""
    recorder = LLMRunRecorder()
    recorder.record(
        LLMRunRecord(
            run_id="run-1",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:claude:test-model",
            model="test-model",
            duration_ms=1200,
            succeeded=True,
            started_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="run-2",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:claude:test-model",
            model="test-model",
            duration_ms=45000,
            succeeded=False,
            error_kind="LLMClassifierError",
            started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="run-3",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:codex:test-model",
            model="test-model",
            duration_ms=800,
            succeeded=True,
            started_at=datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
        ),
    )
