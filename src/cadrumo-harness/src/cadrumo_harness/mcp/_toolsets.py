"""Group the manifest-derived tools into domain toolsets.

Dumping the whole verb tree into ``tools/list`` crowds out the user's question
and degrades tool selection, so the console groups the common surfaces into a
small closed set of domain toolsets. The five toolsets -
``renta``, ``iva``, ``ledger``, ``censo``, ``modelo-lifecycle`` - are the curated
common path; verbs outside them are reached through the ``search`` + ``execute``
meta-tool fallback, so a toolset is a curated subset, never a full partition.

Membership is DERIVED, never hand-listed. ``ledger`` and ``modelo-lifecycle`` map
directly onto their live operator-surface manifest domains
(:class:`~application.operator_surface.MountedCommandDomain`). The three
tax-concept toolsets are finer than the family-granular manifest can express, so
they key on the command tree's own stable segment tokens - the census surface
(Modelo 036), the IVA wallet surface, and the
renta draft (borrador) surface. In every case the member set is computed against
the live command keys, so a verb added to any of these surfaces joins its toolset
automatically and the console cannot drift from the CLI.

This module owns no MCP protocol detail; it reads the manifest and the command
keys and emits SDK-independent pydantic records, so it is unit-tested directly.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from cadrumo.application.operator_surface import (
    MountedCommandDomain,
)
from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION
from cadrumo.entrypoints.cli.command_api import is_exposable_command

from ._capability_manifest import build_operator_surface_manifest

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class Toolset(StrEnum):
    """The closed set of curated domain toolsets the console groups tools into."""

    RENTA = "renta"
    IVA = "iva"
    LEDGER = "ledger"
    CENSO = "censo"
    MODELO_LIFECYCLE = "modelo-lifecycle"


class ToolsetGroup(BaseModel):
    """One toolset and the command keys derived into it from the live surface."""

    model_config = _STRICT_FROZEN

    toolset: Toolset
    command_keys: tuple[str, ...] = ()


def _family_domain_map() -> dict[str, MountedCommandDomain]:
    """Map each normalized command-family child token to its manifest domain."""
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    return {family.child.replace("-", "_"): family.domain for family in contract.command_families}


def _domain_for_key(command_key: str, family_map: dict[str, MountedCommandDomain]) -> MountedCommandDomain | None:
    """Resolve a command key's owning manifest domain, or ``None`` if unmounted."""
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return family_map.get(family_token)


def toolset_for_command(command_key: str, *, family_map: dict[str, MountedCommandDomain]) -> Toolset | None:
    """Classify one command key into its curated toolset, or ``None`` for the tail.

    The tax-concept toolsets carve out of the modelo domain first (the census and
    IVA-wallet surfaces are Modelo verbs a client would expect grouped by tax
    concept, not lumped under the generic lifecycle), then the remaining domain
    families map through the manifest. A key that matches no curated toolset falls
    to the meta-tool fallback.

    Returns:
        The owning :class:`Toolset`, or ``None`` when the key is long-tail.
    """
    segments = set(command_key.split("."))
    if "m036" in segments or "censo" in segments:
        return Toolset.CENSO
    if "iva_wallet" in segments:
        return Toolset.IVA
    if command_key.startswith("app.live.borrador.100"):
        return Toolset.RENTA
    domain = _domain_for_key(command_key, family_map)
    if domain is MountedCommandDomain.LEDGER:
        return Toolset.LEDGER
    if domain is MountedCommandDomain.MODELO:
        return Toolset.MODELO_LIFECYCLE
    return None


#: The hard cap on simultaneously-active toolsets. Activation is an enhancement
#: that widens the advertised surface within the persona scope; a cap keeps
#: the surface from creeping back toward the flat listing the core surface
#: exists to avoid.
MAX_ACTIVE_TOOLSETS = 3


def command_keys_for_toolsets(active: frozenset[Toolset]) -> frozenset[str]:
    """Return every command key belonging to an active toolset.

    The union of the member keys of the active groups, derived from the live
    toolset membership so it cannot drift from the manifest.
    """
    if not active:
        return frozenset[str]()
    members = {group.toolset: group.command_keys for group in build_toolsets()}
    keys: set[str] = set()
    for toolset in active:
        keys.update(members.get(toolset, ()))
    return frozenset(keys)


def build_toolsets() -> tuple[ToolsetGroup, ...]:
    """Derive the toolset membership from the live manifest and command keys.

    Every exposable command key is classified once through
    :func:`toolset_for_command`; the result is one :class:`ToolsetGroup` per
    :class:`Toolset` in declaration order, each carrying its sorted member keys.
    Long-tail keys belong to no group and are omitted.

    Returns:
        One :class:`ToolsetGroup` per toolset, in :class:`Toolset` order.
    """
    from cadrumo.entrypoints.cli.command_api import command_schema_refs

    family_map = _family_domain_map()
    members: dict[Toolset, list[str]] = {toolset: [] for toolset in Toolset}
    for ref in command_schema_refs():
        key = ref.command
        if not is_exposable_command(key):
            continue
        toolset = toolset_for_command(key, family_map=family_map)
        if toolset is not None:
            members[toolset].append(key)
    return tuple(ToolsetGroup(toolset=toolset, command_keys=tuple(sorted(keys))) for toolset, keys in members.items())
