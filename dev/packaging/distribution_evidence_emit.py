"""Emit cohort-bound evidence for installed Cadrumo CLI artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ._command import CommandResult
from ._hashing import sha256_path
from ._installed_wheel_binding import installed_wheel_payload_sha256, sealed_wheel_payload_sha256
from .cohort_manifest import LoadedReleaseCohort
from .evidence import (
    AcquisitionIdentity,
    CommandTranscript,
    DestinationIdentity,
    DistributionEvidence,
    EvidenceStatus,
    ExecutionIsolation,
    InstalledExecutableIdentity,
    ResultIdentity,
    create_distribution_evidence,
    current_runtime_identity,
    write_distribution_evidence,
)
from .evidence_scrub import scrub_distribution_evidence
from .installed_tax_oracle import InstalledTaxEvidence


class EvidenceCohortBindingError(RuntimeError):
    """Raised when an oracle capture is not bound to its release cohort."""


def _command_transcript(command: CommandResult) -> CommandTranscript:
    summary = f"{Path(command.argv[0]).name} exit={command.returncode} ({command.duration_seconds}s)"
    version = [line for line in command.stdout.strip().splitlines()[:1] if line] if "--version" in command.argv else []
    return CommandTranscript.from_result(command, relevant_output=(*version, summary))


def _assert_oracle_bound_to_cohort(*, cohort: LoadedReleaseCohort, tax_evidence: InstalledTaxEvidence) -> None:
    version = cohort.manifest.version
    if not re.search(rf"(?<![\w.]){re.escape(version)}(?![\w.])", tax_evidence.version_output):
        raise EvidenceCohortBindingError(f"installed CLI output does not carry cohort version {version!r}")
    records = {record.name: record for record in cohort.manifest.artifacts}
    expected = (
        cohort.manifest.source.commit,
        records["python-cohort-manifest"].sha256,
        records["cadrumo-wheel"].sha256,
    )
    observed = (
        tax_evidence.cohort_source_commit,
        tax_evidence.cohort_manifest_sha256,
        tax_evidence.cohort_root_wheel_sha256,
    )
    if observed != expected:
        raise EvidenceCohortBindingError(
            f"installed oracle cohort provenance mismatch: expected {expected!r}, got {observed!r}"
        )
    executable = Path(tax_evidence.resolved_executable).resolve(strict=True)
    if sha256_path(executable) != tax_evidence.executable_sha256:
        raise EvidenceCohortBindingError("installed oracle executable digest mismatch")
    payload = sealed_wheel_payload_sha256(cohort.artifact("cadrumo-wheel"))
    if tax_evidence.installed_wheel_payload_sha256 != payload or installed_wheel_payload_sha256(executable) != payload:
        raise EvidenceCohortBindingError("installed cadrumo payload does not match the sealed root wheel")


def build_installed_oracle_evidence(
    *,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    observed_at: datetime | None = None,
) -> DistributionEvidence:
    """Build evidence for a Python, Homebrew, or Scoop CLI installation."""
    _assert_oracle_bound_to_cohort(cohort=cohort, tax_evidence=tax_evidence)
    executable = Path(tax_evidence.resolved_executable).resolve(strict=True)
    isolation = ExecutionIsolation(
        checkout_imports_removed=tax_evidence.checkout_imports_removed,
        ambient_product_executables_removed=tax_evidence.ambient_product_executables_removed,
        installed_executables=(
            InstalledExecutableIdentity(name="aeat", path=str(executable), sha256=sha256_path(executable)),
        ),
    )
    cli = {key: value for key, value in tax_evidence.to_jsonable().items() if key != "commands"}
    evidence = create_distribution_evidence(
        row_id=row_id,
        cohort=cohort,
        runtime=current_runtime_identity(),
        client=None,
        isolation=isolation,
        acquisition=acquisition,
        commands=tuple(_command_transcript(item) for item in tax_evidence.commands),
        result=ResultIdentity(
            status=EvidenceStatus.PASSED,
            assertions=(
                f"installed CLI computed {tax_evidence.target_casilla}={tax_evidence.target_value} "
                f"via {tax_evidence.formula_id}",
                "every persisted observation carried legal and source grounding",
            ),
            observations={"cli_oracle": cli},
        ),
        observed_at=observed_at or datetime.now(UTC),
        destination=destination,
    )
    return scrub_distribution_evidence(evidence)


def emit_installed_oracle_evidence(
    *,
    directory: Path,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    observed_at: datetime | None = None,
) -> Path:
    """Build and persist one installed-CLI evidence record."""
    return write_distribution_evidence(
        directory,
        build_installed_oracle_evidence(
            row_id=row_id,
            cohort=cohort,
            tax_evidence=tax_evidence,
            acquisition=acquisition,
            destination=destination,
            observed_at=observed_at,
        ),
    )


def _tax_evidence_from_mapping(data: dict[str, Any]) -> InstalledTaxEvidence:
    missing = [key for key in ("checkout_imports_removed", "ambient_product_executables_removed") if key not in data]
    if missing:
        raise EvidenceCohortBindingError(
            f"installed CLI oracle JSON is missing isolation field(s) {missing}; recapture it"
        )
    commands = tuple(
        CommandResult(
            argv=tuple(item["argv"]),
            cwd=item["cwd"],
            started_at=datetime.fromisoformat(item["started_at"]),
            completed_at=datetime.fromisoformat(item["completed_at"]),
            duration_seconds=item["duration_seconds"],
            returncode=item["returncode"],
            stdout=item["stdout"],
            stderr=item["stderr"],
        )
        for item in data["commands"]
    )
    fields = {key: value for key, value in data.items() if key != "commands"}
    for key in ("legal_refs", "source_refs", "notice_codes"):
        fields[key] = tuple(fields[key])
    return InstalledTaxEvidence(**fields, commands=commands)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("row-id", "acquisition-mechanism", "acquisition-source", "destination-kind", "destination-locator"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--release-cohort-dir", required=True, type=Path)
    parser.add_argument("--tax-evidence", required=True, type=Path)
    parser.add_argument("--distribution-evidence-dir", type=Path, default=Path("var/distribution-install-readiness"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Emit an installed-CLI evidence record from retained oracle JSON."""
    from .cohort_manifest import load_release_cohort

    args = _parser().parse_args(argv)
    cohort = load_release_cohort(args.release_cohort_dir)
    path = emit_installed_oracle_evidence(
        directory=args.distribution_evidence_dir,
        row_id=args.row_id,
        cohort=cohort,
        tax_evidence=_tax_evidence_from_mapping(json.loads(args.tax_evidence.read_text(encoding="utf-8"))),
        acquisition=AcquisitionIdentity(mechanism=args.acquisition_mechanism, source=args.acquisition_source),
        destination=DestinationIdentity(
            kind=args.destination_kind, locator=args.destination_locator, version=cohort.manifest.version
        ),
    )
    print(path)
    return 0


__all__ = ["EvidenceCohortBindingError", "build_installed_oracle_evidence", "emit_installed_oracle_evidence", "main"]
if __name__ == "__main__":
    raise SystemExit(main())
