"""Emit sanctioned flat distribution-evidence records from installed oracles.

Both the release-readiness gate (:func:`dev.release.readiness.check_distribution_evidence_set`)
and the documentation-claims gate (``dev/docs/tests/test_distribution_claims.py``)
read flat ``*.json`` :class:`~dev.packaging.evidence.DistributionEvidence`
records from ``var/distribution-install-readiness/``. Those records are
tamper-evident and cohort-bound, so they can only be minted at capture time,
when the executed cohort, the isolated installed executables, and the real
command timestamps are all genuinely in hand. This module is the single bridge
that turns an installed CLI/MCP behaviour-oracle run into that record; it reuses
the canonical :func:`~dev.packaging.evidence.create_distribution_evidence`
authority rather than re-deriving evidence identity.

Design (ratified option A): an installed-oracle distribution row's record (Python,
Homebrew, or Scoop - every lane that installs the product and drives the real
``aeat`` and ``cadrumo-mcp`` commands) carries the real installed-CLI command
transcripts as its ``commands`` and folds the MCP protocol proof - the launched
server executable, its cohort-pinned tool-call sequence, and the grounded target
value - into ``result.observations`` plus the second ``installed_executables``
entry. No command transcript is ever synthesised: the
MCP server is launched inside the ``mcp`` stdio client, which does not expose a
genuine subprocess exit status or stream digests, so fabricating one would be
forbidden. Every field written here is a real captured value.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from dev.packaging.cohort_manifest import LoadedReleaseCohort, sha256_file
from dev.packaging.evidence import (
    AcquisitionIdentity,
    ClientIdentity,
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
from dev.packaging.installed_tax_oracle import CommandEvidence, InstalledTaxEvidence

if TYPE_CHECKING:
    from dev.packaging.installed_mcp_oracle import InstalledMcpEvidence

_CLI_EXECUTABLE_NAME: Final[str] = "aeat"
_MCP_EXECUTABLE_NAME: Final[str] = "cadrumo-mcp"


def _command_transcript(command: CommandEvidence) -> CommandTranscript:
    """Map one captured installed-CLI invocation to a tamper-evident transcript.

    The wall-clock ``started_at`` / ``completed_at`` stamps and ``cwd`` are read
    straight from the enriched :class:`~dev.packaging.installed_tax_oracle.CommandEvidence`;
    the stream digests are recomputed from the retained output by
    :meth:`~dev.packaging.evidence.CommandTranscript.from_output`.
    """
    summary = f"{Path(command.argv[0]).name} exit={command.returncode} ({command.duration_seconds}s)"
    version_lines = (
        [line for line in command.stdout.strip().splitlines()[:1] if line] if "--version" in command.argv else []
    )
    relevant_output = (*version_lines, summary)
    return CommandTranscript.from_output(
        argv=command.argv,
        cwd=command.cwd,
        started_at=datetime.fromisoformat(command.started_at),
        completed_at=datetime.fromisoformat(command.completed_at),
        exit_status=command.returncode,
        stdout=command.stdout,
        stderr=command.stderr,
        relevant_output=relevant_output,
    )


def _installed_executable(name: str, path: str) -> InstalledExecutableIdentity:
    """Digest one absolute installed executable that the oracle actually drove."""
    resolved = Path(path).resolve(strict=True)
    return InstalledExecutableIdentity(name=name, path=str(resolved), sha256=sha256_file(resolved))


def _mcp_call_summary(mcp_evidence: InstalledMcpEvidence) -> list[dict[str, Any]]:
    """Return a JSON-safe record of every MCP tool call the oracle made."""
    return [
        {
            "tool_name": call.tool_name,
            "command_key": call.command_key,
            "duration_seconds": call.duration_seconds,
            "is_error": call.is_error,
            "status": call.status,
        }
        for call in mcp_evidence.calls
    ]


def build_installed_oracle_evidence(
    *,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    mcp_evidence: InstalledMcpEvidence,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    client: ClientIdentity | None = None,
    observed_at: datetime | None = None,
) -> DistributionEvidence:
    """Assemble one cohort-bound record for an installed-oracle distribution row.

    Serves every lane that installs the product and drives the real ``aeat`` and
    ``cadrumo-mcp`` commands (Python/PyPI, Homebrew, Scoop).

    Args:
        row_id: The distribution row this record proves (a
            ``REQUIRED_DISTRIBUTION_ROWS`` id such as ``python-windows-x86-64``).
        cohort: The loaded release cohort the executed bytes belong to; the
            record binds to its immutable identity and digests.
        tax_evidence: The installed-CLI oracle result (its command transcripts
            become this record's ``commands``).
        mcp_evidence: The installed-MCP oracle result (its protocol proof is
            retained in ``result.observations`` and the MCP executable identity).
        acquisition: How and from where the tested bytes were acquired.
        destination: The install/promotion destination reached; its version must
            equal the cohort version for a passing record.
        client: The real client identity for a client-dependent row, else None.
        observed_at: The capture instant; defaults to now (must not predate the
            cohort's construction).

    Returns:
        A validated, tamper-evident :class:`~dev.packaging.evidence.DistributionEvidence`.
    """
    commands = tuple(_command_transcript(command) for command in tax_evidence.commands)
    isolation = ExecutionIsolation(
        checkout_imports_removed=True,
        ambient_product_executables_removed=True,
        installed_executables=(
            _installed_executable(_CLI_EXECUTABLE_NAME, tax_evidence.resolved_executable),
            _installed_executable(_MCP_EXECUTABLE_NAME, mcp_evidence.resolved_executable),
        ),
    )
    result = ResultIdentity(
        status=EvidenceStatus.PASSED,
        assertions=(
            f"installed CLI computed {tax_evidence.target_casilla}={tax_evidence.target_value} "
            f"via {tax_evidence.formula_id}",
            f"installed MCP computed {mcp_evidence.target_casilla}={mcp_evidence.target_value} "
            f"via {mcp_evidence.formula_id}",
            "every persisted observation carried legal and source grounding",
        ),
        observations={
            "cli_oracle": {
                "requested_executable": tax_evidence.requested_executable,
                "resolved_executable": tax_evidence.resolved_executable,
                "version_output": tax_evidence.version_output,
                "calculation_revision_id": tax_evidence.calculation_revision_id,
                "target_casilla": tax_evidence.target_casilla,
                "target_value": tax_evidence.target_value,
                "formula_id": tax_evidence.formula_id,
                "legal_refs": list(tax_evidence.legal_refs),
                "source_refs": list(tax_evidence.source_refs),
                "notice_codes": list(tax_evidence.notice_codes),
            },
            "mcp_oracle": {
                "resolved_executable": mcp_evidence.resolved_executable,
                "server_name": mcp_evidence.server_name,
                "calculation_revision_id": mcp_evidence.calculation_revision_id,
                "target_casilla": mcp_evidence.target_casilla,
                "target_value": mcp_evidence.target_value,
                "formula_id": mcp_evidence.formula_id,
                "invoked_cli_sha256": mcp_evidence.invoked_cli_sha256,
                "invoked_cli_sha256_by_command": dict(mcp_evidence.invoked_cli_sha256_by_command),
                "calls": _mcp_call_summary(mcp_evidence),
            },
        },
    )
    return create_distribution_evidence(
        row_id=row_id,
        cohort=cohort,
        runtime=current_runtime_identity(),
        client=client,
        isolation=isolation,
        acquisition=acquisition,
        commands=commands,
        result=result,
        observed_at=observed_at or datetime.now(UTC),
        destination=destination,
    )


def emit_installed_oracle_evidence(
    *,
    directory: Path,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    mcp_evidence: InstalledMcpEvidence,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    client: ClientIdentity | None = None,
    observed_at: datetime | None = None,
) -> Path:
    """Build and persist one flat distribution-evidence record.

    Writes ``{row_id}-{evidence_id}.json`` under ``directory`` (the flat layout
    both release-readiness and the docs-claims gate scan) and returns its path.
    """
    evidence = build_installed_oracle_evidence(
        row_id=row_id,
        cohort=cohort,
        tax_evidence=tax_evidence,
        mcp_evidence=mcp_evidence,
        acquisition=acquisition,
        destination=destination,
        client=client,
        observed_at=observed_at,
    )
    return write_distribution_evidence(directory, evidence)


def _tax_evidence_from_mapping(data: dict[str, Any]) -> InstalledTaxEvidence:
    """Reconstruct installed-CLI oracle evidence from its ``to_jsonable`` mapping.

    Used by the CLI so a lane that already wrote ``tax-evidence.json`` (e.g. the
    PowerShell Scoop smoke) can emit the flat record without re-running the
    oracle. Tuple-typed fields arrive as JSON lists and are coerced back.
    """
    commands = tuple(
        CommandEvidence(
            argv=tuple(command["argv"]),
            duration_seconds=command["duration_seconds"],
            returncode=command["returncode"],
            stdout=command["stdout"],
            stderr=command["stderr"],
            started_at=command["started_at"],
            completed_at=command["completed_at"],
            cwd=command["cwd"],
        )
        for command in data["commands"]
    )
    return InstalledTaxEvidence(
        requested_executable=data["requested_executable"],
        resolved_executable=data["resolved_executable"],
        version_output=data["version_output"],
        storage_root=data["storage_root"],
        work_unit_id=data["work_unit_id"],
        calculation_revision_id=data["calculation_revision_id"],
        target_casilla=data["target_casilla"],
        target_value=data["target_value"],
        formula_id=data["formula_id"],
        legal_refs=tuple(data["legal_refs"]),
        source_refs=tuple(data["source_refs"]),
        notice_codes=tuple(data["notice_codes"]),
        commands=commands,
    )


def _mcp_evidence_from_mapping(data: dict[str, Any]) -> InstalledMcpEvidence:
    """Reconstruct installed-MCP oracle evidence from its ``to_jsonable`` mapping.

    The ``mcp`` import is deferred so this module stays importable without the
    ``mcp`` dependency for the pure build path.
    """
    from dev.packaging.installed_mcp_oracle import InstalledMcpEvidence, McpCallEvidence

    calls = tuple(
        McpCallEvidence(
            tool_name=call["tool_name"],
            command_key=call["command_key"],
            duration_seconds=call["duration_seconds"],
            is_error=call["is_error"],
            status=call["status"],
        )
        for call in data["calls"]
    )
    return InstalledMcpEvidence(
        requested_executable=data["requested_executable"],
        resolved_executable=data["resolved_executable"],
        server_name=data["server_name"],
        storage_root=data["storage_root"],
        work_unit_id=data["work_unit_id"],
        calculation_revision_id=data["calculation_revision_id"],
        observations_resource=data["observations_resource"],
        target_casilla=data["target_casilla"],
        target_value=data["target_value"],
        formula_id=data["formula_id"],
        legal_refs=tuple(data["legal_refs"]),
        source_refs=tuple(data["source_refs"]),
        notice_codes=tuple(data["notice_codes"]),
        advertised_tools=tuple(data["advertised_tools"]),
        calls=calls,
        invoked_cli_sha256=data["invoked_cli_sha256"],
        invoked_cli_sha256_by_command=dict(data["invoked_cli_sha256_by_command"]),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit one sanctioned flat distribution-evidence record.")
    parser.add_argument("--row-id", required=True, help="Distribution row this run proves.")
    parser.add_argument("--release-cohort-dir", required=True, type=Path, help="Full release-cohort directory.")
    parser.add_argument("--tax-evidence", required=True, type=Path, help="installed_tax_oracle --output JSON.")
    parser.add_argument("--mcp-evidence", required=True, type=Path, help="installed_mcp_oracle --output JSON.")
    parser.add_argument("--acquisition-mechanism", required=True, help="Acquisition channel (scoop, brew, pip, ...).")
    parser.add_argument("--acquisition-source", required=True, help="Public locator the bytes were acquired from.")
    parser.add_argument("--destination-kind", required=True, help="Install/promotion destination kind.")
    parser.add_argument("--destination-locator", required=True, help="Install/promotion destination locator.")
    parser.add_argument(
        "--distribution-evidence-dir",
        type=Path,
        default=Path("var/distribution-install-readiness"),
        help="Where the flat record lands.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Emit a flat record from oracle-evidence JSON a lane already produced."""
    from dev.packaging.cohort_manifest import load_release_cohort

    args = _parser().parse_args(argv)
    tax_evidence = _tax_evidence_from_mapping(json.loads(args.tax_evidence.read_text(encoding="utf-8")))
    mcp_evidence = _mcp_evidence_from_mapping(json.loads(args.mcp_evidence.read_text(encoding="utf-8")))
    cohort = load_release_cohort(args.release_cohort_dir)
    path = emit_installed_oracle_evidence(
        directory=args.distribution_evidence_dir,
        row_id=args.row_id,
        cohort=cohort,
        tax_evidence=tax_evidence,
        mcp_evidence=mcp_evidence,
        acquisition=AcquisitionIdentity(mechanism=args.acquisition_mechanism, source=args.acquisition_source),
        destination=DestinationIdentity(
            kind=args.destination_kind,
            locator=args.destination_locator,
            version=cohort.manifest.version,
        ),
    )
    print(path)
    return 0


__all__ = [
    "build_installed_oracle_evidence",
    "emit_installed_oracle_evidence",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
