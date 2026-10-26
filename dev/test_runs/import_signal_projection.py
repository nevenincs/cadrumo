"""Project import contract path overlap, diagnostic amplification and remediation evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from dev.first_party_source import is_test_module_name

from .signal_values import _top

_REMEDIATION_CODE_FAMILIES: Final[dict[str, frozenset[str]]] = {
    "canonical_import_surface": frozenset(
        {"CANONICAL_TARGET_MISSING", "FORWARDING_MODULE", "PACKAGE_FACADE", "REEXPORT_OR_ALIAS"}
    ),
    "dynamic_or_raw_target": frozenset(
        {
            "DYNAMIC_TARGET_UNRESOLVED",
            "RAW_FIRST_PARTY_IMPORT",
            "STATIC_TARGET_UNRESOLVED",
            "UNRESOLVED_DYNAMIC_TARGET",
        }
    ),
    "initializer_hygiene": frozenset({"ACTIVE_INITIALIZER"}),
    "private_encapsulation": frozenset({"PRIVATE_CROSS_PACKAGE"}),
}


@dataclass(frozen=True)
class _ContractPath:
    """One normalized dependency path reported under one forbidden edge."""

    forbidden_from: str
    forbidden_to: str
    normalized: str
    edges: tuple[tuple[str, str], ...]


def _module_is_test_scoped(module: str) -> bool:
    """Classify module names using explicit test-path naming conventions only."""
    parts = module.split(".")
    return (
        is_test_module_name(module) or parts[0] == "test_support" or parts[-1].endswith(("_test_support", "_fixture"))
    )


def _contract_path_deductions(self: _ImportBoundariesProcessor) -> dict[str, object]:
    """Reduce broken-contract paths without treating overlapping contracts as new imports."""
    self._finish_contract_path()
    path_multiplicity = Counter(path.normalized for path in self._contract_paths)
    lanes: defaultdict[tuple[str, str], list[_ContractPath]] = defaultdict(list)
    for path in self._contract_paths:
        lanes[(path.forbidden_from, path.forbidden_to)].append(path)
    by_forbidden_edge: dict[str, object] = {}
    for (forbidden_from, forbidden_to), paths in sorted(lanes.items()):
        by_forbidden_edge[f"{forbidden_from} -> {forbidden_to}"] = _forbidden_edge_impact(paths)
    repeated = [count for count in path_multiplicity.values() if count > 1]
    return {
        "by_forbidden_edge": by_forbidden_edge,
        "classification": "test_scoped uses module naming conventions; non_test_scoped is its complement",
        "maximum_contract_multiplicity": max(path_multiplicity.values(), default=0),
        "overlapping_unique_paths": len(repeated),
        "reported_paths": len(self._contract_paths),
        "reports_for_overlapping_paths": sum(repeated),
        "unique_dependency_paths": len(path_multiplicity),
    }


def _diagnostic_deductions(self: _ImportBoundariesProcessor) -> dict[str, object]:
    """Expose finding amplification and recurring diagnostic surfaces."""
    by_code: dict[str, object] = {}
    for code, findings in sorted(self.diagnostics.items()):
        test_scoped = self._diagnostic_test_scoped[code]
        by_code[code] = {
            "files": len(self._diagnostic_files_by_code[code]),
            "findings": findings,
            "locations": len(self._diagnostic_locations_by_code[code]),
            "non_test_scoped_findings": findings - test_scoped,
            "test_scoped_findings": test_scoped,
            "top_targets": _top(self._diagnostic_targets[code]),
        }
    multi_locations = Counter({location: count for location, count in self._diagnostic_locations.items() if count > 1})
    top_locations = []
    for item in _top(self._diagnostic_locations):
        location = str(item["value"])
        top_locations.append(
            {
                **item,
                "by_code": dict(sorted(self._diagnostic_location_codes[location].items())),
            }
        )
    return {
        "amplification": {
            "files": len(self._diagnostic_files),
            "findings": sum(self.diagnostics.values()),
            "findings_at_multi_finding_locations": sum(multi_locations.values()),
            "locations": len(self._diagnostic_locations),
            "locations_with_multiple_findings": len(multi_locations),
            "maximum_findings_at_one_location": max(self._diagnostic_locations.values(), default=0),
        },
        "by_code": by_code,
        "classification": "test_scoped uses path naming conventions; non_test_scoped is its complement",
        "top_locations": top_locations,
    }


def _remediation_lanes(self: _ImportBoundariesProcessor) -> dict[str, object]:
    """Group diagnostic codes by the import defect they describe."""
    lanes: dict[str, object] = {}
    for lane, codes in sorted(_REMEDIATION_CODE_FAMILIES.items()):
        active_codes = sorted(code for code in codes if self.diagnostics[code])
        findings = sum(self.diagnostics[code] for code in active_codes)
        locations = set().union(*(self._diagnostic_locations_by_code[code] for code in active_codes))
        test_scoped = sum(self._diagnostic_test_scoped[code] for code in active_codes)
        lanes[lane] = {
            "codes": active_codes,
            "findings": findings,
            "locations": len(locations),
            "non_test_scoped_findings": findings - test_scoped,
            "test_scoped_findings": test_scoped,
        }
    return lanes


def _forbidden_edge_impact(paths: list[_ContractPath]) -> dict[str, object]:
    """Count each forbidden edge span without multiplying a shared dependency path."""
    sources = Counter(path.edges[0][0] for path in paths)
    terminals = Counter(path.edges[-1][1] for path in paths)
    bridges: Counter[str] = Counter()
    for path in paths:
        bridges.update(target for _, target in path.edges[:-1])
    test_scoped = sum(_module_is_test_scoped(path.edges[0][0]) for path in paths)
    return {
        "direct_paths": sum(len(path.edges) == 1 for path in paths),
        "non_test_scoped_paths": len(paths) - test_scoped,
        "reported_paths": len(paths),
        "test_scoped_paths": test_scoped,
        "top_bridge_modules": _top(bridges, minimum_count=2),
        "top_source_modules": _top(sources, minimum_count=2),
        "top_terminal_modules": _top(terminals, minimum_count=2),
        "transitive_paths": sum(len(path.edges) > 1 for path in paths),
        "unique_source_modules": len({path.edges[0][0] for path in paths}),
        "unique_terminal_modules": len(terminals),
    }


if TYPE_CHECKING:
    from .import_boundaries_signal import _ImportBoundariesProcessor
