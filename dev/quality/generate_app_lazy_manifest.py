"""Generate the static app-subtree lazy-registration manifest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = frozenset(
    {"diagnostics", "ledger", "live", "maintenance", "modelo", "overview", "quickfile", "registry", "review"}
)
LANGUAGES = ("ca", "en", "es", "hu")


def _probe(language: str) -> dict[str, dict[str, object]]:
    code = r"""
import json
from typer._click.core import Context
from cadrumo.entrypoints.cli import full_command_tree

root = full_command_tree()
rows = {}
def owner(callback):
    if callback is None:
        return "<none>"
    module = getattr(callback, "__module__", type(callback).__module__)
    qualname = getattr(callback, "__qualname__", type(callback).__qualname__)
    return f"{module}:{qualname}"
def walk(command, path):
    is_group = callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))
    if len(path) >= 3 and path[1] == "app":
        rows["\u001f".join(path[2:])] = {
            "kind": "group" if is_group else "leaf",
            "help": command.help or "",
            "short_help": command.short_help,
            "hidden": bool(command.hidden),
            "deprecated": command.deprecated,
            "invoke_without_command": bool(getattr(command, "invoke_without_command", False)),
            "no_args_is_help": bool(getattr(command, "no_args_is_help", False)),
            "handler_owner": owner(command.callback),
        }
    if is_group:
        ctx = Context(command, info_name=path[-1])
        try:
            for name in command.list_commands(ctx):
                child = command.get_command(ctx, name)
                if child is not None:
                    walk(child, (*path, name))
        finally:
            ctx.close()
walk(root, ("aeat",))
print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
"""
    env = os.environ.copy()
    env["CADRUMO_OUTPUT_LANGUAGE"] = language
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned probe
        [sys.executable, "-c", code], cwd=ROOT, env=env, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return json.loads(completed.stdout)


def _payload() -> dict[str, object]:
    by_language = {language: _probe(language) for language in LANGUAGES}
    baseline = by_language["en"]
    paths = sorted(key for key in baseline if key.split("\u001f", 1)[0] in FAMILIES)
    for language, rows in by_language.items():
        if set(rows).intersection({key for key in rows if key.split("\u001f", 1)[0] in FAMILIES}) != set(paths):
            raise RuntimeError(f"localized app census drifted for {language}")
    records = []
    for key in paths:
        row = baseline[key]
        records.append(
            {
                "path": key.split("\u001f"),
                "kind": row["kind"],
                "help_by_language": {language: by_language[language][key]["help"] for language in LANGUAGES},
                "short_help_by_language": {
                    language: by_language[language][key]["short_help"] for language in LANGUAGES
                },
                "hidden": row["hidden"],
                "deprecated": row["deprecated"],
                "invoke_without_command": row["invoke_without_command"],
                "no_args_is_help": row["no_args_is_help"],
                "handler_owner": row["handler_owner"],
            }
        )
    return {"format_version": 1, "records": records}


def main() -> None:
    """Write or check the deterministic localized app-node registration resource."""
    parser = ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    target = ROOT / "src/cadrumo/entrypoints/cli/app_lazy_manifest.v1.json"
    rendered = json.dumps(_payload(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.check:
        if target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("app lazy manifest is stale; regenerate it")
        return
    target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
