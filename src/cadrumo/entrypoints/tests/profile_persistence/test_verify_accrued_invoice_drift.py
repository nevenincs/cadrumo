"""A draft that holds an accrued unpaid invoice goes stale when that invoice moves.

Worked by hand: under accrual an issued invoice of base 1000.00 with no receipt adds
1000.00 to the year's income through no ledger row. Edited to 2000.00 the income is
2000.00; deleted it is nothing. Under cash the same invoice adds nothing, so no draft
holds it and its edits move nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports
from cadrumo.adapters.persistence.profile.catalogue_reads import build_invoice_catalogue_read_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_filing_fingerprint import (
    CURRENT_INVOICE_FIELD_SET_VERSION,
    capture_invoice_fingerprint,
    fingerprint_scope_is_narrower,
    invoice_row_fingerprint,
)
from cadrumo.application.aggregation.renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationFilingHistory,
)
from cadrumo.application.invoices.catalogue_lifecycle import (
    CatalogueInvoicePatch,
    remove_catalogue_invoice,
    update_catalogue_invoice,
)
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, operation_performed_role
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.invoice_fingerprint import (
    InvoiceFingerprintSnapshot,
    InvoiceRowFingerprint,
    invoice_snapshot_fingerprint,
)
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_ledger_membership_ports,
    build_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.ledger_drift_support import TAX_ID
from cadrumo.entrypoints.tests.profile_persistence.observation_seeding_support import save_stamped_observation
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_substance_support import (
    workflow_profile as plain_workflow_profile,
)
from cadrumo.tests.env_scope import ready_clave_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "34700000-0000-4000-8000-000000000349"
_YEAR = newest_authored_edition("100")
_T0 = datetime(_YEAR + 1, 1, 10, 10, 0, tzinfo=UTC)
_DRIFT_KEY = "application.modelo.findings.invoice_fingerprint_drift"
_NARROWER_KEY = "application.modelo.findings.invoice_fingerprint_narrower_scope"
_M130_INCOME = "01"
_CRITERION = "irpf.activity_income_imputation_criterion"
_ACCOUNTING = "irpf.codigo_comercio_accounting"
_ACCRUED = date(_YEAR, 2, 10)
_CUSTOMER = "B00015016"
_WORK = (("130", "1T"),)
_TICK = count(1)
_PRIOR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PRIOR_NET_INCOME_CASILLAS = ("0224", "1479", "1553", "1577")


def _minoracion_ceiling() -> Decimal:
    """The highest prior-year net activity income box 13's minoracion still reduces, read from the pinned formula."""
    with bundled_indexed_authority().operation() as operation:
        formulas = operation.snapshot("130", filing_year=_YEAR, period="1T").revision.formulas
    (formula,) = (item for item in formulas if item.target_casilla_id == "13")
    ceilings: list[Decimal] = []

    def collect(expression: FormulaExpression) -> None:
        if expression.op == "less_equal" and any(arg.binding == _PRIOR_NET_INCOME_BINDING for arg in expression.args):
            ceilings.extend(arg.literal for arg in expression.args if arg.literal is not None)
        for arg in expression.args:
            collect(arg)

    collect(formula.expression)
    return max(ceilings)


def _record_prior_year_renta(objects: SecureObjectRepository) -> None:
    """Record last year's Modelo 100 with net activity income above the minoracion ceiling.

    The activity began years before this quarter, so box 13 reads last year's return; above
    the ceiling the minoracion is zero and the quarter rests only on the invoices.
    """
    net_income = _minoracion_ceiling() + Decimal("1000.00")
    casilla_values = dict.fromkeys(
        (validated_casilla_id(box) for box in _PRIOR_NET_INCOME_CASILLAS[1:]), Decimal("0.00")
    )
    casilla_values[validated_casilla_id(_PRIOR_NET_INCOME_CASILLAS[0])] = net_income
    save_stamped_observation(
        CalculationObservationRepository(objects=objects),
        RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period="0A",
            observations=registry_grounded_observations(
                modelo="100", filing_year=_YEAR - 1, period="0A", casilla_values=casilla_values
            ),
        ),
        source_kind="app_filing",
        captured_at=datetime(_YEAR, 6, 1, 12, 0, tzinfo=UTC),
    )


def _facts(criterion: str, regime: str) -> tuple[UserProfileFact, ...]:
    def dated(path: str, value: object) -> UserProfileFact:
        return UserProfileFact.model_validate(
            {"path": path, "value": value, "valid_from": date(_YEAR, 1, 1), "valid_to": date(_YEAR, 12, 31)}
        )

    return persona_facts_beneath(
        (
            UserProfileFact(path="identity.tax_id", value=TAX_ID),
            UserProfileFact(path="identity.name", value="Ready"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="accrued-invoice-drift"),
            UserProfileFact(path="censo.activity_start_date", value=date(_YEAR - 5, 1, 1)),
            UserProfileFact(path="withholding.colegio_concertado", value=False),
            UserProfileFact(path="irpf.estimation_regime", value=regime),
            dated(_ACCOUNTING, False),
            dated(_CRITERION, criterion),
        ),
        without=(_ACCOUNTING, _CRITERION),
    )


def _unpaid(number: str = "V-001", *, on: date = _ACCRUED, base: Decimal = Decimal("1000.00")) -> Invoice:
    iva = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.ISSUED,
            invoice_number=number,
            issued_at=on,
            counterparty_tax_id=_CUSTOMER,
            currency="EUR",
            grand_total=base + iva,
        ),
        bucket_id=_BUCKET,
        kind=InvoiceKind.ISSUED,
        invoice_number=number,
        issued_at=on,
        operation_date=on,
        operation_date_role=operation_performed_role(),
        counterparty_name="CLIENTE SL",
        counterparty_tax_id=_CUSTOMER,
        counterparty_country="ES",
        base_total=base,
        iva_total=iva,
        grand_total=base + iva,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=base,
                subtotal=base,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva,
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )


def _corrected_base() -> Invoice:
    return _unpaid(base=Decimal("2000.00"))


@dataclass(frozen=True)
class _Draft:
    objects: SecureObjectRepository
    invoices: InvoiceCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    work_unit: WorkUnit
    invoice: Invoice


def _later() -> datetime:
    return datetime(_YEAR + 1, 4, 20, 12, 0, tzinfo=UTC) + timedelta(hours=next(_TICK))


def _calculate(draft: _Draft) -> CalculationRevision:
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            draft.work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET, operation=operation),
            clock=_later(),
        ).revision


def _verify(draft: _Draft, revision: CalculationRevision) -> VerificationReport:
    with bundled_indexed_authority().operation() as operation:
        return verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=plain_workflow_profile(tax_id=TAX_ID, activity_start_date=date(_YEAR - 5, 1, 1)),
            settings=ready_clave_settings(TAX_ID),
            verification_repositories=replace(
                build_verification_repository_bundle(_BUCKET, operation=operation),
                ledger_membership_ports=build_ledger_membership_ports(
                    bucket_id=_BUCKET,
                    transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET, objects=draft.objects),
                ),
            ),
            clock=_later(),
            operator_scope_ports=build_operator_scope_ports(),
            operation=operation,
        ).report


def _drift_counts(report: VerificationReport) -> tuple[object, object, object] | None:
    found = [finding for finding in report.findings if finding.message_locale_key == _DRIFT_KEY]
    if not found:
        return None
    (finding,) = found
    assert finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    facts = finding.message_facts
    return facts["changed_count"], facts["removed_count"], facts["added_count"]


def _open_draft(tmp_path: Path, *, modelo: str, period: str, criterion: str, regime: str) -> Iterator[_Draft]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=_facts(criterion, regime),
                created_at=_T0,
                updated_at=_T0,
                context=profile_creation_context_for_test(),
            ),
        )
        objects = profile.repository
        _record_prior_year_renta(objects)
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=objects)
        invoice = _unpaid()
        invoices.save(build_invoice_catalogue((invoice,)))
        with bundled_indexed_authority().operation() as operation:
            revision_id = operation.snapshot(modelo, filing_year=_YEAR, period=period).revision.id
            work_unit = create_work_unit(
                bucket_id=_BUCKET,
                modelo=modelo,
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, period),
                revision_id=revision_id,
                ports=WorkLifecyclePorts(
                    work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                    bucket_event_repository=BucketEventHistoryRepository(objects=objects),
                ),
                operation=operation,
                clock=_T0,
            )
        yield _Draft(
            objects=objects,
            invoices=invoices,
            calculations=CalculationRevisionCatalogueRepository(objects=objects),
            work_unit=work_unit,
            invoice=invoice,
        )


@pytest.fixture(params=_WORK, ids=lambda work: f"m{work[0]}")
def draft(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[_Draft]:
    modelo, period = request.param
    yield from _open_draft(tmp_path, modelo=modelo, period=period, criterion="devengo", regime="directa_normal")


@pytest.fixture
def cash_draft(tmp_path: Path) -> Iterator[_Draft]:
    yield from _open_draft(
        tmp_path, modelo="130", period="1T", criterion="cobros_y_pagos", regime="directa_simplificada"
    )


def test_editing_the_held_invoice_blocks_the_draft(draft: _Draft) -> None:
    revision = _calculate(draft)
    assert _drift_counts(_verify(draft, revision)) is None

    draft.invoices.save(build_invoice_catalogue((_corrected_base(),)))

    # The total enters an invoice's identity, so a corrected base is one record out and one in.
    report = _verify(draft, revision)
    assert _drift_counts(report) == (0, 1, 1)
    assert report.granted_verificado_completo is False


def test_an_edit_keeping_its_identity_blocks_the_draft(draft: _Draft) -> None:
    revision = _calculate(draft)

    update_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=draft.invoice.invoice_id,
        patch=CatalogueInvoicePatch(operation_date=date(_YEAR, 2, 20)),
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
        occurred_at=_later(),
    )

    assert _drift_counts(_verify(draft, revision)) == (1, 0, 0)


def test_deleting_the_held_invoice_blocks_the_draft(draft: _Draft) -> None:
    revision = _calculate(draft)

    remove_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=draft.invoice.invoice_id,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
    )

    report = _verify(draft, revision)
    assert _drift_counts(report) == (0, 1, 0)
    assert report.granted_verificado_completo is False


def test_a_new_accrued_invoice_blocks_the_draft(draft: _Draft) -> None:
    revision = _calculate(draft)

    added = _unpaid("V-002", on=date(_YEAR, 3, 3))
    draft.invoices.save(build_invoice_catalogue((draft.invoice, added)))

    assert _drift_counts(_verify(draft, revision)) == (0, 0, 1)


def test_recalculating_clears_the_drift(draft: _Draft) -> None:
    revision = _calculate(draft)
    draft.invoices.save(build_invoice_catalogue((_corrected_base(),)))
    assert _drift_counts(_verify(draft, revision)) == (0, 1, 1)

    assert revision.casilla_values[_M130_INCOME] == Decimal("1000.00")
    recalculated = _calculate(draft)
    assert recalculated.casilla_values[_M130_INCOME] == Decimal("2000.00")
    assert _drift_counts(_verify(draft, recalculated)) is None


def test_an_invoice_of_a_later_window_is_out_of_scope(draft: _Draft) -> None:
    revision = _calculate(draft)
    later_year = _unpaid("V-LATER", on=date(_YEAR + 1, 2, 2))
    draft.invoices.save(build_invoice_catalogue((draft.invoice, later_year)))
    assert _drift_counts(_verify(draft, revision)) is None


def test_under_cash_an_unpaid_invoice_is_out_of_scope(cash_draft: _Draft) -> None:
    revision = _calculate(cash_draft)
    cash_draft.invoices.save(build_invoice_catalogue((_corrected_base(),)))
    assert _drift_counts(_verify(cash_draft, revision)) is None


def _as_stored_by_the_previous_build(
    draft: _Draft, revision: CalculationRevision, *rows: Invoice, version: int = 1
) -> CalculationRevision:
    """Store the draft as an older version left it, with that version's digests of the rows given."""
    fingerprints = tuple(
        InvoiceRowFingerprint(
            invoice_id=row.invoice_id, fingerprint=invoice_row_fingerprint(row, field_set_version=version)
        )
        for row in rows
    )
    old = revision.model_copy(
        update={
            "invoice_fingerprint": InvoiceFingerprintSnapshot(
                rows=fingerprints,
                snapshot_fingerprint=invoice_snapshot_fingerprint(fingerprints),
                captured_at=revision.created_at,
                field_set_version=version,
            )
        }
    )
    draft.calculations.save(upsert_calculation_revision(draft.calculations.load(), old))
    stored = draft.calculations.load().get(old.calculation_revision_id)
    assert stored is not None
    assert stored.invoice_fingerprint == old.invoice_fingerprint
    return stored


def _requires_recalculating(report: VerificationReport) -> None:
    """Assert the one finding says the draft cannot prove it is current, and that it blocks."""
    (blocking,) = [finding for finding in report.findings if finding.message_locale_key == _NARROWER_KEY]
    assert blocking.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert blocking.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert _drift_counts(report) is None


def test_a_stored_version_one_draft_stays_readable_and_must_be_calculated_again(draft: _Draft) -> None:
    """Its scope leaves out what the figures rest on, so it cannot prove it is current, whether or not anything moved."""
    stored = _as_stored_by_the_previous_build(draft, _calculate(draft))
    assert stored.invoice_fingerprint is not None

    _requires_recalculating(_verify(draft, stored))
    draft.invoices.save(build_invoice_catalogue((_corrected_base(),)))
    _requires_recalculating(_verify(draft, stored))


def test_a_narrower_scope_never_binds_a_cash_draft(cash_draft: _Draft) -> None:
    """Under cash no invoice enters by accrual and no correction nets, so version 1 misses nothing."""
    stored = _as_stored_by_the_previous_build(cash_draft, _calculate(cash_draft))
    assert not [f for f in _verify(cash_draft, stored).findings if f.message_locale_key == _NARROWER_KEY]


def _narrower(
    draft: _Draft,
    version: int,
    *,
    criterion: str = "devengo",
    regime: str = "directa_normal",
    filings: ImputationFilingHistory | None = None,
) -> bool:
    with bundled_indexed_authority().operation() as operation:
        return fingerprint_scope_is_narrower(
            InvoiceFingerprintSnapshot(
                rows=(),
                snapshot_fingerprint=invoice_snapshot_fingerprint(()),
                captured_at=_T0,
                field_set_version=version,
            ),
            revision=operation.revision(draft.work_unit.modelo, draft.work_unit.revision_id),
            work_unit=draft.work_unit,
            criteria=ImputationCriteria(facts=_facts(criterion, regime), filings=filings or ImputationFilingHistory()),
        )


def test_each_older_version_is_narrower_than_the_current_for_an_accrual_draft(draft: _Draft) -> None:
    assert [_narrower(draft, version) for version in (1, 2, 3, CURRENT_INVOICE_FIELD_SET_VERSION)] == [
        True,
        True,
        True,
        False,
    ]


def test_a_filed_return_contradicting_the_election_leaves_no_accrual_scope_to_miss(draft: _Draft) -> None:
    """The filed return states cash and the profile accrual, so no criterion holds and the resolver refuses the box."""
    stated = ImputationFilingHistory(stated={_YEAR: ActivityImputationCriterion.COBROS_Y_PAGOS})
    assert _narrower(draft, 1) is True
    assert _narrower(draft, 1, filings=stated) is False


def test_an_oss_draft_of_an_older_version_is_narrower_under_any_criterion(tmp_path: Path) -> None:
    """A version 1 OSS digest does not hold the number a correction names, so it never saw a correction move."""
    criterion, regime = "cobros_y_pagos", "directa_simplificada"
    for drafted in _open_draft(tmp_path, modelo="369", period="EXT-1T", criterion=criterion, regime=regime):
        assert _narrower(drafted, 1, criterion=criterion, regime=regime) is True
        current = CURRENT_INVOICE_FIELD_SET_VERSION
        assert _narrower(drafted, current, criterion=criterion, regime=regime) is False


def test_recalculating_a_version_one_draft_moves_it_to_the_wider_scope(draft: _Draft) -> None:
    revision = _calculate(draft)
    stored = _as_stored_by_the_previous_build(draft, revision)

    repinned = _calculate(draft)

    assert repinned.calculation_revision_id == stored.calculation_revision_id
    assert repinned.invoice_fingerprint is not None
    assert repinned.invoice_fingerprint.field_set_version == CURRENT_INVOICE_FIELD_SET_VERSION
    assert [row.invoice_id for row in repinned.invoice_fingerprint.rows] == [draft.invoice.invoice_id]
    assert not [f for f in _verify(draft, repinned).findings if f.message_locale_key == _NARROWER_KEY]


def test_the_annual_scope_holds_the_year_and_not_the_next(draft: _Draft) -> None:
    """Modelo 100 reads the whole year through the same scope; only a window's reach differs."""
    late = _unpaid("V-DEC", on=date(_YEAR, 12, 30))
    next_year = _unpaid("V-NEXT", on=date(_YEAR + 1, 1, 2))
    draft.invoices.save(build_invoice_catalogue((draft.invoice, late, next_year)))
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("100", filing_year=_YEAR, period="0A").revision
        snapshot = capture_invoice_fingerprint(
            work_unit=WorkUnit.model_construct(
                bucket_id=_BUCKET,
                modelo="100",
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, "0A"),
                revision_id=revision.id,
            ),
            revision=revision,
            contributors=frozenset(),
            ports=build_invoice_catalogue_read_ports(bucket_id=_BUCKET),
            captured_at=_later(),
            criteria=ImputationCriteria(facts=_facts("devengo", "directa_normal")),
        )
    assert snapshot is not None
    assert {row.invoice_id for row in snapshot.rows} == {draft.invoice.invoice_id, late.invoice_id}


def _received_unpaid(number: str = "C-001", *, on: date = _ACCRUED) -> Invoice:
    """A purchase of 100,00 + 21,00 with no ledger row, which under accrual leaves the expense boxes unresolved."""
    base = Decimal("100.00")
    iva = Decimal("21.00")
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.RECEIVED,
            invoice_number=number,
            issued_at=on,
            counterparty_tax_id=_CUSTOMER,
            currency="EUR",
            grand_total=base + iva,
        ),
        bucket_id=_BUCKET,
        kind=InvoiceKind.RECEIVED,
        invoice_number=number,
        issued_at=on,
        operation_date=on,
        operation_date_role=operation_performed_role(),
        counterparty_name="PROVEEDOR SL",
        counterparty_tax_id=_CUSTOMER,
        counterparty_country="ES",
        base_total=base,
        iva_total=iva,
        grand_total=base + iva,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Suministro",
                quantity=Decimal("1"),
                unit_price=base,
                subtotal=base,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva,
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )


def test_a_received_invoice_added_after_calculating_blocks_the_draft(draft: _Draft) -> None:
    revision = _calculate(draft)
    assert _drift_counts(_verify(draft, revision)) is None

    draft.invoices.save(build_invoice_catalogue((draft.invoice, _received_unpaid())))

    assert _drift_counts(_verify(draft, revision)) == (0, 0, 1)


def test_under_cash_an_unpaid_received_invoice_is_out_of_scope(cash_draft: _Draft) -> None:
    revision = _calculate(cash_draft)
    cash_draft.invoices.save(build_invoice_catalogue((cash_draft.invoice, _received_unpaid())))
    assert _drift_counts(_verify(cash_draft, revision)) is None


def test_a_draft_captured_before_the_expense_scope_must_be_calculated_again(draft: _Draft) -> None:
    """A version 2 draft cannot see a received invoice that entered its window, so it cannot prove it is current."""
    stored = _as_stored_by_the_previous_build(draft, _calculate(draft), draft.invoice, version=2)

    draft.invoices.save(build_invoice_catalogue((draft.invoice, _received_unpaid())))
    _requires_recalculating(_verify(draft, stored))
