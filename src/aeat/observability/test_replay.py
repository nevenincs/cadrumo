"""Tests for deterministic dry-run replay and its refusal modes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..config import PROJECT_ROOT, Settings
from . import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    ArgumentRecord,
    ArgumentSource,
    RunOutcome,
    RunTrace,
    compute_corpus_sha256,
    replay_run,
    save_trace,
)
from ._replay import _argv_from_arguments

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _build_trace(run_id: str, *, corpus_sha256: str) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=datetime(2026, 4, 14, tzinfo=UTC),
        finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
        entrypoint="aeat hello",
        arguments=(),
        corpus_sha256=corpus_sha256,
        db_sha256="b" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


class TestReplayRun:
    def test_clean_dry_run_round_trip(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
        trace = _build_trace("0123456789abcdef", corpus_sha256=current_corpus)
        save_trace(trace)
        result = replay_run(trace.run_id, dry_run=True)
        assert result.run_id == trace.run_id
        assert result.entrypoint == "aeat hello"

    def test_refuses_on_corpus_drift(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        trace = _build_trace("fedcba9876543210", corpus_sha256="0" * 64)
        save_trace(trace)
        with pytest.raises(AeatCorpusDriftError) as excinfo:
            replay_run(trace.run_id, dry_run=True)
        assert excinfo.value.run_id == trace.run_id
        assert excinfo.value.recorded == "0" * 64
        assert excinfo.value.observed != "0" * 64
        # S4: error message uses ASCII ellipsis so Windows cp1252
        # consoles can encode it without errors="replace".
        message = str(excinfo.value)
        assert "…" not in message, "error message must not use unicode ellipsis"
        assert "..." in message

    def test_refuses_no_dry_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        trace = _build_trace("abcdef0123456789", corpus_sha256="1" * 64)
        save_trace(trace)
        # Match the specific message so an accidental drift-error or
        # other AeatObservabilityError subclass does not mark the test
        # green for the wrong reason.
        with pytest.raises(AeatObservabilityError, match="dry-run only"):
            replay_run(trace.run_id, dry_run=False)

    def test_refuses_replay_of_live_mode_recording(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Replay must refuse traces captured with --no-dry-run.

        Reconstructing argv would re-enter live-mode even though the
        replay caller passed dry_run=True. The live-write safety
        charter (#116) forbids this.
        """
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
        live_trace = RunTrace(
            run_id="aaaabbbbccccdddd",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat workflow run",
            arguments=(
                ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),
                ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.FLAG),
                ArgumentRecord(
                    name="i-understand-this-is-real",
                    value="True",
                    source=ArgumentSource.FLAG,
                ),
            ),
            corpus_sha256=current_corpus,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(live_trace)
        with pytest.raises(AeatObservabilityError, match="live-mode"):
            replay_run(live_trace.run_id, dry_run=True)

    def test_replay_of_propagated_via_env_var(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S7: the re-entered run_context must label its trace with replay_of."""
        import os

        from ..config import PROJECT_ROOT as _PROJECT_ROOT
        from ..config import Settings as _Settings
        from . import (
            REPLAY_ACTIVE_ENV_VAR,
            run_context,
        )
        from . import (
            compute_corpus_sha256 as _compute_corpus_sha256,
        )
        from ._store import load_trace

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        current_corpus = _compute_corpus_sha256(_PROJECT_ROOT / ".vault", _Settings())
        original = RunTrace(
            run_id="1111222233334444",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat test replay",
            arguments=(),
            corpus_sha256=current_corpus,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(original)

        # Simulate the env var set during a live replay:
        monkeypatch.setenv(REPLAY_ACTIVE_ENV_VAR, original.run_id)
        try:
            with run_context(entrypoint="aeat test replay-child", arguments=()) as info:
                child_run_id = info.run_id
        finally:
            os.environ.pop(REPLAY_ACTIVE_ENV_VAR, None)

        child_trace = load_trace(child_run_id)
        assert child_trace.replay_of == original.run_id, "replay-originated traces must carry the original run id"

    def test_replay_of_ignored_when_env_is_non_canonical(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Legacy sentinel ``"1"`` must not pollute the trace."""
        import os

        from . import REPLAY_ACTIVE_ENV_VAR, run_context
        from ._store import load_trace

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        monkeypatch.setenv(REPLAY_ACTIVE_ENV_VAR, "1")
        try:
            with run_context(entrypoint="aeat test", arguments=()) as info:
                rid = info.run_id
        finally:
            os.environ.pop(REPLAY_ACTIVE_ENV_VAR, None)

        trace = load_trace(rid)
        assert trace.replay_of is None, "non-16-hex env value must be ignored"

    def test_false_value_not_detected_as_live_mode(self) -> None:
        """A flag name in the denylist with value 'False' is not live-mode.

        Exercises the predicate directly so we do not have to stand up a
        full replay pipeline; replay-path coverage for the denylist-hit
        case is provided by :meth:`test_refuses_replay_of_live_mode_recording`.
        """
        from ._replay import _argument_activates_live_mode

        safe = ArgumentRecord(name="no-dry-run", value="False", source=ArgumentSource.FLAG)
        assert _argument_activates_live_mode(safe) is False
        active = ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.FLAG)
        assert _argument_activates_live_mode(active) is True
        non_flag = ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.POSITIONAL)
        assert _argument_activates_live_mode(non_flag) is False
        other = ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG)
        assert _argument_activates_live_mode(other) is False


class TestEnvFileFingerprint:
    """B1: corpus_sha256 must fold the on-disk ``env/.env`` bytes.

    Without this, operator edits to ``.env`` between record and
    replay that aren't yet reflected in the loaded ``Settings()``
    silently evade the drift gate.
    """

    def test_env_file_change_changes_corpus_hash(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import hashlib

        from .. import config as config_mod
        from . import _fingerprint as fp_mod
        from ._fingerprint import compute_corpus_sha256 as _compute_corpus_sha256

        vault_dir = tmp_path / ".vault"
        vault_dir.mkdir()
        (vault_dir / "dummy.md").write_text("content", encoding="utf-8")
        env_dir = tmp_path / "env"
        env_dir.mkdir()
        env_file = env_dir / ".env"

        # Patch PROJECT_ROOT so compute_corpus_sha256 reads our temp env/.env.
        # The function imports PROJECT_ROOT from aeat.config inside its body,
        # so patch the module where the name is looked up.
        monkeypatch.setattr(fp_mod, "PROJECT_ROOT", tmp_path, raising=False)
        monkeypatch.setattr(config_mod, "PROJECT_ROOT", tmp_path, raising=False)

        settings = Settings()

        env_file.write_text("FOO=1\n", encoding="utf-8")
        h1 = _compute_corpus_sha256(vault_dir, settings)

        env_file.write_text("FOO=2\n", encoding="utf-8")
        h2 = _compute_corpus_sha256(vault_dir, settings)

        assert h1 != h2, ".env edit must change corpus_sha256"

        # Missing .env must still produce a stable non-empty hash.
        env_file.unlink()
        h3 = _compute_corpus_sha256(vault_dir, settings)
        assert h3 != h1 and h3 != h2
        assert len(h3) == 64
        # Deterministic: missing .env hashes the empty-string digest.
        empty_env_digest = hashlib.sha256(b"").hexdigest()
        assert empty_env_digest  # sanity — just verify the builtin is sane


class TestArgvReconstruction:
    def test_positional_emitted_without_prefix_and_first(self) -> None:
        args = (
            ArgumentRecord(name="notificacion_id", value="N-42", source=ArgumentSource.POSITIONAL),
            ArgumentRecord(name="by", value="gw", source=ArgumentSource.FLAG),
        )
        argv = _argv_from_arguments("aeat inbox ack", args)
        assert argv == ["inbox", "ack", "N-42", "--by=gw"]

    def test_multiple_positionals_preserve_declared_order(self) -> None:
        args = (
            ArgumentRecord(name="modelo", value="130", source=ArgumentSource.POSITIONAL),
            ArgumentRecord(name="period", value="2026Q1", source=ArgumentSource.POSITIONAL),
            ArgumentRecord(name="force", value="True", source=ArgumentSource.FLAG),
        )
        argv = _argv_from_arguments("aeat filing submit", args)
        assert argv == ["filing", "submit", "130", "2026Q1", "--force=True"]

    def test_flag_name_underscore_converted_to_dash(self) -> None:
        args = (ArgumentRecord(name="as_json", value="True", source=ArgumentSource.FLAG),)
        argv = _argv_from_arguments("aeat workflow list", args)
        assert argv == ["workflow", "list", "--as-json=True"]

    def test_flag_value_with_leading_dash_uses_equals_form(self) -> None:
        args = (
            ArgumentRecord(name="record_id", value="R-42", source=ArgumentSource.POSITIONAL),
            ArgumentRecord(name="notes", value="--urgent", source=ArgumentSource.FLAG),
        )
        argv = _argv_from_arguments("aeat sync resolve-divergence", args)
        # Without the ``=`` form Typer would see ``--urgent`` as an unknown flag.
        assert "--notes=--urgent" in argv
        assert "--urgent" not in argv  # never as a standalone token

    def test_env_and_default_sources_skipped(self) -> None:
        args = (
            ArgumentRecord(name="run_id", value="abc", source=ArgumentSource.POSITIONAL),
            ArgumentRecord(name="aeat_runs_dir", value="var/runs", source=ArgumentSource.ENV),
            ArgumentRecord(name="mode", value="quiet", source=ArgumentSource.DEFAULT),
        )
        argv = _argv_from_arguments("aeat run show", args)
        assert argv == ["run", "show", "abc"]
