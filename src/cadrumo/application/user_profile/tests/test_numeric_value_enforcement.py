"""Real-behavior tests: the write door enforces declared numeric bounds.

The declaration was inert. `attribution_entity_socios.share_pct` declares
`minimum = 0` and `maximum = 100`, the schema checked that pair for its own
coherence at build time, and then nothing ever compared a value to it -- so
the door accepted `999` and stored it. That value drives the M184 attribution
calculation, which divides a taxable amount between members, so it reached a
filing a human submits to AEAT as a silently wrong number rather than as any
kind of failure.

These go through the real encrypted write path rather than calling the rule
directly, because the rule being correct and the door consulting it are two
different claims and only the second one protects a taxpayer.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from ....domain.user_profile import ProfileSchemaValidationError, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow import workflow_state_repository
from .. import ProfileRepository, profile_create_storage_span, set_active_fields
from .._validation import NUMERIC_VALUE_ISSUE_CODE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
_SOCIOS = "attribution_entity_socios"


def _register_active() -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name="numeric-operator",
            overrides={"identity.tax_id": "12345678Z"},
        ),
    )


def _refusal_context_sequence(
    refusal: pytest.ExceptionInfo[ProfileSchemaValidationError],
    key: str,
) -> Sequence[object]:
    """Read one sequence off a refusal's structured context.

    ``CadrumoError.context`` is ``dict[str, object] | None``, so the two narrowing
    asserts are what let the membership checks below be checked rather than
    inferred against ``object``.
    """
    context = refusal.value.context
    assert context is not None, "the refusal carried no structured context"
    values = context[key]
    assert isinstance(values, Sequence), f"context[{key!r}] is not a sequence: {values!r}"
    return values


def _socio_row(share_pct: str, *, index: int = 0) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path=f"{_SOCIOS}.{index}.nif", value="B12345678"),
        UserProfileFact(path=f"{_SOCIOS}.{index}.name", value="Socio Uno"),
        UserProfileFact(path=f"{_SOCIOS}.{index}.share_pct", value=share_pct),
        UserProfileFact(path=f"{_SOCIOS}.{index}.base_imponible_assigned", value="1000"),
        UserProfileFact(path=f"{_SOCIOS}.{index}.participe_clave", value="1"),
    )


def _write(*facts: UserProfileFact) -> None:
    workflow_state_repository().update(lambda state: set_active_fields(state, facts))


def _stored_share_pct(index: int = 0) -> object:
    record = ProfileRepository().load(_BUCKET_ID).record
    return next(
        (fact.value for fact in record.facts if fact.path == f"{_SOCIOS}.{index}.share_pct"),
        None,
    )


@pytest.mark.parametrize("share_pct", ["999", "abc"])
def test_the_door_refuses_a_value_its_declaration_does_not_admit(share_pct: str) -> None:
    """Both shapes that used to get through, and nothing is left behind.

    `999` was stored and flowed on silently; `abc` was stored and crashed
    later inside a calculation. Neither reaches the record now, and the
    batch is judged as a whole, so the rest of the row does not land either.
    """
    _register_active()

    with pytest.raises(ProfileSchemaValidationError) as refusal:
        _write(*_socio_row(share_pct))

    assert NUMERIC_VALUE_ISSUE_CODE in _refusal_context_sequence(refusal, "issue_codes")
    assert _stored_share_pct() is None


@pytest.mark.parametrize("share_pct", ["0", "100"])
def test_the_door_accepts_a_value_exactly_on_a_bound(share_pct: str) -> None:
    """The boundary, through the real door.

    A socio holding none of an entity or all of it are ordinary filings.
    This is the case an over-strict comparison breaks while every value in
    between keeps working, so it is asserted on the stored record rather
    than on the rule in isolation.
    """
    _register_active()

    _write(*_socio_row(share_pct))

    assert str(_stored_share_pct()) == share_pct


def test_a_malformed_value_is_refused_even_on_an_unbounded_field() -> None:
    """Type binds everywhere, not only where a range happens to be declared.

    Two of the schema's fifty-six numeric fields carry bounds. If the type
    check rode along with the range check, the other fifty-four would keep
    accepting text.
    """
    _register_active()

    with pytest.raises(ProfileSchemaValidationError):
        _write(
            UserProfileFact(path=f"{_SOCIOS}.0.nif", value="B12345678"),
            UserProfileFact(path=f"{_SOCIOS}.0.name", value="Socio Uno"),
            UserProfileFact(path=f"{_SOCIOS}.0.share_pct", value="50"),
            UserProfileFact(path=f"{_SOCIOS}.0.base_imponible_assigned", value="not-an-amount"),
        )


def test_the_refusal_tells_the_operator_what_would_be_accepted() -> None:
    """A refusal naming neither the field nor the range is not actionable."""
    _register_active()

    with pytest.raises(ProfileSchemaValidationError) as refusal:
        _write(*_socio_row("999"))

    assert f"{_SOCIOS}.0.share_pct" in _refusal_context_sequence(refusal, "issue_paths")


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
