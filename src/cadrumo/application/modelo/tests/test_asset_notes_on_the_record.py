"""What a calculation knew about the register stays with its revision, element by element.

The diagnostics come from the real Modelo 100 resolver and persist through the real
projection. The session that calculated is then gone: a fresh note store knows nothing,
so whatever the form still says comes from the revision. None of these notes withholds
anything.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from string import Formatter

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ....core.i18n.render import lookup_translation, tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_sources import (
    CalculationNoteFact,
    CalculationNoteSentence,
    CalculationSourceIssue,
    RecordedCalculationNote,
    recorded_calculation_notes,
)
from ....entrypoints.cli._modelo_rendering import recorded_note_notices
from ...actividad_asset.history import ActivityAssetHistory
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from ...aggregation.tests.test_modelo_source_mesh_ledger import register_asset, resolve_m100
from ..calculation_bucket_actions import _unrouted_source_issues
from ..calculation_notes import (
    GATE_REFUSED_REASONS,
    CalculationNoteStore,
    fact_locale_key,
    what_to_do_locale_key,
)
from ..printed_boxes import snapshot_printed_boxes
from ..verification_projection import ModeloVerificationSnapshot
from ..work_form_issue_lines import ModeloFormIssueLine, form_issue_lines
from .test_work_form_gate_agreement import _checked_form, _revision, _work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _two_elements_without_claims() -> tuple[CalculationSourceDiagnostic, ...]:
    """Each element's year at 10 %: 12,000 gives 1,200.00 and 6,000 gives 600.00, both in box 0208."""
    return resolve_m100(
        ActivityAssetHistory(
            revisions=(
                register_asset("furniture", transaction_id="c" * 64),
                register_asset("lathe", transaction_id="d" * 64, basis=Decimal("6000.00")),
            ),
        ),
    ).diagnostics


def _persisted(operation: PinnedAuthorityOperation) -> tuple[CalculationRevision, tuple[CalculationSourceIssue, ...]]:
    snapshot = operation.snapshot("100", filing_year=2025, period="0A")
    issues = _unrouted_source_issues(_two_elements_without_claims(), snapshot_printed_boxes(operation, snapshot))
    revision = _revision(_work_unit(operation), *issues)
    return CalculationRevision.model_validate_json(revision.model_dump_json()), issues


def _gap_lines(operation: PinnedAuthorityOperation, language: OutputLanguage) -> list[ModeloFormIssueLine]:
    revision, _ = _persisted(operation)
    form = _checked_form(operation, revision)
    return [line for line in form_issue_lines(form, language) if "2025-01-01" in line.message]


def test_a_fresh_store_knows_nothing_and_the_form_still_tells_two_elements_apart(
    operation: PinnedAuthorityOperation,
) -> None:
    assert CalculationNoteStore().diagnostics_for("b" * 64, "a" * 64) is None

    furniture, lathe = sorted(_gap_lines(operation, OutputLanguage.EN), key=lambda line: line.message)

    assert "Asset furniture" in furniture.message
    assert "from 2025-01-01 to 2026-01-01" in furniture.message
    assert "1200.00 EUR" in furniture.message
    assert "Asset lathe" in lathe.message
    assert "600.00 EUR" in lathe.message
    assert furniture.detail is not None
    assert "1200.00" not in furniture.detail


def test_the_note_is_read_in_the_operators_language_with_its_figures(operation: PinnedAuthorityOperation) -> None:
    lines = _gap_lines(operation, OutputLanguage.ES)

    assert any("El elemento furniture" in line.message and "1200.00 EUR" in line.message for line in lines)


def test_the_notes_that_persist_for_the_record_withhold_nothing(operation: PinnedAuthorityOperation) -> None:
    _, issues = _persisted(operation)

    assert "activity_asset_claim_gap" in {issue.reason for issue in issues}
    assert not {issue.reason for issue in issues} & GATE_REFUSED_REASONS
    revision, _ = _persisted(operation)
    form = _checked_form(operation, revision)
    assert form.blocking_calculation_notes == ()


def test_two_notes_of_one_reason_are_two_calculations(operation: PinnedAuthorityOperation) -> None:
    """A note is part of what the revision says, so a different figure is a different revision."""
    unit = _work_unit(operation)
    base = {"reason": "activity_asset_claim_gap", "binding_source": None, "message": "gap"}
    first = CalculationSourceIssue(
        **base, fact=CalculationNoteFact.of(CalculationNoteSentence.ACCRUAL_UNAVAILABLE, element="furniture")
    )
    second = CalculationSourceIssue(
        **base, fact=CalculationNoteFact.of(CalculationNoteSentence.ACCRUAL_UNAVAILABLE, element="lathe")
    )

    assert _revision(unit, first).calculation_revision_id != _revision(unit, second).calculation_revision_id


def test_a_long_technical_account_does_not_fail_the_calculation(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("100", filing_year=2025, period="0A")
    diagnostic = CalculationSourceDiagnostic(
        reason="register_acquisition_row_missing",
        source_kind="activity-asset",
        message="elements " + "x" * 2000,
        fact=CalculationNoteFact.of(CalculationNoteSentence.REGISTER_ROW_MISSING, elements="x", rows="y"),
    )

    (issue,) = _unrouted_source_issues((diagnostic,), snapshot_printed_boxes(operation, snapshot))

    assert len(issue.message) == 512
    assert issue.fact is diagnostic.fact


def test_verify_and_export_say_what_the_calculation_noted(operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    from ....core.period import Period
    from ....entrypoints.cli.modelo_export_commands import _export_notices, _export_text_lines
    from ..export_contracts import ModeloExportResult
    from ..export_projection import ModeloFicheroBoePublicReceipt
    from ..verification_preconditions import ModeloVerificationResult
    from .test_verification_preconditions import _blocked_report

    _, issues = _persisted(operation)
    notes = recorded_calculation_notes((*issues, *issues))
    assert sum(note.reason == "activity_asset_claim_gap" for note in notes) == 2

    verification = ModeloVerificationResult(
        report=_blocked_report(()), published=True, finding_preconditions=(), calculation_notes=notes
    )
    assert ModeloVerificationSnapshot.from_verification(verification).to_verification().calculation_notes == notes

    exported = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="100",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        output_path=tmp_path / "modelo-100.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        calculation_notes=notes,
    )
    restored = ModeloFicheroBoePublicReceipt.from_result(exported).to_result()
    assert restored.calculation_notes == notes
    assert any("1200.00 EUR" in notice.message for notice in _export_notices(restored))
    assert any("600.00 EUR" in line for line in _export_text_lines(restored))


def test_a_restated_note_says_its_level_its_facts_and_what_to_do() -> None:
    note = RecordedCalculationNote(
        reason="activity_asset_disposal_finding",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.DISPOSAL_FIGURE_IN_BOX,
            element="furniture",
            date=date(2025, 6, 30).isoformat(),
            amount="897.53",
            box="1654",
        ),
    )

    (notice,), (line,) = recorded_note_notices((note,), code="modelo.calculation_note")

    assert all(part in notice.message for part in ("897.53 EUR", "furniture", "2025-06-30", "1654"))
    assert notice.context is not None
    assert notice.context["level"] == "check"
    assert notice.message in line
    assert tr(what_to_do_locale_key("activity_asset_disposal_finding")) in line


@pytest.mark.parametrize("sentence", tuple(CalculationNoteSentence))
def test_every_language_names_the_same_facts(sentence: CalculationNoteSentence) -> None:
    def named(language: str) -> set[str]:
        text = lookup_translation(fact_locale_key(sentence), locale=language)
        assert text is not None
        return {field for _, field, _, _ in Formatter().parse(text) if field is not None}

    assert {language: named(language) for language in SUPPORTED_OUTPUT_LANGUAGES} == dict.fromkeys(
        SUPPORTED_OUTPUT_LANGUAGES, named("en")
    )


def test_the_disposal_note_points_at_what_it_says_in_every_language() -> None:
    texts = {
        language: lookup_translation(what_to_do_locale_key("activity_asset_disposal_finding"), locale=language)
        for language in SUPPORTED_OUTPUT_LANGUAGES
    }

    assert all(text is not None for text in texts.values())
    assert texts["en"] is not None
    assert "Read the note on" not in texts["en"]
