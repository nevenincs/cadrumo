"""IS-3 first-year flag resolves WITHOUT the wizard catalogue (#30 decouple).

Companion to ``application/modelo/tests/test_modelo_200_first_year_cuota_e2e.py``
(which exercises the CLI path WITH the wizard ``SETUP_FLOW`` catalogue registered).
That path could not, before #30, surface the failure mode: the engine's first-year
derivation (``_first_year_modalidad_cuota_no_m202`` / ``activity_start_date_for_bucket``)
re-built the profile through ``taxpayer_profile_from_mapping`` -> ``get_setup_flow()``
and SILENTLY swallowed ``WizardCatalogueNotRegisteredError``, so in any process that
computes an M200 without registering the catalogue (a non-CLI calc entrypoint) the
first-year relaxation silently over-blocked (cuota-diferencial unresolved), cause
hidden.

#30 decouples the derivation onto the wizard-FREE profile projection
(``record_to_path_values``). This module proves it in a GENUINELY
catalogue-unregistered process: a self-contained child process that does its own
isolated bucket setup and full M200 calculate but NEVER imports the wizard
catalogue, so ``get_setup_flow()`` raises there. The child asserts the catalogue is
unregistered (the discriminating condition), then:

  POST-fix: the first-year flag resolves True off the projection, the activity-start
  date resolves, and the M200/2025 cuota-diferencial (DP200014B:00611) COMPUTES.
  PRE-fix: the wizard error was swallowed -> flag False, date None, 00611 ABSENT.

Real-behaviour, real-adapter (the child runs the real encrypted-SQLite store via
``isolated_runtime_profile``, the real registry authority, the real calculate
action). No mocks, no monkeypatch (the no-catalogue condition is achieved by
process isolation, not by patching ``get_setup_flow``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Child process: does its own isolated setup + full M200/2025 first-year calculate
# WITHOUT ever importing cadrumo.application.wizard.catalogue, so the wizard SETUP_FLOW
# catalogue is unregistered in this process. argv[1] is a tmp dir for the bucket.
_CHILD_SCRIPT = r"""
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# Discriminating precondition: the wizard catalogue must NOT be registered here.
from cadrumo.core.wizard_catalogue import WizardCatalogueNotRegisteredError, get_setup_flow

try:
    get_setup_flow()
    print("CATALOGUE:REGISTERED")
    raise SystemExit(3)
except WizardCatalogueNotRegisteredError:
    print("CATALOGUE:UNREGISTERED")

from cadrumo.application.calculations._relation_prefill import (
    activity_start_date_for_bucket,
    _first_year_modalidad_cuota_no_m202,
)
from cadrumo.core import Period, RegistryAuthorityGrade
from cadrumo.core.resources import resources
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.secure_sql import isolated_runtime_profile
from cadrumo.tests.profile_capsule import seed_test_profile_record
from cadrumo.application.modelo._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from cadrumo.application.modelo._work_lifecycle import create_work_unit

# Custody is composed AFTER the catalogue probe above, so it cannot perturb the
# discriminating precondition this child exists to prove. The ports are bound by
# an explicit composition root that a `python -c` child does not inherit.
from contextlib import ExitStack

from cadrumo.adapters.persistence.storage import (
    build_profile_custody_port,
    build_profile_login_session_port,
)
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port

composition = ExitStack()
composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))

_PROFILE_ID = "20020020-0200-4200-8200-200200200200"
_BUCKET = _PROFILE_ID
_T0 = datetime(2026, 1, 12, 10, 0, tzinfo=UTC)
tmp = Path(sys.argv[1])

with isolated_runtime_profile(tmp_path=tmp, bucket_id=_BUCKET) as profile:
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
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

    # The decoupled helpers must resolve off the projection with NO catalogue.
    print("FIRST_YEAR:" + str(_first_year_modalidad_cuota_no_m202(_BUCKET, filing_year=2025)))
    print("ACTIVITY_START:" + str(activity_start_date_for_bucket(_BUCKET)))

    secure_objects = profile.repository
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    # This child asks a CALCULATION question -- it resolves a modalidad and
    # calculates, and never renders a fichero or an export layout -- so it asks
    # for the calculation rung. Modelo 200's revision declares exactly that rung
    # and deliberately refuses the filing rung while it spans two incompatible
    # AEAT layouts, so demanding filing here would be asking for an authority
    # this work does not need and the registry is right to withhold.
    snapshot = bundled_authority().snapshot(
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
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )
    present = "DP200014B:00611" in result.revision.casilla_values
    print("CUOTA_DIFERENCIAL:" + ("PRESENT" if present else "ABSENT"))
"""


def test_first_year_modalidad_cuota_resolves_without_wizard_catalogue(tmp_path: Path) -> None:
    """In a process where the wizard catalogue is unregistered, the first-year flag still resolves.

    The child process never registers the wizard ``SETUP_FLOW`` catalogue, so it is
    the genuine non-CLI calc context. Post-#30, the decoupled projection-based
    derivation resolves the first-year relaxation and the M200/2025 cuota-diferencial
    COMPUTES; pre-#30 the swallowed ``WizardCatalogueNotRegisteredError`` left the
    flag False, the date None, and the casilla ABSENT.
    """
    child = subprocess.run(  # noqa - fixed executable and in-module script constant
        [sys.executable, "-c", _CHILD_SCRIPT, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    out = child.stdout
    detail = f"\n--- stdout ---\n{out}\n--- stderr ---\n{child.stderr}"

    # The discriminating precondition: the catalogue is genuinely unregistered.
    assert "CATALOGUE:UNREGISTERED" in out, f"test invalid - wizard catalogue was registered in the child{detail}"
    assert child.returncode == 0, f"child process failed{detail}"

    # Post-#30: the decoupled derivation resolves off the wizard-free projection.
    assert "FIRST_YEAR:True" in out, f"first-year flag must resolve True WITHOUT the wizard catalogue{detail}"
    assert "ACTIVITY_START:2025-01-01" in out, f"activity-start must resolve off the projection{detail}"
    # And the full calculate computes the cuota-diferencial (no silent over-block).
    assert "CUOTA_DIFERENCIAL:PRESENT" in out, (
        f"M200/2025 first-year cuota-diferencial DP200014B:00611 must COMPUTE without the wizard catalogue{detail}"
    )
