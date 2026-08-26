"""Real-behavior proofs for the transient financial operand contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from .._financial_operand import (
    OperationFinancialOperandRefusalReason,
    OperationTransientFinancialOperandAccess,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandExpiry,
    OperationTransientFinancialOperandProtocolV1,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandRelease,
    OperationTransientFinancialOperandRequirement,
    OperationTransientFinancialOperandSubmission,
)
from ..secret_submission import EphemeralSecretSubmission, OperationSecretRequirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)

_OPERAND_RECORDS = (
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandRequirement,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandExpiry,
    OperationTransientFinancialOperandRelease,
)


def _declaration(**overrides: object) -> OperationTransientFinancialOperandDeclaration:
    values: dict[str, object] = {
        "operand_kind": "pago.fraccionado",
        "currency": "EUR",
        "scale": 2,
        "minimum": Decimal("0.00"),
        "maximum": Decimal("1000.00"),
        "lifetime": timedelta(minutes=5),
    }
    values.update(overrides)
    return OperationTransientFinancialOperandDeclaration(**values)  # type: ignore[arg-type]


def test_a_declaration_admits_only_its_declared_scale_and_range() -> None:
    """An operand is judged on its own declared terms, not inside the executor."""
    declaration = _declaration()

    assert declaration.admits(Decimal("12.34"))
    assert declaration.admits(Decimal("0.00"))
    assert declaration.admits(Decimal("1000.00"))
    assert not declaration.admits(Decimal("12.345"))
    assert not declaration.admits(Decimal("1000.01"))
    assert not declaration.admits(Decimal("-0.01"))


def test_a_declaration_refuses_an_unbounded_lifetime_and_an_inverted_range() -> None:
    """The bounds that make an operand transient are validated, not documented."""
    with pytest.raises(ValidationError):
        _declaration(lifetime=timedelta(hours=2))
    with pytest.raises(ValidationError):
        _declaration(lifetime=timedelta())
    with pytest.raises(ValidationError):
        _declaration(minimum=Decimal("10.00"), maximum=Decimal("1.00"))


def test_a_declaration_refuses_a_scale_beyond_currency_representation() -> None:
    """A declared scale stays inside what a financial amount can represent."""
    with pytest.raises(ValidationError):
        _declaration(scale=9)


def test_no_operand_record_can_carry_an_amount() -> None:
    """The value crosses as a call argument, so no record can serialize it."""
    for record in _OPERAND_RECORDS:
        for name, field in record.model_fields.items():
            annotation = str(field.annotation)
            if record is OperationTransientFinancialOperandDeclaration and name in {"minimum", "maximum"}:
                continue
            assert "Decimal" not in annotation, f"{record.__name__}.{name} carries an amount"


def test_no_operand_record_can_carry_a_durable_derivative() -> None:
    """A digest of an amount over a known scale is the amount, so none is allowed."""
    forbidden = ("digest", "hash", "fingerprint", "checksum", "signature")
    for record in _OPERAND_RECORDS:
        for name in record.model_fields:
            assert not any(token in name.lower() for token in forbidden), f"{record.__name__}.{name}"


def test_the_operand_contract_is_distinct_from_the_ephemeral_secret_port() -> None:
    """An amount is not credential material and does not travel the secret port."""
    assert OperationTransientFinancialOperandSubmission is not EphemeralSecretSubmission
    assert not issubclass(OperationTransientFinancialOperandRequirement, OperationSecretRequirement)
    assert "submit_ephemeral_secret" not in dir(OperationTransientFinancialOperandSubmission)
    assert "submit_transient_financial_operand" not in dir(EphemeralSecretSubmission)


def test_every_settlement_record_requires_an_aware_timestamp() -> None:
    """A naive settlement time cannot be recorded for a bounded runtime wait."""
    requirement = OperationTransientFinancialOperandRequirement.model_construct(
        operand_kind="pago.fraccionado",
        expires_at=_NOW,
    )
    with pytest.raises(ValidationError):
        OperationTransientFinancialOperandRelease(
            requirement=requirement,
            released_at=datetime(2026, 3, 4, 9, 0, 0),  # the naive value under test
        )


def test_the_settlement_outcomes_are_disjoint_and_self_describing() -> None:
    """Acceptance, refusal, expiry and release never read as one another."""
    outcomes = {
        record.model_fields["outcome"].default
        for record in (
            OperationTransientFinancialOperandAcknowledgement,
            OperationTransientFinancialOperandRefusal,
            OperationTransientFinancialOperandExpiry,
            OperationTransientFinancialOperandRelease,
        )
    }

    assert outcomes == {"accepted", "refused", "expired", "released"}


def test_a_refusal_names_a_reason_the_caller_can_act_on() -> None:
    """Every refusal reason is a distinct, actionable condition."""
    reasons = {member.value for member in OperationFinancialOperandRefusalReason}

    assert reasons == {
        "expired",
        "cancelled",
        "out_of_declared_range",
        "scale_not_representable",
        "unknown_requirement",
        "already_settled",
    }


def test_the_broker_protocol_exposes_no_durable_derivative_of_an_operand() -> None:
    """The broker settles and releases; it never hands back a stored amount."""
    members = {name for name in dir(OperationTransientFinancialOperandProtocolV1) if not name.startswith("_")}

    assert {"declare_requirement", "grant_access", "release", "expire_lapsed"} <= members
    assert not any("digest" in name or "hash" in name for name in members)


def test_the_contracts_are_runtime_checkable_structural_ports() -> None:
    """A supervisor can be checked against these ports without inheriting them."""
    for protocol in (
        OperationTransientFinancialOperandSubmission,
        OperationTransientFinancialOperandAccess,
        OperationTransientFinancialOperandProtocolV1,
    ):
        assert getattr(protocol, "_is_runtime_protocol", False), protocol.__name__
        assert not issubclass(protocol, BaseModel)
