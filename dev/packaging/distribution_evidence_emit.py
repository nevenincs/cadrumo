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
``aeat`` command) carries the real installed-CLI command transcripts as its
``commands`` and folds the MCP protocol proof - the launched server executable,
its cohort-pinned tool-call sequence, and the grounded target value - into
``result.observations`` plus the second ``installed_executables`` entry. A lane
that ships no MCP leg (the CLI-only Scoop and Homebrew lanes, which never install
``cadrumo-mcp``) records that absence honestly: ``mcp_oracle`` is ``None`` and
the isolation and executable facts come from the tax oracle alone. No command
transcript is ever synthesised: the MCP server is launched inside the ``mcp``
stdio client, which does not expose a genuine subprocess exit status or stream
digests, so fabricating one would be forbidden. Every field written here is a
real captured value.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dev._paths import UTF_8

from ._command import CommandResult
from ._hashing import sha256_path
from ._installed_wheel_binding import installed_wheel_payload_sha256, sealed_wheel_payload_sha256
from .cohort_manifest import LoadedReleaseCohort
from .evidence import (
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
from .evidence_scrub import scrub_distribution_evidence
from .installed_tax_oracle import InstalledTaxEvidence

if TYPE_CHECKING:
    from .installed_mcp_oracle import InstalledMcpEvidence

_CLI_EXECUTABLE_NAME: Final[str] = "aeat"
_MCP_EXECUTABLE_NAME: Final[str] = "cadrumo-mcp"
_UTF_8: Final[str] = UTF_8

# The client identity an acquire lane declares when it drives the published
# artifact through the MCP SDK over ``uv``/``uvx`` rather than a real Claude
# client. Shared with the acquire lanes so the honesty guard below and the lanes
# agree on one spelling.
SDK_CLIENT_NAME: Final[str] = "cadrumo-mcp-sdk-client"

# The REQUIRED real-client rows: these are real-Claude-client claims (the plan
# step language is "install in Claude Desktop and execute the real tax-work tool
# call"), satisfiable only by real-client lane evidence, never an SDK-driven run.
# Kept in lock-step with the claude-* subset of
# ``dev.release.readiness.REQUIRED_DISTRIBUTION_ROWS`` by a parity test.
_REQUIRED_REAL_CLIENT_ROW_IDS: Final[frozenset[str]] = frozenset(
    {
        "claude-code-plugin",
        "claude-cowork-plugin",
        "claude-desktop-plugin",
        "claude-desktop-mcpb",
    },
)


class RealClientSession(BaseModel):
    """The minimum successful client-session proof permitted in passing release evidence."""

    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    connected: Literal[True]
    status: Literal["passed"]
    tool_called: str = Field(min_length=1)


def _command_transcript(command: CommandResult) -> CommandTranscript:
    """Map one captured installed-CLI invocation to a tamper-evident transcript.

    The wall-clock ``started_at`` / ``completed_at`` stamps and ``cwd`` are read
    straight from the canonical :class:`~dev.packaging._command.CommandResult`;
    the stream digests are recomputed from the retained output by
    :meth:`~dev.packaging.evidence.CommandTranscript.from_output`.
    """
    summary = f"{Path(command.argv[0]).name} exit={command.returncode} ({command.duration_seconds}s)"
    version_lines = (
        [line for line in command.stdout.strip().splitlines()[:1] if line] if "--version" in command.argv else []
    )
    relevant_output = (*version_lines, summary)
    return CommandTranscript.from_result(
        command,
        relevant_output=relevant_output,
    )


def _installed_executable(name: str, path: str) -> InstalledExecutableIdentity:
    """Digest one absolute installed executable that the oracle actually drove."""
    resolved = Path(path).resolve(strict=True)
    return InstalledExecutableIdentity(name=name, path=str(resolved), sha256=sha256_path(resolved))


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


def _mcp_observations(mcp_evidence: InstalledMcpEvidence) -> dict[str, Any]:
    """Return the retained MCP protocol proof (the full evidence, no command fabricated)."""
    return {
        "resolved_executable": mcp_evidence.resolved_executable,
        "server_name": mcp_evidence.server_name,
        "calculation_revision_id": mcp_evidence.calculation_revision_id,
        "target_casilla": mcp_evidence.target_casilla,
        "target_value": mcp_evidence.target_value,
        "formula_id": mcp_evidence.formula_id,
        "invoked_cli_sha256": mcp_evidence.invoked_cli_sha256,
        "invoked_cli_sha256_by_command": dict(mcp_evidence.invoked_cli_sha256_by_command),
        "calls": _mcp_call_summary(mcp_evidence),
    }


class EvidenceCohortBindingError(RuntimeError):
    """Raised when an oracle capture is not bound to the release cohort it is minted against."""


def _assert_oracle_bound_to_cohort(
    *,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
) -> None:
    """Refuse to mint a record whose oracle capture is not the cohort's build.

    The CLI reconstitutes ``tax-evidence.json`` a lane already produced, then
    binds a cohort. Without this check the two are independent: a capture of a
    *different* build could be minted against any cohort, and the destination
    version is merely copied from the cohort. The installed CLI's ``--version``
    output is the captured fact that pins the capture to the cohort: it must
    carry the cohort version, or the capture is not this cohort's build and
    minting is refused. A lane's MCP dimension, when present, is bound
    transitively — both oracles are captured from one installed cohort run; the
    MCP telemetry ``invoked_cli_sha256`` is an attested CLI-*path* digest, not a
    cohort artifact digest, so it cannot bind to the cohort manifest directly.
    """
    version = cohort.manifest.version
    # Match on a token boundary, not a bare substring: a 0.2.10 or 0.2.1rc1
    # capture must NOT false-accept against a 0.2.1 cohort. The guards reject an
    # adjacent version-continuation character (word char or dot) on either side.
    version_token = re.compile(rf"(?<![\w.]){re.escape(version)}(?![\w.])")
    if not version_token.search(tax_evidence.version_output):
        raise EvidenceCohortBindingError(
            f"installed CLI version output {tax_evidence.version_output!r} does not carry the "
            f"cohort version {version!r} as a distinct version token: the captured oracle is not "
            "this cohort's build. Re-run the installed oracles against the cohort under test before "
            "emitting evidence.",
        )
    records = {record.name: record for record in cohort.manifest.artifacts}
    expected = {
        "cohort_source_commit": cohort.manifest.source.commit,
        "cohort_manifest_sha256": records["python-cohort-manifest"].sha256,
        "cohort_root_wheel_sha256": records["cadrumo-wheel"].sha256,
    }
    observed = {
        "cohort_source_commit": tax_evidence.cohort_source_commit,
        "cohort_manifest_sha256": tax_evidence.cohort_manifest_sha256,
        "cohort_root_wheel_sha256": tax_evidence.cohort_root_wheel_sha256,
    }
    if observed != expected:
        raise EvidenceCohortBindingError(
            f"installed oracle cohort provenance mismatch: expected {expected!r}, got {observed!r}",
        )
    executable = Path(tax_evidence.resolved_executable).resolve(strict=True)
    actual_executable_sha256 = sha256_path(executable)
    if actual_executable_sha256 != tax_evidence.executable_sha256:
        raise EvidenceCohortBindingError(
            "installed oracle executable digest mismatch: the captured executable was replaced "
            "or the evidence was swapped before minting",
        )
    expected_payload_sha256 = sealed_wheel_payload_sha256(cohort.artifact("cadrumo-wheel"))
    observed_payload_sha256 = installed_wheel_payload_sha256(executable)
    if (
        tax_evidence.installed_wheel_payload_sha256 != expected_payload_sha256
        or observed_payload_sha256 != expected_payload_sha256
    ):
        raise EvidenceCohortBindingError(
            "installed cadrumo payload does not match the exact sealed root wheel",
        )


def build_installed_oracle_evidence(
    *,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    mcp_evidence: InstalledMcpEvidence | None = None,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    client: ClientIdentity | None = None,
    observed_at: datetime | None = None,
) -> DistributionEvidence:
    """Assemble one cohort-bound record for an installed-oracle distribution row.

    Serves every lane that installs the product and drives the real ``aeat``
    command (Python/PyPI, Homebrew, Scoop).

    Args:
        row_id: The distribution row this record proves (a
            ``REQUIRED_DISTRIBUTION_ROWS`` id such as ``python-windows-x86-64``).
        cohort: The loaded release cohort the executed bytes belong to; the
            record binds to its immutable identity and digests.
        tax_evidence: The installed-CLI oracle result (its command transcripts
            become this record's ``commands``).
        mcp_evidence: The installed-MCP oracle result (its protocol proof is
            retained in ``result.observations`` and the MCP executable identity).
            ``None`` for a lane that ships no MCP leg: the isolation and
            executable facts then come from the tax oracle alone and
            ``mcp_oracle`` is recorded as the absent marker ``None``.
        acquisition: How and from where the tested bytes were acquired.
        destination: The install/promotion destination reached; its version must
            equal the cohort version for a passing record.
        client: The real client identity for a client-dependent row, else None.
        observed_at: The capture instant; defaults to now (must not predate the
            cohort's construction).

    Returns:
        A validated, tamper-evident :class:`~dev.packaging.evidence.DistributionEvidence`.
    """
    _assert_oracle_bound_to_cohort(cohort=cohort, tax_evidence=tax_evidence)
    commands = tuple(_command_transcript(command) for command in tax_evidence.commands)
    cli_observations = {
        "requested_executable": tax_evidence.requested_executable,
        "resolved_executable": tax_evidence.resolved_executable,
        "version_output": tax_evidence.version_output,
        "cohort_source_commit": tax_evidence.cohort_source_commit,
        "cohort_manifest_sha256": tax_evidence.cohort_manifest_sha256,
        "cohort_root_wheel_sha256": tax_evidence.cohort_root_wheel_sha256,
        "executable_sha256": tax_evidence.executable_sha256,
        "installed_wheel_payload_sha256": tax_evidence.installed_wheel_payload_sha256,
        "calculation_revision_id": tax_evidence.calculation_revision_id,
        "target_casilla": tax_evidence.target_casilla,
        "target_value": tax_evidence.target_value,
        "formula_id": tax_evidence.formula_id,
        "legal_refs": list(tax_evidence.legal_refs),
        "source_refs": list(tax_evidence.source_refs),
        "notice_codes": list(tax_evidence.notice_codes),
    }
    if mcp_evidence is None:
        isolation = ExecutionIsolation(
            # Derived from what the oracle actually recorded, not asserted: if a
            # future refactor stops stripping checkout imports or product
            # executables, the oracle records False and the evidence schema
            # refuses to mint a PASSED record.
            checkout_imports_removed=tax_evidence.checkout_imports_removed,
            ambient_product_executables_removed=tax_evidence.ambient_product_executables_removed,
            installed_executables=(_installed_executable(_CLI_EXECUTABLE_NAME, tax_evidence.resolved_executable),),
        )
        assertions = (
            f"installed CLI computed {tax_evidence.target_casilla}={tax_evidence.target_value} "
            f"via {tax_evidence.formula_id}",
            "the lane ships no MCP leg: cadrumo-mcp is not part of this distribution",
            "every persisted observation carried legal and source grounding",
        )
        observations: dict[str, Any] = {"cli_oracle": cli_observations, "mcp_oracle": None}
    else:
        isolation = ExecutionIsolation(
            # Derived from what the oracles actually recorded, not asserted: if a future
            # refactor stops stripping checkout imports or product executables, the oracle
            # records False and the evidence schema refuses to mint a PASSED record.
            checkout_imports_removed=tax_evidence.checkout_imports_removed and mcp_evidence.checkout_imports_removed,
            ambient_product_executables_removed=mcp_evidence.ambient_product_executables_removed,
            installed_executables=(
                _installed_executable(_CLI_EXECUTABLE_NAME, tax_evidence.resolved_executable),
                _installed_executable(_MCP_EXECUTABLE_NAME, mcp_evidence.resolved_executable),
            ),
        )
        assertions = (
            f"installed CLI computed {tax_evidence.target_casilla}={tax_evidence.target_value} "
            f"via {tax_evidence.formula_id}",
            f"installed MCP computed {mcp_evidence.target_casilla}={mcp_evidence.target_value} "
            f"via {mcp_evidence.formula_id}",
            "every persisted observation carried legal and source grounding",
        )
        observations = {"cli_oracle": cli_observations, "mcp_oracle": _mcp_observations(mcp_evidence)}
    result = ResultIdentity(
        status=EvidenceStatus.PASSED,
        assertions=assertions,
        observations=observations,
    )
    evidence = create_distribution_evidence(
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
    # Rows are published (draft transport, then the final release), so runner
    # metadata is scrubbed at birth: one identity, no unscrubbed copy exists.
    return scrub_distribution_evidence(evidence)


def build_client_evidence(
    *,
    row_id: str,
    cohort: LoadedReleaseCohort,
    mcp_evidence: InstalledMcpEvidence,
    launch_transcript: CommandTranscript,
    client: ClientIdentity,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    real_client_session: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> DistributionEvidence:
    """Assemble one cohort-bound record for a pure-client (MCP-only) row.

    Client rows (``claude-*``) have no installed-CLI oracle, so option A applies:
    the single command transcript is a genuinely-owned bounded launch of the
    installed ``cadrumo-mcp`` server subprocess (real argv, cwd, timestamps, exit
    status, and stream digests), and the full MCP protocol proof rides in
    ``result.observations``. Nothing is synthesised.

    For a REAL Claude client row the client itself launches the server internally
    (a subprocess we do not own), so the owned launch here proves the exact
    installed server starts, and the operator's real Claude client session -
    passed as ``real_client_session`` - is retained in ``result.observations`` as
    the real-client dimension, with ``client`` naming the real Claude client.

    Args:
        row_id: The client row this record proves (e.g. ``claude-desktop-mcpb``).
        cohort: The loaded release cohort the served bytes belong to.
        mcp_evidence: The installed-MCP oracle result (protocol proof + target).
        launch_transcript: The real owned server-launch subprocess captured;
            becomes this record's sole command transcript.
        client: The real client identity (required for a client row).
        acquisition: How and from where the served bytes were acquired.
        destination: The install/serve destination; its version must equal the
            cohort version for a passing record.
        real_client_session: The operator's real Claude client session summary
            (connected, tool_called, status, ...) retained as the real-client
            proof; ``None`` for an SDK acquire artifact-serves record.
        observed_at: The capture instant; defaults to now.

    Returns:
        A validated, tamper-evident :class:`~dev.packaging.evidence.DistributionEvidence`.

    Raises:
        ValueError: If an SDK-client record is asked to satisfy a REQUIRED
            real-client row, or a REQUIRED real-client row is minted without a
            real client session. Those rows are real-Claude-client claims.
    """
    is_required_real_client_row = row_id in _REQUIRED_REAL_CLIENT_ROW_IDS
    if client.name == SDK_CLIENT_NAME and is_required_real_client_row:
        raise ValueError(
            f"an SDK-client record cannot satisfy the real-client row {row_id!r}: those rows are minted "
            "only by real-client lanes (authenticated Claude Code / operator in-app captures). "
            "Emit this SDK acquire proof under a distinct artifact-serves id instead.",
        )
    if is_required_real_client_row and real_client_session is None:
        raise ValueError(
            f"the real-client row {row_id!r} requires a real Claude client session as its real-client "
            "proof; an owned launch alone cannot satisfy a real-client claim.",
        )
    validated_real_client_session: RealClientSession | None = None
    if real_client_session is not None:
        try:
            validated_real_client_session = RealClientSession.model_validate(real_client_session)
        except ValidationError as exc:
            raise ValueError(
                "real-client evidence requires a connected, passed session with a recorded tool_called value",
            ) from exc
    isolation = ExecutionIsolation(
        # Derived from the MCP oracle's recorded isolation (see build_installed_oracle_evidence).
        checkout_imports_removed=mcp_evidence.checkout_imports_removed,
        ambient_product_executables_removed=mcp_evidence.ambient_product_executables_removed,
        installed_executables=(_installed_executable(_MCP_EXECUTABLE_NAME, mcp_evidence.resolved_executable),),
    )
    observations: dict[str, Any] = {"mcp_oracle": _mcp_observations(mcp_evidence)}
    if validated_real_client_session is not None:
        observations["real_client_session"] = validated_real_client_session.model_dump(mode="json")
    result = ResultIdentity(
        status=EvidenceStatus.PASSED,
        assertions=(
            f"client MCP computed {mcp_evidence.target_casilla}={mcp_evidence.target_value} "
            f"via {mcp_evidence.formula_id}",
            "the installed client launched the cohort-pinned server and completed the protocol",
        ),
        observations=observations,
    )
    evidence = create_distribution_evidence(
        row_id=row_id,
        cohort=cohort,
        runtime=current_runtime_identity(),
        client=client,
        isolation=isolation,
        acquisition=acquisition,
        commands=(launch_transcript,),
        result=result,
        observed_at=observed_at or datetime.now(UTC),
        destination=destination,
    )
    # Client rows publish identically; scrub at birth (see build_installed_oracle_evidence).
    return scrub_distribution_evidence(evidence)


def emit_client_evidence(
    *,
    directory: Path,
    row_id: str,
    cohort: LoadedReleaseCohort,
    mcp_evidence: InstalledMcpEvidence,
    launch_transcript: CommandTranscript,
    client: ClientIdentity,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    real_client_session: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> Path:
    """Build and persist one flat client-row distribution-evidence record."""
    evidence = build_client_evidence(
        row_id=row_id,
        cohort=cohort,
        mcp_evidence=mcp_evidence,
        launch_transcript=launch_transcript,
        client=client,
        acquisition=acquisition,
        destination=destination,
        real_client_session=real_client_session,
        observed_at=observed_at,
    )
    return write_distribution_evidence(directory, evidence)


def emit_installed_oracle_evidence(
    *,
    directory: Path,
    row_id: str,
    cohort: LoadedReleaseCohort,
    tax_evidence: InstalledTaxEvidence,
    mcp_evidence: InstalledMcpEvidence | None = None,
    acquisition: AcquisitionIdentity,
    destination: DestinationIdentity,
    client: ClientIdentity | None = None,
    observed_at: datetime | None = None,
) -> Path:
    """Build and persist one flat distribution-evidence record.

    Writes ``{row_id}-{evidence_id}.json`` under ``directory`` (the flat layout
    both release-readiness and the docs-claims gate scan) and returns its path.
    ``mcp_evidence`` is optional exactly as in :func:`build_installed_oracle_evidence`:
    a lane that ships no MCP leg omits it and the record marks the leg absent.
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


def _require_isolation_fields(data: dict[str, Any], *, kind: str, fields: tuple[str, ...]) -> None:
    """Refuse a pre-isolation-recording capture with an instructive re-capture action.

    Evidence JSON captured before the oracle recorded its isolation facts lacks
    these keys. Rather than die with a raw ``KeyError``, name the missing fields
    and the re-capture action. This is a hard refusal, not a tolerance branch:
    an old-shape capture is never minted with defaulted isolation.
    """
    missing = [field for field in fields if field not in data]
    if missing:
        raise EvidenceCohortBindingError(
            f"{kind} oracle JSON is missing the isolation field(s) {missing}: this capture predates the "
            "isolation-fact recording and cannot be minted. Re-run the installed oracles against the cohort "
            "under test to produce a current capture.",
        )


def _tax_evidence_from_mapping(data: dict[str, Any]) -> InstalledTaxEvidence:
    """Reconstruct installed-CLI oracle evidence from its ``to_jsonable`` mapping.

    Used by the CLI so a lane that already wrote ``tax-evidence.json`` (e.g. the
    PowerShell Scoop smoke) can emit the flat record without re-running the
    oracle. Tuple-typed fields arrive as JSON lists and are coerced back.
    """
    _require_isolation_fields(
        data,
        kind="installed CLI",
        fields=("checkout_imports_removed", "ambient_product_executables_removed"),
    )
    commands = tuple(
        CommandResult(
            argv=tuple(command["argv"]),
            cwd=command["cwd"],
            started_at=datetime.fromisoformat(command["started_at"]),
            completed_at=datetime.fromisoformat(command["completed_at"]),
            duration_seconds=command["duration_seconds"],
            returncode=command["returncode"],
            stdout=command["stdout"],
            stderr=command["stderr"],
        )
        for command in data["commands"]
    )
    return InstalledTaxEvidence(
        requested_executable=data["requested_executable"],
        resolved_executable=data["resolved_executable"],
        version_output=data["version_output"],
        cohort_source_commit=data["cohort_source_commit"],
        cohort_manifest_sha256=data["cohort_manifest_sha256"],
        cohort_root_wheel_sha256=data["cohort_root_wheel_sha256"],
        executable_sha256=data["executable_sha256"],
        installed_wheel_payload_sha256=data["installed_wheel_payload_sha256"],
        storage_root=data["storage_root"],
        work_unit_id=data["work_unit_id"],
        calculation_revision_id=data["calculation_revision_id"],
        target_casilla=data["target_casilla"],
        target_value=data["target_value"],
        formula_id=data["formula_id"],
        legal_refs=tuple(data["legal_refs"]),
        source_refs=tuple(data["source_refs"]),
        notice_codes=tuple(data["notice_codes"]),
        checkout_imports_removed=data["checkout_imports_removed"],
        ambient_product_executables_removed=data["ambient_product_executables_removed"],
        commands=commands,
    )


def _mcp_evidence_from_mapping(data: dict[str, Any]) -> InstalledMcpEvidence:
    """Reconstruct installed-MCP oracle evidence from its ``to_jsonable`` mapping.

    The ``mcp`` import is deferred so this module stays importable without the
    ``mcp`` dependency for the pure build path.
    """
    from .installed_mcp_oracle import InstalledMcpEvidence, McpCallEvidence

    _require_isolation_fields(
        data,
        kind="installed MCP",
        fields=("checkout_imports_removed", "ambient_product_executables_removed"),
    )
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
        checkout_imports_removed=data["checkout_imports_removed"],
        ambient_product_executables_removed=data["ambient_product_executables_removed"],
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit one sanctioned flat distribution-evidence record.")
    parser.add_argument("--row-id", required=True, help="Distribution row this run proves.")
    parser.add_argument("--release-cohort-dir", required=True, type=Path, help="Full release-cohort directory.")
    parser.add_argument("--tax-evidence", required=True, type=Path, help="installed_tax_oracle --output JSON.")
    parser.add_argument(
        "--mcp-evidence",
        type=Path,
        default=None,
        help="Optional installed_mcp_oracle --output JSON; omit for a lane that ships no MCP leg.",
    )
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
    from .cohort_manifest import load_release_cohort

    args = _parser().parse_args(argv)
    tax_evidence = _tax_evidence_from_mapping(json.loads(args.tax_evidence.read_text(encoding=_UTF_8)))
    mcp_evidence = None
    if args.mcp_evidence is not None:
        mcp_evidence = _mcp_evidence_from_mapping(json.loads(args.mcp_evidence.read_text(encoding=_UTF_8)))
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
    "SDK_CLIENT_NAME",
    "EvidenceCohortBindingError",
    "build_client_evidence",
    "build_installed_oracle_evidence",
    "emit_client_evidence",
    "emit_installed_oracle_evidence",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
