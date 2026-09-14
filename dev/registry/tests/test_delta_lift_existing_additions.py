"""Lifting an already defaulted declaration preserves its effective references."""

import json

import pytest

from dev.registry.edition_delta_migration import (
    _Block,
    _block_row,
    _defaulted,
    _Defaults,
    _delta_authored,
    _lift,
    _lifted_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_reference_defaults_do_not_claim_member_inheritance() -> None:
    assert not _delta_authored({"casilla_source_refs": ["design"]})
    assert not _delta_authored({"casilla_source_refs": ["design"], "predecessor": {"none": {}}})
    assert _delta_authored({"casilla_source_refs": ["design"], "predecessor": "2023"})


@pytest.mark.parametrize("scope", ["row", "table", "inline"])
@pytest.mark.parametrize("extra", [[], ["dictionary", "xsd"]])
def test_existing_additions_drop_duplicate_default_without_changing_references(scope: str, extra: list[str]) -> None:
    header = '[[revisions."2024".casillas]]\nid = "0568"\n'
    refs = "additional_source_refs = " + json.dumps(["design", *extra])
    text = {
        "row": header + refs + "\n",
        "table": header + '[revisions."2024".casillas.constraints]\n' + refs + "\n",
        "inline": header + "constraints = { " + refs + " }\n",
    }[scope]
    raw = _block_row(text)
    defaults = _Defaults(source_refs=("design",), orden=())
    effective = _defaulted(raw, defaults)
    if "constraints" in raw:
        effective["constraints"] = _defaulted(raw["constraints"], defaults)
    lift = _lift(effective, source_default=defaults.source_refs, orden=())
    actual = _block_row(_lifted_text(_Block(text, raw), lift))
    assert actual == lift.row
    target = actual if scope == "row" else actual["constraints"]
    assert target.get("additional_source_refs", []) == extra
    assert _defaulted(target, defaults)["source_refs"] == ["design", *extra]
