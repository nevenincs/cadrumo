"""Strict payload checks for ``CensoFileFactPayload``.

``CensoFileFactPayload`` used to be an unconstrained path/value/source row,
unlike the sibling ``CensoPullFactPayload`` which already re-validates
against the canonical :class:`~cadrumo.domain.user_profile.UserProfileFact`
contract. It now applies the same re-validation while retaining the
non-official artefact source policy (the source token is still a declared
provenance, just never the AEAT-verified censal-read one).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..._config_payloads import CensoFileFactPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_censo_file_fact_payload_round_trips_a_valid_row() -> None:
    row = CensoFileFactPayload(path="contact.postcode", value="28001", source="censo_artefact_g313")

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
def test_censo_file_fact_payload_refuses_malformed_row(kwargs: dict[str, str]) -> None:
    """A malformed path, a blank/oversized source, or an undeclared source is refused."""
    with pytest.raises(ValidationError):
        CensoFileFactPayload(**kwargs)
