"""Shared fresh-process adapter for installed acceptance CLI journeys.

The adapter owns only the isolated child environment, stdin-only profile
credential delivery, envelope decoding, and sanitized command evidence.  Each
acceptance package owns its scenario inputs, assertions, and receipt schema.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class InstalledCliError(RuntimeError):
    """An installed command did not produce an accepted public envelope."""


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    """Sanitized result of one fresh installed CLI process."""

    command: str
    returncode: int
    status: str
    notice_codes: tuple[str, ...]


def build_installed_cli_environment(*, storage_root: Path, authority_root: Path) -> dict[str, str]:
    """Build the allowlisted product environment for one isolated child process."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_AUTHORITY_ROOT": str(authority_root),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return environment


class InstalledCli:
    """Fresh-process adapter for public commands from an installed executable."""

    def __init__(self, executable: Path, *, storage_root: Path, authority_root: Path, passphrase: str) -> None:
        """Bind the executable to one isolated store and authority tree."""
        self.executable = executable.resolve(strict=True)
        self.storage_root = storage_root.resolve()
        self.authority_root = authority_root.resolve(strict=True)
        self.passphrase = passphrase
        self.commands: list[CommandEvidence] = []

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
        if authenticated and stdin_payload is not None:
            raise ValueError("authenticated command cannot also supply a custom stdin payload")
        argv = [str(self.executable), "--format", "json"]
        input_text = stdin_payload
        if authenticated:
            argv.append("--profile-secrets-stdin")
            input_text = json.dumps({"profile_passphrase": self.passphrase}, separators=(",", ":"))
        argv.extend(args)
        command_identity = command or " ".join(args[:4])
        completed = subprocess.run(  # noqa: S603 - executable is an explicit acceptance input
            argv,
            check=False,
            capture_output=True,
            cwd=self.storage_root,
            env=build_installed_cli_environment(storage_root=self.storage_root, authority_root=self.authority_root),
            input=input_text,
            text=True,
            timeout=180,
            encoding="utf-8",
        )
        try:
            document = decode_cli_document(completed.stdout, completed.stderr)
        except json.JSONDecodeError as exc:
            if allow_error:
                self.commands.append(
                    CommandEvidence(
                        command=command_identity,
                        returncode=completed.returncode,
                        status="non_json_failure",
                        notice_codes=(),
                    )
                )
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
            raise InstalledCliError(f"{command_identity}: no CLI JSON envelope") from exc
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
            )
        )
        if completed.returncode != 0 and not allow_error:
            raise InstalledCliError(f"{command_identity}: command failed ({_error_code(document)})")
        return document

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
        "--secrets-stdin",
    )


def authority_generation(authority_root: Path) -> str:
    """Read the selected authority generation from its public descriptor."""
    descriptor = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    generation = descriptor.get("logical_generation")
    if not isinstance(generation, str):
        raise InstalledCliError("authority descriptor has no logical generation")
    return generation


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
            if candidates:
                return candidates[-1]
        else:
            if isinstance(document, dict):
                return document
    raise json.JSONDecodeError("no CLI JSON envelope", stdout or stderr, 0)


def _error_code(document: dict[str, Any]) -> str:
    error = document.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and code.replace("_", "").replace(".", "").isalnum():
        return code
    return "unknown"
