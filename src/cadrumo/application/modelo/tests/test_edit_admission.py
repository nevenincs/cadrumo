"""Focused proofs for the value-free Modelo Edit Contract admission producer."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
from typing import override

import pytest
import yaml

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)
from ....domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.ids import RevisionId
from ....domain.calculations.registry.ledger_renta_income_bindings import LedgerRentaIncomeProvider
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import (
    BindingDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.financial_operand_contract import OperationTransientFinancialOperandPublicDeclarationV1
from ...operations.registry import OperationPublicContractSetV1, OperationPublicDefinitionContractV1
from ...operations.schema_identity import OperationSchemaIdentityV1
from ...operations.subject_reference import OperationSubjectReferenceV1
from ..edit_admission import admit_modelo_edit_baseline
from ..edit_apply_scalar_contracts import wire_scalar_value
from ..edit_contract import ModeloEditMutationFamily
from ..edit_execution import channel_value
from ..edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditFindingSeverity,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableReason,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditParseRequestV1,
    ModeloEditParseResultV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditSubmissionV1,
    ModeloEditValueAddressV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from ..edit_parsing import parse_modelo_edit_lexeme
from ..edit_preflight import INTENT_NOT_ADMITTED, preflight_modelo_edit
from ..edit_review_wording import edit_finding_words, edit_refusal_words
from ..edit_services import validate_binding_intent
from ..edit_transient_operand import modelo_edit_financial_operand
from ..edit_value_grammar import ModeloEditValueGrammarV1
from ..work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ..work_form_models import (
    ModeloWorkForm,
    revised_field,
)
from ..work_form_scalar_values import comparable_entry
from .advisory_diagnostic_repositories import EmptyObservationRepository
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_M100_YEAR = newest_authored_edition("100")
_M100_REVISION_ID = str(revision_covering("100", _M100_YEAR).id)
_NOW = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
_DIGEST = "a" * 64


def _recording_operation(
    prepared: RegistrySnapshot, layout: FormLayoutDefinition | None = None
) -> tuple[PinnedAuthorityOperation, list[dict[str, object]]]:
    """Return a pinned operation serving ``prepared`` and its form ``layout``, and the coordinates it is asked for."""
    calls: list[dict[str, object]] = []

    class _RecordingOperation(PinnedAuthorityOperation):
        @override
        def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
            return filing_year_envelope()

        @override
        def form_layout(self, modelo_id: str | Modelo, revision_id: str) -> FormLayoutDefinition | None:
            return layout

        @override
        def snapshot(
            self,
            modelo_id: str | Modelo,
            *,
            filing_year: int,
            period: str,
            on: date | None = None,
            revision_id: RevisionId | None = None,
            grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
        ) -> RegistrySnapshot:
            calls.append(
                {
                    "modelo_id": modelo_id,
                    "filing_year": filing_year,
                    "period": period,
                    "on": on,
                    "revision_id": revision_id,
                    "grade": grade,
                }
            )
            return prepared

    return _RecordingOperation.__new__(_RecordingOperation), calls


_MONEY_VALUE = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)


def _casilla(casilla_id: str, input_kind: InputKind, data_type: CasillaDataType) -> CasillaDefinition:
    return CasillaDefinition.model_construct(id=casilla_id, input_kind=input_kind, data_type=data_type)


def _manual_binding(binding_id: str) -> BindingDefinition:
    return BindingDefinition.model_construct(
        id=binding_id, provider=ManualInputProvider.model_construct(), value=_MONEY_VALUE
    )


def _ledger_binding(binding_id: str) -> BindingDefinition:
    return BindingDefinition.model_construct(
        id=binding_id, provider=LedgerRentaIncomeProvider.model_construct(), value=_MONEY_VALUE
    )


def _modelo_100_snapshot(
    casillas: tuple[CasillaDefinition, ...],
    bindings: tuple[BindingDefinition, ...],
) -> RegistrySnapshot:
    revision = ModeloRevision.model_construct(
        id=_M100_REVISION_ID,
        casillas=casillas,
        bindings=bindings,
        completeness_manifest=None,
    )
    return RegistrySnapshot.model_construct(modelo=ModeloDefinition.model_construct(id="100"), revision=revision)


def _work_unit(*, current_calculation_revision_id: str | None = None) -> WorkUnit:
    period = Period.from_year_and_code(_M100_YEAR, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="income-edit-bucket",
            modelo="100",
            filing_year=_M100_YEAR,
            period=period,
            revision_id=_M100_REVISION_ID,
        ),
        bucket_id="income-edit-bucket",
        modelo="100",
        filing_year=_M100_YEAR,
        period=period,
        revision_id=_M100_REVISION_ID,
        name=f"Income {_M100_YEAR}",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=current_calculation_revision_id,
    )


def _snapshot() -> RegistrySnapshot:
    return _modelo_100_snapshot(
        casillas=(
            _casilla("0001", InputKind.MANUAL, CasillaDataType.TEXT),
            _casilla("0171", InputKind.COMPUTED, CasillaDataType.MONEY),
        ),
        bindings=(
            _manual_binding("renta-manual"),
            _ledger_binding("renta-ledger"),
        ),
    )


_EDIT_DECLARATION = modelo_edit_financial_operand(None)
#: The public projection of the real edit operand declaration admission pins.
_EDIT_FINANCIAL_OPERAND = OperationTransientFinancialOperandPublicDeclarationV1(
    operand_schema=_EDIT_DECLARATION.operand_schema,
    baseline_schema=_EDIT_DECLARATION.baseline_schema,
    lifetime_seconds=_EDIT_DECLARATION.lifetime.total_seconds(),
)


def _contracts(*, include_edit: bool = True) -> OperationPublicContractSetV1:
    schema = OperationSchemaIdentityV1(
        schema_id="modelo.edit.apply.request", schema_version=1, schema_fingerprint=_DIGEST
    )
    contract = OperationPublicDefinitionContractV1.model_construct(
        manifest_version=4,
        definition_id="modelo.edit.apply",
        request_schema=schema,
        subject_reference=OperationSubjectReferenceV1.payload_field("work_unit_id"),
        result_schema=OperationSchemaIdentityV1(
            schema_id="modelo.edit.apply.result", schema_version=1, schema_fingerprint="b" * 64
        ),
        review_projection_schema=None,
        workspace_refresh_target_schema=OperationSchemaIdentityV1(
            schema_id="modelo.workspace.refresh-target", schema_version=1, schema_fingerprint="c" * 64
        ),
        transient_financial_operand=_EDIT_FINANCIAL_OPERAND,
        definition_contract_digest="d" * 64,
    )
    return OperationPublicContractSetV1.model_construct(
        definitions=(contract,) if include_edit else (),
        contract_set_digest="e" * 64,
    )


def _admit(
    *,
    current_calculation_revision_id: str | None = None,
    contracts: OperationPublicContractSetV1 | None = None,
    snapshot: RegistrySnapshot | None = None,
):
    work_unit = _work_unit(current_calculation_revision_id=current_calculation_revision_id)
    operation, calls = _recording_operation(_snapshot() if snapshot is None else snapshot)
    outcome = admit_modelo_edit_baseline(
        work_unit_id=work_unit.work_unit_id,
        work_catalogue=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
        calculation_catalogue=CalculationRevisionCatalogue(),
        operation=operation,
        operation_contracts=_contracts() if contracts is None else contracts,
        issued_at=_NOW,
    )
    return outcome, calls


def _sized_snapshot(*, casillas: int, bindings: int) -> RegistrySnapshot:
    return _modelo_100_snapshot(
        casillas=tuple(
            _casilla(f"{index:04d}", InputKind.COMPUTED, CasillaDataType.MONEY) for index in range(1, casillas + 1)
        ),
        bindings=tuple(_manual_binding(f"renta-surface-{index}") for index in range(bindings)),
    )


def test_published_modelo_100_surface_size_is_admitted_without_dropping_entries() -> None:
    outcome, _ = _admit(snapshot=_sized_snapshot(casillas=2249, bindings=71))

    assert isinstance(outcome, ModeloEditAdmittedV1)
    assert len(outcome.baseline.permitted_surface) == 2320
    assert (
        sum(
            isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
            for entry in outcome.baseline.permitted_surface
        )
        == 71
    )


def _published_modelo_100_baseline() -> ModeloEditBaselineV1:
    return _published_baseline("100", filing_year=_M100_YEAR, code="0A")


def _read_entry(
    baseline: ModeloEditBaselineV1, address: ModeloEditValueAddressV1, lexeme: str, language: OutputLanguage
) -> ModeloEditParseResultV1:
    return parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(address=address, entry_locale=language, lexeme=lexeme),
        baseline=baseline,
        tax_id_format=None,
    )


def _writable_yes_no_addresses(
    baseline: ModeloEditBaselineV1,
) -> list[tuple[ModeloEditValueAddressV1, ModeloEditValueGrammarV1]]:
    found: list[tuple[ModeloEditValueAddressV1, ModeloEditValueGrammarV1]] = []
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.grammar.data_type == "boolean":
            found.append((ModeloEditScalarAddressV1(casilla_id=entry.casilla_id), entry.grammar))
        elif (
            isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.grammar.data_type == "boolean"
        ):
            found.append((ModeloEditBindingAddressV1(binding_id=entry.binding_id), entry.grammar))
    return found


#: Each way a published declaration offers a yes/no: Modelo 100 writes boolean casillas directly, and
#: Modelo 131 offers manual-input boolean bindings, the only source of a writable binding override.
_YES_NO_SOURCES = (
    pytest.param("100", "0A", ModeloEditScalarAddressV1, id="scalar-casilla"),
    pytest.param("131", "1T", ModeloEditBindingAddressV1, id="binding-override"),
)


@pytest.mark.parametrize(("modelo", "code", "address_type"), _YES_NO_SOURCES)
@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_yes_or_no_on_a_published_declaration_reads_the_1_or_0_its_editor_sends(
    language: OutputLanguage, modelo: str, code: str, address_type: type[ModeloEditValueAddressV1]
) -> None:
    baseline = _published_baseline(modelo, filing_year=_YEAR, code=code)
    addresses = [
        (address, grammar) for address, grammar in _writable_yes_no_addresses(baseline) if type(address) is address_type
    ]

    assert addresses
    for address, grammar in addresses:
        for lexeme, expected, channel in (("1", True, "1"), ("0", False, "0")):
            read = _read_entry(baseline, address, lexeme, language)
            assert isinstance(read, ModeloEditParsedValueV1), address
            assert read.value is expected
            # What the window sends back on apply is that value, and it reaches the engine as the figure.
            assert (
                channel_value(wire_scalar_value(read.value), address=address, grammar=grammar, tax_id_format=None)
                == channel
            )
        for lexeme, reason in (
            ("2", ModeloEditParseReason.NOT_A_BOOLEAN),
            ("true", ModeloEditParseReason.NOT_A_BOOLEAN),
            ("  ", ModeloEditParseReason.EMPTY),
        ):
            refused = _read_entry(baseline, address, lexeme, language)
            assert isinstance(refused, ModeloEditRefusedV1), address
            assert isinstance(refused.refusal, ModeloEditParseRefusalV1)
            assert refused.refusal.reason is reason


def _published_baseline(modelo: str, *, filing_year: int, code: str) -> ModeloEditBaselineV1:
    snapshot = published_snapshot(modelo, filing_year=filing_year, period=code)
    period = Period.from_year_and_code(filing_year, code)
    revision_id = str(snapshot.revision.id)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="edit-bucket", modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id="edit-bucket",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo} {filing_year}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    operation, _ = _recording_operation(snapshot)
    outcome = admit_modelo_edit_baseline(
        work_unit_id=work_unit.work_unit_id,
        work_catalogue=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
        calculation_catalogue=CalculationRevisionCatalogue(),
        operation=operation,
        operation_contracts=_contracts(),
        issued_at=_NOW,
    )
    assert isinstance(outcome, ModeloEditAdmittedV1)
    return outcome.baseline


@pytest.mark.parametrize("filing_year", filing_year_envelope().years[-2:])
def test_a_box_that_declares_a_blank_token_keeps_missing_blank_and_refused_apart(filing_year: int) -> None:
    baseline = _published_baseline("322", filing_year=filing_year, code="01")
    (grammar,) = (
        entry.grammar
        for entry in baseline.permitted_surface
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == "decl.sin-actividad"
    )
    address = ModeloEditScalarAddressV1(casilla_id="decl.sin-actividad")

    assert grammar.choices is not None
    assert [choice.code for choice in grammar.choices] == ["X", ""]
    # Nothing typed is a stated blank, which the design allows; no entry at all stays no entry.
    blank = _read_entry(baseline, address, "", OutputLanguage.ES)
    assert isinstance(blank, ModeloEditParsedValueV1)
    assert blank.value == ""
    marked = _read_entry(baseline, address, "x", OutputLanguage.ES)
    assert isinstance(marked, ModeloEditParsedValueV1)
    assert marked.value == "X"
    refused = _read_entry(baseline, address, "Y", OutputLanguage.ES)
    assert isinstance(refused, ModeloEditRefusedV1)
    assert isinstance(refused.refusal, ModeloEditParseRefusalV1)
    assert refused.refusal.reason is ModeloEditParseReason.NOT_IN_CHOICES


def test_a_province_box_serves_every_province_with_the_key_of_its_word() -> None:
    baseline = _published_baseline("714", filing_year=_YEAR, code="0A")
    grammars = [
        entry.grammar
        for entry in baseline.permitted_surface
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.grammar.data_type == "province_code"
    ]

    assert grammars
    for grammar in grammars:
        assert grammar.choices is not None
        assert [choice.code for choice in grammar.choices] == [f"{number:02d}" for number in range(1, 53)]
        assert grammar.choices[27].word == "application.modelo.edit_choice.province_code.28"


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_each_province_word_is_the_name_the_official_table_gives_its_code(locale: str) -> None:
    table = (
        files("cadrumo")
        .joinpath("_data", "corpus", "normatives", "html", "orden-eha-3481-2008.html.extracted.md")
        .read_text(encoding="utf-8")
    )
    lines = [line.strip() for line in table.splitlines()]
    official: dict[str, str] = {}
    for previous, line in itertools.pairwise(lines):
        if len(line) == 2 and line.isdecimal() and "01" <= line <= "52" and previous.istitle() and line not in official:
            official[line] = previous
    catalogue = yaml.safe_load(
        files("cadrumo").joinpath("locales", locale, "application.yml").read_text(encoding="utf-8")
    )
    words = catalogue["application"]["modelo"]["edit_choice"]["province_code"]

    assert {code: words[code] for code in official} == official
    assert official["28"] == "Madrid"
    assert len(words) == 52


def test_choosing_the_same_yes_or_no_again_changes_nothing(authority_operation: PinnedAuthorityOperation) -> None:
    baseline = _published_modelo_100_baseline()
    on_form = {
        str(field.address.casilla_id): field
        for field in built_form(authority_operation, "100", _M100_YEAR, "0A").fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    address = next(
        address
        for address, _ in _writable_yes_no_addresses(baseline)
        if isinstance(address, ModeloEditScalarAddressV1) and str(address.casilla_id) in on_form
    )
    # A calculation holds a yes or no box as the figure its decimal channel carried.
    field = revised_field(
        on_form[str(address.casilla_id)],
        editability=ModeloFormEditability.EDITABLE_VALUE,
        origin=ModeloFormOrigin.ENTERED,
        value=Decimal("1"),
    )

    read = _read_entry(baseline, address, "1", OutputLanguage.EN)
    assert isinstance(read, ModeloEditParsedValueV1)
    assert comparable_entry(read.value) == field.own_value
    other = _read_entry(baseline, address, "0", OutputLanguage.EN)
    assert isinstance(other, ModeloEditParsedValueV1)
    assert comparable_entry(other.value) != field.own_value


def test_a_date_or_year_box_the_filer_fills_is_refused_for_want_of_an_engine_channel() -> None:
    revision = published_snapshot("100", filing_year=_M100_YEAR, period="0A").revision
    baseline = _published_modelo_100_baseline()
    templates = set(row_field_template_records_by_casilla(revision))
    filled_by_hand = {
        casilla.id: casilla.data_type
        for casilla in revision.casillas
        if casilla.input_kind is InputKind.MANUAL
        and casilla.data_type in {CasillaDataType.DATE, CasillaDataType.YEAR}
        and casilla.id not in templates
    }
    reasons = {
        entry.casilla_id: entry.reason
        for entry in baseline.permitted_surface
        if isinstance(entry, ModeloEditNonWritableScalarSurfaceEntryV1)
    }

    assert CasillaDataType.YEAR in filled_by_hand.values()
    for casilla_id in filled_by_hand:
        assert reasons[casilla_id] is ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE
        read = _read_entry(baseline, ModeloEditScalarAddressV1(casilla_id=casilla_id), str(_YEAR), OutputLanguage.ES)
        assert isinstance(read, ModeloEditRefusedV1)
        assert isinstance(read.refusal, ModeloEditParseRefusalV1)
        assert read.refusal.reason is ModeloEditParseReason.ADDRESS_NOT_WRITABLE


def test_oversized_edit_surface_refuses_at_admission_before_model_validation() -> None:
    from ..edit_models import MAX_MODELO_EDIT_SURFACE_ENTRIES

    outcome, _ = _admit(snapshot=_sized_snapshot(casillas=MAX_MODELO_EDIT_SURFACE_ENTRIES + 1, bindings=0))

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.code is ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT
    assert outcome.refusal.facts == ("edit_surface_exceeds_contract_limit",)


def test_admission_refuses_when_the_law_selected_revision_is_not_the_work_units_pinned_revision() -> None:
    """The resolver picks the revision; a work unit pinned to another one is refused, not redirected."""
    moved = _snapshot()
    snapshot = RegistrySnapshot.model_construct(
        modelo=moved.modelo,
        revision=moved.revision.model_copy(update={"id": "moved-revision"}),
    )

    outcome, _ = _admit(snapshot=snapshot)

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.code is ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT
    assert outcome.refusal.facts == ("law_selected_revision_id",)


def test_admission_re_resolves_the_work_and_pinned_authority_into_a_value_free_five_minute_baseline() -> None:
    outcome, calls = _admit()

    assert isinstance(outcome, ModeloEditAdmittedV1)
    baseline = outcome.baseline
    assert baseline.issued_at == _NOW
    assert baseline.expires_at == _NOW + timedelta(minutes=5)
    assert baseline.law_selected_revision_id == _M100_REVISION_ID
    assert baseline.compatibility.operation_definition_id == "modelo.edit.apply"
    assert calls == [
        {
            "modelo_id": "100",
            "filing_year": _M100_YEAR,
            "period": "0A",
            "on": None,
            "revision_id": None,
            "grade": RegistryAuthorityGrade.CALCULATION,
        }
    ]
    assert not any("value" in field for field in baseline.model_dump(mode="json"))
    assert any(
        isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == "0001"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditNonWritableScalarSurfaceEntryV1) and entry.casilla_id == "0171"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == "renta-manual"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == "renta-ledger"
        for entry in baseline.permitted_surface
    )


def test_admission_refuses_a_missing_current_calculation_head_without_reusing_a_workspace_read() -> None:
    outcome, _ = _admit(current_calculation_revision_id="f" * 64)

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.code == "calculation_head_conflict"


def test_admission_refuses_when_the_required_public_operation_contract_is_not_composed() -> None:
    outcome, _ = _admit(contracts=_contracts(include_edit=False))

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.kind == "unsupported_compatibility"


def test_a_ledger_binding_is_locked_by_its_source_not_by_the_schema() -> None:
    outcome, _ = _admit()

    assert isinstance(outcome, ModeloEditAdmittedV1)
    ledger = next(
        entry
        for entry in outcome.baseline.permitted_surface
        if isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == "renta-ledger"
    )
    assert ledger.reason is ModeloEditNonWritableReason.SOURCE_LOCKED


def test_a_revision_below_calculation_grade_is_refused_not_raised() -> None:
    """A revision that only declares applicability cannot be calculated, so it cannot be edited."""

    class _ApplicabilityOnlyOperation(PinnedAuthorityOperation):
        @override
        def snapshot(
            self,
            modelo_id: str | Modelo,
            *,
            filing_year: int,
            period: str,
            on: date | None = None,
            revision_id: RevisionId | None = None,
            grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
        ) -> RegistrySnapshot:
            raise RegistryValidationError("the revision cannot satisfy the requested calculation snapshot authority")

    work_unit = _work_unit()
    outcome = admit_modelo_edit_baseline(
        work_unit_id=work_unit.work_unit_id,
        work_catalogue=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
        calculation_catalogue=CalculationRevisionCatalogue(),
        operation=_ApplicabilityOnlyOperation.__new__(_ApplicabilityOnlyOperation),
        operation_contracts=_contracts(),
        issued_at=_NOW,
    )

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert isinstance(outcome.refusal, ModeloEditDomainRefusalV1)
    assert outcome.refusal.code is ModeloEditRefusalCode.ADMISSION_DENIED
    assert outcome.refusal.facts == ("registry_authority_grade",)


def _held_source_unit(modelo: str, *, filing_year: int, code: str) -> WorkUnit:
    """A work unit for an earlier declaration the application holds."""
    period = Period.from_year_and_code(filing_year, code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="edit-bucket", modelo=modelo, filing_year=filing_year, period=period, revision_id="held"
        ),
        bucket_id="edit-bucket",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id="held",
        name=f"{modelo} {filing_year}",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _served_baseline(
    operation: PinnedAuthorityOperation,
    modelo: str,
    *,
    filing_year: int,
    code: str,
    held: tuple[WorkUnit, ...] = (),
) -> tuple[ModeloEditBaselineV1, WorkUnitCatalogue]:
    """Admit an edit baseline over the published revision and its published form layout."""
    snapshot = form_snapshot(operation, modelo, filing_year, code)
    period = Period.from_year_and_code(filing_year, code)
    revision_id = str(snapshot.revision.id)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="edit-bucket", modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id="edit-bucket",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo} {filing_year}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    catalogue = WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in (work_unit, *held)})
    recording, _ = _recording_operation(snapshot, operation.form_layout(modelo, revision_id))
    outcome = admit_modelo_edit_baseline(
        work_unit_id=work_unit.work_unit_id,
        work_catalogue=catalogue,
        calculation_catalogue=CalculationRevisionCatalogue(),
        operation=recording,
        operation_contracts=_contracts(),
        issued_at=datetime.now(UTC),
        observation_repository=EmptyObservationRepository(),
        filing_catalogue=ModeloRecordCatalogue(),
    )
    assert isinstance(outcome, ModeloEditAdmittedV1)
    return outcome.baseline, catalogue


def _binding_entry(
    baseline: ModeloEditBaselineV1, binding_id: str
) -> ModeloEditWritableBindingOverrideSurfaceEntryV1 | ModeloEditNonWritableBindingOverrideSurfaceEntryV1:
    return next(
        entry
        for entry in baseline.permitted_surface
        if isinstance(
            entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
        )
        and entry.binding_id == binding_id
    )


def _form_bindings(form: ModeloWorkForm) -> set[str]:
    """Every binding a field or answer of the form is addressed to, edits, or is fed by first."""
    served = {
        str(address.binding_id)
        for field in form.fields()
        for address in (field.address, field.edit_address)
        if isinstance(address, ModeloFormBindingAddressV1)
    }
    return served | {str(field.bindings[0].binding_id) for field in form.fields() if field.bindings}


def _override(binding_id: str) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id),
        kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        value="12.50",
    )


def _preflight(
    baseline: ModeloEditBaselineV1, catalogue: WorkUnitCatalogue, intent: ModeloBindingEditIntentV1
) -> ModeloEditPreflightEvaluatedV1:
    result = preflight_modelo_edit(
        ModeloEditSubmissionV1(
            baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, binding_intents=(intent,)
        ),
        work_catalogue=catalogue,
        calculation_catalogue=CalculationRevisionCatalogue(),
        tax_id_format=None,
        prior_carry_bindings=frozenset(),
    )
    assert isinstance(result, ModeloEditPreflightEvaluatedV1)
    return result


_FIRST_QUARTER_ANSWER = "irpf.previous_year_economic_activity_net_income"
_QUARTERLY_ROW_FIELD = "modelo-131.dpa.local-unico"
_FOREIGN_ASSET_ROW_FIELD = "modelo-720.type_2.numero-de-valores"
_FOREIGN_ASSET_BASELINE = "modelo-720-prior-year-cuentas-valoracion-baseline"


def test_an_override_the_form_serves_an_answer_for_is_admitted(authority_operation: PinnedAuthorityOperation) -> None:
    baseline, catalogue = _served_baseline(authority_operation, "130", filing_year=_YEAR, code="1T")
    form = built_form(authority_operation, "130", _YEAR, "1T", permitted_surface=baseline.permitted_surface)
    address = ModeloEditBindingAddressV1(binding_id=_FIRST_QUARTER_ANSWER)

    assert isinstance(_binding_entry(baseline, _FIRST_QUARTER_ANSWER), ModeloEditWritableBindingOverrideSurfaceEntryV1)
    answer = next(
        field
        for field in form.answers
        if field.edit_address == ModeloFormBindingAddressV1(binding_id=_FIRST_QUARTER_ANSWER)
    )
    assert answer.editability in {ModeloFormEditability.EDITABLE_OVERRIDE, ModeloFormEditability.OVERRIDABLE_SOURCE}
    assert validate_binding_intent(baseline, address, ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE) is None
    assert _preflight(baseline, catalogue, _override(_FIRST_QUARTER_ANSWER)).findings == ()


def _statement(binding_id: str) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id),
        kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
        value="12846.30",
    )


@pytest.mark.parametrize("offset", [0, 1], ids=["floor", "floor-plus-one"])
def test_a_carry_the_application_holds_no_source_for_takes_a_stated_figure_inside_or_outside_the_envelope(
    authority_operation: PinnedAuthorityOperation, offset: int
) -> None:
    year = filing_year_envelope().floor + offset
    baseline, catalogue = _served_baseline(authority_operation, "130", filing_year=year, code="1T")
    entry = _binding_entry(baseline, _FIRST_QUARTER_ANSWER)

    assert isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in entry.allowed_intents
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in entry.allowed_intents
    address = ModeloEditBindingAddressV1(binding_id=_FIRST_QUARTER_ANSWER)
    assert validate_binding_intent(baseline, address, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE) is None
    assert _preflight(baseline, catalogue, _statement(_FIRST_QUARTER_ANSWER)).findings == ()


@pytest.mark.parametrize("offset", [0, 1], ids=["floor", "floor-plus-one"])
def test_a_carry_whose_source_the_application_holds_is_refused_a_stated_figure(
    authority_operation: PinnedAuthorityOperation, offset: int
) -> None:
    year = filing_year_envelope().floor + offset
    source = _held_source_unit("100", filing_year=year - 1, code="0A")
    baseline, catalogue = _served_baseline(authority_operation, "130", filing_year=year, code="1T", held=(source,))
    entry = _binding_entry(baseline, _FIRST_QUARTER_ANSWER)

    # Where a source exists the dependency follows it, so a figure stated over it would never read as proof.
    assert isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE not in entry.allowed_intents
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in entry.allowed_intents
    refusal = validate_binding_intent(
        baseline,
        ModeloEditBindingAddressV1(binding_id=_FIRST_QUARTER_ANSWER),
        ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
    )
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.code is ModeloEditRefusalCode.DISALLOWED_INTENT
    findings = _preflight(baseline, catalogue, _statement(_FIRST_QUARTER_ANSWER)).findings
    assert [finding.code for finding in findings] == [INTENT_NOT_ADMITTED]


def test_a_stated_figure_must_carry_a_value() -> None:
    with pytest.raises(ValueError, match="ATTEST_PRIOR_VALUE binding intent requires a typed value"):
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=_FIRST_QUARTER_ANSWER),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
        )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "code", "binding_id", "reason"),
    [
        ("131", _YEAR, "3T", _QUARTERLY_ROW_FIELD, ModeloEditNonWritableReason.ROW_FIELD_TEMPLATE),
        ("720", _YEAR, "0A", _FOREIGN_ASSET_ROW_FIELD, ModeloEditNonWritableReason.ROW_FIELD_TEMPLATE),
        ("720", _YEAR, "0A", _FOREIGN_ASSET_BASELINE, ModeloEditNonWritableReason.NOT_READ_BY_CALCULATION),
    ],
)
@pytest.mark.parametrize("language", list(OutputLanguage))
def test_an_override_the_form_serves_nothing_for_is_refused_in_words(
    authority_operation: PinnedAuthorityOperation,
    modelo: str,
    filing_year: int,
    code: str,
    binding_id: str,
    reason: ModeloEditNonWritableReason,
    language: OutputLanguage,
) -> None:
    baseline, catalogue = _served_baseline(authority_operation, modelo, filing_year=filing_year, code=code)
    form = built_form(authority_operation, modelo, filing_year, code, permitted_surface=baseline.permitted_surface)
    address = ModeloEditBindingAddressV1(binding_id=binding_id)

    entry = _binding_entry(baseline, binding_id)
    assert isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    assert entry.reason is reason
    assert binding_id not in _form_bindings(form), "the form serves a field for an override the surface refuses"
    refusal = validate_binding_intent(baseline, address, ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE)
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.code is ModeloEditRefusalCode.DISALLOWED_INTENT
    assert refusal.address == address
    findings = _preflight(baseline, catalogue, _override(binding_id)).findings
    assert [(finding.code, finding.severity) for finding in findings] == [
        (INTENT_NOT_ADMITTED, ModeloEditFindingSeverity.ERROR)
    ]
    for words in (edit_finding_words(findings[0], language), edit_refusal_words(refusal, language)):
        assert words
        assert "workspace." not in words
    # The reason the surface records is worded in every language for the form that would show it.
    reason_words = lookup_translation(f"workspace.modelo.not_writable.{reason.value}", locale=language.value)
    assert reason_words is not None
    assert len(reason_words) > 0
    assert "not_writable" not in reason_words


def test_the_surface_and_the_form_agree_on_every_published_override(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    admitted = 0
    for modelo, filing_year, code in (
        ("100", _M100_YEAR, "0A"),
        ("130", _YEAR, "1T"),
        ("131", _YEAR, "3T"),
        ("720", _YEAR, "0A"),
    ):
        baseline, _catalogue = _served_baseline(authority_operation, modelo, filing_year=filing_year, code=code)
        form = built_form(authority_operation, modelo, filing_year, code, permitted_surface=baseline.permitted_surface)
        # A column the filer states row by row is admitted for statements that each name a calculated row;
        # the form serves no field for it, so it is outside this agreement.
        row_stated = {
            binding.id
            for binding in form_snapshot(authority_operation, modelo, filing_year, code).revision.bindings
            if binding.absence_attestation is not None and binding.absence_attestation.row_grain
        }
        writable = {
            entry.binding_id
            for entry in baseline.permitted_surface
            if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id not in row_stated
        }
        assert writable <= _form_bindings(form), f"{modelo}: {sorted(writable - _form_bindings(form))}"
        admitted += len(writable)
    assert admitted, "no published override was admitted, so the agreement proved nothing"
