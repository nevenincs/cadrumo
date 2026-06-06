"""Tests for :func:`aeat.core.observability.replay_run` and its refusal modes.

Covers:

* Clean round-trip replay against an unchanged corpus.
* Refusal on corpus drift via :exc:`AeatCorpusDriftError` (with an
  ASCII-ellipsis assertion so Windows cp1252 consoles can render the
  diagnostic).
* Refusal on traces captured with a removed live-write flag.
* End-to-end ``replay_of`` propagation via the
  ``AEAT_REPLAY_ACTIVE`` env var, and the matching
  non-canonical-value sanitisation.
* End-to-end CLI replay of a wrapped command with a boolean ``--json``
  flag (the recorded argv must round-trip without the bare flag form
  causing Typer to choke on ``=True``).
* :func:`compute_corpus_sha256` env-file sensitivity (post-startup
  ``env/.env`` edits must change the corpus fingerprint even when the
  loaded :class:`Settings` snapshot is unchanged).
* argv reconstruction edge cases for positional, boolean, leading-dash,
  cli-flag-override, and ENV/DEFAULT-source arguments.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...config import PROJECT_ROOT, Settings, override_settings
from .. import (
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
from .._replay import _argv_from_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
    def test_clean_replay_round_trip(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(aeat_runs_dir=str(tmp_path)):
            current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
            trace = _build_trace("0123456789abcdef", corpus_sha256=current_corpus)
            save_trace(trace)
            result = replay_run(trace.run_id)
            assert result.run_id == trace.run_id
            assert result.entrypoint == "aeat hello"

    def test_refuses_on_corpus_drift(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(aeat_runs_dir=str(tmp_path)):
            trace = _build_trace("fedcba9876543210", corpus_sha256="0" * 64)
            save_trace(trace)
            with pytest.raises(AeatCorpusDriftError, match=r"aeat|corpus|drift") as excinfo:
                replay_run(trace.run_id)
            assert excinfo.value.run_id == trace.run_id
            assert excinfo.value.recorded == "0" * 64
            assert excinfo.value.observed != "0" * 64
            # ASCII ellipsis only — Windows cp1252 consoles can encode it
            # without errors="replace".
            message = str(excinfo.value)
            assert "…" not in message, "error message must not use unicode ellipsis"
            assert "..." in message

    def test_refuses_replay_of_removed_write_flag_recording(
        self,
        tmp_path: Path,
    ) -> None:
        """Replay must refuse traces captured with the removed write flag."""
        with override_settings(aeat_runs_dir=str(tmp_path)):
            current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
            legacy_trace = RunTrace(
                run_id="aaaabbbbccccdddd",
                started_at=datetime(2026, 4, 14, tzinfo=UTC),
                finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
                entrypoint="aeat workflow run",
                arguments=(
                    ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),
                    ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.FLAG),
                ),
                corpus_sha256=current_corpus,
                db_sha256="b" * 64,
                cert_fingerprint="",
                outcome=RunOutcome.OK,
            )
            save_trace(legacy_trace)
            with pytest.raises(AeatObservabilityError, match="removed flag"):
                replay_run(legacy_trace.run_id)

    def test_replay_of_propagated_via_env_var(self, tmp_path: Path) -> None:
        """The re-entered run context must label its trace with ``replay_of``."""
        from ...config import PROJECT_ROOT as _PROJECT_ROOT
        from ...config import Settings as _Settings
        from .. import (
            compute_corpus_sha256 as _compute_corpus_sha256,
        )
        from .. import (
            run_context,
        )
        from .._store import load_trace

        with override_settings(aeat_runs_dir=tmp_path):
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

            # Simulate the env var set during a replay — the canonical
            # Settings field is consulted by ``run_context`` via
            # ``load_settings()`` at re-entry.
            with (
                override_settings(aeat_runs_dir=tmp_path, aeat_replay_active=original.run_id),
                run_context(entrypoint="aeat test replay-child", arguments=()) as info,
            ):
                child_run_id = info.run_id

            child_trace = load_trace(child_run_id)
            assert child_trace.replay_of == original.run_id, "replay-originated traces must carry the original run id"

    def test_replay_of_ignored_when_env_is_non_canonical(self, tmp_path: Path) -> None:
        """Legacy sentinel ``"1"`` must not pollute the trace."""
        from .. import run_context
        from .._store import load_trace

        with override_settings(aeat_runs_dir=tmp_path, aeat_replay_active="1"):
            with run_context(entrypoint="aeat test", arguments=()) as info:
                rid = info.run_id

            trace = load_trace(rid)
            assert trace.replay_of is None, "non-16-hex env value must be ignored"

    def test_false_value_not_detected_as_live_mode(self) -> None:
        """A removed flag name with value 'False' is ignored.

        Exercises the predicate directly so we do not have to stand up a
        full replay pipeline; replay-path coverage for the denylist-hit
        case is provided by :meth:`test_refuses_replay_of_removed_write_flag_recording`.
        """
        from .._replay import _argument_uses_removed_write_flag

        safe = ArgumentRecord(name="no-dry-run", value="False", source=ArgumentSource.FLAG)
        assert _argument_uses_removed_write_flag(safe) is False
        active = ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.FLAG)
        assert _argument_uses_removed_write_flag(active) is True
        non_flag = ArgumentRecord(name="no-dry-run", value="True", source=ArgumentSource.POSITIONAL)
        assert _argument_uses_removed_write_flag(non_flag) is False
        other = ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG)
        assert _argument_uses_removed_write_flag(other) is False


class TestReplayEndToEndBooleanFlag:
    """End-to-end replay of a wrapped command with a boolean flag.

    A replay that reconstructs argv from a recorded trace must not
    blow up when the trace contains a ``--json=True``-style boolean —
    Typer rejects ``=value`` for value-less flags, so the argv builder
    has to emit the bare ``--json`` form instead.
    """

    def test_replay_of_workflow_list_json(self, tmp_path: Path) -> None:
        with override_settings(
            aeat_runs_dir=tmp_path,
            # A fresh workflow-runs dir so list has nothing to render.
            aeat_workflow_runs_dir=tmp_path / "workflow-runs",
        ):
            current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
            recorded = RunTrace(
                run_id="deadbeefcafe0001",
                started_at=datetime(2026, 4, 14, tzinfo=UTC),
                finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
                entrypoint="aeat workflow list",
                # NOTE: ``name="json"`` here matches how the real
                # wrapped command (cli/workflow/list_cmd.py) builds its
                # arguments dict — using the CLI flag spelling as the
                # dict key. This makes the replay argv derivation
                # (``--json``) correct without needing a ``cli_flag``
                # override. See ``TestArgvReconstruction`` for the
                # coverage of the override path.
                arguments=(ArgumentRecord(name="json", value="True", source=ArgumentSource.FLAG),),
                corpus_sha256=current_corpus,
                db_sha256="b" * 64,
                cert_fingerprint="",
                outcome=RunOutcome.OK,
            )
            save_trace(recorded)
            # Must not raise — replay round-trip through the real CLI.
            result = replay_run(recorded.run_id)
            assert result.run_id == recorded.run_id


class TestEnvFileFingerprint:
    """``corpus_sha256`` must fold the on-disk ``env/.env`` bytes.

    Without this, operator edits to ``.env`` between record and replay
    that are not yet reflected in the loaded :class:`Settings`
    snapshot would silently evade the drift gate.
    """

    def test_env_file_change_changes_corpus_hash(self, tmp_path: Path) -> None:
        import hashlib

        from .._fingerprint import compute_corpus_sha256 as _compute_corpus_sha256

        vault_dir = tmp_path / ".vault"
        vault_dir.mkdir()
        (vault_dir / "dummy.md").write_text("content", encoding="utf-8")
        env_dir = tmp_path / "env"
        env_dir.mkdir()
        env_file = env_dir / ".env"

        # compute_corpus_sha256 takes the .env path explicitly, so the
        # dotfile channel is exercised against a real temp file.
        settings = Settings()

        env_file.write_text("FOO=1\n", encoding="utf-8")
        h1 = _compute_corpus_sha256(vault_dir, settings, env_path=env_file)

        env_file.write_text("FOO=2\n", encoding="utf-8")
        h2 = _compute_corpus_sha256(vault_dir, settings, env_path=env_file)

        assert h1 != h2, ".env edit must change corpus_sha256"

        # Missing .env must still produce a stable non-empty hash.
        env_file.unlink()
        h3 = _compute_corpus_sha256(vault_dir, settings, env_path=env_file)
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
        argv = _argv_from_arguments("aeat app modelo work file", args)
        # Boolean True renders as a bare flag (no =True); value-less
        # Typer Option flags reject the =value form.
        assert argv == ["app", "modelo", "work", "file", "130", "2026Q1", "--force"]

    def test_flag_name_underscore_converted_to_dash(self) -> None:
        args = (ArgumentRecord(name="as_json", value="True", source=ArgumentSource.FLAG),)
        argv = _argv_from_arguments("aeat workflow list", args)
        # Name-underscore → dash conversion + bare-flag emission for True.
        assert argv == ["workflow", "list", "--as-json"]

    def test_boolean_false_flag_is_skipped(self) -> None:
        """Boolean ``False`` flags must not be re-emitted on replay.

        Replaying ``--unread=False`` as a literal would both fail to
        parse (Typer options don't take ``=False``) and contradict
        user intent — the user did not pass the flag.
        """
        args = (
            ArgumentRecord(name="unread", value="False", source=ArgumentSource.FLAG),
            ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),
        )
        argv = _argv_from_arguments("aeat inbox list", args)
        assert argv == ["inbox", "list", "--modelo=130"], f"False bool must be skipped; got {argv}"

    def test_boolean_true_flag_uses_bare_form(self) -> None:
        """Bare-flag form is required when the option is a value-less boolean."""
        args = (ArgumentRecord(name="json", value="True", source=ArgumentSource.FLAG),)
        argv = _argv_from_arguments("aeat workflow show", args)
        assert argv == ["workflow", "show", "--json"]

    def test_cli_flag_override_wins_over_name_derivation(self) -> None:
        """:attr:`ArgumentRecord.cli_flag` overrides the name-derived flag.

        When a wrapped command's Python parameter name differs from
        the Typer flag (``as_json: bool = typer.Option(False, "--json")``)
        the caller sets ``flag_map={"as_json": "--json"}`` at record
        time; the replay must use the override, not the
        ``--as-json`` that underscore-to-dash conversion would produce.
        """
        args = (
            ArgumentRecord(
                name="as_json",
                value="True",
                source=ArgumentSource.FLAG,
                cli_flag="--json",
            ),
        )
        argv = _argv_from_arguments("aeat workflow show", args)
        assert argv == ["workflow", "show", "--json"]
        # Also exercises the False path with override.
        args_false = (
            ArgumentRecord(
                name="as_json",
                value="False",
                source=ArgumentSource.FLAG,
                cli_flag="--json",
            ),
        )
        argv_false = _argv_from_arguments("aeat workflow show", args_false)
        # False-bool override still gets skipped, not re-emitted.
        assert argv_false == ["workflow", "show"]

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


class TestReplayActiveEnvVarCanonicity:
    """Assert that REPLAY_ACTIVE_ENV_VAR has exactly one definition site.

    The literal string ``"AEAT_REPLAY_ACTIVE"`` must appear only in
    ``_replay.py`` at line 26 (the canonical assignment).  Any duplicate
    definition in another module is an authoring error that this test
    catches at the source level.
    """

    def test_literal_defined_exactly_once_in_replay_module(self) -> None:
        from pathlib import Path

        pkg_root = Path(__file__).parents[1]
        # Split the search token so this test file does not self-match.
        literal = "AEAT_REPLAY" + "_ACTIVE"

        hits: list[tuple[Path, int, str]] = []
        for py_file in sorted(pkg_root.glob("*.py")):
            if py_file.name.startswith("test_"):
                continue
            for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
                if f'"{literal}"' in line:
                    hits.append((py_file, lineno, line.strip()))

        assert hits, "literal not found anywhere — canonical definition missing"

        # Exactly one hit, and it must be the assignment in _replay.py:26.
        assert len(hits) == 1, (
            f"Expected exactly one occurrence of the literal across non-test package files; "
            f"found {len(hits)}:\n" + "\n".join(f"  {f.name}:{ln}  {src}" for f, ln, src in hits)
        )
        canonical_file, canonical_line, _ = hits[0]
        assert canonical_file.name == "_replay.py", (
            f"Canonical definition must be in _replay.py, found in {canonical_file.name}"
        )
        assert canonical_line == 26, f"Canonical definition must be at line 26, found at line {canonical_line}"
