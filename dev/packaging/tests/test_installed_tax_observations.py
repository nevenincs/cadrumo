"""The installed oracle refuses ambiguous or ungrounded persisted evidence."""

from __future__ import annotations

from typing import Any

import pytest

from ..installed_tax_oracle import InstalledTaxOracleError, assert_grounded_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _persisted_observations() -> dict[str, Any]:
    return {
        "calculation_revision_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "observations": [
            {
                "casilla_id": "DP200014:00562",
                "value": "23000.00",
                "formula_id": "modelo-200-cuota-integra",
                "legal_refs": ["ley-27-2014:art-29"],
                "source_refs": ["aeat-modelo-200-manual-2024"],
            }
        ],
    }


def _assert_observations(document: dict[str, Any]) -> dict[str, Any]:
    return assert_grounded_observations(
        document,
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
    )


def test_grounded_persisted_target_is_accepted() -> None:
    document = _persisted_observations()
    assert _assert_observations(document) == document["observations"][0]


@pytest.mark.parametrize("identity", ["calculation_revision_id", "work_unit_id"])
def test_evidence_from_another_revision_or_work_unit_is_refused(identity: str) -> None:
    document = _persisted_observations()
    document[identity] = "c" * 64
    with pytest.raises(InstalledTaxOracleError, match="different"):
        _assert_observations(document)


@pytest.mark.parametrize("grounding", ["legal_refs", "source_refs"])
def test_every_observation_requires_grounding(grounding: str) -> None:
    document = _persisted_observations()
    other: dict[str, Any] = dict(document["observations"][0], casilla_id="DP200012:00501")
    other[grounding] = []
    document["observations"].append(other)
    with pytest.raises(InstalledTaxOracleError, match="lack legal or source grounding"):
        _assert_observations(document)


def test_duplicate_target_observations_are_refused() -> None:
    document = _persisted_observations()
    document["observations"].append(dict(document["observations"][0]))
    with pytest.raises(InstalledTaxOracleError, match="expected one"):
        _assert_observations(document)


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("value", "23000.01"),
        ("formula_id", "another-formula"),
        ("legal_refs", ["another-article"]),
        ("source_refs", ["another-manual"]),
    ],
)
def test_a_grounded_target_must_match_the_oracle(field: str, wrong_value: object) -> None:
    document = _persisted_observations()
    document["observations"][0][field] = wrong_value
    with pytest.raises(InstalledTaxOracleError):
        _assert_observations(document)
