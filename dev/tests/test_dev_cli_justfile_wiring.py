"""Contract between maintained developer CLIs and the public Just surface."""

from __future__ import annotations

from typing import Final

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPECTED_WIRING: Final[dict[str, str]] = {
    "dev.docs.apidocs": "docs-api-scaffold",
    "dev.docs.sequences": "docs-sequences-check",
    "dev.docs.terminology.coverage": "docs-terminology-coverage",
    "dev.docs.terminology.sweep": "docs-terminology-sweep",
    "dev.docs.terminology.synonyms": "docs-terminology-synonyms",
    "dev.docs.terminology_handbook": "docs-terminology",
    "dev.identity": "check-identity",
    "dev.locales": "locales",
    "dev.registry.aeip": "audit-aeip",
    "dev.registry.conformance": "audit-registry-conformance",
    "dev.registry.newmodelo": "newmodelo",
    "dev.registry.pipeline": "registry-pipeline",
    "dev.tui": "tui-review",
    "dev.tui.harness": "tui-harness",
}

_STANDALONE_CLIS: Final[frozenset[str]] = frozenset(
    {
        "dev.docs.terminology.coverage",
        "dev.docs.terminology.sweep",
        "dev.docs.terminology.synonyms",
    }
)


def test_every_maintained_dev_cli_is_reachable_from_a_named_recipe() -> None:
    """A module-level command must not require contributors to know its import path."""
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    missing = {
        module: recipe
        for module, recipe in _EXPECTED_WIRING.items()
        if recipe not in justfile or f"python -m {module}" not in justfile
    }
    assert not missing, f"developer CLIs missing their Just wiring: {missing}"


def test_the_wiring_census_names_every_package_entry_point() -> None:
    """A newly added ``dev/**/__main__.py`` cannot silently escape the contract."""
    discovered = {
        ".".join(path.relative_to(REPO_ROOT).parent.parts) for path in (REPO_ROOT / "dev").rglob("__main__.py")
    }
    expected_packages = set(_EXPECTED_WIRING) - _STANDALONE_CLIS
    assert discovered == expected_packages, (
        "update the developer CLI wiring and its census together: "
        f"missing={sorted(discovered - expected_packages)}, "
        f"stale={sorted(expected_packages - discovered)}"
    )


def test_standalone_cli_modules_in_the_wiring_census_exist() -> None:
    """Standalone executable modules receive the same existence check as packages."""
    missing = [module for module in _STANDALONE_CLIS if not (REPO_ROOT / (module.replace(".", "/") + ".py")).is_file()]
    assert not missing, f"standalone developer CLI modules no longer exist: {missing}"
