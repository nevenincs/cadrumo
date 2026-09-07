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
written, or this fails naming it. Discovered from the PARSED TREE, because the
text pattern that did this before could only see a quoted prefix beginning
``cadrumo-``: a family named outside that stem was neither judged nor counted,
and a gate reports a population it never assembled exactly as it reports a
clean one.

Two ways to satisfy the rule, because both are legitimate:

* the prefix is swept centrally, which is what catches a process that is
  *killed* and so runs no finalizer at all; or
* the call site registers its own finalizer, which is what handles the clean
  path promptly rather than waiting out a staleness ceiling.

A family that does neither is the defect.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from cadrumo.tests.collection_storage_root import SETTINGS_STEM, SWEPT_SCRATCH_STEMS

from ..._paths import REPO_ROOT
from ...quality.unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Prefixes the central sweep reclaims. The per-session stem carries the owning
#: PID and is minted by the sweep's own module, so it is not a discovered
#: subject; every other swept family is.
_SWEPT: Final = (*SWEPT_SCRATCH_STEMS, SETTINGS_STEM, "cadrumo-pytest-")


def _mkdtemp_prefixes(source: str) -> tuple[list[str], int, int]:
    """Return every ``mkdtemp`` prefix in ``source``, read from its parsed tree.

    The pattern this replaces matched text, and both of its narrowings removed
    subjects rather than adding findings. It required the prefix to be a QUOTED
    LITERAL, so a prefix reaching the call through a parameter was invisible;
    and it required that literal to begin ``cadrumo-``, so a family named
    outside the stem was invisible too. ``serving-benchmark-`` was one: minted
    once per benchmark run, reclaimed by nothing, and absent from this gate's
    population, which therefore reported green over five call sites while the
    tree held seven.

    Returns:
        The literal prefixes; the number of calls whose prefix is present but
        not readable as a literal; and the number naming no prefix at all. The
        last are not this gate's subject -- nothing keyed on a stem can reclaim
        a directory that has none -- but they are counted rather than dropped,
        so the omission is stated instead of shrinking the population in
        silence.

    Raises:
        SyntaxError: If ``source`` does not parse. The caller reports that as an
            unread input rather than failing, because a sibling process editing
            this tree can be caught mid-write.
    """
    prefixes: list[str] = []
    unreadable = 0
    anonymous = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", None)
        if name != "mkdtemp":
            continue
        # ``mkdtemp(suffix, prefix, dir)``: the second positional is the prefix,
        # and reading only the keyword would rebuild the blind spot this
        # function exists to remove, one argument over.
        keyword = next((word.value for word in node.keywords if word.arg == "prefix"), None)
        given = keyword if keyword is not None else (node.args[1] if len(node.args) > 1 else None)
        if given is None:
            anonymous += 1
        elif isinstance(given, ast.Constant) and isinstance(given.value, str):
            prefixes.append(given.value)
        else:
            unreadable += 1
    return prefixes, unreadable, anonymous


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
        path for root in _SOURCE_ROOTS for path in (REPO_ROOT / root).rglob("*.py") if "__pycache__" not in path.parts
    )


def _reportable(path: Path) -> str:
    """Name ``path`` for an operator, whether or not it sits in the repository.

    The scan is driven with an isolated tree by the cases below, so a path
    outside the repository root is a normal input rather than an error. Making
    the repository-relative form conditional keeps the message readable for the
    real subjects without the formatting raising on the synthetic ones -- which
    it did, turning both teeth cases into errors instead of the assertions they
    were written to make.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _unreclaimed(paths: list[Path]) -> tuple[list[str], int]:
    """Return every unreclaimed scratch family, and how many were examined.

    The count is what stops this passing vacuously. A discovery gate that finds
    no subject at all reports exactly the same green as one where every subject
    complies, and the first of those is asserting nothing.
    """
    offenders: list[str] = []
    unread: list[str] = []
    unnamed: list[str] = []
    examined = 0
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as refusal:
            # A source that will not read declares no scratch family, which is
            # exactly what a compliant one looks like from here. The counter
            # below guards vacuity but not partial loss: five families are
            # examined across 6,999 sources, so one unreadable file carrying
            # a family removes a fifth of the subject with nothing said.
            unread.append(f"{path} ({type(refusal).__name__})")
            continue
        try:
            prefixes, unreadable, anonymous = _mkdtemp_prefixes(source)
        except SyntaxError as refusal:
            unread.append(f"{path} (SyntaxError: {refusal.msg})")
            continue
        if anonymous:
            unnamed.append(f"{_reportable(path)} ({anonymous})")
        if not prefixes and not unreadable:
            continue
        finalized = bool(_FINALIZED.search(source))
        for prefix in sorted(set(prefixes)):
            examined += 1
            if prefix.startswith(_SWEPT) or finalized:
                continue
            offenders.append(f"{_reportable(path)}: {prefix!r}")
        examined += unreadable
        if unreadable and not finalized:
            # An unreadable prefix cannot be checked against the swept tuple, so
            # a local finalizer is the only remaining way to satisfy the rule.
            # Passing it over instead would be the original defect in miniature.
            offenders.append(
                f"{_reportable(path)}: {unreadable} mkdtemp prefix(es) this gate cannot read as a "
                "literal, and the module registers no finalizer",
            )
    report_unread(
        "scratch reclamation sweep",
        "these sources were not read, so a scratch family declared in one was neither examined nor counted below",
        unread,
    )
    report_unread(
        "scratch family census",
        "these mkdtemp calls name no prefix, so no stem-keyed sweep can reach them and this gate does not judge them",
        unnamed,
    )
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


def test_a_family_outside_the_cadrumo_stem_is_reported(tmp_path: Path) -> None:
    """The exact shape the replaced text pattern could not see.

    ``serving-benchmark-`` was written, minted once per run, reclaimed by
    nothing, and reported by nothing: the pattern required the literal to begin
    ``cadrumo-``, so the family never entered the population at all. A gate that
    judges a smaller set reads identically to one judging a clean set, which is
    why this case is asserted rather than assumed.
    """
    stray = tmp_path / "stray.py"
    stray.write_text(
        'import tempfile\nroot = tempfile.mkdtemp(prefix="serving-benchmark-")\n',
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([stray])

    assert examined == 1
    assert len(offenders) == 1
    assert "serving-benchmark-" in offenders[0]


def test_a_prefix_that_is_not_a_literal_demands_a_finalizer(tmp_path: Path) -> None:
    """A prefix arriving through a parameter cannot be checked against the tuple.

    The replaced pattern passed such a call over in silence. Refusing it unless
    the module disposes of what it mints is the only honest reading: the gate
    cannot say the family is swept, so it must not imply that it is.
    """
    indirect = tmp_path / "indirect.py"
    indirect.write_text(
        "import tempfile\n\n\ndef mint(prefix: str) -> str:\n    return tempfile.mkdtemp(prefix=prefix)\n",
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([indirect])

    assert examined == 1
    assert len(offenders) == 1
    assert "cannot read as a literal" in offenders[0]


def test_an_unreadable_prefix_with_a_finalizer_is_accepted(tmp_path: Path) -> None:
    """The refusal above must be the rule's second half, not a blanket ban."""
    indirect = tmp_path / "tidy_indirect.py"
    indirect.write_text(
        "import atexit\nimport shutil\nimport tempfile\n\n\n"
        "def mint(prefix: str) -> str:\n"
        "    root = tempfile.mkdtemp(prefix=prefix)\n"
        "    atexit.register(shutil.rmtree, root, ignore_errors=True)\n"
        "    return root\n",
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([indirect])

    assert examined == 1
    assert offenders == []


def test_a_positional_prefix_is_read(tmp_path: Path) -> None:
    """``mkdtemp(suffix, prefix)`` names a family without a keyword.

    Reading only the keyword would rebuild the same blind spot one argument
    over, so the positional spelling is asserted rather than trusted.
    """
    positional = tmp_path / "positional.py"
    positional.write_text(
        'import tempfile\nroot = tempfile.mkdtemp("", "cadrumo-brand-new-family-")\n',
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([positional])

    assert examined == 1
    assert len(offenders) == 1
    assert "cadrumo-brand-new-family-" in offenders[0]


def test_a_prefixless_call_is_counted_but_not_judged(tmp_path: Path) -> None:
    """A directory with no stem cannot be swept by one, and is not this rule.

    It is still announced rather than dropped, because a population that shrinks
    without saying so is the failure this whole module is written against.
    """
    unnamed = tmp_path / "unnamed.py"
    unnamed.write_text("import tempfile\nroot = tempfile.mkdtemp()\n", encoding="utf-8")

    offenders, examined = _unreclaimed([unnamed])

    assert offenders == []
    assert examined == 0


def test_an_unparsable_source_is_announced_not_swallowed(tmp_path: Path) -> None:
    """A sibling process caught mid-write must not read as a compliant file."""
    broken = tmp_path / "broken.py"
    broken.write_text("def mint(:\n", encoding="utf-8")

    offenders, examined = _unreclaimed([broken])

    assert offenders == []
    assert examined == 0


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
        'import tempfile\nroot = tempfile.mkdtemp(\n    prefix="cadrumo-brand-new-family-",\n    dir=None,\n)\n',
        encoding="utf-8",
    )

    offenders, examined = _unreclaimed([wrapped])

    assert examined == 1
    assert len(offenders) == 1
