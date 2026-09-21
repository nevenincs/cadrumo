"""A platform-variant recipe pair must agree on what it does, not how it says it.

``just`` lets one recipe name carry two bodies, one per platform attribute, and
a runner executes exactly one of them. The two are written in different shells
and read nothing like each other, which is the point -- and which is also why
nobody compares them. Nothing else in this repository does: the only test that
handles pairs at all,
``test_check_set_contract.py::test_platform_variant_recipes_are_read_once_per_platform``,
asserts that a pair's commands are COUNTED once rather than twice, and its
fixture happens to give both sides identical bodies. It would pass unchanged if
the two did completely different things, because it only ever reads the unix
side. ``declared_lanes`` flattens a pair into two independent rows and never
compares them either.

The motivating example is live and sits in the required merge gate. ``test-gate``
is a platform pair. Its unix body ends with a bare ``just test-pytest-harness``
and relies on ``set -euo pipefail`` to propagate a failure; its windows body
follows the same call with an explicit ``$LASTEXITCODE`` check. Those are
equivalent TODAY. Delete ``set -e`` from the unix body and the harness verdict
is silently swallowed on Linux while Windows still fails the job -- a gate
weaker on one operating system than the other, with nothing anywhere to say so.

So this compares MEANING and refuses to compare text. Five properties, each
readable from the body without executing either shell:

* the ``-m`` marker expressions, because a pair selecting different tests is
  two different gates wearing one name;
* the pytest target paths, for the same reason one level out;
* the non-zero exit statuses each side tolerates, which is the specific
  asymmetry most likely to recur -- an exit-5 tolerance added to one body and
  forgotten on the other turns an empty selection into a hard failure on one
  platform only;
* the ``just`` recipes each side invokes, because a pair that delegates
  differently runs different work regardless of what its own lines say;
* the pytest options, which exist because two live pairs -- ``test-coverage``
  and ``doctor-python`` -- carry none of the four above, and a pair the
  reader takes nothing from passes while asserting nothing. That is the
  precise failure this file was written to name in another test, so it has
  to be refused here too; ``test_the_gate_can_say_something_about_every_pair
  _that_runs_pytest`` keeps it refused.

Textual equality is deliberately NOT asserted. The bodies differ in idiom
because that is the entire reason a pair exists, and a gate demanding they
match character for character would have to be suppressed immediately.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT

from ..lane_reachability import _recipes_invoked_by

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ROOT: Final[Path] = REPO_ROOT
_UTF_8: Final[str] = "utf-8"

#: The platform attributes just understands, mapped to the platform that runs them.
_PLATFORM_ATTRIBUTES: Final[dict[str, str]] = {
    "[unix]": "unix",
    "[linux]": "unix",
    "[macos]": "unix",
    "[windows]": "windows",
}

#: A recipe header: a name at column zero, then optional parameters, then a colon.
_RECIPE_HEADER: Final[re.Pattern[str]] = re.compile(r"^(?P<name>[a-z][\w-]*)\b[^:\n]*:(?![=])")

#: A pytest marker expression, in either quoting style.
_MARKER_EXPRESSION: Final[re.Pattern[str]] = re.compile(r"-m\s+(['\"])(?P<expression>.*?)\1")

#: A repository-relative test target as a recipe writes one.
_TARGET_PATH: Final[re.Pattern[str]] = re.compile(r"(?:dev|src|packaging)/[\w./*-]+")

#: A pytest option as either shell writes one. Included because two of the six
#: live pairs carry no marker expression, no repository path and no delegated
#: recipe, so without it the gate would read nothing from them and pass while
#: saying nothing -- which is the failure this file was written to name in
#: somebody else's test.
#: `-ne` is a shell comparison operator, not an option, so the worker pin is
#: matched only in its real forms: a count, `auto`, or a just variable.
_PYTEST_OPTION: Final[re.Pattern[str]] = re.compile(r"(?<![\w-])(--[\w-]+(?:=\S+)?|-n\s?(?:\d+|auto|\{\{[^}]+\}\}))")

#: The token that proves a body runs pytest at all, and therefore that the gate
#: ought to be able to say something about it.
_PYTEST_CALL: Final[str] = "pytest"

#: An exit-status comparison. Both idioms spell it `-ne`: bash as
#: `"$status" -ne 5`, pwsh as `$LASTEXITCODE -ne 5`.
_EXIT_COMPARISON: Final[re.Pattern[str]] = re.compile(r"-ne\s+(?P<status>\d+)")


def _platform_bodies(text: str) -> dict[tuple[str, str], str]:
    """Return every platform-attributed recipe body, keyed by (name, platform).

    Only recipes that DECLARE a platform attribute are returned. An ordinary
    recipe has one body for every platform and cannot disagree with itself.
    """
    bodies: dict[tuple[str, str], list[str]] = {}
    attributes: list[str] = []
    current: tuple[str, str] | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if raw.startswith("[") and stripped.endswith("]"):
            attributes.append(stripped)
            continue
        header = _RECIPE_HEADER.match(raw)
        if header is not None:
            platforms = {_PLATFORM_ATTRIBUTES[item] for item in attributes if item in _PLATFORM_ATTRIBUTES}
            name = header.group("name")
            current = (name, platforms.pop()) if len(platforms) == 1 and isinstance(name, str) else None
            attributes = []
            if current is not None:
                bodies.setdefault(current, [])
            continue
        if stripped and raw[:1] not in {" ", "\t", "@"}:
            current = None
            attributes = []
            continue
        if current is not None:
            bodies[current].append(raw)
    return {key: "\n".join(lines) for key, lines in bodies.items()}


def _meaning(body: str) -> dict[str, frozenset[str]]:
    """Return the four comparable properties of one recipe body."""
    return {
        "marker expressions": frozenset(match.group("expression") for match in _MARKER_EXPRESSION.finditer(body)),
        "target paths": frozenset(_TARGET_PATH.findall(body)),
        "tolerated exit statuses": frozenset(
            match.group("status") for match in _EXIT_COMPARISON.finditer(body) if match.group("status") != "0"
        ),
        "pytest options": frozenset(match.group(1) for match in _PYTEST_OPTION.finditer(body)),
        "invoked recipes": frozenset(_recipes_invoked_by(body)),
    }


def _divergences(bodies: dict[tuple[str, str], str]) -> list[str]:
    """Return one finding per property a pair disagrees on."""
    names = {name for name, _platform in bodies}
    findings: list[str] = []
    for name in sorted(names):
        unix = bodies.get((name, "unix"))
        windows = bodies.get((name, "windows"))
        if unix is None or windows is None:
            continue
        unix_meaning = _meaning(unix)
        windows_meaning = _meaning(windows)
        for label, unix_value in unix_meaning.items():
            windows_value = windows_meaning[label]
            if unix_value != windows_value:
                findings.append(f"{name}: {label} differ -- unix {sorted(unix_value)}, windows {sorted(windows_value)}")
    return findings


@pytest.fixture(name="live_bodies", scope="module")
def _live_bodies() -> dict[tuple[str, str], str]:
    """Return the platform-attributed bodies of the tracked justfile."""
    return _platform_bodies((_ROOT / "justfile").read_text(encoding=_UTF_8))


def test_the_reader_finds_the_live_pairs(live_bodies: dict[tuple[str, str], str]) -> None:
    """Anchor: a reader that found no pairs would pass every case below.

    Named rather than counted, and `test-gate` is named explicitly because it is
    the recipe the required merge gate runs and the reason this file exists.
    """
    paired = {
        name for name, _platform in live_bodies if (name, "unix") in live_bodies and (name, "windows") in live_bodies
    }

    assert paired, "no platform-variant recipe pair was read; every case below would be vacuous"
    assert "test-gate" in paired, f"the merge gate's own recipe is not being read as a pair: {sorted(paired)}"


def test_every_platform_pair_agrees_on_what_it_does(live_bodies: dict[tuple[str, str], str]) -> None:
    """The gate. Idiom may differ; selection, targets, tolerance and delegation may not."""
    divergences = _divergences(live_bodies)

    assert divergences == [], (
        "these platform-variant recipes do different work depending on the operating system, "
        "so a gate is weaker on one of them than the other:\n  " + "\n  ".join(divergences)
    )


def test_the_gate_can_say_something_about_every_pair_that_runs_pytest(
    live_bodies: dict[tuple[str, str], str],
) -> None:
    """A pair the reader takes nothing from passes while asserting nothing.

    That is the exact shape this file exists to refuse elsewhere, so it has to
    refuse it about itself. A pair whose bodies invoke pytest must yield at
    least one comparable property; if a future recipe reads as entirely empty,
    this fails rather than quietly adding an unguarded pair.
    """
    silent: list[str] = []
    for (name, platform), body in sorted(live_bodies.items()):
        if _PYTEST_CALL not in body:
            continue
        if not any(_meaning(body).values()):
            silent.append(f"{name} [{platform}]")

    assert silent == [], (
        "the reader extracted no comparable property from these pytest-running bodies, so the "
        "parity gate passes them without comparing anything:\n  " + "\n  ".join(silent)
    )


def test_a_pair_differing_only_in_idiom_is_accepted() -> None:
    """The positive control, and the reason textual equality is not asserted.

    This is `test-ci-contracts-serial`'s real shape reduced to its essentials:
    bash captures the status in a variable, pwsh reads `$LASTEXITCODE`, and the
    two share a marker expression, a target and an exit-5 tolerance. A gate
    that reported this would be suppressed within a day.
    """
    justfile = (
        "[unix]\n"
        "serial:\n"
        "    #!/usr/bin/env bash\n"
        "    set -uo pipefail\n"
        '    uv run pytest -n0 -m "serial" dev/ci/tests\n'
        "    status=$?\n"
        '    if [ "$status" -ne 0 ] && [ "$status" -ne 5 ]; then\n'
        '        exit "$status"\n'
        "    fi\n"
        "\n"
        "[windows]\n"
        "serial:\n"
        "    #!pwsh\n"
        "    $ErrorActionPreference = 'Continue'\n"
        '    uv run pytest -n0 -m "serial" dev/ci/tests\n'
        "    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 5) { exit $LASTEXITCODE }\n"
    )

    assert _divergences(_platform_bodies(justfile)) == []


def test_a_pair_selecting_different_tests_is_reported() -> None:
    """Teeth: two gates wearing one name."""
    justfile = (
        "[unix]\n"
        "lane:\n"
        '    uv run pytest -m "unit" dev/ci/tests\n'
        "\n"
        "[windows]\n"
        "lane:\n"
        '    uv run pytest -m "unit and not slow" dev/ci/tests\n'
    )

    divergences = _divergences(_platform_bodies(justfile))

    assert len(divergences) == 1
    assert "lane: marker expressions differ" in divergences[0]


def test_a_pair_tolerating_an_exit_status_on_one_side_only_is_reported() -> None:
    """Teeth for the asymmetry most likely to recur.

    An exit-5 tolerance added to one body and forgotten on the other turns an
    empty selection into a hard failure on that platform alone -- and an empty
    selection is exactly what a marker move produces, which is how this class
    arrives in the first place.
    """
    justfile = (
        "[unix]\n"
        "serial:\n"
        '    uv run pytest -n0 -m "serial" dev/ci/tests\n'
        "    status=$?\n"
        '    if [ "$status" -ne 0 ] && [ "$status" -ne 5 ]; then\n'
        '        exit "$status"\n'
        "    fi\n"
        "\n"
        "[windows]\n"
        "serial:\n"
        '    uv run pytest -n0 -m "serial" dev/ci/tests\n'
        "    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n"
    )

    divergences = _divergences(_platform_bodies(justfile))

    assert len(divergences) == 1
    assert "serial: tolerated exit statuses differ" in divergences[0]


def test_a_pair_delegating_to_different_recipes_is_reported() -> None:
    """Teeth: a body's own lines can match while the work it delegates does not."""
    justfile = "[unix]\ngate:\n    just test-pytest-harness\n\n[windows]\ngate:\n    just test-unit\n"

    divergences = _divergences(_platform_bodies(justfile))

    assert len(divergences) == 1
    assert "gate: invoked recipes differ" in divergences[0]


def test_a_recipe_without_a_platform_attribute_is_not_a_pair() -> None:
    """An ordinary recipe has one body everywhere and cannot disagree with itself."""
    justfile = 'plain:\n    uv run pytest -m "unit" dev/ci/tests\n'

    bodies = _platform_bodies(justfile)

    assert bodies == {}
    assert _divergences(bodies) == []
