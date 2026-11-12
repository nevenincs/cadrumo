"""The borrador comparison reads the real encrypted draft store and a real saved Modelo 100 calculation.

Each case seeds a synthetic 2025 taxpayer, imports a draft into encrypted
custody and saves a calculation through the production calculation service,
then compares them through the registered read's own service. The draft's
work-withholding credit is held only to cross-check the payer records, so a
certificate the payer records hold makes the two sides differ; the
tax-residence answer is taken from the draft, so it agrees without confirming
anything independently. A missing, refused or newer draft and a missing
calculation each keep their own state.

A synthetic draft PDF read through the real parser keeps its printed results,
the boxes no binding owns, as comparison-only observations: they are compared
with the calculation and never reach it.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.live.borrador_100 import (
    Borrador100ObservationGrade,
    Borrador100PrintedObservation,
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
from ....application.live.borrador_100_import import prepare_borrador_100_import
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.operations.public_scalar import PublicDecimal
from ....core.casilla_id import CasillaId
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
    RENTA_UNMARRIED_TAXPAYER_FACTS,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.fixtures.borrador.generate import render_borrador_pdf
from ...adapter_composition_ports import build_borrador_100_snapshot_repository
from ...live_borrador_operation_composition import build_borrador_100_operation_ports
from .file_flow_test_support import calculation_ports_for_test
from .work_income_support import record_work_income

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
_PRINTED_RESULTS: tuple[CasillaId, ...] = ("0505", "0545", "0546", "0585", "0586")


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

    def import_pdf(
        self,
        tmp_path: Path,
        printed: dict[CasillaId, Decimal],
        also_printed: tuple[Borrador100PrintedObservation, ...] = (),
    ) -> str:
        """Read a synthetic draft PDF through the real parser and keep it in encrypted custody.

        ``also_printed`` adds printed boxes the draft import does not read, as a
        draft could print them, so a box the calculation does settle is compared.
        """
        source = tmp_path / "borrador.pdf"
        source.write_bytes(render_borrador_pdf(_YEAR, printed, tax_id=_TAX_ID))
        ports = build_borrador_100_operation_ports(profile_id=_PROFILE_ID, operation=self.operation)
        prepared = prepare_borrador_100_import(
            source,
            filing_year=_YEAR,
            period=_PERIOD,
            operation=self.operation,
            parser=ports.parser,
            profile_tax_id=ports.profile_tax_id,
        )
        assert dict(prepared.binding_values) == {}
        return (
            Borrador100SnapshotService(bucket_id=_BUCKET_ID, repository=self.drafts)
            .capture(
                filing_year=_YEAR,
                period=_PERIOD,
                captured_at=_FIRST_IMPORT,
                source_url=prepared.source_url,
                binding_values=prepared.binding_values,
                printed_observations=(*prepared.printed_observations, *also_printed),
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
        self,
        work_unit_id: str,
        snapshot_id: str | None,
        residence: str | None = None,
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
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    *RENTA_UNMARRIED_TAXPAYER_FACTS,
                )
            ),
            created_at=datetime(2026, 4, 1, tzinfo=UTC),
            updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            context=profile_creation_context_for_test(),
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


@dataclass(frozen=True, slots=True)
class _ComparedWorld:
    snapshot_id: str
    head: CalculationRevision
    result: Borrador100ComparisonProjection


def _compared_credit_and_residence(profile: _Profile) -> _ComparedWorld:
    """Compare a draft carrying the credit and the residence with a calculation whose payer records hold 1,00."""
    snapshot_id = profile.import_draft({_CREDIT: Decimal("125.50"), _RESIDENCE: "madrid"})
    work_unit_id = profile.create_work()
    seed_payer_certificate(
        operation=profile.operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B00015016",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1.00"),
    )
    head = profile.calculate(work_unit_id, snapshot_id)
    return _ComparedWorld(snapshot_id=snapshot_id, head=head, result=profile.compare(OutputLanguage.ES))


def test_a_compared_draft_names_its_capture_and_the_calculation_it_was_replayed_into(profile: _Profile) -> None:
    """The payer records' credit differs from the draft, so the two sides are compared and each keeps its own grade."""
    world = _compared_credit_and_residence(profile)
    result = world.result

    assert result.status.token == Borrador100ComparisonStatus.COMPARED
    assert result.status.words == _words("status.compared", OutputLanguage.ES)
    assert result.stale_reasons == ()
    assert result.capture is not None and result.capture.snapshot_id == world.snapshot_id
    assert result.calculation is not None
    assert result.calculation.calculation_revision_id == world.head.calculation_revision_id
    assert result.calculation.replayed_snapshot_id == world.snapshot_id
    assert result.calculation.evidence.words == _words("evidence.calculation", OutputLanguage.ES)
    assert result.capture.evidence.words != result.calculation.evidence.words


def test_the_credit_the_payer_records_hold_differs_from_the_draft_under_its_registry_identity(
    profile: _Profile,
) -> None:
    result = _compared_credit_and_residence(profile).result

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


def test_the_residence_the_draft_supplied_agrees_without_an_independent_confirmation(profile: _Profile) -> None:
    result = _compared_credit_and_residence(profile).result

    residence = _row(result, _box_of(profile.operation, _RESIDENCE))
    assert residence.borrador_value == "madrid" and residence.calculation_value == "madrid"
    assert residence.classification.token == Borrador100ComparisonClassification.AGREE
    assert residence.reason.token == Borrador100ComparisonReason.TAKEN_FROM_BORRADOR
    assert residence.difference is None


def test_every_other_box_of_a_draft_captured_without_printed_results_is_not_comparable(profile: _Profile) -> None:
    result = _compared_credit_and_residence(profile).result
    credit = _row(result, _box_of(profile.operation, _CREDIT))
    residence = _row(result, _box_of(profile.operation, _RESIDENCE))

    # This draft was captured without its printed results, so a box the draft import reads is
    # one it kept nothing for, and a box it does not read says nothing either way.
    for row in result.rows:
        if row.casilla_id not in {credit.casilla_id, residence.casilla_id}:
            assert row.borrador_value is None
            assert row.classification.token == Borrador100ComparisonClassification.NOT_COMPARABLE
            expected = (
                Borrador100ComparisonReason.BORRADOR_VALUE_NOT_KEPT
                if row.casilla_id in _PRINTED_RESULTS
                else Borrador100ComparisonReason.BORRADOR_DOES_NOT_READ_BOX
            )
            assert row.reason.token == expected
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


_EARNINGS_BOX: CasillaId = "0003"
_EARNINGS_TOTAL_BOX: CasillaId = "0012"
_EARNINGS = Decimal("32000.00")


def _record_work_income(profile: _Profile) -> None:
    """Record the earnings the way an operator does: as the payer's certificate of work income."""
    record_work_income(
        operation=profile.operation,
        taxpayer_tax_id=_TAX_ID,
        filing_year=_YEAR,
        gross=_EARNINGS,
        payer_tax_id="B00015016",
    )


def _printed(casilla_id: CasillaId, value: Decimal) -> Borrador100PrintedObservation:
    """A printed box the draft import does not read, kept for comparison as the import keeps one."""
    return Borrador100PrintedObservation(casilla_id=casilla_id, continuidad_id=None, value=value)


def _reason_for(calculated: object, printed: Decimal) -> Borrador100ComparisonReason:
    if calculated is None:
        return Borrador100ComparisonReason.CALCULATION_HAS_NO_VALUE
    assert isinstance(calculated, PublicDecimal)
    if Decimal(calculated.decimal) == printed:
        return Borrador100ComparisonReason.SAME_VALUE
    return Borrador100ComparisonReason.VALUES_DIFFER


def test_printed_results_read_through_the_parser_are_kept_and_compared_box_by_box(
    profile: _Profile, tmp_path: Path
) -> None:
    """The draft's printed results are kept under their registry identity and compared, never dropped."""
    work_unit_id = profile.create_work()
    _record_work_income(profile)
    printed = {casilla_id: Decimal("1000.00") + index for index, casilla_id in enumerate(_PRINTED_RESULTS)}

    snapshot_id = profile.import_pdf(
        tmp_path,
        printed,
        also_printed=(_printed(_EARNINGS_BOX, Decimal("31000.00")), _printed(_EARNINGS_TOTAL_BOX, _EARNINGS)),
    )
    profile.calculate(work_unit_id, None)

    (stored,) = profile.drafts.list_snapshots()
    assert stored.snapshot_id == snapshot_id and dict(stored.binding_values) == {}
    revision = profile.operation.snapshot("100", filing_year=_YEAR, period="0A").revision
    continuity = {casilla.id: casilla.continuidad_id for casilla in revision.casillas}
    assert {
        row.casilla_id: (row.value, row.continuidad_id)
        for row in stored.printed_observations
        if row.casilla_id in _PRINTED_RESULTS
    } == {casilla_id: (printed[casilla_id], continuity[casilla_id]) for casilla_id in _PRINTED_RESULTS}
    assert all(row.grade is Borrador100ObservationGrade.AEAT_PRINTED_DRAFT for row in stored.printed_observations)

    result = profile.compare()

    assert result.status.token == Borrador100ComparisonStatus.COMPARED
    for casilla_id in _PRINTED_RESULTS:
        row = _row(result, casilla_id)
        assert row.borrador_value == PublicDecimal(decimal=str(printed[casilla_id]))
        assert row.reason.token == _reason_for(row.calculation_value, printed[casilla_id])
    total = _row(result, _EARNINGS_TOTAL_BOX)
    assert total.calculation_value == PublicDecimal(decimal=str(_EARNINGS))
    assert total.classification.token == Borrador100ComparisonClassification.AGREE
    assert total.reason.token == Borrador100ComparisonReason.SAME_VALUE
    earnings = _row(result, _EARNINGS_BOX)
    assert earnings.borrador_value == PublicDecimal(decimal="31000.00")
    assert earnings.classification.token == Borrador100ComparisonClassification.DIFFER
    assert earnings.difference is not None and Decimal(earnings.difference.decimal) == Decimal("1000.00")
    assert all(row.reason.token != Borrador100ComparisonReason.BORRADOR_VALUE_NOT_KEPT for row in result.rows)


def test_a_printed_result_never_reaches_the_calculation_that_replays_its_draft(
    profile: _Profile, tmp_path: Path
) -> None:
    """Replaying a draft whose printed results are wrong leaves every calculated box as the calculation made it."""
    work_unit_id = profile.create_work()
    wrong = Decimal("987654.32")
    _record_work_income(profile)
    independent = profile.calculate(work_unit_id, None)
    snapshot_id = profile.import_pdf(
        tmp_path, dict.fromkeys(_PRINTED_RESULTS, wrong), also_printed=(_printed(_EARNINGS_TOTAL_BOX, wrong),)
    )

    head = profile.calculate(work_unit_id, snapshot_id)

    assert head.borrador_snapshot_id == snapshot_id
    assert tuple(head.bindings_sourced_from_borrador) == ()
    assert str(wrong) not in head.binding_overrides.values()
    assert wrong not in head.casilla_values.values()
    assert dict(head.casilla_values) == dict(independent.casilla_values)
    result = profile.compare()
    assert result.calculation is not None and result.calculation.replayed_snapshot_id == snapshot_id
    total = _row(result, _EARNINGS_TOTAL_BOX)
    assert total.calculation_value == PublicDecimal(decimal=str(_EARNINGS))
    assert total.borrador_value == PublicDecimal(decimal=str(wrong))
    assert total.reason.token == Borrador100ComparisonReason.VALUES_DIFFER
    for casilla_id in (*_PRINTED_RESULTS, _EARNINGS_TOTAL_BOX):
        row = _row(result, casilla_id)
        assert row.borrador_value == PublicDecimal(decimal=str(wrong))
        assert row.calculation_value != PublicDecimal(decimal=str(wrong))
        assert row.reason.token != Borrador100ComparisonReason.TAKEN_FROM_BORRADOR
