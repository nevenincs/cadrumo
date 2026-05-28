"""Audit gate: module-level test coverage inventory.

S215 enumeration — production modules without a paired test file:
  Walks every production Python module under src/aeat/ and compares
  against the set of test_*.py files present in the same directory.
  Modules without a sibling test_*.py are recorded as coverage gaps.

S216 assertion — this file provides the real-behavior test that asserts
  every production module either has a paired test or appears in the
  documented exemption list below.

Wave 2 follow-up Steps (S215 enumeration output):
  The COVERAGE_GAPS set below is the canonical output of the S215
  enumeration pass.  Each entry is a Wave 2 follow-up target.  Entries
  are removed as tests are added; the test below enforces that the
  on-disk state never exceeds the declared gap set (i.e. new untested
  modules cannot be added silently).

Exemption criteria (modules excluded from the gap requirement):
  - __init__.py files (package roots; tested transitively)
  - conftest.py (pytest configuration; not production logic)
  - Modules named fixtures.py or _fixtures.py (test-support only)
  - Modules under __pycache__ directories
  - test_*.py files themselves
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = PROJECT_ROOT / "src" / "aeat"

# Modules exempted from the pairing requirement.  Each entry is a
# POSIX path relative to PROJECT_ROOT.  Add a one-line justification
# comment for each.
_EXEMPTIONS: frozenset[str] = frozenset(
    {
        # Package __init__ files are tested transitively through their submodules.
        # Fixtures / conftest modules are test-support infrastructure.
        # _playwright.py requires a running browser; browser integration tests
        # live in a separate live-test suite.
        "src/aeat/adapters/outbound/aeat/_playwright.py",
        # Locale scaffold tooling; exercised via CLI integration tests.
        "src/aeat/locales/scaffold.py",
    }
)

# Modules that exist without a paired test_*.py as of the S215 enumeration
# pass (2026-05-28).  These are the Wave 2 follow-up targets.  The test
# below asserts that the live gap set is a subset of this declared set —
# new untested modules cannot sneak in without updating this file.
COVERAGE_GAPS: frozenset[str] = frozenset(
    {
        # Wave 2 follow-ups from S215 enumeration pass (2026-05-28).
        # These modules reside in directories with no paired test_*.py file.
        # Each is a follow-up target for Wave 2 test-coverage work.
        #
        # adapters/inbound — sub-parsers in directories with no test file
        "src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py",
        "src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py",
        "src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py",
        "src/aeat/adapters/inbound/justificante/_parsers/_pdfplumber_backend.py",
        # adapters/outbound — certificate backends and LLM providers
        "src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_base.py",
        "src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py",
        "src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py",
        "src/aeat/adapters/outbound/llm/_providers/anthropic.py",
        "src/aeat/adapters/outbound/llm/_providers/base.py",
        "src/aeat/adapters/outbound/llm/_providers/deterministic.py",
        "src/aeat/adapters/outbound/llm/_providers/gemini.py",
        "src/aeat/adapters/outbound/llm/_providers/local.py",
        "src/aeat/adapters/outbound/llm/_providers/openai.py",
        # core — error registry sub-packages and access gate
        "src/aeat/core/access_gate/_errors.py",
        "src/aeat/core/errors/registry/_adapters.py",
        "src/aeat/core/errors/registry/_application.py",
        "src/aeat/core/errors/registry/_core.py",
        "src/aeat/core/errors/registry/_domain.py",
        "src/aeat/core/errors/registry/_entrypoints.py",
        # domain — reconciliation errors and portal entry definitions
        "src/aeat/domain/filing/reconciliation/_errors.py",
        "src/aeat/domain/portals/_entries/_common.py",
        "src/aeat/domain/portals/_entries/portal_calendario_contribuyente.py",
        "src/aeat/domain/portals/_entries/portal_cert_selection.py",
        "src/aeat/domain/portals/_entries/portal_cert_validation_rest.py",
        "src/aeat/domain/portals/_entries/portal_clave_gestiones.py",
        "src/aeat/domain/portals/_entries/portal_clave_idp_root.py",
        "src/aeat/domain/portals/_entries/portal_clave_sede_entry.py",
        "src/aeat/domain/portals/_entries/portal_consulta_pagos.py",
        "src/aeat/domain/portals/_entries/portal_dnie_sede_entry.py",
        "src/aeat/domain/portals/_entries/portal_domiciliacion_bancaria.py",
        "src/aeat/domain/portals/_entries/portal_m036_censal.py",
        "src/aeat/domain/portals/_entries/portal_m037_censal_simplificada.py",
        "src/aeat/domain/portals/_entries/portal_m100_renta.py",
        "src/aeat/domain/portals/_entries/portal_m111_retenciones_trabajo.py",
        "src/aeat/domain/portals/_entries/portal_m115_retenciones_arrendamientos.py",
        "src/aeat/domain/portals/_entries/portal_m123_retenciones_capital.py",
        "src/aeat/domain/portals/_entries/portal_m130_pago_fraccionado_ed.py",
        "src/aeat/domain/portals/_entries/portal_m131_pago_fraccionado_eo.py",
        "src/aeat/domain/portals/_entries/portal_m180_resumen_arrendamientos.py",
        "src/aeat/domain/portals/_entries/portal_m190_resumen_trabajo.py",
        "src/aeat/domain/portals/_entries/portal_m193_resumen_capital.py",
        "src/aeat/domain/portals/_entries/portal_m200_sociedades_anual.py",
        "src/aeat/domain/portals/_entries/portal_m202_sociedades_fraccionado.py",
        "src/aeat/domain/portals/_entries/portal_m232_vinculadas.py",
        "src/aeat/domain/portals/_entries/portal_m303_iva_autoliquidacion.py",
        "src/aeat/domain/portals/_entries/portal_m347_operaciones_terceros.py",
        "src/aeat/domain/portals/_entries/portal_m349_intracomunitarias.py",
        "src/aeat/domain/portals/_entries/portal_m369_oss_ioss.py",
        "src/aeat/domain/portals/_entries/portal_m390_resumen_iva.py",
        "src/aeat/domain/portals/_entries/portal_m720_bienes_extranjero.py",
        "src/aeat/domain/portals/_entries/portal_m840_iae.py",
        "src/aeat/domain/portals/_entries/portal_mi_area_personal.py",
        "src/aeat/domain/portals/_entries/portal_mis_datos_censales.py",
        "src/aeat/domain/portals/_entries/portal_mis_documentos_pendientes_firma.py",
        "src/aeat/domain/portals/_entries/portal_mis_expedientes.py",
        "src/aeat/domain/portals/_entries/portal_mis_notificaciones.py",
        "src/aeat/domain/portals/_entries/portal_pago_autoliquidacion_cuenta.py",
        "src/aeat/domain/portals/_entries/portal_pago_autoliquidacion_tarjeta_bizum.py",
        "src/aeat/domain/portals/_entries/portal_pago_liquidaciones_deudas.py",
        "src/aeat/domain/portals/_entries/portal_pre303_ayuda.py",
        "src/aeat/domain/portals/_entries/portal_presentar_consultar_index.py",
        "src/aeat/domain/portals/_entries/portal_renta_web_borrador.py",
        "src/aeat/domain/portals/_entries/portal_sede_root.py",
        # tests/fixtures — generator scripts; no test file in their directories
        "src/aeat/tests/fixtures/financial/n26/_generate.py",
        "src/aeat/tests/fixtures/justificantes/_generate.py",
    }
)


def _is_exempt(rel: str) -> bool:
    """Return True if ``rel`` is exempted from the coverage requirement."""
    if rel in _EXEMPTIONS:
        return True
    parts = Path(rel).parts
    name = parts[-1] if parts else ""
    if name in {"__init__.py", "conftest.py", "fixtures.py", "_fixtures.py"}:
        return True
    if "__pycache__" in parts:
        return True
    return False


def _collect_production_modules() -> list[Path]:
    """Return every non-test, non-exempt Python module under src/aeat/."""
    return [
        p
        for p in sorted(_SRC_ROOT.rglob("*.py"))
        if not p.name.startswith("test_")
        and "__pycache__" not in p.parts
        and not _is_exempt(p.relative_to(PROJECT_ROOT).as_posix())
    ]


def _has_paired_test(module: Path) -> bool:
    """Return True if any test_*.py exists in the same directory as ``module``."""
    return any(module.parent.glob("test_*.py"))


def test_new_production_modules_have_test_coverage() -> None:
    """Every production module must either have a test or be in COVERAGE_GAPS.

    A new module added without a paired test_*.py will fail this gate
    immediately, surfacing the gap before it grows stale.  Existing known
    gaps are tracked in COVERAGE_GAPS and treated as Wave 2 follow-ups.
    """
    production_modules = _collect_production_modules()
    new_gaps: list[str] = []
    for module in production_modules:
        if _has_paired_test(module):
            continue
        rel = module.relative_to(PROJECT_ROOT).as_posix()
        if rel not in COVERAGE_GAPS:
            new_gaps.append(rel)

    assert not new_gaps, (
        "New production modules added without a paired test_*.py.\n"
        "Either add a test file or add the module to COVERAGE_GAPS in\n"
        f"src/aeat/test_coverage_inventory.py with a Wave 2 follow-up note:\n\n"
        + "\n".join(f"  {g}" for g in sorted(new_gaps))
    )


def test_coverage_gaps_declared_set_matches_reality() -> None:
    """Every entry in COVERAGE_GAPS must still exist as an untested module.

    When a test is added for a gap module, its COVERAGE_GAPS entry must
    be removed.  This test fails if a gap entry is stale (the module now
    has a test or was deleted).
    """
    stale: list[str] = []
    for rel in sorted(COVERAGE_GAPS):
        module = PROJECT_ROOT / rel
        if not module.exists():
            stale.append(f"{rel} (module deleted)")
            continue
        if _has_paired_test(module):
            stale.append(f"{rel} (now has a paired test — remove from COVERAGE_GAPS)")

    assert not stale, (
        "Stale entries in COVERAGE_GAPS — remove them:\n"
        + "\n".join(f"  {s}" for s in stale)
    )
