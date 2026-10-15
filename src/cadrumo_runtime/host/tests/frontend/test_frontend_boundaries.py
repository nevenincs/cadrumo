"""The managing runtime owns composition and integration of the tax interfaces."""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SOURCE = Path(__file__).resolve().parents[4]
_FORBIDDEN = (
    "cadrumo_runtime",
    "cadrumo_client.transport.installed_client",
    "cadrumo_client.transport.credentials",
    "cadrumo_client.commands.profile_admission",
)


def _host_references(source: str, package: str) -> frozenset[str]:
    tree = ast.parse(source)
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            reference = "." * node.level + (node.module or "")
            references.add(resolve_name(reference, package) if node.level else reference)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Deferred import targets must obey the same rule as static imports.
            references.add(node.value)
    return frozenset(
        reference
        for reference in references
        if any(reference == prefix or reference.startswith(prefix + ".") for prefix in _FORBIDDEN)
    )


def test_tax_interfaces_and_their_unit_tests_have_no_host_composition_dependency() -> None:
    files = tuple((_SOURCE / "cadrumo" / "entrypoints").rglob("*.py"))
    assert len(files) > 100
    offenders: dict[str, tuple[str, ...]] = {}
    for path in files:
        module = ".".join(path.relative_to(_SOURCE).with_suffix("").parts)
        package = module if path.stem == "__init__" else module.rpartition(".")[0]
        references = _host_references(path.read_text(encoding="utf-8"), package)
        if references:
            offenders[path.relative_to(_SOURCE).as_posix()] = tuple(sorted(references))
    assert not offenders, offenders


@pytest.mark.parametrize(
    "source",
    (
        "from cadrumo_runtime.host.frontend.cli.app import aeat_cli_app",
        "from cadrumo_client.transport.installed_client import open_installed_client",
        "from cadrumo_client.commands.profile_admission import activate_profile",
        'target = DeferredTarget("cadrumo_runtime.host.frontend.tui.launcher", "main")',
    ),
)
def test_boundary_check_rejects_representative_host_leaks(source: str) -> None:
    assert _host_references(source, "cadrumo.entrypoints.cli")


def test_boundary_check_accepts_public_ports_and_transport_contracts() -> None:
    source = "from cadrumo_client.contracts.contracts import RefusalError"
    assert not _host_references(source, "cadrumo.entrypoints.cli")


def test_installed_composition_and_native_journeys_are_runtime_owned() -> None:
    product = _SOURCE / "cadrumo" / "entrypoints" / "tui"
    host = _SOURCE / "cadrumo_runtime" / "host"
    assert not (product / "installed_session.py").exists()
    assert not (product / "runtime_admission.py").exists()
    assert (host / "frontend" / "tui" / "installed_session.py").is_file()
    assert (host / "frontend" / "cli" / "app.py").is_file()
    assert (host / "tests" / "frontend" / "tui" / "test_profile_wizard_native.py").is_file()
    assert (host / "tests" / "frontend" / "cli" / "test_censo_credentials_native.py").is_file()
