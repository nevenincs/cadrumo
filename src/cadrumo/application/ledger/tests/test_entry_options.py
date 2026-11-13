"""What a ledger entry form is offered, read through each list's real owner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, time
from decimal import Decimal
from importlib.resources import files
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ....core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bienes_inversion_catalogue import resolve_bienes_inversion_catalogue
from ....domain.calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ....domain.calculations.registry.invoice_legal_classification import resolve_invoice_legal_classification_catalogue
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ....domain.calculations.registry.iva_deduction_catalogue import resolve_iva_deduction_catalogue
from ....domain.calculations.registry.prorrata_register_catalogue import (
    prorrata_sector_letters,
    resolve_prorrata_register_catalogue,
)
from ....domain.categories.spending_category import SpendingCategory, SpendingCategoryFamily
from ....domain.categories.spending_category_catalogue import resolve_spending_category_catalogue
from ....domain.invoices.business_premises import SituacionInmueble
from ....domain.iva.establishment import StatedCountryCodeStatus, stated_country_code_status
from ....domain.renta.errors import RentaValidationError
from ....domain.renta.retencion_soportada import (
    RetencionSoportadaOrigen,
    RetencionSoportadaRecord,
    certificate_figures,
)
from ....domain.transactions.classification_rule import require_new_rule_decision
from ....domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    RULE_DECIDED_STATES,
    BusinessClassification,
)
from ....domain.transactions.errors import ClassificationRuleError, TransactionValidationError
from ....domain.transactions.irpf_categories import ledger_irpf_category_catalogue, require_ledger_irpf_category
from ....domain.transactions.m210_income_classification import M210IncomeClassification
from ....domain.transactions.model_validation import validate_business_pct_coupling
from ....domain.transactions.models import Transaction
from ....domain.usage_ratios.errors import UsageRatioValidationError
from ....domain.usage_ratios.model import UsageRatioProfile, eligible_usage_ratio_categories
from ...export.tabular import ExportSerializationFormat
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import actions_import
from ..actions_import import LedgerProviderID, installed_ledger_providers
from ..entry_options_operation import (
    LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
    LedgerEntryOptionsExecutionResult,
    LedgerEntryOptionsExecutor,
    LedgerEntryOptionsProjection,
    LedgerEntryOptionsRequest,
    build_ledger_entry_options_definition,
    build_ledger_entry_options_registration,
    ledger_entry_options,
)
from ..manual_update import command_from_patch
from ..models import ManualLedgerTransactionPatch
from .transaction_row_support import outgoing_manual_row

_ON_DATE = date(filing_year_envelope().horizon, 6, 15)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("31313131-3131-4131-8131-313131313131")
_OTHER_PROFILE = UUID("32323232-3232-4232-8232-323232323232")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@pytest.fixture(scope="module")
def served(operation: PinnedAuthorityOperation) -> dict[str, tuple[tuple[str, str | None], ...]]:
    return {
        family.family: tuple((option.value, option.label_key) for option in family.options)
        for family in ledger_entry_options(_PROFILE, operation=operation).families
    }


def test_every_family_is_served_once(served: dict[str, tuple[tuple[str, str | None], ...]]) -> None:
    assert set(served) == {
        "country",
        "currency",
        "deduction_fact_kind",
        "m210_payer_mode",
        "m210_tipo_renta",
        "iva_category",
        "irpf_category",
        "spending_category",
        "usage_ratio_category",
        "invoice_class",
        "premises_situation",
        "prorrata_provenance",
        "prorrata_sector_letter",
        "capital_good_kind",
        "capital_good_disposal",
        "import_format",
        "export_format",
        "gasto_capital_inmobiliario",
        "rental_lease",
        "rental_property",
        "withholding_certificate_figure",
    }


def _values(served: dict[str, tuple[tuple[str, str | None], ...]], family: str) -> list[str]:
    return [value for value, _ in served[family]]


def test_iva_categories_are_the_registry_catalogue_in_its_order(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    catalogue = resolve_iva_category_catalogue(authority=operation, effective_date=_ON_DATE)

    assert _values(served, "iva_category") == [str(token) for token in catalogue.all_categories]
    assert {"domestic_general", "intra_community_supply", "unknown"} <= set(_values(served, "iva_category"))
    for token in _values(served, "iva_category"):
        assert str(catalogue.require(token)) == token


def test_irpf_categories_are_the_taxonomy_ids(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    ids = _values(served, "irpf_category")

    assert ids == [item.id for item in ledger_irpf_category_catalogue(authority=operation)]
    assert "actividad_economica" in ids
    for category in ids:
        assert require_ledger_irpf_category(category, authority=operation) == category


def test_each_spending_category_is_served_once_under_the_family_the_registry_files_it_in(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    projection = {
        family.family: family.options for family in ledger_entry_options(_PROFILE, operation=operation).families
    }
    options = projection["spending_category"]
    catalogue = resolve_spending_category_catalogue(authority=operation)

    values = [option.value for option in options]
    assert len(values) == len(set(values))
    assert set(values) == {str(category) for category in catalogue.categories}
    assert {option.label_key for option in options} == {None}
    for option in options:
        assert option.group is not None
        assert str(catalogue.family_for(SpendingCategory.from_registry(option.value))) == option.group
    assert {option.group for option in options} == {family.value for family in SpendingCategoryFamily}
    assert _values(served, "spending_category") == values


def test_usage_ratio_categories_are_the_ones_a_ratio_may_be_stated_for(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    offered = _values(served, "usage_ratio_category")

    assert offered
    assert set(offered) == {str(category) for category in eligible_usage_ratio_categories()}
    assert set(offered) <= set(_values(served, "spending_category"))
    assert "ibi_vivienda_afecto" in offered
    assert "material_oficina" not in offered
    # The writer that owns the ratio accepts every offered category and refuses the others.
    empty = UsageRatioProfile()
    for category in offered:
        stated = empty.with_ratio(SpendingCategory.from_registry(category), Decimal("0.5"))
        assert stated.ratios[SpendingCategory.from_registry(category)] == Decimal("0.5")
    with pytest.raises(UsageRatioValidationError):
        empty.with_ratio(SpendingCategory.from_registry("material_oficina"), Decimal("0.5"))


def test_invoice_classes_are_the_ones_the_registry_declares(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    classes = _values(served, "invoice_class")
    catalogue = resolve_invoice_legal_classification_catalogue()

    assert classes == [str(token) for token in catalogue.invoice_class_choices]
    assert {
        str(catalogue.ordinaria_token),
        str(catalogue.simplificada_token),
        str(catalogue.rectificativa_token),
    } == set(classes)


_OPTIONAL_CERTIFICATE_FIGURES = (
    RetencionSoportadaCantidad.REDUCCIONES_APLICABLES,
    RetencionSoportadaCantidad.GASTOS_DEDUCIBLES,
)
"""The figures a record holds optionally because a certificate states them only for some income classes."""


def _stated_figure(figure: RetencionSoportadaCantidad, stated: frozenset[str]) -> Decimal | None:
    return Decimal("0.00") if figure.value in stated else None


def _withholding_record(income_class: RetencionSoportadaClase, stated: frozenset[str]) -> RetencionSoportadaRecord:
    """A record of ``income_class`` stating the optional figures named in ``stated`` and leaving the others out."""
    return RetencionSoportadaRecord(
        ejercicio=_ON_DATE.year,
        payer_tax_id="B00000001",
        payer_ref="0" * 64,
        income_class=income_class,
        importe_integro_dinerario=Decimal("1000.00"),
        valoracion_especie=Decimal("0.00"),
        retencion=Decimal("100.00"),
        ingreso_a_cuenta=Decimal("0.00"),
        ingreso_a_cuenta_repercutido=Decimal("0.00"),
        origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
        evidence_fingerprint="a" * 64,
        captured_at=datetime.combine(_ON_DATE, time(9), tzinfo=UTC),
        reducciones_aplicables=_stated_figure(RetencionSoportadaCantidad.REDUCCIONES_APLICABLES, stated),
        gastos_deducibles=_stated_figure(RetencionSoportadaCantidad.GASTOS_DEDUCIBLES, stated),
    )


def _served_figures(
    operation: PinnedAuthorityOperation,
) -> dict[str | None, frozenset[str]]:
    family = next(
        family
        for family in ledger_entry_options(_PROFILE, operation=operation).families
        if family.family == "withholding_certificate_figure"
    )
    grouped: dict[str | None, set[str]] = {}
    for option in family.options:
        grouped.setdefault(option.group, set()).add(option.value)
    return {group: frozenset(values) for group, values in grouped.items()}


def test_each_income_class_is_served_the_figures_its_record_takes(operation: PinnedAuthorityOperation) -> None:
    served = _served_figures(operation)

    assert set(served) == {income_class.value for income_class in RetencionSoportadaClase}
    for income_class in RetencionSoportadaClase:
        figures = served[income_class.value]
        assert figures == {figure.value for figure in certificate_figures(income_class)}
        record = _withholding_record(income_class, figures)
        assert not record.lacks_work_certificate_figures
        assert all(record.states(RetencionSoportadaCantidad(figure)) for figure in figures)
        for unserved in sorted(figure.value for figure in _OPTIONAL_CERTIFICATE_FIGURES if figure.value not in figures):
            with pytest.raises((RentaValidationError, ValidationError)):
                _withholding_record(income_class, figures | {unserved})


def test_withholding_figures_carry_their_words_and_keep_the_record_order(
    served: dict[str, tuple[tuple[str, str | None], ...]],
) -> None:
    options = served["withholding_certificate_figure"]

    assert all(
        label == f"application.ledger.entry_options.withholding_certificate_figure.{value}" for value, label in options
    )
    work = [figure.value for figure in certificate_figures(RetencionSoportadaClase.TRABAJO)]
    assert [value for value, _ in options][: len(work)] == work


def test_premises_situations_are_the_codes_the_record_carries(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    codes = _values(served, "premises_situation")

    assert codes == list(SituacionInmueble.form_codes(authority=operation).values())
    assert len(codes) == len(SituacionInmueble)
    for code in codes:
        assert SituacionInmueble.from_code(code, authority=operation).value in {m.value for m in SituacionInmueble}


def test_prorrata_provenances_and_sector_letters_are_the_register_vocabularies(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    catalogue = resolve_prorrata_register_catalogue(authority=operation)

    assert _values(served, "prorrata_provenance") == [str(item.token) for item in catalogue.provenances]
    assert _values(served, "prorrata_sector_letter") == [
        str(token) for token in prorrata_sector_letters(authority=operation)
    ]
    assert _values(served, "prorrata_sector_letter")
    for provenance in _values(served, "prorrata_provenance"):
        assert str(catalogue.require_provenance(provenance)) == provenance


def test_rental_expense_concepts_are_the_registry_vocabulary_in_its_order_each_worded_under_its_token(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    catalogue = resolve_gasto_capital_inmobiliario_catalogue(authority=operation)

    assert _values(served, "gasto_capital_inmobiliario") == [str(concept.token) for concept in catalogue.concepts]
    for token, key in served["gasto_capital_inmobiliario"]:
        assert str(catalogue.require(token)) == token
        assert key == f"application.ledger.entry_options.gasto_capital_inmobiliario.{token}"


def test_a_profile_without_stated_facts_is_offered_no_rental_row(
    served: dict[str, tuple[tuple[str, str | None], ...]],
) -> None:
    assert served["rental_lease"] == ()
    assert served["rental_property"] == ()


def test_capital_goods_kinds_and_disposals_are_the_register_vocabularies(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    catalogue = resolve_bienes_inversion_catalogue()

    assert _values(served, "capital_good_kind") == [str(kind) for kind in catalogue.kind_choices]
    assert _values(served, "capital_good_disposal") == [str(regime) for regime in catalogue.disposal_regime_choices]
    for kind in _values(served, "capital_good_kind"):
        assert str(catalogue.require_kind(kind)) == kind


def test_import_formats_are_the_installed_parsers(served: dict[str, tuple[tuple[str, str | None], ...]]) -> None:
    assert _values(served, "import_format") == [str(provider) for provider in installed_ledger_providers()]
    assert all(label is None for _, label in served["import_format"])


def test_a_format_whose_extra_is_absent_is_not_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(actions_import, "optional_extra_available", lambda extra: extra.extra != "ofx")
    without = installed_ledger_providers()
    monkeypatch.setattr(actions_import, "optional_extra_available", lambda extra: True)
    with_all = installed_ledger_providers()

    assert with_all == tuple(LedgerProviderID)
    assert without == tuple(p for p in LedgerProviderID if p not in {LedgerProviderID.OFX, LedgerProviderID.QFX})


def test_a_dated_catalogue_is_read_on_the_day_asked_and_the_undated_ones_ignore_it(
    operation: PinnedAuthorityOperation,
) -> None:
    years = sorted(operation.supported_filing_years().years)
    assert len(years) >= 2
    first, last = date(years[0], 6, 30), date(years[-1], 6, 30)

    for day in (first, last):
        projection = ledger_entry_options(_PROFILE, operation=operation, on_date=day)
        by_family = {family.family: [option.value for option in family.options] for family in projection.families}
        assert by_family["iva_category"] == [
            str(token)
            for token in resolve_iva_category_catalogue(effective_date=day, authority=operation).all_categories
        ]
        assert by_family["invoice_class"] == [
            str(token)
            for token in resolve_invoice_legal_classification_catalogue(effective_date=day).invoice_class_choices
        ]
        assert by_family["spending_category"] == [
            str(category)
            for members in resolve_spending_category_catalogue(
                effective_date=day, authority=operation
            ).family_members.values()
            for category in members
        ]
    early = ledger_entry_options(_PROFILE, operation=operation, on_date=first)
    late = ledger_entry_options(_PROFILE, operation=operation, on_date=last)
    undated = {"country", "currency", "irpf_category", "usage_ratio_category", "m210_payer_mode"}
    assert {f.family: f.options for f in early.families if f.family in undated} == {
        f.family: f.options for f in late.families if f.family in undated
    }


def test_the_request_names_a_day_or_none() -> None:
    assert LedgerEntryOptionsRequest(profile_id=_PROFILE).on_date is None
    assert LedgerEntryOptionsRequest(profile_id=_PROFILE, on_date=date(2026, 1, 31)).on_date == date(2026, 1, 31)
    with pytest.raises(ValidationError):
        LedgerEntryOptionsRequest.model_validate({"profile_id": str(_PROFILE), "on_date": "not-a-day"})


def test_country_codes_are_sorted_catalogued_and_carry_no_word(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    codes = [code for code, _ in served["country"]]

    assert codes == sorted(codes)
    assert len(codes) == len(set(codes))
    assert {"ES", "DE", "MC", "US"} <= set(codes)
    assert not {"ZZ", "XX", "es"} & set(codes)
    assert all(len(code) == 2 and code.isascii() and code.isupper() for code in codes)
    assert {key for _, key in served["country"]} == {None}
    for code in codes:
        assert stated_country_code_status(code, operation=operation) is StatedCountryCodeStatus.CATALOGUED, code
    assert stated_country_code_status("ZZ", operation=operation) is StatedCountryCodeStatus.UNASSIGNED


def test_currency_codes_are_sorted_and_carry_no_word(served: dict[str, tuple[tuple[str, str | None], ...]]) -> None:
    codes = [code for code, _ in served["currency"]]

    assert codes == sorted(codes)
    assert {"EUR", "USD", "GBP"} <= set(codes)
    assert "ZZZ" not in codes
    assert {key for _, key in served["currency"]} == {None}


def test_the_functional_currency_is_served_and_is_one_of_the_served_currencies(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    default = ledger_entry_options(_PROFILE, operation=operation).default_currency

    assert default == "EUR"
    assert default in {code for code, _ in served["currency"]}


def test_every_deduction_kind_is_served_with_a_word_key_naming_its_own_token(
    served: dict[str, tuple[tuple[str, str | None], ...]],
) -> None:
    assert served["deduction_fact_kind"]
    for kind, key in served["deduction_fact_kind"]:
        assert key == f"application.ledger.entry_options.deduction_fact_kind.{kind}"


def test_deduction_kinds_are_the_ones_a_row_may_state_in_their_registry_order(
    served: dict[str, tuple[tuple[str, str | None], ...]], operation: PinnedAuthorityOperation
) -> None:
    kinds = [kind for kind, _ in served["deduction_fact_kind"]]

    assert kinds == [
        "domestic_current",
        "domestic_investment",
        "import_current",
        "import_investment",
        "intra_eu_current",
        "intra_eu_investment",
        "reagp_compensation",
        "rectification",
    ]
    assert "investment_goods_regularisation" not in kinds
    catalogue = resolve_iva_deduction_catalogue(authority=operation)
    for kind in kinds:
        assert catalogue.require_kind(kind).value == kind


def test_payer_modes_keep_their_registry_order(served: dict[str, tuple[tuple[str, str | None], ...]]) -> None:
    assert [mode for mode, _ in served["m210_payer_mode"]] == ["single_payer", "multiple_payers_code_35"]


def _classified(code: str, mode: str) -> M210IncomeClassification:
    return M210IncomeClassification.model_validate(
        {
            "official_tipo_renta_code": code,
            "gross_income_amount": Decimal("100"),
            "applicable_rate": Decimal("0.19"),
            "payer_mode": mode,
        }
    )


def test_every_tipo_renta_offered_is_one_the_writer_accepts(
    served: dict[str, tuple[tuple[str, str | None], ...]],
) -> None:
    codes = [code for code, _ in served["m210_tipo_renta"]]

    assert "35" in codes
    for code in codes:
        mode = "multiple_payers_code_35" if code == "35" else "single_payer"
        assert _classified(code, mode).official_tipo_renta_code == code
    with pytest.raises(ValidationError):
        _classified("99", "single_payer")


@pytest.mark.parametrize("code", ["13", "19", "20", "27", "31"])
def test_a_code_the_calculation_must_fetch_is_not_offered(
    code: str, served: dict[str, tuple[tuple[str, str | None], ...]]
) -> None:
    assert code not in {offered for offered, _ in served["m210_tipo_renta"]}


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_every_word_exists_in_every_locale(locale: str, served: dict[str, tuple[tuple[str, str | None], ...]]) -> None:
    catalogue = yaml.safe_load(
        files("cadrumo").joinpath("locales", locale, "application.yml").read_text(encoding="utf-8")
    )
    missing: list[str] = []
    for options in served.values():
        for _, key in options:
            if key is None:
                continue
            node: object = catalogue
            for part in key.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if not isinstance(node, str) or not node.strip():
                missing.append(key)

    assert missing == []


class _Operands:
    def __init__(self) -> None:
        self.stored: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        self.stored.append(value)
        return "ref"


class _Events:
    async def phase(self, name: str) -> None:
        del name


def _no_profile_facts(bucket_id: str, operation: PinnedAuthorityOperation) -> None:
    del bucket_id, operation


def _context(operation: PinnedAuthorityOperation, *, definition_id: str, subject: str) -> SimpleNamespace:
    return SimpleNamespace(
        identity=OperationIdentity(operation_id="a" * 64, definition_id=definition_id, subject_ref=subject),
        events=_Events(),
        operands=_Operands(),
        authority_operation=operation,
    )


def test_the_executor_answers_for_the_active_profile(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cadrumo.application.ledger.entry_options_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    subject = profile_operation_subject(str(_PROFILE))
    request = OperationRequest[LedgerEntryOptionsRequest](
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=LedgerEntryOptionsRequest(profile_id=_PROFILE),
    )
    context = _context(operation, definition_id=request.definition_id, subject=subject)
    read: list[str] = []

    def profile_facts(bucket_id: str, pinned: PinnedAuthorityOperation) -> dict[str, str]:
        assert pinned is operation
        read.append(bucket_id)
        return {
            "renta_inmueble.0.situacion": "5",
            "renta_arrendamiento.2.inmueble": "0",
            "renta_arrendamiento.2.fecha_contrato": _ON_DATE.isoformat(),
            "renta_arrendamiento.2.fecha_inicio": _ON_DATE.isoformat(),
        }

    asyncio.run(LedgerEntryOptionsExecutor(profile_facts).execute(request, cast(OperationExecutorContext, context)))

    (stored,) = context.operands.stored
    assert isinstance(stored, LedgerEntryOptionsExecutionResult)
    assert isinstance(stored.result, LedgerEntryOptionsProjection)
    assert stored.result.profile_id == _PROFILE
    # The rental rows offered are the exact profile's own, valued by the reference a ledger row stores.
    assert read == [str(_PROFILE)]
    families = {family.family: family.options for family in stored.result.families}
    assert [option.value for option in families["rental_property"]] == ["0"]
    assert [option.value for option in families["rental_lease"]] == ["2"]
    assert all(
        option.label_words and option.label_words_language is not None and option.label_key is None
        for option in (*families["rental_property"], *families["rental_lease"])
    )


def test_the_executor_refuses_another_active_profile(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cadrumo.application.ledger.entry_options_operation.require_active_bucket_id", lambda: str(_OTHER_PROFILE)
    )
    subject = profile_operation_subject(str(_PROFILE))
    request = OperationRequest[LedgerEntryOptionsRequest](
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=LedgerEntryOptionsRequest(profile_id=_PROFILE),
    )
    context = _context(operation, definition_id=request.definition_id, subject=subject)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(
            LedgerEntryOptionsExecutor(_no_profile_facts).execute(request, cast(OperationExecutorContext, context))
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert context.operands.stored == []


def _registration(*, context_profile: UUID = _PROFILE) -> tuple[OperationRegistry, OperationAccessContext]:
    definition = build_ledger_entry_options_definition(_no_profile_facts)
    registration = build_ledger_entry_options_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, OperationAccessContext(
        profile_id=context_profile,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=None,
    )


def _access_request(*, payload_profile: UUID, subject_profile: UUID) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerEntryOptionsRequest(profile_id=payload_profile),
    )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        pytest.param(_OTHER_PROFILE, _PROFILE, _PROFILE, id="admitted-under-another-profile"),
        pytest.param(_PROFILE, _OTHER_PROFILE, _PROFILE, id="payload-names-another-profile"),
        pytest.param(_PROFILE, _PROFILE, _OTHER_PROFILE, id="subject-names-another-profile"),
    ],
)
def test_another_profile_is_refused_at_admission(
    context_profile: UUID, payload_profile: UUID, subject_profile: UUID
) -> None:
    registry, context = _registration(context_profile=context_profile)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_access_request(payload_profile=payload_profile, subject_profile=subject_profile),
            context=context,
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_admission_binds_the_exact_profile() -> None:
    registry, context = _registration()

    resolved = resolve_operation_access(
        registry=registry,
        request=_access_request(payload_profile=_PROFILE, subject_profile=_PROFILE),
        context=context,
    )

    assert resolved.request.profile_id == _PROFILE
    assert AccessAction.COMMIT not in resolved.policy.actions


def test_each_invoice_class_is_filed_under_what_it_means_to_a_form(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    served = ledger_entry_options(uuid4(), operation=authority_operation, on_date=date(2026, 4, 15))
    family = next(item for item in served.families if item.family == "invoice_class")
    # The registry's three classes: a form starts on the ordinary one, a rectificativa names
    # what it rectifies, and a simplificada may leave the tax id out.
    assert {option.value: option.group for option in family.options} == {
        "ORDINARIA": "default",
        "SIMPLIFICADA": "simplified",
        "RECTIFICATIVA": "corrective",
    }


def _accepts(check: Callable[[], None]) -> bool:
    """Whether the writer's own check lets the case through."""
    try:
        check()
    except (ClassificationRuleError, TransactionValidationError):
        return False
    return True


def test_every_classification_is_served_once_in_the_enums_order(operation: PinnedAuthorityOperation) -> None:
    served = ledger_entry_options(_PROFILE, operation=operation).classifications

    assert [item.classification for item in served] == list(BusinessClassification)


@pytest.mark.parametrize("classification", list(BusinessClassification))
def test_the_business_share_flag_is_what_the_coupling_check_enforces(
    classification: BusinessClassification, operation: PinnedAuthorityOperation
) -> None:
    served = next(
        item
        for item in ledger_entry_options(_PROFILE, operation=operation).classifications
        if item.classification is classification
    )

    takes_a_share = _accepts(lambda: validate_business_pct_coupling(classification, Decimal("0.5")))
    takes_none = _accepts(lambda: validate_business_pct_coupling(classification, None))

    assert served.takes_business_share is takes_a_share
    assert served.takes_business_share is not takes_none


@pytest.mark.parametrize("classification", list(BusinessClassification))
def test_the_rule_category_flag_is_what_a_new_rule_is_held_to(
    classification: BusinessClassification, operation: PinnedAuthorityOperation
) -> None:
    served = next(
        item
        for item in ledger_entry_options(_PROFILE, operation=operation).classifications
        if item.classification is classification
    )

    with_category = _accepts(lambda: require_new_rule_decision(classification, "office_supplies"))

    assert served.rule_may_name_category is with_category
    if classification in RULE_DECIDED_STATES:
        assert _accepts(lambda: require_new_rule_decision(classification, None))
    else:
        assert served.rule_may_name_category is False


def test_a_split_part_is_told_to_name_a_category_only_where_it_carries_business_figures(
    operation: PinnedAuthorityOperation,
) -> None:
    served = ledger_entry_options(_PROFILE, operation=operation).classifications

    asked = {item.classification for item in served if item.split_part_requires_category}

    assert asked
    assert asked <= BUSINESS_BEARING_STATES
    assert asked == {BusinessClassification.BUSINESS}


def _row_keeping_everything() -> Transaction:
    """A mixed row that holds every fact a classification write may drop."""
    row = outgoing_manual_row(
        "kept",
        amount=Decimal("100.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="compra",
        classification=BusinessClassification.BUSINESS,
    )
    return row.model_copy(
        update={
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.5"),
            "usage_ratio_id": "ratio-1",
            "category_id": "office_supplies",
            "taxable_base": Decimal("82.64"),
        },
    )


@pytest.mark.parametrize("classification", list(BusinessClassification))
def test_the_figure_flags_are_what_a_classification_write_keeps(
    classification: BusinessClassification, operation: PinnedAuthorityOperation
) -> None:
    served = next(
        item
        for item in ledger_entry_options(_PROFILE, operation=operation).classifications
        if item.classification is classification
    )

    rebuilt = command_from_patch(
        bucket_id="b" * 36,
        current=_row_keeping_everything(),
        patch=ManualLedgerTransactionPatch(business_classification=classification),
        actor="operator",
        source_command="aeat app ledger classify",
    )

    assert (rebuilt.business_pct is not None) is served.takes_business_share
    assert (rebuilt.usage_ratio_id is not None) is served.takes_usage_ratio
    assert (rebuilt.category_id is not None) is served.keeps_category
    assert (rebuilt.taxable_base is not None) is served.carries_business_figures
    assert served.carries_business_figures is (classification in BUSINESS_BEARING_STATES)


def test_export_formats_are_the_serializations_an_export_writes(
    served: dict[str, tuple[tuple[str, str | None], ...]],
) -> None:
    assert _values(served, "export_format") == [str(item) for item in ExportSerializationFormat]
    assert all(label is None for _, label in served["export_format"])
