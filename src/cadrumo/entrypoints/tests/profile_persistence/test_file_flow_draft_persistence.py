"""The approved filing draft a verify run produces is durably stored.

Approval used to happen entirely in memory: the workflow gate built the draft,
approved it, handed it to preflight and dropped it. Nothing else in the
application wrote the encrypted filing-draft namespace, so every reader of that
store -- the review queue's draft rows, the workspace summary's draft count,
the CLI's draft lookup -- read an empty store and reported zero permanently.
An operator reads that as having no drafts, not as the application declining to
keep them, which is the absent-versus-zero collapse the filing surfaces exist
to keep distinguishable.

The control matters as much as the assertion: the store must be empty before
the run, or a passing test proves only that something, sometime, wrote a draft.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.submission.models import ModeloDraftStatus
from cadrumo.entrypoints.adapter_composition import build_draft_review_ports
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    T1,
    T2,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
    verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_a_verified_revision_leaves_its_approved_draft_in_the_store(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    drafts = ModeloDraftRepository(bucket_id=work_unit.bucket_id)

    assert tuple(drafts.iter_drafts()) == ()
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_49:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_49,
            clock=T1,
        )
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert report.granted_verificado_completo is True

    stored = tuple(drafts.iter_drafts())
    assert len(stored) == 1
    assert stored[0].status is ModeloDraftStatus.APROBADO
    assert stored[0].modelo == work_unit.modelo
    # the approval basis is what stale detection later compares against, so a
    # draft stored without one is stored in a state that can never go stale
    assert stored[0].approval_basis is not None


def test_re_verifying_the_same_revision_rewrites_one_row(repos: Repos) -> None:
    """``draft_id`` is a content address, so an unchanged draft is idempotent."""
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    drafts = ModeloDraftRepository(bucket_id=work_unit.bucket_id)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_85:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_85,
            clock=T1,
        )
    for clock in (T1, T2):
        verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=clock,
        )

    stored = tuple(drafts.iter_drafts())
    assert len(stored) == 1


def test_a_freshly_approved_draft_is_not_immediately_stale(repos: Repos) -> None:
    """The approval the gate stamps must survive its own first read.

    The gate approves against a transient empty ``TransactionCatalogue`` because
    persisted transaction evidence belongs to the calculation revision, while
    the review queue recomputes the basis from whatever the bucket holds. If
    those two disagree by construction, every draft the product stores reads as
    an aged-out approval the moment anyone opens the queue, and a permanent
    high-severity row that is always wrong is worse than no row at all.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        from cadrumo.application.review.source_adapters import reviewed_against_current_state

        wu_repo, cr_repo, _, vr_repo, bv_repo = repos
        work_unit = seed_work_unit(wu_repo, filing_year=2024)
        # A NON-empty bucket ledger is the whole point. Against an empty one the
        # digest of a transient empty catalogue and the digest of the bucket's own
        # agree by accident, and the assertion below holds however the basis is
        # stamped.
        _seed_one_bucket_transaction(work_unit.bucket_id)
        with calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_130:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
                binding_values=DEFAULT_130_BINDING_VALUES,
                ports=_calculation_ports_130,
                clock=T1,
            )
        verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=T2,
        )

        stored = tuple(ModeloDraftRepository(bucket_id=work_unit.bucket_id).iter_drafts())
        assert len(stored) == 1
        assert stored[0].status is ModeloDraftStatus.APROBADO

        # Asserted through the refresh rather than through drafts_pending, whose
        # empty result is the CORRECT answer for a healthy approved draft and so
        # cannot distinguish a working invariant from a queue that saw nothing.
        refreshed, reasons = reviewed_against_current_state(
            stored[0],
            bucket_id=work_unit.bucket_id,
            ports=build_draft_review_ports(bucket_id=work_unit.bucket_id),
            operation=_authority_operation_for_test,
        )
        assert reasons == ()
        assert refreshed.status is ModeloDraftStatus.APROBADO


def _seed_one_bucket_transaction(bucket_id: str) -> None:
    """Put one row in the bucket's transaction catalogue."""
    from datetime import UTC, date, datetime
    from decimal import Decimal
    from pathlib import Path

    from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from cadrumo.domain.transactions.enums import (
        BusinessClassification,
        TransactionDirection,
        TransactionLifecycleState,
    )
    from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
    from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

    ingested_at = datetime(2024, 1, 2, tzinfo=UTC)
    transaction = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="staleness-probe-1",
                booked_date=date(2024, 1, 2),
                value_date=date(2024, 1, 2),
                amount=Decimal("100.00"),
                currency="EUR",
                counterparty="Cliente SA",
                description="factura 1T",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=ingested_at,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": "factura 1T"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": Decimal("100.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": ingested_at,
            "classified_by": "manual",
        },
    )
    TransactionCatalogueRepository(bucket_id=bucket_id).save(
        TransactionCatalogue.from_transactions((transaction,)),
    )
