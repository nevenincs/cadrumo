"""What a ledger entry form is offered, read through each list's real owner."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal
from importlib.resources import files
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.iva_deduction_catalogue import resolve_iva_deduction_catalogue
from ....domain.iva.establishment import StatedCountryCodeStatus, stated_country_code_status
from ....domain.transactions.m210_income_classification import M210IncomeClassification
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
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
    assert set(served) == {"country", "currency", "deduction_fact_kind", "m210_payer_mode", "m210_tipo_renta"}


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
def test_every_word_exists_in_every_locale(
    locale: str, served: dict[str, tuple[tuple[str, str | None], ...]]
) -> None:
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

    asyncio.run(LedgerEntryOptionsExecutor().execute(request, cast(OperationExecutorContext, context)))

    (stored,) = context.operands.stored
    assert isinstance(stored, LedgerEntryOptionsExecutionResult)
    assert isinstance(stored.result, LedgerEntryOptionsProjection)
    assert stored.result.profile_id == _PROFILE


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
        asyncio.run(LedgerEntryOptionsExecutor().execute(request, cast(OperationExecutorContext, context)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert context.operands.stored == []


def _registration(*, context_profile: UUID = _PROFILE) -> tuple[OperationRegistry, OperationAccessContext]:
    definition = build_ledger_entry_options_definition()
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
