"""Packaging probe: the operator harness data ships and the accessor reads it.

The harness operating layer is reviewed product data under ``aeat/_data/agent/``.
It ships in the wheel through the same hatch tracked-file inclusion that ships the
corpus, registry, and terminology trees, and it is read through the same
bundled-data boundary (``importlib.resources`` via ``aeat.core.resources``). This
probe asserts the tree resolves through that boundary and the ``aeat.agent``
accessor reads the shipped rules, so a packaging or accessor regression that would
leave the harness empty at install time fails here rather than at operator runtime.
"""

from __future__ import annotations

import pytest

from aeat.agent import harness_root, iter_operator_rules, operator_rules_text
from aeat.core.resources import packaged_data

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_EXPECTED_RULES = frozenset(
    {
        "operator-operating-rules.md",
        "operator-safety-handoff.md",
        "operator-envelope-reading.md",
        "operator-grounding.md",
    },
)


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
