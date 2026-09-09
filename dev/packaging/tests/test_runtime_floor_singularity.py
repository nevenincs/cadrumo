"""Gate: every toolchain declaration of the supported-runtime floor derives from one authority.

``dev/ci/python-runtime-matrix.json`` names ``minimum_minor`` -- the oldest
CPython minor this project supports. The floor is then RE-DECLARED, as a bare
literal, in every site below, none of which any other gate reads:

* ``.python-version`` -- the exact toolchain patch. Its exact value is derived
  properly (``dev.packaging.release_cohort`` reads the file and the workflow
  pin gate forbids a workflow naming a rival interpreter), but nothing has ever
  compared its MINOR to the supported floor.
* ``uv.lock`` -- carries its own ``requires-python``. Every consumer digests
  the lock; none parses this field, so its value is sealed but never read.
* the repository-root ``Dockerfile``'s ``ARG PYTHON_BASE_IMAGE`` tag, whose
  minor component is the interpreter every container stage ships.

A fourth site used to stand beside them: the ``Dockerfile``'s
``uv venv --python <minor>`` line, which selected the interpreter the
development image's virtualenv was built on. It is gone by DESIGN, not by
neglect -- the image now runs ``uv sync --locked``, which creates the
virtualenv against the lock's own ``requires-python`` rather than against a
second hand-written minor, and the Dockerfile's "One base, declared once"
banner records the consolidation. Its scan below is deliberately retained but
no longer required: if such a line ever returns -- in this Dockerfile or a
second one -- it is covered on arrival without editing this module, because the
shape it creates is the sharpest failure this gate knows. Bump the base image
alone and uv does not fail on the stale minor, it silently DOWNLOADS a managed
interpreter of that minor into the new image, so the container's tag and its
virtualenv disagree and everything inside it works.

The published manifests' ``requires-python`` floors are joined to the same
authority by ``test_classifier_parity``; this gate covers the toolchain side of
the same field and deliberately does not restate that join.

Why this seam rots silently. Raising the floor is a routine change, and the
author is forced past the classifier gate, the security manifest assertion, the
runtime-matrix literal and all three packaging manifests -- every one of which
names a DIFFERENT declaration than the sites above. Nothing fails when these
lag: the wheels still build, the lock still resolves, the image still builds,
and CI still goes green while every lane exercises a runtime the project has
just declared unsupported.

Sufficiency of the scan is asserted by NAME, never by a count. A count is the
weaker instrument in both directions: it passes a map that lost ``uv.lock`` and
gained an unrelated site, and it has to be edited -- indistinguishably from
ratcheting it down to clear a red -- whenever the population legitimately
changes. Naming each required site fails loudly on the one that vanished, and a
site retired by design is retired here in the same change that retires it in
the tree, with the reason written down.

Specifiers are PARSED, never string-compared against a pinned literal. A
legitimate respelling of the same floor must not turn red, while an upper bound
or a non-bare specifier still cannot pass.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ...ci.python_runtime_matrix import load_runtime_inventory
from .._base_image import linux_base_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final[Path] = REPO_ROOT

#: An exact toolchain patch, whose leading two components are the minor.
_TOOLCHAIN_PIN: Final = re.compile(r"^(?P<minor>3\.\d+)\.\d+$")

#: ``requires-python`` as the lock header spells it, either quoting style.
_LOCK_REQUIRES_PYTHON: Final = re.compile(r"""^requires-python\s*=\s*["'](?P<specifier>[^"']+)["']\s*$""", re.MULTILINE)

#: A bare ``>=3.N`` floor. An upper bound, a compatible-release clause or a
#: comma-joined pair does not match, and therefore cannot pass.
_BARE_FLOOR: Final = re.compile(r"^>=\s*(?P<minor>3\.\d+)$")

#: ``python:3.13-slim-trixie`` and ``python:3.13.11-slim`` both carry minor 3.13.
_BASE_IMAGE_TAG: Final = re.compile(r"^python:(?P<minor>3\.\d+)(?:\.\d+)?(?:[-.]\S*)?$")

#: Every interpreter the Dockerfile selects for a virtualenv, found by scan
#: rather than by line number. No such line exists today -- `uv sync --locked`
#: replaced it -- so this yields nothing and is not required below; it is kept
#: so that one reappearing anywhere in the Dockerfile is covered on arrival.
_UV_VENV_PYTHON: Final = re.compile(r"uv\s+venv\s+--python\s+(?P<minor>3\.\d+)(?:\.\d+)?\b")

#: The declaration sites that must be present for an agreeing map to MEAN
#: agreement, each named by the label its absence is reported under and
#: recognised by a predicate over the scanned site key. Named rather than
#: counted: a site that disappears is reported by name instead of being masked
#: by an unrelated site arriving, and a site retired by design is retired here
#: explicitly rather than by decrementing a number.
_REQUIRED_DECLARATION_SITES: Final[Mapping[str, Callable[[str], bool]]] = {
    ".python-version": lambda site: site == ".python-version",
    "uv.lock": lambda site: site == "uv.lock",
    "Dockerfile ARG PYTHON_BASE_IMAGE": lambda site: site.startswith("Dockerfile ARG PYTHON_BASE_IMAGE"),
}


def _base_image_floor_minor(image: str) -> str:
    """Return the CPython minor a ``python:`` base-image tag ships."""
    match = _BASE_IMAGE_TAG.fullmatch(image.strip())
    assert match is not None, (
        f"the declared base image {image!r} is not a `python:<minor>...` tag, so the "
        "interpreter every container stage ships cannot be read back from it"
    )
    return str(match.group("minor"))


def _file_floor_minors(root: Path) -> dict[str, str]:
    """Return the floor minor each on-disk toolchain declaration under ``root`` states."""
    declared: dict[str, str] = {}

    pin_path = root / ".python-version"
    pin = pin_path.read_text(encoding=UTF_8).strip()
    pin_match = _TOOLCHAIN_PIN.fullmatch(pin)
    assert pin_match is not None, f"{pin_path}: expected one exact `3.N.P` patch, got {pin!r}"
    declared[".python-version"] = pin_match.group("minor")

    lock_path = root / "uv.lock"
    lock_match = _LOCK_REQUIRES_PYTHON.search(lock_path.read_text(encoding=UTF_8))
    assert lock_match is not None, f"{lock_path}: declares no `requires-python` header to compare"
    specifier = lock_match.group("specifier").strip()
    floor_match = _BARE_FLOOR.fullmatch(specifier)
    assert floor_match is not None, (
        f"{lock_path}: `requires-python` must be a bare '>=3.N' floor, got {specifier!r}; "
        "an upper bound here silently narrows the resolution the wheels are built against"
    )
    declared["uv.lock"] = floor_match.group("minor")

    dockerfile_path = root / "Dockerfile"
    dockerfile = dockerfile_path.read_text(encoding=UTF_8)
    lines = dockerfile.splitlines()
    for match in _UV_VENV_PYTHON.finditer(dockerfile):
        line_number = dockerfile.count("\n", 0, match.start()) + 1
        declared[f"Dockerfile:{line_number} {lines[line_number - 1].strip()}"] = match.group("minor")

    return declared


def _toolchain_floor_minors(root: Path, *, base_image: str) -> dict[str, str]:
    """Return every toolchain declaration of the runtime floor, keyed by its site.

    ``base_image`` is injected rather than re-parsed here: the ``ARG
    PYTHON_BASE_IMAGE`` line is already the single declaration point read back
    by :func:`dev.packaging._base_image.linux_base_image`, and a second parse of
    it in this module would be the very duplication the gate exists to refuse.
    """
    declared = _file_floor_minors(root)
    declared[f"Dockerfile ARG PYTHON_BASE_IMAGE={base_image}"] = _base_image_floor_minor(base_image)
    return declared


def _unreached_required_sites(declared: Mapping[str, str]) -> list[str]:
    """Return the required declaration sites the scan did not reach, by name."""
    return sorted(
        name for name, matches in _REQUIRED_DECLARATION_SITES.items() if not any(matches(site) for site in declared)
    )


def _assert_floor_agreement(declared: Mapping[str, str], *, minimum_minor: str) -> None:
    """Every toolchain declaration must state exactly the supported floor minor."""
    unreached = _unreached_required_sites(declared)
    assert not unreached, (
        f"the scan reached {sorted(declared)} but found no declaration at {unreached}; "
        "an agreeing map that is missing a known site is not evidence of agreement, it is "
        "evidence the scan stopped looking. If a site was retired by design, retire it from "
        "_REQUIRED_DECLARATION_SITES in the same change, with the reason"
    )
    lagging = {site: minor for site, minor in declared.items() if minor != minimum_minor}
    assert not lagging, (
        f"these toolchain declarations do not state the supported floor {minimum_minor!r}:\n  "
        + "\n  ".join(f"{site} -> {minor}" for site, minor in sorted(lagging.items()))
        + "\nThe floor is declared once, in dev/ci/python-runtime-matrix.json (`minimum_minor`). "
        "A declaration that lags it still builds, still resolves and still passes every lane, "
        "while exercising a runtime the project no longer supports."
    )


def test_every_toolchain_declaration_states_the_supported_floor() -> None:
    """Every toolchain floor declaration in the live tree equals the inventory minimum."""
    inventory = load_runtime_inventory()

    declared = _toolchain_floor_minors(_REPO_ROOT, base_image=linux_base_image())

    _assert_floor_agreement(declared, minimum_minor=inventory.minimum_minor)


def test_the_live_scan_reaches_every_known_declaration_site() -> None:
    """The scan reaches each named site, so a silently narrowed scan cannot read as agreement.

    Derived from ``_REQUIRED_DECLARATION_SITES`` rather than restating the site
    list, so the population is declared exactly once in this module too.
    """
    declared = _toolchain_floor_minors(_REPO_ROOT, base_image=linux_base_image())

    assert _unreached_required_sites(declared) == []


def _agreeing(minor: str) -> dict[str, str]:
    """Return a full, unanimous declaration map at ``minor``."""
    return {
        ".python-version": minor,
        "uv.lock": minor,
        f"Dockerfile ARG PYTHON_BASE_IMAGE=python:{minor}-slim-trixie": minor,
    }


def test_unanimous_agreement_at_a_raised_floor_passes() -> None:
    """The gate is not one-directional: a fully carried floor bump is accepted.

    Without this the gate could be satisfied by pinning today's value, and a
    legitimate raise would have to fight it.
    """
    _assert_floor_agreement(_agreeing("3.14"), minimum_minor="3.14")


@pytest.mark.parametrize("lagging_site", sorted(_agreeing("3.14")))
def test_a_single_lagging_declaration_is_detected(lagging_site: str) -> None:
    """Each declaration is load-bearing on its own, not covered by its neighbours."""
    declared = _agreeing("3.14")
    declared[lagging_site] = "3.13"

    with pytest.raises(AssertionError, match=r"do not state the supported floor"):
        _assert_floor_agreement(declared, minimum_minor="3.14")


@pytest.mark.parametrize("dropped_site", sorted(_agreeing("3.13")))
def test_a_narrowed_scan_cannot_read_as_agreement(dropped_site: str) -> None:
    """Dropping any required declaration is refused, and the refusal names it.

    Parametrised over the whole population: each site is separately load-bearing
    for sufficiency, exactly as each is separately load-bearing for agreement.
    """
    declared = _agreeing("3.13")
    del declared[dropped_site]

    with pytest.raises(AssertionError, match=r"evidence the scan stopped looking"):
        _assert_floor_agreement(declared, minimum_minor="3.13")


def test_an_unrelated_site_cannot_substitute_for_a_missing_one() -> None:
    """A replacement site does not restore sufficiency -- the named one is still gone.

    This is what naming buys over counting. A count reads this map as the full
    population and passes it; the missing site is then silently outside the gate
    while the map still looks unanimous.
    """
    declared = _agreeing("3.13")
    del declared["uv.lock"]
    declared["Dockerfile:155 uv venv --python 3.13"] = "3.13"

    with pytest.raises(AssertionError, match=r"no declaration at \['uv\.lock'\]"):
        _assert_floor_agreement(declared, minimum_minor="3.13")


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("python:3.13-slim-trixie", "3.13"),
        ("python:3.14-slim-trixie", "3.14"),
        ("python:3.13.11-slim", "3.13"),
    ],
)
def test_a_base_image_tag_yields_its_minor(image: str, expected: str) -> None:
    """The minor is parsed out of the tag, so a distribution respelling is not drift."""
    assert _base_image_floor_minor(image) == expected


def test_a_base_image_that_is_not_a_python_tag_is_refused() -> None:
    """A base whose interpreter cannot be read back fails rather than yielding nothing."""
    with pytest.raises(AssertionError, match=r"cannot be read back"):
        _base_image_floor_minor("ghcr.io/actions/actions-runner:latest")


def _write_tree(root: Path, *, pin: str, lock: str, venv: str) -> None:
    """Materialise an isolated tree carrying the three file-borne declarations."""
    (root / ".python-version").write_text(f"{pin}\n", encoding=UTF_8)
    (root / "uv.lock").write_text(f'version = 1\nrevision = 3\nrequires-python = "{lock}"\n', encoding=UTF_8)
    (root / "Dockerfile").write_text(
        f"FROM base AS dev\nRUN uv venv --python {venv} .venv \\\n    && uv pip install -e .\n",
        encoding=UTF_8,
    )


def test_the_collector_reads_each_file_borne_declaration(tmp_path: Path) -> None:
    """Teeth on the parsers themselves, in an isolated tree rather than the worktree."""
    _write_tree(tmp_path, pin="3.14.2", lock=">=3.14", venv="3.14")

    declared = _file_floor_minors(tmp_path)

    assert declared[".python-version"] == "3.14"
    assert declared["uv.lock"] == "3.14"
    assert [minor for site, minor in declared.items() if "uv venv --python" in site] == ["3.14"]


def test_a_vanished_file_borne_declaration_is_refused(tmp_path: Path) -> None:
    """A site that disappears from the tree fails closed instead of shortening the map.

    The on-disk counterpart of the named-site check, proved in an isolated tree
    rather than by removing a file from the worktree: the collector refuses a
    tree it cannot read the declaration out of, so a deleted `uv.lock` can never
    reach the agreement check as a smaller unanimous population.
    """
    _write_tree(tmp_path, pin="3.14.2", lock=">=3.14", venv="3.14")
    (tmp_path / "uv.lock").unlink()

    with pytest.raises(OSError):
        _file_floor_minors(tmp_path)


def test_a_drifted_venv_selection_is_read_from_the_isolated_tree(tmp_path: Path) -> None:
    """The Dockerfile's virtualenv interpreter is read independently of the base tag.

    No such line exists in the live Dockerfile today, which is why the scan for
    it is retained but not required. This proves the retained scan still has
    teeth for the day one returns: the image moves and the venv line does not,
    and uv answers the stale minor by downloading it rather than by failing, so
    the container builds and every command inside it works.
    """
    _write_tree(tmp_path, pin="3.14.2", lock=">=3.14", venv="3.13")

    declared = _toolchain_floor_minors(tmp_path, base_image="python:3.14-slim-trixie")

    with pytest.raises(AssertionError, match=r"uv venv --python"):
        _assert_floor_agreement(declared, minimum_minor="3.14")


def test_an_upper_bounded_lock_specifier_is_refused(tmp_path: Path) -> None:
    """A bounded ``requires-python`` cannot pass by happening to start at the floor."""
    _write_tree(tmp_path, pin="3.13.11", lock=">=3.13,<3.14", venv="3.13")

    with pytest.raises(AssertionError, match=r"must be a bare '>=3.N' floor"):
        _file_floor_minors(tmp_path)


def test_a_respelled_lock_floor_is_accepted(tmp_path: Path) -> None:
    """Whitespace is not drift: the specifier is parsed, never string-compared."""
    _write_tree(tmp_path, pin="3.13.11", lock=">= 3.13", venv="3.13")

    assert _file_floor_minors(tmp_path)["uv.lock"] == "3.13"


def test_an_inexact_toolchain_pin_is_refused(tmp_path: Path) -> None:
    """``.python-version`` must select one exact patch, so its minor is unambiguous."""
    _write_tree(tmp_path, pin="3.13", lock=">=3.13", venv="3.13")

    with pytest.raises(AssertionError, match=r"expected one exact"):
        _file_floor_minors(tmp_path)
