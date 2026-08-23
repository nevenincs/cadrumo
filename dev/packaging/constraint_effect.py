"""Assert an installed environment matches the tested pinned constraint closure.

The Scoop manifest and the MCPB bundle install the product wheels and then let
``uv`` resolve their transitive dependencies against a pinned constraints file
exported from ``uv.lock`` (:mod:`dev.packaging.uv_constraints`). Pinning the
closure at install time is necessary but not sufficient: nothing yet observes
that the environment the installer actually produced landed on those pins. This
module closes that gap. It drives the *installed* interpreter to enumerate its
own distributions through :mod:`importlib.metadata` (a standard-library
one-liner, so no ``pip`` dependency is assumed inside the provisioned
environment), parses the pinned rows, and refuses — fail-closed — when any
constrained distribution is missing or drifted from its pin.

Distribution names are compared under PEP 503 normalisation on both sides.
Environment markers are EVALUATED against the running platform, not treated as
a mere if-installed hint. A universal lock export lists platform-gated rows
(``jeepney`` on Linux, ``pywin32`` on Windows) and may pin one name to
different versions under mutually exclusive markers. A row whose marker is false
here describes another platform and is ignored. A row whose marker is true here
(or carries no marker) is ACTIVE: its distribution must be installed at exactly
that version — so a gated distribution missing on its OWN platform is a
failure, and only the version whose marker holds is accepted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from packaging.markers import InvalidMarker, Marker

from dev._paths import UTF_8

from ._distribution_names import normalise_distribution_name

_UTF_8: Final[str] = UTF_8

#: A one-liner run by the INSTALLED interpreter. It imports only the standard
#: library, so it carries no ``pip`` dependency and works in the bundle-local or
#: Scoop-provisioned virtual environment exactly as installed.
_ENUMERATE_SNIPPET: Final[str] = (
    "import importlib.metadata, json;"
    "print(json.dumps({"
    "(d.metadata['Name'] or '').lower(): d.version "
    "for d in importlib.metadata.distributions() if d.metadata['Name']"
    "}))"
)

_VERSION_REJECT: Final[str] = " ,<>=!*"


class ConstraintDriftError(RuntimeError):
    """Raised when the installed environment diverges from the pinned closure."""


@dataclass(frozen=True)
class ConstraintPin:
    """One constrained distribution that is ACTIVE on the running platform.

    ``versions`` accumulates the pinned version(s) from every row whose marker
    holds here (marker-free rows always hold). Because markers are evaluated,
    mutually exclusive rows contribute only the version whose marker is true, so
    on any single platform this is normally one version. Every entry in the
    parsed map is required present: an active distribution missing from the
    installed set is a failure.
    """

    name: str
    versions: frozenset[str]


def _marker_is_active(marker_text: str) -> bool:
    """Return True when ``marker_text`` holds for the running environment.

    An empty marker always holds. An unparseable marker is fail-closed: it
    raises rather than silently dropping (or silently keeping) the row.
    """
    text = marker_text.strip()
    if not text:
        return True
    try:
        return bool(Marker(text).evaluate())
    except InvalidMarker as exc:
        raise ConstraintDriftError(f"constraint row has an invalid environment marker: {text!r}") from exc


def parse_constraint_lines(constraint_lines: Sequence[str]) -> dict[str, ConstraintPin]:
    """Parse ``name==version`` rows into a normalised name -> :class:`ConstraintPin` map.

    Blank rows, comment rows, and marker-only continuation rows are ignored. The
    environment marker after ``;`` is EVALUATED against the running platform: a
    row whose marker is false describes another platform and is dropped, so it
    contributes neither a version nor a requiredness. Only bare ``==`` pins are
    honoured; a non-pinned or compound-specifier row is refused so a loose
    requirement can never silently pass the effect gate.
    """
    versions: dict[str, set[str]] = {}
    for raw in constraint_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirement, _marker_sep, marker = stripped.partition(";")
        requirement = requirement.strip()
        if not requirement:
            # A marker-only continuation line carries no requirement to pin.
            continue
        if "==" not in requirement:
            raise ConstraintDriftError(f"constraint row is not an == pin: {stripped!r}")
        name_part, _, version = requirement.partition("==")
        name = normalise_distribution_name(name_part.split("[", 1)[0])
        version = version.strip()
        if not name or not version or any(character in version for character in _VERSION_REJECT):
            raise ConstraintDriftError(f"constraint row is not a single == pin: {stripped!r}")
        if not _marker_is_active(marker):
            # Another platform's row: not expected in this environment.
            continue
        versions.setdefault(name, set()).add(version)
    if not versions:
        raise ConstraintDriftError("no active pinned constraints were parsed for this platform")
    return {name: ConstraintPin(name=name, versions=frozenset(pins)) for name, pins in versions.items()}


def enumerate_installed_distributions(python_exe: Path) -> dict[str, str]:
    """Return the normalised name -> version map of ``python_exe``'s installed set."""
    completed = subprocess.run(  # noqa: S603 - fixed stdlib snippet, caller-provided interpreter
        [str(python_exe), "-c", _ENUMERATE_SNIPPET],
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
        check=False,
    )
    if completed.returncode != 0:
        raise ConstraintDriftError(
            f"could not enumerate installed distributions via {python_exe}: "
            f"exit {completed.returncode}; stderr:\n{completed.stderr.strip()}",
        )
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ConstraintDriftError(
            f"{python_exe} did not emit one distribution JSON object: {completed.stdout!r}",
        ) from exc
    if not isinstance(raw, dict):
        raise ConstraintDriftError(f"{python_exe} emitted a non-object distribution set: {raw!r}")
    return {normalise_distribution_name(str(name)): str(version) for name, version in raw.items()}


def assert_installed_matches_constraints(python_exe: Path, constraint_lines: Sequence[str]) -> None:
    """Refuse unless ``python_exe``'s installed set matches the pinned closure.

    Every constrained distribution ACTIVE on the running platform (marker-free,
    or marker true here) must be installed at exactly one of its active pinned
    versions — so a gated distribution missing on its own platform fails, and a
    name pinned under mutually exclusive markers accepts only the version whose
    marker holds. On any drift or missing active distribution a
    :class:`ConstraintDriftError` is raised enumerating each offending
    distribution as ``name: expected <pins>, actual <observed>``.
    """
    pins = parse_constraint_lines(constraint_lines)
    installed = enumerate_installed_distributions(python_exe)
    problems: list[str] = []
    for name, pin in sorted(pins.items()):
        expected = ", ".join(sorted(pin.versions))
        actual = installed.get(name)
        if actual is None:
            problems.append(f"  {name}: expected {expected}, actual <missing>")
            continue
        if actual not in pin.versions:
            problems.append(f"  {name}: expected {expected}, actual {actual}")
    if problems:
        raise ConstraintDriftError(
            "installed environment diverged from the pinned constraint closure "
            f"({python_exe}):\n" + "\n".join(problems),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path, help="Installed interpreter to inspect.")
    parser.add_argument(
        "--constraints",
        required=True,
        type=Path,
        help="Pinned constraints file exported from uv.lock.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Assert the installed environment matches the pinned constraints from the CLI."""
    args = _parser().parse_args(argv)
    constraint_lines = args.constraints.read_text(encoding=_UTF_8).splitlines()
    try:
        assert_installed_matches_constraints(args.python, constraint_lines)
    except ConstraintDriftError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"installed environment matches the pinned constraint closure: {args.python}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
