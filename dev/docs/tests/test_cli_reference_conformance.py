"""Conformance gate for the CLI reference documentation.

Two independent conformance assertions:

1. **Docs-versus-tree completeness** — every live leaf command is documented in
   the generated reference; every documented command path resolves to a real
   CLI leaf.

2. **Schema-registry conformance** — every entry in :data:`SCHEMA_REGISTRY`
   maps to a real CLI leaf path (or a known group-callback emit site); the
   documented output-schema class for each command matches the registered
   schema; no registry key is an orphan.

Both walk the live materialised CLI tree via a subprocess, so they are honest
about the actual command surface rather than any curated contract tuple.
Each test carries the active ``unit`` and ``hex_entrypoint`` markers.

Language pinning: a fresh subprocess with ``CADRUMO_OUTPUT_LANGUAGE=en`` ensures
``tr()`` help strings resolve to English before any CLI module is imported.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from typer.main import get_command

from cadrumo.entrypoints.schema_surface import GROUP_CALLBACK_SCHEMA_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]

_DOCS_CLI_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs" / "cli"

#: Group-callback emit sites that register a schema but are not CLI leaf
#: commands — they appear as group callbacks, not reachable leaves.
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = GROUP_CALLBACK_SCHEMA_KEYS

#: Generated pages that carry navigation or root-level behaviour rather than
#: per-command sections.  Only the family pages emit ``**Registry key:**``
#: lines, so these are excluded from the per-command parsing helpers.
_NON_FAMILY_PAGES: frozenset[str] = frozenset({"cli/index.rst", "cli/automation.rst", "cli/schemas.rst"})


@pytest.fixture(autouse=True)
def _isolated_cadrumo_storage_root(tmp_path: Path) -> Iterator[None]:
    """Give direct Cadrumo imports an isolated, per-test local-storage root."""
    from cadrumo.tests.env_scope import isolated_aeat_env

    with isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path / "cadrumo-state")):
        yield


def _project_root() -> Path:
    """Return the project root, inferred from the location of this test file."""
    return Path(__file__).parent.parent.parent.parent.parent


def _populate_schema_registry() -> None:
    """Load schemas through the production payload-module discovery path."""
    from cadrumo.entrypoints.cli._app_contract import _ensure_result_schemas_registered

    failures = _ensure_result_schemas_registered()
    assert failures == (), f"payload schema modules failed to import: {failures!r}"


def _rendered_reference() -> dict[str, str]:
    """Render the CLI reference fresh in an English-pinned subprocess.

    The CLI reference is generated at build time, not committed, so the
    conformance gates render it in a fresh subprocess (which pins
    ``CADRUMO_OUTPUT_LANGUAGE=en`` before any CLI import) to a temporary directory
    and inspect the returned content, rather than reading committed pages.

    Returns:
        A mapping from relative path (for example ``"cli/app.rst"``) to rendered
        reStructuredText content.
    """
    import tempfile

    from dev.docs.cli_reference import generate_cli_reference_in_subprocess

    with tempfile.TemporaryDirectory() as tmp:
        return generate_cli_reference_in_subprocess(Path(tmp))


def _rendered_doc_registry_keys() -> set[str]:
    """Extract registry keys from a freshly rendered CLI reference.

    Returns:
        A set of registry-key strings extracted from the rendered family pages.
    """
    keys: set[str] = set()
    for rel_path, content in _rendered_reference().items():
        if rel_path in _NON_FAMILY_PAGES:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("**Registry key:**"):
                # **Registry key:** ``some.key.here``
                parts = stripped.split("``")
                if len(parts) >= 2:
                    keys.add(parts[1])
    return keys


# ---------------------------------------------------------------------------
# Gate 1: docs-versus-tree completeness
# ---------------------------------------------------------------------------


def test_typer_positional_renders_as_argument() -> None:
    """A real Typer positional renders as an ``Argument``, never an ``Option``."""
    from dev.docs.cli_reference import _render_param_table

    app = typer.Typer()

    @app.command()
    def view(transaction_id: str = typer.Argument(..., help="The ledger transaction id.")) -> None:
        """Inspect a ledger transaction."""

    command = get_command(app)
    if hasattr(command, "commands"):
        command = next(iter(command.commands.values()))

    rendered = _render_param_table(list(command.params))

    assert "transaction_id" in rendered
    positional_line = next(line for line in rendered.splitlines() if "Argument" in line or "Option" in line)
    assert "*Argument, required.*" in positional_line
    assert "Option" not in positional_line


def test_every_live_leaf_is_documented() -> None:
    """Every non-retired live leaf command must appear in the generated reference.

    Walks the materialised CLI tree via a subprocess (guaranteeing en-language
    pinning) to enumerate the full leaf set, then checks that every normalised
    registry key is present in the generated reference.

    Failures indicate that the build-time renderer omitted a live command.
    """
    from dev.docs.cli_reference import collect_live_leaf_paths_in_subprocess

    live_keys = set(collect_live_leaf_paths_in_subprocess())
    assert live_keys, "the live CLI walk enumerated no leaves; this gate would pass over an empty tree"
    documented_keys = _rendered_doc_registry_keys()

    missing_from_docs = sorted(live_keys - documented_keys)
    assert not missing_from_docs, (
        f"Live CLI leaf commands not documented in docs/cli/ ({len(missing_from_docs)}):\n"
        + "\n".join(f"  - {k}" for k in missing_from_docs)
        + "\nThe reference is generated at build time from the live command tree."
    )


def test_every_documented_path_resolves_to_a_live_command() -> None:
    """Every registry key in the generated reference must map to a live CLI leaf.

    Failures indicate that the build-time renderer emitted a stale command entry.
    """
    from dev.docs.cli_reference import collect_live_leaf_paths_in_subprocess

    live_keys = set(collect_live_leaf_paths_in_subprocess())
    assert live_keys, "the live CLI walk enumerated no leaves; this gate would pass over an empty tree"
    documented_keys = _rendered_doc_registry_keys()

    orphan_docs = sorted(documented_keys - live_keys)
    assert not orphan_docs, (
        f"Documented command paths with no matching live CLI leaf ({len(orphan_docs)}):\n"
        + "\n".join(f"  - {k}" for k in orphan_docs)
        + "\nThe reference is generated at build time from the live command tree."
    )


# ---------------------------------------------------------------------------
# Gate 2: schema-registry conformance
# ---------------------------------------------------------------------------


def test_schema_registry_entries_map_to_live_commands_or_group_callbacks() -> None:
    """Every :data:`SCHEMA_REGISTRY` key must map to a live CLI leaf or known group callback.

    Imports all payload modules to populate the registry, then checks that no
    registered schema key is an orphan — pointing to a command that no longer
    exists in the live tree.

    Group-callback emit sites are explicitly exempted because they register
    under a group callback rather than a leaf command.
    """
    from cadrumo.core.json_contract import SCHEMA_REGISTRY
    from dev.docs.cli_reference import collect_live_leaf_paths_in_subprocess

    _populate_schema_registry()
    live_keys = set(collect_live_leaf_paths_in_subprocess())
    assert live_keys, "the live CLI walk enumerated no leaves; this gate would pass over an empty tree"
    registry_keys = set(SCHEMA_REGISTRY.keys())
    expected_reachable = live_keys | _GROUP_CALLBACK_EMIT_KEYS

    orphan_registry = sorted(registry_keys - expected_reachable)
    assert not orphan_registry, (
        f"Schema registry keys with no matching live CLI leaf ({len(orphan_registry)}):\n"
        + "\n".join(f"  - {k}" for k in orphan_registry)
        + "\nRemove the orphan @register_schema decorators or wire them to a CLI leaf."
    )


def test_every_live_leaf_has_a_registered_schema() -> None:
    """Every live CLI leaf must have a registered :class:`OutputSchema`.

    Imports all payload modules to populate the registry, then walks the live
    tree and asserts that every leaf's normalised key is present in the
    registry.  The group-callback emit sites are excluded (they are not leaves).

    This is a non-tautological gate: it compares the live tree (one source of
    truth) against the registry (an independent source of truth).  The
    generated reference docs are not consulted here so the gate is independent
    of the drift check.
    """
    from cadrumo.core.json_contract import SCHEMA_REGISTRY
    from dev.docs.cli_reference import collect_live_leaf_paths_in_subprocess

    _populate_schema_registry()
    live_keys = set(collect_live_leaf_paths_in_subprocess())
    assert live_keys, "the live CLI walk enumerated no leaves; this gate would pass over an empty tree"
    registry_keys = set(SCHEMA_REGISTRY.keys())

    unregistered = sorted(live_keys - registry_keys)
    assert not unregistered, (
        f"Live CLI leaves without a registered OutputSchema ({len(unregistered)}):\n"
        + "\n".join(f"  - {k}" for k in unregistered)
        + "\nAdd @register_schema decorators for these commands."
    )


def test_documented_schema_classes_match_registry() -> None:
    """Documented schema class names must match the registered schema for each command.

    For each command that has a schema, the generated reference page states
    the fully-qualified class name.  This gate verifies that the documented
    class name matches the actual registered schema class — catching a renderer
    projection that disagrees with the live registry.
    """
    from cadrumo.core.json_contract import SCHEMA_REGISTRY

    _populate_schema_registry()
    # Parse the freshly-rendered pages for (registry_key -> documented_class_name) pairs.
    documented: dict[str, str] = {}
    for rel_path, content in sorted(_rendered_reference().items()):
        if rel_path in _NON_FAMILY_PAGES:
            continue
        current_key: str | None = None
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("**Registry key:**"):
                parts = stripped.split("``")
                if len(parts) >= 2:
                    current_key = parts[1]
            elif stripped.startswith("validated against ``") and current_key is not None:
                # "validated against ``module.ClassName``."
                parts = stripped.split("``")
                if len(parts) >= 2:
                    documented[current_key] = parts[1]
                    current_key = None

    mismatches: list[str] = []
    for key, documented_cls in sorted(documented.items()):
        registered = SCHEMA_REGISTRY.get(key)
        if registered is None:
            # Orphan documented key — caught by test_every_documented_path_resolves_to_a_live_command
            continue
        actual_cls = f"{registered.__module__}.{registered.__name__}"
        if actual_cls != documented_cls:
            mismatches.append(f"{key}: documented={documented_cls!r} but registered={actual_cls!r}")

    assert not mismatches, (
        f"Documented schema classes do not match the registry ({len(mismatches)}):\n"
        + "\n".join(f"  - {m}" for m in mismatches)
        + "\nThe reference is generated at build time from the live command tree."
    )
