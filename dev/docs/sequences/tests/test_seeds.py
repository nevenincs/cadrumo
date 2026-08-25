"""Real-behaviour tests for ``:seed:`` recipe loading and inlining.

These prove that a named seed recipe of ``@setup`` frames is read from disk,
parsed, and inlined before a sequence's own frames; that its captures thread into
the body's placeholders; that a recipe may hold only ``@setup`` frames; and that a
missing or malformed recipe surfaces as an instructive accumulated problem, never
a silent skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from .. import (
    SANDBOX_PROFILE_LABEL,
    SEED_SUFFIX,
    FrameKind,
    default_seeds_root,
    load_seed_frames,
    parse_sequence,
)
from ..errors import SequenceParseError

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


# --- Committed seed recipes stay bound to the sandbox contract -------------
#
# A committed recipe runs inside the runner's sandbox, whose one profile is
# registered under ``SANDBOX_PROFILE_LABEL``. A recipe frame that addresses a
# profile must therefore use exactly that label — a hardcoded copy silently
# breaks every enrolled page at docs-build time the day the constant moves.
# These tests bind the committed literals to the constant so a rename fails
# HERE, naming the seed and line, instead of failing in the docs build.


def _committed_seeds() -> tuple[Path, ...]:
    return scan_directory(default_seeds_root(), pattern=f"*{SEED_SUFFIX}")


def _profile_label_positional(argv: tuple[str, ...]) -> str | None:
    """Return the profile-label positional of a ``config profile <verb>`` frame.

    The label is the first positional token after the verb, skipping options
    and their space-separated values (an ``=``-joined value rides its option
    token). Returns ``None`` for frames that do not address a profile.
    """
    tokens = list(argv)
    try:
        anchor = next(
            index for index in range(len(tokens) - 1) if tokens[index] == "config" and tokens[index + 1] == "profile"
        )
    except StopIteration:
        return None
    previous_was_option = False
    for token in tokens[anchor + 3 :]:  # after "config profile <verb>"
        if token.startswith("-"):
            previous_was_option = "=" not in token
            continue
        if previous_was_option:
            previous_was_option = False
            continue
        return token
    return None


def test_committed_seeds_parse_cleanly() -> None:
    """Every committed recipe loads without problems, so a broken seed reds the
    engine suite instead of the next docs build."""
    seeds = _committed_seeds()
    assert seeds, f"no committed seed recipes under {default_seeds_root()}"
    for path in seeds:
        _, problems = load_seed_frames(path.stem)
        assert problems == [], f"{path.name}: {problems}"


def test_committed_seed_profile_labels_are_the_sandbox_label() -> None:
    """F3 binding: every profile-addressing frame in a committed recipe uses
    the CURRENT ``SANDBOX_PROFILE_LABEL`` — renaming the constant fails here,
    naming the seed and line, not silently at docs-build time."""
    labelled_frames = 0
    for path in _committed_seeds():
        builders, problems = load_seed_frames(path.stem)
        assert problems == [], f"{path.name}: {problems}"
        for builder in builders:
            label = _profile_label_positional(builder.argv)
            if label is None:
                continue
            labelled_frames += 1
            assert label == SANDBOX_PROFILE_LABEL, (
                f"{path.name} line {builder.line_number}: profile label {label!r} "
                f"must be the sandbox profile label {SANDBOX_PROFILE_LABEL!r} "
                "(the runner registers exactly one profile, under that label)"
            )
    # Anti-vacuity ratchet: the corpus currently addresses the profile at least
    # once; if a future recipe reshape removes every such frame, this assert
    # fails so the binding is consciously re-anchored rather than rotting.
    assert labelled_frames > 0, "no committed seed frame addresses a profile; re-anchor this binding test"


def test_seed_step_descriptions_inline_with_their_frames(tmp_path: Path) -> None:
    """An ``@step`` in a recipe rides its ``@setup`` frame through inlining,
    located in the recipe for diagnostics, exactly like the frame itself."""
    _write_seed(
        tmp_path,
        "with-steps",
        "@step Create the taxpayer profile.\n"
        "@setup aeat config profile create --nif 12345678Z\n"
        "@setup aeat app ledger import --file fixtures/2026-1t-statement.csv\n",
    )
    sequence = _parse_with_seed(tmp_path, seed="with-steps")

    first, second = sequence.frames[0], sequence.frames[1]
    assert first.step_description == "Create the taxpayer profile."
    assert first.source == "seed:with-steps"
    assert second.step_description is None


def test_seed_trailing_step_is_located_in_the_recipe(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        "trailing-step",
        "@setup aeat config profile create --nif 12345678Z\n@step This attaches to nothing.\n",
    )
    with pytest.raises(SequenceParseError) as excinfo:
        _parse_with_seed(tmp_path, seed="trailing-step")
    assert any(
        "seed:trailing-step line 2" in problem and "trailing @step" in problem for problem in excinfo.value.problems
    )
