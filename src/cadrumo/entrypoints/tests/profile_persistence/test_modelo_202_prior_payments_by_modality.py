"""The earlier instalments' payments are a required input of a Modelo 202 only under art. 40.3.

The Modelo 202 instructions place "pagos fraccionados de períodos anteriores"
(clave [30]) in the art. 40.3 modality alone: clave [32] = (... ) - clave [30] -
clave [31]. Under art. 40.2 the instalment is 18 % of the base less only the
result of a declaration it complements (clave [03] = 18 % x clave [01] - clave
[02]); no earlier instalment is deducted. So a sociedad below the art. 40.3
threshold that never elected art. 40.3 calculates its December instalment
whatever its October one did, while a sociedad bound to art. 40.3 still needs
the earlier payments and is refused without them.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production work-unit door, the production calculation action and its ports,
with every year taken from the published support envelope.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.action_errors import ModeloRequiredBindingsMissingError
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_work_lifecycle_ports,
)

from ..modelo_operator_work_storage import SEEDED_AT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-000000002023"
_PERSONA = "sociedad-limitada"
_MODELO_200 = "200"
_MODELO_202 = "202"
_ANNUAL = "0A"
_DECEMBER = "3P"
_PRIOR_PAYMENTS_BINDING = "modelo-202-pagos-fraccionados-anteriores"
_CUOTA_BASE_CASILLA = validated_casilla_id("DP200014B:00599")
_INSTALMENT_CASILLA = validated_casilla_id("03")
_ART_40_3_RESULT_CASILLA = validated_casilla_id("34")
_ELECTION_PATH = "taxpayer_type.pago_fraccionado_art_40_3_elected"
_INCN_PATH = "taxpayer_type.incn_prior_12_months"
_BELOW_THRESHOLD = Decimal("28500.00")
_ABOVE_THRESHOLD = Decimal("7000000.00")


def _ejercicio() -> int:
    return filing_year_envelope().horizon - 1


def _seed_sociedad(bucket_id: str, *, incn: Decimal, elected: bool) -> None:
    create_context, _ = profile_authority_contexts()
    seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path=_INCN_PATH, value=incn),
                    UserProfileFact(path=_ELECTION_PATH, value=elected),
                    UserProfileFact(
                        path="censo.activity_start_date", value=date(filing_year_envelope().floor - 1, 1, 1)
                    ),
                ),
                persona_id=_PERSONA,
            ),
            created_at=SEEDED_AT,
            updated_at=SEEDED_AT,
        )
    )


def _save(modelo: str, filing_year: int, period: str, casilla_values: dict[CasillaId, Decimal]) -> None:
    repository = CalculationObservationRepository()
    observation = registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=ObservationSourceKind.APP_FILING,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _calculate_december_instalment(tmp_path: Path, *, incn: Decimal, elected: bool) -> dict[CasillaId, Decimal]:
    """Calculate the December instalment after a filed April one and no October filing."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        _seed_sociedad(profile.bucket_id, incn=incn, elected=elected)
        # The Modelo 200 one year back, the October and December base, with a 300.00 cuota.
        _save(_MODELO_200, _ejercicio() - 1, _ANNUAL, {_CUOTA_BASE_CASILLA: Decimal("300.00")})
        _save(
            _MODELO_202,
            _ejercicio(),
            "1P",
            {_INSTALMENT_CASILLA: Decimal("54.00"), _ART_40_3_RESULT_CASILLA: Decimal("0.00")},
        )
        period = Period.from_year_and_code(_ejercicio(), _DECEMBER)
        revision = operation.revision_for_context(_MODELO_202, filing_year=_ejercicio(), period=_DECEMBER)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=_MODELO_202,
            filing_year=_ejercicio(),
            period=period,
            revision_id=str(revision.id),
            ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
            clock=SEEDED_AT,
            operation=operation,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation),
            actor="operator-test",
            clock=SEEDED_AT,
        )
    return dict(result.revision.casilla_values)


def _assert_names_the_earlier_payments(error: ModeloRequiredBindingsMissingError) -> None:
    context = error.context
    assert context is not None
    missing = context["missing_bindings"]
    assert isinstance(missing, tuple)
    assert _PRIOR_PAYMENTS_BINDING in missing


def test_an_art_40_2_sociedad_calculates_its_december_instalment_without_the_earlier_payments(
    tmp_path: Path,
) -> None:
    values = _calculate_december_instalment(tmp_path, incn=_BELOW_THRESHOLD, elected=False)

    # 18 % of the 300.00 cuota, with nothing deducted for the instalments before it.
    assert values[_INSTALMENT_CASILLA] == Decimal("54.00")


def test_an_art_40_3_sociedad_still_needs_the_earlier_payments(tmp_path: Path) -> None:
    with pytest.raises(ModeloRequiredBindingsMissingError) as refused:
        _calculate_december_instalment(tmp_path, incn=_ABOVE_THRESHOLD, elected=False)

    _assert_names_the_earlier_payments(refused.value)


def test_an_elected_art_40_3_sociedad_still_needs_the_earlier_payments(tmp_path: Path) -> None:
    with pytest.raises(ModeloRequiredBindingsMissingError) as refused:
        _calculate_december_instalment(tmp_path, incn=_BELOW_THRESHOLD, elected=True)

    _assert_names_the_earlier_payments(refused.value)
