"""The borrador comparison reads the real encrypted draft store and a real saved Modelo 100 calculation.

Each case seeds a synthetic 2025 taxpayer, imports a draft into encrypted
custody and saves a calculation through the production calculation service,
then compares them through the registered read's own service. The draft's
work-withholding credit is held only to cross-check the payer records, so a
certificate the payer records hold makes the two sides differ; the
tax-residence answer is taken from the draft, so it agrees without confirming
anything independently. A missing, refused or newer draft and a missing
calculation each keep their own state.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotService,
    derive_borrador_100_snapshot_id,
)
from ....application.live.borrador_100_comparison import (
    Borrador100ComparisonClassification,
    Borrador100ComparisonProjection,
    Borrador100ComparisonReason,
    Borrador100ComparisonRow,
    Borrador100ComparisonSources,
    Borrador100ComparisonStaleReason,
    Borrador100ComparisonStatus,
    compare_borrador_100_with_calculation,
)
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.operations.public_scalar import PublicDecimal
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import casillas_by_binding
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.user_profile.tests.general_regime_facts import (
    GENERAL_REGIME_NATURAL_PERSON_FACTS,
    RENTA_UNMARRIED_TAXPAYER_FACTS,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ...adapter_composition_ports import build_borrador_100_snapshot_repository
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "21111111-1111-4111-8111-111111111111"
_PROFILE_ID = UUID(_BUCKET_ID)
_TAX_ID = "12345678Z"
_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "0A")
_CREDIT: BindingId = "renta-retencion-soportada-trabajo"
_RESIDENCE: BindingId = "renta-profile-tax-residence-ccaa"
_SOURCE_URL = "file-import:sha256:" + "b" * 64
_FIRST_IMPORT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
_SECOND_IMPORT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
_WORDS = "application.live.borrador.comparison"


@dataclass(frozen=True, slots=True)
class _Profile:
    operation: PinnedAuthorityOperation
    work_units: WorkUnitCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    events: BucketEventHistoryRepository
    drafts: Borrador100SnapshotRepository

    def sources(self) -> Borrador100ComparisonSources:
        return Borrador100ComparisonSources(
            bucket_id=_BUCKET_ID,
            work_units=self.work_units,
            calculations=self.calculations,
            verifications=VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID),
        )

    def compare(self, language: OutputLanguage = OutputLanguage.EN) -> Borrador100ComparisonProjection:
        reading = Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=self.drafts).read_latest_for_year(
            filing_year=_YEAR, operation=self.operation
        )
        return compare_borrador_100_with_calculation(
            profile_id=_PROFILE_ID,
            filing_year=_YEAR,
            reading=reading,
            sources=self.sources(),
            operation=self.operation,
            language=language,
        )

    def import_draft(self, values: dict[str, Decimal | str], *, captured_at: datetime = _FIRST_IMPORT) -> str:
        return (
            Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=self.drafts)
            .capture(
                filing_year=_YEAR,
                period=_PERIOD,
                captured_at=captured_at,
                source_url=_SOURCE_URL,
                binding_values=values,
                operation=self.operation,
            )
            .snapshot_id
        )

    def create_work(self) -> str:
        return create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_PERIOD,
            revision_id="2025",
            ports=WorkLifecyclePorts(work_unit_repository=self.work_units, bucket_event_repository=self.events),
            operation=self.operation,
        ).work_unit_id

    def calculate(
        self, work_unit_id: str, snapshot_id: str | None, residence: str | None = None
    ) -> CalculationRevision:
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=self.work_units,
            calculation_repository=self.calculations,
            bucket_event_repository=self.events,
            borrador_snapshot_repository=self.drafts,
        ) as ports:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit_id,
                actor="operator-A",
                casilla_inputs={},
                binding_values=_filler_binding_values(self.operation),
                enum_binding_values={} if residence is None else {_RESIDENCE: residence},
                borrador_snapshot_id=snapshot_id,
                relation_values=_zero_relation_values(self.operation),
                ports=ports,
            ).revision


def _filler_binding_values(operation: PinnedAuthorityOperation) -> dict[BindingId, Decimal]:
    """Zero every caller binding the draft, the profile and the records do not own."""
    snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
    alternates = {binding_id for casilla in snapshot.revision.casillas for binding_id in casilla.alternate_bindings}
    exclusions = {_CREDIT, _RESIDENCE, *alternates}
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id not in exclusions
        and binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "retencion_soportada"
    }


def _zero_relation_values(operation: PinnedAuthorityOperation) -> dict[RelationId, Decimal]:
    """Zero every relation that does not feed the credit box, which only its records may fill."""
    revision = operation.snapshot("100", filing_year=_YEAR, period="0A").revision
    targets = casillas_by_binding(revision)
    credit_boxes = set(targets.get(_CREDIT, ()))
    return {
        binding.id: Decimal("0")
        for binding, _ in relation_prefill_bindings_for_period(revision)
        if not credit_boxes.intersection(targets.get(binding.id, ()))
    }


def _seed_taxpayer() -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                *GENERAL_REGIME_NATURAL_PERSON_FACTS,
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
            ),
            created_at=datetime(2026, 4, 1, tzinfo=UTC),
            updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            context=_profile_creation_context_for_test(),
        ),
    )


@pytest.fixture
def profile(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[_Profile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        _seed_taxpayer()
        yield _Profile(
            operation=operation,
            work_units=WorkUnitCatalogueRepository(objects=objects),
            calculations=CalculationRevisionCatalogueRepository(objects=objects),
            events=BucketEventHistoryRepository(objects=objects),
            drafts=build_borrador_100_snapshot_repository(bucket_id=_BUCKET_ID),
        )


def _row(result: Borrador100ComparisonProjection, casilla_id: str) -> Borrador100ComparisonRow:
    (row,) = (row for row in result.rows if row.casilla_id == casilla_id)
    return row


def _box_of(operation: PinnedAuthorityOperation, binding_id: BindingId) -> str:
    revision = operation.snapshot("100", filing_year=_YEAR, period="0A").revision
    (casilla_id,) = casillas_by_binding(revision)[binding_id]
    return casilla_id


def _words(key: str, language: OutputLanguage) -> str:
    return tr(f"{_WORDS}.{key}", locale=language.value)


def test_nothing_imported_and_nothing_calculated_is_no_capture_not_agreement(profile: _Profile) -> None:
    result = profile.compare()

    assert result.status.token == Borrador100ComparisonStatus.NO_CAPTURE
    assert result.status.words == _words("status.no_capture", OutputLanguage.EN)
    assert result.capture is None and result.calculation is None
    assert result.rows == () and result.refused_captures == 0 and result.outdated_stored_captures == 0
    assert result.counts.agree == 0


def test_a_draft_without_a_saved_calculation_is_no_calculation(profile: _Profile) -> None:
    snapshot_id = profile.import_draft({_CREDIT: Decimal("125.50")})
    profile.create_work()

    result = profile.compare()

    assert result.status.token == Borrador100ComparisonStatus.NO_CALCULATION
    assert result.capture is not None and result.capture.snapshot_id == snapshot_id
    assert result.capture.evidence.words == _words("evidence.borrador", OutputLanguage.EN)
    assert result.calculation is None
    assert result.rows == ()


def test_a_stored_draft_the_rules_refuse_is_capture_refused_not_absent(profile: _Profile) -> None:
    ref = profile.operation.snapshot("100", filing_year=_YEAR, period="0A").snapshot_ref
    values: dict[str, Decimal | str] = {"casilla.0596": Decimal("15.25")}
    profile.drafts.save(
        Borrador100Snapshot(
            snapshot_id=derive_borrador_100_snapshot_id(
                filing_year=_YEAR,
                period=_PERIOD,
                registry_snapshot_ref=ref,
                source_url=_SOURCE_URL,
                binding_values=values,
            ),
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_PERIOD,
            registry_snapshot_ref=ref,
            captured_at=_FIRST_IMPORT,
            source_url=_SOURCE_URL,
            state=SnapshotLifecycleState.ACTIVE,
            binding_values=values,
        )
    )

    result = profile.compare()

    assert result.status.token == Borrador100ComparisonStatus.CAPTURE_REFUSED
    assert result.refused_captures == 1
    assert result.capture is None and result.rows == ()


def test_each_box_is_compared_under_its_registry_identity_and_keeps_both_grades(profile: _Profile) -> None:
    """The payer records' credit differs from the draft; the residence the draft supplied agrees, but not independently."""
    snapshot_id = profile.import_draft({_CREDIT: Decimal("125.50"), _RESIDENCE: "madrid"})
    work_unit_id = profile.create_work()
    seed_payer_certificate(
        operation=profile.operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B12345674",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1.00"),
    )
    head = profile.calculate(work_unit_id, snapshot_id)

    result = profile.compare(OutputLanguage.ES)

    assert result.status.token == Borrador100ComparisonStatus.COMPARED
    assert result.status.words == _words("status.compared", OutputLanguage.ES)
    assert result.stale_reasons == ()
    assert result.capture is not None and result.capture.snapshot_id == snapshot_id
    assert result.calculation is not None
    assert result.calculation.calculation_revision_id == head.calculation_revision_id
    assert result.calculation.replayed_snapshot_id == snapshot_id
    assert result.calculation.evidence.words == _words("evidence.calculation", OutputLanguage.ES)
    assert result.capture.evidence.words != result.calculation.evidence.words

    credit = _row(result, _box_of(profile.operation, _CREDIT))
    assert credit.borrador_value == PublicDecimal(decimal="125.50")
    assert credit.calculation_value is not None and isinstance(credit.calculation_value, PublicDecimal)
    assert Decimal(credit.calculation_value.decimal) == Decimal("1.00")
    assert credit.difference is not None and Decimal(credit.difference.decimal) == Decimal("-124.50")
    assert credit.classification.token == Borrador100ComparisonClassification.DIFFER
    assert credit.reason.token == Borrador100ComparisonReason.VALUES_DIFFER
    assert credit.reason.words == _words("reason.values_differ", OutputLanguage.ES)
    assert credit.classification.words == _words("classification.differ", OutputLanguage.ES)
    assert credit.label.text

    residence = _row(result, _box_of(profile.operation, _RESIDENCE))
    assert residence.borrador_value == "madrid" and residence.calculation_value == "madrid"
    assert residence.classification.token == Borrador100ComparisonClassification.AGREE
    assert residence.reason.token == Borrador100ComparisonReason.TAKEN_FROM_BORRADOR
    assert residence.difference is None

    # 2025 declares no draft reading, so a box the draft holds nothing for says nothing either way.
    for row in result.rows:
        if row.casilla_id not in {credit.casilla_id, residence.casilla_id}:
            assert row.borrador_value is None
            assert row.classification.token == Borrador100ComparisonClassification.NOT_COMPARABLE
            assert row.reason.token == Borrador100ComparisonReason.BORRADOR_DOES_NOT_READ_BOX
    counts = result.counts
    assert counts.agree == 1 and counts.differ == 1
    assert counts.only_in_borrador == 0 and counts.only_in_calculation == 0
    assert counts.not_comparable == len(result.rows) - 2


def test_text_answers_that_differ_are_served_without_an_amount_difference(profile: _Profile) -> None:
    snapshot_id = profile.import_draft({_RESIDENCE: "madrid"})
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, snapshot_id, residence="cataluna")

    result = profile.compare(OutputLanguage.HU)

    residence = _row(result, _box_of(profile.operation, _RESIDENCE))
    assert residence.borrador_value == "madrid" and residence.calculation_value == "cataluna"
    assert residence.classification.token == Borrador100ComparisonClassification.DIFFER and residence.difference is None
    assert residence.reason.words == _words("reason.values_differ", OutputLanguage.HU)


def test_a_draft_imported_after_the_calculation_replayed_another_is_stale(profile: _Profile) -> None:
    first = profile.import_draft({_RESIDENCE: "madrid"})
    work_unit_id = profile.create_work()
    profile.calculate(work_unit_id, first)
    second = profile.import_draft({_RESIDENCE: "cataluna"}, captured_at=_SECOND_IMPORT)

    result = profile.compare(OutputLanguage.CA)

    assert result.status.token == Borrador100ComparisonStatus.STALE
    assert Borrador100ComparisonStaleReason.CALCULATION_USED_OTHER_CAPTURE in {
        reason.token for reason in result.stale_reasons
    }
    assert result.capture is not None and result.capture.snapshot_id == second
    assert result.calculation is not None and result.calculation.replayed_snapshot_id == first
    residence = _row(result, _box_of(profile.operation, _RESIDENCE))
    assert residence.classification.token == Borrador100ComparisonClassification.DIFFER
    assert residence.reason.token == Borrador100ComparisonReason.VALUES_DIFFER
