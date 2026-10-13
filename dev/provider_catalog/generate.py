"""Generate the provider-settings lane catalog from a cadrumo-agent checkout.

cadrumo-agent owns which provider identities and lanes exist, which settings
field receives each credential, each gateway's default endpoint and the program
each CLI lane runs. This generator reads those declarations statically, with
:mod:`ast`, from an explicitly supplied agent checkout, and writes
``src/cadrumo/_data/provider_settings/catalog.toml``. It never imports the
agent, which is not installed beside Cadrumo.

Sources read (all relative to ``src/cadrumo_agent``):

- ``provider_definitions.py``: ``Provider`` and ``SUPPORTED_PROVIDERS`` (which
  identities take an API key, field ``<identity>_api_key``);
- ``graph/enums.py``: ``ExecutionLane``, its ``provider`` property (lane to
  identity) and ``transport`` property (api lanes);
- ``providers/registry.py``: ``_CORE_PROVIDERS`` display names;
- ``providers/gateways.py``: ``ANTHROPIC_GATEWAYS`` display names, default
  endpoints and token settings;
- ``providers/cli_resolution.py``: ``SYSTEM_CLI_LANES`` programs (gateway lanes
  run the Claude CLI's ACP wrapper);
- ``control/env_registry.py``: whether the agent reads a Claude OAuth token.

The output records the agent's package version and a digest of exactly these
files, so ``--check`` names drift without consulting any version-control tool.
A lane's id is ``<identity>_<transport>``, and every lane must match a
transport ``SUPPORTED_PROVIDERS`` declares for its identity. The Cadrumo-side
development fallback is the settings field ``cadrumo_llm_<credential field>``
when the settings model declares it.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.config import Settings
from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT, UTF_8

AGENT_CHECKOUT_ENV: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
_AGENT_SOURCES: Final = (
    "provider_definitions.py",
    "graph/enums.py",
    "providers/registry.py",
    "providers/gateways.py",
    "providers/cli_resolution.py",
    "control/env_registry.py",
)
_CLAUDE_OAUTH_FIELD: Final = "claude_code_oauth_token"
_GATEWAY_PROGRAM_LANE: Final = "CLAUDE_CLI"


class AgentDefinitionError(ValueError):
    """The agent checkout does not declare what the generator expects."""


@dataclass(frozen=True, slots=True)
class Lane:
    """One generated catalog lane."""

    id: str
    provider: str
    transport: str
    display_name: str
    auth_kind: str
    default_base_url: str | None
    credential_field: str | None
    cli_program: str | None
    development_setting: str | None


def target_path(repo_root: Path | None = None) -> Path:
    """Return the generated catalog's path."""
    return (repo_root or REPO_ROOT) / "src" / "cadrumo" / "_data" / "provider_settings" / "catalog.toml"


def _module(agent_src: Path, relative: str) -> ast.Module:
    path = agent_src / relative
    try:
        return ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise AgentDefinitionError(f"cannot read agent source {relative}: {exc}") from exc


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AgentDefinitionError(f"class {name} not found")


def _assigned(module: ast.Module, name: str) -> ast.expr:
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return node.value
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AgentDefinitionError(f"assignment {name} not found")


def _attribute_chain(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def _unwrap_call(node: ast.expr) -> ast.expr:
    """Return the first argument of a wrapper call such as ``MappingProxyType({...})``."""
    while isinstance(node, ast.Call) and node.args and not isinstance(node.args[0], ast.Constant):
        if isinstance(node.args[0], ast.Dict | ast.Tuple | ast.Call):
            node = node.args[0]
            continue
        break
    return node


def _string(node: ast.expr | None, what: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise AgentDefinitionError(f"{what} is not a string literal")


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _identities(module: ast.Module) -> tuple[dict[str, bool], set[tuple[str, str]]]:
    """Return ``{identity: uses_api_key}`` and the declared (identity, transport) pairs."""
    members = {
        target.id: _string(statement.value, f"Provider.{target.id}")
        for statement in _class(module, "Provider").body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    rows = _assigned(module, "SUPPORTED_PROVIDERS")
    if not isinstance(rows, ast.Tuple):
        raise AgentDefinitionError("SUPPORTED_PROVIDERS is not a tuple")
    identities: dict[str, bool] = {}
    pairs: set[tuple[str, str]] = set()
    for row in rows.elts:
        if not isinstance(row, ast.Call) or not row.args:
            raise AgentDefinitionError("SUPPORTED_PROVIDERS row is not a ProviderDefinition call")
        chain = _attribute_chain(row.args[0])
        if len(chain) < 2 or chain[-2] not in members:
            raise AgentDefinitionError("SUPPORTED_PROVIDERS row does not name a Provider member")
        uses_api_key = _keyword(row, "uses_api_key")
        identities[members[chain[-2]]] = not (isinstance(uses_api_key, ast.Constant) and uses_api_key.value is False)
        transports = row.args[1] if len(row.args) > 1 else None
        if not isinstance(transports, ast.Tuple) or not transports.elts:
            raise AgentDefinitionError("SUPPORTED_PROVIDERS row declares no transports")
        pairs.update((members[chain[-2]], _attribute_chain(element)[-1].lower()) for element in transports.elts)
    return identities, pairs


def _lanes(module: ast.Module, identities: dict[str, bool]) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Return lane member to id, lane id to identity, and the api lane ids."""
    lane_class = _class(module, "ExecutionLane")
    member_ids: dict[str, str] = {}
    literal_members: set[str] = set()
    for statement in lane_class.body:
        if not isinstance(statement, ast.Assign) or not isinstance(statement.targets[0], ast.Name):
            continue
        member = statement.targets[0].id
        if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            member_ids[member] = statement.value.value
            literal_members.add(member)
        else:
            chain = _attribute_chain(statement.value)
            if len(chain) < 2 or chain[-1] != "value" or chain[-2].lower() not in identities:
                raise AgentDefinitionError(f"ExecutionLane.{member} is neither a literal nor a Provider value")
            member_ids[member] = chain[-2].lower()
    overrides: dict[str, str] = {}
    api_members: set[str] = set()
    for function in lane_class.body:
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if function.name == "provider" and isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                lane = _attribute_chain(node.test.comparators[0])[-1]
                returned = next((n for n in node.body if isinstance(n, ast.Return)), None)
                if returned is not None and returned.value is not None:
                    overrides[lane] = _attribute_chain(returned.value)[-1].lower()
            if function.name == "transport" and isinstance(node, ast.Set):
                api_members.update(_attribute_chain(element)[-1] for element in node.elts)
    if api_members != literal_members or set(overrides) != literal_members:
        raise AgentDefinitionError("api lanes, literal lane ids and provider overrides disagree")
    identity = {member_ids[member]: overrides.get(member, member_ids[member]) for member in member_ids}
    if set(identity.values()) != set(identities):
        raise AgentDefinitionError("lanes and supported identities disagree")
    return member_ids, identity, {member_ids[member] for member in api_members}


def _display_names(registry: ast.Module, member_ids: dict[str, str]) -> dict[str, str]:
    core = _assigned(registry, "_CORE_PROVIDERS")
    if not isinstance(core, ast.Tuple):
        raise AgentDefinitionError("_CORE_PROVIDERS is not a tuple")
    names: dict[str, str] = {}
    for row in core.elts:
        if not isinstance(row, ast.Call) or len(row.args) < 2:
            raise AgentDefinitionError("_CORE_PROVIDERS row is not a _core call")
        names[member_ids[_attribute_chain(row.args[0])[-1]]] = _string(row.args[1], "core display name")
    return names


def _gateways(gateways: ast.Module, member_ids: dict[str, str]) -> dict[str, tuple[str, str | None, str]]:
    """Return ``{lane: (display_name, base_url_default, token_setting)}``."""
    rows = _unwrap_call(_assigned(gateways, "ANTHROPIC_GATEWAYS"))
    if not isinstance(rows, ast.Tuple):
        raise AgentDefinitionError("ANTHROPIC_GATEWAYS is not a tuple")
    table: dict[str, tuple[str, str | None, str]] = {}
    for row in rows.elts:
        if not isinstance(row, ast.Call):
            raise AgentDefinitionError("gateway row is not a call")
        lane = member_ids[_attribute_chain(_keyword(row, "provider") or ast.Constant(None))[-1]]
        default = _keyword(row, "base_url_default")
        base_url = None if isinstance(default, ast.Constant) and default.value is None else _string(default, "base url")
        table[lane] = (
            _string(_keyword(row, "display_name"), "gateway display name"),
            base_url,
            _string(_keyword(row, "token_setting"), "gateway token setting"),
        )
    return table


def _programs(cli_resolution: ast.Module, member_ids: dict[str, str]) -> dict[str, str]:
    table = _unwrap_call(_assigned(cli_resolution, "SYSTEM_CLI_LANES"))
    if not isinstance(table, ast.Dict):
        raise AgentDefinitionError("SYSTEM_CLI_LANES is not a mapping")
    programs: dict[str, str] = {}
    for key, value in zip(table.keys, table.values, strict=True):
        if key is None:
            raise AgentDefinitionError("SYSTEM_CLI_LANES uses an unpacked entry")
        programs[member_ids[_attribute_chain(key)[-1]]] = _string(value, "cli program")
    return programs


def _reads_claude_oauth(env_registry: ast.Module) -> bool:
    return any(isinstance(node, ast.Constant) and node.value == _CLAUDE_OAUTH_FIELD for node in ast.walk(env_registry))


def _build_lanes(agent_src: Path) -> tuple[Lane, ...]:
    """Read every lane from the agent sources under ``agent_src``."""
    identities, declared_pairs = _identities(_module(agent_src, "provider_definitions.py"))
    member_ids, identity_of, api_lanes = _lanes(_module(agent_src, "graph/enums.py"), identities)
    core_names = _display_names(_module(agent_src, "providers/registry.py"), member_ids)
    gateways = _gateways(_module(agent_src, "providers/gateways.py"), member_ids)
    programs = _programs(_module(agent_src, "providers/cli_resolution.py"), member_ids)
    claude_oauth = _reads_claude_oauth(_module(agent_src, "control/env_registry.py"))
    gateway_program = programs[member_ids[_GATEWAY_PROGRAM_LANE]]
    identities_with_api = {identity_of[lane] for lane in api_lanes}

    lanes: list[Lane] = []
    for lane_id in member_ids.values():
        identity = identity_of[lane_id]
        gateway = gateways.get(lane_id)
        transport = "api" if lane_id in api_lanes else "cli"
        if (identity, transport) not in declared_pairs:
            raise AgentDefinitionError(f"lane {lane_id} is not a declared {identity}/{transport} pair")
        if gateway is not None:
            auth_kind, field, base_url = "api_key_with_base_url", gateway[2], gateway[1]
        elif transport == "api":
            auth_kind, field, base_url = "api_key", f"{identity}_api_key", None
        elif identity in identities_with_api or not identities[identity]:
            # The identity's key belongs to its api lane; this cli lane signs in.
            oauth = identity == "claude" and claude_oauth
            auth_kind = "oauth_token_or_provider_sign_in" if oauth else "provider_sign_in_only"
            field, base_url = (_CLAUDE_OAUTH_FIELD if oauth else None), None
        else:
            auth_kind, field, base_url = "api_key", f"{identity}_api_key", None
        if lane_id not in core_names and gateway is None:
            raise AgentDefinitionError(f"lane {lane_id} has no display name")
        program = None if transport == "api" else programs.get(lane_id, gateway_program if gateway else None)
        if transport == "cli" and program is None:
            raise AgentDefinitionError(f"cli lane {lane_id} has no program")
        setting = f"cadrumo_llm_{field}"
        lanes.append(
            Lane(
                id=f"{identity}_{transport}",
                provider=identity,
                transport=transport,
                display_name=gateway[0] if gateway is not None else core_names[lane_id],
                auth_kind=auth_kind,
                default_base_url=base_url,
                credential_field=field,
                cli_program=program,
                development_setting=setting
                if auth_kind in {"api_key", "api_key_with_base_url"} and setting in Settings.model_fields
                else None,
            ),
        )
    if {(lane.provider, lane.transport) for lane in lanes} != declared_pairs:
        raise AgentDefinitionError("declared provider transports and execution lanes disagree")
    order = list(identities)
    lanes.sort(key=lambda lane: (order.index(lane.provider), lane.transport != "api", lane.id))
    return tuple(lanes)


def agent_lanes(agent_root: Path) -> tuple[tuple[Lane, ...], str, str]:
    """Return the lanes, agent version and source digest read from ``agent_root``."""
    agent_src = agent_root / "src" / "cadrumo_agent"
    digest = hashlib.sha256()
    for relative in _AGENT_SOURCES:
        digest.update(relative.encode(UTF_8) + b"\0")
        try:
            digest.update((agent_src / relative).read_bytes().replace(b"\r\n", b"\n"))
        except OSError as exc:
            raise AgentDefinitionError(f"cannot read agent source {relative}: {exc}") from exc
        digest.update(b"\0")
    try:
        project = parse_toml((agent_root / "pyproject.toml").read_text(encoding=UTF_8))
        version = str(project["project"]["version"])
    except (OSError, KeyError, TypeError) as exc:
        raise AgentDefinitionError(f"cannot read the agent version: {exc}") from exc

    try:
        lanes = _build_lanes(agent_src)
    except KeyError as exc:
        raise AgentDefinitionError(f"agent definitions reference an undeclared lane or identity: {exc}") from exc
    return lanes, version, digest.hexdigest()


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_catalog(lanes: tuple[Lane, ...], version: str, digest: str) -> str:
    """Render the catalog document."""
    lines = [
        "# GENERATED FILE - DO NOT EDIT.",
        "# Regenerate with: just generate-provider-catalog (python -m dev.provider_catalog.generate)",
        "# Source of truth: cadrumo-agent's provider, lane, gateway and CLI definitions.",
        "#",
        "# One entry per cadrumo-agent lane. id is <provider>_<transport>; provider is",
        "# the identity it reaches; credential_field is the agent settings field that",
        "# receives the lane's credential and keys the hosted-agent frame.",
        "",
        "schema_version = 1",
        "",
        "[source]",
        f"agent_version = {_quote(version)}",
        f"agent_source_digest = {_quote(digest)}",
    ]
    for lane in lanes:
        lines += [
            "",
            "[[providers]]",
            f"id = {_quote(lane.id)}",
            f"provider = {_quote(lane.provider)}",
            f"transport = {_quote(lane.transport)}",
            f"display_name = {_quote(lane.display_name)}",
            f"auth_kind = {_quote(lane.auth_kind)}",
            'consumers = ["assistant"]',
        ]
        for key, value in (
            ("default_base_url", lane.default_base_url),
            ("credential_field", lane.credential_field),
            ("cli_program", lane.cli_program),
            ("development_setting", lane.development_setting),
        ):
            if value is not None:
                lines.append(f"{key} = {_quote(value)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the catalog from an agent checkout, or verify it with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-root", type=Path, default=None, help=f"cadrumo-agent checkout (or ${AGENT_CHECKOUT_ENV})."
    )
    parser.add_argument("--check", action="store_true", help="Exit 1 when the committed catalog drifts.")
    args = parser.parse_args(argv)
    checkout = os.environ.get(AGENT_CHECKOUT_ENV)
    root = args.agent_root or (Path(checkout) if checkout is not None and checkout else None)
    if root is None:
        print(f"REFUSED: supply --agent-root or set {AGENT_CHECKOUT_ENV} to a cadrumo-agent checkout.", file=sys.stderr)
        return 2
    try:
        lanes, version, digest = agent_lanes(root.resolve())
    except AgentDefinitionError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    fresh = render_catalog(lanes, version, digest)
    path = target_path()
    if args.check:
        on_disk = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
        if on_disk != fresh.encode(UTF_8):
            print(
                f"DRIFT: {path} differs from cadrumo-agent's definitions; run just generate-provider-catalog",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {path} matches cadrumo-agent {version} ({digest[:12]}).")
        return 0
    path.write_text(fresh, encoding=UTF_8, newline="\n")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
