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
from pydantic import ValidationError

from ...adapters.persistence.storage import SensitivityClass
from ...tests.secure_sql import isolated_runtime_profile
from ._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ._verification_repository import (
    _VERIFICATION_CATALOGUE_VERSION,
    _VERIFICATION_OBJECT_KEY,
    VerificationReportCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_BUCKET_ID = "modelo-runtime"


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
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
    assert (profile.paths.db_dir / "aeat.db").is_file()


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
    a blocking finding), reloads the runtime-owned secure object,
    surgically flips the boolean to True in the encrypted JSON
    envelope, and asserts the load path catches the drift via the
    model_validator.

    If this test passes silently with the flipped grant, the
    verification report boundary is tautological and every report
    roundtrip in the suite is suspect.
    """

    import json as _json

    from ._verification_repository import _VERIFICATION_NAMESPACE

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        report = _populated_report()
        catalogue = VerificationReportCatalogue(
            reports={report.verification_report_id: report},
        )
        repo = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(catalogue)

        record = profile.repository.load(
            _VERIFICATION_NAMESPACE,
            _VERIFICATION_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_VERIFICATION_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        reports = envelope["payload"]["reports"]
        report_dict = reports[report.verification_report_id]
        assert report_dict.get("granted_verificado_completo") is False, (
            "fixture must serialise granted_verificado_completo=False "
            "on the BLOCKED report for this proof test to be meaningful"
        )
        # Flip the grant flag to True. The BLOCKED + blocking-finding
        # combination must trip the granted ↔ completeness invariant.
        report_dict["granted_verificado_completo"] = True
        profile.repository.save(
            namespace=_VERIFICATION_NAMESPACE,
            object_key=_VERIFICATION_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError):
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()
