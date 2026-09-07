"""Every ``var/`` scratch family is minted through the registry that sweeps it.

The reclaim's whole safety argument is that it removes members of the families
this package mints and nothing else. That argument has two halves, and only one
of them is enforced by the reclaim module itself. The module decides what a
registered family looks like; whether the mint sites AGREE is a property of the
call sites, and until it is checked the module's promise -- that a rename cannot
leave the sweep looking for a name nothing writes -- is a convention.

Both directions cost something real when they drift. A family named in the
registry that no site writes reclaims nothing and reads as coverage. A name
written at a site and registered nowhere leaks without bound: the cohort build's
extracted source tree is thirty-nine thousand files, its Git archive several
hundred megabytes, and both are removed only in a ``finally`` block that a
killed process never reaches.

So the subjects are DISCOVERED from the source rather than enumerated. A new
hidden name minted under ``var/`` is caught the moment it is written, or this
fails naming it.

What the discovery cannot see is stated rather than implied: it reads the
production modules of this package, where the ``var/`` mints live, and judges a
name by its spelling. A mint site in another tree, or one assembled from
fragments no literal contains, is outside it -- the same boundary the temporary
directory prefix gate draws around ``mkdtemp``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ..build_scratch_reclaim import VAR_SCRATCH_FAMILIES, ScratchFamily, matching_family

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The package whose production modules mint under ``var/``.
_PACKAGE_ROOT: Final[Path] = REPO_ROOT / "dev" / "packaging"

#: The reclaim module names every family on purpose, and this gate quotes them.
_DISCOVERY_EXCLUSIONS: Final[frozenset[str]] = frozenset(
    {"build_scratch_reclaim.py", "test_var_scratch_mint_sites_are_registered.py"},
)

#: A hidden name joined onto a path: ``base / ".name"`` or ``base / f".{x}-work"``.
#: Spans lines, because the join is routinely wrapped and a single-line pattern
#: would under-report exactly the sites most likely to be missed.
_HIDDEN_JOIN: Final[re.Pattern[str]] = re.compile(r"""/\s*f?["'](\.[^"'\n]*)["']""", re.DOTALL)

#: Interpolation inside an f-string literal, replaced by a stand-in body so the
#: rendered name can be judged by the same function the sweep judges names with.
_INTERPOLATION: Final[re.Pattern[str]] = re.compile(r"\{[^{}]*\}")

#: A stand-in for whatever a mint site interpolates. Any non-empty run of body
#: characters serves: the family judgement reads the two anchors and the presence
#: of something between them, never the body's content.
_BODY_STANDIN: Final[str] = "BODY"

#: Hidden names this package RESOLVES but does not mint under ``var/``: version
#: control and toolchain files it reads, and installation scratch created under a
#: temporary directory the operating system already reclaims. Adding a name here
#: is a deliberate act, and the wrong place to put a new build-scratch family.
_NOT_VAR_SCRATCH: Final[frozenset[str]] = frozenset(
    {
        ".cadrumo",
        ".cadrumo-mcp-profile-secret.json",
        ".git",
        ".github",
        ".gitignore",
        ".python-version",
        ".venv",
    },
)


def _production_modules() -> list[Path]:
    """Return the package's production modules, which are where the mints live.

    Tests are excluded because their scratch lands under a ``tmp_path`` the
    operating system reclaims, not under the repository's ``var/``.
    """
    return sorted(
        path
        for path in _PACKAGE_ROOT.glob("*.py")
        if path.name not in _DISCOVERY_EXCLUSIONS and not path.name.startswith("test_")
    )


def _reportable(path: Path) -> str:
    """Name ``path`` for an operator, whether or not it sits in the repository.

    The scan is driven with an isolated file by the detector cases below, so a
    path outside the repository root is a normal input rather than an error.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _rendered(literal: str) -> str:
    """Return ``literal`` with every interpolation replaced by a stand-in body."""
    return _INTERPOLATION.sub(_BODY_STANDIN, literal)


def _hand_spelled_mints(paths: list[Path]) -> tuple[list[str], int]:
    """Return every hidden name spelled at a call site, and how many were examined.

    The count is what stops this passing vacuously. A discovery gate that finds
    no subject at all reports exactly the same green as one where every subject
    complies, and the first of those is asserting nothing.
    """
    offenders: list[str] = []
    examined = 0
    for path in paths:
        try:
            source = path.read_text(encoding=UTF_8)
        except (OSError, UnicodeDecodeError):
            continue
        for literal in sorted(set(_HIDDEN_JOIN.findall(source))):
            examined += 1
            if literal in _NOT_VAR_SCRATCH:
                continue
            registered = matching_family(_rendered(literal)) is not None
            offenders.append(f"{_reportable(path)}: {literal!r} ({'registered' if registered else 'unregistered'})")
    return offenders, examined


def _unminted_families(named: dict[str, ScratchFamily], sources: list[Path]) -> list[str]:
    """Return every family constant no source in ``sources`` names."""
    text = "\n".join(
        path.read_text(encoding=UTF_8, errors="ignore") for path in sources if path.name not in _DISCOVERY_EXCLUSIONS
    )
    return sorted(constant for constant in named if constant not in text)


def _named_families() -> dict[str, ScratchFamily]:
    """Return the reclaim module's family constants, keyed by the name they carry."""
    from .. import build_scratch_reclaim

    return {name: value for name, value in vars(build_scratch_reclaim).items() if isinstance(value, ScratchFamily)}


def test_no_var_scratch_name_is_spelled_at_its_call_site() -> None:
    """A hidden name minted under ``var/`` comes from the registry or from nowhere.

    The failure this prevents has two shapes and one consequence. A site that
    re-spells a REGISTERED family's anchors survives a rename of the family and
    starts writing a name the sweep no longer looks for. A site that invents an
    UNREGISTERED one is swept by nothing at all, which is how a killed build
    leaves thirty-nine thousand files behind permanently.
    """
    offenders, examined = _hand_spelled_mints(_production_modules())

    assert examined, "no hidden path name was discovered; this gate is asserting nothing"
    assert offenders == [], (
        "these hidden names are spelled at their call site instead of being built with "
        "var_scratch_name from a registered family, so nothing guarantees the sweep looks "
        "for what they write:\n  " + "\n  ".join(offenders)
    )


def test_the_registry_and_the_family_constants_agree() -> None:
    """A family constant the registry omits is a family the sweep never considers."""
    assert set(_named_families().values()) == set(VAR_SCRATCH_FAMILIES)


def test_every_registered_family_is_named_by_a_mint_site() -> None:
    """A family the registry carries and no site writes is coverage that reclaims nothing."""
    named = _named_families()
    unminted = _unminted_families(named, sorted(REPO_ROOT.joinpath("dev").rglob("*.py")))

    assert named, "no family constant was discovered; this gate is asserting nothing"
    assert unminted == [], (
        "these registered families are named by no source outside the reclaim module, so "
        "the sweep is looking for names nothing writes:\n  " + "\n  ".join(unminted)
    )


def test_a_new_unregistered_mint_is_reported(tmp_path: Path) -> None:
    """Teeth, against an isolated file rather than the tree being protected.

    Written the way the defect appeared: a per-run hidden name joined onto a
    build directory, matching no family, swept by nothing.
    """
    leak = tmp_path / "leaks.py"
    leak.write_text('work = output.parent / f".{output.name}-scratch"\n', encoding=UTF_8)

    offenders, examined = _hand_spelled_mints([leak])

    assert examined == 1
    assert len(offenders) == 1
    assert "unregistered" in offenders[0]


def test_a_re_spelled_registered_family_is_reported(tmp_path: Path) -> None:
    """The second shape: a site spelling anchors the registry already owns.

    Harmless until the family is renamed, at which point the sweep looks for a
    name nothing writes any more and the site writes a name nothing sweeps.
    """
    respelled = tmp_path / "respelled.py"
    respelled.write_text('staging = var / f".{output.name}-{token}.staging"\n', encoding=UTF_8)

    offenders, examined = _hand_spelled_mints([respelled])

    assert examined == 1
    assert len(offenders) == 1
    assert offenders[0].endswith("(registered)")


def test_a_resolved_toolchain_dotfile_is_accepted(tmp_path: Path) -> None:
    """The rule is about minting, not about every dot in a path.

    Without this the gate would push a module that merely READS
    ``.python-version`` into inventing a scratch family for it.
    """
    reader = tmp_path / "reads.py"
    reader.write_text('pin = (root / ".python-version").read_text()\n', encoding=UTF_8)

    offenders, examined = _hand_spelled_mints([reader])

    assert examined == 1
    assert offenders == []


def test_the_pattern_reads_a_wrapped_join(tmp_path: Path) -> None:
    """A join split across lines is the shape most likely to be missed."""
    wrapped = tmp_path / "wrapped.py"
    wrapped.write_text('work = (\n    output.parent\n    / f".{output.name}-scratch"\n)\n', encoding=UTF_8)

    offenders, examined = _hand_spelled_mints([wrapped])

    assert examined == 1
    assert len(offenders) == 1


def test_an_unminted_registered_family_is_reported(tmp_path: Path) -> None:
    """Teeth for the reverse direction, against an isolated source set."""
    source = tmp_path / "writes.py"
    source.write_text("name = var_scratch_name(RELEASE_STAGING_FAMILY, body)\n", encoding=UTF_8)
    named = {
        "RELEASE_STAGING_FAMILY": ScratchFamily(prefix=".", suffix=".staging"),
        "ORPHAN_FAMILY": ScratchFamily(prefix=".", suffix="-nothing-writes-this"),
    }

    assert _unminted_families(named, [source]) == ["ORPHAN_FAMILY"]
