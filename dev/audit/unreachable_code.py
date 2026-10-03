"""Coordinate the read-only shipped module, symbol and orphan-test reachability audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError
from dev._paths import REPO_ROOT

from .unreachable_findings import _module_findings, _symbol_findings, _test_findings
from .unreachable_graph import _shipped_importers, _spawn_edges, module_edges, reachable_closure
from .unreachable_memo import shared_scan_memo
from .unreachable_models import Confidence, ShippedModule, UnreachableCodeOutcome, UnreachableCodeResult
from .unreachable_outside import _outside_use
from .unreachable_policy import _EXIT_ERROR, _EXIT_FINDINGS
from .unreachable_references import _data_tokens, _declared_data_values
from .unreachable_reporting import filter_by_confidence, render_console_report, result_as_json
from .unreachable_tree import EntryPoint, ShippedTreeSpec, shipped_modules


def _resolve_scan_roots(
    spec: ShippedTreeSpec, modules: dict[str, ShippedModule], companion_entries: tuple[EntryPoint, ...]
) -> tuple[tuple[str, ...], list[str]] | UnreachableCodeResult:
    """Resolve scan roots."""
    roots = (
        tuple(entry.spec for entry in spec.entry_points)
        + tuple(f"{module} (python -m)" for module in spec.module_roots)
        + tuple(f"{entry.spec} (workspace sibling)" for entry in companion_entries)
    )
    root_modules = (
        [entry.module for entry in spec.entry_points]
        + list(spec.module_roots)
        + [entry.module for entry in companion_entries]
    )
    missing = [module for module in root_modules if module not in modules]
    if missing:
        return UnreachableCodeResult.error(f"root module(s) absent from the shipped tree: {', '.join(missing)}")
    return roots, root_modules


def _resolve_scan_graph(
    spec: ShippedTreeSpec,
    modules: dict[str, ShippedModule],
    companion_entries: tuple[EntryPoint, ...],
    root_modules: list[str],
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str], dict[str, frozenset[str]]]:
    """Resolve scan graph."""
    known = frozenset(modules)
    edges = {name: module_edges(module, known) for name, module in modules.items()}
    spawned = {name: _spawn_edges(module, known) for name, module in modules.items()}
    runtime_edges = {name: runtime | spawned[name] for name, (runtime, _) in edges.items()}
    full_edges = {name: runtime | type_only | spawned[name] for name, (runtime, type_only) in edges.items()}
    script_reach = reachable_closure(
        [entry.module for entry in spec.entry_points] + [entry.module for entry in companion_entries],
        modules,
        runtime_edges,
    )
    runtime_reach = reachable_closure(root_modules, modules, runtime_edges)
    full_reach = reachable_closure(root_modules, modules, full_edges)
    return known, script_reach, runtime_reach, full_reach, full_edges


def scan_unreachable_code(spec: ShippedTreeSpec) -> UnreachableCodeResult:
    """Run the two-layer reachability scan over the tree ``spec`` describes."""
    with shared_scan_memo():
        return _scan_with_memo(spec)


def _scan_with_memo(spec: ShippedTreeSpec) -> UnreachableCodeResult:
    try:
        modules = shipped_modules(spec)
    except SyntaxError as exc:
        return UnreachableCodeResult.error(f"shipped module does not parse: {exc.filename}:{exc.lineno}: {exc.msg}")
    except OSError as exc:
        return UnreachableCodeResult.error(f"shipped tree could not be read ({exc})")
    if not modules:
        return UnreachableCodeResult.error(f"no shipped modules found under {spec.src_root / spec.package}")

    companion_entries = tuple(entry for companion in spec.companions for entry in companion.entry_points)
    root_result = _resolve_scan_roots(spec, modules, companion_entries)
    if isinstance(root_result, UnreachableCodeResult):
        return root_result
    roots, root_modules = root_result

    known, script_reach, runtime_reach, full_reach, full_edges = _resolve_scan_graph(
        spec, modules, companion_entries, root_modules
    )

    audited_names = _audited_module_names(spec, modules)
    audited_total = len(audited_names)
    outside = _outside_use(spec, known)
    data_tokens = _data_tokens(spec)
    declared_values = _declared_data_values(spec)
    shipped_importers = _shipped_importers(full_edges)
    module_findings = _module_findings(
        spec, modules, script_reach, runtime_reach, full_reach, outside, shipped_importers
    )
    symbol_findings, data_cleared, dev_cleared = _symbol_findings(
        spec, modules, runtime_reach, full_reach, outside, data_tokens, declared_values
    )

    if not module_findings and not symbol_findings:
        return UnreachableCodeResult.clean(
            roots=roots, shipped_modules=audited_total, reachable_modules=len(runtime_reach & audited_names)
        )
    return UnreachableCodeResult.from_findings(
        roots=roots,
        shipped_modules=audited_total,
        reachable_modules=len(runtime_reach & audited_names),
        modules=module_findings,
        symbols=symbol_findings,
        tests=_test_findings(spec, known, module_findings, symbol_findings),
        data_cleared=data_cleared,
        dev_cleared=dev_cleared,
    )


def run_unreachable_code_scan(
    repo_root: Path = REPO_ROOT, *, extra_roots: tuple[str, ...] = ()
) -> UnreachableCodeResult:
    """Scan this repository's shipped tree from its declared console scripts.

    The one entry point ``just report-product-reachability`` calls.
    """
    try:
        spec = ShippedTreeSpec.from_repository(repo_root, extra_roots=extra_roots)
    except (OSError, KeyError, ValueError, TomlDecodeError) as exc:
        return UnreachableCodeResult.error(f"packaging config unreadable ({exc})")
    return scan_unreachable_code(spec)


def main() -> int:
    """Run the scan and print the report; exit 3 on findings, 1 on error, 0 when clean."""
    parser = argparse.ArgumentParser(description="Audit shipped code no console-script entrypoint can reach.")
    parser.add_argument("--full", action="store_true", help="List every finding, uncapped.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="MODULE:ATTR",
        help="Add a root the packaging does not declare (a python -m surface, for example). Repeatable.",
    )
    parser.add_argument(
        "--confidence",
        choices=[tier.value for tier in Confidence],
        help="Report only findings derived at this tier; 'exact' is the campaign-ready set.",
    )
    args = parser.parse_args()

    result = run_unreachable_code_scan(REPO_ROOT, extra_roots=tuple(args.root))
    if args.confidence is not None:
        result = filter_by_confidence(result, Confidence(args.confidence))
    print(result_as_json(result) if args.json else render_console_report(result, full=args.full))

    if result.outcome is UnreachableCodeOutcome.ERROR:
        return _EXIT_ERROR
    if result.outcome is UnreachableCodeOutcome.FINDINGS:
        return _EXIT_FINDINGS
    return 0


def _audited_module_names(spec: ShippedTreeSpec, modules: dict[str, ShippedModule]) -> frozenset[str]:
    """Keep the audited package denominator separate from workspace consumers."""
    return frozenset(name for name in modules if name == spec.package or name.startswith(spec.package + "."))


if __name__ == "__main__":
    sys.exit(main())
