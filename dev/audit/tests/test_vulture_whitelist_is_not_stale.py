"""Prove every vulture whitelist entry still names a live parameter.

It is a SUPPRESSION surface: every name in it is a name vulture stops
reporting, so a stale entry does not merely sit there - it goes on hiding a dead
parameter after the reason for the exemption is gone.

The file states the rule itself: "When any of these parameters is removed at its
source, delete its line here so the audit re-detects a stale whitelist entry."
Nothing enforced it. The rule was a sentence asking a future contributor to
remember an unrelated file while deleting a parameter, which is precisely the
kind of discipline that decays without notice - and decays silently, because a
suppression's failure mode is a report that stays clean.

Each entry is checked against the signature it cites, resolved through a real
import. A parameter removed at its source makes this fail, which is what the
file's own sentence asks for.

The citation map below duplicates the prose citations deliberately. If IT rots,
the symbol stops resolving and this fails loudly; the state being replaced was a
whitelist that rotted and said nothing at all.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from fnmatch import fnmatchcase
from types import ModuleType

import pytest
import vulture
from vulture.config import make_config

from cadrumo.adapters.outbound.google import api as google_api
from cadrumo.adapters.outbound.workbook import calc_sheets_xlsx
from dev._paths import REPO_ROOT
from dev.first_party_source import SOURCE_PACKAGES

from .. import vulture_whitelist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CITATIONS: dict[str, tuple[ModuleType, str | None, str]] = {
    "_custom_document_properties_append": (calc_sheets_xlsx, "_CustomDocumentProperties", "append"),
    "_execute": (google_api, "ExecutableRequest", "execute"),
}


def _declared_parameters(source: str) -> dict[str, tuple[str, ...]]:
    """Return each mirror function in whitelist source mapped to its parameter names."""
    tree = ast.parse(source)
    declared: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            declared[node.name] = tuple(argument.arg for argument in node.args.args)
    return declared


def _cited_parameters(module: ModuleType, class_name: str | None, attribute: str) -> frozenset[str]:
    owner = getattr(module, class_name) if class_name is not None else module
    return frozenset(inspect.signature(getattr(owner, attribute)).parameters)


@pytest.fixture(scope="module")
def declared() -> dict[str, tuple[str, ...]]:
    source = pathlib.Path(vulture_whitelist.__file__).read_text(encoding="utf-8")
    return _declared_parameters(source)


def test_the_whitelist_actually_declares_something(declared: dict[str, tuple[str, ...]]) -> None:
    """A parse that found nothing would make every case below vacuously true."""
    assert declared
    assert all(parameters for parameters in declared.values())


def test_every_mirror_function_carries_a_citation(declared: dict[str, tuple[str, ...]]) -> None:
    """A new entry with no cited source cannot be checked, so it must not be added silently.

    This is the half that keeps the map honest in the other direction: without
    it, an exemption could be added here and this file would go on passing
    while checking nothing about it.
    """
    # The equality catches a ONE-SIDED collapse - a citation added without a
    # whitelist entry, or the reverse. It cannot catch both emptying
    # together, which would also reduce the parametrize below to zero cases
    # and retire that gate in silence: a whitelist file that exists declares
    # at least one mirror, or it should be deleted rather than kept empty.
    assert declared, "the whitelist declares no mirror, so the per-mirror gate below runs over nothing"
    assert set(declared) == set(_CITATIONS)


@pytest.mark.parametrize("mirror", sorted(_CITATIONS))
def test_each_whitelisted_parameter_still_exists_at_its_source(
    mirror: str,
    declared: dict[str, tuple[str, ...]],
) -> None:
    """The staleness check the file's own docstring asks for.

    A suppression outliving its reason keeps a dead parameter invisible, and
    nothing else in the tree would report it: vulture is silent by
    construction once the name appears here.
    """
    module_name, class_name, attribute = _CITATIONS[mirror]
    live = _cited_parameters(module_name, class_name, attribute)

    stale = [parameter for parameter in declared[mirror] if parameter not in live]

    assert not stale, f"{mirror} whitelists {stale}, absent from {module_name}.{attribute}"


def test_a_parameter_removed_at_its_source_is_detected() -> None:
    """Detector teeth: the comparison must fail on a name the signature lacks.

    Proven against a real signature and a constructed whitelist entry, so the
    check is shown to work without editing the live whitelist or the module it
    cites.
    """
    module_name, class_name, attribute = _CITATIONS["_execute"]
    live = _cited_parameters(module_name, class_name, attribute)
    invented = _declared_parameters("def _mirror(retired_parameter: object) -> None:\n    pass\n")

    stale = [parameter for parameter in invented["_mirror"] if parameter not in live]

    assert stale == ["retired_parameter"]


def test_the_whitelist_holds_only_parameter_mirrors(declared: dict[str, tuple[str, ...]]) -> None:
    """Every entry is a parameter exemption, not a suppressed function or class.

    A whitelisted NAME suppresses that name everywhere vulture looks, so an
    entry that named a class or a helper would exempt far more than one
    signature - which is exactly the broad exemption the file promises it is
    not.
    """
    source = pathlib.Path(vulture_whitelist.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    mirrors = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

    assert mirrors, "the whitelist defines no mirror, so the absence claim below holds vacuously"
    assert declared, "the parsed whitelist declared no parameters, so the public-name claim below ranges over nothing"
    assert not [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert all(name.startswith("_") for name in declared), "a mirror is exported under a public name"


def _names_vulture_reports_without_the_whitelist() -> frozenset[str]:
    """Scan the production tree exactly as the audit does, minus the whitelist file."""
    configuration = make_config(["--config", str(REPO_ROOT / "pyproject.toml"), *SOURCE_PACKAGES])
    patterns = tuple(
        (pattern if any(char in pattern for char in "*?[") else f"*{pattern}*").lower()
        for pattern in configuration["exclude"]
    )
    modules = [
        str(module)
        for package in SOURCE_PACKAGES
        for module in (REPO_ROOT / package).resolve().glob("**/*.py")
        if not any(fnmatchcase(str(module).lower(), pattern) for pattern in patterns)
    ]
    scanner = vulture.Vulture(
        ignore_names=configuration["ignore_names"], ignore_decorators=configuration["ignore_decorators"]
    )
    scanner.scavenge(modules)
    return frozenset(item.name for item in scanner.get_unused_code(min_confidence=configuration["min_confidence"]))


@pytest.fixture(scope="module")
def reported_without_whitelist() -> frozenset[str]:
    names = _names_vulture_reports_without_the_whitelist()
    assert names, "the production scan reported nothing, so the per-entry check below would prove nothing"
    return names


def test_every_whitelisted_name_still_clears_a_vulture_finding(
    declared: dict[str, tuple[str, ...]], reported_without_whitelist: frozenset[str]
) -> None:
    """A parameter that still exists at its source can nonetheless stop needing the exemption.

    The signature check above cannot see that: a body that now reads the parameter,
    or a decorator vulture ignores, leaves the name present while the entry
    clears nothing. Such an entry only hides an unrelated same-named finding
    later, so it must be deleted.
    """
    idle = sorted({name for names in declared.values() for name in names} - reported_without_whitelist)

    assert not idle, f"whitelist entries that clear no vulture finding: {idle}"


def test_the_effect_check_names_an_entry_that_clears_nothing(reported_without_whitelist: frozenset[str]) -> None:
    """Detector teeth: an invented name is absent from the scan, so it would be called idle."""
    invented = _declared_parameters("def _mirror(never_reported_anywhere: object) -> None:\n    pass\n")

    idle = [name for name in invented["_mirror"] if name not in reported_without_whitelist]

    assert idle == ["never_reported_anywhere"]
