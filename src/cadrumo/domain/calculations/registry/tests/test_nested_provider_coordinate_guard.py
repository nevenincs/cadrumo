"""The relative-coordinate guard must see a coordinate nested inside a provider.

A provider declares timeless intent and derives its source coordinate from the
target filing context at resolve time. The structural guard enforces that by
refusing a field whose TYPE names a concrete coordinate -- an ``int``, a
``RevisionId``, a ``date``.

A guard that inspected only a provider's own fields would be satisfied by
moving the coordinate one model down: ``window: SourceWindow`` where
``SourceWindow`` carries ``filing_year: int`` is exactly as pinned as
``filing_year: int`` on the provider itself, and would have pinned every
resolution to one year while reading as a structured, relative declaration.

These tests are detector teeth over fabricated provider models: nothing here
touches the enrolled registration table, and each defect is paired with the
clean shape it is a defect of, so the guard is shown to detect rather than
merely to be present.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import pytest
from pydantic import BaseModel

from ..binding_provider_registration import absolute_coordinate_offenders
from ..ids import RevisionId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _RelativeWindow(BaseModel):
    """A nested shape naming no coordinate at all."""

    source_periods: tuple[str, ...] = ()


class _YearPinnedWindow(BaseModel):
    """A nested shape pinning one concrete filing year."""

    filing_year: int


class _RevisionPinnedWindow(BaseModel):
    """A nested shape pinning one concrete revision."""

    revision_id: RevisionId


class _DatePinnedWindow(BaseModel):
    """A nested shape pinning one concrete date."""

    effective_on: date


class _TemporalUnionMember(BaseModel):
    """The one nested shape allowed to carry moving numbers."""

    kind: Literal["offset"] = "offset"
    years: int


class _CleanProvider(BaseModel):
    kind: Literal["clean"] = "clean"
    source_casilla_id: str
    window: _RelativeWindow = _RelativeWindow()


class _NestedYearProvider(BaseModel):
    kind: Literal["nested_year"] = "nested_year"
    window: _YearPinnedWindow


class _NestedRevisionProvider(BaseModel):
    kind: Literal["nested_revision"] = "nested_revision"
    window: _RevisionPinnedWindow


class _NestedDateProvider(BaseModel):
    kind: Literal["nested_date"] = "nested_date"
    window: _DatePinnedWindow


class _OptionalNestedYearProvider(BaseModel):
    kind: Literal["optional_nested_year"] = "optional_nested_year"
    window: _YearPinnedWindow | None = None


class _TwiceNestedYearProvider(BaseModel):
    kind: Literal["twice_nested_year"] = "twice_nested_year"
    outer: _NestedYearProvider


class _TemporalOnlyProvider(BaseModel):
    kind: Literal["temporal_only"] = "temporal_only"
    temporal: _TemporalUnionMember


class _LayoutAddressedRow(BaseModel):
    """A nested shape whose integer is named after a record-layout field."""

    offset: int


class _NestedLayoutNameProvider(BaseModel):
    kind: Literal["nested_layout_name"] = "nested_layout_name"
    row: _LayoutAddressedRow


class _LayoutAddressedProvider(BaseModel):
    """The provider's OWN record-layout address, which is authored design data."""

    kind: Literal["layout_addressed"] = "layout_addressed"
    offset: int
    length: int
    decimals: int


class _TemporalNamedRow(BaseModel):
    """A nested shape reusing the provider-level ``temporal`` field name."""

    temporal: int


class _NestedTemporalNameProvider(BaseModel):
    kind: Literal["nested_temporal_name"] = "nested_temporal_name"
    row: _TemporalNamedRow


class _SelfReferentialProvider(BaseModel):
    kind: Literal["self_referential"] = "self_referential"
    parent: _SelfReferentialProvider | None = None


def test_clean_provider_reports_nothing() -> None:
    """A provider with no coordinate at any depth is silent."""
    assert absolute_coordinate_offenders("provider 'clean'", _CleanProvider) == ()


@pytest.mark.parametrize(
    ("model", "expected_path", "expected_field"),
    [
        (_NestedYearProvider, "provider.window", "filing_year"),
        (_NestedRevisionProvider, "provider.window", "revision_id"),
        (_NestedDateProvider, "provider.window", "effective_on"),
        (_OptionalNestedYearProvider, "provider.window", "filing_year"),
        (_TwiceNestedYearProvider, "provider.outer.window", "filing_year"),
    ],
)
def test_nested_coordinate_is_detected_with_its_path(
    model: type[BaseModel],
    expected_path: str,
    expected_field: str,
) -> None:
    """The coordinate is reported, and the diagnostic names where it sits."""
    offenders = absolute_coordinate_offenders("provider", model)

    assert offenders == (f"{expected_path} declares absolute coordinate field {expected_field!r}",)


def test_the_providers_own_temporal_field_is_skipped() -> None:
    """The temporal union is where a relative coordinate belongs, so it is not walked."""
    assert absolute_coordinate_offenders("provider", _TemporalOnlyProvider) == ()


def test_the_providers_own_record_layout_address_is_accepted() -> None:
    """``offset``/``length``/``decimals`` on the provider are authored design data."""
    assert absolute_coordinate_offenders("provider", _LayoutAddressedProvider) == ()


@pytest.mark.parametrize(
    ("model", "expected_field"),
    [(_NestedLayoutNameProvider, "offset"), (_NestedTemporalNameProvider, "temporal")],
)
def test_the_exemptions_do_not_follow_their_names_into_a_nested_model(
    model: type[BaseModel],
    expected_field: str,
) -> None:
    """Both exemptions belong to the provider model itself, not to a name.

    ``offset`` on a provider is an address in an official fixed-width record and
    ``temporal`` on a provider is the union built to carry relative coordinates.
    A nested model reusing either name is a different field under a different
    contract, so an exemption that followed the NAME down would let any nested
    structure re-admit an absolute coordinate just by spelling it ``offset``.
    """
    offenders = absolute_coordinate_offenders("provider", model)

    assert offenders == (f"provider.row declares absolute coordinate field {expected_field!r}",)


def test_self_referential_provider_terminates() -> None:
    """A model reachable from itself is visited once rather than forever."""
    assert absolute_coordinate_offenders("provider", _SelfReferentialProvider) == ()
