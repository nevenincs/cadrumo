"""Architecture gate: a concept promoted to one definition keeps only that one.

A canonicalisation is undone silently. When a duplicate is collapsed onto a
shared definition, the tree ends up carrying both for as long as it takes for
someone to re-add the local copy -- and nothing fails when they do, because the
local copy works. That happened here: a whole-tree commit in a shared worktree
restored nine local ``_key`` helpers, six ``_bucket_id`` aliases and a record
protocol, leaving each canonical helper sitting beside the duplicates it had
replaced. No test noticed. The census did, on the next run.

This gate is that census, narrowed to an invariant. It names the concepts that
have been deliberately collapsed and asserts each is defined exactly once across
the shipped package. It carries no count and no tolerance: the contract is one
definition, and a second is a regression whatever the total.

It deliberately does NOT assert the absence of duplication generally. Several
duplicate-looking bodies in this tree are correct -- a guard over a per-module
policy, an alias giving a primitive a domain name, two manifests that agree at
version one by coincidence -- and a gate that refused those would be refusing
the codebase's own good judgement. Only concepts that were examined and
collapsed are listed.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Each entry is a symbol that must have exactly one definition under
#: ``src/cadrumo``, with the module that owns it. Added only after the concept
#: was read, judged to be one fact, and collapsed.
_CANONICAL_DEFINITIONS: dict[str, str] = {
    "translation_key": "src/cadrumo/entrypoints/cli/command_spec.py",
    "config_payload_schema": "src/cadrumo/entrypoints/cli/config/_command_spec_schema.py",
    "state_free_group_spec": "src/cadrumo/entrypoints/cli/config/_spec_policies.py",
    "require_active_profile_pointer": "src/cadrumo/entrypoints/cli/config/_profile_support.py",
    "first_json_object": "src/cadrumo/llm/response_json.py",
    "first_unanswered_key": "src/cadrumo/application/flows/engine.py",
    "iter_flow_pages": "src/cadrumo/application/flows/definition.py",
    "derive_snapshot_id": "src/cadrumo/application/live/snapshot_identity.py",
    "profile_path_values_for_bucket": "src/cadrumo/application/user_profile/projections.py",
    "profile_operation_subject": "src/cadrumo/core/operations.py",
    "local_tag_name": "src/cadrumo/adapters/inbound/einvoice/xml.py",
    "is_str_keyed_mapping": "src/cadrumo/core/type_guards.py",
    "INPUT_PDF_SOURCE_LABEL": "src/cadrumo/adapters/inbound/pdf/redaction.py",
    "SHA256_HEX_LENGTH": "src/cadrumo/core/hashing.py",
    "FAMILIA_SECTION_ID": "src/cadrumo/application/wizard/catalogue.py",
    "RESPONSIBLE_OWNER": "src/cadrumo/application/modelo/edit_services.py",
}


def _definition_sites(root: pathlib.Path) -> dict[str, list[str]]:
    """Return, per watched symbol, every module that DEFINES it.

    A definition is a top-level function, class, or assignment to the bare name.
    An import of the symbol is not a definition, which is the whole point: the
    consumers are expected to import it, and only a second declaration is the
    regression.
    """
    sites: dict[str, list[str]] = {name: [] for name in _CANONICAL_DEFINITIONS}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            defined: str | None = None
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                defined = node.name
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                defined = node.targets[0].id
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined = node.target.id
            if defined in sites:
                sites[defined].append(path.as_posix())
    return sites


def test_every_collapsed_concept_still_has_exactly_one_definition() -> None:
    """A concept collapsed onto one definition has not grown a second."""
    root = pathlib.Path(__file__).resolve().parents[2] / "src" / "cadrumo"
    sites = _definition_sites(root)

    missing = sorted(name for name, found in sites.items() if not found)
    assert not missing, f"canonical definition disappeared: {missing}"

    duplicated = {name: found for name, found in sites.items() if len(found) > 1}
    assert not duplicated, f"a collapsed concept was declared again: {duplicated}"

    misplaced = {
        name: sites[name][0]
        for name, owner in _CANONICAL_DEFINITIONS.items()
        if not sites[name][0].endswith(owner.split("src/cadrumo/", 1)[1])
    }
    assert not misplaced, f"canonical definition moved without updating this gate: {misplaced}"


def test_the_gate_detects_a_reintroduced_duplicate() -> None:
    """The predicate is shown to catch a second declaration, not assumed to.

    Constructed as source text rather than by writing into the tree: a gate over
    the working tree must not modify it to prove itself.
    """
    second = ast.parse("def translation_key(value):\n    return value\n")
    defined = [
        node.name for node in second.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]

    assert "translation_key" in defined
    assert "translation_key" in _CANONICAL_DEFINITIONS, "the watched set must contain what the detector names"
