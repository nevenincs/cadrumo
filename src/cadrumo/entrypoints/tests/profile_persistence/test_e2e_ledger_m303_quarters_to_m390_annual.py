"""E2E vertical: real ledger → M303 1T-4T (computed) → M390 annual reconciliation.

The IVA counterpart of ``test_e2e_ledger_m130_quarters_to_m100_annual``. Two
segments are each covered in isolation today:

* ledger IVA transactions → M303 computed cuota
  (``test_bucket_aggregation_flow``, a single quarter).
* M303 quarter totals → M390 annual reconciliation fold-in
  (``test_modelo_390_303_fold_in_live``, but with **injected** M303 observations,
  not values the M303 calc actually computed).

Neither joins the two: no test drives *real persisted IVA ledger transactions*
through the live bucket-aggregation calculate action for four quarters, files
each through the production observation-persistence path, and proves the annual
M390 reconciliation casillas fold in the **engine-computed** quarterly IVA totals.
That full IVA vertical — the autónomo's real yearly IVA cadence — is what this
test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + ``isolated_runtime_profile``, the real registry
authority, the real calculation engine, the real ``ledger_iva_aggregation``
resolver, and the real ``relation_prefill`` fold-in resolver. No mocks, stubs,
skips, or xfail.

Non-tautology argument: each quarter's IVA totals are **computed by the engine**
from the ledger transactions' ``iva_amount`` through the M303 formula chain
(repercutido/soportado casillas → cuota-devengada-total / cuota-deducible-total →
resultado-regimen-general); the test never hand-recomputes a registry formula.
The load-bearing assertions are *transport / wiring* invariants: each quarter's
computed cuota-devengada-total equals the persisted incoming IVA the operator
never re-keyed, and the annual M390 reconciliation casillas equal the **sum of
the four engine-computed quarterly totals** (distinct per quarter, so a coincidental
or off-by-one-quarter sum cannot satisfy them).

LIVA art. 88/92 (repercusión / deducción) and the M390 orden ground the
reconciliation; this test asserts the *wiring*, leaving rate currency to the
registry grounding gate.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.action_errors import ModeloCrossPeriodCleanStateError
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    _BUCKET_ID,
    _YEAR,
    IRENE_ANNUAL_EXPECTED,
    IRENE_QUARTER_FACTS,
    LAURA_ANNUAL_EXPECTED,
    persist_year_of_invoices,
    product_software_identity,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

from .m303_m390_chain_support import (
    CASILLA_59,
    DEDUCIBLE_TOTAL,
    DEVENGADA_TOTAL,
    FILE_AT,
    IRENE_FILE_AT,
    IRENE_TAX_ID,
    IRENE_YEAR,
    M390_DEDUCIBLE,
    M390_DEVENGADA,
    M390_RESULTADO,
    OPERATOR_SCOPE_PORTS,
    QUARTER_ORDER,
    RESULTADO,
    TAX_ID,
    ComputedM303CasillasByPeriod,
    bucket_id,
    calculate_and_file_m303_quarter,
    calculate_m303_quarter_revision,
    calculate_m390_annual,
    filing_ports,
    ireneworkflow_profile,
    non_official_local_chain_advisory_periods,
    store_irene_sl_profile,
    store_profile,
    verification_ports,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["bucket_id", "secure_objects"]


def test_persisted_m303_ledger_revision_verifies_and_exports(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Persona-like persisted ledger input verifies under the live revision and exports its fichero."""
    store_profile(secure_objects)
    stored = persist_year_of_invoices(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    _work_unit, revision = calculate_m303_quarter_revision(secure_objects, period="1T", operation=operation)
    assert Decimal(revision.casilla_values[DEVENGADA_TOTAL]) == stored["1T"]["devengada"]
    assert Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]) == stored["1T"]["deducible"]

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=verification_ports(
                operation=operation,
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=vr_repo,
                event_repo=event_repo,
                tx_repo=tx_repo,
            ),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            clock=FILE_AT,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    verified = cr_repo.load().get(revision.calculation_revision_id)
    assert verified is not None
    assert verified.ledger_filing_snapshot is not None
    assert verified.ledger_filing_evidence is not None

    output_path = tmp_path / f"modelo-303-{_YEAR}-1T.boe"
    with bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id=TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=vr_repo,
                bucket_event=event_repo,
            ),
            operation=operation,
            clock=FILE_AT,
        )

    assert output_path.read_bytes().startswith(b"<T3030")


def test_irene_sl_local_m303_files_support_m390_verify_and_annual_export(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Irene SL: a late local M303 FILE chain feeds M390 without claiming AEAT acceptance.

    This is the persona path that direct observation seeding did not cover:
    calculate -> verify -> local file for each closed/overdue M303 quarter,
    then calculate -> verify -> export M390 from those local records.
    The local filing records remain non-official (``aeat_accepted=False``);
    dependent periods surface the non-official-local-chain advisory.
    """
    store_irene_sl_profile(secure_objects)
    stored = persist_year_of_invoices(
        secure_objects,
        filing_year=IRENE_YEAR,
        facts_by_period=IRENE_QUARTER_FACTS,
    )
    workflow_profile = ireneworkflow_profile()
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    verification_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    observation_repo = CalculationObservationRepository(objects=secure_objects)
    wallet_repo = IvaWalletDecisionRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in QUARTER_ORDER:
        _work_unit, revision = calculate_m303_quarter_revision(
            secure_objects,
            period=period,
            filing_year=IRENE_YEAR,
            taxpayer_nif=IRENE_TAX_ID,
            calculated_at=IRENE_FILE_AT,
            operation=operation,
        )
        assert Decimal(revision.casilla_values[DEVENGADA_TOTAL]) == stored[period]["devengada"]
        assert Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]) == stored[period]["deducible"]
        assert Decimal(revision.casilla_values[RESULTADO]) == stored[period]["resultado"]
        computed[period] = {
            DEVENGADA_TOTAL: Decimal(revision.casilla_values[DEVENGADA_TOTAL]),
            DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]),
            RESULTADO: Decimal(revision.casilla_values[RESULTADO]),
        }

        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision_with_preconditions(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=verification_ports(
                    operation=operation,
                    work_repo=wu_repo,
                    calc_repo=cr_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                    event_repo=event_repo,
                    tx_repo=tx_repo,
                ),
                actor="irene",
                workflow_profile=workflow_profile,
                settings=ready_clave_settings("12345678Z"),
                clock=IRENE_FILE_AT,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
                operation=operation,
            ).report
        assert report.granted_verificado_completo is True, report.findings

        with bundled_indexed_authority().operation() as operation:
            filing = file_modelo_revision(
                revision.calculation_revision_id,
                approved_verification_report_id=report.verification_report_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                actor="irene",
                workflow_profile=workflow_profile,
                ports=filing_ports(
                    work_repo=wu_repo,
                    calc_repo=cr_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                    event_repo=event_repo,
                    wallet_repo=wallet_repo,
                    observation_repo=observation_repo,
                    operation=operation,
                ),
                clock=IRENE_FILE_AT,
                operator_scope_ports=OPERATOR_SCOPE_PORTS,
                operation=operation,
            ).record
        assert filing.aeat_accepted is False
        assert filing.external_evidence is None
        stored_observation = observation_repo.load_observation("303", Period.from_year_and_code(IRENE_YEAR, period))
        assert stored_observation is not None
        assert stored_observation.source_kind == "app_filing"

    annual = calculate_m390_annual(secure_objects, filing_year=IRENE_YEAR, operation=operation)
    for m390_casilla, m303_output in (
        (M390_DEVENGADA, DEVENGADA_TOTAL),
        (M390_DEDUCIBLE, DEDUCIBLE_TOTAL),
        (M390_RESULTADO, RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in QUARTER_ORDER), Decimal("0"))
        assert Decimal(annual.casilla_values[m390_casilla]) == expected
    assert Decimal(annual.casilla_values[M390_DEVENGADA]) == IRENE_ANNUAL_EXPECTED["devengada"]
    assert Decimal(annual.casilla_values[M390_DEDUCIBLE]) == IRENE_ANNUAL_EXPECTED["deducible"]
    assert Decimal(annual.casilla_values[M390_RESULTADO]) == IRENE_ANNUAL_EXPECTED["resultado"]

    with bundled_indexed_authority().operation() as operation:
        annual_report = verify_modelo_revision_with_preconditions(
            annual.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=verification_ports(
                operation=operation,
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=verification_repo,
                event_repo=event_repo,
                tx_repo=tx_repo,
            ),
            actor="irene",
            workflow_profile=workflow_profile,
            settings=ready_clave_settings("12345678Z"),
            clock=IRENE_FILE_AT,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report
    assert annual_report.granted_verificado_completo is True, annual_report.findings
    assert non_official_local_chain_advisory_periods(annual_report) == set(QUARTER_ORDER), annual_report.findings

    # The annual resumen verifies from the locally filed quarters and exports.
    annual_output = tmp_path / f"modelo-390-{IRENE_YEAR}-0A.boe"
    with bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=annual_output,
                actor="irene",
            ),
            workflow_profile=workflow_profile,
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id=IRENE_TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=verification_repo,
                bucket_event=event_repo,
                observation=observation_repo,
            ),
            operation=operation,
            clock=IRENE_FILE_AT,
        )
    assert annual_output.read_bytes().startswith(b"<T3900")


def test_ledger_drives_m303_quarters_and_folds_into_m390_annual(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The full yearly IVA cadence: persisted ledger → 4×M303 → M390 reconciliation."""
    store_profile(secure_objects)
    stored = persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in QUARTER_ORDER:
        revision = calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)

        # Transport invariant #1: the computed cuota totals equal the IVA amounts
        # STORED on the persisted invoices (the aggregator sums the stored
        # iva_amount field — it does not re-derive base×rate, confirmed in
        # application/aggregation/iva_ledger.py). Asserting against the stored
        # field, not a fresh base*rate, keeps the seed and the expectation from
        # sharing a literal.
        assert Decimal(revision.casilla_values[DEVENGADA_TOTAL]) == stored[period]["devengada"], (
            f"{period}: cuota-devengada-total must equal the stored issued IVA {stored[period]['devengada']}; "
            f"got {revision.casilla_values.get(DEVENGADA_TOTAL)}"
        )
        assert Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]) == stored[period]["deducible"], (
            f"{period}: cuota-deducible-total must equal the stored received IVA {stored[period]['deducible']}; "
            f"got {revision.casilla_values.get(DEDUCIBLE_TOTAL)}"
        )
        assert Decimal(revision.casilla_values[CASILLA_59]) == stored[period]["casilla_59"], (
            f"{period}: casilla 59 must equal the stored EU supply base {stored[period]['casilla_59']}; "
            f"got {revision.casilla_values.get(CASILLA_59)}"
        )
        assert Decimal(revision.casilla_values[RESULTADO]) == stored[period]["resultado"], (
            f"{period}: resultado-regimen-general must match Laura's expected quarterly result "
            f"{stored[period]['resultado']}; got {revision.casilla_values.get(RESULTADO)}"
        )
        computed[period] = {
            DEVENGADA_TOTAL: Decimal(revision.casilla_values[DEVENGADA_TOTAL]),
            DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]),
            RESULTADO: Decimal(revision.casilla_values[RESULTADO]),
        }

    # Laura's quarterly resultado values are distinct, so a stale or shifted
    # quarterly dependency cannot satisfy the annual result assertion below.
    result_values = [computed[p][RESULTADO] for p in QUARTER_ORDER]
    assert len(set(result_values)) == 4, f"quarterly resultado values must be distinct: {result_values}"

    annual = calculate_m390_annual(secure_objects, operation=operation)
    casillas = annual.casilla_values

    # Transport invariant #2: M390 annual reconciliation folds the SUM of the four
    # engine-computed M303 quarterly totals.
    for m390_casilla, m303_output in (
        (M390_DEVENGADA, DEVENGADA_TOTAL),
        (M390_DEDUCIBLE, DEDUCIBLE_TOTAL),
        (M390_RESULTADO, RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in QUARTER_ORDER), Decimal("0"))
        assert Decimal(casillas[m390_casilla]) == expected, (
            f"M390 {m390_casilla} must fold sum(1T-4T {m303_output})={expected}; got {casillas.get(m390_casilla)}"
        )
    assert Decimal(casillas[M390_DEVENGADA]) == LAURA_ANNUAL_EXPECTED["devengada"]
    assert Decimal(casillas[M390_DEDUCIBLE]) == LAURA_ANNUAL_EXPECTED["deducible"]
    assert Decimal(casillas[M390_RESULTADO]) == LAURA_ANNUAL_EXPECTED["resultado"]


def test_m390_refuses_zero_reconciliation_when_m303_calculated_but_observations_missing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Laura regression: calculated nonzero 303 quarters must not become zero M390 reconciliation slots."""
    store_profile(secure_objects)
    persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in QUARTER_ORDER:
        _work_unit, revision = calculate_m303_quarter_revision(secure_objects, period=period, operation=operation)
        computed[period] = {
            DEVENGADA_TOTAL: Decimal(revision.casilla_values[DEVENGADA_TOTAL]),
            DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[DEDUCIBLE_TOTAL]),
            RESULTADO: Decimal(revision.casilla_values[RESULTADO]),
        }

    assert sum((computed[p][DEVENGADA_TOTAL] for p in QUARTER_ORDER), Decimal("0")) == Decimal("9828.00")
    assert sum((computed[p][DEDUCIBLE_TOTAL] for p in QUARTER_ORDER), Decimal("0")) == Decimal("2163.00")
    assert sum((computed[p][RESULTADO] for p in QUARTER_ORDER), Decimal("0")) == Decimal("7665.00")

    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    before_revision_ids = frozenset(cr_repo.load().revisions)
    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        calculate_m390_annual(secure_objects, operation=operation)
    after_revision_ids = frozenset(cr_repo.load().revisions)

    assert after_revision_ids == before_revision_ids
    assert isinstance(exc_info.value, CadrumoError)
    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == ("1T", "2T", "3T", "4T")
    # Without a filed fourth quarter the annual prorrata regularisation is
    # unresolved, so the annual deduction total and result that sum it are
    # unknown, which proves no zero slot; the output-IVA total refuses as well.
    assert context["zero_reconciliation_casillas_at_risk"] == (
        M390_DEVENGADA,
        M390_DEDUCIBLE,
        M390_RESULTADO,
    )


def test_m390_refuses_annual_zeros_no_source_or_operator_ever_stated(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """An empty ledger and no M303 quarters leave every annual box unknown, not a proven zero.

    The operator states only the annual prorrata regularisation, so the deduction
    totals no longer wait on a filed fourth quarter. Every other box the annual
    totals sum was never supplied, and the engine reads such a box as zero; that
    zero proves nothing, so no reconciliation slot may be saved as zero.
    """
    store_profile(secure_objects)

    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    before_revision_ids = frozenset(cr_repo.load().revisions)
    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        calculate_m390_annual(
            secure_objects,
            operation=operation,
            binding_values={"modelo-390-prorrata-regularizacion-anual": Decimal("0.00")},
        )

    assert frozenset(cr_repo.load().revisions) == before_revision_ids
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == QUARTER_ORDER
    assert context["zero_reconciliation_casillas_at_risk"] == (M390_DEVENGADA, M390_DEDUCIBLE, M390_RESULTADO)
    assert context["annual_casillas_not_proven_zero"] == (
        validated_casilla_id("iva.anual.cuota-devengada-total"),
        validated_casilla_id("iva.anual.cuota-deducible-total"),
        validated_casilla_id("iva.anual.resultado-regimen-general"),
    )
