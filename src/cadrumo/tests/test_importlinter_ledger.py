"""Structural checks for the Import Linter ignore ledger.

See Also:
    :mod:`~tests._inventory`
        Provides the repository root anchor used to parse ``.importlinter``
        without depending on the current working directory.
    ``.importlinter``
        Layered architecture contract and ignore ledger ratcheted by these
        tests.

The layered import-boundary model and its sanctioned exception registry must
not drift unnoticed; this ratchet is what makes that drift visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from ._inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IMPORTLINTER = REPO_ROOT / ".importlinter"
_SOURCE_ROOT = REPO_ROOT / "src"

_CONTRACT_RE = re.compile(r"^\[importlinter:contract:(?P<contract>[^\]]+)\]$")
_IGNORE_EDGE_RE = re.compile(r"^\s*(?P<source>cadrumo\.[\w.*]+)\s*->\s*(?P<target>cadrumo\.[\w.*]+)\s*$")

_APPLICATION_TO_ADAPTERS_BASELINE = 199  # reconciled live ceiling; this ratchet may decrease but not grow
_APPLICATION_SOURCE_MODULE_BASELINE = 78  # prorrata register application adapter pin
_DOMAIN_TO_ADAPTERS_BASELINE = 70  # filing-amendment repository domain roundtrip test increment (+1)


@dataclass(frozen=True)
class IgnoreEdge:
    contract: str
    line_no: int
    source: str
    target: str


def _ignore_edges() -> tuple[IgnoreEdge, ...]:
    contract = ""
    edges: list[IgnoreEdge] = []
    for line_no, line in enumerate(_IMPORTLINTER.read_text(encoding="utf-8").splitlines(), start=1):
        contract_match = _CONTRACT_RE.match(line)
        if contract_match is not None:
            contract = contract_match.group("contract")
            continue
        edge_match = _IGNORE_EDGE_RE.match(line)
        if edge_match is None:
            continue
        edges.append(
            IgnoreEdge(
                contract=contract,
                line_no=line_no,
                source=edge_match.group("source"),
                target=edge_match.group("target"),
            ),
        )
    return tuple(edges)


@pytest.fixture(scope="module")
def ignore_edges() -> tuple[IgnoreEdge, ...]:
    """Return parsed Import Linter ignore edges once for this test module."""
    return _ignore_edges()


@pytest.fixture(scope="module")
def layered_edges(ignore_edges: tuple[IgnoreEdge, ...]) -> tuple[IgnoreEdge, ...]:
    """Return the parsed layered-contract ignore edges."""
    return tuple(edge for edge in ignore_edges if edge.contract == "layered")


def _resolve_module_path(module: str) -> Path:
    wildcard_index = module.find(".*")
    if wildcard_index != -1:
        module = module[:wildcard_index]
    return _SOURCE_ROOT / Path(*module.split("."))


def _module_exists(module: str) -> bool:
    path = _resolve_module_path(module)
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def test_ignore_import_modules_resolve_on_disk(ignore_edges: tuple[IgnoreEdge, ...]) -> None:
    missing: list[str] = []
    for edge in ignore_edges:
        for module in (edge.source, edge.target):
            if not _module_exists(module):
                missing.append(f"line {edge.line_no}: {module}")

    assert missing == []


def test_application_to_adapters_pin_count_does_not_grow(layered_edges: tuple[IgnoreEdge, ...]) -> None:
    application_adapter_edges = tuple(
        edge
        for edge in layered_edges
        if edge.source.startswith("cadrumo.application.") and edge.target.startswith("cadrumo.adapters")
    )
    blanket_edges = tuple(
        edge
        for edge in application_adapter_edges
        if edge.source == "cadrumo.application.**" and edge.target == "cadrumo.adapters.**"
    )
    source_module_edges = tuple(edge for edge in application_adapter_edges if edge.target == "cadrumo.adapters.**")

    assert not blanket_edges
    assert len(application_adapter_edges) <= _APPLICATION_TO_ADAPTERS_BASELINE
    assert len(source_module_edges) <= _APPLICATION_SOURCE_MODULE_BASELINE


def test_domain_to_adapters_pin_count_does_not_grow(layered_edges: tuple[IgnoreEdge, ...]) -> None:
    domain_adapter_edges = tuple(
        edge
        for edge in layered_edges
        if edge.source.startswith("cadrumo.domain.") and edge.target.startswith("cadrumo.adapters")
    )

    assert len(domain_adapter_edges) <= _DOMAIN_TO_ADAPTERS_BASELINE


def test_zero_production_domain_to_adapters_edges(ignore_edges: tuple[IgnoreEdge, ...]) -> None:
    """No production domain module may pin a domain -> adapters ignore edge.

    Every production domain repository now sits behind a Protocol port with its
    concrete class under ``adapters.persistence.profile``. Only test-file roundtrip / anti-tautology edges —
    which legitimately construct the concrete adapter to exercise the encrypted
    boundary — may remain. A production domain -> adapters edge reappearing here
    is an architecture regression and must fail loudly, not ratchet.
    """
    production_domain_adapter_edges = tuple(
        edge
        for edge in ignore_edges
        if edge.source.startswith("cadrumo.domain.")
        and edge.target.startswith("cadrumo.adapters")
        and ".tests." not in edge.source
        and not edge.source.endswith(".conftest")
    )

    assert production_domain_adapter_edges == (), (
        "production domain -> adapters ignore edges must be zero after the ports-inversion "
        f"seam closeout; found: {[f'line {e.line_no}: {e.source} -> {e.target}' for e in production_domain_adapter_edges]}"
    )
