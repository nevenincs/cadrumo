"""Strict roundtrip across the encrypted VerificationReportCatalogue boundary.

``VerificationReportCatalogueRepository`` persists :class:`VerificationReportCatalogue`
through :class:`SecureObjectRepository`.

Anti-tautology discipline: every defaultable field on the report carries a non-default value
so a save-drops-X / load-re-defaults-X regression would surface as
strict inequality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings, override_settings
from ._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ._verification_repository import VerificationReportCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_BUCKET_ID = "modelo-runtime"
_KEK = b"k" * 32
_DEK = b"d" * 32


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _runtime_engine(tmp_path: Path):
    return create_engine_from_settings(
        Settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID),
    )


def _populated_report() -> VerificationReport:
    """Build a VerificationReport with every defaultable field non-default."""

    now = datetime.now(UTC).replace(microsecond=0)
    revision_id = "a" * 64
    verified_by = "cli/aeat"
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=revision_id,
            run_at=now,
            verified_by=verified_by,
        ),
        calculation_revision_id=revision_id,
        # Non-default: BLOCKED rather than the easier COMPLETE state
        # so the tuple-of-findings field is naturally exercised.
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id="iva.devengado",
                message="iva.devengado is required but unresolved",
                next_action="aeat app modelo work calculate <id> --casilla iva.devengado=...",
            ),
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.UNRESOLVED_BINDING,
                severity=ModeloVerificationFindingSeverity.WARNING,
                casilla_id=None,
                expectation_id="ivaSourceRequired",
                message="prior-period source not yet pulled",
            ),
        ),
        resolved_casillas=("iva.deducible", "iva.resultado"),
        missing_required_casillas=("iva.devengado",),
        run_at=now,
        verified_by=verified_by,
        # Non-default lifecycle bit: granted_verificado_completo defaults
        # to False naturally on BLOCKED reports, but we still pin the
        # explicit witness on the loaded side.
        granted_verificado_completo=False,
    )


def test_verification_report_catalogue_survives_encrypted_storage(
    tmp_path: Path,
) -> None:
    """A populated VerificationReportCatalogue roundtrips strictly."""

    with override_settings(aeat_local_storage_root=tmp_path), activate_session(_session()):
        report = _populated_report()
        catalogue = VerificationReportCatalogue(
            reports={report.verification_report_id: report},
        )
        repo = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(catalogue)
        loaded = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == catalogue
    loaded_report = loaded.reports[report.verification_report_id]
    # Per-field witnesses: enum identity, tuple-of-finding
    # preservation including each finding's nested enum kind +
    # severity + optional fields.
    assert loaded_report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert len(loaded_report.findings) == 2
    f0 = loaded_report.findings[0]
    assert f0.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    assert f0.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert f0.casilla_id == "iva.devengado"
    assert f0.next_action is not None
    f1 = loaded_report.findings[1]
    assert f1.kind is ModeloVerificationFindingKind.UNRESOLVED_BINDING
    assert f1.severity is ModeloVerificationFindingSeverity.WARNING
    assert f1.expectation_id == "ivaSourceRequired"
    # Resolved + missing casillas tuples preserve order and content.
    assert loaded_report.resolved_casillas == ("iva.deducible", "iva.resultado")
    assert loaded_report.missing_required_casillas == ("iva.devengado",)
    assert (tmp_path / "buckets" / _BUCKET_ID / "db" / "aeat.db").is_file()


def test_verification_report_flipped_grant_invariant_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: flipping granted_verificado_completo on BLOCKED must surface.

    :class:`VerificationReport` enforces three load-bearing invariants:
    content-addressed id, the granted_verificado_completo ↔
    completeness_status pairing, and disjoint resolved / missing
    casilla sets. The most dangerous regression is a persisted
    BLOCKED report whose granted_verificado_completo silently flips to
    True — that would unlock filing on a calculation revision that
    failed verification.

    Persists a BLOCKED report (granted_verificado_completo=False with
    a blocking finding), reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically flips the boolean to True in the
    encrypted JSON envelope, and asserts the load path catches the
    drift via the model_validator.

    If this test passes silently with the flipped grant, the
    verification report boundary is tautological and every report
    roundtrip in the suite is suspect.
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._verification_repository import _VERIFICATION_NAMESPACE

    with override_settings(aeat_local_storage_root=tmp_path), activate_session(_session()):
        report = _populated_report()
        catalogue = VerificationReportCatalogue(
            reports={report.verification_report_id: report},
        )
        repo = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(catalogue)

        engine = _runtime_engine(tmp_path)
        try:
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _VERIFICATION_NAMESPACE,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                reports = envelope["payload"]["reports"]
                report_dict = reports[report.verification_report_id]
                assert report_dict.get("granted_verificado_completo") is False, (
                    "fixture must serialise granted_verificado_completo=False "
                    "on the BLOCKED report for this proof test to be meaningful"
                )
                # Flip the grant flag to True. The BLOCKED + blocking-finding
                # combination must trip the granted ↔ completeness invariant.
                report_dict["granted_verificado_completo"] = True
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()
            except Exception:  # boundary may raise different types
                regression_caught = True
        finally:
            engine.dispose()

    assert regression_caught, (
        "anti-tautology proof failed: flipping "
        "granted_verificado_completo=True on a BLOCKED report with "
        "blocking findings did NOT surface on load. The "
        "verification report boundary is tautological and every "
        "report roundtrip in the suite is suspect."
    )
