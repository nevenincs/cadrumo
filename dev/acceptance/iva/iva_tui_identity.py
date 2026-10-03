"""Installed IVA source, package and authority identity attestation guards."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from importlib import metadata, resources
from pathlib import Path

from cadrumo.core.hashing import hash_file, sha256_hex
from cadrumo.domain.calculations.registry.authority_store import (
    AUTHORITY_DESCRIPTOR_FILENAME,
    AuthorityDescriptor,
    AuthorityStoreError,
)
from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
)

from .iva_tui_contracts import _SOURCE_MODULES, AuthorityIdentity, IvaInstalledTuiError, SourceIdentity
from .iva_tui_projection import _required_text


def _require_reopened_product_identity(
    observed_origin: str,
    observed_init: str,
    observed_version: str,
    product_origin: str | None,
    product_init_sha256: str | None,
    package_version: str | None,
) -> None:
    """Require reopened product identity."""
    if product_origin is not None and observed_origin != product_origin:
        raise IvaInstalledTuiError("fresh installed TUI child product origins differ")
    if product_init_sha256 is not None and observed_init != product_init_sha256:
        raise IvaInstalledTuiError("fresh installed TUI child product initializers differ")
    if package_version is not None and observed_version != package_version:
        raise IvaInstalledTuiError("fresh installed TUI child package versions differ")


def _source_identity(workspace_root: Path) -> SourceIdentity:
    """Hash the exact critical source members before the supported wheel build."""
    root = workspace_root.resolve(strict=True)
    rows: list[tuple[str, str]] = []
    for module_name, relative_path in _SOURCE_MODULES:
        source = root / relative_path
        if not source.is_file():
            raise IvaInstalledTuiError("critical installed-TUI source member is absent")
        rows.append((module_name, sha256_hex(source.read_bytes())))
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return SourceIdentity(manifest_sha256=sha256_hex(payload), module_sha256s=tuple(rows))


def _authority_identity(authority_root: Path) -> AuthorityIdentity:
    """Read and verify the one published authority pair supplied to the run."""
    root = authority_root.resolve(strict=True)
    descriptor_path = root / AUTHORITY_DESCRIPTOR_FILENAME
    if not descriptor_path.is_file():
        raise IvaInstalledTuiError("authority root has no published current descriptor")
    try:
        descriptor = AuthorityDescriptor.read(descriptor_path)
    except AuthorityStoreError as exc:
        raise IvaInstalledTuiError(f"authority descriptor is unavailable: {exc}") from exc
    database_path = root / descriptor.database
    if not database_path.is_file():
        raise IvaInstalledTuiError("authority descriptor names an invalid database member")
    database_sha256, database_size = hash_file(database_path)
    if database_sha256 != descriptor.database_sha256 or database_size != descriptor.database_size:
        raise IvaInstalledTuiError("authority database bytes do not match the descriptor digest")
    return AuthorityIdentity(
        logical_generation=descriptor.logical_generation,
        descriptor_sha256=sha256_hex(descriptor_path.read_bytes()),
        database_sha256=database_sha256,
    )


def _assert_bundled_authority(expected: AuthorityIdentity) -> None:
    """Require the installed wheel to carry the same descriptor and database."""
    authority = resources.files("cadrumo").joinpath("_data", "registry", "authority")
    descriptor_resource = authority.joinpath(AUTHORITY_DESCRIPTOR_FILENAME)
    try:
        descriptor_bytes = descriptor_resource.read_bytes()
        descriptor = json.loads(descriptor_bytes)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise InstalledTuiChildError("installed wheel has no readable bundled authority descriptor") from exc
    if not isinstance(descriptor, dict):
        raise InstalledTuiChildError("installed wheel authority descriptor is not an object")
    database = descriptor.get("database")
    if not isinstance(database, str) or not database:
        raise InstalledTuiChildError("installed wheel authority descriptor has no database member")
    if sha256_hex(descriptor_bytes) != expected.descriptor_sha256:
        raise InstalledTuiChildError("installed wheel authority descriptor differs from the supplied authority")
    try:
        database_bytes = authority.joinpath(database).read_bytes()
    except FileNotFoundError as exc:
        raise InstalledTuiChildError("installed wheel omits the descriptor-selected authority database") from exc
    if sha256_hex(database_bytes) != expected.database_sha256:
        raise InstalledTuiChildError("installed wheel authority database differs from the supplied authority")


def _module_hash_arguments(source: SourceIdentity) -> tuple[str, ...]:
    """Render only module names and digests for the isolated child process."""
    arguments: list[str] = []
    for module_name, digest in source.module_sha256s:
        arguments.extend(("--source-module", f"{module_name}={digest}"))
    return tuple(arguments)


def _parse_module_hashes(items: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """Validate source-module attestations passed by the parent driver."""
    parsed: list[tuple[str, str]] = []
    for item in items:
        module_name, separator, digest = item.partition("=")
        if not separator or not module_name or len(digest) != 64:
            raise InstalledTuiChildError("installed TUI child received an invalid source-module attestation")
        parsed.append((module_name, digest))
    if not parsed or len({module for module, _ in parsed}) != len(parsed):
        raise InstalledTuiChildError("installed TUI child received duplicate or empty source-module attestations")
    return tuple(sorted(parsed))


def _assert_installed_source_modules(
    *, expected_manifest_sha256: str, expected_modules: tuple[tuple[str, str], ...]
) -> None:
    """Prove the critical modules' installed distribution bytes are the source selected for this run.

    Each dotted module name maps to exactly one file under the installed
    distribution root; the child already runs the site-packages product, so
    the file the launcher imports is the file hashed here.
    """
    distribution_root = Path(str(metadata.distribution("cadrumo").locate_file(""))).resolve(strict=True)
    actual: list[tuple[str, str]] = []
    for module_name, expected_digest in expected_modules:
        origin = distribution_root.joinpath(*module_name.split(".")).with_suffix(".py")
        if not origin.is_file():
            raise InstalledTuiChildError("critical installed-TUI module is absent from the installed distribution")
        actual_digest = sha256_hex(origin.read_bytes())
        if actual_digest != expected_digest:
            raise InstalledTuiChildError("installed wheel source member differs from the source selected for this run")
        actual.append((module_name, actual_digest))
    payload = json.dumps(actual, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if sha256_hex(payload) != expected_manifest_sha256:
        raise InstalledTuiChildError("installed critical-source manifest differs from the parent attestation")


def _assert_child_identity(
    document: Mapping[str, object],
    *,
    source: SourceIdentity,
    authority: AuthorityIdentity,
    product_origin: str | None = None,
    product_init_sha256: str | None = None,
    package_version: str | None = None,
) -> tuple[str, str, str]:
    """Require both child processes to attest one installed source/package/authority."""
    observed_origin = _required_text(document, "product_origin")
    observed_init = _required_text(document, "product_init_sha256")
    observed_version = _required_text(document, "package_version")
    if observed_origin != "site-packages":
        raise IvaInstalledTuiError("installed TUI child did not attest a site-packages product origin")
    if document.get("source_manifest_sha256") != source.manifest_sha256:
        raise IvaInstalledTuiError("installed TUI child source manifest differs from the supported wheel build input")
    if document.get("source_module_count") != len(source.module_sha256s):
        raise IvaInstalledTuiError("installed TUI child source-module count differs from the attestation")
    expected_authority = {
        "authority_generation": authority.logical_generation,
        "authority_descriptor_sha256": authority.descriptor_sha256,
        "authority_database_sha256": authority.database_sha256,
    }
    if any(document.get(key) != value for key, value in expected_authority.items()):
        raise IvaInstalledTuiError(
            "installed TUI child authority identity differs from the selected published authority"
        )
    _require_reopened_product_identity(
        observed_origin, observed_init, observed_version, product_origin, product_init_sha256, package_version
    )
    return observed_origin, observed_init, observed_version
