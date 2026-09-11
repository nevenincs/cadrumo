"""Read-only status facts for the complete bundled registry lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority_artifact_path

from ..conformance.cli import load_bundled_runtime_authority, validate_registry
from ..maintenance_support import OracleEnvironment
from ..parity.maintenance import audit_registry_oracles
from ..pipeline.authority_publication import AuthorityArtifactCurrencyStatus, authority_artifact_currency

_TARGET_STATE_NAMES: Final[tuple[str, ...]] = ("current", "stale", "drifted", "never-committed", "unreadable")


@dataclass(frozen=True, slots=True)
class RegistryStatus:
    """All lifecycle axes observed by the report; collecting it never mutates data."""

    valid: bool
    oracles: bool
    targets: tuple[tuple[str, int], ...]
    target_findings: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]
    authority: str
    authority_recorded_digest: str | None
    authority_candidate_digest: str | None
    loadable: bool
    details: tuple[str, ...]


def collect_registry_status(
    *,
    registry_root: Path | None = None,
    source_root: Path | None = None,
    authority_artifact: Path | None = None,
) -> RegistryStatus:
    """Delegate each status axis to its owning validator or currency primitive."""
    resolved_registry_root = registry_root or bundled_path("registry", "aeat")
    resolved_source_root = source_root or bundled_path()
    resolved_artifact = authority_artifact or bundled_authority_artifact_path()
    details: list[str] = []

    authority = None
    try:
        authority = validate_registry(registry_root=resolved_registry_root, source_root=resolved_source_root)
        valid = True
    except Exception as error:
        valid = False
        details.append(f"VALID: {type(error).__name__}: {error}")

    try:
        oracle_report = audit_registry_oracles(
            resolved_registry_root,
            environment=OracleEnvironment.PRODUCTION,
        )
        oracles = not oracle_report.failures
        if not oracles:
            details.append(f"ORACLES: {', '.join(oracle_report.failures)}")
    except Exception as error:
        oracles = False
        details.append(f"ORACLES: {type(error).__name__}: {error}")

    if authority is None:
        targets = Counter({"unreadable": 1})
        target_findings = (("unreadable", (("unknown", "unknown", "whole-registry validity failed"),)),)
        details.append("TARGETS: unavailable because whole-registry validity failed")
    else:
        try:
            from .generated_tree_state import generated_state_inventory

            states, excluded = generated_state_inventory(
                authority,
                tuple(str(modelo.id) for modelo in authority.modelos),
            )
            expected_target_count = sum(len(modelo.revisions) for modelo in authority.modelos)
            excluded_target_count = max(0, expected_target_count - len(states))
            targets = Counter(
                {
                    "current": sum(item.state == "reproducible" for item in states),
                    "stale": sum(item.state == "manifest_only_stale" for item in states),
                    "drifted": sum(item.state == "record_drift" for item in states),
                    "never-committed": sum(item.state == "never_committed" for item in states),
                    "unreadable": excluded_target_count,
                }
            )
            if excluded_target_count:
                details.append(f"TARGETS: {excluded_target_count} target(s) were excluded by the generated-state owner")
            grouped_findings: dict[str, list[tuple[str, str, str]]] = {
                "stale": [],
                "drifted": [],
                "never-committed": [],
                "unreadable": list(excluded),
            }
            state_names = {
                "manifest_only_stale": "stale",
                "record_drift": "drifted",
                "never_committed": "never-committed",
            }
            for item in states:
                projected_state = state_names.get(item.state)
                if projected_state is not None:
                    grouped_findings[projected_state].append((item.modelo, item.revision, item.detail))
            target_findings = tuple((state, tuple(grouped_findings[state])) for state in grouped_findings)
        except Exception as error:
            targets = Counter({"unreadable": 1})
            target_findings = (("unreadable", (("unknown", "unknown", str(error)),)),)
            details.append(f"TARGETS: {type(error).__name__}: {error}")

    recorded_digest: str | None = None
    candidate_digest: str | None = None
    try:
        currency = authority_artifact_currency(
            resolved_artifact,
            registry_root=resolved_registry_root,
            source_root=resolved_source_root,
        )
        authority_status = currency.status.value
        recorded_digest = currency.recorded_identity_digest
        candidate_digest = currency.candidate_identity_digest
        if currency.status is not AuthorityArtifactCurrencyStatus.CURRENT:
            details.append(f"AUTHORITY: {currency.detail}")
    except Exception as error:
        authority_status = AuthorityArtifactCurrencyStatus.UNREADABLE.value
        details.append(f"AUTHORITY: {type(error).__name__}: {error}")

    try:
        load_bundled_runtime_authority()
        loadable = True
    except Exception as error:
        loadable = False
        details.append(f"LOADABLE: {type(error).__name__}: {error}")

    return RegistryStatus(
        valid=valid,
        oracles=oracles,
        targets=tuple((state, targets[state]) for state in _TARGET_STATE_NAMES),
        target_findings=target_findings,
        authority=authority_status,
        authority_recorded_digest=recorded_digest,
        authority_candidate_digest=candidate_digest,
        loadable=loadable,
        details=tuple(details),
    )


def _payload(status: RegistryStatus, *, blocking: bool) -> dict[str, object]:
    target_counts = dict(status.targets)
    blocking_target_count = sum(target_counts[state] for state in ("stale", "drifted", "never-committed"))
    lanes = {
        "authority_currency": (
            "passed" if status.authority == AuthorityArtifactCurrencyStatus.CURRENT.value else "failed"
        ),
        "oracle_bindings": "passed" if status.oracles else "failed",
        "registry_validity": "passed" if status.valid else "failed",
        "runtime_loadability": "passed" if status.loadable else "failed",
        "target_currentness": "passed" if blocking_target_count == 0 else "failed",
        "target_coverage": "partial" if target_counts["unreadable"] else "passed",
    }
    failed_lanes = sorted(lane for lane, state in lanes.items() if state == "failed")
    partial_lanes = sorted(lane for lane, state in lanes.items() if state == "partial")
    target_overview: dict[str, object] = {}
    for state, findings in status.target_findings:
        if not findings:
            continue
        sample_limit = 5 if state == "unreadable" else 10
        reason_counts: dict[str, int] = {}
        if state == "unreadable":
            for _, _, detail in findings:
                if "declares no export layout" in detail:
                    reason = "no_export_layout"
                elif "cites no record-design source" in detail:
                    reason = "no_record_design_source"
                elif "has no authored inputs" in detail:
                    reason = "missing_authored_inputs"
                else:
                    reason = "other"
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        target_overview[state] = {
            "count": len(findings),
            "affected_modelos": sorted({modelo for modelo, _, _ in findings}),
            "sample_targets": [
                {"modelo": modelo, "revision": revision, "detail": detail}
                for modelo, revision, detail in findings[:sample_limit]
            ],
            "targets_omitted": max(0, len(findings) - sample_limit),
            **({"reason_counts": dict(sorted(reason_counts.items()))} if reason_counts else {}),
        }
    actions: list[dict[str, object]] = []
    if status.authority != AuthorityArtifactCurrencyStatus.CURRENT.value:
        actions.append(
            {
                "code": "authority_not_current",
                "command": "just registry-publish-authority",
                "detail": "Publish the validated authority after reviewing the authored registry changes.",
            }
        )
    action_by_state = {
        "stale": ("review_then_republish_target", "Review the generated diff, then use registry-republish-target."),
        "drifted": ("investigate_record_drift", "Investigate record-byte drift; do not republish blindly."),
        "never-committed": ("publish_target", "Review and publish the missing generated target."),
    }
    for state, findings in status.target_findings:
        if state not in action_by_state:
            continue
        code, detail = action_by_state[state]
        for modelo, revision, _ in findings:
            actions.append({"code": code, "modelo": modelo, "revision": revision, "detail": detail})
    return {
        "schema_version": 1,
        "command": "check-registry" if blocking else "report-registry-status",
        "posture": "blocking" if blocking else "advisory",
        "result": "passed" if not failed_lanes else "failed",
        "classification": "clean" if not failed_lanes else "registry_findings",
        "headline": (
            "Registry health passed across all lifecycle lanes."
            if not failed_lanes
            else f"Registry health found {len(failed_lanes)} failing lifecycle lane(s)."
        ),
        "summary": {
            "lanes_total": len(lanes),
            "lanes_passed": len(lanes) - len(failed_lanes) - len(partial_lanes),
            "lanes_failed": len(failed_lanes),
            "lanes_partial": len(partial_lanes),
            "details_total": len(status.details),
        },
        "lanes": dict(sorted(lanes.items())),
        "failed_lanes": failed_lanes,
        "partial_lanes": partial_lanes,
        "targets": target_counts,
        "target_findings": target_overview,
        "authority": {
            "status": status.authority,
            "recorded_identity_digest": status.authority_recorded_digest,
            "candidate_identity_digest": status.authority_candidate_digest,
        },
        "details": list(status.details),
        "actions": actions,
    }


def main(argv: list[str] | None = None) -> int:
    """Print lifecycle facts without publishing, repairing, or regenerating artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the status payload as JSON")
    parser.add_argument("--check", action="store_true", help="exit non-zero when any lifecycle lane fails")
    args = parser.parse_args(argv)
    status = collect_registry_status()
    payload = _payload(status, blocking=args.check)
    if args.json:
        for state, findings in status.target_findings:
            for modelo, revision, detail in findings:
                print(
                    f"TARGET_DETAIL\tstate={state}\tmodelo={modelo}\trevision={revision}\tdetail={detail}",
                    file=sys.stderr,
                )
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 1 if args.check and payload["result"] == "failed" else 0

    print("report-registry-status\tposture=report-only; exit_status=0")
    print(f"VALID\t{'pass' if status.valid else 'fail'}")
    print(f"ORACLES\t{'pass' if status.oracles else 'fail'}")
    target_values = " ".join(f"{state}={count}" for state, count in status.targets)
    print(f"TARGETS\t{target_values or 'unreadable=1'}")
    print(f"AUTHORITY\t{status.authority}")
    print(f"LOADABLE\t{'pass' if status.loadable else 'fail'}")
    for detail in status.details:
        print(f"DETAIL\t{detail}")
    return 1 if args.check and payload["result"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RegistryStatus", "collect_registry_status", "main"]
