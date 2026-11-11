"""Compare command-line environment names with package declarations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, cast

from .environment_conformance_types import Finding, Reference

_FIELD_ACCEPTS: Final[Mapping[str, frozenset[str]]] = {
    "path": frozenset({"directory", "file", "executable"}),
    "boolean": frozenset({"boolean"}),
    "integer": frozenset({"integer", "port"}),
    "number": frozenset({"number", "integer"}),
    "language": frozenset({"language"}),
    "text": frozenset({"text", "language", "integer", "number", "boolean", "port"}),
}


SERVICE_PROFILE: Final = "cadrumo-agent-service"
"""The agent service's launch profile, whose slots the desktop fills."""


def service_slots(reference: Reference) -> set[str]:
    """The slots the agent service's launch profile declares."""
    for profile in reference.section["profiles"]:
        if profile["name"] == SERVICE_PROFILE:
            return {slot["name"] for slot in profile["slots"]}
    return set()


def accepts_kind(label: str | None, kind: str) -> bool:
    """Check that a component field accepts the declared package kind."""
    return label is not None and kind in _FIELD_ACCEPTS.get(label, frozenset())


def _reads(subject: str, reader: str, name: str, kind: str, settings: Mapping[str, str | None]) -> list[Finding]:
    if name not in settings:
        return [Finding(subject, name, f"{reader} reads no such setting")]
    label = settings[name]
    if label is None:
        return [Finding(subject, name, f"{reader} names it without a settings field to hold a value")]
    if label == "secret":
        return [Finding(subject, name, f"{reader} holds a credential in it; a package name never carries one")]
    if not accepts_kind(label, kind):
        return [Finding(subject, name, f"the package declares kind {kind}, wider than {reader}'s {label} field")]
    return []


def _check_package_or_pin(
    reference: Reference,
    name: str,
    kind: str,
    role: str,
    settings: Mapping[str, str | None],
    temporary_variables: Sequence[str],
) -> list[Finding]:
    check, reader = "command-line-names", "the command line"
    if role == "package":
        if name in settings:
            return _reads(check, reader, name, kind, settings)
        if name != reference.declaration.path_external:
            return [Finding(check, name, "neither the command line reads it nor the host consumes it")]
    elif name not in temporary_variables:
        return [Finding(check, name, "is pinned as a temporary variable the command line does not use")]
    return []


def _check_fixed_cli_name(
    reference: Reference, name: str, kind: str, settings: Mapping[str, str | None], cli: Mapping[str, object]
) -> list[Finding]:
    if name != reference.declaration.authority.name:
        return []
    check = "command-line-names"
    findings = _reads(check, "the command line", name, kind, settings)
    if name not in cast(Sequence[str], cli["authority_variables"]):
        findings.append(Finding(check, name, "is not the setting that names the command line's authority"))
    return findings


def _slot_is_read(reference: Reference, name: str, cli: Mapping[str, object]) -> bool:
    """Whether an installed component reads the slot: the command line its profile folder, the agent service its own.

    The service's own slots are held to what it reads by the runtime's launch check.
    """
    return name in cast(Sequence[str], cli.get("profile_variables", ())) or name in service_slots(reference)


def _check_command_line_entry(
    reference: Reference,
    name: str,
    entry: Mapping[str, str],
    settings: Mapping[str, str | None],
    cli: Mapping[str, object],
) -> list[Finding]:
    check, reader = "command-line-names", "the command line"
    role, kind = entry["role"], entry["kind"]
    if role in {"location", "operator"}:
        return _reads(check, reader, name, kind, settings)
    if role == "package":
        return _check_package_or_pin(reference, name, kind, role, settings, ())
    if role == "pin":
        return _check_package_or_pin(
            reference, name, kind, role, settings, cast(Sequence[str], cli["temporary_variables"])
        )
    if role == "fixed":
        return _check_fixed_cli_name(reference, name, kind, settings, cli)
    if role == "pass" and name in settings:
        return _reads(check, reader, name, kind, settings)
    if role == "slot" and _slot_is_read(reference, name, cli):
        return []
    if not name.startswith(reference.agent["prefix"]):
        return [Finding(check, name, f"role {role} is read by no installed component")]
    return []


def check_command_line_names(reference: Reference, cli: Mapping[str, object]) -> list[Finding]:
    """Hold every name the package sets, passes or lets an operator override to what the command line reads."""
    declaration = reference.declaration
    settings = cast(Mapping[str, str | None], cli["settings"])
    findings: list[Finding] = []
    for name, entry in declaration.names.items():
        findings.extend(_check_command_line_entry(reference, name, entry, settings, cli))
    if set(declaration.temporary) != set(cast(Sequence[str], cli["temporary_variables"])):
        findings.append(
            Finding(
                "command-line-names",
                "temporary variables",
                f"the package pins {sorted(declaration.temporary)}; the command line pins {cli['temporary_variables']}",
            )
        )
    return findings
