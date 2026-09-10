"""Compiler refusal gates for invalid authored IVA-rate candidates.

These tests stage a real candidate ``rates.toml`` and run the development
compiler against the same reviewed catalogues and corpus as publication. They
prove that an invalid edit is refused before it can become an authority
artifact; shipped runtime never opens this authoring input.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues
from cadrumo.domain.iva.errors import IvaCatalogueError
from dev.registry.compiler.iva import compile_iva_rate_facts, reset_iva_rate_fact_provider
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@contextmanager
def _reviewed_compilation_scope() -> Iterator[None]:
    """Supply the real reviewed catalogues and evidence to a staged candidate."""
    registry_root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(registry_root)
    with compiling_catalogues(catalogues.legal, catalogues.sources, bundled_path()):
        yield


def _candidate_rate_table(tmp_path: Path) -> Path:
    """Stage the production candidate input at the compiler's expected root."""
    candidate = tmp_path / "registry" / "aeat"
    rates = candidate / "iva" / "rates.toml"
    rates.parent.mkdir(parents=True)
    source = bundled_path("registry", "aeat", "iva", "rates.toml")
    rates.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return rates


def _replace_one_authored_reference(rates: Path, *, lane: str) -> None:
    """Turn one declared evidence reference into an unresolvable candidate edit."""
    payload = tomllib.loads(rates.read_text(encoding="utf-8"))
    reference = next(reference_id for row in payload["rates"] for reference_id in row.get(lane, ()))
    rates.write_text(
        rates.read_text(encoding="utf-8").replace(reference, "candidate-reference-that-does-not-exist", 1),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("lane", "expected_failure"),
    (
        pytest.param("legal_refs", "unknown legal_ref", id="unknown-legal-reference"),
        pytest.param("source_refs", "unknown source_ref", id="unknown-source-reference"),
    ),
)
def test_compiler_refuses_candidate_with_unresolvable_grounding_reference(
    tmp_path: Path, lane: str, expected_failure: str
) -> None:
    """A bad evidence edit cannot pass the compiler or reach artifact publication."""
    rates = _candidate_rate_table(tmp_path)
    _replace_one_authored_reference(rates, lane=lane)
    reset_iva_rate_fact_provider()

    with _reviewed_compilation_scope(), pytest.raises(IvaCatalogueError, match=expected_failure):
        compile_iva_rate_facts(rates.parents[1])
