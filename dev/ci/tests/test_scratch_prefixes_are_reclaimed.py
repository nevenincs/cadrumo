"""Every ``mkdtemp`` scratch family is reclaimed by something.

A ``TemporaryDirectory`` cleans itself up when its block ends. A bare
``mkdtemp`` does not, and nothing in the language complains: the directory
simply stays, one per call, until a person notices the volume filling. On this
shared box that is not hypothetical. A census of the operator's temp directory
found **7,403** ``cadrumo-object-name-`` snapshots of the whole tracked tree,
fourteen ``cadrumo-client-venv-`` copies of a 4.3 GB development environment,
and fifty-eight built wheel cohorts -- roughly 69 GB, and 80% of every entry in
the directory, none of it reachable by any sweep.

Each of those was fixed where it was found. This gate exists because finding
them that way does not scale: the sweep's prefix tuple is a list someone has to
remember to extend, and a prefix added to a ``mkdtemp`` call and forgotten here
leaks silently and indefinitely. So the subjects are DISCOVERED from the source
rather than enumerated -- a new scratch family is covered the moment it is
written, or this fails naming it.

Two ways to satisfy the rule, because both are legitimate:

* the prefix is swept centrally, which is what catches a process that is
  *killed* and so runs no finalizer at all; or
* the call site registers its own finalizer, which is what handles the clean
  path promptly rather than waiting out a staleness ceiling.

A family that does neither is the defect.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from cadrumo.tests.collection_storage_root import SWEPT_SCRATCH_STEMS, SETTINGS_STEM

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Prefixes the central sweep reclaims. The per-session stem carries the owning
#: PID and is minted by the sweep's own module, so it is not a discovered
#: subject; every other swept family is.
_SWEPT: Final = (*SWEPT_SCRATCH_STEMS, SETTINGS_STEM, "cadrumo-pytest-")

#: A ``mkdtemp`` naming a Cadrumo scratch family. Spans lines, because the call
#: is routinely wrapped, and a single-line pattern would silently under-report
#: exactly the sites most likely to be missed.
_MKDTEMP: Final = re.compile(
    r"""mkdtemp\(\s*(?:[^)]*?,\s*)?prefix\s*=\s*["'](cadrumo-[a-z0-9-]*)["']""",
    re.DOTALL,
)

#: Evidence that a module disposes of what it mints. Deliberately coarse: this
#: gate proves a finalizer was *registered*, not that it is correct, and says so
#: rather than implying a guarantee it cannot make. The central sweep is the
#: rule that does not depend on reading intent out of a call site.
_FINALIZED: Final = re.compile(r"atexit\.register|addfinalizer|\brmtree\b")

#: Trees that can mint a scratch directory. Excludes the vault, which is
#: documentation, and caches, which are build output.
_SOURCE_ROOTS: Final = ("src", "dev", "packaging")


def _python_sources() -> list[Path]:
    return sorted(
        path
        for root in _SOURCE_ROOTS
        for path in (REPO_ROOT / root).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _unreclaimed(paths: list[Path]) -> tuple[list[str], int]:
    """Return every unreclaimed scratch family, and how many were examined.

    The count is what stops this passing vacuously. A discovery gate that finds
    no subject at all reports exactly the same green as one where every subject
    complies, and the first of those is asserting nothing.
    """
    offenders: list[str] = []
    examined = 0
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        prefixes = set(_MKDTEMP.findall(source))
        if not prefixes:
            continue
        finalized = bool(_FINALIZED.search(source))
        for prefix in sorted(prefixes):
            examined += 1
            if prefix.startswith(_SWEPT) or finalized:
                continue
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {prefix!r}")
    return offenders, examined


def test_every_scratch_family_is_swept_or_finalized() -> None:
    """The failure this prevents is a volume filling, reported by nothing."""
    offenders, examined = _unreclaimed(_python_sources())

    assert examined, "no mkdtemp scratch family was discovered; this gate is asserting nothing"
    assert offenders == [], (
        "these scratch families are neither swept centrally nor finalized at their call site, "
        "so one directory accumulates per call forever:\n  " + "\n  ".join(offenders)
    )


def test_a_new_unreclaimed_family_is_reported(tmp_path: Path) -> None:
    """Teeth, against an isolated file rather than the tree being protected.

    Written the way the defect actually appeared: a plain ``mkdtemp`` with a
    fresh prefix and no disposal anywhere in the module.
    """
    leak = tmp_path / "leaks.py"
    leak.write_text(
        'import tempfile\nroot = tempfile.mkdtemp(prefix="cadrumo-brand-new-family-")\n',
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([leak])

    assert examined == 1
    assert len(offenders) == 1
    assert "cadrumo-brand-new-family-" in offenders[0]


def test_a_finalized_family_is_accepted(tmp_path: Path) -> None:
    """The rule has two satisfying halves, and the second must really pass.

    Without this the gate would be indistinguishable from one that demands
    central sweeping and nothing else, which would push call sites into the
    tuple that have already solved the problem locally.
    """
    tidy = tmp_path / "tidy.py"
    tidy.write_text(
        "import atexit, shutil, tempfile\n"
        'root = tempfile.mkdtemp(prefix="cadrumo-brand-new-family-")\n'
        "atexit.register(shutil.rmtree, root, ignore_errors=True)\n",
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([tidy])

    assert examined == 1
    assert offenders == []


def test_the_pattern_reads_a_wrapped_call(tmp_path: Path) -> None:
    """A call split across lines is the shape most likely to be missed.

    It is also the shape the real leaks took, so a single-line pattern would
    have under-reported precisely the sites this gate exists for.
    """
    wrapped = tmp_path / "wrapped.py"
    wrapped.write_text(
        "import tempfile\n"
        "root = tempfile.mkdtemp(\n"
        '    prefix="cadrumo-brand-new-family-",\n'
        "    dir=None,\n"
        ")\n",
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([wrapped])

    assert examined == 1
    assert len(offenders) == 1
