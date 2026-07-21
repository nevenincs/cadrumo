"""M390 annual carries the régimen simplificado cuota devengada from the 4T M303.

Estimación-objetiva (EO) autónomos under the IVA régimen simplificado settle the
régimen annually in the fourth-quarter Modelo 303: casilla 54
("RS - Total cuota resultante") holds the year's cuota devengada del régimen
simplificado. The official Modelo 390 surfaces that figure in the régimen
simplificado apartado as box 79 ("IVA devengado - Total cuota resultante",
AEAT Diseño de Registros 2025, campo 89 ``[79]``). Before this wiring the M390
modelled only the régimen general totals, so the simplificado cuota devengada
never reached the annual resumen.

The fold is the canonical annual_summary relation
``modelo-390-rel-303-cuota-devengada-simplificado`` whose ``target_binding``
``modelo-390-prev-303-cuota-devengada-simplificado`` (``source = relation_prefill``)
materialises the value onto the bound casilla
``iva.anual.reconciliacion.devengada-simplificado-303`` (box 79). Régimen
simplificado is declared only in the 4T autoliquidación (1T-3T are ingresos a
cuenta), so the relation sources the single 4T quarter and carries (``copy``) it
onto the 0A annual target — it does NOT sum across quarters like the régimen
general totals.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real enrolled relation resolver,
real source mesh — no mocks, stubs, skips, or xfail).

Non-tautological value parity:
- Casilla 54 is seeded with a DISTINCT value in every quarter, so a wrong
  aggregation (summing the four quarters, or carrying the wrong quarter) yields a
  number that fails the assertion. Only the 4T value carried by ``copy`` matches.
- The expected box-79 value is the seeded 4T casilla-54 observation, NOT a value
  re-derived from a registry formula.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, RelationPrefillSourceResolver
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39000000-0000-4000-8000-000000000391"
_T0 = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 20, 11, 0, tzinfo=UTC)
_YEAR = 2025
_TAX_ID = "12345678Z"

_M303_SIMPLIFICADO_CUOTA_DEVENGADA: CasillaId = validated_casilla_id("54", surface="M303 RS total cuota resultante")
_M390_DEVENGADA_SIMPLIFICADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.reconciliacion.devengada-simplificado-303",
    surface="M390 box 79 simplificado",
)

_RELATION_ID = "modelo-390-rel-303-cuota-devengada-simplificado"
_TARGET_BINDING_ID = "modelo-390-prev-303-cuota-devengada-simplificado"
_RELATION_PREFILL_SOURCE = "relation_prefill"

# DISTINCT per-quarter casilla-54 values. Régimen simplificado is realistically
# declared only in the 4T autoliquidación, but seeding every quarter with a
# distinct value proves the fold reads the 4T quarter and CARRIES it (copy),
# rather than summing the four quarters or carrying the wrong one.
_CUOTA_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("111.11"),
    "2T": Decimal("222.22"),
    "3T": Decimal("333.33"),
    "4T": Decimal("444.44"),
}
# Expected: the 4T value carried by copy. A sum would be 1111.10; a wrong quarter
# would be 111.11 / 222.22 / 333.33.
_EXPECTED_BOX_79 = _CUOTA_BY_PERIOD["4T"]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_m303_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist one M303/2025 simplificado filing per quarter carrying casilla 54.

    Written through the production observation-persistence API the local-file
    carry flow uses, stamped with the non-official ``app_filing`` source_kind.
    """
    for period, cuota in _CUOTA_BY_PERIOD.items():
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="303",
                filing_year=_YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=_YEAR,
                    period=period,
                    casilla_values={_M303_SIMPLIFICADO_CUOTA_DEVENGADA: cuota},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )


def _store_ready_profile(secure_objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="M390 simplificado fold test",
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _calculate_m390_annual(secure_objects: SecureObjectRepository):
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
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


def test_m390_carries_simplificado_cuota_devengada_from_4t_m303_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """The 4T M303 régimen-simplificado cuota devengada folds into M390 box 79.

    With four M303/2025 quarterly filings seeded (each carrying casilla 54 with a
    DISTINCT value), a live calculate of the M390/2025 annual draws the
    ``modelo-390-rel-303-cuota-devengada-simplificado`` relation through the
    enrolled :class:`RelationPrefillSourceResolver` and materialises the 4T value
    onto box 79. The asserted value is the seeded 4T observation, never a registry
    formula re-evaluation (non-tautological).
    """
    _store_ready_profile(secure_objects)
    obs_repo = CalculationObservationRepository()
    _seed_m303_quarters(obs_repo=obs_repo)

    # Sanity: the seeded values are distinct so a sum or wrong-quarter carry cannot
    # coincidentally satisfy the assertion.
    assert len(set(_CUOTA_BY_PERIOD.values())) == 4, "test requires DISTINCT per-quarter casilla-54 values"
    four_quarter_sum = sum(_CUOTA_BY_PERIOD.values(), Decimal("0"))
    assert four_quarter_sum != _EXPECTED_BOX_79, (
        "expected 4T value must differ from the four-quarter sum to discriminate copy from sum"
    )

    result = _calculate_m390_annual(secure_objects)
    casilla_values = result.revision.casilla_values

    assert Decimal(casilla_values[_M390_DEVENGADA_SIMPLIFICADO_CASILLA]) == _EXPECTED_BOX_79, (
        f"M390 box 79 must carry the 4T M303 régimen-simplificado cuota devengada (casilla 54)={_EXPECTED_BOX_79!r}; "
        f"got {casilla_values[_M390_DEVENGADA_SIMPLIFICADO_CASILLA]!r}"
    )

    # The relation_prefill source is CLAIMED (resolver enrolled): the simplificado
    # relation resolved, so no unhandled-source advisory names it.
    relation_prefill_diags = tuple(
        diag for diag in result.source_diagnostics if diag.source_kind == _RELATION_PREFILL_SOURCE
    )
    assert relation_prefill_diags == (), (
        f"relation_prefill must be a claimed source with no diagnostics; got {relation_prefill_diags}"
    )


def test_simplificado_relation_is_enrolled_not_dormant() -> None:
    """Structural: the simplificado relation is enrolled in the live mesh, not dormant.

    Three enrollment facts (no-dormant-source-resolvers): the relation exists on
    the M390 revision, its ``target_binding`` is a DECLARED ``relation_prefill``
    binding the engine materialises, and the live calculate mesh's
    :class:`RelationPrefillSourceResolver` owns the ``relation_prefill`` source
    kind — so the relation feeds the engine's relation channel rather than blanking
    silently.
    """
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_YEAR, period="0A")
    relations = {relation.id: relation for relation in snapshot.revision.relations}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    assert _RELATION_ID in relations, "simplificado relation must be declared on the M390 revision"
    relation = relations[_RELATION_ID]
    assert relation.target_binding == _TARGET_BINDING_ID
    assert relation.source_modelo == "303"
    assert relation.source_casilla_id == _M303_SIMPLIFICADO_CUOTA_DEVENGADA
    assert relation.source_periods == ("4T",), "régimen simplificado settles in the 4T autoliquidación only"

    target = bindings.get(_TARGET_BINDING_ID)
    assert target is not None, "the relation target_binding must be a declared binding (a materialised slot)"
    assert str(target.source) == _RELATION_PREFILL_SOURCE, (
        "a relation-targeted slot must declare source 'relation_prefill'"
    )

    assert BindingSourceKind.RELATION_PREFILL in RelationPrefillSourceResolver.owned_sources, (
        "the enrolled mesh resolver must own the relation_prefill source kind"
    )
