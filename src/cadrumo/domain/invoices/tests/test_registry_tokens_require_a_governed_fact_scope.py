"""A missing governed-fact scope is not reported as an undeclared invoice token."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.time.clock import today_madrid
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ...calculations.registry.tests.fact_scope import outside_governed_fact_validation
from ..enums import InvoiceLegalMention, IvaRate, invoice_legal_mention_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCOPE_REFUSAL = "requires an explicit generation-pinned governed-fact scope"
_RATE_SLOT = "RATE_2"


def _declared_legal_mention() -> str:
    with bundled_indexed_authority().operation():
        return str(invoice_legal_mention_declarations(today_madrid())[0].token)


@pytest.mark.parametrize("token_type", (IvaRate, InvoiceLegalMention))
def test_a_token_validator_refuses_a_missing_scope_as_an_invariant_failure(token_type: type) -> None:
    token = _RATE_SLOT if token_type is IvaRate else _declared_legal_mention()

    with (
        outside_governed_fact_validation(),
        pytest.raises(InternalInvariantError, match=_SCOPE_REFUSAL),
    ):
        TypeAdapter(token_type).validate_python(token)


@pytest.mark.parametrize("token_type", (IvaRate, InvoiceLegalMention))
def test_the_same_token_validates_inside_a_scope(token_type: type) -> None:
    """CONTROL: the refusal above is the missing scope, not the token."""
    token = _RATE_SLOT if token_type is IvaRate else _declared_legal_mention()

    with bundled_indexed_authority().operation():
        assert TypeAdapter(token_type).validate_python(token) is not None


@pytest.mark.parametrize("token_type", (IvaRate, InvoiceLegalMention))
def test_an_undeclared_token_is_still_a_validation_error(token_type: type) -> None:
    with bundled_indexed_authority().operation(), pytest.raises(ValidationError, match="not declared"):
        TypeAdapter(token_type).validate_python("NO_SUCH_TOKEN")
