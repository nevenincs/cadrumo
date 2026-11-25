"""The export's own draft guards refuse as terminal integrity defects, worded in every locale.

The Modelo export builds and approves the draft it hands to the filing export
from the same registry provider, so an unapproved draft or one built from other
Modelo definitions reaches the filing guards only through a caller fault. The
guards are driven through the real ``export_draft``, and the export boundary
must keep their served words and the terminal door.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.filing.errors import FilingExportIntegrityError
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.export import export_draft
from ...filing.tests.export_support import (
    EXPORT_PERIOD,
    approved_registry_draft,
    export_schema_provider,
    typed_producer_snapshot,
)
from ..export import export_write_failure
from ..export_contracts import ModeloExportCommand, ModeloExportDesignIntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_LOCALES = ("es", "ca", "en", "hu")


def _approved() -> ModeloDraft:
    draft = approved_registry_draft()
    assert isinstance(draft, ModeloDraft)
    return draft


def _unapproved() -> ModeloDraft:
    return _approved().model_copy(update={"status": ModeloDraftStatus.LISTO_PARA_PRESENTAR})


def _other_definitions() -> ModeloDraft:
    return _approved().model_copy(update={"schema_version": "other-modelo-definitions"})


def _refusal(draft: ModeloDraft, output_path: Path) -> FilingExportIntegrityError:
    with pytest.raises(FilingExportIntegrityError) as refused:
        export_draft(
            draft,
            output_path=output_path,
            producer_snapshot=typed_producer_snapshot(),
            schema_provider=export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T"),
        )
    return refused.value


@pytest.mark.parametrize(
    ("draft_factory", "message_key"),
    [
        (_unapproved, "errors.integrity.filing_export_draft_unapproved"),
        (_other_definitions, "errors.integrity.filing_export_draft_schema_mismatch"),
    ],
    ids=["unapproved", "other-definitions"],
)
def test_a_draft_the_export_did_not_build_and_approve_refuses_as_a_terminal_integrity_defect(
    draft_factory: Callable[[], ModeloDraft], message_key: str, tmp_path: Path
) -> None:
    output_path = tmp_path / "export.txt"

    refusal = _refusal(draft_factory(), output_path)

    assert refusal.translated_message == message_key
    registered = get_registered_error_code(refusal)
    assert (registered.code, registered.category) == ("INTEGRITY_FILING_EXPORT", ErrorCategory.INTEGRITY)
    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert not output_path.exists()

    failure = export_write_failure(ModeloExportCommand.model_construct(calculation_revision_id="revision-1"), refusal)

    assert isinstance(failure, ModeloExportDesignIntegrityError)
    assert failure.translated_message == message_key
    boundary_verdict = nested_terminal_precondition_verdict(failure)
    assert boundary_verdict is not None
    assert boundary_verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    for locale in _LOCALES:
        message = resolve_error_message(failure, locale=locale)
        assert message
        assert "%{" not in message
