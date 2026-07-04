"""Approval-basis staleness coverage for the prior-filing observation source.

Exercises the ``prior_filing_observations_fingerprint`` added to
:class:`~aeat.domain.filing.ModeloApprovalBasis` (calculation-source-connectivity
ADR, Phase 9 / W05.P10.S62): an ``APROBADO`` draft must go stale with
:attr:`~aeat.application.filing.ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED`
when the bucket's prior filed observations change (the ``previous_filing`` carry
and relation fold-in source), and must NOT be flagged when they are unchanged.

The digest is self-loaded from the bucket's
:class:`~aeat.application.calculations.CalculationObservationRepository` — a
bucket-keyed, enumerable store — so change-detection is reproducible at approve
and refresh time with only ``bucket_id`` in scope, without running the source
mesh or resolving any relation in the review layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.calculations.registry import (
    CasillaId,
    CasillaObservation,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.secure_sql import TestRuntimeProfile
from ...calculations import CalculationObservationRepository
from .. import (
    CasillaSchemaProvider,
    ModeloApprovalStaleReason,
    ModeloDraft,
    approval_stale_reasons,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    empty_prior_filing_observations_fingerprint,
)
from .._review import _prior_filing_observations_fingerprint
from ..testing import ModeloTestProfile

_PERIOD = Period.from_year_and_code(2026, "1T")
_LEGAL_REFS = ("ley-35-2006:art-99",)
_SOURCE_REFS = ("boe-modelo-130-2025-form",)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="prior filing staleness test")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_M130_RESULTADO_CASILLA: CasillaId = _casilla_id("19")


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloTestProfile(tax_id="12345678Z", display_name="Prior filing staleness test"),
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


@pytest.mark.integration
@pytest.mark.hex_application
def test_approval_goes_stale_when_prior_filing_observation_changes(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    bucket_id = _active_bucket_runtime.bucket_id
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)
    repository = CalculationObservationRepository(bucket_id=bucket_id)

    repository.save_observation(_prior_observation(value="100.00"), source_kind="app_filing")
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
    repository.save_observation(_prior_observation(value="250.00"), source_kind="app_filing")

    reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    # Only the prior-filing source changed: draft, transactions, invoices, category
    # profiles, and schema are unchanged, so PRIOR_FILING_OBSERVATIONS_CHANGED is
    # the sole reason.
    assert reasons == (ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED,)


@pytest.mark.integration
@pytest.mark.hex_application
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

    repository.save_observation(_prior_observation(value="100.00"), source_kind="app_filing")
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


# Registry-free unit coverage of the fingerprint mechanism the prior-filing stale
# detection relies on. These build the digest directly from real
# `RegistryModeloObservation` values wrapped in a data-only carrier that matches
# the observation repository's stored-envelope shape, so they exercise the
# change-detection signal without a schema provider or the secure backend.


@dataclass(frozen=True)
class _StoredObservation:
    """Data-only carrier matching the fingerprint helper's structural shape."""

    observation: RegistryModeloObservation
    source_kind: str
    member_nif: str | None
    stamped_revision_id: str


def _carrier(
    *, value: str, source_kind: str = "app_filing", stamped_revision_id: str = "2019-y-siguientes"
) -> _StoredObservation:
    return _StoredObservation(
        observation=_prior_observation(value=value),
        source_kind=source_kind,
        member_nif=None,
        stamped_revision_id=stamped_revision_id,
    )


@pytest.mark.unit
@pytest.mark.hex_application
def test_prior_filing_fingerprint_changes_when_a_filed_value_changes() -> None:
    before = _prior_filing_observations_fingerprint([_carrier(value="100.00")])
    after = _prior_filing_observations_fingerprint([_carrier(value="250.00")])

    assert before != after


@pytest.mark.unit
@pytest.mark.hex_application
def test_prior_filing_fingerprint_tracks_the_stamped_revision() -> None:
    before = _prior_filing_observations_fingerprint([_carrier(value="100.00", stamped_revision_id="2019-y-siguientes")])
    after = _prior_filing_observations_fingerprint([_carrier(value="100.00", stamped_revision_id="2024-y-siguientes")])

    # Same filed value, different stamped registry revision -> different digest,
    # so a revision re-stamp of an otherwise-identical prior is not silently missed.
    assert before != after


@pytest.mark.unit
@pytest.mark.hex_application
def test_prior_filing_fingerprint_is_deterministic_and_order_independent() -> None:
    a = _carrier(value="100.00")
    b = _StoredObservation(
        observation=RegistryModeloObservation(
            modelo="130",
            filing_year=2025,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id=_M130_RESULTADO_CASILLA,
                    value=Decimal("200.00"),
                    legal_refs=_LEGAL_REFS,
                    source_refs=_SOURCE_REFS,
                ),
            ),
        ),
        source_kind="app_filing",
        member_nif=None,
        stamped_revision_id="2019-y-siguientes",
    )

    assert _prior_filing_observations_fingerprint([a, b]) == _prior_filing_observations_fingerprint([b, a])


@pytest.mark.unit
@pytest.mark.hex_application
def test_prior_filing_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = _prior_filing_observations_fingerprint([])
    populated = _prior_filing_observations_fingerprint([_carrier(value="100.00")])

    assert empty != populated
    # The exported empty-set helper matches an empty stream and is stable.
    assert empty == empty_prior_filing_observations_fingerprint()
    assert empty == _prior_filing_observations_fingerprint([])
