"""Amend-flow tests for ledger contributors, export refusal and the amendment write shape."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url

from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ....application.modelo.action_errors import (
    StoredRowFieldScalarInputError,
)
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.calculation_revision_queries import get_calculation_revision
from ....application.modelo.export import export_modelo_revision
from ....application.modelo.export_contracts import ModeloExportCommand, ModeloExportEvidenceMissingError
from ....application.modelo.work_lifecycle import (
    get_work_unit,
)
from ....core.casilla_id import validated_casilla_id
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevisionState,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.filing_record import (
    FilingDeclarationKind,
    ModeloRecord,
    ModeloRecordStatus,
)
from ....tests.write_unit_recorder import WriteUnitRecorder
from ...adapter_composition_work_ports import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_filing_action_ports,
    build_work_lifecycle_ports,
)
from ..filing_record_read_support import persisted_filing_record
from .amend_flow_support import (
    AMEND_INCOME_CASILLA,
    EARLIER_YEAR,
    PROFILE_ID,
    T4,
    AmendRuntime,
    Repos,
    amend_runtime,
    drive_amend_creates_complementaria,
    repos,
    seed_external_baseline,
)
from .file_flow_test_support import (
    workflow_profile,
)

__all__ = ["amend_runtime", "repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_amend_baseline_carries_no_ledger_contributors(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """An amendment baseline is an imported filing, so it has no ledger rows.

    This pins the fact the export evidence guard silently depends on. The
    amend path mints its own BORRADOR -> VERIFICADO_COMPLETO -> PRESENTADO
    transitions in-process and never calls ``verify_modelo_revision_with_preconditions``, so
    ``_persist_verified_revision_evidence`` — which lives inside verify's
    granted branch — never runs for an amendment. An amendment therefore
    reaches an export-admitted state carrying neither snapshot nor bundle.

    That is only safe because the amendment also carries no
    ``source_transaction_ids``: the export guard returns early on an empty
    contributor set, so it never reaches the refusal. The emptiness is
    structural rather than incidental — ``amend_modelo_revision`` refuses a
    baseline without ``external_evidence``, and the external-import path
    builds its revision without contributors — but nothing asserted it, and
    the safety of a filing-grade guard should not rest on an unstated
    property of a different module.

    If a future path lets an imported baseline carry ledger contributors,
    this fails, and it should: that amendment would reach export with
    contributors and no evidence, which the guard refuses. The fix then
    belongs on the amend path, not on the guard.
    """
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )

    assert outcome.baseline_revision.source_transaction_ids == ()
    assert new_revision.source_transaction_ids == ()
    # The amendment genuinely reaches an export-admitted state with no evidence;
    # the empty contributor set is the only reason that is not a refusal.
    assert new_revision.state is CalculationRevisionState.PRESENTADO
    assert new_revision.ledger_filing_snapshot is None
    assert new_revision.ledger_filing_evidence is None


def _persist_baseline_justificante(baseline: ModeloRecord, *, tax_id: str) -> None:
    evidence = baseline.external_evidence
    assert evidence is not None
    pdf_sha256 = hashlib.sha256(f"justificante {evidence.reference_id}".encode()).hexdigest()
    with bundled_indexed_authority().operation():
        JustificanteRepository().save(
            Justificante(
                csv=evidence.reference_id,
                modelo=str(baseline.modelo),
                period=baseline.period,
                ejercicio=str(baseline.filing_year),
                presentation_id="1300000000001",
                presented_at=baseline.filed_at,
                tax_id=tax_id,
                total_a_ingresar=None,
                total_a_devolver=None,
                verification_url=TypeAdapter(AnyHttpUrl).validate_python(
                    justificante_cotejo_url(evidence.reference_id)
                ),
                source_pdf_path=source_pdf_reference_path(pdf_sha256),
                source_pdf_sha256=pdf_sha256,
                parsed_at=baseline.filed_at,
            ),
        )


def test_export_refuses_an_amendment_carrying_contributors(
    repos: Repos, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The latent half: contributors without evidence IS refused.

    The sibling test pins that an amendment carries no contributors. This
    one pins what the export action does if that ever stops holding, so the pair
    states the whole invariant rather than half of it — the reachability
    fact and the consequence are recorded together.
    """
    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    # The amended baseline is AEAT-accepted, so its receipt is on file: the
    # export reaches the contributor check rather than stopping at the receipt.
    _persist_baseline_justificante(outcome.baseline, tax_id=workflow_profile().tax_id)
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )

    contributed = new_revision.model_copy(update={"source_transaction_ids": ("a" * 64,)})
    # The contributor set is part of the content-addressed identity.
    with_contributors = contributed.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(contributed)}
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), with_contributors))

    # Exercise the public export boundary: the persisted revision has no ledger
    # snapshot/evidence for its contributor, so export must refuse before bytes
    # are rendered or written.
    with pytest.raises(ModeloExportEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=with_contributors.calculation_revision_id,
                output_path=tmp_path / "refused-amendment-export.txt",
                actor="operator-A",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=PROFILE_ID,
                calculation=cr_repo,
                work_unit=wu_repo,
                filing=fr_repo,
                bucket_event=bv_repo,
            ),
            clock=T4,
            operation=operation,
        )


def test_amendment_commits_its_catalogues_and_event_in_one_transaction(
    amend_runtime: AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """The amendment's three catalogues and its event share one transaction.

    Saved separately with ``modelo.amended`` emitted last, an event-storage
    failure left the amended filing durable and the work-unit pointers advanced
    onto it while the history had no corresponding event and no retryable
    incomplete-amendment marker named the gap.
    """
    repos_tuple = amend_runtime.repos
    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos_tuple
    _, _, baseline = seed_external_baseline(
        repos_tuple,
        casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )
    recorder = WriteUnitRecorder(amend_runtime.engine)

    with recorder.recording(), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=T4,
        )

    assert recorder.commits_between_writes() == 0


def test_split_amendment_write_shape_commits_between_catalogues(
    amend_runtime: AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """Anti-tautology: the recorder does report a seam when one exists.

    Persisting the same catalogues through independent saves -- the shape the
    amendment path replaced -- must be observed as more than one transaction.
    """
    repos_tuple = amend_runtime.repos
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = seed_external_baseline(
        repos_tuple,
        casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=T4,
        )
    revisions = cr_repo.load()
    filings = fr_repo.load()
    work_units = wu_repo.load()
    events = bv_repo.load()
    recorder = WriteUnitRecorder(amend_runtime.engine)

    with recorder.recording():
        cr_repo.save(revisions)
        fr_repo.save(filings)
        wu_repo.save(work_units)
        bv_repo.save(events)

    assert recorder.commits_between_writes() >= 1


def test_amendment_event_and_state_are_both_present_after_success(
    amend_runtime: AmendRuntime, *, operation: PinnedAuthorityOperation
) -> None:
    """Parity: co-committing the event does not change what an amendment records."""
    repos_tuple = amend_runtime.repos
    _wu_repo, _cr_repo, _fr_repo, _, bv_repo = repos_tuple
    _, _, baseline = seed_external_baseline(
        repos_tuple,
        casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")},
        operation=operation,
    )

    with bundled_indexed_authority().operation() as operation:
        amended = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="under-reported turnover",
            actor="operator-A",
            clock=T4,
        )

    refreshed = get_work_unit(
        baseline.work_unit_id,
        ports=build_work_lifecycle_ports(bucket_id=PROFILE_ID),
    )
    assert refreshed.current_filing_record_id == amended.filing_record_id
    assert refreshed.filed_calculation_revision_id == amended.calculation_revision_id
    assert (
        persisted_filing_record(
            baseline.filing_record_id,
            ports=build_filing_action_ports(bucket_id=PROFILE_ID, operation=operation),
        ).status
        is ModeloRecordStatus.SUPERSEDIDO
    )

    amended_events = [
        event for event in bv_repo.load().events.values() if event.event_type is BucketEventType.MODELO_AMENDED
    ]
    assert len(amended_events) == 1
    assert amended_events[0].object_id == amended.filing_record_id
    assert amended_events[0].payload["amends_filing_record_id"] == baseline.filing_record_id


def test_amend_refuses_a_baseline_saved_with_a_scalar_row_field_input(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A filed revision that stores one scalar for a per-row casilla cannot seed a correction.

    Calculate now refuses such an input. A revision filed before it did holds
    an operator input no observation explains, and the correction would carry
    it forward, so amend refuses and names the work unit to recalculate.
    """
    row_field = validated_casilla_id("perc.retenciones")
    work_unit, revision, baseline = seed_external_baseline(
        repos,
        casilla_values={validated_casilla_id("decl.total-perceptores"): Decimal("1")},
        modelo="180",
        filing_year=EARLIER_YEAR,
        period_code="0A",
        input_values_by_casilla_id={row_field: "150"},
        operation=operation,
    )

    with (
        pytest.raises(StoredRowFieldScalarInputError) as exc_info,
        bundled_indexed_authority().operation() as amend_operation,
    ):
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=amend_operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={validated_casilla_id("decl.total-perceptores"): Decimal("2")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="baseline stored a per-row value as a scalar",
            actor="operator-A",
            clock=T4,
        )

    assert exc_info.value.translated_message == "errors.refused.refused_modelo_stored_row_field_input"
    assert exc_info.value.context == {
        "casilla_ids": row_field,
        "calculation_revision_id": revision.calculation_revision_id,
        "work_unit_id": work_unit.work_unit_id,
    }


def test_amend_does_not_demand_row_field_casillas_as_scalars(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A clean Modelo 180 correction passes the completeness gate without per-row scalars.

    Every required manual casilla Modelo 180 declares is a perceptor-row field,
    so a gate demanding them as scalars would refuse every 180 correction,
    including one whose baseline stores nothing it should not.
    """
    _work_unit, _revision, baseline = seed_external_baseline(
        repos,
        casilla_values={validated_casilla_id("decl.total-perceptores"): Decimal("1")},
        modelo="180",
        filing_year=EARLIER_YEAR,
        period_code="0A",
        operation=operation,
    )

    with bundled_indexed_authority().operation() as amend_operation:
        amended = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=amend_operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={validated_casilla_id("decl.total-perceptores"): Decimal("2")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="one more perceptor",
            actor="operator-A",
            clock=T4,
        )

    assert amended is not None
