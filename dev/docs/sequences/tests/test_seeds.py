"""Real-behaviour tests for ``:seed:`` recipe loading and inlining (ADR D6).

These prove that a named seed recipe of ``@setup`` frames is read from disk,
parsed, and inlined before a sequence's own frames; that its captures thread into
the body's placeholders; that a recipe may hold only ``@setup`` frames; and that a
missing or malformed recipe surfaces as an instructive accumulated problem, never
a silent skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import (
    FrameKind,
    SequenceParseError,
    load_seed_frames,
    parse_sequence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


_VERIFY = "Verify the calculation before exporting."
_BODY = (
    "aeat app modelo create 303 --year 2026 --period 1T\n"
    "@result aeat app modelo verify\n"
    '@expect result.status == "verified_complete"\n'
)


def _write_seed(root: Path, name: str, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.seq"
    path.write_text(text, encoding="utf-8")
    return path


def _parse_with_seed(seeds_root: Path, *, seed: str, body: str = _BODY):
    return parse_sequence(
        sequence_id="modelo-303-first-quarter",
        options={"verify": _VERIFY, "seed": seed},
        body=body,
        seeds_root=seeds_root,
    )


def test_seed_frames_are_inlined_before_body_frames(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "autonomo-basic-2026",
        "@setup aeat config profile create --nif 12345678Z\n"
        "@setup aeat app ledger import --file fixtures/2026-1t-statement.csv\n",
    )
    sequence = _parse_with_seed(tmp_path, seed="autonomo-basic-2026")

    kinds = [frame.kind for frame in sequence.frames]
    assert kinds == [FrameKind.SETUP, FrameKind.SETUP, FrameKind.COMMAND, FrameKind.RESULT]
    assert sequence.seed == "autonomo-basic-2026"

    first, second = sequence.frames[0], sequence.frames[1]
    assert first.source == "seed:autonomo-basic-2026"
    assert first.argv == ("aeat", "config", "profile", "create", "--nif", "12345678Z")
    assert second.argv == ("aeat", "app", "ledger", "import", "--file", "fixtures/2026-1t-statement.csv")
    # Body frames keep their own source.
    assert sequence.frames[2].source == "body"


def test_seed_capture_threads_into_body_placeholder(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "with-profile",
        "@setup aeat config profile create --nif 12345678Z\n@capture profile_id result.profile_id\n",
    )
    body = (
        "aeat app modelo create 303 --profile {profile_id}\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    sequence = _parse_with_seed(tmp_path, seed="with-profile", body=body)

    assert sequence.capture_names == ("profile_id",)
    create_frame = sequence.frames[1]
    assert create_frame.placeholder_names == ("profile_id",)


def test_missing_recipe_is_an_instructive_problem(tmp_path: Path) -> None:
    with pytest.raises(SequenceParseError) as excinfo:
        _parse_with_seed(tmp_path, seed="does-not-exist")
    assert any("recipe not found" in problem for problem in excinfo.value.problems)


def test_recipe_with_visible_command_frame_is_refused(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "leaky",
        "@setup aeat config profile create --nif 12345678Z\naeat app modelo create 303\n",
    )
    with pytest.raises(SequenceParseError) as excinfo:
        _parse_with_seed(tmp_path, seed="leaky")
    assert any("may contain only @setup frames" in problem for problem in excinfo.value.problems)


def test_recipe_with_result_frame_is_refused(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "has-result",
        "@setup aeat config profile create --nif 12345678Z\n@result aeat app modelo verify\n",
    )
    with pytest.raises(SequenceParseError) as excinfo:
        _parse_with_seed(tmp_path, seed="has-result")
    assert any("may contain only @setup frames" in problem for problem in excinfo.value.problems)


def test_load_seed_frames_returns_setup_builders_directly(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "basic",
        "@setup aeat config profile create --nif 12345678Z\n",
    )
    builders, problems = load_seed_frames("basic", seeds_root=tmp_path)
    assert problems == []
    assert len(builders) == 1
    assert builders[0].kind is FrameKind.SETUP
    assert builders[0].source == "seed:basic"


def test_load_seed_frames_reports_missing_recipe(tmp_path: Path) -> None:
    builders, problems = load_seed_frames("absent", seeds_root=tmp_path)
    assert builders == []
    assert any("recipe not found" in problem for problem in problems)


def test_seed_grammar_faults_are_located_in_the_recipe(tmp_path: Path) -> None:
    _write_seed(tmp_path, "broken", "@setup ls -la\n")
    with pytest.raises(SequenceParseError) as excinfo:
        _parse_with_seed(tmp_path, seed="broken")
    assert any(
        "seed:broken line 1" in problem and "must invoke 'aeat'" in problem for problem in excinfo.value.problems
    )
