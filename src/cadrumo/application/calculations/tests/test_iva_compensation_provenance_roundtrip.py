"""Persistence-boundary proof for the IVA compensation provenance pair.

Covers the encrypted `SecureObjectRepository` boundary the compensation
history writes through, with a real key provider and a real SQLite engine --
no repository double, because a double returning what the assertion wants is
the canonical false positive.

Three claims, in order of what each can catch:

* the pair survives a strict round trip with EVERY defaultable field carrying a
  non-default value, so a save-drops-field / load-re-defaults-field regression
  cannot hide behind a fixture that used the default;
* deleting the persisted ``provenance`` from the stored payload makes the load
  RAISE rather than silently re-defaulting -- the anti-tautology proof, and the
  reason the field is required with no default;
* the discriminated pair refuses every state the domain does not have.

The anti-tautology proof asserts the field was PRESENT before deleting it. A
proof that deletes an absent key and then observes a refusal proves nothing
about the deletion, and would keep passing if the producer stopped writing the
field at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core import IvaCompensationStateProvenance
from ....core.period import Period
from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..iva_compensation_history import IvaCompensationHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRESENTED_AT = datetime(2026, 1, 20, 10, 30, tzinfo=UTC)
_EXPEDIENTE = "202530300000001Z"
_DIGEST = "b" * 64


def _fully_populated_state() -> IvaCompensationPeriodState:
    """Return an AEAT-capture state with no field left at its default."""
    return IvaCompensationPeriodState(
        taxpayer_nif="12345678Z",
        provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        expediente_id=_EXPEDIENTE,
        status="presentada",
        presented_at=_PRESENTED_AT,
        prior_pending_amount=Decimal("100.00"),
        applied_amount=Decimal("25.00"),
        pending_for_later_amount=Decimal("75.00"),
        period_result_amount=Decimal("-75.00"),
        final_result_amount=Decimal("0.00"),
        generated_amount=Decimal("50.00"),
        available_end_amount=Decimal("125.00"),
        source_observation_key="303:2025:4T:202530300000001Z",
        source_artefact_sha256=_DIGEST,
    )


def test_the_provenance_pair_survives_a_strict_round_trip(tmp_path: Path) -> None:
    """Save and load through the real encrypted boundary; assert model equality."""
    original = _fully_populated_state()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = IvaCompensationHistoryRepository()
        repository.save_period(original)
        loaded = repository.load_period(original.period)

    assert loaded == original
    assert loaded is not None
    assert loaded.provenance is IvaCompensationStateProvenance.AEAT_CAPTURE
    assert loaded.expediente_id == _EXPEDIENTE
    assert loaded.status == "presentada"


def test_every_defaultable_field_carries_a_non_default_value() -> None:
    """Guard the round trip above against a fixture that uses the defaults.

    Without this, a save that dropped an optional field and a load that
    re-defaulted it would compare equal and the round trip would pass while
    the boundary was broken.
    """
    state = _fully_populated_state()
    defaulted = [
        name
        for name, field in type(state).model_fields.items()
        if not field.is_required() and getattr(state, name) == field.get_default(call_default_factory=True)
    ]
    assert defaulted == [], f"round-trip fixture leaves fields at their default: {defaulted}"


def test_a_state_stripped_of_its_persisted_provenance_refuses_to_load(tmp_path: Path) -> None:
    """The anti-tautology proof: delete the field, assert refusal, not a default.

    The refusal is asserted on its REASON, not merely on its type. A bare
    ``pytest.raises(ValidationError)`` here passes vacuously: with the
    expediente still in the payload, a model that gave ``provenance`` a
    non-AEAT default would refuse anyway -- for violating the pair rule, not
    for the missing field. That refusal looks identical from outside, so the
    proof would keep passing with the very default it exists to forbid.
    """
    original = _fully_populated_state()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = IvaCompensationHistoryRepository()
        repository.save_period(original)
        identifier = repository.extract_identifier(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == repository.namespace,
            SecureObjectRow.object_key == identifier,
        )

        def mutate(payload):
            state_payload = payload["payload"]
            assert "provenance" in state_payload, (
                "the producer must write provenance before deleting it proves anything"
            )
            assert state_payload["provenance"] == IvaCompensationStateProvenance.AEAT_CAPTURE.value
            del state_payload["provenance"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError) as caught:
            repository.load_period(original.period)

    reported = [(error["type"], error["loc"]) for error in caught.value.errors()]
    assert reported == [("missing", ("payload", "provenance"))], (
        f"expected only a missing-provenance error, got {reported}"
    )


def test_an_operator_declared_state_cannot_carry_an_aeat_expediente() -> None:
    """The impersonation the discriminated pair exists to make unrepresentable."""
    with pytest.raises(ValidationError, match="operator_seed compensation state must not carry an expediente_id"):
        IvaCompensationPeriodState(
            taxpayer_nif="12345678Z",
            provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            expediente_id=_EXPEDIENTE,
            presented_at=_PRESENTED_AT,
            generated_amount=Decimal("0.00"),
            available_end_amount=Decimal("10.00"),
            source_observation_key="303:seed:2025:4T",
        )


def test_an_aeat_capture_without_an_expediente_refuses() -> None:
    """The other half of the pair: an AEAT row must carry what AEAT issued."""
    with pytest.raises(
        ValidationError, match="aeat_capture compensation state must carry the AEAT-issued expediente_id"
    ):
        IvaCompensationPeriodState(
            taxpayer_nif="12345678Z",
            provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            presented_at=_PRESENTED_AT,
            generated_amount=Decimal("0.00"),
            available_end_amount=Decimal("10.00"),
            source_observation_key="303:2025:4T",
        )


@pytest.mark.parametrize(
    "provenance",
    [
        IvaCompensationStateProvenance.APP_FILING,
        IvaCompensationStateProvenance.CASILLA_RECONSTRUCTION,
        IvaCompensationStateProvenance.OPERATOR_SEED,
        IvaCompensationStateProvenance.OPERATOR_CORRECTION,
    ],
)
def test_status_is_refused_on_every_non_aeat_provenance(
    provenance: IvaCompensationStateProvenance,
) -> None:
    """`status` reports an AEAT-printed register status or nothing at all.

    This is the clause that stops provenance being readable off two fields
    that can disagree, which is the state the old model was in on four of its
    five supplying paths.
    """
    with pytest.raises(ValidationError):
        IvaCompensationPeriodState(
            taxpayer_nif="12345678Z",
            provenance=provenance,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            status="presentada",
            presented_at=_PRESENTED_AT,
            generated_amount=Decimal("0.00"),
            available_end_amount=Decimal("10.00"),
            source_observation_key="303:2025:4T",
        )


def test_the_provenance_enum_names_every_supplying_path_and_no_catch_all() -> None:
    """A new supplying path must be added here, never absorbed into a member."""
    assert {member.value for member in IvaCompensationStateProvenance} == {
        "aeat_capture",
        "app_filing",
        "casilla_reconstruction",
        "operator_seed",
        "operator_correction",
    }
