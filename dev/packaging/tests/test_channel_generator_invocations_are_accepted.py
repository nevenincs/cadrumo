"""Every flag the cohort build passes a channel generator is one it accepts.

The cohort build shells out to the Homebrew and Scoop generators. Nothing binds
the two: the caller assembles an argument list, the generator declares a parser,
and a flag removed from one side stays spelled on the other until something runs
a real build. That is minutes into a workflow, on a self-hosted runner, after a
cohort has already been compiled -- the most expensive place in the project to
discover a typo.

It has happened. Removing the release-asset base URL from both generators left
the caller still passing ``--release-base-url``; the argument parser refused,
the build died four minutes in, and no local suite noticed, because every test
that exercises a generator calls its Python entry point directly rather than
through the command line the build actually uses.

So the subjects are DISCOVERED from the caller rather than listed here: the
flags are read out of the invocation, the parser is read out of the generator,
and the two are compared. A flag added to either side is covered the moment it
is written.

This checks the contract, not the behaviour -- that the generator would accept
the call, not that it produces a correct manifest. The generator suites own
that, and they build a real cohort to do it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The module that assembles the generator command lines.
_CALLER: Final = REPO_ROOT / "dev" / "packaging" / "release_cohort.py"

#: Generators the caller invokes, by the path fragment naming each in the source.
_GENERATORS: Final = {
    "scoop": REPO_ROOT / "packaging" / "scoop" / "generate.py",
    "homebrew": REPO_ROOT / "packaging" / "homebrew" / "generate.py",
}

#: A long option as it appears in an assembled argument list.
_FLAG: Final = re.compile(r'^--[a-z][a-z0-9-]*$')


def _string_constants(node: ast.AST) -> list[str]:
    """Every string literal anywhere beneath ``node``.

    The caller builds a generator's path by joining components, so the path is
    a call rather than a literal and a shallow read of the list finds neither
    the channel name nor the flags beside it. Descending is what makes the two
    visible together.
    """
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _passed_flags(source: str, channel: str) -> set[str]:
    """Return the long options the caller passes to ``channel``'s generator.

    Read from the syntax tree rather than by pattern, because an argument list
    is exactly the shape a regular expression reads plausibly and wrongly: a
    flag spelled in a neighbouring call would be attributed here and the gate
    would fail against a caller that is correct. The channel's own name
    appearing in the same list is what ties the list to one generator.
    """
    flags: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.List):
            continue
        literals = _string_constants(node)
        if channel not in literals:
            continue
        flags.update(text for text in literals if _FLAG.match(text))
    return flags


def _accepted_flags(path: Path) -> set[str]:
    """Return the long options a generator's parser declares.

    Also read from the syntax tree. Executing the module would resolve a parser
    built inside a function, but it also runs whatever else the module does at
    import, and it made this gate fail on a generator that is correct -- a
    dataclass cannot resolve its own annotations under a synthetic module name.
    Every option here is a literal in an ``add_argument`` call, so reading them
    needs no execution at all.
    """
    flags: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        attribute = node.func
        if not isinstance(attribute, ast.Attribute) or attribute.attr != "add_argument":
            continue
        flags.update(
            argument.value
            for argument in node.args
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and _FLAG.match(argument.value)
        )
    return flags


@pytest.mark.parametrize("channel", sorted(_GENERATORS))
def test_the_cohort_build_passes_only_flags_the_generator_declares(channel: str) -> None:
    """The failure this prevents costs a full cohort build to discover."""
    passed = _passed_flags(_CALLER.read_text(encoding="utf-8"), channel)
    accepted = _accepted_flags(_GENERATORS[channel])

    assert passed, f"no flags were discovered for the {channel} generator; this gate is asserting nothing"
    assert accepted, f"no parser options were discovered in the {channel} generator"

    unknown = sorted(passed - accepted)
    assert unknown == [], (
        f"the cohort build passes {unknown} to the {channel} generator, which does not declare them. "
        "The build fails at argument parsing, minutes in, after the cohort has already been compiled."
    )


def test_the_gate_reports_a_flag_the_generator_dropped(tmp_path: Path) -> None:
    """Teeth, in the exact shape the real defect took.

    A generator loses an option while the caller keeps passing it. Written
    against an isolated pair rather than by mutating either real file.
    """
    generator = tmp_path / "scoop" / "generate.py"
    generator.parent.mkdir()
    generator.write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        'parser.add_argument("--cohort-dir", required=True)\n'
        'parser.add_argument("--output", required=True)\n',
        encoding="utf-8",
    )
    caller = (
        "cmd = [\n"
        '    "python",\n'
        '    str(root / "packaging" / "scoop" / "generate.py"),\n'
        '    "--cohort-dir", str(d),\n'
        '    "--release-base-url", url,\n'
        '    "--output", str(o),\n'
        "]\n"
    )

    passed = _passed_flags(caller, "scoop")
    accepted = _accepted_flags(generator)

    assert "--release-base-url" in passed
    assert sorted(passed - accepted) == ["--release-base-url"]


def test_a_matching_pair_is_accepted(tmp_path: Path) -> None:
    """The other direction: a caller in step with its generator must pass.

    Without this the gate is indistinguishable from one that reports every
    flag as unknown, which would be red on a correct tree and teach a reader
    to ignore it.
    """
    generator = tmp_path / "homebrew" / "generate.py"
    generator.parent.mkdir()
    generator.write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        'parser.add_argument("--cohort-dir", required=True)\n'
        'parser.add_argument("--output-dir", required=True)\n',
        encoding="utf-8",
    )
    caller = (
        "cmd = [\n"
        '    "python",\n'
        '    str(root / "packaging" / "homebrew" / "generate.py"),\n'
        '    "--cohort-dir", str(d),\n'
        '    "--output-dir", str(o),\n'
        "]\n"
    )

    assert sorted(_passed_flags(caller, "homebrew") - _accepted_flags(generator)) == []
