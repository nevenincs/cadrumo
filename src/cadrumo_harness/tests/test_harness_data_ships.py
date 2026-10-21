"""Packaging probe: the operator harness data ships and the accessor reads it.

The harness operating layer is reviewed product data under
``cadrumo_harness/_data/agent/``. It ships in the ``cadrumo`` wheel alongside
the engine and is read through its package's bundled-data boundary
(``importlib.resources`` via ``cadrumo_harness._resources``). This probe asserts
the tree resolves through that boundary and the ``cadrumo_harness`` accessor reads the shipped
rules, so a packaging or accessor regression that would leave the harness empty
at install time fails here rather than at operator runtime.
"""

from __future__ import annotations

import re

import pytest

from .._resources import packaged_data
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
