"""The absent-llm lane's premise must be constructible, not merely asserted.

The lane in :mod:`dev.packaging.smoke_absent_llm` installs the cohort without
the ``llm`` extra and requires every inference-adjacent surface to refuse with
``pip install cadrumo[llm]``. That lane costs a wheel build and a venv install,
so the cheap structural preconditions it depends on are checked here, where they
fail in seconds instead of minutes.

The precondition that matters is **probe exclusivity**. A guard probes ONE
import name; if the distribution supplying that name is an unconditional core
requirement, the probe succeeds in every core install, ``require_optional_extra``
is a permanent no-op, and the guard is dormant by construction. Every
source-level test of such a guard still passes -- against a condition no install
can reach -- so nothing in the source tree reports the problem. That is the
failure this module exists to make visible.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import packages_distributions

import pytest

from ..._paths import REPO_ROOT
from .._distribution_names import normalise_distribution_name
from .._smoke_common import optional_extra_registry
from ..smoke_absent_llm import _EXPECTED_EXTRA, _INFERENCE_SURFACES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def _core_requirement_names() -> set[str]:
    """Return the normalised distributions every install gets unconditionally.

    Read from ``[project.dependencies]``, which is exactly what becomes the
    wheel's unmarked ``Requires-Dist`` set; the wheel-versus-pyproject agreement
    is already gated by ``assert_wheel_metadata_matches_pyproject``, so reading
    the cheaper surface here does not weaken the check.
    """
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    names: set[str] = set()
    for requirement in pyproject["project"]["dependencies"]:
        name = requirement.split(";")[0].strip()
        for separator in ("[", "=", ">", "<", "!", "~", " "):
            name = name.split(separator)[0]
        if name:
            names.add(normalise_distribution_name(name))
    return names


def _distributions_providing(import_name: str) -> set[str]:
    """Return the normalised distributions providing ``import_name`` here."""
    found = {normalise_distribution_name(name) for name in packages_distributions().get(import_name, [])}
    return found or {normalise_distribution_name(import_name)}


def test_every_optional_extra_probes_a_package_core_does_not_supply() -> None:
    """No extra may probe an import name the core closure already satisfies.

    Applied to every registered extra rather than only to ``llm``, because the
    defect is a class: the moment a package declared in an extra is ALSO needed
    by core, that extra's guard silently stops guarding, and nothing else in the
    tree notices.
    """
    core_names = _core_requirement_names()
    registry_extras, _symbols = optional_extra_registry(_REPO_ROOT)

    dormant = {
        extra: sorted(supplied)
        for extra, import_name in registry_extras.items()
        if (supplied := _distributions_providing(import_name) & core_names)
    }

    assert dormant == {}, (
        f"these extras probe an import name supplied by an unconditional core requirement: {dormant}. "
        "The probe therefore succeeds in every core install, require_optional_extra is a permanent no-op, "
        "and every surface behind that guard runs unguarded. Repoint the registry entry at an import name "
        "supplied only by the extra -- do not relax this gate, and do not delete the core requirement, "
        "which is load-bearing where it is declared."
    )


def test_the_llm_extra_declares_a_requirement_core_does_not() -> None:
    """The extra must add something, or there is nothing for a probe to detect.

    Distinct from the assertion above and checked separately: an extra can carry
    an exclusive requirement while its PROBE still points at a shared one, and
    it can probe correctly while declaring nothing exclusive. Both are needed,
    and a single combined check would not say which half broke.
    """
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    extra_requirements = pyproject["project"]["optional-dependencies"]["llm"]
    core_names = _core_requirement_names()

    exclusive = {
        normalise_distribution_name(requirement.split(">")[0].split("<")[0].split("=")[0].strip())
        for requirement in extra_requirements
    } - core_names

    assert exclusive, (
        f"every requirement of the llm extra ({extra_requirements!r}) is also an unconditional core "
        "requirement, so `pip install cadrumo[llm]` installs nothing `pip install cadrumo` did not, and "
        "the extra cannot be detected by any probe"
    )


def test_the_surface_inventory_names_real_exported_entry_points() -> None:
    """Non-vacuity: an inventory of names that do not exist would drive nothing.

    The lane reaches its surfaces by name in a child interpreter, so a rename in
    the inference package would surface there as an ImportError inside a
    minutes-long lane rather than here. It would also be indistinguishable from
    the lane simply having nothing to drive.
    """
    from cadrumo import llm

    assert _INFERENCE_SURFACES, "the lane drives no surfaces"
    missing = [name for name, _call in _INFERENCE_SURFACES if name not in llm.__all__]
    assert missing == [], (
        f"the absent-llm lane names surfaces that the inference package does not export: {missing}. "
        "The lane would fail on the import line having proved nothing about refusals."
    )


def test_the_expected_extra_matches_the_registered_extra() -> None:
    """The lane's expected refusal identity is the registry's, not a copy that can drift."""
    from cadrumo.core import LLM_EXTRA

    assert LLM_EXTRA.extra == _EXPECTED_EXTRA
