"""The oversized reader-facing frame advisory.

A reader-facing frame whose recorded output exceeds
:data:`~dev.docs.sequences.checks.READER_FRAME_OUTPUT_ADVISORY_BYTES` draws a
named advisory from both refresh and check, never a failure. The boundary is
pinned on synthetic frames (exact byte counts, multi-byte text, every stored
stream), and both surfaces are driven end to end through a real command that
straddles the limit: ``app modelo casillas`` prints well over it as JSON and
well under it as text, which is exactly the remedy the advisory recommends.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from cadrumo.tests.golden_comparison import canonicalise

from ..checks import (
    READER_FRAME_OUTPUT_ADVISORY_BYTES,
    check_sequences,
    oversized_frame_advisories,
    recorded_output_bytes,
    refresh_sequences,
)
from ..cli import main
from ..golden_store import GoldenFrame, SequenceGolden
from ..schema import FrameKind

_PAGE = "tutorials/output-advisory-case"
_SEQUENCE_ID = "output-advisory-case"
_ARGV = ("aeat", "app", "modelo", "casillas", "303")
_LIMIT = READER_FRAME_OUTPUT_ADVISORY_BYTES


def _golden(*frames: GoldenFrame) -> SequenceGolden:
    return SequenceGolden(sequence_id=_SEQUENCE_ID, frames=frames)


def _text_frame(text: str, *, kind: FrameKind = FrameKind.COMMAND) -> GoldenFrame:
    return GoldenFrame(kind=kind, argv=_ARGV, exit_code=0, text=text)


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
class TestAdvisoryBoundary:
    def test_the_limit_is_sixty_four_kibibytes(self) -> None:
        assert _LIMIT == 65536

    def test_output_at_the_limit_draws_no_advisory(self) -> None:
        frame = _text_frame("x" * _LIMIT)
        assert recorded_output_bytes(frame) == _LIMIT
        assert oversized_frame_advisories(_PAGE, _golden(frame)) == ()

    def test_one_byte_over_the_limit_draws_a_named_advisory(self) -> None:
        frame = _text_frame("x" * (_LIMIT + 1))
        advisories = oversized_frame_advisories(_PAGE, _golden(_text_frame("short"), frame))
        assert len(advisories) == 1
        advisory = advisories[0]
        assert repr(_PAGE) in advisory and repr(_SEQUENCE_ID) in advisory
        assert "frame 1 " in advisory
        assert " ".join(_ARGV) in advisory
        assert f"{_LIMIT + 1} bytes" in advisory
        assert "print the text output" in advisory and "narrow the command" in advisory

    def test_size_is_measured_in_utf8_bytes_not_characters(self) -> None:
        """A two-byte character counts twice, so half the limit in characters is
        exactly at the limit and one more ASCII byte crosses it."""
        at_limit = _text_frame("é" * (_LIMIT // 2))
        assert len(at_limit.text or "") == _LIMIT // 2
        assert recorded_output_bytes(at_limit) == _LIMIT
        assert oversized_frame_advisories(_PAGE, _golden(at_limit)) == ()

        over = _text_frame("é" * (_LIMIT // 2) + "x")
        assert len(oversized_frame_advisories(_PAGE, _golden(over))) == 1

    def test_envelope_text_and_stderr_all_count_toward_the_size(self) -> None:
        """Every stored stream is recorded output: the canonical JSON of the
        envelope plus the stdout text plus the stderr text. Split across two
        streams, a frame crosses the limit though neither stream does alone."""
        half = _LIMIT // 2
        envelope: dict[str, JsonValue] = {"status": "success", "result": {"rows": ["r" * half]}}
        envelope_bytes = len(canonicalise(envelope).encode("utf-8"))
        enveloped = GoldenFrame(
            kind=FrameKind.RESULT,
            argv=_ARGV,
            exit_code=0,
            envelope=envelope,
            envelope_source="stdout",
            stderr_text="w" * half,
        )
        assert envelope_bytes < _LIMIT
        assert recorded_output_bytes(enveloped) == envelope_bytes + half
        assert len(oversized_frame_advisories(_PAGE, _golden(enveloped))) == 1

        texts = GoldenFrame(kind=FrameKind.RESULT, argv=_ARGV, exit_code=0, text="t" * half, stderr_text="w" * half)
        assert recorded_output_bytes(texts) == _LIMIT
        assert oversized_frame_advisories(_PAGE, _golden(texts)) == ()
        longer = GoldenFrame(
            kind=FrameKind.RESULT,
            argv=_ARGV,
            exit_code=0,
            text="t" * half,
            stderr_text="w" * (half + 1),
        )
        assert len(oversized_frame_advisories(_PAGE, _golden(longer))) == 1

    def test_setup_frames_are_never_measured(self) -> None:
        """Setup frames are not reader-facing and record no output."""
        setup = GoldenFrame(kind=FrameKind.SETUP, argv=_ARGV, exit_code=0)
        assert oversized_frame_advisories(_PAGE, _golden(setup, _text_frame("small"))) == ()


#: One setup frame, then the same real command as text (under the limit) and as
#: JSON (over it). Only the JSON frame may draw the advisory.
_CONTRACT_BODY = "\n".join(
    [
        "@setup aeat --format json config profile list",
        "aeat app modelo casillas 303 --period 1T",
        "@result aeat --format json app modelo casillas 303 --period 1T",
        "@expect exit_code == 0",
    ],
)

_PAGE_TEXT = (
    "# Output advisory case\n"
    "\n"
    "Create a profile first with `aeat config profile create`.\n"
    "\n"
    f"```{{cli-sequence}} {_SEQUENCE_ID}\n"
    ":verify: Verify the casilla listing is produced.\n"
    "```\n"
)

_JSON_ARGV = "aeat --format json app modelo casillas 303 --period 1T"


def _oversized(advisories: tuple[str, ...]) -> list[str]:
    return [advisory for advisory in advisories if "reader-facing limit" in advisory]


@pytest.fixture(scope="module")
def docs_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("advisory-docs")
    page = root / f"{_PAGE}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_PAGE_TEXT, encoding="utf-8")
    contract = root / "_sequences" / "contracts" / _PAGE / f"{_SEQUENCE_ID}.seq"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(_CONTRACT_BODY + "\n", encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def refreshed(docs_tree: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, tuple[str, ...]]:
    goldens_root = tmp_path_factory.mktemp("advisory-goldens")
    written, problems, advisories = refresh_sequences(docs_root=docs_tree, goldens_root=goldens_root)
    assert problems == (), problems
    assert len(written) == 1
    return goldens_root, advisories


@pytest.mark.integration
@pytest.mark.hex_core
@pytest.mark.docs
class TestBothModesReportTheAdvisory:
    def test_the_real_command_straddles_the_limit(self, refreshed: tuple[Path, tuple[str, ...]]) -> None:
        """Anti-vacuity: the fixture measures what the surface tests assume, so a
        command that shrinks below the limit fails here, not silently later."""
        goldens_root, _ = refreshed
        stored = json.loads((goldens_root / _PAGE / f"{_SEQUENCE_ID}.json").read_text(encoding="utf-8"))
        golden = SequenceGolden.model_validate_json(json.dumps(stored))
        _setup, text_frame, json_frame = golden.frames
        assert text_frame.text is not None and recorded_output_bytes(text_frame) <= _LIMIT
        assert json_frame.envelope is not None and recorded_output_bytes(json_frame) > _LIMIT

    def test_refresh_reports_the_oversized_frame_from_the_golden_it_writes(
        self,
        refreshed: tuple[Path, tuple[str, ...]],
    ) -> None:
        _goldens_root, advisories = refreshed
        oversized = _oversized(advisories)
        assert len(oversized) == 1, advisories
        assert "frame 2 " in oversized[0]
        assert _JSON_ARGV in oversized[0]

    def test_check_reports_the_oversized_frame_without_failing(
        self,
        docs_tree: Path,
        refreshed: tuple[Path, tuple[str, ...]],
    ) -> None:
        goldens_root, _ = refreshed
        problems, advisories = check_sequences(docs_root=docs_tree, goldens_root=goldens_root)
        assert problems == (), problems
        oversized = _oversized(advisories)
        assert len(oversized) == 1, advisories
        assert "frame 2 " in oversized[0]
        assert _JSON_ARGV in oversized[0]

    def test_check_measures_the_committed_golden(self, docs_tree: Path, tmp_path: Path) -> None:
        """Check reads the size from the committed golden, not the live run: a
        golden whose oversized frame was trimmed draws no advisory even though
        the live output is still large, and the trim itself is a divergence."""
        refreshed_root = tmp_path / "goldens"
        written, problems, _advisories = refresh_sequences(docs_root=docs_tree, goldens_root=refreshed_root)
        assert problems == () and len(written) == 1
        document = json.loads(written[0].read_text(encoding="utf-8"))
        document["frames"][2]["envelope"]["result"] = {}
        written[0].write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        problems, advisories = check_sequences(docs_root=docs_tree, goldens_root=refreshed_root)
        assert _oversized(advisories) == []
        assert any("frame 2" in problem for problem in problems), problems

    def test_the_cli_prints_the_advisory_on_the_advisory_channel(
        self,
        docs_tree: Path,
        refreshed: tuple[Path, tuple[str, ...]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        goldens_root, _ = refreshed
        exit_code = main(["check", "--docs-root", str(docs_tree), "--goldens-root", str(goldens_root)])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        advisory_lines = [line for line in captured.out.splitlines() if "reader-facing limit" in line]
        assert len(advisory_lines) == 1
        assert advisory_lines[0].startswith("advisory: ")
        assert "reader-facing limit" not in captured.err
