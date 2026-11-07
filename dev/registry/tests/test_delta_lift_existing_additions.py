"""Lifting an already defaulted declaration preserves its effective references."""

import json

import pytest

from cadrumo.core.toml import freeze_toml_value
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.registry.compiler.reference_defaults import default_row_references
from dev.registry.edition_delta_planning_mode import delta_authored
from dev.registry.edition_delta_source import (
    Block,
    Defaults,
    as_row,
    block_row,
    edition_delta_source_lift,
)
from dev.registry.edition_delta_writer_lifting import lifted_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EDITION = str(filing_year_envelope().horizon)
_PREDECESSOR = str(filing_year_envelope().horizon - 1)


def test_reference_defaults_do_not_claim_member_inheritance() -> None:
    assert not delta_authored({"casilla_source_refs": ["design"]})
    assert not delta_authored({"casilla_source_refs": ["design"], "predecessor": {"none": {}}})
    assert delta_authored({"casilla_source_refs": ["design"], "predecessor": _PREDECESSOR})


@pytest.mark.parametrize("scope", ["row", "table", "inline"])
@pytest.mark.parametrize("extra", [[], ["dictionary", "xsd"]])
def test_existing_additions_drop_duplicate_default_without_changing_references(scope: str, extra: list[str]) -> None:
    header = f'[[revisions."{_EDITION}".casillas]]\nid = "0568"\n'
    refs = "additional_source_refs = " + json.dumps(["design", *extra])
    text = {
        "row": header + refs + "\n",
        "table": header + f'[revisions."{_EDITION}".casillas.constraints]\n' + refs + "\n",
        "inline": header + "constraints = { " + refs + " }\n",
    }[scope]
    raw = block_row(text)
    defaults = Defaults(source_refs=("design",), orden=())
    effective = as_row(
        default_row_references("0568", freeze_toml_value(raw), source_default=("design",), orden_default=())
    )
    lift = edition_delta_source_lift(effective, source_default=defaults.source_refs, orden=())
    actual = block_row(lifted_text(Block(text, raw), lift))
    assert actual == lift.row
    target: dict[str, object] = actual
    if scope != "row":
        constraints = actual.get("constraints")
        assert isinstance(constraints, dict)
        target = as_row(constraints)
    assert target.get("additional_source_refs", []) == extra
    defaulted = as_row(
        default_row_references("0568", freeze_toml_value(target), source_default=("design",), orden_default=())
    )
    assert defaulted["source_refs"] == ["design", *extra]
