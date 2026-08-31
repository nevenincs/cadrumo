"""Strict roundtrip across the encrypted VerificationReportCatalogue boundary.

``VerificationReportCatalogueRepository`` persists :class:`VerificationReportCatalogue`
through :class:`SecureObjectRepository`.

Anti-tautology discipline: every defaultable field on the report carries a non-default value
so a save-drops-X / load-re-defaults-X regression would surface as
strict inequality.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.classification.policies import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ..verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ..verification_repository import VerificationReportPersistenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The registry definition is the sole authority for this namespace's identifier,
# singleton object key, and envelope schema version; the probe reads it rather
# than restating the values the repository under test writes at.
_VERIFICATION_NAMESPACE = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.namespace
_VERIFICATION_OBJECT_KEY = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.require_default_object_key()
_VERIFICATION_CATALOGUE_VERSION = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.schema_version
_BUCKET_ID = "df5dd25a-ff53-4086-9cc4-a13e61538a09"  # was 'modelo-runtime'


_IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.devengado")
_IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.deducible")
_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_IVA_RESOLVED_CASILLA_IDS = (_IVA_DEDUCIBLE_CASILLA, _IVA_RESULTADO_CASILLA)
_IVA_MISSING_REQUIRED_CASILLA_IDS = (_IVA_DEVENGADO_CASILLA,)
_TEST_FINDING_LEGAL_REFS = ("ley-58-2003:art-119",)
_REPORT_RUN_AT = datetime(2026, 5, 28, 11, 5, 0, tzinfo=UTC)
_LEGACY_KEY_REPORT_RUN_AT = datetime(2026, 5, 28, 11, 10, 0, tzinfo=UTC)
_CORRUPT_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 11, 15, 0, tzinfo=UTC)
_FUTURE_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 11, 20, 0, tzinfo=UTC)


_WORK_UNIT_ID = "9" * 64
_REVISION_CREATED_AT = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)


def _persist_parent_revision() -> str:
    """Persist the calculation revision the reports under test assess, and return its id.

    A verification report is a decision about one calculation revision, and
    the repository refuses reports whose parent is not in the same bucket.
    The fixture therefore stores a real parent rather than naming a synthetic
    id, so the roundtrip exercises the production shape.
    """
    revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        created_at=_REVISION_CREATED_AT,
        updated_at=_REVISION_CREATED_AT,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).save(
        CalculationRevisionCatalogue(revisions={revision_id: revision}),
    )
    return revision_id


def _populated_report(revision_id: str) -> VerificationReport:
    """Build a VerificationReport with every defaultable field non-default."""

    verified_by = "cli/aeat"
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=_IVA_DEVENGADO_CASILLA,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": str(_IVA_DEVENGADO_CASILLA)},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=None,
            expectation_id="iva-source-required",
            message_locale_key="application.modelo.findings.test_prior_period_source_missing",
            message_facts={"expectation_id": "iva-source-required"},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
    )
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=revision_id,
            # Non-default: BLOCKED rather than the easier COMPLETE state
            # so the tuple-of-findings field is naturally exercised.
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=findings,
            verified_by=verified_by,
        ),
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        resolved_casilla_ids=_IVA_RESOLVED_CASILLA_IDS,
        missing_required_casilla_ids=_IVA_MISSING_REQUIRED_CASILLA_IDS,
        run_at=_REPORT_RUN_AT,
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
        report = _populated_report(_persist_parent_revision())
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
    assert loaded_report.run_at == _REPORT_RUN_AT
    assert loaded_report.run_at.utcoffset() == UTC.utcoffset(loaded_report.run_at)
    assert len(loaded_report.findings) == 2
    f0 = loaded_report.findings[0]
    assert f0.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    assert f0.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert f0.casilla_id == _IVA_DEVENGADO_CASILLA
    f1 = loaded_report.findings[1]
    assert f1.kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert f1.severity is ModeloVerificationFindingSeverity.WARNING
    assert f1.expectation_id == "iva-source-required"
    # Resolved + missing casilla-id tuples preserve order and content.
    assert loaded_report.resolved_casilla_ids == _IVA_RESOLVED_CASILLA_IDS
    assert loaded_report.missing_required_casilla_ids == _IVA_MISSING_REQUIRED_CASILLA_IDS
    assert profile.paths.database_file.is_file()


@pytest.mark.parametrize(
    "run_at",
    (
        datetime(2026, 5, 28, 11, 5, 0),
        datetime(2026, 5, 28, 12, 5, 0, tzinfo=timezone(timedelta(hours=1))),
    ),
    ids=("naive", "non-utc"),
)
def test_verification_report_refuses_non_utc_run_at(run_at: datetime) -> None:
    """A report cannot be constructed with an ambiguous persisted run instant."""

    # Model-level construction only: no storage boundary is crossed, so this
    # case needs no persisted parent revision.
    report = _populated_report("a" * 64)
    with pytest.raises(ValidationError, match="datetime must be"):
        VerificationReport.model_validate({**report.model_dump(), "run_at": run_at})


@pytest.mark.parametrize(
    "persisted_run_at",
    ("2026-05-28T11:05:00", "2026-05-28T12:05:00+01:00"),
    ids=("naive", "non-utc"),
)
def test_verification_report_catalogue_refuses_non_utc_run_at_at_encrypted_load(
    tmp_path: Path,
    persisted_run_at: str,
) -> None:
    """Encrypted report storage cannot rehydrate an ambiguous run instant."""

    import json as _json

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        report = _populated_report(_persist_parent_revision())
        repo = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(VerificationReportCatalogue(reports={report.verification_report_id: report}))
        record = profile.repository.load(
            _VERIFICATION_NAMESPACE,
            _VERIFICATION_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_VERIFICATION_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        envelope["payload"]["reports"][report.verification_report_id]["run_at"] = persisted_run_at
        profile.repository.save(
            namespace=_VERIFICATION_NAMESPACE,
            object_key=_VERIFICATION_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError, match="datetime must be"):
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()


def test_verification_report_rejects_legacy_casilla_list_keys() -> None:
    """VerificationReport must not accept pre-canonical casilla list field names."""

    revision_id = "b" * 64
    verified_by = "cli/aeat"
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(),
        verified_by=verified_by,
    )

    with pytest.raises(ValidationError) as raised:
        VerificationReport.model_validate(
            {
                "verification_report_id": report_id,
                "calculation_revision_id": revision_id,
                "completeness_status": VerificationCompletenessStatus.BLOCKED,
                "findings": (),
                "resolved_casillas": _IVA_RESOLVED_CASILLA_IDS,
                "missing_required_casillas": _IVA_MISSING_REQUIRED_CASILLA_IDS,
                "run_at": _LEGACY_KEY_REPORT_RUN_AT,
                "verified_by": verified_by,
                "granted_verificado_completo": False,
            },
        )

    message = str(raised.value)
    assert "resolved_casillas" in message
    assert "missing_required_casillas" in message


def test_verification_finding_requires_legal_refs() -> None:
    """A finding is invalid unless it carries its legal grounding."""

    with pytest.raises(ValidationError) as raised:
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=(),
        )

    assert "legal_refs" in str(raised.value)


def test_verification_finding_refuses_retired_free_form_recovery_text() -> None:
    """The persisted domain finding carries facts, never operator command prose."""

    with pytest.raises(ValidationError, match="next_action"):
        ModeloVerificationFinding.model_validate(
            {
                "kind": ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
                "severity": ModeloVerificationFindingSeverity.BLOCKING,
                "casilla_id": _IVA_DEVENGADO_CASILLA,
                "message_locale_key": "application.modelo.findings.missing_required_casilla",
                "message_facts": {"casilla_id": str(_IVA_DEVENGADO_CASILLA)},
                "next_action": "aeat app modelo work calculate",
                "legal_refs": _TEST_FINDING_LEGAL_REFS,
            },
        )


def test_verification_finding_refuses_retired_message_prose() -> None:
    """The domain record has no compatibility field for rendered text."""
    with pytest.raises(ValidationError, match="message"):
        ModeloVerificationFinding.model_validate(
            {
                "kind": ModeloVerificationFindingKind.BLOCKING_RULE,
                "severity": ModeloVerificationFindingSeverity.BLOCKING,
                "message": "rendered prose",
                "message_locale_key": "application.modelo.findings.test_blocked",
                "message_facts": {},
                "legal_refs": _TEST_FINDING_LEGAL_REFS,
            },
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("message_locale_key", "Rendered prose"),
        ("message_facts", {"next_hint": "operator.modelo.calculate"}),
        ("message_facts", {"reason_code": "human readable prose"}),
    ),
)
def test_verification_finding_rejects_presentation_in_locale_neutral_fields(
    field: str,
    value: object,
) -> None:
    payload: dict[str, object] = {
        "kind": ModeloVerificationFindingKind.BLOCKING_RULE,
        "severity": ModeloVerificationFindingSeverity.BLOCKING,
        "message_locale_key": "application.modelo.findings.test_blocked",
        "message_facts": {"reason_code": "blocked"},
        "legal_refs": _TEST_FINDING_LEGAL_REFS,
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        ModeloVerificationFinding.model_validate(payload)


def test_verification_finding_rejects_blank_grounding_refs() -> None:
    """Finding provenance entries must be registry ids, not blank strings."""
    with pytest.raises(ValidationError, match="legal_refs"):
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=(" ",),
        )
    with pytest.raises(ValidationError, match="source_refs"):
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
            source_refs=(" ",),
        )


def test_report_id_is_clock_free_for_an_identical_outcome() -> None:
    """Two reports with an identical outcome but different run_at share one id.

    The id derivation takes no clock; it is content-addressed by the outcome.
    Constructing two reports that differ ONLY in run_at must therefore yield the
    same id (the model validator accepts both), so an identical-outcome verify
    retry collapses on upsert instead of accumulating.
    """
    revision_id = "c" * 64
    verified_by = "cli/aeat"
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.test_reconciliation_mismatch",
            message_facts={},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
    )
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        verified_by=verified_by,
    )
    report_early = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        verified_by=verified_by,
        granted_verificado_completo=False,
    )
    report_late = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
        verified_by=verified_by,
        granted_verificado_completo=False,
    )
    assert report_early.verification_report_id == report_late.verification_report_id == report_id
    assert report_early.run_at != report_late.run_at


def test_report_id_diverges_when_findings_change() -> None:
    """A changed findings tuple (same revision and actor) yields a distinct id.

    The findings tuple is part of the outcome identity, so a re-verify whose
    findings differ produces a new distinct report rather than colliding with
    the prior one.
    """
    revision_id = "d" * 64
    verified_by = "cli/aeat"
    base_finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.test_reconciliation_mismatch",
        message_facts={},
        legal_refs=_TEST_FINDING_LEGAL_REFS,
    )
    extra_finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=_IVA_DEVENGADO_CASILLA,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": str(_IVA_DEVENGADO_CASILLA)},
        legal_refs=_TEST_FINDING_LEGAL_REFS,
    )
    id_one = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(base_finding,),
        verified_by=verified_by,
    )
    id_two = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(base_finding, extra_finding),
        verified_by=verified_by,
    )
    assert id_one != id_two


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        report = _populated_report(_persist_parent_revision())
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


def test_verification_report_catalogue_wrong_inner_classification_is_localized(
    tmp_path: Path,
) -> None:
    """A corrupted envelope classification raises a translated persistence error."""

    from ....adapters.persistence.storage.envelope._envelope import Envelope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[VerificationReportCatalogue](
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.AUDIT,
            payload=VerificationReportCatalogue(),
        )
        profile.repository.save(
            namespace=_VERIFICATION_NAMESPACE,
            object_key=_VERIFICATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(VerificationReportPersistenceError) as raised:
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_verification_report_persistence"
    assert raised.value.context == {
        "reason": "classification_mismatch",
        "expected_classification": "financial",
        "actual_classification": "audit",
    }


def test_verification_report_catalogue_unsupported_storage_version_is_localized(
    tmp_path: Path,
) -> None:
    """A future inner envelope schema version raises a translated persistence error."""

    from ....adapters.persistence.storage.envelope._envelope import Envelope

    stored_schema_version = _VERIFICATION_CATALOGUE_VERSION + 1
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[VerificationReportCatalogue](
            schema_version=stored_schema_version,
            written_at=_FUTURE_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=VerificationReportCatalogue(),
        )
        profile.repository.save(
            namespace=_VERIFICATION_NAMESPACE,
            object_key=_VERIFICATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(VerificationReportPersistenceError) as raised:
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_verification_report_persistence"
    assert raised.value.context == {
        "reason": "unsupported_envelope_version",
        "stored_schema_version": stored_schema_version,
        "max_supported_version": _VERIFICATION_CATALOGUE_VERSION,
    }


def test_report_for_a_revision_outside_this_bucket_is_refused_at_save(
    tmp_path: Path,
) -> None:
    """A report whose parent revision is not in this bucket is not persistable.

    A verification report asserts an audit outcome *about* one calculation
    revision. Detached from that parent it claims to have verified something
    this bucket cannot produce, so the write boundary refuses it rather than
    storing a decision nothing can be checked against.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _persist_parent_revision()
        foreign = _populated_report("f" * 64)
        catalogue = VerificationReportCatalogue(reports={foreign.verification_report_id: foreign})

        with pytest.raises(VerificationReportPersistenceError) as raised:
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).save(catalogue)

    assert raised.value.context == {
        "reason": "foreign_calculation_revision",
        "boundary": "save",
        "calculation_revision_ids": ["f" * 64],
    }


def test_report_for_a_missing_revision_is_refused_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: the binding is durable, not construction-time only.

    Persists a report against a real parent, then removes the parent from the
    calculation catalogue in the same bucket. If the read path still returned
    the report, the save-side check would only be a convention held by callers
    that happen to write in order.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        revision_id = _persist_parent_revision()
        report = _populated_report(revision_id)
        VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).save(
            VerificationReportCatalogue(reports={report.verification_report_id: report}),
        )
        assert (
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID)
            .load()
            .get(
                report.verification_report_id,
            )
            == report
        )

        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).save(CalculationRevisionCatalogue())

        with pytest.raises(VerificationReportPersistenceError) as raised:
            VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.context == {
        "reason": "foreign_calculation_revision",
        "boundary": "load",
        "calculation_revision_ids": [revision_id],
    }
