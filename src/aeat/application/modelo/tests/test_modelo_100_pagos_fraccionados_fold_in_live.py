"""M100 annual 0604 folds in M130 1T-4T pagos fraccionados (LIVE path).

The annual IRPF declaration (Modelo 100) casilla ``0604`` ("Pagos fraccionados
ingresados") is a *computed* casilla whose registry formula
``renta-2024-pagos-fraccionados-ingresados`` sums two cross-model relations:

* ``renta-2024-rel-130-pagos-fraccionados`` — ``source_modelo='130'``,
  ``source_casilla_id='19'``, ``source_periods=('1T','2T','3T','4T')``.
* ``renta-2024-rel-131-pagos-fraccionados`` — ``source_modelo='131'``,
  ``source_casilla_id='15'``, same four periods.

Each relation materialises into its declared ``target_binding``
(``renta-2024-modelo-130-pagos-fraccionados`` / ``-131-``), whose registry
binding declares ``source='relation_prefill'`` with a ``sum`` aggregation over
``source_casilla_id``. :class:`RelationPrefillSourceResolver` is enrolled in the
live source mesh, making the relation canonical for cross-modelo fold-in. This
module proves the wiring works end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
four prior M130 quarterly filings fold into the annual 0604.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real relation resolver, real source
mesh — no mocks, stubs, skips, or xfail).

The aggregation assertion (``0604 == sum(four seeded M130 c19) + M131 c15``) is a
fold-WIRING invariant, not a tautology: the four seeded c19 values are DISTINCT
non-equal known Decimals, so the assertion can only hold if the resolver folds
those four specific prior filings into the annual casilla. It does not reproduce
any registry formula under test — there is no IRPF formula being hand-recomputed;
the seeded c19 inputs are summed by the declared ``sum`` aggregation and the test
proves the cross-period fold wires the prior filings through to 0604.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-m100-pagos-fold"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024

# Four DISTINCT non-equal known quarterly pagos fraccionados (M130 casilla 19,
# "Resultado a ingresar"). Distinct values make the annual fold unmistakable: an
# off-by-one-quarter or coincidental sum cannot satisfy the assertion. These are
# the values a filed M130 would persist for each quarter's c19.
_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("100.00"),
    "2T": Decimal("250.50"),
    "3T": Decimal("75.25"),
    "4T": Decimal("300.00"),
}
_EXPECTED_M130_TOTAL = Decimal("100.00") + Decimal("250.50") + Decimal("75.25") + Decimal("300.00")  # 725.75
_M130_SOURCE_CASILLA_ID: CasillaId = validated_casilla_id("19", surface="_M130_SOURCE_CASILLA_ID")
_M131_SOURCE_CASILLA_ID: CasillaId = validated_casilla_id("15", surface="_M131_SOURCE_CASILLA_ID")
_M100_ANNUAL_PERIOD = "0A"
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)
_RELATION_PREFILL_SOURCE = "relation_prefill"
_M130_PAGOS_RELATION_ID = "renta-2024-rel-130-pagos-fraccionados"

# The M100 0604 formula references BOTH the M130 and M131 pagos-fraccionados
# relations directly (``sum(relation 130, relation 131)``); unresolved prior
# filings now leave the computed casilla blank and surface source diagnostics
# instead of zero-contributing. So the M131 leg must also be present for 0604 to
# compute.
# This persona has no estimación-objetiva (M131) activity, so its four c15
# quarters are a true zero — folded as 0 into 0604, leaving 0604 == the M130 sum.
_M131_C15_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_m130_quarters(
    *,
    obs_repo: CalculationObservationRepository,
    periods: tuple[str, ...],
) -> Decimal:
    """Persist one M130/2024 filing observation per requested period carrying c19.

    Persisted through the production observation-persistence API
    (:meth:`CalculationObservationRepository.save_observation`) — the same write
    path the local-file carry flow uses — stamped with the non-official
    ``app_filing`` source_kind. Returns the summed c19 over the seeded periods.
    """
    total = Decimal("0")
    for period in periods:
        value = _M130_C19_BY_PERIOD[period]
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="130",
                filing_year=_YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo="130",
                    filing_year=_YEAR,
                    period=period,
                    casilla_values={_M130_SOURCE_CASILLA_ID: value},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
        total += value
    return total


def _seed_m131_zero_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist the four M131/2024 c15 quarters as a true zero (no módulos activity).

    The 0604 formula sums both the M130 and M131 pagos relations directly, so the
    M131 leg must resolve for the engine not to raise. This persona files no
    estimación-objetiva, so its four c15 quarters are zero and fold as 0.
    """
    for period in _M131_C15_QUARTERS:
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="131",
                filing_year=_YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo="131",
                    filing_year=_YEAR,
                    period=period,
                    casilla_values={_M131_SOURCE_CASILLA_ID: Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )


def _seed_prior_year_m100_zero_carry(secure_objects: SecureObjectRepository) -> None:
    CalculationObservationRepository(objects=secure_objects).save_observation(
        RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period=_M100_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_M100_ANNUAL_PERIOD,
                casilla_values={_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0")},
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
    Mirrors ``test_modelo_100_multiyear_renta_enrollment._seed_taxpayer_unit_profile``.
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_minimos_aggregate_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.gastos_guarderia_reales_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_menores_3_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=Decimal("0")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(record)


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced.

    The annual M100 revision binds many casillas (the Anexo-C base-liquidable
    carry, ...) whose values an empty bucket does not supply; the engine refuses
    the consuming casilla before reaching 0604. These are supplied as zero
    through the caller channel (the pure-pagos-fold persona declares no other
    prior activity), leaving the two ``relation_prefill`` pagos bindings UNSET so
    the enrolled relation resolver folds them from the seeded M130 store on the
    live path. Mirrors the non-profile zero-default in
    ``test_modelo_100_multiyear_renta_enrollment._calculate_100``.
    """
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_income_aggregation",
            "ledger_renta_expense_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        )
    }


def _calculate_m100_annual(secure_objects: SecureObjectRepository):
    """Run the live M100/2024/0A calculate over the seeded bucket.

    Seeds the taxpayer profile and zero-defaults non-profile/non-relation
    bindings so the engine reaches casilla 0604; the two pagos-fraccionados
    ``relation_prefill`` bindings are deliberately left UNSET so the enrolled
    relation resolver folds them from the seeded M130 observation store.
    """
    _seed_taxpayer_unit_profile(secure_objects)
    _seed_prior_year_m100_zero_carry(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values=_non_relation_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_m100_0604_folds_in_four_m130_quarters_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """E2E: the four filed M130 quarters fold into the annual M100 0604.

    With four M130/2024 quarters recorded as filed observations (each carrying a
    DISTINCT c19) and the four M131 c15 quarters recorded as a true zero (no
    módulos activity), a live calculate of the M100/2024 annual draws both
    pagos-fraccionados relations through the enrolled
    ``RelationPrefillSourceResolver`` and 0604 equals the summed four M130
    quarters (+ M131 c15, which folds as zero).
    """
    obs_repo = CalculationObservationRepository()
    seeded_total = _seed_m130_quarters(obs_repo=obs_repo, periods=("1T", "2T", "3T", "4T"))
    _seed_m131_zero_quarters(obs_repo=obs_repo)
    # Sanity: the four seeded values are distinct and sum to a strictly-positive
    # known total, so a silent blank (0) or a single-quarter copy would fail below.
    assert seeded_total == _EXPECTED_M130_TOTAL
    assert len(set(_M130_C19_BY_PERIOD.values())) == 4
    assert seeded_total > Decimal("0")

    result = _calculate_m100_annual(secure_objects)

    casilla_0604 = Decimal(result.revision.casilla_values[_M100_PAGOS_CASILLA])
    # M131 c15 folds to zero; 0604 == sum(M130 c19) over the four DISTINCT quarters.
    assert casilla_0604 == _EXPECTED_M130_TOTAL, (
        f"M100 0604 must fold in the four M130 quarters (sum {_EXPECTED_M130_TOTAL}); got {casilla_0604}"
    )

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
    # The whole live resolution is clean — no source diagnostics at all for this
    # pure-pagos-fold persona (no unrouted declarable observation).
    assert result.source_diagnostics == (), (
        f"source_diagnostics must be clean for the pagos-fold persona; got {result.source_diagnostics}"
    )


def test_m100_partial_prior_m130_filings_leave_0604_unresolved_with_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    """A partial prior M130 set leaves 0604 blank and names the missing relation."""
    obs_repo = CalculationObservationRepository()
    _seed_m130_quarters(obs_repo=obs_repo, periods=("1T", "2T"))
    _seed_m131_zero_quarters(obs_repo=obs_repo)

    result = _calculate_m100_annual(secure_objects)

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics


def test_m100_no_prior_m130_filing_leaves_0604_unresolved_with_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    """An absent prior M130 set leaves 0604 blank and names the missing relation."""
    result = _calculate_m100_annual(secure_objects)

    assert _M100_PAGOS_CASILLA not in result.revision.casilla_values
    assert any(
        diagnostic.source_kind == _RELATION_PREFILL_SOURCE
        and diagnostic.relation_id == _M130_PAGOS_RELATION_ID
        and diagnostic.reason == "source_issue"
        for diagnostic in result.source_diagnostics
    ), result.source_diagnostics
