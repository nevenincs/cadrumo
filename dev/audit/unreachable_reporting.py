"""Filter and render typed reachability evidence with the declared output bounds."""

from __future__ import annotations

import json

from .unreachable_models import (
    Confidence,
    ModuleFinding,
    ModuleReach,
    SymbolFinding,
    TestFinding,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    _Finding,
)
from .unreachable_policy import _FINDING_CAP

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _console_finding_sections(result: UnreachableCodeResult) -> list[tuple[str, tuple[_Finding, ...]]]:
    """Console finding sections."""
    unreachable = tuple(f for f in result.modules if f.reach is ModuleReach.UNREACHABLE)
    exec_only = tuple(f for f in result.modules if f.reach is ModuleReach.MODULE_EXEC_ONLY)
    type_only = tuple(f for f in result.modules if f.reach is ModuleReach.TYPE_ONLY)
    sections: list[tuple[str, tuple[_Finding, ...]]] = [
        (f"modules unreachable from the entrypoints ({result.unreachable_module_total} modules) [exact]", unreachable),
        (
            f"modules only a `python -m` surface reaches, never a console script ({len(exec_only)}) [exact]",
            exec_only,
        ),
        (f"modules reachable only through TYPE_CHECKING imports ({len(type_only)}) [exact]", type_only),
        (f"test modules whose every shipped subject is a finding ({len(result.tests)})", result.tests),
        (f"symbols never referenced by reachable shipped code ({len(result.symbols)})", result.symbols),
    ]
    return sections


def filter_by_confidence(result: UnreachableCodeResult, tier: Confidence) -> UnreachableCodeResult:
    """Return the same result narrowed to one confidence tier.

    A campaign picks the exact tier up first, so the narrowing is done here
    rather than by every consumer re-deriving it from the JSON.
    """
    modules = _confidence_rows(result.modules, tier)
    symbols = _confidence_rows(result.symbols, tier)
    tests = _confidence_rows(result.tests, tier)
    outcome = result.outcome
    if outcome is not UnreachableCodeOutcome.ERROR:
        outcome = UnreachableCodeOutcome.FINDINGS if modules or symbols or tests else UnreachableCodeOutcome.CLEAN
    return UnreachableCodeResult(
        outcome=outcome,
        roots=result.roots,
        shipped_modules=result.shipped_modules,
        reachable_modules=result.reachable_modules,
        modules=modules,
        symbols=symbols,
        tests=tests,
        data_cleared=result.data_cleared,
        reason=result.reason,
    )


def _used_by(labels: tuple[str, ...]) -> str:
    return f"[used by: {', '.join(labels)}]" if labels else "[no use anywhere]"


def _capped[T](items: tuple[T, ...], *, full: bool, cap: int) -> tuple[tuple[T, ...], int]:
    shown = items if full else items[:cap]
    return shown, len(items) - len(shown)


def render_console_report(result: UnreachableCodeResult, *, full: bool = False, cap: int = _FINDING_CAP) -> str:
    """Render the operator-facing console report for `just report-product-reachability`."""
    out = [f"unreachable code: {result.headline()}"]
    if result.outcome is UnreachableCodeOutcome.ERROR:
        return out[0]
    out.append(f"  roots: {', '.join(result.roots)}")
    if result.data_cleared:
        out.append(f"  {result.data_cleared} data-shaped member(s) cleared by the shipped registry/locale payloads")
    if result.dev_cleared:
        out.append(f"  {result.dev_cleared} top-level symbol(s) cleared by a resolved reference from dev/ tooling")
    if result.outcome is UnreachableCodeOutcome.CLEAN:
        return "\n".join(out)

    sections = _console_finding_sections(result)
    for title, findings in sections:
        if not findings:
            continue
        out.append(f"  {title}:")
        shown, hidden = _capped(findings, full=full, cap=cap)
        for finding in shown:
            out.append(f"    {_render_finding(finding)}")
        if hidden:
            out.append(f"    ... {hidden} more (--full for all)")
    return "\n".join(out)


def _render_finding(finding: _Finding) -> str:
    if isinstance(finding, ModuleFinding):
        label = "package" if finding.is_package else "module"
        span = f"  ({finding.spanned_modules} modules)" if finding.spanned_modules > 1 else ""
        return f"{label:<8} {finding.path}{span}  {_used_by(finding.used_by)}"
    if isinstance(finding, TestFinding):
        return f"{finding.path}  exercises only: {', '.join(finding.subjects)}  [{finding.confidence.value}]"
    tier = f"  [{finding.confidence.value}]"
    return (
        f"{finding.path}:{finding.line}  {finding.kind.value:<11} {finding.qualname}  {_used_by(finding.used_by)}{tier}"
    )


def result_as_json(result: UnreachableCodeResult) -> str:
    """Serialise the result for machine consumers."""
    return json.dumps(
        {
            "outcome": result.outcome.value,
            "headline": result.headline(),
            "roots": list(result.roots),
            "shipped_modules": result.shipped_modules,
            "reachable_modules": result.reachable_modules,
            "data_cleared": result.data_cleared,
            "dev_cleared": result.dev_cleared,
            "exact_finding_ids": [finding.id for finding in result.exact_findings],
            "modules": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "module": f.module,
                    "reach": f.reach.value,
                    "spanned_modules": f.spanned_modules,
                    "used_by": list(f.used_by),
                    "importers": list(f.importers),
                }
                for f in result.modules
            ],
            "symbols": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "line": f.line,
                    "kind": f.kind.value,
                    "module": f.module,
                    "name": f.name,
                    "qualname": f.qualname,
                    "used_by": list(f.used_by),
                }
                for f in result.symbols
            ],
            "tests": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "module": f.module,
                    "subjects": list(f.subjects),
                }
                for f in result.tests
            ],
            "reason": result.reason,
        },
        indent=2,
        ensure_ascii=False,
    )


def _confidence_rows[T: (ModuleFinding, SymbolFinding, TestFinding)](
    findings: tuple[T, ...], tier: Confidence
) -> tuple[T, ...]:
    """Keep the typed finding family while selecting an exact confidence tier."""
    return tuple(finding for finding in findings if finding.confidence is tier)
