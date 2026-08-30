"""``ExtractionProducer`` records its origin on the one canonical axis.

The producer answers HOW a payload's fields were recovered. That question had
two homes -- a local ``ExtractionSourceKind`` here and the ``FieldOrigin`` the
ingestion design puts in ``core`` -- which is one concept with two spellings and
two independently-drifting token sets. The local one is gone; these gates pin
that it stays gone and that the surviving field is genuinely closed rather than
a string that happens to hold enum-looking values today.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ... import llm
from ...core import FieldOrigin
from ...llm.suggestions import ExtractionProducer

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_a_producer_validates_with_a_field_origin() -> None:
    """The positive control. Without it every refusal below could pass vacuously."""
    producer = ExtractionProducer(
        source_kind=FieldOrigin.EXACT_STRUCTURED,
        identity="en16931-cii",
        revision="D16B",
    )

    assert producer.source_kind is FieldOrigin.EXACT_STRUCTURED


@pytest.mark.parametrize("origin", list(FieldOrigin))
def test_every_declared_origin_is_accepted(origin: FieldOrigin) -> None:
    """No member is admissible in the enum but rejected at this boundary."""
    producer = ExtractionProducer(source_kind=origin, identity="qwen2.5vl:3b", revision="sha256:ab")

    assert producer.source_kind is origin


@pytest.mark.parametrize("bogus", ["structured_record", "vision_model", "guessed", ""])
def test_a_bogus_origin_string_is_refused(bogus: str) -> None:
    """Including the two retired tokens, which must not resolve to anything.

    ``structured_record`` and ``vision_model`` were the previous spellings. A
    reader still emitting them fails loudly here rather than being silently
    accepted under a shape that no longer means what it did.
    """
    with pytest.raises(ValidationError):
        ExtractionProducer(source_kind=bogus, identity="en16931-cii", revision="D16B")


def test_the_retired_extraction_source_kind_is_gone_from_the_package() -> None:
    """One concept, one home. A reintroduced alias reddens here."""
    assert not hasattr(llm, "ExtractionSourceKind")
    assert "ExtractionSourceKind" not in llm.__all__
