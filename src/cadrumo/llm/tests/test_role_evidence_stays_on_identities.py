"""The prompt does not grow: role evidence stays on the identity fields.

Deterministic co-location attributes address values in CODE, from the document's
own layout, precisely so the reader is never asked for more. This gate holds that
line. The design target is a lowest-bound vision model with a hard context
budget, so every added key costs the fields already in the prompt, and a key with
no consumer buys review surface rather than safety.

Gated on the PROPERTY rather than a tally: the assertion is that every
role-evidence-bearing field names a party identity and no attributed address
field carries one. A legitimately-added identity field passes; an address field
acquiring a role-evidence key does not. A pinned count would have to be edited
either way, which trains everyone to edit it.

See Also:
    :func:`~application.ledger.party_colocation.resolve_party_attribution_by_colocation`
        The code that attributes address values instead of the prompt.
"""

from __future__ import annotations

import pytest

from ...application.ledger.party_attribution import PARTY_ATTRIBUTED_ADDRESS_FIELDS, party_addresses
from ...core.period import Period
from ..invoice_extraction_prompt import build_invoice_extraction_prompt
from ..invoice_field_contract import (
    INVOICE_FIELD_CONTRACTS,
    identity_field_names,
    role_evidence_key_for_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _role_evidence_bearing() -> set[str]:
    return {contract.field_name for contract in INVOICE_FIELD_CONTRACTS if contract.carries_role_evidence}


def test_no_attributed_address_field_asks_the_reader_for_role_evidence() -> None:
    """The widening the record refused, asserted as a property of the contracts."""
    assert _role_evidence_bearing() & PARTY_ATTRIBUTED_ADDRESS_FIELDS == set()


def test_every_role_evidence_key_belongs_to_a_party_identity_field() -> None:
    """Role evidence is an identity concept; nothing else may acquire it."""
    assert _role_evidence_bearing() == set(identity_field_names())
    assert _role_evidence_bearing() == {party.tax_id_field for party in party_addresses()}


def test_the_prompt_never_names_an_address_role_evidence_key() -> None:
    """The rendered prompt is checked, not only the contracts that build it.

    A contract table can stay honest while the prompt template hardcodes an extra
    instruction, and the prompt is what the model's context actually pays for.
    """
    compiled = build_invoice_extraction_prompt(period=Period(filing_year=2026, code="1T"))
    rendered = compiled.model_dump_json()

    for field in sorted(PARTY_ATTRIBUTED_ADDRESS_FIELDS):
        assert role_evidence_key_for_field(field) not in rendered
