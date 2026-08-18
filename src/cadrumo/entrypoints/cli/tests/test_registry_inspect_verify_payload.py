"""Strict JSON payload checks for ``aeat app registry inspect`` / ``verify``.

``RegistryInspectResult`` and ``RegistryVerifyResult`` used to be
``extra="allow"`` shells declaring only a subset of
``RegistryTreeReport``'s fields, so a negative count, a malformed nested
detail row, or an unrecognised top-level key crossed the envelope. They now
project the canonical report in full through typed rows, and -- since the
two commands' schemas are field-identical -- through the single
``RegistryInspectResult`` class, registered under both ``registry.inspect``
and ``registry.verify``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._registry_payloads import RegistryInspectResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _report_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "registry_root": "registry",
        "source_root": None,
        "modelo_count": 1,
        "revision_count": 1,
        "legal_reference_count": 0,
        "source_reference_count": 0,
        "casilla_count": 2,
        "formula_count": 2,
        "extraction_profile_count": 0,
        "cross_reference_count": 0,
        "workbook_parity_ref_count": 0,
        "verification_expectation_count": 0,
        "application_link_count": 0,
        "application_link_surfaces": [],
        "relation_count": 0,
        "relation_dependency_roles": [],
        "filing_schedule_count": 0,
        "modelos": ["303"],
        "revision_details": [],
        "verified": True,
    }
    base.update(overrides)
    return base


def test_registry_tree_result_round_trips_valid_report() -> None:
    result = RegistryInspectResult.model_validate(_report_kwargs())

    assert result.registry_root == "registry"
    assert result.modelos == ["303"]


@pytest.mark.parametrize(
    "mutation",
    (
        {"revision_count": -1},
        {"relation_count": -1},
        {"casilla_count": -1},
        {"revision_details": [{}]},
        {"unknown_extra_key": "x"},
    ),
)
def test_registry_tree_result_refuses_malformed_report(mutation: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RegistryInspectResult.model_validate({**_report_kwargs(), **mutation})


def test_registry_tree_result_refuses_a_minimal_payload_missing_roots_and_detail() -> None:
    """A payload carrying only a stray count, missing the canonical roots/detail contract, is refused."""
    with pytest.raises(ValidationError):
        RegistryInspectResult.model_validate({"modelo_count": 1})


def test_registry_tree_result_round_trips_a_populated_revision_detail_row() -> None:
    """A well-formed nested revision-detail row -- including workbook parity -- round-trips."""
    result = RegistryInspectResult.model_validate(
        _report_kwargs(
            revision_details=[
                {
                    "modelo": "303",
                    "revision": "2022",
                    "legal_refs": ["ley-37-1992:art-78"],
                    "source_refs": ["aeat-modelo-303-instrucciones-2026"],
                    "export_layout_ids": [],
                    "export_layout_count": 0,
                    "export_record_count": 0,
                    "export_field_count": 0,
                    "deadline_window_count": 1,
                    "deadline_periods": ["1T"],
                    "relation_ids": [],
                    "relation_count": 0,
                    "relation_dependency_roles": [],
                    "filing_schedule_ids": [],
                    "filing_schedule_count": 1,
                    "portal_guard_policy_ids": [],
                    "workbook_parity": [
                        {
                            "id": "wpref-1",
                            "workbook_source": "aeat-modelo-303-workbook",
                            "formula_coverage": "full",
                            "runner_required": True,
                            "output_cell_count": 12,
                        },
                    ],
                },
            ],
        ),
    )

    (detail,) = result.revision_details
    assert detail.modelo == "303"
    (parity,) = detail.workbook_parity
    assert parity.output_cell_count == 12
