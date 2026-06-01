"""Audit gate: module-level test coverage inventory.

Walks every production Python module under src/aeat/ and compares
against the set of test_*.py files present in the same directory.
Modules without a sibling test_*.py are recorded as coverage gaps.

This file provides the real-behavior test that asserts every
production module either has a paired test or appears in the
documented exemption list below. The COVERAGE_GAPS set captures
the currently-known untested modules; entries are removed as tests
are added, and the test enforces that the on-disk state never exceeds
the declared gap set (i.e. new untested modules cannot be added
silently).

Exemption criteria (modules excluded from the gap requirement):
  - __init__.py files (package roots; tested transitively)
  - conftest.py (pytest configuration; not production logic)
  - Modules named fixtures.py or _fixtures.py (test-support only)
  - Modules under __pycache__ directories
  - test_*.py files themselves
"""

from __future__ import annotations

import ast
from collections import deque
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

# Modules that exist without a paired test_*.py at the time of this
# inventory.  The test below asserts that the live gap set is a subset
# of this declared set — new untested modules cannot sneak in without
# updating this file.
COVERAGE_GAPS: frozenset[str] = frozenset(
    {
        # Known untested modules.  These reside in directories with no
        # paired test_*.py file and are tracked for future coverage.
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
        "src/aeat/tests/fixtures/borrador/_generate.py",
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
    gaps are tracked in COVERAGE_GAPS.
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
        f"src/aeat/test_coverage_inventory.py with a justification note:\n\n"
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


# ---------------------------------------------------------------------------
# Import-graph-aware coverage helper.
#
# The legacy ``_has_paired_test`` check above only recognises the trivial
# "module M lives next to a ``test_*.py`` file" pattern. Many production
# modules are exercised transitively: a sibling ``__init__.py`` or aggregator
# module imports them, and the aggregator is in turn imported by a real test.
# This helper walks the import graph rooted at every ``test_*.py`` /
# ``conftest.py`` under ``src/aeat/``, resolves relative imports to their
# absolute ``aeat.*`` dotted paths, and computes the transitive closure of
# production modules reachable from any test. A module that is reachable in
# this closure is considered transitively covered.
#
# Limitations: the walker only follows static ``import`` / ``from ... import``
# statements. Dynamic imports (importlib.import_module on a runtime-built
# string) are invisible to the walker; modules loaded only through dynamic
# dispatch must still be tracked through ``_EXEMPTIONS`` or a dedicated test.
# ---------------------------------------------------------------------------


_AEAT_PACKAGE = "aeat"


def _module_path_for_dotted(dotted: str) -> Path | None:
    """Return the on-disk file for an ``aeat.*`` dotted module name.

    Resolves to either ``<rel>.py`` or ``<rel>/__init__.py`` if either
    exists; returns ``None`` for names that do not map to a real file
    (e.g. ``from .foo import bar`` where ``bar`` is a re-exported name
    in ``foo``'s namespace and not a submodule).
    """
    if not dotted.startswith(_AEAT_PACKAGE):
        return None
    parts = dotted.split(".")
    base = _SRC_ROOT.parent  # src/
    candidate_module = base.joinpath(*parts).with_suffix(".py")
    if candidate_module.is_file():
        return candidate_module
    candidate_package = base.joinpath(*parts, "__init__.py")
    if candidate_package.is_file():
        return candidate_package
    return None


def _file_to_dotted(file_path: Path) -> str:
    """Convert a file under ``src/aeat/`` to its dotted module name."""
    rel = file_path.relative_to(_SRC_ROOT.parent)  # relative to src/
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current_dotted: str, level: int, module: str | None) -> str | None:
    """Resolve a relative-import target to an absolute dotted name.

    ``current_dotted`` is the dotted name of the file containing the
    ``from ... import`` statement (e.g. ``aeat.domain.portals._registry``).
    ``level`` is the number of leading dots in the relative import.
    ``module`` is the module name after the dots, or ``None`` for
    ``from . import x``.
    """
    if level == 0:
        return module
    parts = current_dotted.split(".")
    # __init__-style files are represented without the trailing __init__,
    # so the file at aeat.domain.portals (init) treats `.foo` as
    # aeat.domain.portals.foo. A submodule file like
    # aeat.domain.portals._registry treats `.foo` as
    # aeat.domain.portals.foo (level=1 strips _registry).
    init_path = _SRC_ROOT.parent.joinpath(*parts, "__init__.py")
    is_init = init_path.is_file()
    if is_init:
        # `current_dotted` is the package; level 1 stays in the same package.
        ancestor = parts[: len(parts) - (level - 1)] if level > 0 else parts
    else:
        # `current_dotted` is a module file; level 1 means the parent package.
        ancestor = parts[: len(parts) - level]
    if not ancestor:
        return None
    if module:
        return ".".join([*ancestor, module])
    return ".".join(ancestor)


def _aeat_imports_in(file_path: Path) -> set[str]:
    """Return absolute ``aeat.*`` dotted names imported by ``file_path``.

    For ``from X import Y, Z`` the returned set includes ``X``, ``X.Y``,
    and ``X.Z``; the caller resolves each candidate to a file via
    :func:`_module_path_for_dotted` and silently drops non-module names.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return set()

    current_dotted = _file_to_dotted(file_path)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_AEAT_PACKAGE):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative(current_dotted, node.level, node.module)
            if base is None or not base.startswith(_AEAT_PACKAGE):
                continue
            found.add(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                found.add(f"{base}.{alias.name}")
    return found


def _collect_test_entrypoints() -> list[Path]:
    """Return every ``test_*.py`` and ``conftest.py`` under ``src/aeat/``."""
    return [
        p
        for p in sorted(_SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in p.parts and (p.name.startswith("test_") or p.name == "conftest.py")
    ]


def _transitively_reachable_from_tests() -> set[Path]:
    """Return the set of production module paths reachable from any test.

    The closure starts at every test/conftest entrypoint, follows static
    ``aeat.*`` imports, and stops when no new on-disk module is added.
    Returned paths are absolute and may include both ``foo.py`` modules
    and ``foo/__init__.py`` package roots.
    """
    seen: set[Path] = set()
    queue: deque[Path] = deque(_collect_test_entrypoints())
    while queue:
        current = queue.popleft()
        for dotted in _aeat_imports_in(current):
            target = _module_path_for_dotted(dotted)
            if target is None or target in seen:
                continue
            seen.add(target)
            queue.append(target)
    return seen


def _has_import_graph_coverage(module: Path, reachable: set[Path]) -> bool:
    """Return True if ``module`` is in the test-rooted import closure.

    Package ``__init__.py`` files are considered covered when any module
    under the same package is reachable; the package always imports as a
    side-effect of its submodules being touched.
    """
    if module in reachable:
        return True
    if module.name == "__init__.py":
        package_root = module.parent
        return any(package_root in p.parents for p in reachable)
    return False


def test_import_graph_helper_recognises_aggregator_pattern() -> None:
    """Positive control: portal entries are covered via _registry aggregator."""
    reachable = _transitively_reachable_from_tests()
    # _registry.py imports every portal entry; test_registry.py imports
    # _registry. The closure must therefore include at least one of the
    # portal entry files even though no test_*.py sits next to them.
    portal_entries_dir = _SRC_ROOT / "domain" / "portals" / "_entries"
    portal_modules = [
        p
        for p in portal_entries_dir.glob("portal_*.py")
        if not p.name.startswith("test_")
    ]
    assert portal_modules, "expected portal_*.py entries to exist"
    reached = [p for p in portal_modules if p in reachable]
    assert reached, (
        "import-graph helper failed to reach any portal entry via "
        "aeat.domain.portals._registry aggregator imports"
    )


def test_import_graph_helper_skips_orphan_modules() -> None:
    """Negative control: a synthetic dotted name with no file resolves to None."""
    assert _module_path_for_dotted("aeat.does.not.exist.module") is None
    # And a non-aeat dotted name is never resolved.
    assert _module_path_for_dotted("os.path") is None


def test_hidden_coverage_gaps_inventory() -> None:
    """Enumerate production modules invisible to the import-graph closure.

    A "hidden gap" is a production module that (a) has no paired
    ``test_*.py`` in its directory (so the legacy check would record it
    under COVERAGE_GAPS) AND (b) is not reachable through the static
    import graph from any test entrypoint. These modules are the real
    coverage debt that the legacy filename-pairing rule masks behind
    the COVERAGE_GAPS allowlist.

    This test FAILS by design until each hidden gap is either covered
    with a real-behavior test or formally exempted with a rationale.
    The failure message enumerates the per-module list so subsequent
    sessions can plan the work.
    """
    production_modules = _collect_production_modules()
    reachable = _transitively_reachable_from_tests()
    hidden_gaps: list[str] = []
    for module in production_modules:
        if _has_paired_test(module):
            continue
        if _has_import_graph_coverage(module, reachable):
            continue
        hidden_gaps.append(module.relative_to(PROJECT_ROOT).as_posix())

    assert not hidden_gaps, (
        f"Hidden coverage gaps detected ({len(hidden_gaps)} modules).\n"
        "These production modules have no paired test_*.py and are not\n"
        "reachable through the static import graph from any test entrypoint.\n"
        "Either author a real-behavior test, route the module through an\n"
        "existing covered aggregator, or exempt it in _EXEMPTIONS with a\n"
        "rationale.\n\n"
        + "\n".join(f"  {g}" for g in sorted(hidden_gaps))
    )
