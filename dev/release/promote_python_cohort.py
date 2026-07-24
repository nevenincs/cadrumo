"""Validate a tested Python cohort and emit exact publication artifact paths."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Final, cast

from dev.packaging.installed_tax_oracle import (
    EXPECTED_FORMULA,
    EXPECTED_LEGAL_REF,
    EXPECTED_SOURCE_REF,
    EXPECTED_VALUE,
    TARGET_CASILLA,
)
from dev.packaging.python_cohort import PythonCohort, load_python_cohort

_UTF_8: Final[str] = "utf-8"
_PYPI_PROJECTS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)


def _evidence_document(evidence_file: Path, cohort: PythonCohort) -> dict[str, Any]:
    expected = evidence_file.resolve(strict=True)
    if expected.name != "evidence.json" or expected.parent.name != cohort.source_commit:
        raise SystemExit(
            f"installed cohort evidence path is not bound to {cohort.source_commit}: {expected}",
        )
    document = json.loads(expected.read_text(encoding=_UTF_8))
    if not isinstance(document, dict):
        raise SystemExit("installed cohort evidence must be a JSON object")
    expected_hashes = {
        "cadrumo": cohort.sha256["cadrumo"],
        "cadrumo-data-manuals": cohort.sha256["cadrumo-data-manuals"],
        "cadrumo-data-official": cohort.sha256["cadrumo-data-official"],
    }
    if document.get("source_commit") != cohort.source_commit:
        raise SystemExit("installed evidence source commit does not match the cohort")
    if document.get("artifact_sha256") != expected_hashes:
        raise SystemExit(
            f"installed evidence artifact digests do not match the cohort: {document.get('artifact_sha256')!r}",
        )
    return document


def _assert_oracle(evidence: object, *, transport: str) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise SystemExit(f"{transport} installed oracle evidence is missing")
    document = cast("dict[str, Any]", evidence)
    if document.get("target_casilla") != TARGET_CASILLA:
        raise SystemExit(f"{transport} target casilla drifted: {document!r}")
    if document.get("target_value") != str(EXPECTED_VALUE):
        raise SystemExit(f"{transport} target value drifted: {document!r}")
    if document.get("formula_id") != EXPECTED_FORMULA:
        raise SystemExit(f"{transport} formula id drifted: {document!r}")
    legal_refs = document.get("legal_refs")
    source_refs = document.get("source_refs")
    if not isinstance(legal_refs, list) or EXPECTED_LEGAL_REF not in legal_refs:
        raise SystemExit(f"{transport} legal grounding is incomplete")
    if not isinstance(source_refs, list) or EXPECTED_SOURCE_REF not in source_refs:
        raise SystemExit(f"{transport} source grounding is incomplete")
    return document


def validate_promotion(
    cohort_dir: Path,
    evidence_file: Path,
    *,
    expected_source_commit: str,
) -> PythonCohort:
    """Require exact cohort digests plus complete CLI and MCP installed evidence."""
    cohort = load_python_cohort(cohort_dir)
    if cohort.source_commit != expected_source_commit:
        raise SystemExit(
            f"cohort source {cohort.source_commit} != packaging run source {expected_source_commit}",
        )
    evidence = _evidence_document(evidence_file, cohort)
    cli = _assert_oracle(evidence.get("cli_oracle"), transport="CLI")
    mcp = _assert_oracle(evidence.get("mcp_oracle"), transport="MCP")
    if cli.get("legal_refs") != mcp.get("legal_refs"):
        raise SystemExit("CLI and MCP legal grounding differs")
    if cli.get("source_refs") != mcp.get("source_refs"):
        raise SystemExit("CLI and MCP source grounding differs")
    invoked_cli = mcp.get("invoked_cli_sha256")
    invoked_by_command = mcp.get("invoked_cli_sha256_by_command")
    if not isinstance(invoked_cli, str) or len(invoked_cli) != 64:
        raise SystemExit("MCP evidence lacks the child executable attestation")
    if not isinstance(invoked_by_command, dict) or set(invoked_by_command.values()) != {invoked_cli}:
        raise SystemExit("MCP child executable attestations are incomplete or divergent")
    return cohort


def _write_outputs(path: Path, cohort: PythonCohort) -> None:
    rows = {
        "manuals_sdist": cohort.manuals_sdist,
        "manuals_wheel": cohort.manuals_wheel,
        "official_sdist": cohort.official_sdist,
        "official_wheel": cohort.official_wheel,
        "root_sdist": cohort.root_sdist,
        "root_wheel": cohort.root_wheel,
        "source_commit": cohort.source_commit,
        "version": cohort.version,
    }
    with path.open("a", encoding=_UTF_8) as handle:
        for name, value in rows.items():
            handle.write(f"{name}={value}\n")


def assert_pypi_destinations_absent(cohort: PythonCohort) -> None:
    """Fail before upload when any destination already owns the cohort version."""
    for project in _PYPI_PROJECTS:
        url = f"https://pypi.org/pypi/{project}/{cohort.version}/json"
        request = urllib.request.Request(  # fixed HTTPS PyPI endpoint.
            url,
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                response.read(1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise SystemExit(
                f"PyPI destination check failed for {project}: HTTP {exc.code}",
            ) from exc
        except urllib.error.URLError as exc:
            raise SystemExit(
                f"PyPI destination check failed for {project}: {exc.reason}",
            ) from exc
        raise SystemExit(
            f"PyPI already contains {project} {cohort.version}; refusing overwrite",
        )


def main() -> int:
    """Validate retained promotion evidence and emit exact artifact paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--check-pypi", action="store_true")
    # The immutable release cohort's installed behaviour is proven per-OS by the
    # DistributionEvidence rows (readiness gate), not by this per-OS-smoke-build
    # evidence, so the publish path re-points here for ONLY the pre-upload PyPI
    # destination guard + the version/path outputs, skipping the smoke-build
    # evidence binding that does not apply to the sealed cohort's bytes.
    parser.add_argument("--check-pypi-only", action="store_true")
    args = parser.parse_args()
    if args.check_pypi_only:
        cohort = load_python_cohort(args.cohort_dir)
        assert_pypi_destinations_absent(cohort)
        if args.github_output is not None:
            _write_outputs(args.github_output, cohort)
        print(json.dumps({"version": cohort.version, "source_commit": cohort.source_commit}, sort_keys=True))
        return 0
    if args.evidence_file is None or args.expected_source_commit is None:
        raise SystemExit("--evidence-file and --expected-source-commit are required unless --check-pypi-only")
    cohort = validate_promotion(
        args.cohort_dir,
        args.evidence_file,
        expected_source_commit=args.expected_source_commit,
    )
    if args.check_pypi:
        assert_pypi_destinations_absent(cohort)
    if args.github_output is not None:
        _write_outputs(args.github_output, cohort)
    print(
        json.dumps(
            {
                "sha256": cohort.sha256,
                "source_commit": cohort.source_commit,
                "version": cohort.version,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
