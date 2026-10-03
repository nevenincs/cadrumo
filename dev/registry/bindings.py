"""Measure authored and executable binding-route signal without running tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dev.registry.binding_signal.common import required_mapping, stable_dump
from dev.registry.binding_signal.consumer_audit import audit_consumers
from dev.registry.binding_signal.report import blocking_findings, build_report, summary
from dev.registry.binding_signal.revision_audit import audit_revisions
from dev.registry.binding_signal.sources import collect_inputs


def audit(root: Path) -> dict[str, object]:
    """Return the complete advisory binding inventory and reverse-route signal."""
    from dev.registry.identifier_edition import edition_token_in_identifier

    inputs = collect_inputs(root)
    revisions = audit_revisions(inputs, edition_token_in_identifier)
    consumers = audit_consumers(inputs, revisions)
    return build_report(inputs, revisions, consumers)


def main() -> int:
    """Measure bindings, persist the detailed artifact, and print one summary envelope."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR", ".tmp")) / "binding-signal.json",
        help="Detailed JSON destination; the just command overrides this with its run artifact path.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when actionable error findings exist; default findings are advisory.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        payload = audit(root)
        stable_dump(output, payload)
        report_summary = summary(payload, output)
        print(json.dumps(report_summary, ensure_ascii=False, sort_keys=True))
        summary_data = required_mapping(payload["summary"], context="audit summary")
        processing_error = summary_data["classification"] == "processing_error"
        actionable_errors = bool(blocking_findings(payload))
        if processing_error:
            return 2
        if args.strict and actionable_errors:
            return 1
        return 0
    except Exception as exc:
        failure = {
            "schema_version": "binding-signal-summary.v3",
            "output": output.resolve().as_posix(),
            "summary": {
                "classification": "processing_error",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            },
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
