"""Tests for :func:`cadrumo.core.observability.replay_run` and its refusal modes.

Covers:

* Clean round-trip replay against an unchanged corpus.
* Refusal on corpus drift via :exc:`AeatCorpusDriftError` (with an
  ASCII-ellipsis assertion so Windows cp1252 consoles can render the
  diagnostic).
* Refusal on traces captured with a removed live-write flag.
* End-to-end ``replay_of`` propagation via the
  ``CADRUMO_REPLAY_ACTIVE`` env var, and the matching
  non-canonical-value sanitisation.
* End-to-end CLI replay of a wrapped command with a boolean ``--json``
  flag (the recorded argv must round-trip without the bare flag form
  causing Typer to choke on ``=True``).
* argv reconstruction edge cases for positional, boolean, leading-dash,
  cli-flag-override, and ENV/DEFAULT-source arguments.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.storage_scope import storage_overrides
from ...config import Settings, override_settings
from ...directory_scan import scan_directory
from ...storage_taxonomy import StorageCategory
from ..errors import AeatCorpusDriftError, CadrumoObservabilityError
from ..fingerprint import compute_corpus_sha256
from ..models import ArgumentRecord, ArgumentSource, RunOutcome, RunTrace
from ..replay import _argv_from_arguments, replay_run
from ..store import save_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _build_trace(run_id: str, *, corpus_sha256: str) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=datetime(2026, 4, 14, tzinfo=UTC),
        finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
        entrypoint="cadrumo hello",
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
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            current_corpus = compute_corpus_sha256(Settings())
            trace = _build_trace("0123456789abcdef", corpus_sha256=current_corpus)
            save_trace(trace)
            result = replay_run(trace.run_id)
            assert result.run_id == trace.run_id
            assert result.entrypoint == "cadrumo hello"

    def test_refuses_on_corpus_drift(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
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
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            current_corpus = compute_corpus_sha256(Settings())
            legacy_trace = RunTrace(
                run_id="aaaabbbbccccdddd",
                started_at=datetime(2026, 4, 14, tzinfo=UTC),
                finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
                entrypoint="cadrumo workflow run",
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
            with pytest.raises(CadrumoObservabilityError, match="removed flag"):
                replay_run(legacy_trace.run_id)

    def test_replay_of_propagated_via_env_var(self, tmp_path: Path) -> None:
        """The re-entered run context must label its trace with ``replay_of``."""
        from ...config import Settings as _Settings
        from ..context import run_context
        from ..fingerprint import compute_corpus_sha256 as _compute_corpus_sha256
        from ..store import load_trace

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            current_corpus = _compute_corpus_sha256(_Settings())
            original = RunTrace(
                run_id="1111222233334444",
                started_at=datetime(2026, 4, 14, tzinfo=UTC),
                finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
                entrypoint="cadrumo test replay",
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
                override_settings(
                    cadrumo_replay_active=original.run_id,
                    **storage_overrides(tmp_path, StorageCategory.RUNS),
                ),
                run_context(entrypoint="cadrumo test replay-child", arguments=()) as info,
            ):
                child_run_id = info.run_id

            child_trace = load_trace(child_run_id)
            assert child_trace.replay_of == original.run_id, "replay-originated traces must carry the original run id"

    def test_replay_of_ignored_when_env_is_non_canonical(self, tmp_path: Path) -> None:
        """Legacy sentinel ``"1"`` must not pollute the trace."""
        from ..context import run_context
        from ..store import load_trace

        with override_settings(
            cadrumo_replay_active="1",
            **storage_overrides(tmp_path, StorageCategory.RUNS),
        ):
            with run_context(entrypoint="cadrumo test", arguments=()) as info:
                rid = info.run_id

            trace = load_trace(rid)
            assert trace.replay_of is None, "non-16-hex env value must be ignored"

    def test_false_value_not_detected_as_live_mode(self) -> None:
        """A removed flag name with value 'False' is ignored.

        Exercises the predicate directly so we do not have to stand up a
        full replay pipeline; replay-path coverage for the denylist-hit
        case is provided by :meth:`test_refuses_replay_of_removed_write_flag_recording`.
        """
        from ..replay import _argument_uses_removed_write_flag

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
            # A fresh workflow-runs dir so list has nothing to render.
            **storage_overrides(tmp_path, StorageCategory.RUNS, StorageCategory.WORKFLOW_RUNS),
        ):
            current_corpus = compute_corpus_sha256(Settings())
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


class TestArgvReconstruction:
    def test_argv_reconstruction_cases(self) -> None:
        cases: tuple[
            tuple[str, str, tuple[ArgumentRecord, ...], tuple[str, ...]],
            ...,
        ] = (
            (
                "positional-first",
                "aeat inbox ack",
                (
                    ArgumentRecord(name="notificacion_id", value="N-42", source=ArgumentSource.POSITIONAL),
                    ArgumentRecord(name="by", value="gw", source=ArgumentSource.FLAG),
                ),
                ("inbox", "ack", "N-42", "--by=gw"),
            ),
            (
                "multiple-positionals",
                "aeat app modelo work file",
                (
                    ArgumentRecord(name="modelo", value="130", source=ArgumentSource.POSITIONAL),
                    ArgumentRecord(name="period", value="2026Q1", source=ArgumentSource.POSITIONAL),
                    ArgumentRecord(name="force", value="True", source=ArgumentSource.FLAG),
                ),
                ("app", "modelo", "work", "file", "130", "2026Q1", "--force"),
            ),
            (
                "underscore-flag",
                "aeat workflow list",
                (ArgumentRecord(name="as_json", value="True", source=ArgumentSource.FLAG),),
                ("workflow", "list", "--as-json"),
            ),
            (
                "false-bool-skipped",
                "aeat inbox list",
                (
                    ArgumentRecord(name="unread", value="False", source=ArgumentSource.FLAG),
                    ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),
                ),
                ("inbox", "list", "--modelo=130"),
            ),
            (
                "true-bool-bare",
                "aeat workflow show",
                (ArgumentRecord(name="json", value="True", source=ArgumentSource.FLAG),),
                ("workflow", "view", "--json"),
            ),
            (
                "leading-dash-value",
                "aeat sync resolve-divergence",
                (
                    ArgumentRecord(name="record_id", value="R-42", source=ArgumentSource.POSITIONAL),
                    ArgumentRecord(name="notes", value="--urgent", source=ArgumentSource.FLAG),
                ),
                ("sync", "resolve-divergence", "R-42", "--notes=--urgent"),
            ),
            (
                "env-default-skipped",
                "aeat run show",
                (
                    ArgumentRecord(name="run_id", value="abc", source=ArgumentSource.POSITIONAL),
                    ArgumentRecord(name="cadrumo_runs_dir", value="var/runs", source=ArgumentSource.ENV),
                    ArgumentRecord(name="mode", value="quiet", source=ArgumentSource.DEFAULT),
                ),
                ("run", "view", "abc"),
            ),
        )

        for case_id, entrypoint, args, expected in cases:
            assert tuple(_argv_from_arguments(entrypoint, args)) == expected, case_id

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
        assert argv == ["workflow", "view", "--json"]
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
        assert argv_false == ["workflow", "view"]


class TestReplayActiveEnvVarCanonicity:
    """Assert that REPLAY_ACTIVE_ENV_VAR has exactly one definition site.

    The literal string ``"CADRUMO_REPLAY_ACTIVE"`` must appear only in
    ``replay.py`` at line 26 (the canonical assignment).  Any duplicate
    definition in another module is an authoring error that this test
    catches at the source level.
    """

    def test_literal_defined_exactly_once_in_replay_module(self) -> None:
        from pathlib import Path

        pkg_root = Path(__file__).parents[1]
        # Split the search token so this test file does not self-match.
        literal = "CADRUMO_REPLAY" + "_ACTIVE"

        hits: list[tuple[Path, int, str]] = []
        for py_file in scan_directory(pkg_root, pattern="*.py"):
            if py_file.name.startswith("test_"):
                continue
            for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
                if f'"{literal}"' in line:
                    hits.append((py_file, lineno, line.strip()))

        assert hits, "literal not found anywhere — canonical definition missing"

        # Exactly one hit, and it must be the canonical assignment in replay.py.
        assert len(hits) == 1, (
            f"Expected exactly one occurrence of the literal across non-test package files; "
            f"found {len(hits)}:\n" + "\n".join(f"  {f.name}:{ln}  {src}" for f, ln, src in hits)
        )
        canonical_file, _canonical_line, canonical_source = hits[0]
        assert canonical_file.name == "replay.py", (
            f"Canonical definition must be in replay.py, found in {canonical_file.name}"
        )
        assert canonical_source.startswith("REPLAY_ACTIVE_ENV_VAR = ")
