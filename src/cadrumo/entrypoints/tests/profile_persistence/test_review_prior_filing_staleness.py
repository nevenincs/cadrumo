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
    :func:`~cadrumo.application.filing.tests.filing_support.empty_prior_filing_observations_fingerprint`
        Supplies the explicit empty-source fingerprint used by tests and
        overrides.
    :func:`~application.filing.draft_review.prior_filing_observations_fingerprint`
        Stable, order-independent digest over stored prior-observation payloads.
    :mod:`~application.filing.tests.test_review_profile_activity_staleness`
        Sister approval-basis coverage for another self-loaded source surface.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ....application.filing.draft_construction import build_draft
from ....application.filing.draft_review import ModeloApprovalStaleReason, approval_stale_reasons, approve_draft
from ....application.filing.draft_review_ports import DraftReviewPorts
from ....application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.filing.protocols import CasillaSchemaProvider
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ...adapter_composition_ports import build_draft_review_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERIOD = Period.from_year_and_code(2026, "1T")
_LEGAL_REFS = ("ley-35-2006:art-99",)
_SOURCE_REFS = ("boe-modelo-130-2025-form",)


_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="prior filing staleness test")


def _stamped_revision_id() -> str:
    return str(published_authority_operation().snapshot("130", filing_year=2026, period="1T").revision.id)


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Prior filing staleness test"),
        inputs={
            "01": Decimal("100"),
            "gastos-deducibles-previos": Decimal("25"),
            "modelo-130-estimacion-directa-modalidad": "directa_normal",
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


def _save_prior_filing(
    repository: CalculationObservationRepository, value: str, *, source_kind: str = "app_filing"
) -> None:
    """Store the prior filing's observation at ``value``, replacing any earlier one at the same key."""
    repository.save(
        repository.prepare_observation_envelope(
            _prior_observation(value=value),
            source_kind=source_kind,
            stamped_revision_id=_stamped_revision_id(),
        )
    )


def _approve_operator_draft(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    ports: DraftReviewPorts,
    operation: PinnedAuthorityOperation,
) -> ModeloDraft:
    return approve_draft(
        draft,
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
        ports=ports,
        operation=operation,
    )


def test_approval_goes_stale_when_prior_filing_observation_changes(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = _active_bucket_runtime.bucket_id
        schema_provider = _schema_provider()
        draft = _ready_draft(schema_provider)
        repository = CalculationObservationRepository(bucket_id=bucket_id)

        _save_prior_filing(repository, "100.00")
        ports = build_draft_review_ports(bucket_id=bucket_id)
        approved = _approve_operator_draft(
            draft,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=_authority_operation_for_test,
        )
        assert approved.status is ModeloDraftStatus.APROBADO
        assert approved.approval_basis is not None
        assert approved.approval_basis.prior_filing_observations_fingerprint  # populated, non-empty

        # Mutate ONLY the prior filing: same (modelo, year, period) key, different
        # filed value, so the self-loaded observation-store digest must change.
        _save_prior_filing(repository, "250.00")

        reasons = approval_stale_reasons(
            approved,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=_authority_operation_for_test,
        )

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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = _active_bucket_runtime.bucket_id
        schema_provider = _schema_provider()
        draft = _ready_draft(schema_provider)
        repository = CalculationObservationRepository(bucket_id=bucket_id)

        _save_prior_filing(repository, "100.00")
        ports = build_draft_review_ports(bucket_id=bucket_id)
        approved = _approve_operator_draft(
            draft,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=_authority_operation_for_test,
        )

        # No mutation to any source between approval and the staleness check.
        reasons = approval_stale_reasons(
            approved,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=_authority_operation_for_test,
        )

        assert ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED not in reasons
        assert reasons == ()


def test_pending_correction_changes_approval_but_hidden_official_refresh_does_not(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    """A local 150 replaces official 100; an official refresh to 130 stays behind it."""
    with bundled_indexed_authority().operation() as operation:
        bucket_id = _active_bucket_runtime.bucket_id
        schema_provider = _schema_provider()
        repository = CalculationObservationRepository(bucket_id=bucket_id)
        ports = build_draft_review_ports(bucket_id=bucket_id)
        draft = _ready_draft(schema_provider)
        _save_prior_filing(repository, "100.00", source_kind="aeat_csv_register")
        approved = _approve_operator_draft(
            draft,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=operation,
        )

        _save_prior_filing(repository, "150.00")
        reasons = approval_stale_reasons(
            approved,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=operation,
        )
        assert reasons == (ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED,)

        approved_pending = _approve_operator_draft(
            draft,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=operation,
        )
        _save_prior_filing(repository, "130.00", source_kind="aeat_csv_register")
        reasons_after_official_refresh = approval_stale_reasons(
            approved_pending,
            bucket_id=bucket_id,
            schema_provider=schema_provider,
            ports=ports,
            operation=operation,
        )
        assert reasons_after_official_refresh == ()
        layers = repository.load_observation_layers("130", _PERIOD)
        assert layers.official is not None and layers.pending_local is not None and layers.effective is not None
        assert layers.official.observation.casilla_values[_M130_RESULTADO_CASILLA] == Decimal("130.00")
        assert layers.effective.observation.casilla_values[_M130_RESULTADO_CASILLA] == Decimal("150.00")
