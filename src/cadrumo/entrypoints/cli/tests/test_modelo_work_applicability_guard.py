"""End-to-end CLI verification for the ``work create`` applicability guard.

Previously ``modelo work create --modelo 202`` succeeded for a
natural person with no guard — the operator could provision a work unit
for a modelo their taxpayer model positively excludes, and the engine
would then be asked to run an Impuesto sobre Sociedades cuota for a
natural person.

These tests drive the real ``cadrumo`` CLI against an isolated encrypted
backend and pin the guard behaviour:

* a natural-person profile is refused a ``work create --modelo 202``
  (an Impuesto sobre Sociedades pago fraccionado);
* a legal-entity profile is refused a ``work create --modelo 100``
  (the IRPF Renta);
* the ``--allow-not-applicable`` escape hatch lets the refusal be
  bypassed deliberately, and the bypass is recorded in the payload;
* a modelo that does apply to the profile is still created normally —
  the guard does not over-block.

No mocks: the guard runs the real :func:`derive_modelo_applicability`
against the real persisted profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.resources import resources
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _m100_revision_id(*, filing_year: int, period: str) -> str:
    return str(resources().modelos.authority.snapshot("100", filing_year=filing_year, period=period).revision.id)


def _create_natural_person() -> None:
    """Create a declared natural-person profile (autónomo)."""

    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Guard",
            "activities.description": "design",
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
        },
    )


def _create_legal_entity() -> None:
    """Create a declared legal-entity profile (sociedad limitada)."""

    register_cli_profile(
        label="company",
        facts={
            "identity.tax_id": "B12345674",
            "identity.name": "Company",
            "identity.legal_name": "Company SL",
            "activities.description": "consulting",
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
        },
    )


def _create_non_resident_irnr_natural_person() -> None:
    """Create a declared NON_RESIDENT_IRNR natural-person profile."""

    register_cli_profile(
        label="nonresident",
        facts={
            "identity.tax_id": "X1234567L",
            "identity.name": "Non Resident",
            "identity.surnames": "Guard",
            "activities.description": "design",
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "FR",
        },
    )


def test_work_create_refuses_modelo_202_for_a_natural_person(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """M4: a natural person is refused a Modelo 202 work unit.

    Modelo 202 is the Impuesto sobre Sociedades pago fraccionado — a
    natural person never files it. The guard consults the derived
    applicability and refuses the create cleanly rather than
    provisioning a work unit the engine could never calculate correctly.
    """

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2025", "--period", "1P",
            "--revision", "2025-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # The refusal names the modelo and points at the escape hatch.
    assert "202" in result.output
    assert "--allow-not-applicable" in result.output


def test_work_create_refuses_modelo_100_for_a_legal_entity(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """M4: a sociedad limitada is refused a Modelo 100 work unit.

    Modelo 100 is the IRPF Renta — a legal entity is an Impuesto sobre
    Sociedades contribuyente and never files it. The guard refuses the
    create."""

    _create_legal_entity()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "100", "--year", "2025", "--period", "0A",
            "--revision", _m100_revision_id(filing_year=2025, period="0A"),
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "100" in result.output


def test_work_create_refuses_modelo_130_for_non_resident_irnr(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """A declared IRNR non-resident is refused the resident-IRPF M130 work unit."""

    _create_non_resident_irnr_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "130" in result.output
    assert "NON_RESIDENT_IRNR" in result.output
    assert "--allow-not-applicable" in result.output


def test_work_create_refuses_modelo_100_for_non_resident_irnr(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """A declared IRNR non-resident is refused the resident-IRPF M100 work unit."""

    _create_non_resident_irnr_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "100", "--year", "2025", "--period", "0A",
            "--revision", _m100_revision_id(filing_year=2025, period="0A"),
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "100" in result.output
    assert "NON_RESIDENT_IRNR" in result.output
    assert "--allow-not-applicable" in result.output


def test_work_create_allow_not_applicable_bypasses_the_guard(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """The ``--allow-not-applicable`` escape hatch lets an operator with
    a genuine reason override the refusal; the bypass is recorded in the
    create payload so the audit trail shows it was deliberate."""

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2025", "--period", "1P",
            "--revision", "2025-y-siguientes",
            "--allow-not-applicable",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    # The work unit was provisioned, and the bypass is auditable.
    assert payload["status"] == "created"
    assert payload["applicability_guard_bypassed"] is True


def test_work_create_allows_an_applicable_modelo(
    _isolated_cli_backend: Path,  # noqa: F811
) -> None:
    """The guard does not over-block: a modelo that applies to the
    profile is created normally. An autónomo en estimación directa owes
    Modelo 130, so its work unit is provisioned without a refusal."""

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["status"] == "created"
    # The guard was not bypassed — the modelo genuinely applies.
    assert payload["applicability_guard_bypassed"] is False
