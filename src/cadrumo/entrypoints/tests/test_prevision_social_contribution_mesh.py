"""Contribution certificates recorded through the registered executor feed the real pension contribution source.

The executor runs against the real encrypted repository, the real write path, the
real attachment custody and the pinned authority; only the operation host's event
and operand plumbing is a recording stand-in. Every ejercicio comes from the
published support envelope, and the box each clave reaches is the textual match of
the Modelo 345 subclave wording and the Modelo 100 box wording, written here as an
independent oracle. All identifiers, files and amounts are synthetic.
"""

from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.prevision_social_contribution_evidence_custody import (
    PrevisionSocialContributionEvidenceCustodyAdapter,
)
from cadrumo.adapters.persistence.profile.prevision_social_contribution_records import (
    PrevisionSocialContributionRecordRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.prevision_social_contribution_repository import (
    PinnedPrevisionSocialContributionWriteAuthority,
)
from cadrumo.application.aggregation.prevision_social_contribution_source import (
    PrevisionSocialContributionSourceResolver,
)
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from cadrumo.application.prevision_social_contribution.executor import PrevisionSocialContributionExecutor
from cadrumo.application.prevision_social_contribution.ports import PrevisionSocialPorts
from cadrumo.application.prevision_social_contribution.requests import (
    PrevisionSocialListRequest,
    PrevisionSocialRecordRequest,
    PrevisionSocialRemoveRequest,
)
from cadrumo.application.prevision_social_contribution.results import (
    PrevisionSocialOperationExecutionResult,
    PrevisionSocialRowProjection,
)
from cadrumo.application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
    profile_operation_request,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.identity.bucket import canonical_bucket_id
from cadrumo.core.operations import OperationEffect
from cadrumo.core.period import Period
from cadrumo.core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.prevision_social_contribution_bindings import (
    prevision_social_contribution_binding_by_casilla,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = "4a2d9c3f-6e5b-4f7c-8d9e-1b2c3d4e5f60"
# Synthetic CIFs whose control digit is hand-derived: with every digit before it zero but the last two, the
# control is (10 - (d4 + digit-sum(2 * d7) + d6)) mod 10, so 0001008 -> 2, 0001009 -> 0 and 0001016 -> 5.
_ISSUER = "V00010082"
_PLAN_A = "V00010090"
_PLAN_B = "V00010165"
_WRONG_CONTROL = "V00000001"
_C = PrevisionSocialClave
_S = PrevisionSocialSubclave


def _year(operation: PinnedAuthorityOperation) -> int:
    return min(operation.supported_filing_years().years)


def _repository() -> PrevisionSocialContributionRecordRepositoryAdapter:
    return PrevisionSocialContributionRecordRepositoryAdapter(objects=secure_object_repository_for_active_bucket())


def _custody() -> PrevisionSocialContributionEvidenceCustodyAdapter:
    bucket_id = canonical_bucket_id(_PROFILE)
    return PrevisionSocialContributionEvidenceCustodyAdapter(
        store=AttachmentStore(bucket_id=bucket_id, objects=secure_object_repository_for_active_bucket()),
        bucket_id=bucket_id,
    )


def _ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> PrevisionSocialPorts:
    del profile_id
    return PrevisionSocialPorts(
        repository=_repository(),
        authority=PinnedPrevisionSocialContributionWriteAuthority(operation),
        custody=_custody(),
    )


def _certificate(directory: Path, name: str) -> bytes:
    data = f"%PDF-1.4 synthetic pension contribution certificate {name}".encode()
    (directory / name).write_bytes(data)
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Run:
    """One execution's outcome and what the operation reported on its way."""

    def __init__(self, outcome: object, events: RecordingEvents, operands: RecordingOperands) -> None:
        self.outcome = outcome
        self.effects = events.effects
        (stored,) = operands.stored
        assert isinstance(stored, PrevisionSocialOperationExecutionResult)
        self.result = stored

    @property
    def refused(self) -> bool:
        return isinstance(self.outcome, OperationRefusalEvidence)

    @property
    def reason(self) -> str:
        assert self.result.refusal is not None
        return self.result.refusal.reason

    @property
    def row(self) -> PrevisionSocialRowProjection:
        assert self.result.row is not None
        return self.result.row


def _execute(operation: PinnedAuthorityOperation, definition_id: str, payload: BaseModel) -> _Run:
    events = RecordingEvents()
    operands = RecordingOperands("d" * 64)
    context = executor_context(
        definition_id,
        profile_id=_PROFILE,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=events,
        operands=operands,
    )
    executor = PrevisionSocialContributionExecutor(_ports, definition_id=definition_id)
    outcome = asyncio.run(executor.execute(profile_operation_request(payload, definition_id, _PROFILE), context))
    return _Run(outcome, events, operands)


def _record(
    operation: PinnedAuthorityOperation,
    clave: PrevisionSocialClave,
    subclave: PrevisionSocialSubclave | None,
    amount: str,
    *,
    directory: Path | None = None,
    file: str | None = None,
    fingerprint: str | None = None,
    plan: str | None = _PLAN_A,
    same_plan: bool | None = None,
    issuer: str = _ISSUER,
    beneficiary: PrevisionSocialBeneficiario = PrevisionSocialBeneficiario.TAXPAYER,
    expected_revision: str | None = None,
) -> _Run:
    return _execute(
        operation,
        PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
        PrevisionSocialRecordRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_year(operation),
            issuer_tax_id=issuer,
            issuer_legal_name="Gestora Sintetica SA",
            plan_tax_id=plan,
            plan_name=None if plan is None else "Plan Sintetico",
            clave=clave,
            subclave=subclave,
            amount=PublicDecimal(decimal=amount),
            beneficiary=beneficiary,
            employer_contributed_to_same_plan=same_plan,
            evidence_fingerprint=fingerprint,
            source_path=file,
            source_directory=None if directory is None else str(directory),
            expected_revision_id=expected_revision,
        ),
    )


def _list(operation: PinnedAuthorityOperation) -> _Run:
    return _execute(
        operation,
        PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
        PrevisionSocialListRequest(profile_id=UUID(_PROFILE), ejercicio=_year(operation)),
    )


def _remove(operation: PinnedAuthorityOperation, row: PrevisionSocialRowProjection, revision: str) -> _Run:
    return _execute(
        operation,
        PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
        PrevisionSocialRemoveRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=row.ejercicio,
            issuer_ref=row.issuer_ref,
            plan_ref=row.plan_ref,
            clave=row.clave,
            subclave=row.subclave,
            expected_revision_id=revision,
        ),
    )


def _box_values(operation: PinnedAuthorityOperation) -> dict[str, Decimal]:
    year = _year(operation)
    revision = operation.snapshot(
        "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    resolution = PrevisionSocialContributionSourceResolver(repository=_repository()).resolve(
        CalculationSourceContext(
            bucket_id=canonical_bucket_id(_PROFILE),
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=revision,
            operation=operation,
        )
    )
    boxes = {
        binding: str(casilla) for casilla, binding in prevision_social_contribution_binding_by_casilla(revision).items()
    }
    return {boxes[binding]: value for binding, value in resolution.binding_values.items()}


def test_recorded_certificates_reach_their_boxes_in_the_real_source_and_list_without_tax_ids(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    for name in ("a.pdf", "j-same.pdf", "j-other.pdf"):
        _certificate(files, name)
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        own = _record(operation, _C.CLAVE_A, _S.SUBCLAVE_01, "1000.00", directory=files, file="a.pdf")
        same = _record(
            operation, _C.CLAVE_J, _S.SUBCLAVE_01, "400.00", directory=files, file="j-same.pdf", same_plan=True
        )
        other = _record(
            operation,
            _C.CLAVE_J,
            _S.SUBCLAVE_01,
            "100.00",
            directory=files,
            file="j-other.pdf",
            plan=_PLAN_B,
            same_plan=False,
        )
        listed = _list(operation)
        boxes = _box_values(operation)

    assert [run.refused for run in (own, same, other)] == [False, False, False]
    assert [run.effects[-1] for run in (own, same, other)] == [OperationEffect.UPDATED] * 3
    assert (own.row.casilla_id, same.row.casilla_id, other.row.casilla_id) == ("0465", "0426", "0465")
    assert other.result.count == 3
    # Hand sums: 0465 holds the worker's own 1.000,00 and the J.01 100,00 with no employer in that plan.
    assert boxes == {"0465": Decimal("1100.00"), "0426": Decimal("400.00")}
    assert listed.effects == [OperationEffect.NONE]
    assert listed.result.rows is not None
    assert len(listed.result.rows) == 3
    assert listed.result.ejercicios == tuple(sorted(operation.supported_filing_years().years))
    dumped = listed.result.model_dump_json()
    for tax_id in (_ISSUER, _PLAN_A, _PLAN_B):
        assert tax_id not in dumped


def test_a_clave_the_edition_places_in_no_box_is_refused_at_record_time_and_keeps_no_bytes(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    unplaced = _certificate(files, "d.pdf")
    unstated = _certificate(files, "j.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        refused_d = _record(operation, _C.CLAVE_D, _S.SUBCLAVE_01, "300.00", directory=files, file="d.pdf")
        refused_j = _record(operation, _C.CLAVE_J, _S.SUBCLAVE_01, "300.00", directory=files, file="j.pdf")
        refused_spouse = _record(
            operation,
            _C.CLAVE_A,
            _S.SUBCLAVE_01,
            "300.00",
            directory=files,
            file="d.pdf",
            beneficiary=PrevisionSocialBeneficiario.SPOUSE,
        )
        kept = (_custody().holds(_sha256(unplaced)), _custody().holds(_sha256(unstated)))
        stored = _repository().list_revisioned(_year(operation))

    assert (refused_d.reason, refused_j.reason, refused_spouse.reason) == (
        "unplaced_clave",
        "same_plan_split_unstated",
        "beneficiary_out_of_scope",
    )
    assert all(
        run.refused and run.effects[-1] is OperationEffect.NONE for run in (refused_d, refused_j, refused_spouse)
    )
    assert kept == (False, False)
    assert stored == ()


def test_a_correction_needs_the_listed_revision_and_names_the_certificate_it_replaces(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    first_bytes = _certificate(files, "first.pdf")
    second_bytes = _certificate(files, "second.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        first = _record(operation, _C.CLAVE_A, _S.SUBCLAVE_01, "1000.00", directory=files, file="first.pdf")
        unguarded = _record(operation, _C.CLAVE_A, _S.SUBCLAVE_01, "1200.00", directory=files, file="second.pdf")
        stale = _record(
            operation,
            _C.CLAVE_A,
            _S.SUBCLAVE_01,
            "1200.00",
            directory=files,
            file="second.pdf",
            expected_revision="f" * 64,
        )
        corrected = _record(
            operation,
            _C.CLAVE_A,
            _S.SUBCLAVE_01,
            "1200.00",
            directory=files,
            file="second.pdf",
            expected_revision=first.row.revision_id,
        )
        boxes = _box_values(operation)

    assert (unguarded.reason, stale.reason) == ("stale_revision", "stale_revision")
    assert unguarded.result.refusal is not None
    assert unguarded.result.refusal.code == "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_REVISION_CONFLICT"
    assert not corrected.refused
    assert corrected.result.count == 1
    assert corrected.row.issuer_ref == first.row.issuer_ref
    assert corrected.row.revision_id != first.row.revision_id
    assert corrected.row.evidence_fingerprint == _sha256(second_bytes)
    assert corrected.row.replaces_evidence_fingerprint == _sha256(first_bytes)
    assert boxes == {"0465": Decimal("1200.00")}


def test_a_removal_needs_the_listed_revision_and_a_second_removal_finds_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    _certificate(files, "a.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        recorded = _record(operation, _C.CLAVE_A, _S.SUBCLAVE_01, "500.00", directory=files, file="a.pdf", plan=None)
        stale = _remove(operation, recorded.row, "e" * 64)
        removed = _remove(operation, recorded.row, recorded.row.revision_id)
        missing = _remove(operation, recorded.row, recorded.row.revision_id)
        stored = _repository().list_revisioned(_year(operation))

    assert recorded.row.plan_ref is None
    assert stale.reason == "stale_revision"
    assert stale.effects[-1] is OperationEffect.NONE
    assert not removed.refused
    assert removed.result.count == 0
    assert removed.effects[-1] is OperationEffect.UPDATED
    assert missing.reason == "not_found"
    assert stored == ()


def test_requests_the_record_cannot_represent_are_refused_before_anything_is_kept(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate(files, "a.pdf")
    (files / "empty.pdf").write_bytes(b"")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        reasons = {
            "clave_pair_undefined": _record(
                operation, _C.CLAVE_B, _S.SUBCLAVE_01, "10.00", directory=files, file="a.pdf"
            ),
            "validation": _record(
                operation, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00", directory=files, file="a.pdf", issuer=_WRONG_CONTROL
            ),
            "certificate_fingerprint_required": _record(operation, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00"),
            "certificate_not_in_custody": _record(
                operation, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00", fingerprint=_sha256(b"never kept")
            ),
            "certificate_fingerprint_mismatch": _record(
                operation,
                _C.CLAVE_A,
                _S.SUBCLAVE_01,
                "10.00",
                directory=files,
                file="a.pdf",
                fingerprint=_sha256(b"another file"),
            ),
            "certificate_file_unreadable": _record(
                operation, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00", directory=files, file="empty.pdf"
            ),
            "validation_amount": _record(
                operation, _C.CLAVE_A, _S.SUBCLAVE_01, "10.005", directory=files, file="a.pdf"
            ),
        }
        kept = _custody().holds(_sha256(data))
        stored = _repository().list_revisioned(_year(operation))

    assert {name: run.reason for name, run in reasons.items()} == {
        "clave_pair_undefined": "clave_pair_undefined",
        "validation": "validation",
        "certificate_fingerprint_required": "certificate_fingerprint_required",
        "certificate_not_in_custody": "certificate_not_in_custody",
        "certificate_fingerprint_mismatch": "certificate_fingerprint_mismatch",
        "certificate_file_unreadable": "certificate_file_unreadable",
        "validation_amount": "validation",
    }
    assert all(run.effects[-1] is OperationEffect.NONE for run in reasons.values())
    assert not kept
    assert stored == ()


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_placement_refusal_serves_the_placement_words_with_the_door_to_enter_the_box(
    tmp_path: Path, operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    _certificate(files, "d.pdf")
    with (
        override_settings(cadrumo_output_language=language.value),
        isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE),
    ):
        refused = _record(operation, _C.CLAVE_D, _S.SUBCLAVE_01, "300.00", directory=files, file="d.pdf")

    refusal = refused.result.refusal
    assert refusal is not None
    assert refusal.refusal_words_language is language
    assert refusal.refusal_words == tr(
        "aggregation.prevision_social_contribution.served.unplaced_clave", locale=language.value
    )
    assert not refusal.refusal_words.startswith("aggregation.")
    assert str(tmp_path) not in refusal.refusal_words
