"""Report verification retains existing signing custody without creating keys."""

from __future__ import annotations

from typing import cast

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calculation_report_certification import certify_calculation_report
from ..calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationReason,
    _DocumentReading,
    _ExistingSigningKeypairCapability,
    _trace_against_store,
)
from ..export_ports import ModeloExportPorts
from ..review_package_signing import ReviewPackageSigningError, ReviewPackageSigningKeypair
from ._calculation_report_fixture import BUCKET_ID, EXPORTED_AT, build_fixture_report
from ._review_package_signing_support import InMemoryReviewPackageSigningKeypairCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _AbsentSigningKeypairReader:
    def __init__(self) -> None:
        self.read_buckets: list[str] = []

    def load_keypair(self, *, bucket_id: str) -> ReviewPackageSigningKeypair | None:
        self.read_buckets.append(bucket_id)
        return None


class _UnreadableExportPorts:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"unexpected export port access: {name}")


def test_verification_refuses_an_absent_key_without_accessing_other_stores(
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent profile key refuses provenance through the existing check."""
    report, _ = build_fixture_report(operation)
    exported_keypair = InMemoryReviewPackageSigningKeypairCapability().ensure_keypair(
        bucket_id=BUCKET_ID,
        generated_at=EXPORTED_AT,
    )
    certification = certify_calculation_report(
        report,
        csv_sha256="a" * 64,
        visible_layer_sha256="b" * 64,
        keypair=exported_keypair,
    )
    reader = _AbsentSigningKeypairReader()
    ports = cast(ModeloExportPorts, _UnreadableExportPorts())
    checks = _trace_against_store(
        _DocumentReading(checks=(), statement=certification.statement, report=report),
        active_bucket_id=BUCKET_ID,
        export_ports=ports,
        signing_keypair=reader,
        operation=operation,
    )

    assert reader.read_buckets == [BUCKET_ID]
    assert len(checks) == 1
    assert checks[0].check is CalculationSummaryCheckName.SIGNING_KEY_PROFILE
    assert checks[0].layer is CalculationSummaryVerificationLayer.STORE
    assert checks[0].reason is CalculationSummaryVerificationReason.SIGNING_KEY_NOT_THIS_PROFILE
    assert checks[0].refuses


def test_report_rebuild_capability_retains_its_original_key_and_bucket() -> None:
    """Reconstruction uses the retained singleton and refuses retargeting."""
    keypair = InMemoryReviewPackageSigningKeypairCapability().ensure_keypair(
        bucket_id=BUCKET_ID,
        generated_at=EXPORTED_AT,
    )
    retained = _ExistingSigningKeypairCapability(keypair)

    assert retained.ensure_keypair(bucket_id=BUCKET_ID) is keypair
    assert retained.ensure_keypair(bucket_id=f" {BUCKET_ID} ", generated_at=EXPORTED_AT) is keypair
    with pytest.raises(ReviewPackageSigningError, match="different bucket"):
        retained.ensure_keypair(bucket_id="33333333-3333-4333-8333-333333333333")
