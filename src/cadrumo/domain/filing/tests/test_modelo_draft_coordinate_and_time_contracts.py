"""``ModeloDraft`` pins its lifecycle instants and its collection coordinates.

Three gaps in one aggregate, all with the same shape: the builder produces a
coherent draft, nothing enforced that coherence on the model, and the encrypted
repository round-tripped whatever it was handed.

* Lifecycle instants were bare ``datetime``. Draft ordering and the approval
  decision compare them, so a naive or ``+01:00`` value made those comparisons
  ambiguous while :func:`~core.time.validate_utc_aware` — the shared contract the
  producers already use — rejected the same values.
* ``period`` and ``snapshot_ref`` are one filing period expressed twice; the
  builder derives both from a single :class:`~core.Period`, but only the modelo
  axis was checked, leaving the year and period token free to disagree.
* ``values`` and ``binding_values`` had no uniqueness rule, so two rows could
  claim one casilla, or one ``(binding_id, row_index)`` coordinate.

Every test constructs the model directly, because what is under test is what the
aggregate ACCEPTS. A value the happy path never produces is exactly the one a
broken producer or a tampered stored row would carry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind, Period
from ....core.time import validate_utc_aware
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ...submission import ModeloDraftStatus
from .. import (
    ModeloBindingValue,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_UTC_INSTANT = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 5, 3, 12, 0)
_OFFSET_INSTANT = datetime(2026, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1)))
_NIF = "12345678Z"


def _value(casilla_id: str = "01", amount: str = "1000.00") -> ModeloValue:
    return ModeloValue(
        casilla_id=casilla_id,
        value=Decimal(amount),
        kind=ModeloValueKind.LITERAL,
        source="registry input",
    )


def _binding_value(binding_id: str, *, row_index: int | None = None) -> ModeloBindingValue:
    return ModeloBindingValue(
        binding_id=binding_id,
        value=Decimal("1000.00"),
        kind=ModeloValueKind.LITERAL,
        source=BindingSourceKind.MANUAL_INPUT,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-dr-130-2019",),
        row_index=row_index,
    )


def _draft(**overrides: object) -> ModeloDraft:
    """Build the coherent draft the production builder emits, with overrides."""
    period = Period.from_year_and_code(2026, "1T")
    kwargs: dict[str, object] = {
        "draft_id": "draft-coordinate-test",
        "modelo": "130",
        "period": period,
        "profile_tax_id": _NIF,
        "subject_tax_id": _NIF,
        "snapshot_ref": RegistrySnapshotRef(
            modelo="130",
            revision_id="2019-y-siguientes",
            modelo_year=period.filing_year,
            period=period.registry_token,
        ),
        "status": ModeloDraftStatus.BORRADOR,
        "values": (_value(),),
        "created_at": _UTC_INSTANT,
        "updated_at": _UTC_INSTANT,
        "schema_version": "registry:130:2019-y-siguientes",
    }
    kwargs.update(overrides)
    return ModeloDraft.model_validate(kwargs)


def test_the_coherent_builder_shape_still_constructs() -> None:
    """Positive control for every refusal below.

    Without it an all-refused result would look like three working guards while
    actually meaning the base fixture no longer represents a real draft.
    """
    draft = _draft()

    assert draft.created_at == _UTC_INSTANT
    assert draft.snapshot_ref.modelo_year == draft.period.filing_year
    assert draft.snapshot_ref.period == draft.period.registry_token
    assert len(draft.values) == 1


# --------------------------------------------------------------------------
# Lifecycle instants
# --------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["created_at", "updated_at", "approved_at"])
@pytest.mark.parametrize("bad_instant", [_NAIVE_INSTANT, _OFFSET_INSTANT])
def test_lifecycle_instants_refuse_naive_and_offset_values(field: str, bad_instant: datetime) -> None:
    """Every lifecycle instant refuses what the shared UTC contract refuses.

    ``approved_at`` is optional, so its refusal is asserted separately from its
    ``None`` case: optional and unvalidated are different properties, and the
    field was previously both.
    """
    with pytest.raises(ValidationError):
        _draft(**{field: bad_instant})


def test_the_shared_utc_contract_refuses_the_same_values() -> None:
    """Cross-check: the refusals mirror the core contract, not a local rule.

    This is what makes the enrollment meaningful — the draft is not inventing a
    stricter-or-looser notion of a UTC instant than the rest of the project.
    """
    for bad_instant in (_NAIVE_INSTANT, _OFFSET_INSTANT):
        with pytest.raises(ValueError):
            validate_utc_aware(bad_instant)

    assert validate_utc_aware(_UTC_INSTANT) == _UTC_INSTANT


def test_approved_at_stays_optional() -> None:
    """Anti-tautology: typing the field did not make approval mandatory."""
    assert _draft().approved_at is None
    assert _draft(approved_at=_UTC_INSTANT).approved_at == _UTC_INSTANT


# --------------------------------------------------------------------------
# Snapshot coordinate coherence
# --------------------------------------------------------------------------


def test_draft_refuses_a_snapshot_year_that_is_not_its_filing_year() -> None:
    """A 2026 draft cannot carry a 2025 snapshot reference."""
    period = Period.from_year_and_code(2026, "1T")
    with pytest.raises(ValidationError, match="filing year"):
        _draft(
            snapshot_ref=RegistrySnapshotRef(
                modelo="130",
                revision_id="2019-y-siguientes",
                modelo_year=2025,
                period=period.registry_token,
            ),
        )


def test_draft_refuses_a_snapshot_period_token_that_is_not_its_period() -> None:
    """A 1T draft cannot carry a 4T snapshot reference."""
    with pytest.raises(ValidationError, match="period token"):
        _draft(
            snapshot_ref=RegistrySnapshotRef(
                modelo="130",
                revision_id="2019-y-siguientes",
                modelo_year=2026,
                period="4T",
            ),
        )


def test_the_modelo_axis_refusal_is_unchanged() -> None:
    """The pre-existing modelo check still fires; this change extended it.

    Guards against the year/token additions accidentally replacing rather than
    completing the coordinate contract.
    """
    period = Period.from_year_and_code(2026, "1T")
    with pytest.raises(ValidationError, match="snapshot_ref modelo"):
        _draft(
            snapshot_ref=RegistrySnapshotRef(
                modelo="100",
                revision_id="2019-y-siguientes",
                modelo_year=period.filing_year,
                period=period.registry_token,
            ),
        )


# --------------------------------------------------------------------------
# Collection coordinate uniqueness
# --------------------------------------------------------------------------


def test_draft_refuses_two_rows_claiming_one_casilla() -> None:
    """Duplicate casilla ids leave ambiguous last-write/lookup semantics."""
    with pytest.raises(ValidationError, match="casilla more than once"):
        _draft(values=(_value("01", "1000.00"), _value("01", "2000.00")))


def test_draft_refuses_two_rows_claiming_one_binding_coordinate() -> None:
    """A repeated ``(binding_id, row_index)`` pair is a duplicate coordinate."""
    with pytest.raises(ValidationError, match="coordinate more than once"):
        _draft(
            binding_values=(
                _binding_value("irpf.previous_year_economic_activity_net_income"),
                _binding_value("irpf.previous_year_economic_activity_net_income"),
            ),
        )


def test_distinct_casillas_and_distinct_binding_rows_are_accepted() -> None:
    """Positive control: uniqueness did not forbid multi-value drafts.

    ``row_index`` is part of the binding coordinate, so a repeating record
    legitimately carries one ``binding_id`` many times — a rule keyed on
    ``binding_id`` alone would break every detail-record draft.
    """
    draft = _draft(
        values=(_value("01", "1000.00"), _value("02", "300.00")),
        binding_values=(
            _binding_value("irpf.previous_year_economic_activity_net_income", row_index=1),
            _binding_value("irpf.previous_year_economic_activity_net_income", row_index=2),
        ),
    )

    assert len(draft.values) == 2
    assert len(draft.binding_values) == 2
    assert {value.row_index for value in draft.binding_values} == {1, 2}
