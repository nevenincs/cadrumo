"""An operator's acceptance of a disputed Modelo 100 withholding credit, through the real verify path (LIVE).

The credit casillas 0596 and 0597 are valued from payer certificates and
compared with the AEAT borrador. Two borrador figures that differ from the
certificates leave two disagreements, each with its finding id. Verification
refuses on them until the operator accepts one by its id; the acceptance lifts
the hold on exactly that finding and lasts only while the sources keep stating
the amounts it was made against.

Real encrypted stores, real published authority, real source mesh, calculation,
reconciliation and verification gates; no mocks. Every identifier and figure is
synthetic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_CREDIT_RESOLUTION_NAMESPACE
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.export.review_snapshot_loader import CALCULATION_NOTE_FINDING_PREFIX
from ....application.modelo.calculation_note_gate import (
    SOURCE_DISAGREEMENT_FINDING_ID_LENGTH,
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
)
from ....application.modelo.calculation_notes import note_attention
from ....application.modelo.calculation_report_export import applied_report_resolutions
from ....application.modelo.credit_resolution import (
    applied_resolution_notes,
    credit_resolution_for_finding,
    credit_resolutions_for_work,
    find_finding,
    load_credit_resolutions,
)
from ....application.modelo.credit_resolution_repository import (
    CreditResolutionPersistenceError,
    CreditResolutionRefusedError,
    credit_resolution_key,
    revoke_credit_resolution,
    store_credit_resolution,
)
from ....application.modelo.declaration_summary import declaration_summary
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_form_findings import ModeloFormAttention
from ....core.casilla_id import CasillaId
from ....core.config import override_settings
from ....core.external_constants import UTF_8_ENCODING
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.credit_resolution import CreditResolutionIdentity
from ....entrypoints.calculation_review_snapshot_composition import load_calculation_review_snapshot
from .credit_resolution_live_support import (
    BUCKET_ID,
    CAPITAL_BINDING,
    CAPITAL_CASILLA,
    EXPECTED_CAPITAL_CREDIT,
    EXPECTED_TRABAJO_CREDIT,
    TRABAJO_BINDING,
    TRABAJO_CASILLA,
    YEAR,
    CreditLiveHarness,
)
from .file_flow_test_support import workflow_profile
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]

_AT = datetime(filing_year_envelope().horizon + 1, 4, 3, 9, 0, tzinfo=UTC)
_SESSION = "session-label-one"
_REASON = "Synthetic reason: the payer's own copy of the certificate states this amount."

# What the borrador printed: both figures differ from the certificates by an amount a cent-exact comparison finds.
_TRABAJO_BORRADOR = Decimal("1800.00")
_TRABAJO_BORRADOR_CORRECTED = Decimal("1801.00")
_CAPITAL_BORRADOR = Decimal("499.99")
_BORRADOR = {TRABAJO_BINDING: _TRABAJO_BORRADOR, CAPITAL_BINDING: _CAPITAL_BORRADOR}
_CORRECTED_BORRADOR = {**_BORRADOR, TRABAJO_BINDING: _TRABAJO_BORRADOR_CORRECTED}


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


@pytest.fixture
def harness(secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> CreditLiveHarness:
    return CreditLiveHarness.seed(secure_objects, operation=operation)


def _disagreement(revision: CalculationRevision, casilla: CasillaId) -> CalculationSourceIssue:
    (issue,) = [
        issue
        for issue in revision.source_issues
        if issue.reason == "credit_source_disagreement" and issue.casilla_id == casilla
    ]
    return issue


def _finding_id(issue: CalculationSourceIssue) -> str:
    assert issue.disagreement is not None
    return issue.disagreement.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]


def _identity(issue: CalculationSourceIssue) -> CreditResolutionIdentity:
    fact = issue.disagreement
    assert fact is not None
    return (fact.modelo, fact.filing_year, fact.period, fact.finding_key)


def _blocking_disagreements(revision: CalculationRevision, harness: CreditLiveHarness) -> set[CasillaId]:
    """The casillas whose disagreement still holds ``revision``, as the stored resolutions now decide it."""
    resolutions = credit_resolutions_for_work(harness.resolutions, harness.current_work_unit())
    return {
        issue.casilla_id
        for issue in blocking_calculation_issues(revision, resolutions)
        if issue.reason == "credit_source_disagreement" and issue.casilla_id is not None
    }


def _accept(harness: CreditLiveHarness, revision: CalculationRevision, casilla: CasillaId) -> str:
    """Accept the disagreement on ``casilla`` by its finding id, as the operator's command does."""
    issue = find_finding(revision, _finding_id(_disagreement(revision, casilla)))
    record = credit_resolution_for_finding(issue, reason=_REASON, at=_AT, by_session=_SESSION)
    return store_credit_resolution(
        record, repository=harness.resolutions, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
    )


def _verify_refusal(operation: PinnedAuthorityOperation, revision: CalculationRevision) -> dict[str, object]:
    """Run the real verification and return the context of the refusal it ends in."""
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator-A",
            workflow_profile=workflow_profile(),
            operator_scope_ports=build_operator_scope_ports(),
            operation=operation,
        )
    context = refused.value.context
    assert context is not None
    return dict(context)


def _ids(context: dict[str, object]) -> list[str]:
    return str(context.get("finding_ids", "")).split(",")


def _stale_notes(revision: CalculationRevision) -> list[CalculationSourceIssue]:
    return [issue for issue in revision.source_issues if issue.reason == "credit_resolution_stale"]


def test_a_disagreement_blocks_verify_until_it_is_resolved_and_the_refusal_names_its_finding_id(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    trabajo, capital = _disagreement(revision, TRABAJO_CASILLA), _disagreement(revision, CAPITAL_CASILLA)

    context = _verify_refusal(operation, revision)

    assert "credit_source_disagreement" in str(context["reasons"]).split(",")
    assert set(_ids(context)) == {_finding_id(trabajo), _finding_id(capital)}
    assert _finding_id(trabajo) != _finding_id(capital)
    assert "resolutions_unreadable" not in context
    assert _blocking_disagreements(revision, harness) == {TRABAJO_CASILLA, CAPITAL_CASILLA}


def test_an_active_resolution_lifts_the_hold_on_exactly_the_finding_it_answers(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    trabajo, capital = _disagreement(revision, TRABAJO_CASILLA), _disagreement(revision, CAPITAL_CASILLA)

    _accept(harness, revision, TRABAJO_CASILLA)

    assert _blocking_disagreements(revision, harness) == {CAPITAL_CASILLA}
    context = _verify_refusal(operation, revision)
    # The other casilla's disagreement still refuses verification, and only it is named for an answer.
    assert _ids(context) == [_finding_id(capital)]
    assert _finding_id(trabajo) not in _ids(context)

    _accept(harness, revision, CAPITAL_CASILLA)

    assert _blocking_disagreements(revision, harness) == set()
    context = _verify_refusal(operation, revision)
    assert "credit_source_disagreement" not in str(context["reasons"]).split(",")
    assert "finding_ids" not in context
    # The calculation still used the certificates' credit; an acceptance changes no figure.
    assert Decimal(revision.casilla_values[TRABAJO_CASILLA]) == EXPECTED_TRABAJO_CREDIT
    assert Decimal(revision.casilla_values[CAPITAL_CASILLA]) == EXPECTED_CAPITAL_CREDIT


def test_a_recalculation_with_unchanged_amounts_keeps_the_resolution_and_says_nothing_of_it(
    harness: CreditLiveHarness,
) -> None:
    first = harness.calculate(_BORRADOR).revision
    _accept(harness, first, TRABAJO_CASILLA)

    again = harness.calculate(_BORRADOR).revision

    assert _finding_id(_disagreement(again, TRABAJO_CASILLA)) == _finding_id(_disagreement(first, TRABAJO_CASILLA))
    assert _blocking_disagreements(again, harness) == {CAPITAL_CASILLA}
    assert not _stale_notes(again)


def test_a_changed_amount_makes_the_resolution_stale_and_blocks_the_figure_again(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    first = harness.calculate(_BORRADOR).revision
    old_id = _finding_id(_disagreement(first, TRABAJO_CASILLA))
    _accept(harness, first, TRABAJO_CASILLA)
    assert TRABAJO_CASILLA not in _blocking_disagreements(first, harness)

    corrected = harness.calculate(_CORRECTED_BORRADOR).revision

    new = _disagreement(corrected, TRABAJO_CASILLA)
    assert _finding_id(new) != old_id
    assert TRABAJO_CASILLA in _blocking_disagreements(corrected, harness)
    (stale,) = _stale_notes(corrected)
    assert stale.casilla_id == TRABAJO_CASILLA
    # The note says the acceptance lapsed and withholds nothing itself: the new disagreement does.
    assert stale not in blocking_calculation_issues(corrected)
    assert note_attention("credit_resolution_stale", box="0596") is ModeloFormAttention.CHECK
    context = _verify_refusal(operation, corrected)
    assert _finding_id(new) in _ids(context)
    assert old_id not in _ids(context)
    # The earlier calculation's finding is still the one the acceptance was made against.
    assert TRABAJO_CASILLA not in _blocking_disagreements(first, harness)


def test_the_stale_finding_id_is_refused_against_the_new_calculation_and_the_new_one_is_accepted(
    harness: CreditLiveHarness,
) -> None:
    first = harness.calculate(_BORRADOR).revision
    old_id = _finding_id(_disagreement(first, TRABAJO_CASILLA))
    corrected = harness.calculate(_CORRECTED_BORRADOR).revision

    with pytest.raises(CreditResolutionRefusedError) as refused:
        find_finding(corrected, old_id)
    assert refused.value.reason == "unknown_finding"

    _accept(harness, corrected, TRABAJO_CASILLA)

    assert TRABAJO_CASILLA not in _blocking_disagreements(corrected, harness)
    assert not _stale_notes(harness.calculate(_CORRECTED_BORRADOR).revision)


@pytest.mark.parametrize(
    "finding_id",
    ["0" * SOURCE_DISAGREEMENT_FINDING_ID_LENGTH, "abc", "g" * SOURCE_DISAGREEMENT_FINDING_ID_LENGTH, "", "  "],
    ids=["unknown", "short", "not-hex", "empty", "blank"],
)
def test_an_id_that_names_no_current_finding_is_refused_and_stores_nothing(
    harness: CreditLiveHarness, finding_id: str
) -> None:
    revision = harness.calculate(_BORRADOR).revision

    with pytest.raises(CreditResolutionRefusedError) as refused:
        find_finding(revision, finding_id)

    assert refused.value.reason == "unknown_finding"
    assert harness.resolutions.load_for_work(modelo="100", filing_year=YEAR, period="0A") == ()


def test_the_id_of_a_disagreement_is_found_whatever_its_letter_case_and_surrounding_blanks(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    issue = _disagreement(revision, TRABAJO_CASILLA)

    assert find_finding(revision, f"  {_finding_id(issue).upper()} ") == issue


def test_revoking_a_resolution_blocks_the_figure_again_and_raises_no_stale_note(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    stored_revision = _accept(harness, revision, TRABAJO_CASILLA)
    assert TRABAJO_CASILLA not in _blocking_disagreements(revision, harness)
    issue = _disagreement(revision, TRABAJO_CASILLA)

    revoke_credit_resolution(
        _identity(issue),
        at=_AT + timedelta(days=1),
        by_session=_SESSION,
        repository=harness.resolutions,
        expected_revision_id=stored_revision,
    )

    assert TRABAJO_CASILLA in _blocking_disagreements(revision, harness)
    assert _finding_id(issue) in _ids(_verify_refusal(operation, revision))
    # A revoked acceptance is not a stale one: a later recalculation raises no note about it.
    assert not _stale_notes(harness.calculate(_BORRADOR).revision)


def test_a_store_that_cannot_be_read_is_never_empty_and_never_unblocks(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation, secure_objects: SecureObjectRepository
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    _accept(harness, revision, TRABAJO_CASILLA)
    issue = _disagreement(revision, TRABAJO_CASILLA)
    key = credit_resolution_key(_identity(issue))
    stored = secure_objects.load(
        MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        key,
        expected_class=MODELO_CREDIT_RESOLUTION_NAMESPACE.sensitivity,
        max_supported_version=MODELO_CREDIT_RESOLUTION_NAMESPACE.schema_version,
    )
    assert stored is not None
    assert b'"state":"active"' in stored.payload
    secure_objects.save(
        namespace=MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        object_key=key,
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=stored.payload.replace(b'"state":"active"', b'"state":"no-such-state"'),
    )
    assert load_credit_resolutions(harness.resolutions, modelo="100", filing_year=YEAR, period="0A").unreadable

    context = _verify_refusal(operation, revision)
    recalculated = harness.calculate(_BORRADOR)

    assert _finding_id(issue) in _ids(context)
    assert context["resolutions_unreadable"] == "true"
    # The calculation keeps the disagreement persisted and reports the unreadable store; it raises no stale note.
    assert _disagreement(recalculated.revision, TRABAJO_CASILLA) in blocking_calculation_issues(recalculated.revision)
    assert any(
        diagnostic.reason == "storage_degraded" and diagnostic.source_kind == "credit_resolution"
        for diagnostic in recalculated.source_diagnostics
    )
    assert not _stale_notes(recalculated.revision)


def test_the_reason_and_the_amounts_of_a_resolution_never_reach_the_disk_in_plaintext(
    tmp_path: Path, harness: CreditLiveHarness
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    _accept(harness, revision, TRABAJO_CASILLA)

    (record,) = harness.resolutions.load_for_work(modelo="100", filing_year=YEAR, period="0A")

    assert record.reason == _REASON
    assert record.disagreement == _disagreement(revision, TRABAJO_CASILLA).disagreement
    on_disk = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    assert _REASON.encode(UTF_8_ENCODING) not in on_disk
    assert record.finding_key.encode(UTF_8_ENCODING) not in on_disk


def test_every_applied_resolution_is_listed_with_its_box_sources_amounts_and_reason(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    _accept(harness, revision, TRABAJO_CASILLA)
    trabajo = _disagreement(revision, TRABAJO_CASILLA)

    with override_settings(cadrumo_output_language="en"):
        notes = applied_resolution_notes(
            revision, load_credit_resolutions(harness.resolutions, modelo="100", filing_year=YEAR, period="0A")
        )

    # Only the accepted disagreement is listed; the capital one is still open.
    (note,) = notes
    assert note.reason == "credit_resolution_applied"
    values = dict(note.fact.values)
    assert set(values) == {"box", "accepted", "sources", "reason"}
    assert (values["box"], values["reason"]) == (str(TRABAJO_CASILLA), _REASON)
    assert json.loads(values["accepted"]) == ["decimal", "1950.00"]
    assert [(role, kind_and_text) for role, _family, kind_and_text in json.loads(values["sources"])] == [
        ("value_source", ["decimal", "1950.00"]),
        ("cross_check", ["decimal", "1800.00"]),
    ]
    assert note_attention(note.reason, box=None) is ModeloFormAttention.INFO
    for text in (note.message, note.detail):
        assert text
    # The sentence words the sources and writes the amounts as the language does, and names no id or token.
    assert "1,950.00" in note.message and "1,800.00" in note.message and _REASON in note.message
    assert _finding_id(trabajo) not in note.message and "value_source" not in note.message
    # Once taken back the acceptance lists nothing.
    revoke_credit_resolution(
        _identity(trabajo),
        at=_AT + timedelta(days=1),
        by_session=_SESSION,
        repository=harness.resolutions,
        expected_revision_id=harness.resolutions.load_revisioned(_identity(trabajo))[1],
    )
    assert not applied_resolution_notes(
        revision, load_credit_resolutions(harness.resolutions, modelo="100", filing_year=YEAR, period="0A")
    )


def test_a_report_lists_the_acceptances_that_cover_the_revision_and_refuses_when_they_cannot_be_read(
    harness: CreditLiveHarness, secure_objects: SecureObjectRepository
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    ports = modelo_export_ports_for_test(bucket_id=BUCKET_ID, secure_objects=secure_objects)
    unit = harness.current_work_unit()
    assert applied_report_resolutions(revision, unit, export_ports=ports) == ()
    _accept(harness, revision, TRABAJO_CASILLA)
    trabajo = _disagreement(revision, TRABAJO_CASILLA)

    (applied,) = applied_report_resolutions(revision, unit, export_ports=ports)

    assert applied.identity == _identity(trabajo)
    key = credit_resolution_key(_identity(trabajo))
    stored = secure_objects.load(
        MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        key,
        expected_class=MODELO_CREDIT_RESOLUTION_NAMESPACE.sensitivity,
        max_supported_version=MODELO_CREDIT_RESOLUTION_NAMESPACE.schema_version,
    )
    assert stored is not None
    secure_objects.save(
        namespace=MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        object_key=key,
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=stored.payload.replace(b'"state":"active"', b'"state":"no-such-state"'),
    )
    # A report that could not read the acceptances would state the figure as unanswered on no evidence.
    with pytest.raises(CreditResolutionPersistenceError):
        applied_report_resolutions(revision, unit, export_ports=ports)


def _summary(harness: CreditLiveHarness, revision: CalculationRevision, operation: PinnedAuthorityOperation):
    """The declarations-list row of the harness's work unit, built as the generation reader builds it."""
    unit = harness.current_work_unit()
    declaration = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=unit.work_unit_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        state=unit.state,
        has_current_calculation=True,
        has_current_filing=False,
    )
    lookup = load_credit_resolutions(
        harness.resolutions, modelo="100", filing_year=YEAR, period=unit.period.registry_token
    )
    return declaration_summary(
        declaration,
        revisions={revision.calculation_revision_id: revision},
        verification=None,
        operation=operation,
        resolutions=lookup.resolutions,
    )


def test_the_declarations_list_counts_a_covered_disagreement_as_no_blocker_exactly_as_the_gate_does(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    open_count = _summary(harness, revision, operation).blocking_count
    assert open_count is not None

    _accept(harness, revision, TRABAJO_CASILLA)
    one_answered = _summary(harness, revision, operation).blocking_count
    _accept(harness, revision, CAPITAL_CASILLA)
    both_answered = _summary(harness, revision, operation).blocking_count

    assert (open_count, one_answered, both_answered) == (open_count, open_count - 1, open_count - 2)
    assert both_answered == len(
        blocking_calculation_issues(
            revision, credit_resolutions_for_work(harness.resolutions, harness.current_work_unit())
        )
    )


def test_the_review_workbook_lists_an_accepted_disagreement_as_accepted_and_the_open_one_as_withheld(
    harness: CreditLiveHarness, operation: PinnedAuthorityOperation
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    prefix = CALCULATION_NOTE_FINDING_PREFIX

    def codes() -> dict[str, list[str]]:
        snapshot = load_calculation_review_snapshot(
            revision.calculation_revision_id, profile_id=UUID(BUCKET_ID), operation=operation
        )
        found: dict[str, list[str]] = {}
        for finding in snapshot.findings:
            if finding.code.startswith(prefix):
                # The box leads the related ids; a note that names its source adds it after.
                found.setdefault(finding.code.removeprefix(prefix), []).extend(finding.related_ids[:1])
        return found

    before = codes()
    assert sorted(before["credit_source_disagreement"]) == [str(TRABAJO_CASILLA), str(CAPITAL_CASILLA)]
    assert "credit_resolution_applied" not in before

    _accept(harness, revision, TRABAJO_CASILLA)
    after = codes()

    assert after["credit_source_disagreement"] == [str(CAPITAL_CASILLA)]
    assert after["credit_resolution_applied"] == [str(TRABAJO_CASILLA)]
