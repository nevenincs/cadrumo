"""The first-year flag resolves in a process that never imports the wizard.

The engine's first-year derivation (``_first_year_modalidad_cuota_no_m202`` /
``activity_start_date_for_bucket``) reads the wizard-free profile projection
(``record_to_path_values``). A non-CLI calculation entrypoint therefore resolves
the first-year relaxation without any setup surface.

A self-contained child process builds a real profile record against the real
registry authority, resolves the derivation off its projection, then asserts
that ``cadrumo.application.wizard`` was never imported (the discriminating
condition). In that process the first-year flag resolves True and the
activity-start date resolves. No mocks, no monkeypatch: the no-wizard condition
comes from process isolation. The composed full calculation that consumes this
flag is asserted by its composition owner.
"""

from __future__ import annotations

import sys

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Child process: resolves the first-year derivation off a real profile record
# WITHOUT ever importing cadrumo.application.wizard.
_CHILD_SCRIPT = r"""
import sys
from datetime import UTC, datetime
from decimal import Decimal

from cadrumo.application.calculations.relation_prefill import (
    activity_start_date_for_bucket,
    _first_year_modalidad_cuota_no_m202,
)
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

_PROFILE_ID = "20020020-0200-4200-8200-200200200200"
_BUCKET = _PROFILE_ID
_T0 = datetime(2026, 1, 12, 10, 0, tzinfo=UTC)

with bundled_indexed_authority().operation() as operation:
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="No Wizard SL"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value="false"),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value="false"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
        ),
        created_at=_T0,
        updated_at=_T0,
    )

    class _ProfilePathValuesReader:
        def __init__(self, values):
            self._values = values

        def load_path_values(self, *, bucket_id):
            del bucket_id
            return self._values

    profile_path_values_reader = _ProfilePathValuesReader(record_to_path_values(record))

    # The decoupled helpers must resolve off the projection with NO wizard.
    print(
        "FIRST_YEAR:"
        + str(
            _first_year_modalidad_cuota_no_m202(
                _BUCKET,
                filing_year=2025,
                profile_path_values_reader=profile_path_values_reader,
            )
        )
    )
    print(
        "ACTIVITY_START:"
        + str(
            activity_start_date_for_bucket(
                _BUCKET,
                profile_path_values_reader=profile_path_values_reader,
            )
        )
    )
print("WIZARD:" + ("IMPORTED" if "cadrumo.application.wizard" in sys.modules else "NOT_IMPORTED"))
"""


def test_first_year_modalidad_cuota_resolves_without_wizard_catalogue() -> None:
    """In a process that never imports the wizard, the first-year flag still resolves."""
    child = ensure_text_completed_process(
        run_audited_process(
            [sys.executable, "-c", _CHILD_SCRIPT],
            capture_output=True,
            text=True,
            timeout=None,
            check=False,
        )
    )
    out = child.stdout
    detail = f"\n--- stdout ---\n{out}\n--- stderr ---\n{child.stderr}"

    assert child.returncode == 0, f"child process failed{detail}"
    # The discriminating precondition: the wizard is genuinely absent.
    assert "WIZARD:NOT_IMPORTED" in out, f"test invalid - the child imported the wizard{detail}"

    # Post-#30: the decoupled derivation resolves off the wizard-free projection.
    assert "FIRST_YEAR:True" in out, f"first-year flag must resolve True WITHOUT the wizard{detail}"
    assert "ACTIVITY_START:2025-01-01" in out, f"activity-start must resolve off the projection{detail}"
