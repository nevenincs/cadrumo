"""Retired command-graph generator sources and caches stay physically absent.

Lives here rather than under ``src/cadrumo`` because it names two retired
``dev/quality`` generator scripts and a ``dev/docs`` active consumer directly
-- the check is a cross-tree assertion about the development tooling tree,
not a property of the shipped package alone.
"""

from __future__ import annotations

import ast

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_legacy_registry_and_generated_cache_sources_are_physically_absent() -> None:
    cli = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
    root = REPO_ROOT
    absent = (
        cli / "_app_lazy_registration.py",
        cli / "_app_lazy_families.py",
        cli / "app_lazy_manifest.v1.json",
        cli / "command_registration_metadata.v1.json",
        root / "dev/quality/generate_app_lazy_manifest.py",
        root / "dev/quality/generate_command_registration_metadata.py",
    )
    assert all(not path.exists() for path in absent)
    for path in (cli / "_command_schema.py", cli / "_verb_input_schema.py"):
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert "importlib.resources" not in source
        assert "typer._click" not in source
        assert "schema_surface" not in source
        assert ".v1.json" not in source
    active_consumers = (cli / "_common.py", root / "dev/docs/cli_reference.py")
    forbidden = (
        "ROOT_LANDING_SCHEMA_KEYS",
        "GROUP_CALLBACK_SCHEMA_KEYS",
        "_LAZY_REGISTRY",
        "SCHEMA_REGISTRY",
        "_optional_extra_surface",
    )
    for path in active_consumers:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert all(token not in source for token in forbidden)
    core_contract = root / "src/cadrumo/core/json_contract.py"
    source = core_contract.read_text(encoding="utf-8")
    ast.parse(source)
    assert "SCHEMA_REGISTRY" not in source
    assert "register_schema" not in source
