"""Prove every vulture whitelist entry still names a live parameter.

`dev.quality.module_test_reach` listed `dev/audit/vulture_whitelist.py` as
unreached. It is a SUPPRESSION surface: every name in it is a name vulture stops
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
import importlib
import inspect
import pathlib

import pytest

from .. import vulture_whitelist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CITATIONS: dict[str, tuple[str, str | None, str]] = {
    "_execute": ("cadrumo.adapters.outbound.google.api", "_ExecutableRequest", "execute"),
    "_get_media": (
        "cadrumo.adapters.outbound.google.document_link_resolver",
        "_DriveFilesResource",
        "get_media",
    ),
    "_list_files": (
        "cadrumo.adapters.outbound.google.document_link_resolver",
        "_DriveFilesResource",
        "list",
    ),
    "_reduce_ex": ("cadrumo.application.ledger.evidence_input", "EvidenceInput", "__reduce_ex__"),
    "_set_language_field": ("dev.docs.terminology_handbook._curation", None, "set_language_field"),
    "_sheets_discovery_build": (
        "cadrumo.application.storage.calc_sheets.parity_harness",
        "_SheetsDiscoveryBuilder",
        "__call__",
    ),
}


def _declared_parameters(source: str) -> dict[str, tuple[str, ...]]:
    """Return each mirror function in whitelist source mapped to its parameter names."""
    tree = ast.parse(source)
    declared: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            declared[node.name] = tuple(argument.arg for argument in node.args.args)
    return declared


def _cited_parameters(module_name: str, class_name: str | None, attribute: str) -> frozenset[str]:
    module = importlib.import_module(module_name)
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
    # and retire that gate in silence. A floor, not a pinned count: the
    # whitelist declares 6 mirrored parameters.
    assert len(_CITATIONS) >= 5, (
        f"only {len(_CITATIONS)} citations remain, so the per-mirror gate below runs "
        "over almost nothing and this equality is close to vacuous"
    )
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
    module_name, class_name, attribute = _CITATIONS["_set_language_field"]
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

    assert not [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert all(name.startswith("_") for name in declared), "a mirror is exported under a public name"
