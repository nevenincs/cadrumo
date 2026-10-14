"""The runtime host owns its storage-path producers independently of tax frontends."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.tests.storage_provenance import root_join_sites

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOST = Path(__file__).resolve().parents[1]
_PERMITTED_PRODUCERS = {
    ("tests/windows_worker_parent_fixture.py", "_admitted_worker_composition"),
}


def test_runtime_host_storage_producers_are_owned_and_live() -> None:
    """A host-only join must retain a specific owner; stale declarations also fail."""
    modules = tuple(_HOST.rglob("*.py"))
    assert modules, "the runtime host source census collapsed"
    sites = {
        site.key
        for path in modules
        if "cadrumo_local_storage_root" in (source := path.read_text(encoding="utf-8"))
        for site in root_join_sites(path.relative_to(_HOST).as_posix(), ast.parse(source))
    }
    assert sites == _PERMITTED_PRODUCERS, (
        f"undeclared runtime producers: {sorted(sites - _PERMITTED_PRODUCERS)}; "
        f"stale runtime producer claims: {sorted(_PERMITTED_PRODUCERS - sites)}"
    )
