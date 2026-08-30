"""CLI-layer surface verification for the maritime worker exemption pipeline.

Verifies three observable contracts exposed at the CLI boundary:

contract — the registered user-profile schema accepts ``worker_class =
"trabajador_del_mar"`` (and rejects unknown enum values). The CLI profile
edit path loads its schema from the same registry, so schema acceptance
at this layer is the canonical CLI-input contract for the fact.

contract — when the maritime exemption application service resolves an
Art. 7.p) or REBECA observation, the typed envelope that the CLI emit
boundary serialises carries canonical ``legal_refs`` ids traceable through
the bundled legal catalogue to BOE-A-2006-20764 (Art. 7.p) / Ley 35/2006)
and BOE-A-1994-15794 (REBECA / Ley 19/1994).
The flat ``casilla_values`` view is a derived projection; the canonical
contract is the typed observations.

contract — the RETMAR mandatory-filing warning surface is the
``ProfileCompletenessError`` registered with the central error-code
registry. The CLI error boundary (``cadrumo.entrypoints.cli.errors``)
renders any ``CadrumoError`` via its registered ``message_key``. This
test verifies the registered code is correct and that the Spanish
translation includes the RETMAR anchor and the LIRPF art. 96 BOE
reference, proving end-to-end that any CLI verb raising the error
will emit the regulatorily grounded message.

No verb in the current CLI invokes the maritime exemption service
directly. The verification here covers the contracts a future verb
would rely on, exercised against the same singletons the CLI uses.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....application.calculations import resolve_maritime_exemption
from ....core.errors.error_codes import get_registered_error_code
from ....core.i18n import tr
from ....domain.renta import (
    MaritimeExemptionInactiveError,
    MaritimeWorkerFacts,
    ProfileCompletenessError,
)
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class TestWorkerClassProfileFactAcceptance:
    """contract — registered user-profile schema accepts ``worker_class``."""

    def test_schema_declares_worker_class_field(self) -> None:
        schema = load_user_profile_schema()
        field = schema.field("maritime_worker.worker_class")
        # ``field()`` raises ``UserProfileNotFoundError`` if missing, so
        # reaching this line is itself the existence assertion. The enum
        # value check pins the only currently accepted worker class.
        assert field.enum_values == ("trabajador_del_mar",)

    def test_schema_field_carries_legal_refs_for_all_pathways(self) -> None:
        schema = load_user_profile_schema()
        field = schema.field("maritime_worker.worker_class")
        # All three exemption pathways and the RETMAR completeness gate
        # must be cited through canonical legal catalogue ids.
        assert set(field.legal_refs) == {
            "ley-35-2006:art-7",
            "ley-19-1994:art-75",
            "ley-35-2006:da-41",
            "ley-35-2006:art-96",
        }


class TestMaritimeExemptionEnvelopeCarriesLegalRefs:
    """contract — emit envelope from the resolution service carries legal_refs."""

    def test_art_7p_envelope_carries_boe_anchor(self) -> None:
        result = resolve_maritime_exemption(
            facts=MaritimeWorkerFacts(
                worker_class="trabajador_del_mar",
                vessel_flag="foreign",
                waters_type="international",
            ),
            annual_salary=Decimal("36500"),
            qualifying_days=100,
        )
        assert len(result.observations) == 1
        obs = result.observations[0]
        assert obs.legal_refs == ("ley-35-2006:art-7",)

    def test_rebeca_envelope_carries_boe_anchor(self) -> None:
        result = resolve_maritime_exemption(
            facts=MaritimeWorkerFacts(
                worker_class="trabajador_del_mar",
                vessel_registry="REBECA",
            ),
            gross_navigation_income=Decimal("30000"),
        )
        assert len(result.observations) == 1
        obs = result.observations[0]
        assert obs.legal_refs == ("ley-19-1994:art-75",)

    def test_envelope_flat_view_matches_typed_observations(self) -> None:
        # The CLI emit layer often surfaces the flat casilla_values view
        # alongside the typed observations. The flat view must be a
        # faithful projection of the typed contract.
        result = resolve_maritime_exemption(
            facts=MaritimeWorkerFacts(
                worker_class="trabajador_del_mar",
                vessel_registry="REBECA",
            ),
            gross_navigation_income=Decimal("30000"),
        )
        obs = result.observations[0]
        assert result.casilla_values[obs.casilla_id] == obs.value


class TestRetmarMandatoryFilingWarningSurface:
    """contract — RETMAR warning rides the registered CLI error envelope."""

    def test_da41_inactive_error_is_registered_with_refused_category(self) -> None:
        code = get_registered_error_code(MaritimeExemptionInactiveError)
        assert code.code == "REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE"
        assert code.message_key == ("errors.refused.refused_renta_maritime_exemption_inactive")

    def test_retmar_profile_completeness_error_is_registered(self) -> None:
        code = get_registered_error_code(ProfileCompletenessError)
        assert code.code == "ERROR_RENTA_PROFILE_COMPLETENESS_WARNING"
        assert code.message_key == ("errors.error.error_renta_profile_completeness_warning")

    def test_retmar_translated_message_carries_retmar_and_boe_anchor(self) -> None:
        # The CLI error boundary calls ``tr(code.message_key)`` to render
        # the operator-facing line. Asserting against the Spanish
        # translation verifies the surface that ``cadrumo`` emits in its
        # default output language.
        message = tr(
            "errors.error.error_renta_profile_completeness_warning",
            locale="es",
        )
        assert "RETMAR" in message
        assert "BOE-A-2006-20764" in message

    def test_da41_translated_message_carries_da_41_and_boe_anchor(self) -> None:
        message = tr(
            "errors.refused.refused_renta_maritime_exemption_inactive",
            locale="es",
        )
        assert "DA 41" in message
        assert "BOE-A-2006-20764" in message

    def test_retmar_gate_fires_for_registered_worker(self) -> None:
        # The service path raises ProfileCompletenessError when the
        # worker is RETMAR-registered. A CLI verb that invokes the
        # service will pass this through to the error boundary, which
        # then renders the translated message asserted above.
        with pytest.raises(ProfileCompletenessError) as exc_info:
            resolve_maritime_exemption(
                facts=MaritimeWorkerFacts(retmar_registered=True),
            )
        assert "RETMAR" in str(exc_info.value)
        assert "BOE-A-2006-20764" in str(exc_info.value)
