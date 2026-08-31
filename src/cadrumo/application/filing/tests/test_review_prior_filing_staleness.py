"""Approval-basis staleness coverage for the prior-filing observation source.

Exercises the ``prior_filing_observations_fingerprint`` added to
:class:`~domain.filing.ModeloApprovalBasis`: an ``APROBADO`` draft must go stale with
:attr:`~application.filing.ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED`
when the bucket's prior filed observations change (the ``previous_filing`` carry
and relation fold-in source), and must not be flagged when they are unchanged.

The digest is self-loaded from the bucket's
:class:`~application.calculations.CalculationObservationRepository` — a
bucket-keyed, enumerable store — so change-detection is reproducible at approve
and refresh time with only ``bucket_id`` in scope, without running the source
mesh or resolving any relation in the review layer.

See Also:
    :func:`~application.filing.compute_current_approval_basis`
        Builds the current review fingerprints, including prior observations.
    :func:`~application.filing.approval_stale_reasons`
        Compares the stored basis with the current prior-observation digest.
    :func:`~application.filing.empty_prior_filing_observations_fingerprint`
        Supplies the explicit empty-source fingerprint used by tests and
        overrides.
    :func:`~application.filing._review._prior_filing_observations_fingerprint`
        Stable, order-independent digest over stored prior-observation payloads.
    :mod:`~application.filing.tests.test_review_profile_activity_staleness`
        Sister approval-basis coverage for another self-loaded source surface.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.filing.protocols import CasillaSchemaProvider
from ....domain.filing.schema import ModeloDraft
from ....domain.submission._protocols import ModeloDraftStatus
from ....tests.secure_sql import TestRuntimeProfile
from ...calculations.observations_repository import CalculationObservationRepository
from .._draft_construction import build_draft
from .._review import ModeloApprovalStaleReason, approval_stale_reasons, approve_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_LEGAL_REFS = ("ley-35-2006:art-99",)
_SOURCE_REFS = ("boe-modelo-130-2025-form",)


_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="prior filing staleness test")


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Prior filing staleness test"),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )


def _prior_observation(*, value: str) -> RegistryModeloObservation:
    """A prior Modelo 130 filing carrying one casilla value.

    Modelo 130 first-quarter filing is a real prior the second-quarter draft
    folds in through the cumulative ``previous_filing`` carry, so a change to it
    legitimately invalidates a later approval.
    """
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_M130_RESULTADO_CASILLA,
                value=Decimal(value),
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )


def test_approval_goes_stale_when_prior_filing_observation_changes(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    bucket_id = _active_bucket_runtime.bucket_id
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)
    repository = CalculationObservationRepository(bucket_id=bucket_id)

    repository.save(
        repository.prepare_observation_envelope(_prior_observation(value="100.00"), source_kind="app_filing")
    )
    approved = approve_draft(
        draft,
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
    )
    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    assert approved.approval_basis.prior_filing_observations_fingerprint  # populated, non-empty

    # Mutate ONLY the prior filing: same (modelo, year, period) key, different
    # filed value, so the self-loaded observation-store digest must change.
    repository.save(
        repository.prepare_observation_envelope(_prior_observation(value="250.00"), source_kind="app_filing")
    )

    reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    # Only the prior-filing source changed: draft, transactions, invoices, category
    # profiles, and schema are unchanged, so PRIOR_FILING_OBSERVATIONS_CHANGED is
    # the sole reason.
    assert reasons == (ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED,)


def test_approval_not_stale_when_prior_filing_observations_unchanged(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    """Anti-tautology: an unchanged observation store produces NO stale reason.

    If :func:`approval_stale_reasons` flagged PRIOR_FILING_OBSERVATIONS_CHANGED
    regardless of whether the prior filings actually changed, the signal would be
    meaningless. Approving and re-checking against the identical store must yield
    an empty reason tuple.
    """
    bucket_id = _active_bucket_runtime.bucket_id
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)
    repository = CalculationObservationRepository(bucket_id=bucket_id)

    repository.save(
        repository.prepare_observation_envelope(_prior_observation(value="100.00"), source_kind="app_filing")
    )
    approved = approve_draft(
        draft,
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
    )

    # No mutation to any source between approval and the staleness check.
    reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    assert ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED not in reasons
    assert reasons == ()
