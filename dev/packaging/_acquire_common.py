"""Shared verification core for the public-reacquisition tooling.

The ``acquire_*`` scripts prove that every advertised PUBLIC endpoint serves the
exact promoted cohort bytes AFTER publication. Publication has not happened yet,
so this module centralises the two behaviours every acquisition script needs:

* an INSTRUCTIVE refusal (:func:`refuse_unavailable`) when the public endpoint
  does not yet carry the release — it names the mechanism, the endpoint, the
  expected version, and the operator's next step, and it never returns; and
* a fail-closed digest verification (:func:`verify_artifact_digest`,
  :func:`verify_python_cohort_download`, :func:`verify_release_download`) that
  re-hashes acquired bytes against the promoted cohort manifest.

The oracle runner (:func:`run_installed_behavior_oracles`) re-uses the canonical
installed CLI and MCP oracles rather than re-deriving tax truth. Its heavy
imports (``mcp``) are deferred so the pure digest helpers stay importable in a
minimal environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

from cadrumo.core import scan_directory
from dev._paths import UTF_8

from ._hashing import sha256_path
from .cohort_manifest import LoadedReleaseCohort
from .evidence import CommandTranscript
from .python_cohort import PythonCohort

if TYPE_CHECKING:
    from .installed_mcp_oracle import InstalledMcpEvidence
    from .installed_tax_oracle import InstalledTaxEvidence

_UTF_8: Final[str] = UTF_8

# The distributions the promoted Python cohort carries as installable wheels,
# each keyed by the exact ``python-cohort.json`` digest name. A public
# reacquisition proves these three, and only these three, byte-for-byte.
#
# The independently versioned harness is an exact digest-pinned cohort member.
PYTHON_COHORT_WHEEL_NAMES: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-harness",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)

#: The sibling agent-harness distribution name.
HARNESS_DISTRIBUTION: Final[str] = "cadrumo-harness"

# The grounded Modelo 200 cuota íntegra the installed behaviour oracles must
# reproduce; a divergent value means the acquired bytes are not the promoted
# release. Mirrors ``installed_tax_oracle.EXPECTED_VALUE``.
EXPECTED_ORACLE_TARGET_VALUE: Final[str] = "23000.00"

_REFUSAL_PREFIX: Final[str] = "public reacquisition unavailable"
_MISMATCH_PREFIX: Final[str] = "public reacquisition digest mismatch"


class AcquisitionError(SystemExit):
    """Instructive, fail-closed refusal raised by the reacquisition tooling.

    Subclasses :class:`SystemExit` so a script exits non-zero with the rendered
    message, while remaining catchable as a distinct type by callers and tests.
    """


def refuse_unavailable(
    *,
    mechanism: str,
    endpoint: str,
    version: str,
    reason: str,
    next_step: str,
) -> NoReturn:
    """Refuse an acquisition whose public endpoint does not carry the release.

    Args:
        mechanism: The acquisition channel (``pip``, ``gh release``, ``brew`` …).
        endpoint: The exact public locator queried (index URL, repo slug, tap).
        version: The promoted cohort version that was expected but not served.
        reason: A concrete description of what was missing or unreachable.
        next_step: The operator action that will make the endpoint serve it.

    Raises:
        AcquisitionError: Always; this function never returns.
    """
    raise AcquisitionError(
        f"{_REFUSAL_PREFIX}: {mechanism} endpoint {endpoint!r} does not yet serve "
        f"cadrumo {version}: {reason}. Next step: {next_step}",
    )


def refuse_digest_mismatch(
    *,
    mechanism: str,
    endpoint: str,
    name: str,
    expected_sha256: str,
    actual_sha256: str,
) -> NoReturn:
    """Refuse an acquired artifact whose bytes drift from the cohort manifest.

    Raises:
        AcquisitionError: Always; this function never returns.
    """
    raise AcquisitionError(
        f"{_MISMATCH_PREFIX}: {mechanism} endpoint {endpoint!r} served {name!r} with "
        f"sha256 {actual_sha256} but the promoted cohort declares {expected_sha256}. "
        "The public endpoint is serving different bytes than were tested; refusing.",
    )


def require_command_succeeded(
    *,
    returncode: int,
    stderr: str,
    mechanism: str,
    endpoint: str,
    version: str,
    next_step: str,
) -> None:
    """Refuse instructively when a public-acquisition command exited non-zero.

    A non-zero exit from ``pip download``, ``gh release download``, ``brew
    install``, or an HTTP fetch is the dominant "not yet published" signal: the
    tag, index entry, tap formula, or bundle asset is absent. This turns that
    raw exit into an instructive refusal naming the endpoint and version.

    Args:
        returncode: The acquisition command's exit code.
        stderr: The command's captured standard error (trimmed into the reason).
        mechanism: The acquisition channel, for the refusal message.
        endpoint: The public locator queried, for the refusal message.
        version: The promoted cohort version expected, for the refusal message.
        next_step: The operator action that will make the endpoint serve it.

    Raises:
        AcquisitionError: If ``returncode`` is non-zero.
    """
    if returncode != 0:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "no diagnostic output"
        refuse_unavailable(
            mechanism=mechanism,
            endpoint=endpoint,
            version=version,
            reason=f"the acquisition command exited {returncode}: {detail[:200]}",
            next_step=next_step,
        )


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()


def verify_artifact_digest(
    *,
    mechanism: str,
    endpoint: str,
    name: str,
    path: Path,
    expected_sha256: str,
) -> str:
    """Re-hash one acquired artifact and refuse on any drift from the cohort.

    Args:
        mechanism: The acquisition channel, for the refusal message.
        endpoint: The public locator, for the refusal message.
        name: The cohort artifact name being verified.
        path: The acquired file on disk to re-hash.
        expected_sha256: The digest the promoted cohort manifest declares.

    Returns:
        The verified digest (equal to ``expected_sha256``).

    Raises:
        AcquisitionError: If the acquired bytes do not match the cohort digest.
    """
    actual = sha256_path(path)
    if actual != expected_sha256:
        refuse_digest_mismatch(
            mechanism=mechanism,
            endpoint=endpoint,
            name=name,
            expected_sha256=expected_sha256,
            actual_sha256=actual,
        )
    return actual


def _wheel_distribution_prefix(distribution: str, version: str) -> str:
    """Return the version-delimited wheel filename prefix for a distribution.

    The ``-{version}-`` boundary keeps ``cadrumo`` from matching the
    ``cadrumo_data_*`` companion wheels, whose PEP 427 filenames underscore the
    distribution name (``cadrumo_data_manuals-<version>-...``).
    """
    return f"{distribution.replace('-', '_')}-{version}-"


def match_downloaded_cohort_wheels(
    download_dir: Path,
    cohort: PythonCohort,
    *,
    mechanism: str,
    endpoint: str,
) -> dict[str, Path]:
    """Map each promoted cohort distribution to its one downloaded wheel.

    Args:
        download_dir: A directory holding wheels fetched from a public index.
        cohort: The promoted Python cohort (source of version and digests).
        mechanism: The acquisition channel, for the refusal message.
        endpoint: The public locator, for the refusal message.

    Returns:
        A mapping of cohort distribution name to its resolved wheel path.

    Raises:
        AcquisitionError: If any distribution's wheel is absent (not yet
            published) or resolves to more than one file.
    """
    resolved: dict[str, Path] = {}
    for distribution in PYTHON_COHORT_WHEEL_NAMES:
        distribution_version = (
            cohort.harness_version if distribution == HARNESS_DISTRIBUTION else cohort.version
        )
        prefix = _wheel_distribution_prefix(distribution, distribution_version)
        matches = [path for path in scan_directory(download_dir, pattern="*.whl") if path.name.startswith(prefix)]
        if not matches:
            refuse_unavailable(
                mechanism=mechanism,
                endpoint=endpoint,
                version=distribution_version,
                reason=f"no {distribution}=={distribution_version} wheel was served",
                next_step=(f"publish {distribution}=={distribution_version} to {endpoint} and rerun this check"),
            )
        if len(matches) != 1:
            raise AcquisitionError(
                f"expected one {distribution}=={distribution_version} wheel from {endpoint!r}; "
                f"got {[path.name for path in matches]!r}",
            )
        resolved[distribution] = matches[0]
    return resolved


def verify_python_cohort_download(
    download_dir: Path,
    cohort: PythonCohort,
    *,
    mechanism: str,
    endpoint: str,
) -> dict[str, Path]:
    """Verify every downloaded cohort wheel byte-for-byte against the manifest.

    Args:
        download_dir: The directory into which the public wheels were fetched.
        cohort: The promoted Python cohort carrying the expected digests.
        mechanism: The acquisition channel, for the refusal messages.
        endpoint: The public locator, for the refusal messages.

    Returns:
        The verified distribution-name to wheel-path mapping.

    Raises:
        AcquisitionError: On a missing distribution or a digest mismatch.
    """
    resolved = match_downloaded_cohort_wheels(
        download_dir,
        cohort,
        mechanism=mechanism,
        endpoint=endpoint,
    )
    for distribution, path in resolved.items():
        verify_artifact_digest(
            mechanism=mechanism,
            endpoint=endpoint,
            name=distribution,
            path=path,
            expected_sha256=cohort.sha256[distribution],
        )
    return resolved


def verify_release_download(
    cohort: LoadedReleaseCohort,
    download_dir: Path,
    *,
    mechanism: str,
    endpoint: str,
) -> dict[str, Path]:
    """Verify every promoted release asset was served with matching bytes.

    Every artifact the cohort manifest declares must appear in ``download_dir``
    under its manifest filename with the exact declared size and digest.

    Args:
        cohort: The loaded release cohort (all twelve manifest artifacts).
        download_dir: The directory the public release assets were fetched into.
        mechanism: The acquisition channel, for the refusal messages.
        endpoint: The public locator (repo slug / tag), for the refusal messages.

    Returns:
        A mapping of cohort artifact name to its verified downloaded path.

    Raises:
        AcquisitionError: If any declared asset is missing, mis-sized, or drifts.
    """
    resolved: dict[str, Path] = {}
    for record in cohort.manifest.artifacts:
        filename = Path(record.path).name
        candidate = download_dir / filename
        if not candidate.is_file():
            refuse_unavailable(
                mechanism=mechanism,
                endpoint=endpoint,
                version=cohort.manifest.version,
                reason=f"release asset {filename!r} ({record.name}) was not served",
                next_step=(f"attach every cohort artifact to {endpoint} before verifying reacquisition"),
            )
        if candidate.stat().st_size != record.size:
            raise AcquisitionError(
                f"{_MISMATCH_PREFIX}: {mechanism} endpoint {endpoint!r} served {filename!r} "
                f"with size {candidate.stat().st_size} but the cohort declares {record.size}",
            )
        verify_artifact_digest(
            mechanism=mechanism,
            endpoint=endpoint,
            name=record.name,
            path=candidate,
            expected_sha256=record.sha256,
        )
        resolved[record.name] = candidate
    return resolved


def venv_bin_dir(venv: Path) -> Path:
    """Return the platform-specific virtualenv executable directory."""
    return venv / ("Scripts" if os.name == "nt" else "bin")


def venv_executable(venv: Path, name: str) -> Path:
    """Return a console-script path inside a virtualenv, with the .exe suffix on Windows."""
    suffix = ".exe" if os.name == "nt" else ""
    return venv_bin_dir(venv) / f"{name}{suffix}"


def _initialize_server_name(stdout: str) -> str | None:
    """Return the server name from the MCP ``initialize`` response, if present."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == 1:
            result = message.get("result")
            if isinstance(result, dict):
                server_info = result.get("serverInfo")
                if isinstance(server_info, dict):
                    name = server_info.get("name")
                    return str(name) if name is not None else None
    return None


def capture_owned_server_launch(
    *,
    server: Path,
    server_args: Sequence[str] = (),
    env: Mapping[str, str],
    cwd: Path,
    timeout_seconds: float = 60.0,
    expected_server_name: str = "cadrumo",
) -> CommandTranscript:
    """Spawn the client's MCP server as an owned subprocess and capture its launch.

    For a pure-client (MCP-only) distribution row, this is the single genuine
    command transcript required by option A: we own the process, so its argv,
    cwd, wall-clock span, exit status, and stream digests are all real. The
    handshake drives the public ``initialize`` protocol to prove the installed
    server launches and identifies as ``cadrumo``; closing stdin then lets the
    stdio server loop end and exit ``0`` cleanly (a killed server would report a
    non-zero exit and could never sit in a passing record). No field is
    fabricated.

    Args:
        server: The absolute installed server executable to launch.
        server_args: Any arguments the client passes the server (e.g. uvx args).
        env: The isolated environment the client provides the server.
        cwd: The working directory to launch the server in.
        timeout_seconds: How long to wait for the handshake and clean exit.
        expected_server_name: The server name the ``initialize`` reply must carry.

    Returns:
        The real :class:`~dev.packaging.evidence.CommandTranscript` of the launch.

    Raises:
        AcquisitionError: If the server fails to identify or does not exit cleanly.
    """
    argv = (str(server), *server_args)
    handshake = "".join(
        json.dumps(message) + "\n"
        for message in (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "owned-launch-capture", "version": "0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
    )
    started_at = datetime.now(UTC)
    process = subprocess.Popen(  # noqa: S603 - the executable is the client's own installed server
        argv,
        cwd=str(cwd),
        env=dict(env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=_UTF_8,
    )
    try:
        stdout, stderr = process.communicate(input=handshake, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise AcquisitionError(
            f"installed MCP server did not complete the launch handshake within {timeout_seconds}s: {argv!r}",
        ) from exc
    completed_at = datetime.now(UTC)

    server_name = _initialize_server_name(stdout)
    if server_name != expected_server_name:
        raise AcquisitionError(
            f"installed MCP server launch did not identify as {expected_server_name!r} "
            f"(got {server_name!r}); stderr: {stderr.strip()[:200]}",
        )
    if process.returncode != 0:
        raise AcquisitionError(
            f"installed MCP server did not exit cleanly on stdin EOF (rc={process.returncode}); "
            f"stderr: {stderr.strip()[:200]}",
        )
    return CommandTranscript.from_output(
        argv=argv,
        cwd=str(cwd),
        started_at=started_at,
        completed_at=completed_at,
        exit_status=process.returncode,
        stdout=stdout,
        stderr=stderr,
        relevant_output=(f"initialize serverInfo.name={server_name}",),
    )


def run_installed_behavior_oracles(
    *,
    cli: Path,
    mcp_server: Path,
    storage_root: Path,
    work_dir: Path,
    cohort: PythonCohort,
    timeout_seconds: float = 180.0,
) -> tuple[InstalledTaxEvidence, InstalledMcpEvidence]:
    """Repeat installed CLI and MCP tax work through the canonical oracles.

    Reuses :func:`dev.packaging.installed_tax_oracle.run_installed_tax_oracle`
    and :func:`dev.packaging.installed_mcp_oracle.run_installed_mcp_oracle`
    rather than re-deriving tax truth, then asserts both reproduce the grounded
    target value. The oracle imports are deferred so the pure digest helpers in
    this module stay importable without the ``mcp`` dependency.

    Args:
        cli: The acquired ``aeat`` executable to drive.
        mcp_server: The acquired ``cadrumo-mcp`` executable to drive.
        storage_root: A fresh isolated storage root (both oracles get subdirs).
        work_dir: An execution cwd outside any source checkout.
        cohort: The exact immutable Python cohort whose installed bytes are exercised.
        timeout_seconds: Per-command timeout for the oracle subprocesses.

    Returns:
        The retained tax and MCP evidence records.

    Raises:
        AcquisitionError: If either oracle fails to reproduce the target value.
    """
    from .installed_mcp_oracle import run_installed_mcp_oracle
    from .installed_tax_oracle import run_installed_tax_oracle

    tax_evidence = run_installed_tax_oracle(
        cli,
        storage_root=storage_root / "tax-state",
        work_dir=work_dir / "tax-work",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        timeout_seconds=timeout_seconds,
    )
    if tax_evidence.target_value != EXPECTED_ORACLE_TARGET_VALUE:
        raise AcquisitionError(
            f"installed CLI oracle target value drifted: expected {EXPECTED_ORACLE_TARGET_VALUE}, "
            f"got {tax_evidence.target_value!r}",
        )
    mcp_evidence = run_installed_mcp_oracle(
        mcp_server,
        storage_root=storage_root / "mcp-state",
        work_dir=work_dir / "mcp-work",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.sha256["cadrumo-harness"],
        timeout_seconds=timeout_seconds,
    )
    if mcp_evidence.target_value != EXPECTED_ORACLE_TARGET_VALUE:
        raise AcquisitionError(
            f"installed MCP oracle target value drifted: expected {EXPECTED_ORACLE_TARGET_VALUE}, "
            f"got {mcp_evidence.target_value!r}",
        )
    return tax_evidence, mcp_evidence


__all__ = [
    "EXPECTED_ORACLE_TARGET_VALUE",
    "HARNESS_DISTRIBUTION",
    "PYTHON_COHORT_WHEEL_NAMES",
    "AcquisitionError",
    "capture_owned_server_launch",
    "match_downloaded_cohort_wheels",
    "refuse_digest_mismatch",
    "refuse_unavailable",
    "require_command_succeeded",
    "run_installed_behavior_oracles",
    "sha256_bytes",
    "venv_bin_dir",
    "venv_executable",
    "verify_artifact_digest",
    "verify_python_cohort_download",
    "verify_release_download",
]
