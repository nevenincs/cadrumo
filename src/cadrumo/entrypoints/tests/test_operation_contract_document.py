"""The contract document the MCP harness ships says what the production registry says.

The document is a rendering of the registry's public contract set, shipped as
data so that operations can be found and described with no runtime running.
It is compared with a fresh rendering, so a registry that moved without it
fails here, and it is read back through the harness's own reader and compared
with the registry's typed descriptions, so a rendering the reader takes
differently fails too.

No count is a pass condition. An operation added to the registry changes the
document and the comparison together.
"""

from __future__ import annotations

import json
from functools import cache

import pytest

from cadrumo_harness.mcp.public_operation_discovery import (
    CONTRACT_PART_SUFFIX,
    contract_part_name,
    read_contract_part,
    shipped_public_descriptions,
)

from ...application.operations.registry import (
    OperationPublicContractSetV1,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from ..operation_composition import build_production_operation_registry
from .operation_contract_document import (
    description_line,
    registered_descriptions,
    render_contract_document,
    shipped_contract_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REGENERATE = "write it again with: python -m dev.harness_data.operation_contract_document"


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry()


@cache
def _registered() -> tuple[OperationPublicDefinitionDescriptionV1, ...]:
    return registered_descriptions(_registry())


def _parts_that_differ(left: dict[str, str], right: dict[str, str]) -> list[str]:
    return sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))


def test_the_shipped_document_is_the_rendered_registry() -> None:
    """Every file beside the document is a part, and each part is what the registry renders to today."""
    rendered = render_contract_document(_registered())
    assert rendered, "the production registry describes no operation; the denominator is empty"
    stale = _parts_that_differ(shipped_contract_document(), rendered)
    assert not stale, f"the shipped contract document no longer matches the registry in {stale}; {_REGENERATE}"


def test_the_harness_reads_back_exactly_the_registry_s_descriptions() -> None:
    """Read by the harness, the document is the registry's own typed description of every operation."""
    registered = {description.contract.definition_id: description for description in _registered()}
    shipped = shipped_public_descriptions()

    assert set(shipped) == set(registered), _REGENERATE
    moved = sorted(definition_id for definition_id in registered if shipped[definition_id] != registered[definition_id])
    assert not moved, f"the shipped contract document describes {moved} differently from the registry; {_REGENERATE}"


def test_the_shipped_contracts_reproduce_the_registry_s_contract_set_digest() -> None:
    """The contracts read back are one whole contract set, and it is the registry's."""
    shipped = OperationPublicContractSetV1.build(
        tuple(description.contract for description in shipped_public_descriptions().values())
    )

    assert shipped.contract_set_digest == _registry().public_contract_set.contract_set_digest, _REGENERATE


def test_a_part_holds_one_family_in_definition_id_order() -> None:
    """A reader that wants one operation finds it in the part its id names."""
    for name, text in shipped_contract_document().items():
        assert name.endswith(CONTRACT_PART_SUFFIX), name
        definition_ids = [description.contract.definition_id for description in read_contract_part(text)]
        assert definition_ids, name
        assert definition_ids == sorted(definition_ids), name
        assert {contract_part_name(definition_id) for definition_id in definition_ids} == {name}


def test_a_member_the_contract_holds_as_a_set_is_written_in_one_order() -> None:
    """A set is walked in an order that differs between processes, and the line does not follow it."""
    judged = 0
    for description in _registered():
        written = json.loads(description_line(description))["contract"]
        for member, held in description.contract.model_dump(mode="python").items():
            if isinstance(held, frozenset) and len(held) > 1:
                judged += 1
                assert written[member] == sorted(written[member]), (description.contract.definition_id, member)
                assert len(written[member]) == len(held)
    assert judged, "no registered contract holds a set of two members; nothing was judged"


def test_a_line_reads_back_as_the_description_it_renders() -> None:
    """Putting a set in order changes no description: each line is its own description again."""
    moved = [
        description.contract.definition_id
        for description in _registered()
        if read_contract_part(description_line(description) + "\n") != (description,)
    ]
    assert not moved


def test_a_registry_that_moves_changes_the_document() -> None:
    """An operation gone, and a request schema changed, are each a different document."""
    registered = _registered()
    shipped = shipped_contract_document()
    gone, changed = registered[0], registered[-1]
    assert gone.contract.definition_id != changed.contract.definition_id

    without_one = render_contract_document(registered[1:])
    with_another_request = render_contract_document(
        (*registered[:-1], changed.model_copy(update={"request_json_schema": {"type": "object"}}))
    )

    assert _parts_that_differ(shipped, without_one) == [contract_part_name(gone.contract.definition_id)]
    assert _parts_that_differ(shipped, with_another_request) == [contract_part_name(changed.contract.definition_id)]


def test_an_operation_described_twice_is_refused_when_the_document_is_rendered() -> None:
    """Two lines for one operation would leave the reader to pick one."""
    registered = _registered()
    with pytest.raises(ValueError, match="described once"):
        render_contract_document((*registered, registered[0]))
