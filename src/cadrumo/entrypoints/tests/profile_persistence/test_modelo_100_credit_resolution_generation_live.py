"""An operator's acceptance of a disputed withholding credit across published authority generations (LIVE).

A resolution is keyed to the registry revision id and to the content digest of
the declaration and source values the comparison read, never to the authority
generation. A publication that leaves the revision's ``credit_reconciliation``
entry and every keyed value alone therefore keeps the acceptance, and a
publication that changes the declaration the finding was made against ends it
with ``credit_resolution_stale``.

The generations are published into a private authority root, each derived from
the one before it (see the support module for what that derivation keeps). The
bundled registry tree and the shared authority are never written. Real encrypted
stores, real source mesh, calculation, reconciliation and verification gates; no
mocks. Every identifier and figure is synthetic.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.modelo.calculation_note_gate import (
    SOURCE_DISAGREEMENT_FINDING_ID_LENGTH,
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
)
from ....application.modelo.credit_resolution import (
    credit_resolution_for_finding,
    credit_resolutions_for_work,
    find_finding,
)
from ....application.modelo.credit_resolution_repository import store_credit_resolution
from ....application.modelo.disagreement_words import disagreement_value_text
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.user_profile.profile_record_repository import close_active_profile_record_session
from ....core.casilla_id import CasillaId
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from ....domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from .credit_resolution_generation_support import publish_derived_generation
from .credit_resolution_live_support import (
    BUCKET_ID,
    CAPITAL_BINDING,
    CAPITAL_CASILLA,
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
_BORRADOR = {TRABAJO_BINDING: Decimal("1800.00"), CAPITAL_BINDING: Decimal("499.99")}

_MODELO = "100"
_REVISION = str(YEAR)
_UNRELATED_MODELO = "130"
_UNRELATED_REVISION = str(open_ended_revision(_UNRELATED_MODELO).id)
_CORROBORATED_CLASS = "trabajo"


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


@pytest.fixture
def authority_root(tmp_path: Path) -> Iterator[Path]:
    """A private authority root, holding the published generation, that the shared owner serves for the test."""
    root = tmp_path / "authority"
    root.mkdir()
    with isolated_shared_authority(root):
        yield root


@contextmanager
def _served_generation() -> Generator[PinnedAuthorityOperation]:
    """Lease the generation the private root now selects, as a fresh operation admits it."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _adopt_published_generation() -> None:
    """Retire the record authority the process holds, as adopting a new generation does.

    A profile record session is pinned to the generation it was derived under, so the session that
    served the earlier generation is closed and the next read derives one under the generation now
    selected from the still-open custody session.
    """
    close_active_profile_record_session()


def _seeded_harness(secure_objects: SecureObjectRepository) -> CreditLiveHarness:
    """Seed the profile and its certificates under the generation the private root serves."""
    with _served_generation() as served:
        return CreditLiveHarness.seed(secure_objects, operation=served)


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


def _blocking_disagreements(revision: CalculationRevision, harness: CreditLiveHarness) -> set[CasillaId]:
    """The casillas whose disagreement still holds ``revision``, as the stored resolutions now decide it."""
    resolutions = credit_resolutions_for_work(harness.resolutions, harness.current_work_unit())
    return {
        issue.casilla_id
        for issue in blocking_calculation_issues(revision, resolutions)
        if issue.reason == "credit_source_disagreement" and issue.casilla_id is not None
    }


def _accept(harness: CreditLiveHarness, revision: CalculationRevision, casilla: CasillaId) -> None:
    """Accept the disagreement on ``casilla`` by its finding id, as the operator's command does."""
    issue = find_finding(revision, _finding_id(_disagreement(revision, casilla)))
    record = credit_resolution_for_finding(issue, reason=_REASON, at=_AT, by_session=_SESSION)
    store_credit_resolution(
        record, repository=harness.resolutions, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
    )


def _verify_context(operation: PinnedAuthorityOperation, revision: CalculationRevision) -> dict[str, object]:
    """Run the real verification and return the context of the refusal it ends in.

    The seeded declaration carries only the credit figures, so verification refuses on what else it
    lacks even once every credit disagreement is answered. What a test reads from the refusal is
    therefore whether the credit disagreements are among its reasons.
    """
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


def _reasons(context: dict[str, object]) -> list[str]:
    return str(context["reasons"]).split(",")


def _finding_ids(context: dict[str, object]) -> list[str]:
    return str(context.get("finding_ids", "")).split(",")


def _stale_notes(revision: CalculationRevision) -> list[CalculationSourceIssue]:
    return [issue for issue in revision.source_issues if issue.reason == "credit_resolution_stale"]


def _accept_and_confirm_verify_lifts_the_hold(
    harness: CreditLiveHarness, revision: CalculationRevision, operation: PinnedAuthorityOperation
) -> CalculationSourceIssue:
    """Accept the work disagreement, confirm verification stops naming it, and return the accepted issue."""
    issue = _disagreement(revision, TRABAJO_CASILLA)
    assert _finding_id(issue) in _finding_ids(_verify_context(operation, revision))
    _accept(harness, revision, TRABAJO_CASILLA)
    assert TRABAJO_CASILLA not in _blocking_disagreements(revision, harness)
    context = _verify_context(operation, revision)
    assert _finding_id(issue) not in _finding_ids(context)
    # The capital figure is a second disagreement nobody answered, so it alone still refuses the declaration.
    assert _finding_ids(context) == [_finding_id(_disagreement(revision, CAPITAL_CASILLA))]
    return issue


def _compared_values(issue: CalculationSourceIssue) -> list[tuple[str, str]]:
    """What each source stated, in order, without the snapshot a recalculation reads it from."""
    assert issue.disagreement is not None
    return [(source.role.value, disagreement_value_text(source.value)) for source in issue.disagreement.sources]


def _touch_reviewer(payload: dict[str, Any]) -> None:
    """A change to a revision that no reconciliation declaration or keyed value reads."""
    payload["reviewed_by"] = "synthetic-reviewer"


def _corroborate_trabajo_with_certificates(payload: dict[str, Any]) -> None:
    """Declare one more cross-check for the work credit, so the entry the finding was made against changes."""
    (entry,) = [entry for entry in payload["credit_reconciliation"] if entry["casilla_id"] == str(TRABAJO_CASILLA)]
    entry["cross_checks"].append({"kind": "retencion_soportada", "income_class": _CORROBORATED_CLASS})


def test_a_publication_that_leaves_the_declaration_and_values_unchanged_keeps_the_resolution(
    secure_objects: SecureObjectRepository, authority_root: Path
) -> None:
    harness = _seeded_harness(secure_objects)
    with _served_generation() as first_generation:
        first = harness.calculate(_BORRADOR).revision
        old = _accept_and_confirm_verify_lifts_the_hold(harness, first, first_generation)
        first_pin = first_generation.pin().logical_generation
        declared = first_generation.revision(_MODELO, _REVISION).credit_reconciliation

    second = publish_derived_generation(
        authority_root,
        label="unrelated-revisions",
        revision_edits={
            (_UNRELATED_MODELO, _UNRELATED_REVISION): _touch_reviewer,
            (_MODELO, _REVISION): _touch_reviewer,
        },
    )
    assert second.logical_generation != first_pin
    _adopt_published_generation()

    with _served_generation() as second_generation:
        assert second_generation.pin().logical_generation == second.logical_generation
        assert second_generation.revision(_MODELO, _REVISION).credit_reconciliation == declared
        # The calculation persisted under the earlier generation, verified under this one, is still answered.
        context = _verify_context(second_generation, first)
        assert _finding_id(old) not in _finding_ids(context)
        assert TRABAJO_CASILLA not in _blocking_disagreements(first, harness)
        again = harness.calculate(_BORRADOR).revision

    renewed = _disagreement(again, TRABAJO_CASILLA).disagreement
    assert renewed is not None and old.disagreement is not None
    assert renewed.finding_key == old.disagreement.finding_key
    assert not _stale_notes(again)
    assert _blocking_disagreements(again, harness) == {CAPITAL_CASILLA}


def test_a_publication_that_changes_the_declared_cross_checks_ends_the_resolution_and_reports_it_stale(
    secure_objects: SecureObjectRepository, authority_root: Path
) -> None:
    harness = _seeded_harness(secure_objects)
    with _served_generation() as first_generation:
        first = harness.calculate(_BORRADOR).revision
        old = _accept_and_confirm_verify_lifts_the_hold(harness, first, first_generation)
        first_pin = first_generation.pin().logical_generation
        declared = first_generation.revision(_MODELO, _REVISION).credit_reconciliation

    third = publish_derived_generation(
        authority_root,
        label="more-cross-checks",
        revision_edits={(_MODELO, _REVISION): _corroborate_trabajo_with_certificates},
    )
    assert third.logical_generation != first_pin
    _adopt_published_generation()

    with _served_generation() as third_generation:
        assert third_generation.pin().logical_generation == third.logical_generation
        assert third_generation.revision(_MODELO, _REVISION).credit_reconciliation != declared
        recalculated = harness.calculate(_BORRADOR).revision
        new = _disagreement(recalculated, TRABAJO_CASILLA)
        context = _verify_context(third_generation, recalculated)

    assert new.disagreement is not None and old.disagreement is not None
    # The registry revision and every compared amount are as before: only the declaration moved.
    assert new.disagreement.registry_revision_id == old.disagreement.registry_revision_id
    assert _compared_values(new) == _compared_values(old)
    assert new.disagreement.inputs_digest != old.disagreement.inputs_digest
    assert new.disagreement.finding_key != old.disagreement.finding_key
    assert TRABAJO_CASILLA in _blocking_disagreements(recalculated, harness)
    (stale,) = _stale_notes(recalculated)
    assert stale.casilla_id == TRABAJO_CASILLA
    assert _finding_id(new) in _finding_ids(context)
    assert _finding_id(old) not in _finding_ids(context)
    # The earlier calculation's finding is still the one the acceptance was made against.
    assert TRABAJO_CASILLA not in _blocking_disagreements(first, harness)
