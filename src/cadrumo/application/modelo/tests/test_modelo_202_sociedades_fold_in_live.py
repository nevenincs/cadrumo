"""Sociedades M202 cross-period folds fire on the LIVE calculate path.

The Impuesto sobre Sociedades fraccionado (Modelo 202) carries two cross-period
values that the operator must not re-key. Both are proven here end-to-end on the
LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`),
not the direct-resolver path the existing continuity tests exercise:

* **M202 cumulative self-carry** (``previous_period``). Casilla 30 ("Pagos
  fraccionados de periodos anteriores") is bound by
  ``modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores``
  (``source = relation_prefill``), fed by the two self-pago relations
  ``modelo-202-2025-y-siguientes-rel-self-pagos-2p`` (period 2P, sums the 1P
  pago) and ``-rel-self-pagos-3p`` (period 3P, sums 1P + 2P), both reading
  ``source_casilla_id = '34'`` (the instalment ingresado). So a 2P calculate folds
  the prior 1P pago and a 3P calculate folds 1P + 2P.
* **M202 <- M200 cuota-base ejercicio anterior** (``cross_model_output``).
  Casilla 01 ("Importe de la base") is bound by
  ``modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior``
  (``source = relation_prefill``, ``selector source_modelo = '200',
  source_casilla_id = 'DP200014B:00592'``), fed by the cuota-base relations whose
  ``filing_year_delta`` selects the prior M200 cuota líquida. A 2P calculate
  folds the immediately prior M200 (filing_year_delta = -1) cuota líquida.

Each source period is seeded as a filed observation through the production
observation-persistence API
(:meth:`CalculationObservationRepository.save_observation`, the same write path
the local-file carry flow uses), stamped with the non-official ``app_filing``
source_kind, over a real encrypted-SQLite object store
(:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider` via
:func:`isolated_runtime_profile`). M202 is a sociedad surface: the live calculate
needs a legal-entity profile carrying ``taxpayer_type.entity_type =
legal_entity``, ``legal_entity_form = sl`` and ``incn_prior_12_months`` so the
``incn-prior-12-months`` profile binding resolves and the aggregate cross-store
agreement holds. No mocks, stubs, skips, or xfail.

Non-tautological: the seeded per-period c34 values are DISTINCT non-equal known
Decimals, so an off-by-period fold, a single-period copy, a silent blank, or a
coincidental sum cannot satisfy the cumulative assertion; the prior M200 cuota
líquida is a manual input no formula under test produces. The expected casilla
values derive from the seeded observations via the declared aggregation ops
(``sum`` / cross-year copy), never by re-evaluating any registry formula. A
change in the relation's ``source_casilla_id``, ``source_periods``, or
``aggregation`` op would red the assertion.

----------------------------------------------------------------------------
Coverage map for the sociedades fold surface
----------------------------------------------------------------------------
* **M202 cumulative self-carry (casilla 30)** — proven LIVE here.
* **M202 <- M200 cuota-base (casilla 01)** — proven LIVE here.
* **M200 self BIN stock carry (00670) / dotaciones-deterioro (01494/01495)** —
  already driven through the REAL M200 engine by the direct-resolver continuity
  tests
  ``cadrumo.application.calculations.tests.test_modelo_200_bin_carry_forward_continuity``
  and ``...test_modelo_200_dotaciones_deterioro_carry_continuity``. The live
  operator path additionally requires the full six-binding legal-entity profile
  scaffold (``new-entity-flag``, ``incn-prior-12-months``,
  ``tributacion-estado-porcentaje``, ``sal-reserva-especial-dotada``,
  ``sal-capital-social``, ``legal-entity-form``) plus a zero-default for every
  other bound casilla; the carried value (00670) is reachable but adds no
  fold-wiring assurance beyond the direct-path proof, so it is cross-referenced
  rather than duplicated.
* **M200 <- M202 pagos fraccionados anuales (casilla DP200014B:00611)** —
  proven LIVE here (see
  :func:`test_m200_0a_folds_m202_pagos_fraccionados_into_cuota_diferencial_live`).
  The fold reaches casilla ``DP200014B:00611`` ("cuota diferencial") via the
  formula ``modelo-200-cuota-diferencial``:
  ``00611 = subtract(DP200014B:00599, relation["modelo-200-2024-rel-202-pagos-fraccionados"])``.
  The relation resolves the sum of the three M202 c34 instalments (1P + 2P + 3P)
  through the enrolled :class:`RelationPrefillSourceResolver`; ``00611`` is a
  *computed* casilla whose formula consumes the resolved relation value directly
  — not via a *bound* casilla. With all manual M200 inputs at zero (``00599 =
  0``), the formula produces ``00611 = 0 - sum(M202 1P+2P+3P c34)`` and the
  three DISTINCT seeded values make the subtraction unmistakable.
* **M390 <- M303 iva** — already proven LIVE by
  ``test_modelo_390_303_fold_in_live``; not duplicated here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...tests import register_wizard_catalogue

__all__ = ["register_wizard_catalogue"]

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
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from .. import (
    BucketAggregationCalculationResult,
    ModeloRequiredBindingsMissingError,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "7a432b52-bcc2-4e8c-a150-93a0f33812f3"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M202 = "202"
_M200 = "200"
_FILING_YEAR = 2025
_PRIOR_M200_YEAR = 2024  # filing_year_delta = -1 from the 2025 M202 ejercicio

# M202 source_casilla_id 34 is the instalment ingresado that the self-pago relations
# read; M200 source_casilla_id DP200014B:00592 is the prior cuota líquida the
# cuota-base relation reads.
_M202_PAGO_OUTPUT: CasillaId = validated_casilla_id("34", surface="_M202_PAGO_OUTPUT")
_M202_PAGO_OUTPUT_40_2: CasillaId = validated_casilla_id(
    "03",
    surface="_M202_PAGO_OUTPUT_40_2",
)  # modalidad cuota (art. 40.2); folds alongside casilla 34
_M200_CUOTA_LIQUIDA: CasillaId = validated_casilla_id("DP200014B:00592", surface="_M200_CUOTA_LIQUIDA")
_M202_CUOTA_BASE_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M202_PAGOS_ANTERIORES_BINDING = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"

# Bound casillas on the M202/2025 revision under test.
_CASILLA_BASE: CasillaId = validated_casilla_id(
    "01",
    surface="_CASILLA_BASE",
)  # bound by cuota-base-ejercicio-anterior (M202 <- M200)
_CASILLA_PAGOS_ANTERIORES: CasillaId = validated_casilla_id(
    "30",
    surface="_CASILLA_PAGOS_ANTERIORES",
)  # bound by pagos-fraccionados-anteriores (self-carry)

# DISTINCT non-equal known per-period pago ingresado (M202 c34). Distinct values
# make the cumulative fold unmistakable: a single-period copy or off-by-period
# fold cannot reproduce the multi-period sum.
_M202_C34_BY_PERIOD: dict[str, Decimal] = {
    "1P": Decimal("1234.00"),
    "2P": Decimal("5678.50"),
}
# The prior M200 cuota líquida the 2P cuota-base relation folds (a manual input;
# distinct from every pago value so a cross-wired fold would surface).
_M200_PRIOR_CUOTA = Decimal("48000.00")

_RELATION_PREFILL_SOURCE = "relation_prefill"
#: The M200 relations that fold the same-year M202 pagos fraccionados.
_M202_PAGO_RELATIONS = frozenset(
    {
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
    },
)
#: The M200 cross-year self-carries, absent for this pagos-only persona.
_M200_SELF_CARRY_RELATIONS = frozenset(
    {
        "modelo-200-2024-rel-self-bin-pendiente-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-no-cumplido-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-cumplido-anterior",
    },
)

# ── M200 ← M202 pagos fold proof ────────────────────────────────────────────

# Distinct bucket so the M200 proof does not share observation state with the
# M202 self-carry / cuota-base scenarios above.
_BUCKET_ID_M200 = "8ebc9e26-9e28-48aa-946f-f34d71807ad3"

# The *computed* casilla that the formula ``modelo-200-cuota-diferencial``
# targets: 00611 = subtract(DP200014B:00599, relation[pagos-fraccionados]).
# ``DP200014B`` is the xsd-group prefix for the Apartado B liquidación block.
_CASILLA_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_CASILLA_CUOTA_DIFERENCIAL",
)

# DISTINCT non-equal known c34 values for each of the three M202 instalments
# (1P/2P/3P). Distinct values make the fold unmistakable: a single-period
# copy, an off-by-period fold, or a silent blank cannot reproduce the sum.
# The M200 filing year (2025) sources the same-year M202 instalments
# (filing_year_delta = 0 per the relation declaration).
_M202_C34_PAGOS: dict[str, Decimal] = {
    "1P": Decimal("3100.00"),
    "2P": Decimal("4750.50"),
    "3P": Decimal("2200.25"),
}


@pytest.fixture
def secure_objects_m200(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository (M200 fold proof)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID_M200) as profile:
        yield profile.repository


def _seed_m200_sociedad_profile() -> None:
    """Seed a legal-entity ``UserProfileRecord`` covering M200's six profile bindings.

    M200/2024 declares six ``source = "profile"`` bindings. Four are consumed
    by the cuota chain: ``legal-entity-form``, ``new-entity-flag``,
    ``incn-prior-12-months``, ``tributacion-estado-porcentaje``. Two are
    Sociedad Laboral specific: ``sal-reserva-especial-dotada`` and
    ``sal-capital-social``. For a standard SL (not a SAL), the SAL facts are
    absent / zero, which the formulas treat as no dotacion. The profile resolver
    fills all six from the persisted record via
    :class:`cadrumo.application.modelo._profile_binding.ModeloProfileBindingResolver`;
    no profile binding is hand-fed through the caller channel. ``display_name``
    matches the ``isolated_runtime_profile`` manifest label.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID_M200,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B87654323"),
            UserProfileFact(path="identity.legal_name", value="M200 Fold Sociedad Limitada"),
            UserProfileFact(path="activities.description", value="desarrollo de software"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _seed_m202_pago_for_m200(*, period: str, value: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Persist one filed M202/2025 instalment (c34) for the M200 pagos fold proof."""
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
                        _M202_PAGO_OUTPUT: value,
                        _M202_PAGO_OUTPUT_40_2: Decimal("0"),
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _calculate_m200(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live M200/2025/0A calculate over the seeded M200 bucket.

    All M200 bindings are either ``profile`` (filled by the profile resolver
    from the seeded sociedad record) or ``relation_prefill`` (filled by
    :class:`RelationPrefillSourceResolver` from seeded M202 observations or
    defaulted to zero). No manual M200 casilla inputs are supplied through the
    caller channel, so ``DP200014B:00599`` (cuota a ingresar) resolves to zero
    and ``DP200014B:00611`` (cuota diferencial) == 0 − sum(M202 pagos).
    """
    _seed_m200_sociedad_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID_M200, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(_M200, filing_year=_FILING_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID_M200,
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


def _seed_sociedad_profile() -> None:
    """Seed a legal-entity ``UserProfileRecord`` covering M202's profile binding.

    M202/2025 declares one ``source = "profile"`` binding,
    ``modelo-202-2025-y-siguientes-incn-prior-12-months`` (selector
    ``profile_model = taxpayer, field = incn_prior_12_months``). The live source
    mesh's profile resolver fills it from the persisted record, so the value is
    NOT hand-fed through the caller channel. ``entity_type`` and
    ``legal_entity_form`` describe the sociedad routing axis the corporate-tax
    facts hang off; ``display_name`` matches the ``isolated_runtime_profile``
    manifest label (``"Test runtime profile"``) so the loaded
    :class:`CommittedProfileView` passes its cross-store label-agreement validator.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="M202 Fold Sociedad Limitada"),
            UserProfileFact(path="activities.description", value="servicios empresariales"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _seed_m202_pago(*, period: str, value: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Persist one filed M202/2025 instalment carrying the c34 pago for ``period``."""
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
                        _M202_PAGO_OUTPUT: value,
                        _M202_PAGO_OUTPUT_40_2: Decimal("0"),
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _seed_m200_prior_cuota(*, cuota: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Persist the prior-year M200 cuota líquida (DP200014B:00592) the 2P base folds."""
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_M200,
                filing_year=_PRIOR_M200_YEAR,
                period="0A",
                observations=registry_grounded_observations(
                    modelo=_M200,
                    filing_year=_PRIOR_M200_YEAR,
                    period="0A",
                    casilla_values={_M200_CUOTA_LIQUIDA: cuota},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _calculate_m202(secure_objects: SecureObjectRepository, *, period: str) -> BucketAggregationCalculationResult:
    """Run the live M202/2025/<period> calculate over the seeded bucket.

    The two ``relation_prefill`` bindings (casilla 01 cuota-base, casilla 30
    pagos-anteriores) are deliberately left UNSET so the enrolled relation
    resolver folds them from the seeded observation store; the one ``profile``
    binding resolves from the seeded sociedad record. No ``binding_values`` are
    supplied so the live mesh is the sole value source.
    """
    _seed_sociedad_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(_M202, filing_year=_FILING_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M202,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
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


def test_m202_2p_folds_prior_1p_pago_and_m200_cuota_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: M202 2P folds the prior 1P pago (casilla 30) and prior M200 cuota (casilla 01).

    With a 1P M202 instalment filed (c34) and a prior-year M200 cuota líquida
    recorded, a live calculate of the 2P instalment draws both relation chains
    through the enrolled ``RelationPrefillSourceResolver``:

    - casilla 30 (pagos-fraccionados-anteriores) == the 1P pago (sum over the one
      prior period the 2P self-pago relation declares).
    - casilla 01 (base) == the immediately prior M200 cuota líquida
      (filing_year_delta = -1 cross-model copy).
    """
    obs_repo = CalculationObservationRepository()
    _seed_m202_pago(period="1P", value=_M202_C34_BY_PERIOD["1P"], obs_repo=obs_repo)
    _seed_m200_prior_cuota(cuota=_M200_PRIOR_CUOTA, obs_repo=obs_repo)
    # Sanity: the prior pago and the prior cuota are distinct strictly-positive
    # values, so a cross-wired fold (cuota into pagos, or vice versa) would red
    # the per-casilla assertions below.
    assert _M202_C34_BY_PERIOD["1P"] != _M200_PRIOR_CUOTA
    assert _M202_C34_BY_PERIOD["1P"] > Decimal("0")
    assert Decimal("0") < _M200_PRIOR_CUOTA

    result = _calculate_m202(secure_objects, period="2P")

    values = result.revision.casilla_values
    assert Decimal(values[_CASILLA_PAGOS_ANTERIORES]) == _M202_C34_BY_PERIOD["1P"], (
        f"M202 2P casilla 30 must fold the prior 1P pago ({_M202_C34_BY_PERIOD['1P']}); "
        f"got {values[_CASILLA_PAGOS_ANTERIORES]}"
    )
    assert Decimal(values[_CASILLA_BASE]) == _M200_PRIOR_CUOTA, (
        f"M202 2P casilla 01 must fold the prior M200 cuota líquida ({_M200_PRIOR_CUOTA}); got {values[_CASILLA_BASE]}"
    )

    # Both folds run through claimed sources: no relation_prefill diagnostic and
    # a clean resolution overall (the one profile binding resolves silently).
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    assert result.source_diagnostics == (), (
        f"M202 source_diagnostics must be clean for the sociedad fold persona; got {result.source_diagnostics}"
    )


def test_m202_3p_cumulates_prior_1p_and_2p_pagos_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: M202 3P folds the cumulative 1P + 2P pagos into casilla 30.

    With both the 1P and 2P M202 instalments filed (distinct c34 pagos), a live
    calculate of the 3P instalment draws the 3P self-pago relation
    (``source_periods = [1P, 2P]``, ``sum``) and casilla 30 equals the sum of the
    two prior pagos — the cumulative carry the M202 3P modalidad requires. The
    distinct per-period values make the two-term fold unmistakable: a
    single-period copy or off-by-period fold cannot reproduce the sum.
    """
    obs_repo = CalculationObservationRepository()
    _seed_m202_pago(period="1P", value=_M202_C34_BY_PERIOD["1P"], obs_repo=obs_repo)
    _seed_m202_pago(period="2P", value=_M202_C34_BY_PERIOD["2P"], obs_repo=obs_repo)
    _seed_m200_prior_cuota(cuota=_M200_PRIOR_CUOTA, obs_repo=obs_repo)
    expected_cumulative = _M202_C34_BY_PERIOD["1P"] + _M202_C34_BY_PERIOD["2P"]
    # Sanity: the two seeded pagos are distinct so a single-period copy fails.
    assert _M202_C34_BY_PERIOD["1P"] != _M202_C34_BY_PERIOD["2P"]
    assert expected_cumulative > _M202_C34_BY_PERIOD["1P"]

    result = _calculate_m202(secure_objects, period="3P")

    values = result.revision.casilla_values
    assert Decimal(values[_CASILLA_PAGOS_ANTERIORES]) == expected_cumulative, (
        f"M202 3P casilla 30 must cumulate the prior 1P + 2P pagos (sum {expected_cumulative}); "
        f"got {values[_CASILLA_PAGOS_ANTERIORES]}"
    )
    # casilla 01 still folds the prior M200 cuota (filing_year_delta = -1 holds for 3P too).
    assert Decimal(values[_CASILLA_BASE]) == _M200_PRIOR_CUOTA, (
        f"M202 3P casilla 01 must fold the prior M200 cuota líquida ({_M200_PRIOR_CUOTA}); got {values[_CASILLA_BASE]}"
    )
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    assert result.source_diagnostics == ()


def test_m202_2p_no_prior_filing_refuses_zero_draft_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """A live M202 calculate with missing prior observations must not save zero carries."""
    _seed_sociedad_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(_M202, filing_year=_FILING_YEAR, period="2P")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M202,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "2P"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )

    with pytest.raises(ModeloRequiredBindingsMissingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values={},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )

    context = exc_info.value.context
    assert context is not None
    missing_bindings = context["missing_bindings"]
    assert isinstance(missing_bindings, tuple)
    assert set(missing_bindings) == {
        _M202_CUOTA_BASE_BINDING,
        _M202_PAGOS_ANTERIORES_BINDING,
    }
    assert cr_repo.load().revisions == {}
    stored_work_unit = wu_repo.load().get(work_unit.work_unit_id)
    assert stored_work_unit is not None
    assert stored_work_unit.current_calculation_revision_id is None


# Cuota-a-ingresar leg of the cuota-diferencial subtraction: with no manual M200
# inputs supplied it resolves to zero, so 00611 == 00599 - sum(M202 pagos). The
# assertion below reads 00599 from the result rather than assuming it, so the
# fold-wiring invariant holds regardless of the minuend's resolved value.
_CASILLA_CUOTA_A_INGRESAR: CasillaId = validated_casilla_id(
    "DP200014B:00599",
    surface="_CASILLA_CUOTA_A_INGRESAR",
)


def test_m200_0a_folds_m202_pagos_fraccionados_into_cuota_diferencial_live(
    secure_objects_m200: SecureObjectRepository,
) -> None:
    """E2E: the three filed M202 instalments fold into M200 casilla DP200014B:00611.

    Reconciles a prior dead-wiring false-alarm: the M200 <- M202 pagos fold is NOT dead — it
    reaches the *computed* casilla ``DP200014B:00611`` ("cuota diferencial") via
    the formula ``00611 = subtract(DP200014B:00599, relation[
    modelo-200-2024-rel-202-pagos-fraccionados])`` through the enrolled
    ``RelationPrefillSourceResolver`` (source_modelo 202, output 34, periods
    1P/2P/3P, sum). It does NOT flow through the manual ``is_pagos_fraccionados``
    casillas 00601/00447, which an earlier test exercised by mistake. The three DISTINCT seeded
    pagos make the fold unmistakable: the cuota-diferencial subtraction must drop
    by exactly the seeded sum.
    """
    obs_repo = CalculationObservationRepository()
    for period, value in _M202_C34_PAGOS.items():
        _seed_m202_pago_for_m200(period=period, value=value, obs_repo=obs_repo)
    expected_pagos_sum = sum(_M202_C34_PAGOS.values(), Decimal("0"))
    # Sanity: the three seeded pagos are mutually distinct and strictly positive,
    # so a single-period copy, an off-by-period fold, or a silent blank cannot
    # reproduce the summed subtraction.
    assert len(set(_M202_C34_PAGOS.values())) == 3
    assert expected_pagos_sum > Decimal("0")

    result = _calculate_m200(secure_objects_m200)

    values = result.revision.casilla_values
    cuota_a_ingresar = Decimal(values[_CASILLA_CUOTA_A_INGRESAR])
    cuota_diferencial = Decimal(values[_CASILLA_CUOTA_DIFERENCIAL])
    # Fold-wiring invariant: cuota diferencial == cuota a ingresar - sum(M202 pagos).
    assert cuota_diferencial == cuota_a_ingresar - expected_pagos_sum, (
        f"M200 00611 must fold the three M202 pagos (sum {expected_pagos_sum}) out of "
        f"00599 ({cuota_a_ingresar}); got 00611={cuota_diferencial}"
    )
    # The pagos relation runs through a claimed source — no advisory names IT.
    assert not any(
        diag.source_kind == _RELATION_PREFILL_SOURCE and diag.relation_id in _M202_PAGO_RELATIONS
        for diag in result.source_diagnostics
    ), f"the M202 pagos fold must resolve cleanly; got {result.source_diagnostics}"
    # This persona seeds the M202 pagos and nothing else, so it has no prior-year
    # M200 closing stock and declares no activity start. The three cross-year
    # self-carries therefore declare a zero opening stock that nothing can confirm
    # the filer was entitled to, and each is advised. That is correct for this
    # persona and orthogonal to the pagos fold under test; the sibling M200 module
    # covers the advisory's own behaviour and its first-ejercicio silence.
    advised = {diag.relation_id for diag in result.source_diagnostics if diag.source_kind == _RELATION_PREFILL_SOURCE}
    assert advised == _M200_SELF_CARRY_RELATIONS, (
        f"only the three absent self-carries may be advised here; got {advised}"
    )
