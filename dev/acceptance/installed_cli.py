"""Shared fresh-process adapter for installed acceptance CLI journeys.

The adapter owns only the isolated child environment, stdin-only profile
credential delivery, envelope decoding, and sanitized command evidence.  Each
acceptance package owns its scenario inputs, assertions, and receipt schema.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.domain.calculations.registry.authority_store import (
    AUTHORITY_DESCRIPTOR_FILENAME,
    AuthorityDescriptor,
    AuthorityStoreError,
)
from dev.product_environment import clean_product_env


class InstalledCliError(RuntimeError):
    """An installed command did not produce an accepted public envelope."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str = "installed_cli_failure",
        commands: tuple[CommandEvidence, ...] = (),
    ) -> None:
        """Keep only sanitized public command evidence alongside the exception."""
        self.diagnostic_code = diagnostic_code
        self.commands = commands
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    """Sanitized result of one fresh installed CLI process."""

    command: str
    returncode: int
    status: str
    notice_codes: tuple[str, ...]
    refusal: str | None = None
    """The error's typed category and reason, for example ``REFUSED/KDF_RESOURCE_LIMIT``.

    Only enum-shaped tokens are kept, so a refusal names its cause in a receipt
    without carrying any message text, path or value.
    """
    error_code: str | None = None


def build_installed_cli_environment(
    *, storage_root: Path, authority_root: Path, runtime_socket_dir: Path | None = None
) -> dict[str, str]:
    """Build the allowlisted product environment for one isolated child process."""
    environment = clean_product_env()
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_AUTHORITY_ROOT": str(authority_root),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if runtime_socket_dir is not None:
        environment["CADRUMO_STORAGE_ROOT"] = str(storage_root)
        environment["CADRUMO_RUNTIME_SOCKET_DIR"] = str(runtime_socket_dir)
    return environment


class InstalledCli:
    """Fresh-process adapter for public commands from an installed executable."""

    def __init__(
        self,
        executable: Path,
        *,
        storage_root: Path,
        authority_root: Path,
        passphrase: str,
        runtime_socket_dir: Path | None = None,
        cli_argument_prefix: tuple[str, ...] = (),
    ) -> None:
        """Bind the executable to one isolated store and authority tree."""
        self.executable = executable.resolve(strict=True)
        self.storage_root = storage_root.resolve()
        self.authority_root = authority_root.resolve(strict=True)
        self.passphrase = passphrase
        self.runtime_socket_dir = runtime_socket_dir
        self._cli_argument_prefix = tuple(cli_argument_prefix)
        self.commands: list[CommandEvidence] = []

    @property
    def cli_argument_prefix(self) -> tuple[str, ...]:
        """Immutable interpreter arguments before the public CLI's own options."""
        return self._cli_argument_prefix

    def run(
        self,
        args: Sequence[str],
        *,
        authenticated: bool = True,
        allow_error: bool = False,
        stdin_payload: str | None = None,
        command: str | None = None,
    ) -> dict[str, Any]:
        """Run one JSON command and retain sanitized public status evidence."""
        command_identity = command or " ".join(args[:4])
        completed = self._execute(("--format", "json"), args, authenticated=authenticated, stdin_payload=stdin_payload)
        try:
            document = decode_cli_document(completed.stdout, completed.stderr)
        except json.JSONDecodeError as exc:
            self.commands.append(
                CommandEvidence(
                    command=command_identity,
                    returncode=completed.returncode,
                    status="non_json_failure",
                    notice_codes=(),
                    error_code="acceptance.installed_cli.non_json_failure",
                )
            )
            if allow_error:
                return {
                    "status": "error",
                    "error": {
                        "code": "acceptance.installed_cli.non_json_failure",
                        "context": {
                            "returncode": completed.returncode,
                            "stderr_length": len(completed.stderr),
                            "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
                        },
                    },
                }
            raise InstalledCliError(
                f"{command_identity}: no CLI JSON envelope",
                diagnostic_code="acceptance.installed_cli.non_json_failure",
                commands=tuple(self.commands),
            ) from exc
        notices = document.get("notices", [])
        self.commands.append(
            CommandEvidence(
                command=command_identity,
                returncode=completed.returncode,
                status=str(document.get("status")),
                notice_codes=tuple(
                    sorted(
                        str(notice.get("code"))
                        for notice in notices
                        if isinstance(notice, dict) and notice.get("code") is not None
                    )
                ),
                refusal=typed_refusal(document),
                error_code=_error_code(document) if document.get("status") == "error" else None,
            )
        )
        if completed.returncode != 0 and not allow_error:
            refusal = typed_refusal(document)
            cause = _error_code(document) if refusal is None else f"{_error_code(document)}, {refusal}"
            raise InstalledCliError(
                f"{command_identity}: command failed ({cause})",
                diagnostic_code=_error_code(document),
                commands=tuple(self.commands),
            )
        return document

    def run_text(self, args: Sequence[str], *, authenticated: bool = True, command: str | None = None) -> str:
        """Run one command in its default text format and return its standard output."""
        completed = self._execute((), args, authenticated=authenticated, stdin_payload=None)
        if completed.returncode != 0:
            raise InstalledCliError(
                f"{command or ' '.join(args[:4])}: text command failed (exit_code={completed.returncode})"
            )
        return completed.stdout

    def _execute(
        self,
        global_options: Sequence[str],
        args: Sequence[str],
        *,
        authenticated: bool,
        stdin_payload: str | None,
    ) -> subprocess.CompletedProcess[str]:
        """Run one fresh child with the isolated environment and stdin-only credential."""
        if authenticated and stdin_payload is not None:
            raise ValueError("authenticated command cannot also supply a custom stdin payload")
        argv = [str(self.executable), *self.cli_argument_prefix, *global_options]
        input_text = stdin_payload
        if authenticated:
            argv.append("--profile-secrets-stdin")
            input_text = json.dumps({"profile_passphrase": self.passphrase}, separators=(",", ":"))
        argv.extend(args)
        return subprocess.run(  # noqa: S603 - executable is an explicit acceptance input
            argv,
            check=False,
            capture_output=True,
            cwd=self.storage_root,
            env=build_installed_cli_environment(
                storage_root=self.storage_root,
                authority_root=self.authority_root,
                runtime_socket_dir=self.runtime_socket_dir,
            ),
            input=input_text if input_text is not None else "",
            text=True,
            timeout=180,
            encoding="utf-8",
        )

    def create_profile(self, *, year: int) -> None:
        """Create and complete the shared synthetic natural-person profile."""
        payload = json.dumps(
            {"passphrase": self.passphrase, "passphrase_confirmation": self.passphrase}, separators=(",", ":")
        )
        self.run(
            profile_create_args(year),
            authenticated=False,
            stdin_payload=payload,
            command="config profile create",
        )
        self.run(("config", "profile", "complete-setup"))


def profile_create_args(year: int) -> tuple[str, ...]:
    """Return the shared synthetic profile admission command for one tax year."""
    return (
        "config",
        "profile",
        "create",
        f"income-{year}",
        "--quiet",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "12345678Z",
        "--name",
        "Ada",
        "--surnames",
        "Synthetic",
        "--fiscal-residency",
        "resident_irpf",
        "--tax-residence-jurisdiction-scope",
        "common_regime",
        "--tax-residence-ccaa",
        "madrid",
        "--address-postcode",
        "28001",
        "--irpf-income-categories",
        "actividad_economica",
        "--activity",
        "software services",
        "--activity-start-date",
        f"{year}-01-01",
        "--taxation-type",
        "1",
        "--taxpayer-sex",
        "M",
        "--taxpayer-marital-status",
        "1",
        "--situacion-familiar",
        "soltero",
        "--taxpayer-birth-date",
        f"{year - 35}-06-15",
        "--irpf-estimation-regime",
        "directa_normal",
        "--irpf-special-regime",
        "general",
        "--iva-regime",
        "GENERAL",
        "--iva-m303-regime-composition",
        "general",
        "--no-iva-redeme-enrolled",
        "--no-iva-cash-accounting-regime-enrolled",
        "--no-iva-voluntary-sii-enrolled",
        "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        "--no-has-employees",
        "--no-pays-professionals-with-retencion",
        "--no-pays-rent-with-retencion",
        "--no-pays-capital-income-with-retencion",
        "--no-does-intracomunitario",
        "--no-third-party-transactions-above-347-threshold",
        "--no-bienes-extranjero-above-threshold",
        "--no-monedas-virtuales-extranjero-above-threshold",
        "--no-premio-loteria-gravamen-especial-sin-retencion",
        "--secrets-stdin",
    )


def authority_generation(authority_root: Path) -> str:
    """Read the selected authority generation from its public descriptor."""
    try:
        return AuthorityDescriptor.read(authority_root / AUTHORITY_DESCRIPTOR_FILENAME).logical_generation
    except AuthorityStoreError as exc:
        raise InstalledCliError(f"authority descriptor is unavailable: {exc}") from exc


def _embedded_cli_documents(text: str, decoder: json.JSONDecoder) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            candidate, _end = decoder.raw_decode(text, offset)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "schema_version" in candidate and "status" in candidate:
            candidates.append(candidate)
    return candidates


def decode_cli_document(stdout: str, stderr: str) -> dict[str, Any]:
    """Decode the CLI envelope even when diagnostics precede it on stderr."""
    decoder = json.JSONDecoder()
    for stream in (stdout, stderr):
        text = stream.strip()
        if not text:
            continue
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            candidates = _embedded_cli_documents(text, decoder)
            if candidates:
                return candidates[-1]
        else:
            if isinstance(document, dict):
                return document
    raise json.JSONDecodeError("no CLI JSON envelope", stdout or stderr, 0)


_ENUM_TOKEN = re.compile(r"[A-Z][A-Z0-9_]{1,63}")


def typed_refusal(document: dict[str, Any]) -> str | None:
    """Return an error envelope's ``category/reason`` when both are enum-shaped tokens.

    The reason is the typed ``context.refusal`` a refusal carries -- for example
    the custody refusal's ``KDF_RESOURCE_LIMIT`` -- which the error code alone
    does not name. Anything that is not an enum token is dropped rather than
    echoed, so free text or a value placed in the context can never reach
    evidence.
    """
    error = document.get("error")
    if not isinstance(error, dict):
        return None
    context = error.get("context")
    reason = context.get("refusal") if isinstance(context, dict) else None
    if (
        reason is None
        and error.get("code") == "REFUSED_LOCAL_RUNTIME"
        and isinstance(context, dict)
        and isinstance(context.get("reason"), str)
        and context.get("reason") in {code.value for code in RuntimeRefusalCode}
    ):
        return f"REFUSED/{context['reason']}"
    if not isinstance(reason, str) or not _ENUM_TOKEN.fullmatch(reason):
        return None
    category = error.get("category")
    return f"{category}/{reason}" if isinstance(category, str) and _ENUM_TOKEN.fullmatch(category) else reason


def _error_code(document: dict[str, Any]) -> str:
    error = document.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and code.replace("_", "").replace(".", "").isalnum():
        return code
    return "unknown"
