"""Calculation-completeness and Diseño coverage record-design tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path

from ._record_design_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Calculation-completeness manifest drift + full-Diseño coverage advisory
# (off-load-path)
# ---------------------------------------------------------------------------
#
# Two off-load-path concerns, neither on the snapshot-build hot path:
#
# - The load-blocking calculation-completeness gate in RegistryValidator
#   compares a revision's declared casillas against a checked-in
#   calculation-completeness manifest. The drift test below re-derives
#   each checked-in manifest from its corpus Diseño (the calculation
#   closure intersected with the Diseño) and fails CI if a manifest has
#   drifted from the corpus it claims to be derived from.
#
# - The full-Diseño coverage report is an *advisory* inventory: it
#   extracts every casilla AEAT declares in a Diseño — accounting-
#   statement data-entry fields included — and surfaces form-level
#   coverage as information, never as a load-blocking gate. It is the
#   counterpart to the bounded calculation-completeness gate.


def _modelo_200_record_design_corpus_path() -> Path:
    """Return the corpus path of the Modelo 200 record-design Diseño."""
    modelos, catalogues = _committed_registry_tree()
    modelo_200 = next(modelo for modelo in modelos if modelo.id == "200")
    revision = next(iter(modelo_200.revisions.values()))
    source_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
    return bundled_path() / catalogues.sources[source_ref].corpus_path


def test_modelo_registry_tests_use_public_record_design_dispatcher() -> None:
    registry_tests = scan_directory(Path(__file__).parent, pattern="test_modelo_*_registry.py", require_root=True)

    assert registry_tests, (
        "no test_modelo_*_registry.py module matched; a walk that matches nothing reports no "
        "private record-design import exactly as a suite using only the public dispatcher does"
    )

    private_imports = [
        path.name for path in registry_tests if "._record_design import" in path.read_text(encoding="utf-8")
    ]

    assert private_imports == []


def _record_design_corpus_paths(modelo_id: str) -> tuple[Path, ...]:
    """Every record-design corpus path any revision of ``modelo_id`` cites.

    Keyed on ``modelo.revisions`` rather than a pinned revision id. Modelo 390
    carries one revision today and is being split into filing epochs; a fixed id
    would silently stop covering anything the moment that lands, and would still
    pass, which is the failure this helper exists to avoid.
    """
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == modelo_id)
    paths: list[Path] = []
    for revision in modelo.revisions.values():
        for ref in revision.source_refs:
            source = catalogues.sources[ref]
            if source.kind == "record_design":
                paths.append(bundled_path() / source.corpus_path)
    return tuple(dict.fromkeys(paths))
