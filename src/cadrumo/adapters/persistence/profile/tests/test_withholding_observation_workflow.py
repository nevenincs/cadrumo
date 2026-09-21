"""Integration proof for the atomic withholding observation mutation boundary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.withholding_observation_service import (
    WithholdingMutationEnvelope,
    WithholdingMutationMode,
    WithholdingObservationMutationError,
    WithholdingObservationService,
    WithholdingProjectionEntry,
    WithholdingProjectionIdentity,
    WithholdingProjectionRole,
    WithholdingWindowScope,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _entry(
    *,
    suffix: str,
    retencion: bool,
    recognition_event_id: str | None = None,
    settlement_event_id: str | None = None,
    allocation_id: str | None = None,
) -> WithholdingProjectionEntry:
    identity = WithholdingProjectionIdentity(
        source_kind="manual",
        source_object_id="source-1",
        source_revision_id="revision-1",
        recognition_event_id=recognition_event_id or f"recognition-{suffix}",
        settlement_event_id=settlement_event_id or f"payment-{suffix}",
        allocation_id=allocation_id or f"allocation-{suffix}",
        projection_role=WithholdingProjectionRole.RETENCION if retencion else WithholdingProjectionRole.PERCEPCION,
    )
    if retencion:
        return WithholdingProjectionEntry(
            identity=identity,
            retencion=RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="source-1",
                perceptor_nif="11111111H",
                perceptor_name="Synthetic recipient",
                scheme=RetencionScheme("actividades_economicas"),
                taxable_base=Decimal("100"),
                retencion_amount=Decimal("19"),
                accrued_on="2024-03-15",
            ),
        )
    return WithholdingProjectionEntry(
        identity=identity,
        percepcion=WithholdingObservation(
            source_id="source-1",
            perceptor_tax_id="11111111H",
            perceptor_legal_name="Synthetic recipient",
            country_code="ES",
            transaction_date=date(2024, 3, 15),
            clave=RetencionClave.from_registry("A"),
            subclave="01",
            percibido_dinerario=Decimal("100"),
            retencion_practicada=Decimal("19"),
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
            base_retenciones=Decimal("0"),
        ),
    )


def _service_for(objects: object) -> tuple[WithholdingObservationService, WithholdingObservationWorkflowAdapter]:
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

    assert isinstance(objects, SecureObjectRepository)
    workflow = WithholdingObservationWorkflowAdapter(
        objects=objects,
        retenciones=RetencionObservationRepositoryAdapter(objects=objects),
        percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
    )
    return WithholdingObservationService(workflow), workflow


def test_append_commits_both_projections_and_exact_replay_is_a_noop(tmp_path: Path) -> None:
    """One real batch survives reopening and retains two same-recipient projections."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        command = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-append-1",
            entries=(
                _entry(suffix="one", retencion=True),
                _entry(suffix="two", retencion=False),
            ),
        )

        result = service.apply(command)
        assert result is not None and not result.replayed
        reopened, _reopened_workflow = _service_for(profile.repository)
        replay = reopened.apply(command)
        assert replay is not None and replay.replayed
        state = reopened.read_window(scope)
        assert len(state.entries) == 2
        assert (
            len(
                RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("190", scope.period)
            )
            == 1
        )
        assert (
            len(
                PercepcionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                    "190", scope.period
                )
            )
            == 1
        )


def test_later_settlement_cannot_create_a_second_recognized_liability(tmp_path: Path) -> None:
    """Settlement metadata is not part of the projection identity."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="123", period=Period.from_year_and_code(2025, "3T"))
        recognized = _entry(
            suffix="due",
            retencion=True,
            recognition_event_id="exigibility-1",
            allocation_id="allocation-1",
        )
        recognized = recognized.model_copy(
            update={"identity": recognized.identity.model_copy(update={"settlement_event_id": None})}
        )
        settled = _entry(
            suffix="settled",
            retencion=True,
            recognition_event_id="exigibility-1",
            settlement_event_id="payment-in-later-year",
            allocation_id="allocation-1",
        )
        service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="recognized-capital-1",
                entries=(recognized,),
            )
        )

        with pytest.raises(WithholdingObservationMutationError, match="projection_identity_conflict"):
            service.apply(
                WithholdingMutationEnvelope(
                    scope=scope,
                    mode=WithholdingMutationMode.APPEND,
                    idempotency_key="settled-capital-1",
                    entries=(settled,),
                )
            )
        assert service.read_window(scope).entries == (recognized,)


def test_stale_replace_refuses_without_partial_projection_change(tmp_path: Path) -> None:
    """A baseline mismatch leaves the real encrypted active window intact."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        initial = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-append-2",
                entries=(_entry(suffix="one", retencion=True),),
            ),
        )
        assert initial is not None
        service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-append-3",
                entries=(_entry(suffix="two", retencion=True),),
            ),
        )
        with pytest.raises(WithholdingObservationMutationError, match="stale_baseline"):
            service.apply(
                WithholdingMutationEnvelope(
                    scope=scope,
                    mode=WithholdingMutationMode.REPLACE,
                    idempotency_key="synthetic-replace-stale",
                    baseline=initial.baseline,
                    entries=(_entry(suffix="three", retencion=True),),
                ),
            )
        assert len(service.read_window(scope).entries) == 2


def test_clear_retains_immutable_generation_history(tmp_path: Path) -> None:
    """Clear advances the head rather than deleting the audit history."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        initial = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-append-4",
                entries=(_entry(suffix="one", retencion=True),),
            ),
        )
        assert initial is not None
        cleared = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.CLEAR,
                idempotency_key="synthetic-clear-1",
                baseline=initial.baseline,
                reason="synthetic correction",
            ),
        )
        assert cleared is not None
        assert service.read_window(scope).entries == ()


def test_stale_adapter_writer_rolls_back_its_entire_batch(tmp_path: Path) -> None:
    """A stale head CAS leaves neither its idempotency claim nor projection behind."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, repository = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        initial = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-append-5",
                entries=(_entry(suffix="one", retencion=True),),
            ),
        )
        assert initial is not None
        stale = repository.load_window(scope)
        winning = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-append-6",
            entries=(_entry(suffix="two", retencion=True),),
        )
        repository.commit_transition(
            predecessor=stale,
            successor=(*stale.entries, *winning.entries),
            envelope=winning,
        )
        losing = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-append-7",
            entries=(_entry(suffix="three", retencion=True),),
        )
        with pytest.raises(WithholdingObservationMutationError, match="concurrent_write"):
            repository.commit_transition(
                predecessor=stale,
                successor=(*stale.entries, *losing.entries),
                envelope=losing,
            )
        assert {entry.identity.allocation_id for entry in repository.load_window(scope).entries} == {
            "allocation-one",
            "allocation-two",
        }


def test_omitted_mutation_and_late_replay_preserve_the_original_generation(tmp_path: Path) -> None:
    """Omission is read-only and a replay names its own committed generation, not the current head."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        first = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-append-original",
            entries=(_entry(suffix="one", retencion=True),),
        )
        original = service.apply(first)
        assert original is not None
        before_omission = service.read_window(scope)
        assert service.apply(None) is None
        assert service.read_window(scope) == before_omission
        later = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-append-later",
                entries=(_entry(suffix="two", retencion=True),),
            ),
        )
        assert later is not None and later.baseline != original.baseline
        before_replay = service.read_window(scope)
        replay = service.apply(first)
        assert replay is not None and replay.replayed and replay.baseline == original.baseline
        assert service.read_window(scope) == before_replay


def test_same_key_different_command_and_stale_clear_refuse_without_changes(tmp_path: Path) -> None:
    """A replay-key conflict and a stale clear are both non-mutating refusals."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        initial_command = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-conflict-key",
            entries=(_entry(suffix="one", retencion=True),),
        )
        initial = service.apply(initial_command)
        assert initial is not None
        state = service.read_window(scope)
        with pytest.raises(WithholdingObservationMutationError, match="idempotency_conflict"):
            service.apply(
                initial_command.model_copy(
                    update={"entries": (_entry(suffix="two", retencion=True),)},
                ),
            )
        service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-clear-race",
                entries=(_entry(suffix="three", retencion=True),),
            ),
        )
        with pytest.raises(WithholdingObservationMutationError, match="stale_baseline"):
            service.apply(
                WithholdingMutationEnvelope(
                    scope=scope,
                    mode=WithholdingMutationMode.CLEAR,
                    idempotency_key="synthetic-stale-clear",
                    baseline=initial.baseline,
                    reason="synthetic correction",
                ),
            )
        assert service.read_window(scope) != state
        assert len(service.read_window(scope).entries) == 2


def test_repeated_same_recipient_scheme_survives_by_composite_identity(tmp_path: Path) -> None:
    """Two payments to the same recipient and scheme remain distinct encrypted projection rows."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        result = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-repeated-recipient",
                entries=(_entry(suffix="one", retencion=True), _entry(suffix="two", retencion=True)),
            ),
        )
        assert result is not None
        observations = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "190", scope.period
        )
        assert len(observations) == 2
        assert {(item.perceptor_nif, item.scheme) for item in observations} == {
            ("11111111H", RetencionScheme("actividades_economicas")),
        }


def test_clear_and_correction_generations_are_queryable(tmp_path: Path) -> None:
    """Immutable predecessor, correction, and clear generation records remain readable."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, _workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        initial = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-correction-origin",
                entries=(_entry(suffix="one", retencion=True),),
            ),
        )
        assert initial is not None
        correction = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.REPLACE,
                idempotency_key="synthetic-correction-replace",
                baseline=initial.baseline,
                reason="synthetic corrected source revision",
                supersedes_generation_id=initial.baseline.generation_id,
                entries=(_entry(suffix="two", retencion=True),),
            ),
        )
        assert correction is not None
        audit = service.read_generation(scope, correction.baseline.generation_id)
        assert audit is not None and audit.supersedes_generation_id == initial.baseline.generation_id
        cleared = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.CLEAR,
                idempotency_key="synthetic-correction-clear",
                baseline=correction.baseline,
                reason="synthetic clear",
            ),
        )
        assert cleared is not None
        assert service.read_generation(scope, initial.baseline.generation_id) is not None
        assert service.read_generation(scope, cleared.baseline.generation_id) is not None


def test_distinct_concurrent_appends_converge_after_a_real_head_cas_race(tmp_path: Path) -> None:
    """The append retry reloads after a competing real commit and retains both allocations."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        service, workflow = _service_for(profile.repository)
        scope = WithholdingWindowScope(modelo="190", period=Period.from_year_and_code(2024, "1T"))
        seed = service.apply(
            WithholdingMutationEnvelope(
                scope=scope,
                mode=WithholdingMutationMode.APPEND,
                idempotency_key="synthetic-race-seed",
                entries=(_entry(suffix="one", retencion=True),),
            ),
        )
        assert seed is not None
        competing = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-race-competing",
            entries=(_entry(suffix="two", retencion=True),),
        )
        intended = WithholdingMutationEnvelope(
            scope=scope,
            mode=WithholdingMutationMode.APPEND,
            idempotency_key="synthetic-race-intended",
            entries=(_entry(suffix="three", retencion=True),),
        )

        class _InjectingRace:
            def __init__(self) -> None:
                self.injected = False

            def load_window(self, current_scope):
                return workflow.load_window(current_scope)

            def idempotency_replay(self, current_scope, key):
                return workflow.idempotency_replay(current_scope, key)

            def load_generation(self, current_scope, generation_id):
                return workflow.load_generation(current_scope, generation_id)

            def commit_transition(self, *, predecessor, successor, envelope):
                if not self.injected:
                    self.injected = True
                    workflow.commit_transition(
                        predecessor=predecessor,
                        successor=(*predecessor.entries, *competing.entries),
                        envelope=competing,
                    )
                return workflow.commit_transition(
                    predecessor=predecessor,
                    successor=successor,
                    envelope=envelope,
                )

        result = WithholdingObservationService(_InjectingRace()).apply(intended)
        assert result is not None
        assert {entry.identity.allocation_id for entry in service.read_window(scope).entries} == {
            "allocation-one",
            "allocation-two",
            "allocation-three",
        }
