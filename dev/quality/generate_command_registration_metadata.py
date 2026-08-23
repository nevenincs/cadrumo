"""Generate the non-authoritative, import-light CLI registration projection."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from cadrumo.entrypoints.cli._command_policy import CommandExecutionPolicy

_LANGUAGES = ("es", "en")
_OUTPUT = Path("src/cadrumo/entrypoints/cli/command_registration_metadata.v1.json")


def source_sha256(source_path: str | Path) -> str:
    """Hash UTF-8 source with platform line endings normalized to LF."""
    source = Path(source_path).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(source.encode()).hexdigest()


def _source_identity(owner: object | None) -> tuple[str | None, str | None]:
    if owner is None:
        return None, None
    module_name = getattr(owner, "__module__", None)
    qualname = getattr(owner, "__qualname__", None)
    if not isinstance(module_name, str) or not isinstance(qualname, str):
        return None, None
    module = importlib.import_module(module_name)
    source_path = inspect.getsourcefile(module)
    if source_path is None:
        return f"{module_name}:{qualname}", None
    digest = source_sha256(source_path)
    return f"{module_name}:{qualname}", digest


def _owner_source_sha256(owner: str) -> str | None:
    """Hash the module named by a stable live-node owner string."""
    if owner == "<none>" or ":" not in owner:
        return None
    module = importlib.import_module(owner.split(":", 1)[0])
    source_path = inspect.getsourcefile(module)
    return None if source_path is None else source_sha256(source_path)


def _policy_record(policy: CommandExecutionPolicy | None) -> dict[str, object] | None:
    if policy is None:
        return None
    classification = policy.classification
    return {
        "capabilities": sorted(classification.capabilities),
        "side_effects": sorted(classification.side_effects),
        "performance": classification.performance,
        "write_route": policy.write_route,
        "destructive": policy.destructive,
        "handoff": policy.handoff,
        "live_write": policy.live_write,
    }


def _observe(language: str) -> dict[str, object]:
    os.environ["CADRUMO_OUTPUT_LANGUAGE"] = language

    from typer.main import get_command

    from cadrumo.core.json_contract import SCHEMA_REGISTRY
    from cadrumo.entrypoints.cli import app, full_command_tree
    from cadrumo.entrypoints.cli._command_policy import execution_policy_for
    from cadrumo.entrypoints.cli._command_schema import _materialized_command_schema_refs
    from cadrumo.entrypoints.cli._command_suggestions import walk_live_command_tree
    from cadrumo.entrypoints.cli._verb_input_schema import (
        _build_materialized_verb_input_schemas,
        _resolve_command,
    )

    references = _materialized_command_schema_refs()
    keys = tuple(reference.command for reference in references)
    schemas = _build_materialized_verb_input_schemas(keys)
    root = get_command(app)
    commands: list[dict[str, object]] = []
    for reference in references:
        key = reference.command
        schema_type = SCHEMA_REGISTRY[key]
        schema_owner, schema_sha = _source_identity(schema_type)
        command, resolved, failure = _resolve_command(root, key)
        if failure is not None or command is None:
            commands.append(
                {
                    "command": key,
                    "schema_name": reference.schema_name,
                    "schema_owner": schema_owner,
                    "schema_source_sha256": schema_sha,
                    "cli_path": None,
                    "parameters": None,
                    "help": "",
                    "hidden": None,
                    "deprecated": None,
                    "policy": None,
                    "handler_owner": None,
                    "source_sha256": None,
                }
            )
            continue
        callback = getattr(command, "callback", None)
        handler_owner, source_sha = _source_identity(callback)
        schema = schemas[key]
        commands.append(
            {
                "command": key,
                "schema_name": reference.schema_name,
                "schema_owner": schema_owner,
                "schema_source_sha256": schema_sha,
                "cli_path": list(resolved),
                "parameters": [parameter.model_dump(mode="json") for parameter in schema.parameters],
                "help": schema.help,
                "hidden": bool(getattr(command, "hidden", False)),
                "deprecated": getattr(command, "deprecated", False),
                "policy": _policy_record(execution_policy_for(callback)),
                "handler_owner": handler_owner,
                "source_sha256": source_sha,
            }
        )

    materialized_root = full_command_tree()
    _ = materialized_root
    nodes = [
        {
            "path": list(node.path),
            "kind": node.kind,
            "loader_owner": node.loader_owner,
            "handler_owner": node.handler_owner,
            "source_sha256": _owner_source_sha256(node.handler_owner),
            "policy": _policy_record(node.execution_policy),
        }
        for node in walk_live_command_tree(app)
    ]
    return {"commands": commands, "nodes": nodes}


def _child_observation(language: str) -> dict[str, object]:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, script, and closed language token
        [sys.executable, "-I", str(Path(__file__).resolve()), "--observe", language],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    decoded = json.loads(completed.stdout)
    if not isinstance(decoded, dict):
        raise TypeError("registration observation must be a JSON object")
    return cast("dict[str, object]", decoded)


def _merge(observations: dict[str, dict[str, object]]) -> dict[str, object]:
    baseline = observations[_LANGUAGES[0]]
    commands_by_language: dict[str, dict[str, dict[str, object]]] = {}
    for language, observation in observations.items():
        raw_commands = observation["commands"]
        if not isinstance(raw_commands, list):
            raise TypeError("registration observation commands must be a list")
        rows = cast("list[dict[str, object]]", raw_commands)
        commands_by_language[language] = {cast("str", row["command"]): row for row in rows}
    identities = tuple(commands_by_language[_LANGUAGES[0]])
    for language in _LANGUAGES[1:]:
        if tuple(commands_by_language[language]) != identities:
            raise RuntimeError(f"localized command registration identities drifted for {language}")
    merged: list[dict[str, object]] = []
    for identity in identities:
        rows = {language: dict(commands_by_language[language][identity]) for language in _LANGUAGES}
        help_by_language = {language: rows[language].pop("help") for language in _LANGUAGES}
        parameters_by_language = {language: rows[language].pop("parameters") for language in _LANGUAGES}
        first = rows[_LANGUAGES[0]]
        for language in _LANGUAGES[1:]:
            if rows[language] != first:
                raise RuntimeError(f"non-localized registration metadata drifted for {identity} / {language}")
        first["help_by_language"] = help_by_language
        first["parameters_by_language"] = parameters_by_language
        merged.append(first)
    for language in _LANGUAGES[1:]:
        if observations[language]["nodes"] != baseline["nodes"]:
            raise RuntimeError(f"live command census drifted by locale: {language}")
    return {"format_version": 1, "commands": merged, "nodes": baseline["nodes"]}


def metadata_differences(expected: object, observed: object, *, path: str = "$") -> tuple[str, ...]:
    """Return stable paths for every structural or scalar disagreement."""
    if type(expected) is not type(observed):
        return (path,)
    if isinstance(expected, dict) and isinstance(observed, dict):
        differences: list[str] = []
        for key in sorted(set(expected) | set(observed)):
            child = f"{path}.{key}"
            if key not in expected or key not in observed:
                differences.append(child)
            else:
                differences.extend(metadata_differences(expected[key], observed[key], path=child))
        return tuple(differences)
    if isinstance(expected, list) and isinstance(observed, list):
        differences = []
        for index in range(max(len(expected), len(observed))):
            child = f"{path}[{index}]"
            if index >= len(expected) or index >= len(observed):
                differences.append(child)
            else:
                differences.extend(metadata_differences(expected[index], observed[index], path=child))
        return tuple(differences)
    return () if expected == observed else (path,)


def main() -> None:
    """Generate the projection, or check it byte-for-byte."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--observe", choices=_LANGUAGES)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()
    if args.observe:
        print(json.dumps(_observe(args.observe), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return
    payload = _merge({language: _child_observation(language) for language in _LANGUAGES})
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output = args.output
    current = output.read_text(encoding="utf-8") if output.exists() else None
    if args.check:
        if current is None:
            raise SystemExit("command registration metadata is missing; regenerate it")
        decoded_current = json.loads(current)
        if metadata_differences(payload, decoded_current) or current != rendered:
            raise SystemExit("command registration metadata is stale; regenerate it")
        return
    output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
