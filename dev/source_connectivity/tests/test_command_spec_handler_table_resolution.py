"""Proofs for resolving a handler module routed through a dict-literal table.

Four production command-spec modules hoist their handler module paths into a
module-level ``dict`` constant and index it from the ``_leaf`` wrapper, so the
dotted path reaches ``DeferredTarget`` as a subscript rather than as a literal.
The structural walk could not see through the subscript, resolved the handler to
``None``, and raised on the first such spec -- which took every caller of
``discover_ingress_surfaces`` down with it.

The refusal itself is correct and is proven to survive here: a write command the
tool cannot see is exactly what this analysis exists to refuse to ignore. Only
the set of genuinely determinable shapes widens.

The synthetic proofs below state the shape this package expects; the real-tree
proof states the shape production actually has. Only the second can fail when
the four spec modules change their indirection, so both are carried.

See Also:
    :mod:`dev.source_connectivity.discovery`
        The structural walk under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..discovery import discover_ingress_surfaces

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]

_AUTH_SPECS = Path("src/cadrumo/entrypoints/cli/config/_auth_command_specs.py")

#: A spec module shaped exactly like the four production ones: a policy constant,
#: a ``_handler`` helper indexing a module-level table, and a ``_leaf`` wrapper
#: whose own ``policy`` parameter keeps the wrapper's inner ``CommandSpec`` out of
#: the write-policy sweep.
_SPEC_MODULE = """__TABLE__


PROBE_WRITE = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"local-state"}),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
)


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(__LOOKUP__, name))


def _leaf(key: str, parent: str, token: str, module: str, handler: str, policy: object) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind="leaf",
        help_key=_key("probe.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=policy,
        handler=_handler(module, handler),
        result_schema=_schema("ProbeResult", "probe.add"),
    )


PROBE_COMMAND_SPECS = (_leaf("probe_add", "probe", "add", "_probe", "probe_add", PROBE_WRITE),)
"""


def _write_spec_module(root: Path, table: str, lookup: str) -> None:
    """Materialise a spec module resolving its handler module through ``lookup``."""
    path = root / "src" / "cadrumo" / "entrypoints" / "cli" / "_probe_command_specs.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = _SPEC_MODULE.replace("__TABLE__", table).replace("__LOOKUP__", lookup)
    path.write_text(source, encoding="utf-8")


def test_the_repo_root_this_module_computes_is_the_real_one() -> None:
    """Anti-vacuity: the real-tree proof is worthless if the root is wrong."""
    assert (_REPO_ROOT / _AUTH_SPECS).is_file(), f"computed repo root has no {_AUTH_SPECS}: {_REPO_ROOT}"


def test_handler_module_routed_through_a_dict_literal_subscript_resolves(tmp_path: Path) -> None:
    """``TABLE["key"]`` resolves to the dotted path the table binds for that key."""
    _write_spec_module(
        tmp_path,
        "_HANDLER_MODULES = {\n"
        '    "_other": "cadrumo.entrypoints.cli._other",\n'
        '    "_probe": "cadrumo.entrypoints.cli._probe",\n'
        "}",
        "_HANDLER_MODULES[module]",
    )

    rows = discover_ingress_surfaces(tmp_path)

    assert [(row.module, row.callback_name, row.command_group_symbol, row.command_name) for row in rows] == [
        ("src/cadrumo/entrypoints/cli/_probe.py", "probe_add", "probe", "add")
    ]


def test_an_annotated_handler_table_resolves_the_same_way(tmp_path: Path) -> None:
    """Production declares the table ``Final``, so the annotated form must resolve."""
    _write_spec_module(
        tmp_path,
        '_HANDLER_MODULES: Final[dict[str, str]] = {"_probe": "cadrumo.entrypoints.cli._probe"}',
        "_HANDLER_MODULES[module]",
    )

    rows = discover_ingress_surfaces(tmp_path)

    assert [(row.module, row.callback_name) for row in rows] == [("src/cadrumo/entrypoints/cli/_probe.py", "probe_add")]


def test_a_runtime_constructed_handler_table_stays_unresolvable(tmp_path: Path) -> None:
    """A table built by a call is not a literal, so the walk must still refuse."""
    _write_spec_module(
        tmp_path,
        '_HANDLER_MODULES = dict(_probe="cadrumo.entrypoints.cli._probe")',
        "_HANDLER_MODULES[module]",
    )

    with pytest.raises(ValueError, match="write command spec cannot be resolved structurally"):
        discover_ingress_surfaces(tmp_path)


def test_a_non_constant_table_key_stays_unresolvable(tmp_path: Path) -> None:
    """A key the walk cannot reduce to a string must refuse, never guess."""
    _write_spec_module(
        tmp_path,
        '_HANDLER_MODULES = {"_probe": "cadrumo.entrypoints.cli._probe"}',
        "_HANDLER_MODULES[module.lower()]",
    )

    with pytest.raises(ValueError, match="write command spec cannot be resolved structurally"):
        discover_ingress_surfaces(tmp_path)


def test_a_handler_table_carrying_an_expansion_is_refused_whole(tmp_path: Path) -> None:
    """An expansion can add or shadow keys the walk cannot see, so refuse it all."""
    _write_spec_module(
        tmp_path,
        '_BASE = {"_probe": "cadrumo.entrypoints.cli._probe"}\n'
        '_HANDLER_MODULES = {**_BASE, "_other": "cadrumo.entrypoints.cli._other"}',
        "_HANDLER_MODULES[module]",
    )

    with pytest.raises(ValueError, match="write command spec cannot be resolved structurally"):
        discover_ingress_surfaces(tmp_path)


def test_the_real_config_auth_configure_leaf_resolves_to_its_production_handler() -> None:
    """The live spec module, not an imagined one, must resolve end to end."""
    declaration = _AUTH_SPECS.as_posix()
    lines = (_REPO_ROOT / _AUTH_SPECS).read_text(encoding="utf-8").splitlines()
    key_line = next(index for index, line in enumerate(lines, start=1) if line.strip() == '"config_auth_configure",')

    rows = [
        row
        for row in discover_ingress_surfaces(_REPO_ROOT)
        if row.declaration_module == declaration
        and row.command_group_symbol == "config_auth"
        and row.command_name == "configure"
    ]

    assert [
        (row.capability_id, row.command_group_symbol, row.evidence_locator, row.execution_policy) for row in rows
    ] == [
        (
            "ingress:src/cadrumo/entrypoints/cli/config/_auth.py:auth_configure",
            "config_auth",
            f"{declaration}:{key_line - 1}",
            "ENCRYPTED_WRITE",
        )
    ]
    assert lines[key_line - 2].strip() == "_leaf(", f"locator must address the spec's own call: {lines[key_line - 2]!r}"
