"""Canonical wire checks for the shared censal fact payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import _censo_payloads
from .._censo_payloads import CensoFactPayload, CensoFileIngestResult, CensoPullResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_censo_fact_payload_round_trips_a_valid_row() -> None:
    row = CensoFactPayload(path="contact.postcode", value="28001", source="censo_artefact_g313")

    assert row.path == "contact.postcode"
    assert row.source == "censo_artefact_g313"


@pytest.mark.parametrize(
    "kwargs",
    (
        {"path": "bad", "value": "x", "source": "censo_artefact_g313"},
        {"path": "", "value": "x", "source": "censo_artefact_g313"},
        {"path": "contact.postcode", "value": "x", "source": ""},
        {"path": "contact.postcode", "value": "x", "source": "a" * 81},
        {"path": "contact.postcode", "value": "x", "source": "undeclared_source_token"},
    ),
)
def test_censo_fact_payload_refuses_malformed_row(kwargs: dict[str, str]) -> None:
    """A malformed path, a blank/oversized source, or an undeclared source is refused."""
    with pytest.raises(ValidationError):
        CensoFactPayload(**kwargs)


def test_censo_transport_and_pull_share_one_canonical_fact_wire_projection() -> None:
    assert not hasattr(_censo_payloads, "CensoPullFactPayload")
    assert not hasattr(_censo_payloads, "CensoFileFactPayload")

    row = CensoFactPayload(path="contact.postcode", value="28001", source="censo_artefact_g313")
    file_result = CensoFileIngestResult(applied=False, facts=(row,))
    pull_result = CensoPullResult(
        applied=False,
        source_url="https://example.invalid/censal",
        adopted=(row,),
        unchanged=(row,),
    )

    assert type(file_result.facts[0]) is CensoFactPayload
    assert type(pull_result.adopted[0]) is CensoFactPayload
    assert type(pull_result.unchanged[0]) is CensoFactPayload
    assert file_result.model_dump(mode="json")["facts"] == [row.model_dump(mode="json")]
    assert pull_result.model_dump(mode="json")["adopted"] == [row.model_dump(mode="json")]
