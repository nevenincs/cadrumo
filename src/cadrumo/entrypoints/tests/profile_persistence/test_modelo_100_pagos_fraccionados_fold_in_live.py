"""M100 annual 0604 folds in M130 1T-4T pagos fraccionados (LIVE path).

The annual IRPF declaration (Modelo 100) casilla ``0604`` ("Pagos fraccionados
ingresados") is a *computed* casilla whose registry formula
``renta-pagos-fraccionados-ingresados`` sums two cross-model relations:

* ``renta-modelo-130-pagos-fraccionados`` — ``source_modelo='130'``,
  ``source_casilla_ids=('19', '18')``, ``source_periods=('1T','2T','3T','4T')``.
* ``renta-modelo-131-pagos-fraccionados`` — ``source_modelo='131'``,
  ``source_casilla_ids=('15', '14')``, same four periods. A direct-estimation
  taxpayer does not file M131, so that mutually exclusive leg resolves as
  explicit zero without synthetic filings.

Each relation materialises into its declared ``target_binding``
(``renta-modelo-130-pagos-fraccionados`` / ``-131-``), whose registry binding
declares ``source='relation_prefill'`` with the ``pagos_fraccionados_ingresados``
aggregation: per quarter, the effective filing's previously paid result plus the
positive part of its own result. :class:`RelationPrefillSourceResolver` is enrolled in the
live source mesh, making the relation canonical for cross-modelo fold-in. This
module proves the wiring works end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
four prior M130 quarterly filings fold into the annual 0604.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralBucketSession`, real
registry authority, real calculation engine, real relation resolver, real source
mesh — no mocks, stubs, skips, or xfail).

The aggregation assertion is a fold-WIRING invariant, not a tautology: the test
persists four local M130 filing observations with the persona's reported c19
values (380.00 each) and independently expects the annual credit to be 1520.00.
It does not reproduce any registry formula under test; it proves the
cross-period fold wires the prior filings through to 0604 and that the absent,
not-applicable M131 leg no longer blanks the M130 credit.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from ....domain.modelos.calculation_revision import derive_calculation_revision_id_from_revision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation
from .unchecked_credit_note_support import assert_only_unchecked_credit_notes

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "10006040-0000-4000-8000-000000000604"


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024

# The operator's locally filed M130 quarters reported casilla 19 ("Resultado a ingresar")
# as EUR 380.00 in every quarter, so annual M100 must credit EUR 1520.00.
_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("380.00"),
    "2T": Decimal("380.00"),
    "3T": Decimal("380.00"),
    "4T": Decimal("380.00"),
}
_EXPECTED_M130_TOTAL = Decimal("1520.00")
_M130_SOURCE_CASILLA_ID: CasillaId = validated_casilla_id("19", surface="_M130_SOURCE_CASILLA_ID")
_M130_PRIOR_RESULT_CASILLA_ID: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RESULT_CASILLA_ID")
_M130_LIQUIDACION_CASILLA_ID: CasillaId = validated_casilla_id("14", surface="_M130_LIQUIDACION_CASILLA_ID")
_M130_NEGATIVOS_ANTERIORES_CASILLA_ID: CasillaId = validated_casilla_id(
    "15",
    surface="_M130_NEGATIVOS_ANTERIORES_CASILLA_ID",
)
_M130_DIFERENCIA_CASILLA_ID: CasillaId = validated_casilla_id("17", surface="_M130_DIFERENCIA_CASILLA_ID")
_M100_ANNUAL_PERIOD = "0A"
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
_RELATION_PREFILL_SOURCE = "relation_prefill"
_M130_PAGOS_BINDING_ID: BindingId = "renta-modelo-130-pagos-fraccionados"
_M130_PAGOS_RELATION_ID = "renta-modelo-130-pagos-fraccionados"
_M131_PAGOS_RELATION_ID = "renta-modelo-131-pagos-fraccionados"


def _seed_m130_quarters(
    *,
    obs_repo: CalculationObservationRepository,
    periods: tuple[str, ...],
) -> Decimal:
    """Persist one original M130/2024 filing observation per requested period.

    Persisted through the production observation-persistence API
    (:meth:`CalculationObservationRepository.save_observation`) — the same write
    path the local-file carry flow uses — stamped with the non-official
    ``app_filing`` source_kind. Each filing is an original autoliquidación, so
    casilla 18 carries zero. Returns the summed c19 over the seeded periods.
    """
    total = Decimal("0")
    for period in periods:
        value = _M130_C19_BY_PERIOD[period]
        _save_m130_filing(
            obs_repo,
            period=period,
            casilla_values={_M130_SOURCE_CASILLA_ID: value, _M130_PRIOR_RESULT_CASILLA_ID: Decimal("0")},
        )
        total += value
    return total


def _save_m130_filing(
    obs_repo: CalculationObservationRepository,
    *,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
    captured_at: datetime = _T0,
) -> None:
    """Persist one M130/2024 autoliquidación; a later save replaces the quarter's effective filing."""
    save_stamped_observation(
        obs_repo,
        RegistryModeloObservation(
            modelo="130",
            filing_year=_YEAR,
            period=period,
            observations=registry_grounded_observations(
                modelo="130",
                filing_year=_YEAR,
                period=period,
                casilla_values=casilla_values,
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
    )


def _seed_prior_year_m100_zero_carry(secure_objects: SecureObjectRepository) -> None:
    save_stamped_observation(
        CalculationObservationRepository(objects=secure_objects),
        RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period=_M100_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_M100_ANNUAL_PERIOD,
                casilla_values={
                    _M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0"),
                    **dict.fromkeys(_PRIOR_ANEXO_C_REMAINDERS, Decimal("0")),
                },
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_taxpayer_unit_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed a single-taxpayer ``UserProfileRecord`` covering M100's profile bindings.

    The M100/2024 annual revision declares ``source = "profile"`` bindings (the
    taxpayer birth date for ``age_at_year_end``, CCAA, declaration type, marital
    status, minor-children counts). Without them the engine refuses the bound
    casillas that consume them before it ever reaches casilla 0604. The profile
    is the substrate of record, so the live source mesh's profile resolver
    auto-fills these — no profile fact is hand-fed through the caller channel.
    Mirrors ``test_modelo_100_cross_year_carry_continuity._seed_taxpayer_unit_profile``.
    """
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                # An IAE epigraph outside group 861, so no urban rental is carried on as an activity.
                UserProfileFact(path="activities.iae_epigraph", value="844"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
            )
        ),
        created_at=_T0,
        updated_at=_T0,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced.

    The annual M100 revision binds many casillas (the Anexo-C base-liquidable
    carry, ...) whose values an empty bucket does not supply; the engine refuses
    the consuming casilla before reaching 0604. These are supplied as zero
    through the caller channel (the pure-pagos-fold persona declares no other
    prior activity), leaving the two ``relation_prefill`` pagos bindings UNSET so
    the enrolled relation resolver folds them from the seeded M130 store on the
    live path. Mirrors the non-profile zero-default in
    ``test_modelo_100_cross_year_carry_continuity._calculate_100``.
    """
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_income_aggregation",
            "ledger_renta_gastos_estimacion_directa_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
            "retencion_soportada",
        )
    }


def _calculate_m100_annual(
    secure_objects: SecureObjectRepository,
    *,
    binding_values: dict[BindingId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
):
    """Run the live M100/2024/0A calculate over the seeded bucket.

    Seeds the taxpayer profile and zero-defaults non-profile/non-relation
    bindings so the engine reaches casilla 0604; the two pagos-fraccionados
    ``relation_prefill`` bindings are deliberately left UNSET so the enrolled
    relation resolver folds them from the seeded M130 observation store.
    """
    _seed_taxpayer_unit_profile(secure_objects)
    _seed_prior_year_m100_zero_carry(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    bucket_event_repo = BucketEventHistoryRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bucket_event_repo),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bucket_event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_302:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values={**_non_relation_zero_bindings(), **(binding_values or {})},
            ports=_calculation_ports_302,
            clock=_T1,
        )


def test_m100_0604_folds_in_four_m130_quarters_on_live_calculate(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """E2E: the four filed M130 quarters fold into the annual M100 0604.

    With four M130/2024 quarters recorded as filed observations (each carrying
    the persona's c19=380.00), and no M131 filings because the profile is direct
    estimation, a live calculate of the M100/2024 annual draws both
    pagos-fraccionados relations through the enrolled
    ``RelationPrefillSourceResolver`` and 0604 equals 1520.00.
    """
    obs_repo = CalculationObservationRepository()
    seeded_total = _seed_m130_quarters(obs_repo=obs_repo, periods=("1T", "2T", "3T", "4T"))
    # Sanity: the four seeded observations reproduce the operator's local
    # M130 c19 values and total to a strictly-positive known annual credit.
    assert seeded_total == _EXPECTED_M130_TOTAL
    assert seeded_total > Decimal("0")

    result = _calculate_m100_annual(secure_objects, operation=operation)

    casilla_0604 = Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA])
    # M131 c15 folds to zero by not-applicable profile evidence; 0604 == sum(M130 c19).
    assert casilla_0604 == _EXPECTED_M130_TOTAL, (
        f"M100 0604 must fold in the four M130 quarters (sum {_EXPECTED_M130_TOTAL}); got {casilla_0604}"
    )
    assert Decimal(result.revision.binding_overrides[_M131_PAGOS_RELATION_ID]) == Decimal("0")

    # The relation_prefill source is CLAIMED (resolver enrolled): no
    # unhandled_binding_source advisory names it, and the diagnostics carry no
    # row for it.
    relation_prefill_diags = tuple(
        diag for diag in result.source_diagnostics if diag.source_kind == _RELATION_PREFILL_SOURCE
    )
    assert relation_prefill_diags == (), (
        f"relation_prefill must be a claimed source with no diagnostics; got {relation_prefill_diags}"
    )
    assert not any(
        diag.reason == "unhandled_binding_source" and diag.source_kind == _RELATION_PREFILL_SOURCE
        for diag in result.source_diagnostics
    )
    # The only diagnostics are credit boxes noted as not cross-checked: the gate lets them through.
    assert_only_unchecked_credit_notes(result.source_diagnostics)


def test_m100_explicit_m130_binding_resolves_relation_formula_without_m131_filing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The public --binding override reaches M100 0604's relation formula."""
    result = _calculate_m100_annual(
        secure_objects,
        binding_values={_M130_PAGOS_BINDING_ID: _EXPECTED_M130_TOTAL},
        operation=operation,
    )

    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == _EXPECTED_M130_TOTAL
    assert Decimal(result.revision.binding_overrides[_M130_PAGOS_RELATION_ID]) == _EXPECTED_M130_TOTAL
    assert Decimal(result.revision.binding_overrides[_M131_PAGOS_RELATION_ID]) == Decimal("0")
    assert not set(result.revision.relation_overrides) & {_M130_PAGOS_RELATION_ID, _M131_PAGOS_RELATION_ID}
    assert not any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id in {_M130_PAGOS_RELATION_ID, _M131_PAGOS_RELATION_ID}
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics


def test_m100_partial_prior_m130_filings_leave_0604_unresolved_with_diagnostic(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A partial prior M130 set leaves 0604 blank and names the missing relation."""
    obs_repo = CalculationObservationRepository()
    _seed_m130_quarters(obs_repo=obs_repo, periods=("1T", "2T"))

    result = _calculate_m100_annual(secure_objects, operation=operation)

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics


def test_m100_no_prior_m130_filing_leaves_0604_unresolved_with_diagnostic(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """An absent prior M130 set leaves 0604 blank and names the missing relation."""
    result = _calculate_m100_annual(secure_objects, operation=operation)

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics


# The scenarios below derive 0604 by hand from the AEAT Modelo 130 instructions,
# never from the registry: casilla 17 = 14 - 15 - 16; casilla 18 holds "el
# resultado a ingresar de las autoliquidaciones, modelo 130, presentadas
# anteriormente por el mismo ejercicio y período" (zero when none resulted a
# ingresar); casilla 19 = 17 - 18; a negative casilla 19 "podrá deducirse en
# cualquiera de los siguientes pagos fraccionados" (through a later casilla 15)
# and only a positive casilla 19 goes to "Ingreso". So the amount paid for a
# quarter, read from its effective filing, is casilla 18 plus the positive part
# of casilla 19.


def _original(c19: str) -> dict[CasillaId, Decimal]:
    """Return an original autoliquidación's result pair (no earlier filing, so casilla 18 is zero)."""
    return {_M130_SOURCE_CASILLA_ID: Decimal(c19), _M130_PRIOR_RESULT_CASILLA_ID: Decimal("0")}


def _calculate_0604(
    secure_objects: SecureObjectRepository,
    *,
    filings: tuple[tuple[str, dict[CasillaId, Decimal]], ...],
    operation: PinnedAuthorityOperation,
):
    obs_repo = CalculationObservationRepository()
    for index, (period, casilla_values) in enumerate(filings):
        _save_m130_filing(
            obs_repo,
            period=period,
            casilla_values=casilla_values,
            captured_at=_T0.replace(minute=index),
        )
    return _calculate_m100_annual(secure_objects, operation=operation)


def test_m100_0604_adds_every_positive_quarter(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Four positive quarters were each paid in full."""
    result = _calculate_0604(
        secure_objects,
        filings=(
            ("1T", _original("120.00")),
            ("2T", _original("80.00")),
            ("3T", _original("150.00")),
            ("4T", _original("50.00")),
        ),
        operation=operation,
    )

    # oracle: AEAT-MODELO-130-INSTRUCCIONES casilla 19 y (4) Ingreso; 120.00 + 80.00 + 150.00 + 50.00
    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("400.00")


def test_m100_0604_credits_no_payment_for_a_negative_quarter_deducted_later(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A negative 1T is not paid; 2T deducts it through casilla 15 and pays only its own result."""
    result = _calculate_0604(
        secure_objects,
        filings=(
            ("1T", {**_original("-100.00"), _M130_DIFERENCIA_CASILLA_ID: Decimal("-100.00")}),
            (
                "2T",
                {
                    **_original("200.00"),
                    _M130_LIQUIDACION_CASILLA_ID: Decimal("300.00"),
                    _M130_NEGATIVOS_ANTERIORES_CASILLA_ID: Decimal("100.00"),
                    _M130_DIFERENCIA_CASILLA_ID: Decimal("200.00"),
                },
            ),
            ("3T", _original("0.00")),
            ("4T", _original("50.00")),
        ),
        operation=operation,
    )

    # oracle: AEAT-MODELO-130-INSTRUCCIONES casillas 15, 17 y 19; paid 0 + (300 - 100) + 0 + 50 = 250.00.
    # A signed sum of casilla 19 would give 150.00 and count the deducted 100.00 twice.
    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("250.00")


def test_m100_0604_credits_no_payment_for_a_negative_fourth_quarter(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A negative 4T has no later quarter to deduct it and reduces nothing already paid."""
    result = _calculate_0604(
        secure_objects,
        filings=(
            ("1T", _original("120.00")),
            ("2T", _original("80.00")),
            ("3T", _original("150.00")),
            ("4T", _original("-30.00")),
        ),
        operation=operation,
    )

    # oracle: AEAT-MODELO-130-INSTRUCCIONES casilla 19 y (4) Ingreso; 120.00 + 80.00 + 150.00 + 0 = 350.00
    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("350.00")


def test_m100_0604_reads_a_complementaria_as_the_quarter_total_paid(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A complementaria replaces 2T's effective filing; the quarter paid its 18 plus its 19."""
    complementaria = {
        _M130_DIFERENCIA_CASILLA_ID: Decimal("260.00"),
        _M130_PRIOR_RESULT_CASILLA_ID: Decimal("200.00"),
        _M130_SOURCE_CASILLA_ID: Decimal("60.00"),
    }
    result = _calculate_0604(
        secure_objects,
        filings=(
            ("1T", _original("100.00")),
            ("2T", _original("200.00")),
            ("2T", complementaria),
            ("3T", _original("50.00")),
            ("4T", _original("40.00")),
        ),
        operation=operation,
    )

    # oracle: AEAT-MODELO-130-INSTRUCCIONES casillas 18 y 19; 2T paid 200.00 then 60.00 = 260.00,
    # so 100.00 + 260.00 + 50.00 + 40.00 = 450.00 (casilla 19 alone would give 250.00).
    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("450.00")


def test_m100_0604_counts_a_twice_corrected_quarter_once_after_repeated_source_saves(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A quarter paid 100, then 30, then 20; its final effective total is 150."""
    filings = (
        ("1T", _original("100.00")),
        ("1T", {_M130_PRIOR_RESULT_CASILLA_ID: Decimal("100.00"), _M130_SOURCE_CASILLA_ID: Decimal("30.00")}),
        ("1T", {_M130_PRIOR_RESULT_CASILLA_ID: Decimal("130.00"), _M130_SOURCE_CASILLA_ID: Decimal("20.00")}),
        ("2T", _original("80.00")),
        ("3T", _original("50.00")),
        ("4T", _original("-30.00")),
    )
    result = _calculate_0604(secure_objects, filings=filings, operation=operation)

    # Payments are 150 + 80 + 50 + 0 = 280; neither the older snapshots nor
    # the negative final quarter are extra payments to include in the annual credit.
    assert Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("280.00")
    replayed = _calculate_0604(secure_objects, filings=filings, operation=operation)
    assert Decimal(replayed.revision.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("280.00")
    stored = (
        CalculationRevisionCatalogueRepository(objects=secure_objects)
        .load(operation=operation)
        .get(result.revision.calculation_revision_id)
    )
    assert stored is not None
    assert derive_calculation_revision_id_from_revision(stored) == result.revision.calculation_revision_id
    assert stored.casilla_values == result.revision.casilla_values
    effective = tuple(
        item.observation
        for item in CalculationObservationRepository().iter_modelo("130")
        if item.observation.filing_year == _YEAR
    )
    assert len(effective) == 4
    quarter = next(item for item in effective if item.period == "1T")
    assert quarter.casilla_values[_M130_PRIOR_RESULT_CASILLA_ID] == Decimal("130.00")
    assert quarter.casilla_values[_M130_SOURCE_CASILLA_ID] == Decimal("20.00")


def test_m100_0604_stays_unresolved_when_the_effective_complementaria_lacks_casilla_18(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Without casilla 18 the quarter's earlier payment is unknown, so 0604 is not guessed."""
    result = _calculate_0604(
        secure_objects,
        filings=(
            ("1T", _original("100.00")),
            ("2T", _original("200.00")),
            ("2T", {_M130_DIFERENCIA_CASILLA_ID: Decimal("260.00"), _M130_SOURCE_CASILLA_ID: Decimal("60.00")}),
            ("3T", _original("50.00")),
            ("4T", _original("40.00")),
        ),
        operation=operation,
    )

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
