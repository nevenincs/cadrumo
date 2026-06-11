"""M200 self cross-year STOCK carries fire on the LIVE operator calculate path.

The Impuesto sobre Sociedades carries two kinds of pending STOCK forward across
ejercicios that the operator must not re-key. Both are enrolled
``cross_model_output`` self-relations (``source_modelo = '200'``, ``copy``,
period ``0A``, ``filing_year_delta = -1`` — the prior ejercicio's M200), and both
are proven here end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`), not
the direct ``resolve_relations_from_local_store`` resolver path the existing
continuity tests
(``aeat.application.calculations.tests.test_modelo_200_bin_carry_forward_continuity``
and ``...test_modelo_200_dotaciones_deterioro_carry_continuity``) exercise. This
module closes the M200 self-carry honesty-review gap: before it, the relation
resolver was proven to fire, but only on the now-non-canonical direct path —
never on the operator's live calculate.

* **BIN-pendiente self-carry** (LIS art. 26.1, BIN carries forward without time
  limit). The prior ejercicio's casilla ``00671`` ("pendiente de aplicación en
  períodos futuros", a manual end-of-year stock) feeds this ejercicio's opening
  stock casilla ``00670`` ("pendiente de aplicación a principio del período").
  Relation ``modelo-200-2024-rel-self-bin-pendiente-anterior`` (``source_output =
  '00671'``) drives binding
  ``modelo-200-2024-bin-pendiente-ejercicios-anteriores`` (``copy``), which casilla
  ``00670`` (``input_kind = bound``) consumes.
* **Dotaciones-deterioro self-carry** (LIS art. 13, a dotación whose deducibility
  conditions are not yet met stays pending), tracked SEPARATELY per condition-state
  because only the cumplido stock may be integrated. The prior ejercicio's saldo
  final ``01498`` (NO han cumplido condiciones) / ``01499`` (SÍ han cumplido) feed
  this ejercicio's saldo inicial ``01494`` / ``01495``. Relations
  ``modelo-200-2024-rel-self-dotaciones-deterioro-no-cumplido-anterior``
  (``source_output = '01498'``) and ``-cumplido-anterior`` (``01499``) drive
  bindings ``...saldo-no-cumplido-anteriores`` / ``...saldo-cumplido-anteriores``
  (``copy``), which casillas ``01494`` / ``01495`` (``input_kind = bound``) consume.

The prior ejercicio (2023) is seeded as a filed observation through the production
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
test produces; a change in any relation's ``source_output`` or ``aggregation`` op,
or a binding retraction, would red the assertions.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-m200-self-carry-fold"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M200 = "200"
_M202 = "202"

# The same-year M202 pagos-fraccionados c34 output the M200 cuota-diferencial
# formula folds via relation ``modelo-200-2024-rel-202-pagos-fraccionados``
# (filing_year_delta = 0). That relation is consumed DIRECTLY by a formula operand
# (the cuota-diferencial subtraction), so an absent value RAISES on the live path
# (finding #26) rather than resolving present-or-zero. It is NOT the cross-year
# carry under test, so seed it as zero (no instalments this scenario) to keep the
# live calculate focused on the BIN / dotaciones self-carries.
_M202_PAGO_OUTPUT = "34"
_M202_PAGO_PERIODS = ("1P", "2P", "3P")

# The M200 ejercicio under live calculate, and the prior ejercicio the
# filing_year_delta = -1 self-relations source.
_FILING_YEAR = 2024
_PRIOR_YEAR = 2023

# Prior-ejercicio closing-stock casillas (manual on the prior filing) that the
# self-relations read.
_PRIOR_BIN_PENDIENTE_FUTUROS = "00671"  # source_output for the BIN self-relation
_PRIOR_SALDO_FINAL_NO_CUMPLIDO = "01498"  # source_output for the no-cumplido relation
_PRIOR_SALDO_FINAL_CUMPLIDO = "01499"  # source_output for the cumplido relation

# This-ejercicio opening-stock casillas (bound) the carries populate.
_BIN_PENDIENTE_INICIO = "00670"  # consumes the BIN carry
_SALDO_INICIAL_NO_CUMPLIDO = "01494"  # consumes the no-cumplido carry
_SALDO_INICIAL_CUMPLIDO = "01495"  # consumes the cumplido carry

# Three DISTINCT non-equal known prior-year closing stocks. Distinctness makes a
# channel swap, an off-by-year fold, or a single-channel copy red the per-casilla
# assertions: each opening casilla must copy exactly its own channel's seeded value.
_PRIOR_BIN_STOCK = Decimal("30000.00")
_PRIOR_DOTACIONES_NO_CUMPLIDO = Decimal("8000.00")
_PRIOR_DOTACIONES_CUMPLIDO = Decimal("5000.00")

_RELATION_PREFILL_SOURCE = "relation_prefill"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_m200_sociedad_profile() -> None:
    """Seed a legal-entity ``UserProfileRecord`` covering M200's six profile bindings.

    M200/2024 declares six ``source = "profile"`` bindings. Four are consumed by
    the cuota chain (``legal-entity-form``, ``new-entity-flag``,
    ``incn-prior-12-months``, ``tributacion-estado-porcentaje``); two are Sociedad
    Laboral specific (``sal-reserva-especial-dotada`` / ``sal-capital-social``),
    absent / zero for a standard SL, which the formulas treat as no dotacion. The
    profile resolver fills all six from the persisted record; no profile binding is
    hand-fed through the caller channel. ``display_name`` matches the
    ``isolated_runtime_profile`` manifest label so the loaded
    :class:`ProfileAggregate` passes its cross-store label-agreement validator.
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345678"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _seed_prior_m200_closing_stock(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist the prior-ejercicio (2023) M200 closing stock the self-relations read.

    One filed M200/2023/0A observation carrying the three DISTINCT closing-stock
    casillas (``00671`` BIN-pendiente-futuros, ``01498`` saldo-final-no-cumplido,
    ``01499`` saldo-final-cumplido), stamped ``app_filing`` — the operator's
    historical filing the ``filing_year_delta = -1`` carries fold into the 2024
    ejercicio.
    """
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_M200,
            filing_year=_PRIOR_YEAR,
            period="0A",
            observations=(
                CasillaObservation(casilla_id=_PRIOR_BIN_PENDIENTE_FUTUROS, value=_PRIOR_BIN_STOCK),
                CasillaObservation(casilla_id=_PRIOR_SALDO_FINAL_NO_CUMPLIDO, value=_PRIOR_DOTACIONES_NO_CUMPLIDO),
                CasillaObservation(casilla_id=_PRIOR_SALDO_FINAL_CUMPLIDO, value=_PRIOR_DOTACIONES_CUMPLIDO),
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_zero_m202_pagos(*, obs_repo: CalculationObservationRepository) -> None:
    """Seed same-year M202/2024 instalments as zero c34 so the pagos relation resolves.

    The M200 cuota-diferencial formula folds ``modelo-200-2024-rel-202-pagos-fraccionados``
    (a same-year M202 pagos relation) as a DIRECT formula operand, which raises if
    unsupplied. This scenario declares no instalments, so each period's c34 is filed
    zero — the relation resolves to zero and the live calculate proceeds, leaving
    the cross-year BIN / dotaciones carries the sole subject of the assertions.
    """
    for period in _M202_PAGO_PERIODS:
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo=_M202,
                filing_year=_FILING_YEAR,
                period=period,
                observations=(CasillaObservation(casilla_id=_M202_PAGO_OUTPUT, value=Decimal("0")),),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )


def _calculate_m200(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live M200/2024/0A calculate over the seeded bucket.

    Every M200 binding is either ``profile`` (filled by the profile resolver from
    the seeded sociedad record) or ``relation_prefill`` (filled by the enrolled
    :class:`RelationPrefillSourceResolver` from the seeded prior-ejercicio
    observations, or defaulted present-or-zero). No manual M200 casilla inputs are
    supplied through the caller channel, so the three opening-stock casillas resolve
    solely from the seeded prior-year closing stock via the self cross-year carries.
    The same-year M202 pagos relation (a direct formula operand) is seeded zero so
    the cuota-diferencial formula resolves; it is not the carry under test.
    """
    _seed_m200_sociedad_profile()
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
    """E2E: the prior-ejercicio BIN + dotaciones closing stock fold into M200/2024 live.

    With the prior 2023 M200 closing stock filed (distinct ``00671`` / ``01498`` /
    ``01499``), a live calculate of the 2024 ejercicio draws all three self
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
        f"M200 2024 casilla 00670 must copy the prior 2023 00671 BIN stock ({_PRIOR_BIN_STOCK}); "
        f"got {values[_BIN_PENDIENTE_INICIO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == _PRIOR_DOTACIONES_NO_CUMPLIDO, (
        f"M200 2024 casilla 01494 must copy the prior 2023 01498 no-cumplido stock "
        f"({_PRIOR_DOTACIONES_NO_CUMPLIDO}); got {values[_SALDO_INICIAL_NO_CUMPLIDO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == _PRIOR_DOTACIONES_CUMPLIDO, (
        f"M200 2024 casilla 01495 must copy the prior 2023 01499 cumplido stock "
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
    """Pin the CURRENT live behaviour of the M200 self-carries with NO prior filing.

    The BIN-stock and dotaciones-deterioro self-carries use the previous_filing
    observation-coverage semantics: with NO prior M200 in the store, the
    ``filing_year_delta = -1`` carries resolve present-or-zero rather than raising
    (a first-ejercicio filer simply has no prior stock to carry — a correct zero,
    not a silent under-declaration of a declared prior). The live 2024 calculate
    succeeds and all three opening-stock casillas resolve to zero. This documents
    the status quo and fails loudly if it drifts. (xfail/skip-free per the testing
    mandate.)
    """
    result = _calculate_m200(secure_objects)

    values = result.revision.casilla_values
    assert Decimal(values[_BIN_PENDIENTE_INICIO]) == Decimal("0"), (
        f"M200 2024 casilla 00670 with no prior 00671 must resolve zero; got {values[_BIN_PENDIENTE_INICIO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_NO_CUMPLIDO]) == Decimal("0"), (
        f"M200 2024 casilla 01494 with no prior 01498 must resolve zero; got {values[_SALDO_INICIAL_NO_CUMPLIDO]}"
    )
    assert Decimal(values[_SALDO_INICIAL_CUMPLIDO]) == Decimal("0"), (
        f"M200 2024 casilla 01495 with no prior 01499 must resolve zero; got {values[_SALDO_INICIAL_CUMPLIDO]}"
    )
    assert result.source_diagnostics == ()
