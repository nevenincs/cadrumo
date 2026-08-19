"""M200 self cross-year STOCK carries fire on the LIVE operator calculate path.

The Impuesto sobre Sociedades carries two kinds of pending STOCK forward across
ejercicios that the operator must not re-key. Both are enrolled
``cross_model_output`` self-relations (``source_modelo = '200'``, ``copy``,
period ``0A``, ``filing_year_delta = -1`` — the prior ejercicio's M200), and both
are proven here end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`), not
the direct ``resolve_relations_from_local_store`` resolver path the existing
continuity tests
(``cadrumo.application.calculations.tests.test_modelo_200_bin_carry_forward_continuity``
and ``...test_modelo_200_dotaciones_deterioro_carry_continuity``) exercise. This
module closes the M200 self-carry honesty-review gap: before it, the relation
resolver was proven to fire, but only on the now-non-canonical direct path —
never on the operator's live calculate.

* **BIN-pendiente self-carry** (LIS art. 26.1, BIN carries forward without time
  limit). The prior ejercicio's casilla ``00671`` ("pendiente de aplicación en
  períodos futuros", a manual end-of-year stock) feeds this ejercicio's opening
  stock casilla ``00670`` ("pendiente de aplicación a principio del período").
  Relation ``modelo-200-2024-rel-self-bin-pendiente-anterior`` (``source_casilla_id =
  '00671'``) drives binding
  ``modelo-200-2024-bin-pendiente-ejercicios-anteriores`` (``copy``), which casilla
  ``00670`` (``input_kind = bound``) consumes.
* **Dotaciones-deterioro self-carry** (LIS art. 13, a dotación whose deducibility
  conditions are not yet met stays pending), tracked SEPARATELY per condition-state
  because only the cumplido stock may be integrated. The prior ejercicio's saldo
  final ``01498`` (NO han cumplido condiciones) / ``01499`` (SÍ han cumplido) feed
  this ejercicio's saldo inicial ``01494`` / ``01495``. Relations
  ``modelo-200-2024-rel-self-dotaciones-deterioro-no-cumplido-anterior``
  (``source_casilla_id = '01498'``) and ``-cumplido-anterior`` (``01499``) drive
  bindings ``...saldo-no-cumplido-anteriores`` / ``...saldo-cumplido-anteriores``
  (``copy``), which casillas ``01494`` / ``01495`` (``input_kind = bound``) consume.

The prior ejercicio (2024) is seeded as a filed observation through the production
observation-persistence API
(:meth:`CalculationObservationRepository.save_observation`, the same write path the
local-file carry flow uses), stamped with the non-official ``app_filing``
source_kind, over a real encrypted-SQLite object store
(:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider` via
:func:`isolated_runtime_profile`). M200 is a sociedad surface: the live calculate
needs the six-binding legal-entity profile scaffold (``new-entity-flag``,
``incn-prior-12-months``, ``tributacion-estado-porcentaje``,
``sal-reserva-especial-dotada``, ``sal-capital-social``, ``legal-entity-form``)
filled by the profile resolver from the persisted sociedad record, plus a
zero-default for every other bound casilla (any carry the store cannot satisfy
resolves present-or-zero). No mocks, stubs, skips, or xfail.

Non-tautological: the seeded prior-year ``00671`` / ``01498`` / ``01499`` are three
DISTINCT non-equal known Decimals, and the carry aggregation is ``copy`` — so the
assertion proves each opening-stock casilla equals exactly the seeded prior-year
closing stock (a copy of a distinct seeded value, never a re-evaluated formula). A
channel swap (no-cumplido into cumplido, or BIN into a dotación channel), an
off-by-year fold, a single-channel copy, or a silent blank cannot satisfy the three
per-casilla assertions. The prior-year stock is a manual input no formula under
test produces; a change in any relation's ``source_casilla_id`` or ``aggregation`` op,
or a binding retraction, would red the assertions.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    RegistryModeloObservation,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e30320c1-7532-458b-b0ba-a8b8f4b70c9e"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M200 = "200"
_M202 = "202"

# The same-year M202 pagos-fraccionados c34 output the M200 cuota-diferencial
# formula folds via relation ``modelo-200-2024-rel-202-pagos-fraccionados``
# (filing_year_delta = 0). That relation is consumed DIRECTLY by a formula operand
# (the cuota-diferencial subtraction), so an absent value RAISES on the live path
# rather than resolving present-or-zero. It is NOT the cross-year
# carry under test, so seed it as zero (no instalments this scenario) to keep the
# live calculate focused on the BIN / dotaciones self-carries.
_M202_PAGO_OUTPUT: CasillaId = validated_casilla_id("34", surface="_M202_PAGO_OUTPUT")
_M202_PAGO_OUTPUT_40_2: CasillaId = validated_casilla_id(
    "03",
    surface="_M202_PAGO_OUTPUT_40_2",
)  # modalidad cuota (art. 40.2); folds alongside casilla 34
_M202_PAGO_PERIODS = ("1P", "2P", "3P")
_M202_PAGO_RELATION = "modelo-200-2024-rel-202-pagos-fraccionados"
_CASILLA_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_CASILLA_CUOTA_DIFERENCIAL",
)

# The M200 ejercicio under live calculate, and the prior ejercicio the
# filing_year_delta = -1 self-relations source. The bundled M200 authority
# begins at 2024, so this test must exercise a supported two-year window.
_FILING_YEAR = 2025
_PRIOR_YEAR = 2024

# Prior-ejercicio closing-stock casillas (manual on the prior filing) that the
# self-relations read.
_PRIOR_BIN_PENDIENTE_FUTUROS: CasillaId = validated_casilla_id(
    "00671",
    surface="_PRIOR_BIN_PENDIENTE_FUTUROS",
)  # source_casilla_id for the BIN self-relation
_PRIOR_SALDO_FINAL_NO_CUMPLIDO: CasillaId = validated_casilla_id(
    "01498",
    surface="_PRIOR_SALDO_FINAL_NO_CUMPLIDO",
)  # source_casilla_id for the no-cumplido relation
_PRIOR_SALDO_FINAL_CUMPLIDO: CasillaId = validated_casilla_id(
    "01499",
    surface="_PRIOR_SALDO_FINAL_CUMPLIDO",
)  # source_casilla_id for the cumplido relation

# This-ejercicio opening-stock casillas (bound) the carries populate.
_BIN_PENDIENTE_INICIO: CasillaId = validated_casilla_id(
    "00670",
    surface="_BIN_PENDIENTE_INICIO",
)  # consumes the BIN carry
_SALDO_INICIAL_NO_CUMPLIDO: CasillaId = validated_casilla_id(
    "01494",
    surface="_SALDO_INICIAL_NO_CUMPLIDO",
)  # consumes the no-cumplido carry
_SALDO_INICIAL_CUMPLIDO: CasillaId = validated_casilla_id(
    "01495",
    surface="_SALDO_INICIAL_CUMPLIDO",
)  # consumes the cumplido carry

# Three DISTINCT non-equal known prior-year closing stocks. Distinctness makes a
# channel swap, an off-by-year fold, or a single-channel copy red the per-casilla
# assertions: each opening casilla must copy exactly its own channel's seeded value.
_PRIOR_BIN_STOCK = Decimal("30000.00")
_PRIOR_DOTACIONES_NO_CUMPLIDO = Decimal("8000.00")
_PRIOR_DOTACIONES_CUMPLIDO = Decimal("5000.00")

_RELATION_PREFILL_SOURCE = "relation_prefill"
#: The three cross-year self-carries whose absence declares a zero opening stock.
_M200_SELF_CARRY_RELATIONS = frozenset(
    {
        "modelo-200-2024-rel-self-bin-pendiente-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-no-cumplido-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-cumplido-anterior",
    },
)


def _seed_m200_sociedad_profile(*, activity_start_date: date | None = None) -> None:
    """Seed a legal-entity ``UserProfileRecord`` covering M200's six profile bindings.

    M200 declares six ``source = "profile"`` bindings. Four are consumed by
    the cuota chain (``legal-entity-form``, ``new-entity-flag``,
    ``incn-prior-12-months``, ``tributacion-estado-porcentaje``); two are Sociedad
    Laboral specific (``sal-reserva-especial-dotada`` / ``sal-capital-social``),
    absent / zero for a standard SL, which the formulas treat as no dotacion. The
    profile resolver fills all six from the persisted record; no profile binding is
    hand-fed through the caller channel. ``display_name`` matches the
    ``isolated_runtime_profile`` manifest label so the loaded
    :class:`CommittedProfileView` passes its cross-store label-agreement validator.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Test Runtime Profile SL"),
            UserProfileFact(path="activities.description", value="software consultancy"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            *(
                (UserProfileFact(path="censo.activity_start_date", value=activity_start_date),)
                if activity_start_date is not None
                else ()
            ),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _seed_prior_m200_closing_stock(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist the prior-ejercicio M200 closing stock the self-relations read.

    One filed prior-year M200/0A observation carrying the three DISTINCT closing-stock
    casillas (``00671`` BIN-pendiente-futuros, ``01498`` saldo-final-no-cumplido,
    ``01499`` saldo-final-cumplido), stamped ``app_filing`` — the operator's
    historical filing the ``filing_year_delta = -1`` carries fold into the current
    ejercicio.
    """
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_M200,
                filing_year=_PRIOR_YEAR,
                period="0A",
                observations=registry_grounded_observations(
                    modelo=_M200,
                    filing_year=_PRIOR_YEAR,
                    period="0A",
                    casilla_values={
                        _PRIOR_BIN_PENDIENTE_FUTUROS: _PRIOR_BIN_STOCK,
                        _PRIOR_SALDO_FINAL_NO_CUMPLIDO: _PRIOR_DOTACIONES_NO_CUMPLIDO,
                        _PRIOR_SALDO_FINAL_CUMPLIDO: _PRIOR_DOTACIONES_CUMPLIDO,
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _seed_zero_m202_pagos(*, obs_repo: CalculationObservationRepository) -> None:
    """Seed same-year M202 instalments as zero c34 so the pagos relation resolves.

    The M200 cuota-diferencial formula folds ``modelo-200-2024-rel-202-pagos-fraccionados``
    (a same-year M202 pagos relation) as a DIRECT formula operand, which raises if
    unsupplied. This scenario declares no instalments, so each period's c34 is filed
    zero — the relation resolves to zero and the live calculate proceeds, leaving
    the cross-year BIN / dotaciones carries the sole subject of the assertions.
    """
    for period in _M202_PAGO_PERIODS:
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo=_M202,
                    filing_year=_FILING_YEAR,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo=_M202,
                        filing_year=_FILING_YEAR,
                        period=period,
                        casilla_values={
                            _M202_PAGO_OUTPUT: Decimal("0"),
                            _M202_PAGO_OUTPUT_40_2: Decimal("0"),
                        },
                    ),
                ),
                source_kind=APP_FILING_SOURCE_KIND,
                captured_at=_T0,
            )
        )


def _calculate_m200(
    secure_objects: SecureObjectRepository,
    *,
    seed_m202_pagos: bool = True,
    activity_start_date: date | None = None,
) -> BucketAggregationCalculationResult:
    """Run the live M200 calculate over the seeded bucket.

    Every M200 binding is either ``profile`` (filled by the profile resolver from
    the seeded sociedad record) or ``relation_prefill`` (filled by the enrolled
    :class:`RelationPrefillSourceResolver` from the seeded prior-ejercicio
    observations, or defaulted present-or-zero). No manual M200 casilla inputs are
    supplied through the caller channel, so the three opening-stock casillas resolve
    solely from the seeded prior-year closing stock via the self cross-year carries.
    The same-year M202 pagos relation (a direct formula operand) is seeded zero so
    the cuota-diferencial formula resolves; it is not the carry under test.
    """
    _seed_m200_sociedad_profile(activity_start_date=activity_start_date)
    if seed_m202_pagos:
        _seed_zero_m202_pagos(obs_repo=CalculationObservationRepository())
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(_M200, filing_year=_FILING_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_m200_self_cross_year_stock_carries_fire_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: the prior-ejercicio BIN + dotaciones closing stock fold into live M200.

    With the prior-year M200 closing stock filed (distinct ``00671`` / ``01498`` /
    ``01499``), a live calculate of the current ejercicio draws all three self
    cross-year carries through the enrolled ``RelationPrefillSourceResolver``:

    - casilla ``00670`` (opening BIN stock) == prior ``00671`` (LIS art. 26.1
      unlimited BIN carry-forward, ``copy``).
    - casilla ``01494`` (opening dotaciones no-cumplido) == prior ``01498``.
    - casilla ``01495`` (opening dotaciones cumplido) == prior ``01499``.

    The three distinct seeded values are carried per channel, copy semantics — so
    each opening casilla equals (not sums) its own channel's seeded closing stock.
    """
    obs_repo = CalculationObservationRepository()
    _seed_prior_m200_closing_stock(obs_repo=obs_repo)
    # Sanity: the three seeded closing stocks are mutually distinct and strictly
    # positive, so a channel swap, an off-by-year fold, or a single-channel copy
    # cannot satisfy all three per-channel assertions.
    assert len({_PRIOR_BIN_STOCK, _PRIOR_DOTACIONES_NO_CUMPLIDO, _PRIOR_DOTACIONES_CUMPLIDO}) == 3
    assert min(_PRIOR_BIN_STOCK, _PRIOR_DOTACIONES_NO_CUMPLIDO, _PRIOR_DOTACIONES_CUMPLIDO) > Decimal("0")

    result = _calculate_m200(secure_objects)

    values = result.revision.casilla_values
    assert Decimal(values[_BIN_PENDIENTE_INICIO]) == _PRIOR_BIN_STOCK, (
        f"M200 {_FILING_YEAR} casilla 00670 must copy the prior {_PRIOR_YEAR} 00671 BIN stock "
        f"({_PRIOR_BIN_STOCK}); "
        f"got {values[_BIN_PENDIENTE_INICIO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == _PRIOR_DOTACIONES_NO_CUMPLIDO, (
        f"M200 {_FILING_YEAR} casilla 01494 must copy the prior {_PRIOR_YEAR} 01498 no-cumplido stock "
        f"({_PRIOR_DOTACIONES_NO_CUMPLIDO}); got {values[_SALDO_INICIAL_NO_CUMPLIDO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == _PRIOR_DOTACIONES_CUMPLIDO, (
        f"M200 {_FILING_YEAR} casilla 01495 must copy the prior {_PRIOR_YEAR} 01499 cumplido stock "
        f"({_PRIOR_DOTACIONES_CUMPLIDO}); got {values[_SALDO_INICIAL_CUMPLIDO]}"
    )
    # The two dotaciones channels carry distinct values — a condition-state channel
    # swap would surface here.
    assert values[_SALDO_INICIAL_NO_CUMPLIDO] != values[_SALDO_INICIAL_CUMPLIDO]

    # All three carries run through the claimed relation_prefill source: no
    # unhandled relation diagnostic, and a clean overall resolution (the six
    # profile bindings resolve silently).
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    assert result.source_diagnostics == (), (
        f"M200 source_diagnostics must be clean for the sociedad self-carry persona; got {result.source_diagnostics}"
    )


def test_m200_self_carries_resolve_zero_with_no_prior_filing_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """Pin the live behaviour of the M200 self-carries with NO prior filing.

    The BIN-stock and dotaciones-deterioro self-carries use the previous_filing
    observation-coverage semantics: with NO prior M200 in the store, the
    ``filing_year_delta = -1`` carries resolve present-or-zero rather than raising.
    The live calculate succeeds and all three opening-stock casillas resolve to
    zero. (xfail/skip-free per the testing mandate.)

    The zero remains correct and this test's original premise remains valid for the
    population it named: a first-ejercicio filer genuinely has no prior stock to
    carry. What changed is that this persona declares NO activity start date, so
    nothing upstream can establish that it is such a filer, and the carries now
    also raise a non-blocking advisory. The advisory is asserted here rather than
    the previously-empty diagnostics tuple — the values are unchanged, and the
    silence was the only thing that moved. The sibling test below pins the
    first-ejercicio case, where the advisory correctly does NOT fire.
    """
    result = _calculate_m200(secure_objects)

    values = result.revision.casilla_values
    assert Decimal(values[_BIN_PENDIENTE_INICIO]) == Decimal("0"), (
        f"M200 {_FILING_YEAR} casilla 00670 with no prior 00671 must resolve zero; got {values[_BIN_PENDIENTE_INICIO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == Decimal("0"), (
        f"M200 {_FILING_YEAR} casilla 01494 with no prior 01498 must resolve zero; "
        f"got {values[_SALDO_INICIAL_NO_CUMPLIDO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == Decimal("0"), (
        f"M200 {_FILING_YEAR} casilla 01495 with no prior 01499 must resolve zero; "
        f"got {values[_SALDO_INICIAL_CUMPLIDO]}"
    )
    # The zeros above are the whole of what an operator sees, and each one is a
    # carry that would have reduced the liability. With no declared activity start
    # nothing can rule out that this filer had the obligation, so each absent carry
    # is named. Asserted by property — every self-carry relation appears — not by a
    # diagnostic count.
    advised = {
        diagnostic.relation_id
        for diagnostic in result.source_diagnostics
        if diagnostic.source_kind == _RELATION_PREFILL_SOURCE
    }
    assert advised >= _M200_SELF_CARRY_RELATIONS, (
        f"each absent self-carry must be advised; missing {_M200_SELF_CARRY_RELATIONS - advised}"
    )
    for diagnostic in result.source_diagnostics:
        assert diagnostic.reason == "source_issue"


def test_m200_first_ejercicio_filer_carries_zero_without_an_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """A company in its FIRST ejercicio gets the same zeros and no carry advisory.

    The control that keeps the advisory honest. A first-ejercicio filer has no
    prior stock by construction, so naming its absent carries would be noise on the
    whole population of new companies — the alert-fatigue failure that makes a
    channel worthless on the day one divergence matters.

    Nothing here suppresses the advisory specially. The declared activity start
    puts the prior ejercicio before the company existed, and
    ``_scoped_relation_source_requirements`` removes those source periods upstream
    against the shared no-obligation predicate, so the requirements never reach the
    advisory at all. The zeros are identical to the sibling test; only the silence
    differs, and it differs because of a declared fact rather than a special case.
    """
    result = _calculate_m200(secure_objects, activity_start_date=date(_FILING_YEAR, 1, 1))

    values = result.revision.casilla_values
    assert Decimal(values[_BIN_PENDIENTE_INICIO]) == Decimal("0")
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == Decimal("0")
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == Decimal("0")

    advised = {
        diagnostic.relation_id
        for diagnostic in result.source_diagnostics
        if diagnostic.source_kind == _RELATION_PREFILL_SOURCE
    }
    assert not (_M200_SELF_CARRY_RELATIONS & advised), (
        "a first-ejercicio filer has no prior stock, so its self-carries must not be advised; "
        f"got {_M200_SELF_CARRY_RELATIONS & advised}"
    )


def test_m200_missing_m202_relation_becomes_unresolved_advisory_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """Missing formula-consumed M202 pagos do not raise or zero-contribute.

    This pins the live-path robustness rule: a missing same-year M202 relation
    leaves the dependent M200 formula output unresolved and emits a
    non-blocking relation-prefill advisory naming the missing source filings.
    The bound self-carry casillas still resolve their first-ejercicio zero stock
    without diagnostics because they are not formula relation operands.
    """
    result = _calculate_m200(secure_objects, seed_m202_pagos=False)

    values = result.revision.casilla_values
    assert _CASILLA_CUOTA_DIFERENCIAL not in values, (
        "missing M202 pagos relation must leave M200 cuota diferencial unresolved; "
        f"got {_CASILLA_CUOTA_DIFERENCIAL}={values.get(_CASILLA_CUOTA_DIFERENCIAL)!r}"
    )
    assert Decimal(values[_BIN_PENDIENTE_INICIO]) == Decimal("0")
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == Decimal("0")
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == Decimal("0")

    diagnostics = tuple(diag for diag in result.source_diagnostics if diag.relation_id == _M202_PAGO_RELATION)
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "source_issue"
    assert diagnostic.source_kind == _RELATION_PREFILL_SOURCE
    assert diagnostic.resolver_id == _RELATION_PREFILL_SOURCE
    assert "modelo 202" in diagnostic.message
    assert str(_FILING_YEAR) in diagnostic.message
    for period in _M202_PAGO_PERIODS:
        assert period in diagnostic.message
