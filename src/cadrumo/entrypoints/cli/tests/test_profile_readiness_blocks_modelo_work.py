"""CLI coverage for profile-readiness blocking ahead of modelo work."""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.application.user_profile.language_resolver import mirror_profile_output_language_hint

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....core.config import load_settings
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ..config.tests.isolated_storage_fixture import native_profile_view_server
from ._profile_cli_support import invoke_protected_profile
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_profile_cli(profile_name: str, args: Sequence[str]) -> Result:
    """Supply the real password channel for each independently admitted command."""
    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return invoke_cached_cli(
        ["--language", "en", "--profile", profile_name, "--profile-secrets-stdin", *args],
        input=json.dumps({"profile_passphrase": secret}),
    )


def _create_defaulted_natural_person_profile(profile_name: str) -> None:
    """Register a profile that genuinely lacks the baseline these tests block on.

    The shared CLI door fills every schema-required field -- including the
    conditional ones an economic-activity profile acquires -- so registering
    through it alone yields a COMPLETE profile and the readiness block these
    tests assert can never occur. An empty value is how a caller declines one
    of those fills: the door drops falsy facts before registering, so the field
    is absent rather than blank.
    """
    profile_id = register_cli_profile(
        label=profile_name,
        facts={
            "preferences.output_language": "en",
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "12345678Z",
            "identity.name": "Lucia",
            "identity.surnames": "Navarro",
            "activities.description": "",
        },
        log_in=False,
    )
    # Direct fixture registration bypasses the profile-edit service that mirrors
    # this non-secret hint. The worker reads it before it has private custody.
    mirror_profile_output_language_hint(profile_id, OutputLanguage.EN)


@pytest.mark.parametrize(
    ("profile_name", "modelo", "filing_year", "period"),
    (
        ("lucia_defaults_broken", "303", "2024", "1T"),
        ("ana_defaults_broken", "100", "2025", "0A"),
    ),
    ids=("m303-defaulted-profile", "m100-defaulted-profile"),
)
def test_defaulted_profile_readiness_surfaces_block_before_modelo_work(
    profile_name: str,
    modelo: str,
    filing_year: str,
    period: str,
) -> None:
    _create_defaulted_natural_person_profile(profile_name)
    revision_id = str(
        published_snapshot(
            modelo,
            filing_year=int(filing_year),
            period=period,
        ).revision.id,
    )

    with native_profile_view_server(load_settings().cadrumo_local_storage_root):
        validate = invoke_protected_profile(profile_name, "validate", profile_name)
        assert validate.exit_code == 2, validate.output
        assert "readiness\tblocked" in validate.output
        assert "modelo_work_profile_baseline_missing\tactivities.description" in validate.output
        assert "readiness\tready" not in validate.output

        readiness = _invoke_profile_cli(
            profile_name,
            [
                "app", "modelo", "readiness",
                "--modelo", modelo,
                "--revision-id", revision_id,
                "--year", filing_year,
                "--period", period,
            ],
        )  # fmt: skip
        assert readiness.exit_code == 2, readiness.output
        assert "ready\tFalse" in readiness.output, readiness.output
        assert "profile_ready\tFalse" in readiness.output, readiness.output
        assert "activities.description\tactivities.description" in readiness.output, readiness.output

        work_create = _invoke_profile_cli(
            profile_name,
            [
                "app", "modelo", "work", "create",
                "--modelo", modelo,
                "--year", filing_year,
                "--period", period,
            ],
        )  # fmt: skip
        assert work_create.exit_code == 2, work_create.output
        assert "Activity description" in work_create.output, work_create.output
        assert "work_unit_id" not in work_create.output, work_create.output

        readiness_json = _invoke_profile_cli(
            profile_name,
            [
                "--format", "json",
                "app", "modelo", "readiness",
                "--modelo", modelo,
                "--revision-id", revision_id,
                "--year", filing_year,
                "--period", period,
            ],
        )  # fmt: skip
        assert readiness_json.exit_code == 2, readiness_json.output
        readiness_payload = _payload(readiness_json.output)
        (readiness_missing_row,) = readiness_payload["missing"]
        assert readiness_missing_row["selector"] and readiness_missing_row["label"]
        assert readiness_missing_row["label"] != readiness_missing_row["selector"]
        assert isinstance(readiness_missing_row["legal_refs"], list)
        assert isinstance(readiness_missing_row["modelos"], list)


def test_no_business_landlord_can_create_m100_while_quarterly_activity_modelos_refuse() -> None:
    """A real no-business persona can open its applicable Renta work only."""
    profile_id = register_cli_profile(
        label="pere-landlord",
        facts={
            "preferences.output_language": "en",
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Pere",
            "identity.surnames": "Rosello Rerun",
            "taxpayer_type.irpf_income_categories": "capital_inmobiliario,pension",
            # Declined explicitly: the shared door seeds an activity
            # description for every profile, which is the one fact this
            # persona must not have. A falsy value is dropped before
            # registration, so the field is absent rather than blank.
            "activities.description": "",
            "tax_residence.ccaa": "cataluna",
            "contact.postcode": "08001",
            "renta_filing.declaration_type": "1",
            "renta_taxpayer.sex": "H",
            "renta_taxpayer.birth_date": "1952-02-12",
            "renta_taxpayer.marital_status": "3",
            "renta_family.situacion_familiar": "soltero",
        },
        log_in=False,
    )
    mirror_profile_output_language_hint(profile_id, OutputLanguage.EN)

    with native_profile_view_server(load_settings().cadrumo_local_storage_root):
        validate = invoke_protected_profile("pere-landlord", "validate", "pere-landlord")
        assert validate.exit_code == 0, validate.output
        assert "readiness\tready" in validate.output

        status = invoke_protected_profile("pere-landlord", "status", json_output=True)
        assert status.exit_code == 0, status.output
        status_payload = _payload(status.output)
        assert status_payload["configured"] is True
        assert status_payload["activity_present"] is False

        shown = invoke_protected_profile("pere-landlord", "view")
        assert shown.exit_code == 0, shown.output
        assert "capital_inmobiliario,pension" in shown.output
        assert "activities.description" not in shown.output

        calendar = _invoke_profile_cli(
            "pere-landlord",
            [
                "app", "overview", "calendar",
                "--from", "2026-01-01",
                "--to", "2026-12-31",
                "--show-suppressed", "--allow-incomplete",
            ],
        )  # fmt: skip
        assert calendar.exit_code == 0, calendar.output
        assert "100\t2025 0A" in calendar.output
        assert "130" in calendar.output
        assert "303" in calendar.output

        readiness = _invoke_profile_cli(
            "pere-landlord",
            [
                "app", "modelo", "readiness",
                "--modelo", "100", "--revision-id", "2025", "--year", "2025", "--period", "0A",
            ],
        )  # fmt: skip
        assert readiness.exit_code == 2, readiness.output
        assert "profile_ready\tTrue" in readiness.output, readiness.output

        renta = _invoke_profile_cli(
            "pere-landlord",
            [
                "app", "modelo", "work", "create",
                "--modelo", "100", "--year", "2025", "--period", "0A",
                "--name", "Pere renta 2025", "--by", "continuity-test",
            ],
        )  # fmt: skip
        assert renta.exit_code == 0, renta.output
        assert "work_unit_id" in renta.output

        calculated = _invoke_profile_cli(
            "pere-landlord",
            [
                "--format", "json", "app", "modelo", "work", "calculate",
                "--modelo", "100", "--year", "2025", "--period", "0A",
                "--casilla", "0003=27000", "--casilla", "0102=8400",
                "--binding", "renta-base-liquidable-negativa-general-anterior=0",
            ],
        )  # fmt: skip
        assert calculated.exit_code == 0, calculated.output
        calculation_payload = _payload(calculated.output)
        assert calculation_payload["calculation_revision_id"]
        assert Decimal(str(calculation_payload["casilla_values"]["0545"])) > Decimal("0")
        assert Decimal(str(calculation_payload["casilla_values"]["0546"])) > Decimal("0")

        for modelo, period in (("130", "1T"), ("303", "1T")):
            refused = _invoke_profile_cli(
                "pere-landlord",
                [
                    "app", "modelo", "work", "create",
                    "--modelo", modelo, "--year", "2026", "--period", period,
                ],
            )  # fmt: skip
            assert refused.exit_code == 2, refused.output
            assert "does not apply" in refused.output, refused.output
            assert "work_unit_id" not in refused.output, refused.output


def test_attribution_entity_without_activity_remains_status_blocked() -> None:
    """The no-business natural-person exception does not leak to entities."""
    profile_id = register_cli_profile(
        label="comunidad-sin-actividad",
        facts={
            "preferences.output_language": "en",
            "taxpayer_type.entity_type": "attribution_entity",
            "identity.tax_id": "E12345674",
            "identity.name": "Comunidad sin actividad",
            "activities.description": "",
        },
        # The subject is an entity that is NOT configured, and the door
        # marks setup complete unless told otherwise.
        complete=False,
        log_in=False,
    )
    mirror_profile_output_language_hint(profile_id, OutputLanguage.EN)

    with native_profile_view_server(load_settings().cadrumo_local_storage_root):
        status = invoke_protected_profile("comunidad-sin-actividad", "status", json_output=True)
        assert status.exit_code == 0, status.output
        status_payload = _payload(status.output)
        assert status_payload["configured"] is False
        assert status_payload["activity_present"] is False

        work_create = _invoke_profile_cli(
            "comunidad-sin-actividad",
            ["app", "modelo", "work", "create", "--modelo", "184", "--year", "2025", "--period", "0A"],
        )  # fmt: skip
        assert work_create.exit_code == 2, work_create.output
        assert "Activity description" in work_create.output, work_create.output
        assert "work_unit_id" not in work_create.output, work_create.output


def test_economic_activity_m100_still_requires_the_direct_estimation_modality() -> None:
    """The non-business formula guard must not default a real activity's modality."""
    profile_id = register_cli_profile(
        label="autonomo-renta",
        facts={
            "preferences.output_language": "en",
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Ana",
            "identity.surnames": "Autonoma",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "activities.description": "consultoria",
            "irpf.estimation_regime": "directa_normal",
            "tax_residence.ccaa": "madrid",
            "renta_filing.declaration_type": "1",
            "renta_taxpayer.sex": "M",
            "renta_taxpayer.birth_date": "1980-01-01",
            "renta_taxpayer.marital_status": "1",
            "renta_family.situacion_familiar": "soltero",
        },
        log_in=False,
    )
    mirror_profile_output_language_hint(profile_id, OutputLanguage.EN)

    with native_profile_view_server(load_settings().cadrumo_local_storage_root):
        work_create = _invoke_profile_cli(
            "autonomo-renta",
            ["app", "modelo", "work", "create", "--modelo", "100", "--year", "2025", "--period", "0A"],
        )  # fmt: skip
        assert work_create.exit_code == 0, work_create.output

        calculated = _invoke_profile_cli(
            "autonomo-renta",
            [
                "app", "modelo", "work", "calculate",
                "--modelo", "100", "--year", "2025", "--period", "0A",
                "--casilla", "0003=27000",
                "--binding", "renta-base-liquidable-negativa-general-anterior=0",
            ],
        )  # fmt: skip
        # The registered missing-input calculation error is ERROR (exit 1).
        assert calculated.exit_code == 1, calculated.output
        assert "renta-modelo-100-estimacion-directa-es-normal" in calculated.output, calculated.output
