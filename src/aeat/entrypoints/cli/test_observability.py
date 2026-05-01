"""Tests for the shared ``cli_run_context`` helpers and replay command.

Exercises
:func:`aeat.entrypoints.cli._observability.build_arguments`: ordering
rules (positional first, then flags in insertion order), filtering of
``None`` values, secret-substring redaction (case-insensitive across
``api_key``/``secret``/``passphrase``/``token``/``credential``), and
the ``flag_map`` plumbing that populates
:attr:`aeat.core.observability.ArgumentRecord.cli_flag`. Also covers
``aeat run replay`` round-tripping a persisted
:class:`aeat.core.observability.RunTrace`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...core.config import PROJECT_ROOT, Settings
from ...core.observability import ArgumentSource, RunOutcome, RunTrace, compute_corpus_sha256, save_trace
from . import app
from ._observability import build_arguments

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class TestBuildArguments:
    """Ordering, filtering, and source-tagging rules for ``build_arguments``."""

    def test_preserves_insertion_order_for_flags(self) -> None:
        values = {"b_flag": "1", "a_flag": "2", "c_flag": "3"}
        records = build_arguments(values)
        assert tuple(r.name for r in records) == ("b_flag", "a_flag", "c_flag")
        assert all(r.source is ArgumentSource.FLAG for r in records)

    def test_positional_first_then_flags(self) -> None:
        values = {"as_json": True, "run_id": "abcd1234", "since": "2026-01-01"}
        records = build_arguments(values, positional=("run_id",))
        assert records[0].name == "run_id"
        assert records[0].source is ArgumentSource.POSITIONAL
        flag_names = tuple(r.name for r in records[1:])
        assert flag_names == ("as_json", "since")
        assert all(r.source is ArgumentSource.FLAG for r in records[1:])

    def test_multiple_positionals_preserve_declared_order(self) -> None:
        values = {"modelo": "130", "period": "2026Q1", "force": True}
        records = build_arguments(values, positional=("modelo", "period"))
        positional_names = tuple(r.name for r in records if r.source is ArgumentSource.POSITIONAL)
        assert positional_names == ("modelo", "period")

    def test_none_values_are_skipped(self) -> None:
        values = {"modelo": None, "period": "2026Q1"}
        records = build_arguments(values, positional=("modelo",))
        assert tuple(r.name for r in records) == ("period",)


class TestSecretRedaction:
    """Secret-substring detection and value redaction in ``build_arguments``."""

    def test_secret_named_flag_redacted(self) -> None:
        values = {"password": "hunter2", "modelo": "130"}
        records = build_arguments(values)
        by_name = {r.name: r.value for r in records}
        assert by_name["password"] == "***"  # noqa: S105 - literal sentinel, not a password
        assert by_name["modelo"] == "130"

    def test_every_secret_substring_matched_case_insensitive(self) -> None:
        values = {
            "api_key": "secret-1",
            "CLIENT_SECRET": "secret-2",
            "user_passphrase": "secret-3",
            "auth_token": "secret-4",
            "credential_path": "secret-5",
            "modelo": "130",
            "period": "2026Q1",
        }
        records = build_arguments(values)
        by_name = {r.name: r.value for r in records}
        for secret_key in (
            "api_key",
            "CLIENT_SECRET",
            "user_passphrase",
            "auth_token",
            "credential_path",
        ):
            assert by_name[secret_key] == "***", f"{secret_key} should be redacted"
        assert by_name["modelo"] == "130"
        assert by_name["period"] == "2026Q1"

    def test_secret_positional_redacted(self) -> None:
        values = {"password": "pw-value"}
        records = build_arguments(values, positional=("password",))
        assert records[0].value == "***"


class TestFlagMap:
    """``flag_map`` propagation to :attr:`ArgumentRecord.cli_flag`."""

    def test_flag_map_sets_cli_flag(self) -> None:
        values = {"as_json": True, "modelo": "130"}
        records = build_arguments(values, flag_map={"as_json": "--json"})
        by_name = {r.name: r for r in records}
        assert by_name["as_json"].cli_flag == "--json"
        # Unmapped args have cli_flag=None and rely on name derivation.
        assert by_name["modelo"].cli_flag is None

    def test_missing_flag_map_leaves_cli_flag_none(self) -> None:
        records = build_arguments({"modelo": "130"})
        assert records[0].cli_flag is None

    def test_flag_map_ignored_for_positional(self) -> None:
        values = {"modelo": "130"}
        # Even if the caller maps a positional, it must stay POSITIONAL
        # with cli_flag=None (positional records never use cli_flag).
        records = build_arguments(values, positional=("modelo",), flag_map={"modelo": "--modelo"})
        assert records[0].source.value == "POSITIONAL"
        assert records[0].cli_flag is None


class TestReplayCommand:
    """End-to-end smoke for ``aeat run replay``."""

    def test_replay_invokes_recorded_cli_entrypoint(self, tmp_path: Path) -> None:
        """A persisted ``RunTrace`` is round-tripped through the replay command."""
        settings = Settings(aeat_runs_dir=tmp_path)
        trace = RunTrace(
            run_id="0123456789abcdef",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat run list",
            arguments=(),
            corpus_sha256=compute_corpus_sha256(PROJECT_ROOT / ".vault", settings),
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(trace, settings=settings)

        result = CliRunner().invoke(
            app,
            ["run", "replay", trace.run_id],
            env={"AEAT_RUNS_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0, result.output
        assert "replay OK" in result.output
        assert trace.run_id in result.output
