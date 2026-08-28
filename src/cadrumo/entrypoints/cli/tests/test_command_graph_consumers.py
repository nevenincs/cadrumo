"""The authored CommandSpec graph is the sole CLI/operator projection authority."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ....core.config import override_settings
from .._command_schema import command_registration_metadata, command_schema_refs
from .._command_spec import OptionSpec
from .._command_specs import COMMAND_GRAPH
from .._verb_input_schema import build_verb_input_schemas, cli_path_for_command_key, is_exposable_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("order", [("en", "es", "ca", "hu"), ("hu", "ca", "es", "en")])
def test_command_metadata_locales_are_order_invariant(order: tuple[str, ...]) -> None:
    observed: dict[str, tuple[object, object]] = {}
    for language in order:
        with override_settings(cadrumo_output_language=language):
            row = next(item for item in command_registration_metadata() if item.command == "config.profile.create")
        assert row.parameters_by_language[0][0] == language
        assert row.help_by_language[0][0] == language
        observed[language] = (row.parameters_by_language[0][1], row.help_by_language[0][1])
    assert set(observed) == {"en", "es", "ca", "hu"}


def test_schema_and_input_projections_are_exact_graph_sets() -> None:
    expected = COMMAND_GRAPH.by_schema_identity()
    rows = command_registration_metadata()
    refs = command_schema_refs()
    assert {row.command for row in rows} == set(expected)
    assert {ref.command for ref in refs} == set(expected)
    schemas = build_verb_input_schemas(tuple(sorted(expected)))
    assert set(schemas) == set(expected)
    assert all(schema.cli_path == cli_path_for_command_key(key) for key, schema in schemas.items())


def test_schema_and_operator_help_discovery_loads_no_behavior_target() -> None:
    source = """
import json
import sys
from cadrumo.entrypoints.cli._command_specs import COMMAND_GRAPH
handler_modules = {
    spec.handler.target.module
    for spec in COMMAND_GRAPH.specs
    if spec.handler is not None and spec.handler.target is not None
}
already_loaded = set(sys.modules)
from cadrumo.entrypoints.cli._command_schema import command_schema_refs
from cadrumo.entrypoints.cli._verb_input_schema import build_verb_input_schemas
refs = command_schema_refs()
schemas = build_verb_input_schemas(tuple(sorted(ref.command for ref in refs)))
loaded_handlers = sorted(handler_modules.intersection(set(sys.modules) - already_loaded))
print(json.dumps({
    "expected": len(COMMAND_GRAPH.by_schema_identity()),
    "refs": len(refs),
    "schemas": len(schemas),
    "loaded_handlers": loaded_handlers,
}))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["refs"] == result["schemas"] == result["expected"]
    assert result["loaded_handlers"] == []


def test_operator_help_is_resolved_from_each_owning_spec_translation_key() -> None:
    from ....core.i18n import tr

    expected = COMMAND_GRAPH.by_schema_identity()
    schemas = build_verb_input_schemas(tuple(sorted(expected)))
    assert all(schemas[key].help == tr(spec.help_key.value) for key, spec in expected.items())


def test_non_leaf_retirement_boolean_pairs_and_modelo_choices_are_truthful() -> None:
    assert cli_path_for_command_key("root.status") == ()
    assert not is_exposable_command("root.status")
    assert "config.passphrase.change" in COMMAND_GRAPH.by_schema_identity()
    create = COMMAND_GRAPH.by_schema_identity()["config.profile.create"]
    boolean_pair = next(p for p in create.parameters if p.name == "new_entity_first_two_profit_periods")
    assert isinstance(boolean_pair, OptionSpec)
    assert boolean_pair.declarations == (
        "--new-entity-first-two-profit-periods",
        "--no-new-entity-first-two-profit-periods",
    )
    amend = build_verb_input_schemas(("modelo.work.amend_wizard",))["modelo.work.amend_wizard"]
    modelo = next(parameter for parameter in amend.parameters if parameter.name == "modelo")
    assert "100" in modelo.choices
    assert "303" in modelo.choices


def test_retired_profile_transfer_leaves_do_not_resolve_or_register() -> None:
    """The archive subject's export and import doors replace the retired profile-root leaves."""
    profile_path = ("aeat", "config", "profile")
    registrations = {row.cli_path: row.command for row in command_registration_metadata()}

    for path in ((*profile_path, "archive", "export"), (*profile_path, "archive", "import")):
        spec = COMMAND_GRAPH.resolve_path(path)
        assert spec.result_schema.identity is not None
        assert registrations[path[1:]] == spec.result_schema.identity

    for retired_leaf in ("export", "import"):
        retired_path = (*profile_path, retired_leaf)
        with pytest.raises(LookupError, match="unknown command spec path"):
            COMMAND_GRAPH.resolve_path(retired_path)
        assert retired_path[1:] not in registrations


def test_every_projected_target_matches_its_authored_spec() -> None:
    expected = COMMAND_GRAPH.by_schema_identity()
    for row in command_registration_metadata():
        spec = expected[row.command]
        assert spec.result_schema.target is not None
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert row.schema_owner == spec.result_schema.target.identity
        assert row.schema_name == spec.result_schema.target.qualname
        assert row.handler_owner == spec.handler.target.identity


#: The retired-generator physical-absence proof lives in the development test
#: tree's ``test_command_graph_legacy_sources_absent.py``, which names the two
#: retired generator scripts and their one consumer directly.
