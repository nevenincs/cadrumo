"""CLI reproduction: ``modelo work calculate`` names the bindings and boxes it left without a value."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from cadrumo.application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .native_api_cli_support import native_api_cli_session, operation_lifecycle_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# The newest Modelo 100 edition the registry authors; its prior-year carry reads the
# edition before it.
_REVIEWED_EDITION = newest_authored_edition("100")

_CAPTURED_AT = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)

#: The withholding the synthetic payer's certificate states.
_CERTIFIED_RETENCION = Decimal("4200")

#: The credit operand of box 0598, which only a decided rental-activity applicability can settle.
_RENTAL_ACTIVITY_CREDIT_BINDING = "renta-retencion-soportada-arrendamiento-actividad"

_IDENTITY_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ana"),
    UserProfileFact(path="identity.surnames", value="Retenciones"),
    UserProfileFact(path="activities.description", value="economic activity"),
)

_TAXPAYER_FACTS = (
    UserProfileFact(path="censo.activity_start_date", value=date(_REVIEWED_EDITION - 5, 1, 1)),
    UserProfileFact(path="renta_taxpayer.birth_date", value=date(_REVIEWED_EDITION - 45, 3, 15)),
    UserProfileFact(path="renta_taxpayer.sex", value="H"),
    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
    UserProfileFact(path="renta_filing.declaration_type", value="1"),
    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
    UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
)

_CATEGORIES_FACT = UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica,trabajo")

#: The categories fact follows the general-regime defaults, and the activity's IAE epigraph is not an
#: urban-rental group, so the rental-activity credit in 0598 is a proven zero.
_RESOLVED_PROFILE_FACTS = persona_facts_beneath(
    (
        *_IDENTITY_FACTS,
        _CATEGORIES_FACT,
        UserProfileFact(path="activities.iae_epigraph", value="844"),
        *_TAXPAYER_FACTS,
    )
)

#: The categories fact precedes the general-regime defaults, which replace it with an activity that has
#: no IAE epigraph, so whether the activity is an urban rental is unknown.
_UNKNOWN_RENTAL_PROFILE_FACTS = persona_facts_beneath(
    (
        *_IDENTITY_FACTS,
        _CATEGORIES_FACT,
        *_TAXPAYER_FACTS,
    )
)

_OPERATIONS = frozenset(
    {
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    }
)


def _prepare_m100_profile(
    profile_id: UUID,
    root: Path,
    authority_operation: PinnedAuthorityOperation,
    profile_facts: tuple[UserProfileFact, ...],
) -> None:
    """Complete the enrolled taxpayer and persist canonical prior-year carry evidence."""
    facts = complete_profile_facts(authority_operation.profile_schema(), profile_facts)
    populated = upsert_test_profile_facts(profile_id, facts, root=root)
    with bound_test_profile_record(profile_id, root=root) as repository:
        ready = repository.complete_setup(
            profile_id,
            expected_revision=populated.record_revision,
            expected_content_digest=populated.content_digest,
        )
    assert ready.setup_state is ProfileSetupState.COMPLETE
    _seed_prior_year_zero_carry(profile_id)
    seed_payer_certificate(
        operation=authority_operation,
        taxpayer_tax_id="12345678Z",
        ejercicio=_REVIEWED_EDITION,
        payer_tax_id="B00010082",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=_CERTIFIED_RETENCION,
        importe_integro_dinerario=Decimal("32000"),
    )


def _seed_prior_year_zero_carry(profile_id: UUID) -> None:
    repository = CalculationObservationRepository(bucket_id=str(profile_id))
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_REVIEWED_EDITION - 1,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_REVIEWED_EDITION - 1,
                    period="0A",
                    casilla_values=dict.fromkeys(("1384", "1387", "1390", "1391"), Decimal("0")),
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
            stamped_revision_id=str(
                published_snapshot("100", filing_year=_REVIEWED_EDITION - 1, period="0A").revision.id
            ),
        )
    )


def _calculate_through_cli(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli,
    profile_facts: tuple[UserProfileFact, ...],
) -> dict[str, Any]:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=operation_lifecycle_scope(_OPERATIONS),
        prepare_profile=lambda profile_id, root: _prepare_m100_profile(
            profile_id, root, authority_operation, profile_facts
        ),
        invoke_cli=run_cadrumo_cli,
    ) as session:
        created = session.invoke_password(
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            str(_REVIEWED_EDITION),
            "--period",
            "0A",
            "--revision",
            str(_REVIEWED_EDITION),
        )
        assert created.exit_code == 0, f"{created.output}\n{session.runtime_failure_observations!r}"
        work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
        assert isinstance(work_unit_id, str) and work_unit_id, created.output
        result = session.invoke_password(
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "0003=32000",
            "--casilla",
            "0102=9600",
            "--relation",
            "renta-modelo-130-pagos-fraccionados=0",
            "--relation",
            "renta-modelo-131-pagos-fraccionados=0",
        )
    assert result.exit_code == 0, result.output
    return unwrap_schema_envelope(result.output)


def test_m100_cli_calculate_names_the_unresolved_rental_activity_credit(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli,
) -> None:
    """An unknown rental-activity applicability reaches the calculate JSON as findings, not as zeros."""
    payload = _calculate_through_cli(tmp_path, authority_operation, run_cadrumo_cli, _UNKNOWN_RENTAL_PROFILE_FACTS)

    bindings = {row["binding_id"]: row for row in payload["unresolved_bindings"]}
    assert _RENTAL_ACTIVITY_CREDIT_BINDING in bindings, payload["unresolved_bindings"]
    credit = bindings[_RENTAL_ACTIVITY_CREDIT_BINDING]
    assert credit["casilla_id"] == "0598"
    assert credit["reason"] == "unresolved_binding"
    assert credit["note"], credit
    assert credit["words"], credit
    unresolved_casillas = {row["casilla_id"] for row in payload["unresolved_casillas"]}
    assert {"0609", "0610"} <= unresolved_casillas
    # A box with no value is absent from the result, never zero.
    assert not ({"0598", "0609", "0610"} & set(payload["casilla_values"]))
    assert not (unresolved_casillas & set(payload["casilla_values"]))
    assert payload["words_language"]


def test_m100_cli_calculate_names_no_credit_the_profile_decides(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli,
) -> None:
    """The profile that decides every credit values the credit boxes and names none of them.

    The profile records no inventory decision, so the inventory-sourced boxes stay unresolved and are
    named; the credit family is not among them.
    """
    payload = _calculate_through_cli(tmp_path, authority_operation, run_cadrumo_cli, _RESOLVED_PROFILE_FACTS)

    credit_boxes = {"0596", "0597", "0598", "0603", "0609"}
    named_bindings = {row["binding_id"] for row in payload["unresolved_bindings"]}
    named_boxes = {row["casilla_id"] for row in payload["unresolved_casillas"]} | {
        row["casilla_id"] for row in payload["unresolved_bindings"]
    }
    assert not any(binding.startswith("renta-retencion-soportada") for binding in named_bindings), named_bindings
    assert not (credit_boxes & named_boxes), named_boxes
    assert credit_boxes <= set(payload["casilla_values"])
    assert Decimal(payload["casilla_values"]["0596"]) == _CERTIFIED_RETENCION
    assert Decimal(payload["casilla_values"]["0609"]) == _CERTIFIED_RETENCION
    # Whatever is named has no value in the result.
    assert not (named_boxes & set(payload["casilla_values"]))
