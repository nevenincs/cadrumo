"""Import retirement evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, cast


def _retirement_matrix(raw: dict[str, object]) -> dict[str, object] | Literal[False]:
    """Retirement matrix."""
    required = ("composition_proof", "evidence_digest", "verified_at")
    if any(not isinstance(raw.get(key), str) or not str(raw[key]).strip() for key in required):
        return False
    matrix = raw.get("capability_matrix")
    if not isinstance(matrix, dict) or not matrix:
        return False
    matrix = cast("dict[str, object]", matrix)
    if not all(value in {"required", "optional", "unsupported"} for value in matrix.values()):
        return False
    return matrix


def _valid_composition_report(report: object, capability: str, matrix: dict[str, object]) -> bool:
    """Valid composition report."""
    if not isinstance(report, dict):
        return False
    report = cast("dict[str, object]", report)
    if (
        report.get("schema_version") != 1
        or report.get("event") != "composition_integrity"
        or report.get("verdict") != "clean"
        or report.get("capability") != capability
        or report.get("capability_matrix") != matrix
    ):
        return False
    if not _valid_entrypoint_statuses(report, matrix):
        return False
    return _valid_vertical_slice_checks(report)


def is_source_module_removal(raw: object) -> bool:
    """Recognise the retirement record that claims the entry's source module was deleted.

    The claim is only a shape here; the reconciler proves it against the live
    authority tree on every run, so a returning module invalidates it.
    """
    if (
        not isinstance(raw, dict)
        or set(cast("dict[str, object]", raw)) != {"kind", "verified_at"}
        or raw["kind"] != "source_module_removed"
    ):
        return False
    raw = cast("dict[str, object]", raw)
    verified_at = raw["verified_at"]
    if not isinstance(verified_at, str):
        return False
    try:
        datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def valid_retirement(raw: object, repository: Path, capability: str) -> bool:
    """Verify a digest-bound clean report from the separate composition signal."""
    if not isinstance(raw, dict):
        return False
    raw = cast("dict[str, object]", raw)
    matrix = _retirement_matrix(raw)
    if matrix is False:
        return False
    try:
        datetime.fromisoformat(str(raw["verified_at"]).replace("Z", "+00:00"))
        proof = (repository / str(raw["composition_proof"])).resolve()
        proof.relative_to(repository.resolve())
        content = proof.read_bytes()
        if hashlib.sha256(content).hexdigest() != raw["evidence_digest"]:
            return False
        report = json.loads(content)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return _valid_composition_report(report, capability, matrix)


def _valid_vertical_slice_checks(report: dict[str, object]) -> bool:
    """Valid vertical slice checks."""
    checks = report.get("vertical_slice_checks")
    required_checks = {
        "application_has_no_concrete_adapter_import",
        "capability_port_owned_inward",
        "port_is_capability_level",
        "dependency_required_at_use_case_boundary",
        "dependency_propagates_internally",
        "no_concrete_infrastructure_default",
        "no_global_service_locator",
        "applicable_entrypoints_bind_implementation",
        "unsupported_entrypoints_declared",
        "adapter_dtos_and_errors_stay_outward",
        "integration_tests_live_at_outer_seam",
        "real_binding_composition_proof",
    }
    return (
        isinstance(checks, dict)
        and set(cast("dict[str, object]", checks)) == required_checks
        and all(cast("dict[str, object]", checks).values())
    )


def _valid_entrypoint_statuses(report: dict[str, object], matrix: dict[str, object]) -> bool:
    """Valid entrypoint statuses."""
    entrypoints = report.get("entrypoints")
    if not isinstance(entrypoints, dict) or set(cast("dict[str, object]", entrypoints)) != set(matrix):
        return False
    entrypoints = cast("dict[str, object]", entrypoints)
    for entrypoint, applicability in matrix.items():
        expected = "unsupported" if applicability == "unsupported" else "verified"
        if entrypoints.get(entrypoint) != expected:
            return False
    return True
