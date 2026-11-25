"""A filing, receipt or local observation the operator brings in names the door of its refusal cause.

Each refusal is raised by the function that owns the check and read through the
reader the operation error detail uses.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core.errors.error_codes import resolve_error_message
from ....core.operator_action_enums import ActionArgumentStatus, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.justificante.schema import Justificante
from ....domain.modelos.filing_record import AeatRegisterRef, ExternalEvidenceKind
from ....domain.modelos.work_unit import WorkUnit
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from .. import registry_helpers
from ..action_errors import ExternalModeloImportError, ModeloLocalObservationError
from ..external_import_actions import (
    ExternalFilingBaselineSource,
    external_filing_source_casillas,
    require_bound_justificante_artifact,
)
from ..filed_revision_observation import require_filing_result_disposition
from ..filing_chain_reconciliation import AeatRegisterEntry
from ..local_observation_actions import (
    canonical_casilla_values,
)
from ..local_observation_spreadsheet import parse_casilla_value_spreadsheet

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_OTHER_PERIOD = Period.from_year_and_code(_YEAR, "2T")
_TAX_ID = "X0001500M"
_BUCKET_ID = "13000000-0000-4000-8000-0000000000c1"
_IMPORT_ACTION = "operator.modelo.filing_record.import"


class _Receipts:
    """A receipt store holding the receipts it was given."""

    def __init__(self, *held: Justificante) -> None:
        self._held = {receipt.csv: receipt for receipt in held}

    def load(self, csv: str, /) -> Justificante | None:
        return self._held.get(csv)

    def save(self, justificante: Justificante, /) -> None:
        self._held[justificante.csv] = justificante

    def iter_justificantes(self) -> Iterator[Justificante]:
        yield from (self._held[csv] for csv in sorted(self._held))


def _receipt(csv: str = "RECEIPT0000001") -> Justificante:
    return Justificante(
        csv=csv,
        modelo="130",
        period=_PERIOD,
        ejercicio=str(_YEAR),
        presentation_id=None,
        presented_at=datetime(_YEAR, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=_TAX_ID,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("receipt-source.pdf"),
        source_pdf_sha256=hashlib.sha256(csv.encode()).hexdigest(),
        parsed_at=datetime(_YEAR, 4, 16, 12, 0, tzinfo=UTC),
    )


def _source(lexicals: dict[str, str], *, period: Period = _PERIOD) -> ExternalFilingBaselineSource:
    return ExternalFilingBaselineSource(
        modelo="130",
        filing_year=_YEAR,
        period=period,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="REGISTER-REF-1",
        tax_id=_TAX_ID,
        casilla_lexicals=lexicals,
    )


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _assert_import_door(error: BaseException, *, resolved: set[str], missing: set[str]) -> None:
    verdict = _verdict(error)
    assert verdict.action is not None
    assert verdict.action.action_id == _IMPORT_ACTION
    assert {b.argument_name for b in verdict.argument_bindings if b.status is ActionArgumentStatus.RESOLVED} == resolved
    assert set(verdict.missing_argument_names) == missing


def _assert_no_action(error: BaseException, outcome: NoRecoveryOutcome) -> None:
    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is outcome


def _refusal_of(call: object) -> ExternalModeloImportError:
    assert callable(call)
    with pytest.raises(ExternalModeloImportError) as caught:
        call()
    return caught.value


@pytest.mark.parametrize(
    "lexicals",
    [{}, {"0001": "  "}, {"0001": "not a number"}],
    ids=["no_values", "blank_value", "non_numeric_value"],
)
def test_a_source_value_the_operator_can_state_again_opens_the_import_naming_the_evidence_it_holds(
    lexicals: dict[str, str],
) -> None:
    error = _refusal_of(lambda: external_filing_source_casillas(_source(lexicals)))

    _assert_import_door(error, resolved={"evidence_kind", "evidence_reference_id"}, missing={"work_unit_id"})
    bound = {b.argument_name: b.value for b in _verdict(error).argument_bindings}
    assert bound["evidence_kind"] == ExternalEvidenceKind.AEAT_CSV_REGISTER.value
    assert bound["evidence_reference_id"] == "REGISTER-REF-1"


def test_a_source_the_application_built_inconsistently_is_terminal() -> None:
    other_year = Period.from_year_and_code(_YEAR - 1, "1T")
    error = _refusal_of(lambda: external_filing_source_casillas(_source({"0001": "1"}, period=other_year)))
    _assert_no_action(error, NoRecoveryOutcome.TERMINAL)


@pytest.mark.usefixtures("operation")
def test_an_import_against_an_absent_authority_is_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    def absent_authority(**_: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", "authority.current.json")

    monkeypatch.setattr(registry_helpers, "_normalise_registry_casilla_inputs", absent_authority)
    error = _refusal_of(
        lambda: registry_helpers.reject_unknown_import_casillas(
            modelo=form_for_role("iva.periodic"), filing_year=_YEAR, period=_PERIOD, casilla_values={}
        )
    )
    _assert_no_action(error, NoRecoveryOutcome.TERMINAL)


def test_a_receipt_bound_import_without_a_declared_tax_id_opens_the_profile_edit() -> None:
    error = _refusal_of(
        lambda: require_bound_justificante_artifact(
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="RECEIPT0000001",
            modelo="130",
            filing_year=_YEAR,
            period=_PERIOD,
            expected_tax_id=None,
            justificante_repository=_Receipts(),
        )
    )

    verdict = _verdict(error)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert set(verdict.missing_argument_names) == {"profile_name"}


def test_a_receipt_that_is_not_stored_is_the_operators_decision() -> None:
    error = _refusal_of(
        lambda: require_bound_justificante_artifact(
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="RECEIPT0000001",
            modelo="130",
            filing_year=_YEAR,
            period=_PERIOD,
            expected_tax_id=_TAX_ID,
            justificante_repository=_Receipts(),
        )
    )

    _assert_no_action(error, NoRecoveryOutcome.OPERATOR_DECISION)


@pytest.mark.usefixtures("operation")
def test_a_receipt_for_another_period_opens_the_import_to_state_the_right_evidence() -> None:
    receipt = _receipt()
    error = _refusal_of(
        lambda: require_bound_justificante_artifact(
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id=receipt.csv,
            modelo="130",
            filing_year=_YEAR,
            period=_OTHER_PERIOD,
            expected_tax_id=_TAX_ID,
            justificante_repository=_Receipts(receipt),
        )
    )

    _assert_import_door(error, resolved={"evidence_kind", "evidence_reference_id"}, missing={"work_unit_id"})


def test_a_register_entry_for_another_period_than_its_year_is_terminal() -> None:
    other_year = Period.from_year_and_code(_YEAR - 1, "1T")
    error = _refusal_of(
        lambda: AeatRegisterEntry(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=_YEAR,
            period=other_year,
            register=AeatRegisterRef(expediente_id="EXP-1"),
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            tax_id=_TAX_ID,
        )
    )

    _assert_no_action(error, NoRecoveryOutcome.TERMINAL)


@pytest.mark.usefixtures("operation")
def test_a_receipt_that_disagrees_with_its_register_entry_opens_the_import() -> None:
    receipt = _receipt()
    error = _refusal_of(
        lambda: AeatRegisterEntry(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=_YEAR,
            period=_OTHER_PERIOD,
            register=AeatRegisterRef(expediente_id="EXP-1", csv=receipt.csv),
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            tax_id=_TAX_ID,
            justificante=receipt,
        )
    )

    _assert_import_door(error, resolved={"evidence_kind", "evidence_reference_id"}, missing={"work_unit_id"})


def _local_refusal(call: object) -> ModeloLocalObservationError:
    assert callable(call)
    with pytest.raises(ModeloLocalObservationError) as caught:
        call()
    return caught.value


@pytest.mark.parametrize(
    "casilla_values",
    [{}, {"not a casilla": Decimal(1)}, {"0001": "1"}, {"9999": Decimal(1)}],
    ids=["no_values", "malformed_id", "not_decimal", "undeclared"],
)
def test_stated_casillas_the_registry_refuses_are_the_operators_decision(casilla_values: dict[str, object]) -> None:
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context("130", filing_year=_YEAR, period=_PERIOD.registry_token)
        error = _local_refusal(lambda: canonical_casilla_values(revision=revision, casilla_values=casilla_values))

    _assert_no_action(error, NoRecoveryOutcome.OPERATOR_DECISION)


def test_a_spreadsheet_that_cannot_be_read_is_the_operators_decision(tmp_path: Path) -> None:
    absent = _local_refusal(lambda: parse_casilla_value_spreadsheet(tmp_path / "absent.csv"))
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")
    empty = _local_refusal(lambda: parse_casilla_value_spreadsheet(empty_file))
    malformed_file = tmp_path / "malformed.csv"
    malformed_file.write_text("casilla,value\n0001,abc\n", encoding="utf-8")
    malformed = _local_refusal(lambda: parse_casilla_value_spreadsheet(malformed_file))

    for error in (absent, empty, malformed):
        _assert_no_action(error, NoRecoveryOutcome.OPERATOR_DECISION)


@pytest.mark.usefixtures("operation")
def test_a_303_filing_without_its_result_disposition_is_terminal() -> None:
    work_unit = WorkUnit.model_construct(modelo=form_for_role("iva.periodic"), period=_PERIOD)
    error = _local_refusal(lambda: require_filing_result_disposition(work_unit=work_unit, result_disposition=None))

    _assert_no_action(error, NoRecoveryOutcome.TERMINAL)


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
def test_a_refusal_keeps_its_served_words(locale: str) -> None:
    error = _refusal_of(lambda: external_filing_source_casillas(_source({})))

    message = resolve_error_message(error, locale=locale)
    assert message
    assert "%{" not in message
