"""The schema's declared provenance set binds the facts that carry it.

``UserProfileFact.source`` was a length-constrained string, so the
schema's declared provenance enum bound nothing: a typo persisted
silently as a new, unqueryable origin, and the shipped censal path
stamped a token the schema never declared without any surface
complaining.

Two properties keep that closed. The fact refuses a token the schema does
not declare, and every token shipped code can stamp is declared. The
second is the mechanical form of the check that was missing: the censal
breach was found by hand, and a hand is not a gate.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import (
    PROVENANCE_SOURCE_CENSO_ARTEFACT,
    PROVENANCE_SOURCE_MANUAL_CLI,
)
from ..loader import load_user_profile_schema
from ..values import UserProfileFact, declared_provenance_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_declared_set_is_the_schema_enum() -> None:
    """The enforcement reads the schema, not a copy of it.

    A second hand-maintained list would be the drift this contract
    exists to remove, so the accessor is pinned to the schema field.
    """

    declared = declared_provenance_sources()
    assert declared == frozenset(load_user_profile_schema().field("provenance.source").enum_values)
    assert declared


def test_fact_accepts_every_declared_source() -> None:
    """No declared token may be refused by the carrier that stores it."""

    for token in sorted(declared_provenance_sources()):
        fact = UserProfileFact(path="identity.tax_id", value="12345678Z", source=token)
        assert fact.source == token


def test_fact_refuses_an_undeclared_source() -> None:
    """The point of the contract: an unknown origin cannot be persisted.

    Without this the schema's closed set was prose, and a mistyped
    token became a new origin no query would ever find.
    """

    with pytest.raises(ValidationError) as raised:
        UserProfileFact(path="identity.tax_id", value="12345678Z", source="not_a_declared_source")

    message = str(raised.value)
    assert "not_a_declared_source" in message
    # The refusal names the accepted set, so an operator or agent can act
    # on it rather than guessing what the schema would have taken.
    assert PROVENANCE_SOURCE_MANUAL_CLI in message


def test_the_default_source_is_declared() -> None:
    """A fact built without a source must not be born undeclared."""

    assert UserProfileFact(path="identity.tax_id", value="12345678Z").source in declared_provenance_sources()


def test_every_core_declared_provenance_constant_is_in_the_schema() -> None:
    """The gate the censal breach needed and did not have.

    Provenance tokens are declared by the schema, so the contract is
    anchored there rather than at whichever consumer happens to define a
    string. This checks the constants core publishes for the purpose; a
    token defined in an outer layer is that layer's to check, because a
    domain test reaching upward would invert the dependency direction
    even though no production code does.
    """

    shipped = {PROVENANCE_SOURCE_MANUAL_CLI, PROVENANCE_SOURCE_CENSO_ARTEFACT}
    undeclared = sorted(shipped - declared_provenance_sources())
    assert not undeclared, (
        f"core declares provenance token(s) the schema does not: {undeclared}. "
        "Add the token to provenance.source in the profile schema; do not change what the shipped code stamps."
    )


def test_the_censal_artefact_token_is_declared() -> None:
    """Named explicitly because it is the breach that motivated this.

    The shipped censal-artefact path stamps it, the provenance is real,
    and the schema was simply wrong to omit it.
    """

    assert PROVENANCE_SOURCE_CENSO_ARTEFACT in declared_provenance_sources()
