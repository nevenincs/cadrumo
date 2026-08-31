"""The wrapper CI actually runs must say when the layering gate evaluated nothing.

``dev/quality/suite.py`` annotates an aborted ``lint-imports`` run, and
``dev/audit/report.py`` reconciles evaluated contracts against declared ones.
Both are correct, and neither was on the path CI takes: the ``check-imports``
recipe shells out to ``dev.quality.quiet``, which replayed the tool's output
verbatim. So the one distinction that matters -- a gate that found violations
versus a gate that ran none of its contracts -- was drawn everywhere except
where it would be read.

That is not hypothetical. The gate spent most of a day aborting on a stale
ignore pin, and its entire output was the single line naming that pin. Read
quickly it looks like one narrow complaint about one import; it is every
layering contract going unchecked. It died, was repaired, and died again
within hours.

The annotation is applied to every failing command rather than keyed on the
command's name, and that is deliberate twice over. ``annotate_unevaluated_contracts``
matches the linter's own markers rather than failure itself, so another tool's
output passes through untouched. And a name-keyed branch could not be exercised
without invoking the real linter binary, which would make the guard's own test
depend on the thing it guards.

Both directions are pinned below. An annotator that fired on a genuine breach
would be worse than none: it would tell the reader the gate had not run when it
had, and the breaches it reported were the ones needing attention.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: Real output from the run that found the gate dead, before the pin was removed.
_ABORTED: Final = (
    "=============\n"
    "Import Linter\n"
    "=============\n"
    "\n"
    "\n"
    "No matches for ignored import cadrumo.application.aggregation._modelo_bindings\n"
    "-> cadrumo.adapters.persistence.**.\n"
)

#: Real output from the same command once the stale pin was gone.
_EVALUATED: Final = (
    "=============\n"
    "Import Linter\n"
    "=============\n"
    "\n"
    "Analyzed 5693 files, 34994 dependencies.\n"
    "Contracts: 6 kept, 4 broken.\n"
)


def _run_wrapper(payload: str, *, fail: bool = True) -> subprocess.CompletedProcess[str]:
    """Drive the REAL wrapper over a stand-in that prints ``payload``.

    The stand-in is an interpreter rather than the linter, which is the point:
    the annotation must not depend on recognising a command name, or this test
    could not reach it without invoking the real binary.
    """
    script = f"import sys; sys.stdout.write({payload!r})"
    if fail:
        script += "; raise SystemExit(1)"
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell, test-owned argv
        [sys.executable, "-m", "dev.quality.quiet", sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=_REPO_ROOT,
        check=False,
    )


def test_an_aborted_run_is_named_as_evaluating_nothing() -> None:
    """The blast radius must reach the reader, not just the offending pin's name."""
    result = _run_wrapper(_ABORTED)

    assert "NO CONTRACTS WERE EVALUATED" in result.stdout
    assert "cadrumo.application.aggregation._modelo_bindings" in result.stdout
    assert result.returncode == 1


def test_a_run_that_evaluated_contracts_is_replayed_untouched() -> None:
    """A genuine breach must not be dressed up as a dead gate."""
    result = _run_wrapper(_EVALUATED)

    assert "NO CONTRACTS WERE EVALUATED" not in result.stdout
    assert "Contracts: 6 kept, 4 broken." in result.stdout


def test_an_unrelated_failure_passes_through_untouched() -> None:
    """The wrapper stays a general primitive for every other tool it wraps."""
    result = _run_wrapper("ruff: 3 errors found\n")

    assert "NO CONTRACTS WERE EVALUATED" not in result.stdout
    assert "ruff: 3 errors found" in result.stdout


def test_a_successful_run_stays_silent() -> None:
    """The wrapper's whole purpose survives the change."""
    result = _run_wrapper("chatter that a green tool would print", fail=False)

    assert result.returncode == 0
    assert result.stdout == ""
