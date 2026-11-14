"""An earlier Modelo 200 return stored with bare PyG ids feeds the next year through the live calculate path.

Before the page-qualified rename, a stored Modelo 200 return named its net
turnover box by the bare number ``00255``; the registry now names it
``DP200007:00255``, and the next year's rate reads the preceding period's turnover
(LIS art. 29.1) through that id. Over a real encrypted profile store and the
operator's live calculate path, this suite proves that:

* a prior return written under an earlier authority generation, holding the bare
  id, gives exactly the calculation a prior holding the qualified id gives;
* a prior holding the box under both ids with different values is refused;
* a prior the current generation stamped is read as stored, so its bare id is
  not aliased and the turnover stays unread;
* the reads leave a verified revision's saved rendering byte-for-byte as stored.

Every year is read off the registry envelope; every figure is synthetic.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.calculations.errors import PriorFilingPageQualifiedConflictError
from ....application.calculations.observations_repository import ObservationEnvelopePayload
from ....application.calculations.prior_filing_page_qualified_reads import MODELO_200_PAGE_QUALIFIED_CASILLAS
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_missing_input import ModeloWorkMissingInputError
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.hashing import sha256_hex
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings_previous_filing import (
    PreviousFilingProvider,
    previous_filing_binding_source_casilla_ids,
)
from ....domain.calculations.registry.errors import RegistryError
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_calculation_action_ports, build_work_lifecycle_ports
from .observation_seeding_support import save_preceding_m200_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "3f7a9c2e-6b1d-4e8f-a5c3-9d0e1f2a3b4c"
_MODELO = "200"
_TURNOVER_BARE: CasillaId = validated_casilla_id("00255", surface="_TURNOVER_BARE")
_TURNOVER: CasillaId = MODELO_200_PAGE_QUALIFIED_CASILLAS[_TURNOVER_BARE]
_PRIOR_TURNOVER = Decimal("1800000")
_PRECEDING_TURNOVER_CARRY = "modelo-200-incn-periodo-impositivo-anterior"
#: A generation digest no published authority holds: a row an earlier build wrote.
_EARLIER_GENERATION = sha256_hex(b"an authority generation published before the page-qualified rename")

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


@cache
def _clock() -> datetime:
    return datetime(filing_year_envelope().horizon, 3, 10, 10, 0, tzinfo=UTC)


def _turnover_reading_years() -> tuple[int, ...]:
    """Every envelope year whose Modelo 200 rate reads the preceding period's turnover box."""
    operation = published_authority_operation()
    years: list[int] = []
    for year in sorted(operation.supported_filing_years().years):
        try:
            snapshot = operation.snapshot(
                _MODELO, filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except RegistryError:
            continue
        if any(
            isinstance(binding.provider, PreviousFilingProvider)
            and _TURNOVER in previous_filing_binding_source_casilla_ids(binding)
            for binding in snapshot.revision.bindings
        ):
            years.append(year)
    assert years
    return tuple(years)


def _seed_sociedad_profile() -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="B00015016"),
                UserProfileFact(path="identity.legal_name", value="Test Runtime Profile SL"),
                UserProfileFact(path="activities.description", value="software consultancy"),
                UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            ),
            persona_id="sociedad-limitada",
        ),
        created_at=_clock(),
        updated_at=_clock(),
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


class _Profile:
    """One seeded sociedad profile with a Modelo 200 work unit per turnover-reading year."""

    def __init__(self) -> None:
        _seed_sociedad_profile()
        self.observations = CalculationObservationRepository()
        self.work_units: dict[int, str] = {}
        with bundled_indexed_authority().operation() as operation:
            for year in _turnover_reading_years():
                snapshot = operation.snapshot(
                    _MODELO, filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
                )
                self.work_units[year] = create_work_unit(
                    bucket_id=_BUCKET_ID,
                    modelo=_MODELO,
                    filing_year=year,
                    period=Period.from_year_and_code(year, "0A"),
                    revision_id=snapshot.revision.id,
                    ports=build_work_lifecycle_ports(bucket_id=_BUCKET_ID),
                    operation=operation,
                    clock=_clock(),
                ).work_unit_id

    def calculate(self, year: int) -> BucketAggregationCalculationResult:
        with bundled_indexed_authority().operation() as operation:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                self.work_units[year],
                ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
                binding_values={},
                clock=_clock(),
            )

    def qualified_prior(self, year: int) -> ObservationEnvelopePayload:
        """Store the preceding return through the one write door and return it as stored."""
        save_preceding_m200_turnover(
            self.observations, filing_year=year, turnover=_PRIOR_TURNOVER, captured_at=_clock()
        )
        stored = self.observations.load_observation(_MODELO, Period.from_year_and_code(year - 1, "0A"))
        assert stored is not None
        return stored

    def replace_prior(
        self,
        stored: ObservationEnvelopePayload,
        *,
        generation: str | None,
        box: Callable[[CasillaId], tuple[tuple[CasillaId, Decimal], ...]],
    ) -> None:
        """Store ``stored`` again as another build wrote it: each turnover box rewritten by ``box``."""
        observations = []
        for item in stored.observation.observations:
            if item.casilla_id != _TURNOVER:
                observations.append(item)
                continue
            observations.extend(
                item.model_copy(update={"casilla_id": key, "value": value}) for key, value in box(item.casilla_id)
            )
        legacy = ObservationEnvelopePayload.model_validate(
            {
                **stored.model_dump(),
                "observation": stored.observation.model_copy(update={"observations": tuple(observations)}).model_dump(),
                "authority_generation": generation,
            },
        )
        self.observations.save(legacy)
        reread = self.observations.load(self.observations.envelope_identifier(legacy))
        assert reread is not None
        assert reread == legacy
        assert reread.authority_generation == generation


def _turnover_unresolved(result: BucketAggregationCalculationResult) -> bool:
    return any(diagnostic.binding_id == _PRECEDING_TURNOVER_CARRY for diagnostic in result.source_diagnostics)


def test_bare_prior_turnover_written_by_an_earlier_generation_feeds_the_rate_like_a_qualified_one(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = _Profile()
    for year in _turnover_reading_years():
        stored = profile.qualified_prior(year)
        assert stored.authority_generation == published_authority_operation().pin().logical_generation
        qualified = profile.calculate(year)
        assert not _turnover_unresolved(qualified)

        for generation in (_EARLIER_GENERATION, None):
            profile.replace_prior(stored, generation=generation, box=lambda _key: ((_TURNOVER_BARE, _PRIOR_TURNOVER),))
            legacy = profile.calculate(year)

            assert not _turnover_unresolved(legacy), (year, generation)
            assert dict(legacy.revision.casilla_values) == dict(qualified.revision.casilla_values), (year, generation)
            assert legacy.source_diagnostics == qualified.source_diagnostics


def test_prior_holding_the_turnover_under_both_ids_with_different_values_is_refused(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = _Profile()
    year = max(_turnover_reading_years())
    stored = profile.qualified_prior(year)
    profile.replace_prior(
        stored,
        generation=_EARLIER_GENERATION,
        box=lambda _key: ((_TURNOVER_BARE, _PRIOR_TURNOVER), (_TURNOVER, _PRIOR_TURNOVER + 1)),
    )

    with pytest.raises(PriorFilingPageQualifiedConflictError) as refusal:
        profile.calculate(year)

    context = refusal.value.context
    assert context is not None
    assert context["casilla_ids"] == _TURNOVER
    assert context["source_filing_year"] == year - 1
    assert str(_PRIOR_TURNOVER) not in str(context)


def test_identical_values_under_both_ids_read_once(secure_objects: SecureObjectRepository) -> None:
    profile = _Profile()
    year = max(_turnover_reading_years())
    stored = profile.qualified_prior(year)
    qualified = profile.calculate(year)
    profile.replace_prior(
        stored,
        generation=_EARLIER_GENERATION,
        box=lambda _key: ((_TURNOVER_BARE, _PRIOR_TURNOVER), (_TURNOVER, _PRIOR_TURNOVER)),
    )

    folded = profile.calculate(year)

    assert dict(folded.revision.casilla_values) == dict(qualified.revision.casilla_values)


def test_bare_id_in_a_row_the_current_generation_stamped_is_not_aliased(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = _Profile()
    year = max(_turnover_reading_years())
    stored = profile.qualified_prior(year)
    assert not _turnover_unresolved(profile.calculate(year))
    profile.replace_prior(
        stored,
        generation=published_authority_operation().pin().logical_generation,
        box=lambda _key: ((_TURNOVER_BARE, _PRIOR_TURNOVER),),
    )

    # The stored return exists but holds no qualified turnover box, so the carry
    # asks the operator for it rather than reading the bare id as that box.
    with pytest.raises(ModeloWorkMissingInputError) as refusal:
        profile.calculate(year)

    assert refusal.value.binding_id == _PRECEDING_TURNOVER_CARRY
    assert _TURNOVER in str(refusal.value)


def test_reads_leave_a_verified_revisions_saved_rendering_byte_for_byte(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = _Profile()
    year = max(_turnover_reading_years())
    stored = profile.qualified_prior(year)
    sealed_draft = profile.calculate(year).revision
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    catalogue = calculations.load()
    sealed = sealed_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _clock(),
            "verified_by": "operator",
        },
    )
    calculations.save(
        CalculationRevisionCatalogue(revisions={**catalogue.revisions, sealed.calculation_revision_id: sealed})
    )
    rendering = sealed.rendering_snapshot
    assert rendering is not None
    namespace = MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE

    def stored_body() -> tuple[bytes, str]:
        record = secure_objects.load(
            namespace.namespace,
            rendering.rendering_digest,
            expected_class=namespace.sensitivity,
            max_supported_version=namespace.schema_version,
        )
        assert record is not None
        return record.payload, record.revision_id

    before = stored_body()
    loaded_before = calculations.load().get(sealed.calculation_revision_id)
    profile.replace_prior(stored, generation=_EARLIER_GENERATION, box=lambda _key: ((_TURNOVER_BARE, _PRIOR_TURNOVER),))

    profile.calculate(year)

    assert stored_body() == before
    loaded_after = calculations.load().get(sealed.calculation_revision_id)
    assert loaded_after == loaded_before
    assert loaded_after is not None
    assert loaded_after.rendering_snapshot == rendering
    assert loaded_after.state is CalculationRevisionState.VERIFICADO_COMPLETO
