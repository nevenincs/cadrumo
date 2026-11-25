"""Pension contribution records through the real encrypted store, write path and source resolver.

All tax identifiers and amounts are synthetic. The boxes each Modelo 345 clave
and subclave reaches are the textual matches of the subclave wording and the
Modelo 100 dictionary wording, written here as an independent oracle; each box
total is worked by hand from the records placed in it. Every ejercicio comes
from the published support envelope.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.prevision_social_contribution_repository import (
    PinnedPrevisionSocialContributionWriteAuthority,
    PrevisionSocialContributionRevisionConflictError,
    PrevisionSocialContributionWriteRefusedError,
    prevision_social_contribution_record_key,
    record_prevision_social_contribution,
)
from .....application.aggregation.prevision_social_contribution_source import (
    PrevisionSocialContributionSourceResolver,
)
from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.bucket_pointer import require_active_bucket_id
from .....core.casilla_id import validated_casilla_id
from .....core.external_constants import UTF_8_ENCODING
from .....core.identity.bucket import canonical_bucket_id
from .....core.period import Period
from .....core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.prevision_social_contribution_bindings import (
    prevision_social_contribution_binding_by_casilla,
)
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from .....domain.renta.prevision_social_contribution import PrevisionSocialContribution
from ...storage.attachment import AttachmentStore
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..prevision_social_contribution_evidence_custody import PrevisionSocialContributionEvidenceCustodyAdapter
from ..prevision_social_contribution_records import PrevisionSocialContributionRecordRepositoryAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_C = PrevisionSocialClave
_S = PrevisionSocialSubclave
_ISSUER = "V00010080"
_PLAN_A = "V00010090"
_PLAN_B = "V00010091"
_SECOND_PROFILE = "22222222-2222-4222-8222-222222222222"


def _years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    return tuple(sorted(operation.supported_filing_years().years))


def _revision(operation: PinnedAuthorityOperation, year: int) -> ModeloRevision:
    return operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION).revision


def _repository() -> PrevisionSocialContributionRecordRepositoryAdapter:
    return PrevisionSocialContributionRecordRepositoryAdapter(objects=secure_object_repository_for_active_bucket())


def _custody() -> PrevisionSocialContributionEvidenceCustodyAdapter:
    bucket_id = canonical_bucket_id(require_active_bucket_id())
    return PrevisionSocialContributionEvidenceCustodyAdapter(
        store=AttachmentStore(bucket_id=bucket_id, objects=secure_object_repository_for_active_bucket()),
        bucket_id=bucket_id,
    )


def _certificate(label: str) -> str:
    return _custody().ingest(
        source_path=Path("synthetic-certificate.pdf"),
        data=f"synthetic contribution certificate {label}".encode(),
        mime_type="application/pdf",
        captured_at=datetime.now(UTC),
    )


def _record(
    repository: PrevisionSocialContributionRecordRepositoryAdapter,
    year: int,
    clave: PrevisionSocialClave,
    subclave: PrevisionSocialSubclave | None,
    amount: str,
    *,
    plan: str = _PLAN_A,
    same_plan: bool | None = None,
    beneficiary: PrevisionSocialBeneficiario = PrevisionSocialBeneficiario.TAXPAYER,
    fingerprint: str | None = None,
    replaces: str | None = None,
) -> PrevisionSocialContribution:
    return PrevisionSocialContribution(
        ejercicio=year,
        issuer_tax_id=_ISSUER,
        issuer_legal_name="Gestora Sintetica SA",
        issuer_ref=repository.issuer_reference(_ISSUER),
        plan_tax_id=plan,
        plan_name="Plan Sintetico",
        plan_ref=repository.plan_reference(plan),
        clave=clave,
        subclave=subclave,
        amount=Decimal(amount),
        beneficiary=beneficiary,
        employer_contributed_to_same_plan=same_plan,
        evidence_fingerprint=fingerprint or _certificate(f"{clave}-{subclave}-{plan}-{amount}"),
        replaces_evidence_fingerprint=replaces,
        captured_at=datetime.now(UTC),
    )


def _write(
    repository: PrevisionSocialContributionRecordRepositoryAdapter,
    record: PrevisionSocialContribution,
    operation: PinnedAuthorityOperation,
    *,
    expected_revision_id: str = ABSENT_SECURE_OBJECT_REVISION_ID,
) -> None:
    record_prevision_social_contribution(
        record,
        repository=repository,
        authority=PinnedPrevisionSocialContributionWriteAuthority(operation),
        custody=_custody(),
        expected_revision_id=expected_revision_id,
    )


def _resolve(
    repository: PrevisionSocialContributionRecordRepositoryAdapter,
    operation: PinnedAuthorityOperation,
    year: int,
    *,
    typed: tuple[str, ...] = (),
) -> CalculationSourceResolution:
    context = CalculationSourceContext(
        bucket_id=canonical_bucket_id(require_active_bucket_id()),
        modelo="100",
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        revision=_revision(operation, year),
        operation=operation,
        caller_casilla_ids=frozenset(validated_casilla_id(casilla) for casilla in typed),
    )
    return PrevisionSocialContributionSourceResolver(repository=repository).resolve(context)


def _box_values(resolution: CalculationSourceResolution, revision: ModeloRevision) -> dict[str, Decimal]:
    boxes = {
        binding_id: str(casilla_id)
        for casilla_id, binding_id in prevision_social_contribution_binding_by_casilla(revision).items()
    }
    return {boxes[binding_id]: value for binding_id, value in resolution.binding_values.items()}


def _sentences(resolution: CalculationSourceResolution) -> dict[CalculationNoteSentence, set[str]]:
    found: dict[CalculationNoteSentence, set[str]] = {}
    for diagnostic in resolution.diagnostics:
        if diagnostic.fact is not None:
            found.setdefault(diagnostic.fact.sentence, set()).add(str(diagnostic.casilla_id))
    return found


def test_a_record_survives_the_encrypted_store_and_no_tax_id_is_plaintext(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    year = _years(operation)[0]
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = _repository()
        record = _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "1000.00")
        _write(repository, record, operation)

        assert repository.load_records(year) == (record,)
        assert repository.load_records(year + 1) == ()
        stored, revision_id = repository.load_revisioned(record.identity)
        assert stored == record
        assert revision_id != ABSENT_SECURE_OBJECT_REVISION_ID

        key = prevision_social_contribution_record_key(record.identity)
        assert key == f"{year}:{record.issuer_ref}:{record.plan_ref}:A:01"
        for tax_id in (_ISSUER, _PLAN_A):
            unkeyed = hashlib.sha256(tax_id.encode(UTF_8_ENCODING)).hexdigest()
            assert tax_id not in key
            assert unkeyed not in {record.issuer_ref, record.plan_ref}

        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())
        assert _ISSUER.encode(UTF_8_ENCODING) not in on_disk
        assert _PLAN_A.encode(UTF_8_ENCODING) not in on_disk
        assert b"Gestora Sintetica" not in on_disk


def test_the_references_are_stable_within_a_profile_and_differ_across_profiles(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path / "first"):
        first = _repository()
        issuer = first.issuer_reference(_ISSUER)
        assert first.issuer_reference(f"  {_ISSUER.lower()} ") == issuer
        assert first.plan_reference(_ISSUER) != issuer
        assert first.issuer_reference(_PLAN_A) != issuer
    with isolated_runtime_profile(tmp_path=tmp_path / "second", bucket_id=_SECOND_PROFILE):
        assert _repository().issuer_reference(_ISSUER) != issuer


@pytest.mark.parametrize(
    ("clave", "subclave", "beneficiary", "reason"),
    [
        (_C.CLAVE_D, _S.SUBCLAVE_01, PrevisionSocialBeneficiario.TAXPAYER, "unplaced_clave"),
        (_C.CLAVE_B, None, PrevisionSocialBeneficiario.TAXPAYER, "indirect_match"),
        (_C.CLAVE_J, _S.SUBCLAVE_01, PrevisionSocialBeneficiario.TAXPAYER, "same_plan_split_unstated"),
        (_C.CLAVE_A, _S.SUBCLAVE_01, PrevisionSocialBeneficiario.SPOUSE, "beneficiary_out_of_scope"),
    ],
)
def test_a_record_the_edition_does_not_place_is_refused_before_it_is_stored(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    clave: PrevisionSocialClave,
    subclave: PrevisionSocialSubclave | None,
    beneficiary: PrevisionSocialBeneficiario,
    reason: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        for year in _years(operation):
            record = _record(repository, year, clave, subclave, "300.00", beneficiary=beneficiary)
            with pytest.raises(PrevisionSocialContributionWriteRefusedError) as refused:
                _write(repository, record, operation)
            assert refused.value.reason == reason, year
            assert repository.load_records(year) == ()


def test_an_ejercicio_outside_the_envelope_is_refused(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    below = _years(operation)[0] - 1
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        with pytest.raises(PrevisionSocialContributionWriteRefusedError) as refused:
            _write(repository, _record(repository, below, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00"), operation)
        assert refused.value.reason == "ejercicio_unsupported"
        assert repository.load_records(below) == ()


def test_a_certificate_outside_custody_and_a_forged_reference_are_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    year = _years(operation)[0]
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        absent = _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00", fingerprint="d" * 64)
        with pytest.raises(PrevisionSocialContributionWriteRefusedError) as refused:
            _write(repository, absent, operation)
        assert refused.value.reason == "certificate_not_in_custody"

        forged = _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "10.00").model_copy(
            update={"issuer_ref": hashlib.sha256(_ISSUER.encode(UTF_8_ENCODING)).hexdigest()}
        )
        with pytest.raises(PrevisionSocialContributionWriteRefusedError) as refused:
            _write(repository, forged, operation)
        assert refused.value.reason == "identity_mismatch"
        assert repository.load_records(year) == ()


def test_a_correction_needs_the_read_revision_and_the_replaced_certificate(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    year = _years(operation)[0]
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        first = _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "1000.00")
        _write(repository, first, operation)
        _stored, revision_id = repository.load_revisioned(first.identity)

        corrected = _record(
            repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "1100.00", replaces=first.evidence_fingerprint
        )
        with pytest.raises(PrevisionSocialContributionRevisionConflictError):
            _write(repository, corrected, operation)
        unanchored = corrected.model_copy(update={"replaces_evidence_fingerprint": None})
        with pytest.raises(PrevisionSocialContributionWriteRefusedError) as refused:
            _write(repository, unanchored, operation, expected_revision_id=revision_id)
        assert refused.value.reason == "identity_mismatch"

        _write(repository, corrected, operation, expected_revision_id=revision_id)
        assert repository.load_records(year) == (corrected,)

        _stored, corrected_revision = repository.load_revisioned(corrected.identity)
        with pytest.raises(PrevisionSocialContributionRevisionConflictError):
            repository.delete_revisioned(corrected.identity, expected_revision_id=revision_id)
        repository.delete_revisioned(corrected.identity, expected_revision_id=corrected_revision)
        assert repository.load_records(year) == ()


def test_each_box_sums_the_records_placed_in_it_in_every_supported_year(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The same-plan answer sends one J.01 contribution to 0426 and another to 0465."""
    years = _years(operation)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        for year in years:
            for record in (
                _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "1000.00"),
                _record(repository, year, _C.CLAVE_F, _S.SUBCLAVE_01, "250.50"),
                _record(repository, year, _C.CLAVE_J, _S.SUBCLAVE_01, "400.00", same_plan=True),
                _record(repository, year, _C.CLAVE_J, _S.SUBCLAVE_01, "100.00", plan=_PLAN_B, same_plan=False),
                _record(repository, year, _C.CLAVE_C, _S.SUBCLAVE_01, "600.00"),
                _record(repository, year, _C.CLAVE_L, _S.SUBCLAVE_01, "75.25"),
            ):
                _write(repository, record, operation)

        for year in years:
            resolution = _resolve(repository, operation, year)
            assert _box_values(resolution, _revision(operation, year)) == {
                "0465": Decimal("1350.50"),
                "0426": Decimal("400.00"),
                "0427": Decimal("600.00"),
                "0466": Decimal("75.25"),
            }, year
            assert len(resolution.provenance) == 6, year
            empty = set(resolution.unresolved_binding_ids)
            assert empty == set(resolution.inapplicable_binding_ids), year
            assert {
                str(casilla)
                for casilla, binding in prevision_social_contribution_binding_by_casilla(
                    _revision(operation, year)
                ).items()
                if binding in empty
            } == {"0438", "0499"}, year


def test_a_box_placed_only_by_an_earlier_years_texts_stays_calculation_grade(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The first placing edition cites its own texts; a later year inherits those rows unchanged."""
    first, *later = _years(operation)
    assert later
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        for year in (first, *later):
            _write(repository, _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "500.00"), operation)

        own = _resolve(repository, operation, first)
        assert CalculationNoteSentence.PREVISION_SOCIAL_PLACEMENT_INHERITED not in _sentences(own)
        assert not [item for item in own.diagnostics if item.reason == "advisory_binding_value"]

        for year in later:
            inherited_row = next(
                row for row in _revision(operation, year).prevision_social_placements if row.id == "a-01"
            )
            first_row = next(row for row in _revision(operation, first).prevision_social_placements if row.id == "a-01")
            assert inherited_row == first_row, year
            resolution = _resolve(repository, operation, year)
            assert _sentences(resolution)[CalculationNoteSentence.PREVISION_SOCIAL_PLACEMENT_INHERITED] == {"0465"}
            assert [item.reason for item in resolution.diagnostics if item.casilla_id is not None] == [
                "advisory_binding_value"
            ], year


def test_no_record_is_disclosed_without_blocking(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        for year in _years(operation):
            resolution = _resolve(repository, operation, year)
            assert resolution.binding_values == {}, year
            assert set(resolution.unresolved_binding_ids) == set(resolution.inapplicable_binding_ids), year
            assert [item.reason for item in resolution.diagnostics] == ["source_issue"], year
            assert CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_CERTIFIED in _sentences(resolution)


def test_a_stored_record_the_edition_refuses_holds_the_empty_boxes_open_until_the_filer_types_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A record kept under another generation that the pinned edition no longer places."""
    year = _years(operation)[0]
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        placed = _record(repository, year, _C.CLAVE_A, _S.SUBCLAVE_01, "200.00")
        _write(repository, placed, operation)
        unplaced = _record(repository, year, _C.CLAVE_D, _S.SUBCLAVE_01, "300.00")
        repository.save_revisioned(unplaced, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID)

        held = _resolve(repository, operation, year)
        assert _box_values(held, _revision(operation, year)) == {"0465": Decimal("200.00")}
        assert held.inapplicable_binding_ids == ()
        open_boxes = _sentences(held)[CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_PLACED]
        assert open_boxes == {"0426", "0427", "0438", "0499", "0466"}
        assert {item.reason for item in held.diagnostics} == {"unresolved_binding"}

        typed = _resolve(repository, operation, year, typed=("0499",))
        assert set(typed.unresolved_binding_ids) == set(typed.inapplicable_binding_ids)
        assert CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_PLACED not in _sentences(typed)
