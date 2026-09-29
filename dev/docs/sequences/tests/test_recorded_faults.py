"""Gate: no record that captured a crash, or an undeclared failure, becomes a golden.

A golden captured while the process was crashing INVERTS the gate it belongs to.
``check`` compares a later run against it, so a golden fingerprinting a
traceback goes GREEN on the breakage and RED on the repair — the exact opposite
of what a regression gate is for. One instance shipped: ``filing-spine-file``
frames 8-9 recorded a storage-fault traceback, captured while the fault was live,
and was re-recorded in commit ``7991f30d19``.

The refusal therefore lives where a golden is born: refresh will not fingerprint
such a record, and check fails on one even when it matches its golden. The
scanner reads every carrier of every frame, so each carrier and each frame
position is proved separately below — a first version of this gate read the
wrong keys and reported a clean corpus of 189 goldens after reading nothing.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable

import pytest
from pydantic import JsonValue

from ..checks import check_sequences, refresh_sequences
from ..parser import parse_sequence
from ..record_store import RecordFrame, SequenceRecord
from ..recorded_faults import (
    FAILURE_MARKERS,
    VERSION_LITERAL,
    crash_findings,
    recorded_output_text,
    undeclared_error_findings,
    version_literal_findings,
)
from ..schema import FrameKind, ParsedSequence

_PAGE = "how-to/recorded-faults"
_ARGV = ("aeat", "--format", "json", "app", "overview", "status")
_TRACEBACK = 'Traceback (most recent call last):\n  File "<repo-root>/src/cadrumo/app.py", line 1\n'


def _frame(**streams: object) -> RecordFrame:
    fields: dict[str, object] = {"kind": FrameKind.COMMAND, "argv": _ARGV, "exit_code": 0}
    fields.update(streams)
    return RecordFrame.model_validate(fields)


def _record(*frames: RecordFrame) -> SequenceRecord:
    return SequenceRecord(sequence_id="recorded-faults", frames=frames)


_CLEAN = _frame(envelope={"status": "ok", "result": {"profile": "docs-sequence-sandbox"}}, envelope_source="stdout")


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
class TestCrashMarkers:
    @pytest.mark.parametrize(
        "streams",
        [
            {"text": _TRACEBACK},
            {"stderr_text": _TRACEBACK},
            {"envelope": {"status": "error", "error": {"category": "INTERNAL"}}, "envelope_source": "stderr"},
        ],
        ids=["stdout-text", "stderr-text", "envelope"],
    )
    def test_every_carrier_is_read(self, streams: dict[str, object]) -> None:
        findings = crash_findings(_record(_frame(**streams)), page=_PAGE)
        assert findings, "a crash in this carrier was not seen"
        assert "frame 0" in findings[0] and repr(_PAGE) in findings[0]

    def test_a_crash_in_a_later_frame_is_found(self) -> None:
        """A reader that stopped at the first frame would pass this corpus."""
        findings = crash_findings(_record(_CLEAN, _CLEAN, _frame(stderr_text="--- Logging error ---\n")), page=_PAGE)
        assert len(findings) == 1
        assert "frame 2" in findings[0] and "logging_error" in findings[0]

    @pytest.mark.parametrize("name", sorted(FAILURE_MARKERS))
    def test_each_marker_bites(self, name: str) -> None:
        samples = {
            "traceback": "Traceback (most recent call last)",
            "source_frame": 'File "src/cadrumo/cli.py", line 3',
            "logging_error": "--- Logging error ---",
            "unraisable": "Exception ignored in: <function f>",
            "internal_category": '{"category": "INTERNAL"}',
            "internal_code": "INTERNAL_STORAGE_FAULT",
        }
        findings = crash_findings(_record(_frame(text=samples[name])), page=_PAGE)
        assert any(f"({name}:" in finding for finding in findings), findings

    def test_an_ordinary_refusal_and_clean_output_are_not_crashes(self) -> None:
        """Anti-vacuity: the markers are crash shapes, not every error document."""
        refusal = _frame(
            envelope={"status": "error", "error": {"category": "REFUSED", "code": "WORK_UNIT_NOT_FOUND"}},
            envelope_source="stderr",
            exit_code=2,
        )
        assert crash_findings(_record(_CLEAN, refusal, _frame(text="Imported 3 transactions.\n")), page=_PAGE) == ()
        assert "docs-sequence-sandbox" in recorded_output_text(_CLEAN)


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
class TestUndeclaredErrorOutcomes:
    _BODY = "aeat --format json app overview status\n@result aeat --format json app overview status\n"

    def _sequence(self, expects: str = "") -> ParsedSequence:
        return parse_sequence(
            sequence_id="recorded-faults",
            options={"verify": "Verify the status reads."},
            body=self._BODY + expects + '@expect result.profile == "docs-sequence-sandbox"\n',
        )

    @staticmethod
    def _error(exit_code: int) -> RecordFrame:
        envelope: dict[str, JsonValue] = {"status": "error", "error": {"category": "REFUSED"}}
        return _frame(kind=FrameKind.RESULT, envelope=envelope, envelope_source="stderr", exit_code=exit_code)

    @pytest.mark.parametrize("exit_code", [0, 2], ids=["error-envelope-exit-0", "error-envelope-exit-2"])
    def test_an_undeclared_error_outcome_is_refused(self, exit_code: int) -> None:
        findings = undeclared_error_findings(self._sequence(), _record(_CLEAN, self._error(exit_code)), page=_PAGE)
        assert len(findings) == 1
        assert "frame 1" in findings[0] and f"exit {exit_code}" in findings[0]

    @pytest.mark.parametrize(
        "expects",
        ["@expect exit_code == 2\n", '@expect error.category == "REFUSED"\n'],
        ids=["exit-code", "error-path"],
    )
    def test_a_declared_error_outcome_is_accepted(self, expects: str) -> None:
        sequence = self._sequence(expects)
        assert undeclared_error_findings(sequence, _record(_CLEAN, self._error(2)), page=_PAGE) == ()

    def test_a_clean_run_needs_no_declaration(self) -> None:
        assert undeclared_error_findings(self._sequence(), _record(_CLEAN, _CLEAN), page=_PAGE) == ()


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
class TestVersionLiterals:
    """Pages render from records, so a captured version would be frozen user-facing prose.

    It happened: two goldens froze ``0.2.1``, the version declaration was later
    reset, and the docs build failed on a divergence whose suggested remedy
    would have baked the stale number back in.
    """

    def test_the_detector_discriminates(self) -> None:
        assert VERSION_LITERAL.findall("CADRUMO 0.2.1\n") == ["CADRUMO 0.2.1"]
        assert VERSION_LITERAL.findall("CADRUMO 10.20.30\n") == ["CADRUMO 10.20.30"]
        assert VERSION_LITERAL.findall("CADRUMO <version>\n") == []

    @pytest.mark.parametrize(
        "streams",
        [
            {"text": "CADRUMO 0.2.1\n"},
            {"stderr_text": "running CADRUMO 0.2.1"},
            {"envelope": {"status": "ok", "result": {"banner": "CADRUMO 0.2.1"}}, "envelope_source": "stdout"},
        ],
        ids=["stdout-text", "stderr-text", "envelope"],
    )
    def test_a_version_literal_in_any_carrier_is_refused(self, streams: dict[str, object]) -> None:
        findings = version_literal_findings(_record(_CLEAN, _frame(**streams)), page=_PAGE)
        assert len(findings) == 1 and "frame 1" in findings[0] and "'CADRUMO 0.2.1'" in findings[0]

    def test_the_normalised_token_is_accepted(self) -> None:
        assert version_literal_findings(_record(_frame(text="CADRUMO <version>\n")), page=_PAGE) == ()


def _called_names(function: Callable[..., object]) -> set[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
@pytest.mark.parametrize("engine_function", [refresh_sequences, check_sequences], ids=["refresh", "check"])
def test_refresh_and_check_judge_every_record(engine_function: Callable[..., object]) -> None:
    """Both places a record is produced run both rules over it.

    No hermetic command crashes on demand, and the runner itself refuses an
    undeclared non-zero exit before a record exists, so the wiring is proved on
    the engine's own source rather than by an end-to-end run.
    """
    assert {"crash_findings", "undeclared_error_findings", "version_literal_findings"} <= _called_names(
        engine_function,
    )
