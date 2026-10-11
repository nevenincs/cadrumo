"""Packaging probe: the operator harness data ships and the accessor reads it.

The harness operating layer is reviewed product data under
``cadrumo_harness/_data/agent/``. It ships in the ``cadrumo`` wheel alongside
the engine and is read through its package's bundled-data boundary
(``importlib.resources`` via ``cadrumo_harness._resources``). This probe asserts
the tree resolves through that boundary and the ``cadrumo_harness`` accessor reads the shipped
rules, so a packaging or accessor regression that would leave the harness empty
at install time fails here rather than at operator runtime.

The MCP server's own data ships the same way: the registered operations'
public contracts, under ``cadrumo_harness/_data/operation_contracts/``, which
it reads to find and describe operations with no runtime running. That it
resolves through the boundary, that the server's reader reads every line of
it, and that a distribution built from this tree carries it are asserted here.
"""

from __future__ import annotations

import re

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

from cadrumo.tests.inventory import REPO_ROOT

from .._resources import packaged_data
from ..mcp.public_operation_discovery import (
    CONTRACT_DOCUMENT_DIRECTORY,
    CONTRACT_PART_SUFFIX,
    contract_part_name,
    shipped_public_descriptions,
)
from ..resources import harness_root, iter_operator_rules, iter_reference_documents, operator_rules_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_EXPECTED_RULES = frozenset(
    {
        "cadrumo-operator-operating-rules.md",
        "cadrumo-operator-safety-handoff.md",
        "cadrumo-operator-envelope-reading.md",
        "cadrumo-operator-grounding.md",
        "cadrumo-operator-orientation-routing.md",
        "cadrumo-operator-lifecycle-ordering.md",
        "cadrumo-operator-honest-declaration.md",
    },
)
_UTF_8 = "utf-8"
# A reference document as a rule names it in backticks: a markdown file name, with or without its folder.
_NAMED_REFERENCE = re.compile(r"`(?:reference/)?([a-z0-9][a-z0-9-]*\.md)`")


def test_harness_root_resolves_through_the_bundled_data_boundary() -> None:
    # The same boundary that ships corpus/registry resolves the agent tree.
    boundary_root = packaged_data("agent")
    assert boundary_root.is_dir()
    assert harness_root().is_dir()
    assert {child.name for child in harness_root().iterdir()} >= {"README.md", "rules"}


def test_accessor_reads_every_shipped_operator_rule() -> None:
    shipped = {rule.name for rule in iter_operator_rules()}
    assert shipped == _EXPECTED_RULES


def test_operator_rules_text_is_non_empty_and_concatenates_all_rules() -> None:
    text = operator_rules_text()
    assert text.strip()
    # Each rule contributes its level-one heading to the concatenation.
    assert text.count("\n# ") + text.startswith("# ") == len(_EXPECTED_RULES)


def test_every_reference_document_a_rule_names_ships() -> None:
    shipped = {document.name for document in iter_reference_documents()}
    assert shipped, "no reference document ships under _data/agent/reference"
    rule_names = {rule.name for rule in iter_operator_rules()}
    named = {
        name
        for rule in iter_operator_rules()
        for name in _NAMED_REFERENCE.findall(rule.read_text(encoding=_UTF_8))
        if name not in rule_names
    }
    # A rule that sends the agent to a document the wheel does not carry is a dead instruction,
    # and a document no rule names is one the agent is never told to open.
    assert named == shipped


def _contract_parts() -> dict[str, str]:
    """Every file the contract document's directory ships, by name."""
    root = packaged_data(CONTRACT_DOCUMENT_DIRECTORY)
    assert root.is_dir()
    return {child.name: child.read_text(encoding=_UTF_8) for child in root.iterdir() if child.is_file()}


def test_the_operation_contract_document_ships_and_the_server_reads_every_line_of_it() -> None:
    parts = _contract_parts()
    assert parts, "no part of the operation contract document ships under _data/operation_contracts"
    assert all(name.endswith(CONTRACT_PART_SUFFIX) for name in parts)
    described = shipped_public_descriptions()
    lines = sum(1 for body in parts.values() for line in body.split("\n") if line)
    # A line the reader dropped, or a part it did not open, would leave an operation nobody can find.
    assert len(described) == lines
    assert {contract_part_name(definition_id) for definition_id in described} == set(parts)


@pytest.mark.parametrize(("builder", "prefix"), [(WheelBuilder, ""), (SdistBuilder, "src/")], ids=["wheel", "sdist"])
def test_a_distribution_built_from_this_tree_carries_the_operation_contract_document(
    builder: type[WheelBuilder] | type[SdistBuilder], prefix: str
) -> None:
    """The build backend, under this repository's own declarations, lists every part among what it packs."""
    data_root = f"{prefix}cadrumo_harness/_data"
    carried = {
        included.distribution_path.replace("\\", "/") for included in builder(str(REPO_ROOT)).recurse_included_files()
    }
    # The agent tree is what this listing is known to carry; without it the listing measured nothing.
    assert f"{data_root}/agent/README.md" in carried
    parts = {f"{data_root}/{CONTRACT_DOCUMENT_DIRECTORY}/{name}" for name in _contract_parts()}
    assert parts and parts <= carried
