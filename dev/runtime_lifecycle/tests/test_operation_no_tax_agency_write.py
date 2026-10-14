"""No operation and no external client tool declares, or is named for, a submission to the tax agency.

Cadrumo never submits, files or signs anything at the tax agency, on any
frontend. Three readings hold that here: the one declaration a command policy
has for a live write is never set anywhere in the source tree, every
definition permits only extents of its own local commit, and no operation
that reaches the network, and no external client tool, carries one of the agency's write
verbs in its name.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping

import pytest

from cadrumo.domain.calculations.registry.remote_state_guard import AEAT_WRITE_FORBIDDEN_VERB_TOKENS
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE
from cadrumo_harness.mcp.surface_facts import operation_surface_facts
from dev.operation_contract_manifest.tests.test_operation_catalogue import _production_sources, _registry, _tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCAL_COMMIT_EXTENTS = frozenset({"none", "updated", "partial", "unknown"})
"""The only extents an operation may declare: how much of its own local work committed."""

_LIVE_WRITE = "live_write"


def _declares_no_live_write(value: ast.expr) -> bool:
    """Whether a declared value is the literal refusal or forwards an existing declaration."""
    if isinstance(value, ast.Constant):
        return value.value is False
    if isinstance(value, ast.Attribute):
        return value.attr == _LIVE_WRITE
    return isinstance(value, ast.Name) and value.id == _LIVE_WRITE


def _binds_live_write(target: ast.expr) -> bool:
    if isinstance(target, ast.Name):
        return target.id == _LIVE_WRITE
    return isinstance(target, ast.Attribute) and target.attr == _LIVE_WRITE


def _live_write_values(tree: ast.AST) -> Iterable[ast.expr]:
    """Every value a tree gives the command policy's live-write declaration."""
    for node in ast.walk(tree):
        if (
            (isinstance(node, ast.keyword) and node.arg == _LIVE_WRITE)
            or (isinstance(node, ast.AnnAssign) and node.value is not None and _binds_live_write(node.target))
            or (isinstance(node, ast.Assign) and any(_binds_live_write(target) for target in node.targets))
        ):
            yield node.value
        elif isinstance(node, ast.arguments):
            positional = [*node.posonlyargs, *node.args]
            defaulted = positional[len(positional) - len(node.defaults) :]
            for argument, default in zip(defaulted, node.defaults, strict=True):
                if argument.arg == _LIVE_WRITE:
                    yield default
            for argument, keyword_default in zip(node.kwonlyargs, node.kw_defaults, strict=True):
                if argument.arg == _LIVE_WRITE and keyword_default is not None:
                    yield keyword_default


def test_no_command_policy_in_the_source_tree_declares_a_live_write() -> None:
    """The one declaration a command has for a submission is never set anywhere."""
    declared = [(path, value) for path in _production_sources() for value in _live_write_values(_tree().parsed(path))]
    # The scan must reach the declarations it judges, or it would pass on nothing.
    assert declared
    offenders = sorted((path, value.lineno) for path, value in declared if not _declares_no_live_write(value))
    assert not offenders, f"a command policy declares a live write to the tax agency: {offenders}"


def test_the_live_write_scan_detects_every_way_of_declaring_one() -> None:
    """A keyword, a default and an assignment are all read; a forwarded declaration is not one."""
    source = (
        "policy = ExecutionPolicySpec(capabilities=frozenset(), live_write=True)\n"
        "class Policy:\n"
        "    live_write: bool = True\n"
        "def build(*, live_write=True): ...\n"
        "spec.live_write = enabled\n"
        "safe = ExecutionPolicySpec(live_write=False)\n"
        "projected = Metadata(live_write=declared.live_write)\n"
    )
    verdicts = [_declares_no_live_write(value) for value in _live_write_values(ast.parse(source))]
    # Four declarations set or could set a live write; the last two lines of the source do not.
    assert sorted(verdicts) == [False, False, False, False, True, True]


def _name_words(name: str) -> frozenset[str]:
    """The words of a dotted, dashed or underscored identifier."""
    return frozenset(word for word in re.split(r"[^a-z0-9]+", name.casefold()) if isinstance(word, str) and word)


def _write_verbs(names: Iterable[str]) -> frozenset[str]:
    """The tax agency's write verbs that appear as whole words in these names."""
    return frozenset(word for name in names for word in _name_words(name)) & AEAT_WRITE_FORBIDDEN_VERB_TOKENS


_NETWORK_READS_NAMED_LIKE_A_WRITE: Mapping[str, str] = {
    "live.verify.tgvi": "reads whether a tax id is registered for intra-community operations; it sends nothing",
}
"""Operations that reach the network and whose name carries a write verb of the tax agency.

Each is a read whose name collides with the verb list. The entry must keep
answering a live collision, so a renamed or removed operation fails here."""


def test_every_operation_permits_only_local_extents_of_commit() -> None:
    """No definition declares an effect other than how much of its own local work committed."""
    foreign = {
        item.contract.definition_id: sorted(effect.value for effect in item.contract.permitted_effects)
        for item in _registry().public_registrations
        if not {effect.value for effect in item.contract.permitted_effects} <= _LOCAL_COMMIT_EXTENTS
    }
    assert not foreign, f"definitions that declare an effect outside the local commit extents: {foreign}"


def test_no_operation_that_reaches_the_network_is_named_for_a_tax_agency_write() -> None:
    """An operation that can contact a host never carries a submission verb in its id or phases."""
    collisions: dict[str, list[str]] = {}
    for definition in _registry().definitions:
        verbs = _write_verbs((definition.definition_id, *definition.phase_codes))
        if verbs and operation_surface_facts(definition.definition_id).reaches_network:
            collisions[definition.definition_id] = sorted(verbs)
    undeclared = {key: verbs for key, verbs in collisions.items() if key not in _NETWORK_READS_NAMED_LIKE_A_WRITE}
    assert not undeclared, f"operations that reach the network and are named for a tax agency write: {undeclared}"
    stale = sorted(set(_NETWORK_READS_NAMED_LIKE_A_WRITE) - set(collisions))
    assert not stale, f"named as a read that collides with a write verb, but no longer collides: {stale}"
    unexplained = sorted(key for key, reason in _NETWORK_READS_NAMED_LIKE_A_WRITE.items() if not reason.strip())
    assert not unexplained, f"a declared name collision states no reason: {unexplained}"


def _tool_vocabulary(schema: Mapping[str, object]) -> tuple[str, ...]:
    """Every value a tool's input schema enumerates."""
    properties = schema.get("properties")
    values: list[str] = []
    if isinstance(properties, Mapping):
        for declaration in properties.values():
            enumerated = declaration.get("enum") if isinstance(declaration, Mapping) else None
            if isinstance(enumerated, (list, tuple)):
                values.extend(str(value) for value in enumerated)
    return tuple(values)


_TOOLS_NAMED_LIKE_A_WRITE: Mapping[str, tuple[frozenset[str], str]] = {
    "authority": (
        frozenset({"payment"}),
        "its category filter names a category of the bundled portal catalogue, which lists where the tax agency's "
        "own pages are; the tool reads that list and reaches nothing",
    ),
}
"""external client tools whose name or enumerated actions carry a write verb of the tax agency, and why none is one.

Each entry names exactly the verbs that collide, so a tool that gains another
fails here, and so does an entry whose tool no longer collides."""


def test_no_mcp_tool_is_named_for_a_tax_agency_write() -> None:
    """No tool name, and no action a tool enumerates, is a submission verb, but for a declared collision."""
    tools = list(MCP_TOOL_CATALOGUE)
    assert tools
    named: dict[str, frozenset[str]] = {}
    for name, _description, schema in tools:
        verbs = _write_verbs((name, *_tool_vocabulary(schema)))
        if verbs:
            named[name] = verbs
    undeclared = {
        name: sorted(verbs)
        for name, verbs in named.items()
        if name not in _TOOLS_NAMED_LIKE_A_WRITE or verbs != _TOOLS_NAMED_LIKE_A_WRITE[name][0]
    }
    assert not undeclared, f"external client tools that name or enumerate a tax agency write: {undeclared}"
    stale = sorted(set(_TOOLS_NAMED_LIKE_A_WRITE) - set(named))
    assert not stale, f"declared as colliding with a write verb, but no longer collides: {stale}"
    assert all(reason.strip() for _verbs, reason in _TOOLS_NAMED_LIKE_A_WRITE.values())


def test_the_write_verb_reading_matches_whole_words_only() -> None:
    """A verb is read as a word of the name, never as a fragment of another word."""
    assert _write_verbs(("live.modelo.presentar",)) == frozenset({"presentar"})
    assert _write_verbs(("aeat_submit", "modelo.work.sign-and-send")) == frozenset({"submit", "sign"})
    assert _write_verbs(("ledger.design.assignment", "overview.savepoint")) == frozenset()
    enumerated = _tool_vocabulary({"properties": {"action": {"type": "string", "enum": ["inspect", "submit"]}}})
    assert enumerated == ("inspect", "submit")
