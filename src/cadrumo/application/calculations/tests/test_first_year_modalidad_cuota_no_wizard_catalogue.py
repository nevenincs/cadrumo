"""The first-year flag resolves in a process that never imports the wizard.

The engine's first-year derivation (``_first_year_modalidad_cuota_no_m202`` /
``activity_start_date_for_bucket``) reads the wizard-free profile projection
(``record_to_path_values``). A non-CLI calculation entrypoint therefore resolves
the first-year relaxation without any setup surface.

A self-contained child process does its own isolated bucket setup and full M200
calculate, then asserts that ``cadrumo.application.wizard`` was never imported
(the discriminating condition). In that process the first-year flag resolves
True, the activity-start date resolves, and the M200/2025 cuota-diferencial
(DP200014B:00611) computes.

Real-behaviour, real-adapter (the child runs the real encrypted-SQLite store via
``isolated_runtime_profile``, the real registry authority, the real calculate
action). No mocks, no monkeypatch: the no-wizard condition comes from process
isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Child process: does its own isolated setup + full M200/2025 first-year calculate
# WITHOUT ever importing cadrumo.application.wizard. argv[1] is a tmp dir for the bucket.
_CHILD_SCRIPT = r"""
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.application.calculations.relation_prefill import (
    activity_start_date_for_bucket,
    _first_year_modalidad_cuota_no_m202,
)
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.period import Period
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from cadrumo.application.modelo.work_lifecycle import create_work_unit

# The custody ports are bound by an explicit composition root that a
# `python -c` child does not inherit.
from contextlib import ExitStack

from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port

composition = ExitStack()
composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
operation = composition.enter_context(bundled_indexed_authority().operation())

_PROFILE_ID = "20020020-0200-4200-8200-200200200200"
_BUCKET = _PROFILE_ID
_T0 = datetime(2026, 1, 12, 10, 0, tzinfo=UTC)
tmp = Path(sys.argv[1])

with isolated_runtime_profile(tmp_path=tmp, bucket_id=_BUCKET) as profile:
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
    seed_test_profile_record(record)

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

    ports = build_calculation_action_ports(bucket_id=_BUCKET, operation=operation)
    # This child asks a CALCULATION question -- it resolves a modalidad and
    # calculates, and never renders a fichero or an export layout -- so it asks
    # for the calculation rung. Modelo 200's revision declares exactly that rung
    # and deliberately refuses the filing rung while it spans two incompatible
    # AEAT layouts, so demanding filing here would be asking for an authority
    # this work does not need and the registry is right to withhold.
    snapshot = published_snapshot(
        "200",
        filing_year=2025,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="200",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision_id=snapshot.revision.id,
        ports=ports.work_lifecycle_ports,
        operation=operation,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        ports=ports,
        clock=_T0,
    )
    present = "DP200014B:00611" in result.revision.casilla_values
    print("CUOTA_DIFERENCIAL:" + ("PRESENT" if present else "ABSENT"))
print("WIZARD:" + ("IMPORTED" if "cadrumo.application.wizard" in sys.modules else "NOT_IMPORTED"))
"""


def test_first_year_modalidad_cuota_resolves_without_wizard_catalogue(tmp_path: Path) -> None:
    """In a process that never imports the wizard, the first-year flag still resolves."""
    child = ensure_text_completed_process(
        run_audited_process(
            [sys.executable, "-c", _CHILD_SCRIPT, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=300,
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
    # And the full calculate computes the cuota-diferencial (no silent over-block).
    assert "CUOTA_DIFERENCIAL:PRESENT" in out, (
        f"M200/2025 first-year cuota-diferencial DP200014B:00611 must COMPUTE without the wizard{detail}"
    )
