"""The CLI overview calendar and the TUI workbench calendar decide Modelo 347 alike from the ledger.

Both compositions run over one genuine encrypted profile bucket holding the
same profile record and the same invoice catalogue: the CLI through its
overview read ports, the TUI through its secure workbench generation
provider. A counterparty above the RGAT art. 33.1 floor ("hayan superado la
cifra de 3.005,06 euros durante el año natural correspondiente") makes the
2025 declaration owed whether the profile answers no or leaves the question
unanswered, and both surfaces must show that row.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
from cadrumo.application.overview.read_payload import OverviewCalendarRead
from cadrumo.application.overview.read_request import OverviewReadKind, OverviewReadRequest
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.time.clock import today_madrid
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.overview_read_composition import build_overview_read_ports
from cadrumo.entrypoints.workbench_generation_composition import compose_secure_workbench_generation_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "34700000-0000-4000-8000-000000000347"
_FILING_YEAR = 2025
_CLOCK = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
_THRESHOLD = "obligations.third_party_transactions_above_347_threshold"

_AUTONOMO_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="design"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
)


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _sale_above_the_floor() -> Invoice:
    """One customer at 3.005,07 EUR gross: 2.483,53 base plus 21 % IVA."""
    base_total = Decimal("2483.53")
    iva_total = Decimal("521.54")
    grand_total = base_total + iva_total
    issued_at = date(_FILING_YEAR, 6, 10)
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.ISSUED,
            invoice_number="V-347",
            issued_at=issued_at,
            counterparty_tax_id="B87654323",
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="V-347",
        issued_at=issued_at,
        counterparty_name="CLIENTE GRANDE SL",
        counterparty_tax_id="B87654323",
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=grand_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


def _cli_m347_years(operation: PinnedAuthorityOperation) -> set[int]:
    today = today_madrid()
    payload = build_overview_read_ports(bucket_id=_BUCKET_ID, operation=operation).capture(
        OverviewReadRequest(
            profile_id=UUID(_BUCKET_ID),
            kind=OverviewReadKind.CALENDAR,
            output_language=OutputLanguage.EN,
            from_date=date(today.year - 1, 1, 1),
            to_date=date(today.year, 12, 31),
        ),
        operation=operation,
    )
    assert isinstance(payload, OverviewCalendarRead)
    assert payload.calendar is not None
    return {entry.period.filing_year for entry in payload.calendar.to_calendar().entries if entry.modelo == "347"}


def _tui_m347_years(operation: PinnedAuthorityOperation) -> set[int]:
    generation = compose_secure_workbench_generation_provider(
        profile_id=_BUCKET_ID,
        operation=operation,
        operation_contracts=build_production_operation_registry().public_contract_set,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="347 parity",
            expires_at=_CLOCK,
        ),
    )()
    projection = generation.declarations_calendar.projection
    assert projection is not None
    return {entry.filing_year for entry in projection.entries if entry.modelo == "347"}


@pytest.mark.parametrize(
    ("threshold", "sale_above_the_floor", "owed"),
    [
        pytest.param(False, True, True, id="ledger-yes-profile-no"),
        pytest.param(None, True, True, id="ledger-yes-profile-unanswered"),
        pytest.param(False, False, False, id="empty-ledger-profile-no"),
    ],
)
def test_cli_and_tui_show_the_ledger_derived_modelo_347_row_alike(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    threshold: bool | None,
    sale_above_the_floor: bool,
    owed: bool,
) -> None:
    facts = _AUTONOMO_FACTS if threshold is None else (*_AUTONOMO_FACTS, UserProfileFact(path=_THRESHOLD, value=False))
    with validating_governed_facts(authority_operation):
        catalogue = build_invoice_catalogue([_sale_above_the_floor()] if sale_above_the_floor else [])
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="347 parity") as profile:
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=facts,
                created_at=_CLOCK,
                updated_at=_CLOCK,
                context=profile_creation_context_for_test(),
            ),
        )
        InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(
            catalogue,
        )

        cli_years = _cli_m347_years(authority_operation)
        tui_years = _tui_m347_years(authority_operation)

    assert (_FILING_YEAR in cli_years) is owed
    assert cli_years == tui_years
