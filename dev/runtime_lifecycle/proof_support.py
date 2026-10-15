"""Generic helpers for disposable built-package runtime proofs."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from uuid import UUID

import psutil

from .caller_owned_root import AcceptanceError, Programs, require, run_cli

_TAXPAYER_FACTS = (
    *("--entity-type", "natural_person", "--tax-id", "12345678Z", "--name", "Daniel", "--surnames", "Persona"),
    *("--activity", "consultoria", "--activity-start-date", "2026-01-01"),
    *("--irpf-income-categories", "actividad_economica", "--irpf-estimation-regime", "directa_normal"),
    *("--iva-regime", "GENERAL", "--tax-residence-jurisdiction-scope", "common_regime"),
    *("--iva-m303-regime-composition", "general", "--no-iva-redeme-enrolled"),
    *("--no-iva-cash-accounting-regime-enrolled", "--no-iva-voluntary-sii-enrolled"),
    "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
    *("--fiscal-residency", "resident_irpf", "--tax-residence-ccaa", "madrid"),
)
"""Synthetic taxpayer facts for these disposable development proofs."""


@dataclass(frozen=True, slots=True)
class Profile:
    """Synthetic profile coordinates; a password is disclosed only through protected stdin."""

    name: str
    password: str = field(repr=False)
    profile_id: UUID | None = None
    inventory: tuple[tuple[str, str, bool], ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    """Kernel coordinates captured from an actual spawned invocation."""

    pid: int
    birth: float
    image: Path

    @classmethod
    def capture(cls, pid: int) -> ProcessIdentity:
        """Retain birth and executable; fail if the invocation cannot be observed."""
        process = psutil.Process(pid)
        identity = cls(pid, process.create_time(), Path(process.exe()).resolve(strict=True))
        require(identity.matches(process), "spawned invocation changed during identity capture")
        return identity

    def matches(self, process: psutil.Process) -> bool:
        """Revalidate this exact live kernel incarnation."""
        return bool(
            process.pid == self.pid
            and process.is_running()
            and process.create_time() == self.birth
            and psutil.Process(self.pid).create_time() == self.birth
            and Path(process.exe()).resolve(strict=True) == self.image
        )


def verified_relay(process_id: object, relay: Path, invocation: ProcessIdentity | None) -> bool:
    """Require the packaged relay to be the retained invocation or its live descendant."""
    if type(process_id) is not int or invocation is None:
        return False
    try:
        peer = psutil.Process(process_id)
        peer_identity = ProcessIdentity.capture(process_id)
        if peer_identity.image != relay.resolve(strict=True):
            return False
        chain = [peer, *peer.parents()]
        for index, process in enumerate(chain):
            if process.pid != invocation.pid:
                continue
            if not invocation.matches(process):
                return False
            branch = [ProcessIdentity.capture(item.pid) for item in chain[: index + 1]]
            return (
                all(parent.birth <= child.birth for child, parent in pairwise(branch))
                and all(psutil.Process(child.pid).ppid() == parent.pid for child, parent in pairwise(branch))
                and all(identity.matches(psutil.Process(identity.pid)) for identity in branch)
                and peer_identity.matches(peer)
            )
        return False
    except (psutil.Error, OSError, AcceptanceError):
        return False


def create_profile(programs: Programs, environment: Mapping[str, str], name: str) -> Profile:
    """Create a disposable profile through the package's person-facing command."""
    password = secrets.token_urlsafe(32)
    code, envelope = run_cli(
        programs,
        environment,
        "config",
        "profile",
        "create",
        name,
        "--quiet",
        "--secrets-stdin",
        secret={"passphrase": password, "passphrase_confirmation": password},
    )
    require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile create: {code} {envelope}")
    return Profile(name=name, password=password)


def identify_profile(programs: Programs, environment: Mapping[str, str], profile: Profile) -> Profile:
    """Read the committed active profile UUID through the canonical public tax listing."""
    code, document = run_cli(
        programs,
        {**environment, "CADRUMO_CLI_REVEAL_IDENTIFIERS": "true"},
        "config",
        "profile",
        "list",
    )
    require(code == 0 and document.get("status") in {"success", "warning"}, "profile listing refused")
    listing = document.get("result") or {}
    rows = listing.get("profiles") if isinstance(listing, dict) else None
    if not isinstance(rows, list):
        raise AcceptanceError("runtime profile listing has no committed rows")
    require(len(rows) == 1, "disposable root does not contain exactly one profile")
    matching = [
        row for row in rows if isinstance(row, dict) and row.get("name") == profile.name and row.get("active") is True
    ]
    require(len(matching) == 1, "runtime listing does not select the created profile exactly once")
    identity = matching[0].get("bucket_id")
    require(isinstance(identity, str), "runtime listing omitted the immutable profile identity")
    try:
        profile_id = UUID(identity)
    except ValueError as error:
        raise AcceptanceError("runtime listing returned an invalid profile identity") from error
    return Profile(profile.name, profile.password, profile_id, ((profile.name, identity, True),))


def state_taxpayer(programs: Programs, environment: Mapping[str, str], profile: Profile) -> None:
    """State the synthetic taxpayer facts and complete the setup, as the person does at the command line."""
    for arguments in (
        ("config", "profile", "edit", "--quiet", *_TAXPAYER_FACTS),
        ("config", "profile", "complete-setup"),
    ):
        code, envelope = run_cli(
            programs,
            environment,
            "--profile-secrets-stdin",
            *arguments,
            secret={"profile_passphrase": profile.password},
        )
        require(code == 0, f"{' '.join(arguments[:3])}: {code} {envelope}")


def package_identity(package: Path | None) -> dict[str, object]:
    """Name the package under test by its manifest digest and build record."""
    require(package is not None, "proof artifact identity requires a built package")
    if package is None:
        raise AcceptanceError("no built package was supplied")
    manifest = package / "data" / "package-manifest.json"
    build = package / "data" / "build.json"
    require(manifest.is_file() and build.is_file(), "built package has no manifest or build identity")
    return {
        "package": str(package),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "build": json.loads(build.read_text(encoding="utf-8")),
    }


def started_processes() -> list[str]:
    """List this driver's descendant processes that are still running."""
    survivors = []
    for child in psutil.Process(os.getpid()).children(recursive=True):
        with suppress(psutil.Error):
            if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                survivors.append(f"{child.pid}:{child.name()}")
    return survivors


def acceptance_failure(error: BaseException) -> str | None:
    """Find the contradicted step inside asynchronous task groups."""
    if isinstance(error, AcceptanceError):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            reason = acceptance_failure(inner)
            if reason is not None:
                return reason
    return None
