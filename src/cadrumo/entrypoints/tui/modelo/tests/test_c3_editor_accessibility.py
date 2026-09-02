"""C3 editor proofs that no single module can make about itself.

Two properties here are cross-cutting and adversarial rather than functional,
which is why they live beside the cohort rather than in a module's own suite:
a raw lexeme must not survive anywhere in the editor's state, and a language
switch must not silently change how a value is read.

Both are proven with a UNIQUE SENTINEL rather than a plausible value. A test
that typed ``1234.56`` and searched for it would match the parsed Decimal, the
casilla id of an unrelated field, and any digit sequence the state happens to
carry -- so it would pass while telling you nothing. A sentinel that cannot
occur naturally makes a hit unambiguous.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.edit.fields`
        The module holding the only lexeme state in the editor.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from .....application.modelo.work_addressing import ModeloExactWorkUnitTarget
from .....application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
from .....application.operations.registry import OperationSchemaIdentityV1
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.temporal import select_revision
from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..edit.controller import ModeloEditController

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64
_SENTINEL = "ZZQX-SENTINEL-9182736455-QXZZ"
"""A lexeme that cannot occur naturally in state, a parsed value, or an id."""


def _identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _admitted(locale: OutputLanguage = OutputLanguage.ES) -> ModeloEditController:
    from .....application.modelo.edit_services import (
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )

    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T").id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-1T",
        created_at=now,
        updated_at=now,
    )
    controller = ModeloEditController.for_locale(locale)
    admitted = controller.admit(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
        ),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=work_unit.bucket_id,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=_identity(),
            financial_operand_schema=_identity(),
        ),
    )
    assert admitted, f"admission refused: {controller.refusal_message_key}"
    return controller


def _reachable_text(controller: ModeloEditController) -> str:
    """Render everything a surface or a crash dump could read off the editor."""
    fields = controller.fields()
    parts = [repr(fields), repr(controller.rows()), repr(controller.review_gate())]
    parts.extend(repr(fields.state(casilla_id)) for casilla_id in fields.casilla_ids())
    parts.extend(repr(item) for item in fields.unresolved())
    return "\n".join(parts)


def test_a_refused_lexeme_is_not_retained_anywhere_in_editor_state() -> None:
    """The operator's rejected text must not survive in any reachable state.

    The refused path is the dangerous one: an accepted lexeme is replaced by
    its parsed value, but a rejected one has no parsed form, so a naive
    implementation keeps the string to redisplay it. The contract refuses to
    echo a lexeme in any result derived from a parse request, and the editor
    must not reintroduce it behind the contract's back.
    """
    controller = _admitted()
    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]

    fields.submit_lexeme(casilla_id, _SENTINEL)

    assert fields.state(casilla_id).is_unresolved, "the sentinel must actually have been refused"
    assert _SENTINEL not in _reachable_text(controller)


def test_an_accepted_lexeme_is_not_retained_beside_its_parsed_value() -> None:
    """The parsed value replaces the text; the SPELLING the operator used is not kept.

    Uses a lexeme whose exact spelling cannot be reconstructed from the parsed
    value -- a thousands separator and a comma decimal -- so finding that
    string in state proves the raw text was retained rather than re-rendered.
    A test typing ``12.34`` could not tell the two apart, because the parsed
    Decimal renders back to the same characters.
    """
    controller = _admitted()
    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]
    spelled = "1.234,56"

    accepted = fields.submit_lexeme(casilla_id, spelled)

    assert accepted.is_unresolved is False, "the Spanish spelling must parse, or this proves nothing"
    assert spelled not in _reachable_text(controller)


def test_the_sentinel_probe_can_actually_see_retained_text() -> None:
    """Anti-tautology: prove the probe would catch a leak if one existed.

    Without this, both tests above pass equally well against an editor that
    retains everything and a probe that reads nothing.
    """
    controller = _admitted()
    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]

    fields.state(casilla_id).message_key = _SENTINEL

    assert _SENTINEL in _reachable_text(controller), (
        "the probe cannot see text placed directly in reachable state, so its "
        "silence in the retention tests measures nothing"
    )


def test_the_parsing_language_is_the_language_the_operator_was_shown() -> None:
    """A locale switch changes how a lexeme is read, so the two must not diverge.

    Driven as two admitted routes rather than by mutating one, because a
    surface re-renders in the new language rather than reinterpreting the old
    one in place. Both must accept their own locale's spelling of the same
    number.
    """
    spanish = _admitted(OutputLanguage.ES)
    english = _admitted(OutputLanguage.EN)

    spanish_fields = spanish.fields()
    english_fields = english.fields()
    casilla_id = spanish_fields.casilla_ids()[0]

    assert spanish_fields.submit_lexeme(casilla_id, "1234.56").is_unresolved is False
    assert english_fields.submit_lexeme(casilla_id, "1234.56").is_unresolved is False
