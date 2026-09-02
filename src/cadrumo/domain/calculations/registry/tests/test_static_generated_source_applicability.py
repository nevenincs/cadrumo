"""The diagnostic copy of a source answers applicability exactly as the source does.

``StaticGeneratedArtifactSource`` copies the byte-authority fields a generated
artifact verifier consumes, and the ``GeneratedArtifactSource`` protocol it
serves declares ``applies_across``. The copy did not implement it, so every
probe through the generated-provenance path raised ``AttributeError`` rather
than answering. These tests pin both halves of the repair: the copy implements
the member, and it delegates to the same rule the live source uses instead of
restating it.
"""

from __future__ import annotations

import datetime

import pytest

from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..schema_references import SourceReference, source_window_applies_across
from ..static_inspection import StaticGeneratedArtifactSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SPANS: tuple[tuple[datetime.date, datetime.date | None], ...] = (
    (datetime.date(2019, 1, 1), datetime.date(2019, 12, 31)),
    (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)),
    (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)),
    (datetime.date(2030, 1, 1), None),
)


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def sources(authority: ValidatedRegistryAuthority) -> tuple[SourceReference, ...]:
    return tuple(authority.catalogues.sources.values())


def test_the_copy_answers_every_span_exactly_as_its_source(sources: tuple[SourceReference, ...]) -> None:
    """Across the whole source catalogue the copy never diverges from the live source."""
    assert sources, "the bundled catalogue must carry sources"
    for source in sources:
        copied = StaticGeneratedArtifactSource.from_source(source)
        for span_from, span_to in _SPANS:
            assert copied.applies_across(span_from, span_to) == source.applies_across(span_from, span_to), (
                f"copy of {source.id} diverged on span {span_from}..{span_to}"
            )


def test_a_window_closing_before_the_span_does_not_apply() -> None:
    """A window that ends before the span opens is outside it."""
    assert not source_window_applies_across(
        applies_from=datetime.date(2019, 1, 1),
        applies_to=datetime.date(2020, 12, 31),
        span_from=datetime.date(2025, 1, 1),
        span_to=datetime.date(2025, 12, 31),
    )


def test_a_window_opening_after_the_span_does_not_apply() -> None:
    """A window that begins after the span closes is outside it."""
    assert not source_window_applies_across(
        applies_from=datetime.date(2026, 1, 1),
        applies_to=None,
        span_from=datetime.date(2019, 1, 1),
        span_to=datetime.date(2019, 12, 31),
    )


def test_an_open_bound_means_open_not_unknown() -> None:
    """An absent bound opens the window in that direction rather than refusing."""
    assert source_window_applies_across(
        applies_from=None,
        applies_to=None,
        span_from=datetime.date(2025, 1, 1),
        span_to=datetime.date(2025, 12, 31),
    )
    assert source_window_applies_across(
        applies_from=datetime.date(2019, 1, 1),
        applies_to=None,
        span_from=datetime.date(2025, 1, 1),
        span_to=None,
    )


def test_the_copy_carries_the_member_its_protocol_declares() -> None:
    """The concrete copy implements the protocol member, not merely the fields.

    The regression this guards is exactly the shipped defect: the dataclass
    carried ``applies_from`` and ``applies_to`` and satisfied every field of the
    protocol, so nothing structural complained, while the one method the
    verifier actually calls was absent.
    """
    assert callable(getattr(StaticGeneratedArtifactSource, "applies_across", None))
