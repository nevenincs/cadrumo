"""A declared party kind that contradicts a Spanish identifier's form is surfaced, never resolved.

The identifier's form is read by the canonical NIF kernel from the pinned
identifier-format fact. Its letter rules rest on the Orden EHA/451/2008 (arts. 2
to 4): the NIF of a natural person is eight digits and a check letter, with the
initial letters K, L and M for the special cases of Spaniards without a DNI; the
NIE of a foreigner starts with X, Y or Z; and the NIF of an entity starts with
the organisation letter of its legal form (A, B, C and so on). The bundled
corpus sources ``aeat-nif-personas-fisicas`` and ``aeat-nif-personas-juridicas``
carry that text, and the registry fact cites them.

All identifiers below are synthetic. The name is stored in every case: the
finding reports a disagreement and neither blocks nor rewrites the statement.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ...application.ledger.counterparty_operation import (
    FILING_NAME_KIND_CONTRADICTS_FORM_FINDING,
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
    filing_name_kind_findings,
)
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.filing.declared_party_name import DeclaredPartyKind
from ..cli.ledger_counterparty_filing_name_commands import (
    filing_name_finding_notices,
    filing_name_finding_payloads,
)
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "37373737-3737-4737-8737-37373737373c"

_DNI = "12345678Z"
_NIE = "X0001502F"
_SPECIAL_NATURAL = ("K1234567L", "L1234567L", "M1234567L")
_ENTITY = "B00015016"
_ENTITY_NAME = "Suministros Ficticios del Norte, S.L."


def _statement(
    tax_identifier: str, kind: DeclaredPartyKind, *, country_code: str | None = None
) -> LedgerCounterpartyRequest:
    natural = kind is DeclaredPartyKind.NATURAL_PERSON
    return LedgerCounterpartyRequest(
        profile_id=UUID(_BUCKET_ID),
        action="filing_name",
        tax_identifier=tax_identifier,
        country_code=country_code,
        asserted_by="operator",
        party_kind=kind.value,
        primer_apellido="Ejemplo" if natural else None,
        segundo_apellido="Prueba" if natural else None,
        nombre="Ana" if natural else None,
        razon_social=None if natural else _ENTITY_NAME,
    )


_Runtime = tuple[Any, Any, UUID]


def _run(runtime: _Runtime, request: LedgerCounterpartyRequest) -> LedgerCounterpartyResult:
    """Submit the statement through the registered operation, as every surface does."""
    driver, registry, profile_id = runtime
    submitted, observed = asyncio.run(
        driver.run(
            definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=request.model_copy(update={"profile_id": profile_id}),
        )
    )
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    return conformance.resolve_result_projection(
        driver,
        registry,
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        operation_id=submitted.receipt.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=LedgerCounterpartyResult,
    )


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[_Runtime]:
    """A registered-operation runtime over a real, empty profile."""
    with conformance.conformance_operation_runtime(
        tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
    ) as opened:
        yield opened


@pytest.mark.parametrize("identifier", [_DNI, _NIE, *_SPECIAL_NATURAL])
def test_an_entity_declared_for_a_natural_persons_form_is_a_finding_and_the_name_is_stored(
    runtime: _Runtime, identifier: str
) -> None:
    result = _run(runtime, _statement(identifier, DeclaredPartyKind.ENTITY))
    assert [(f.code, f.declared_kind, f.observed_form) for f in result.findings] == [
        (FILING_NAME_KIND_CONTRADICTS_FORM_FINDING, "entity", "natural_person")
    ]
    assert result.filing_name is not None
    assert (result.filing_name.party_kind, result.filing_name.razon_social) == ("entity", _ENTITY_NAME)
    assert result.recorded is True


def test_a_natural_person_declared_for_an_entitys_form_is_a_finding_and_the_name_is_stored(
    runtime: _Runtime,
) -> None:
    result = _run(runtime, _statement(_ENTITY, DeclaredPartyKind.NATURAL_PERSON))
    assert [(f.code, f.declared_kind, f.observed_form) for f in result.findings] == [
        (FILING_NAME_KIND_CONTRADICTS_FORM_FINDING, "natural_person", "entity")
    ]
    assert result.filing_name is not None
    assert (result.filing_name.party_kind, result.filing_name.nombre) == ("natural_person", "Ana")


@pytest.mark.parametrize(
    ("identifier", "kind"),
    [
        (_DNI, DeclaredPartyKind.NATURAL_PERSON),
        (_NIE, DeclaredPartyKind.NATURAL_PERSON),
        (_SPECIAL_NATURAL[0], DeclaredPartyKind.NATURAL_PERSON),
        (_ENTITY, DeclaredPartyKind.ENTITY),
    ],
)
def test_agreement_raises_no_finding_and_stores_the_name(
    runtime: _Runtime, identifier: str, kind: DeclaredPartyKind
) -> None:
    result = _run(runtime, _statement(identifier, kind))
    assert result.findings == ()
    assert result.filing_name is not None
    assert result.filing_name.party_kind == kind.value


@pytest.mark.parametrize(
    ("identifier", "country_code"),
    [("DE123456789", "DE"), ("DE123456789", None), ("FR12345678901", "FR")],
)
def test_a_foreign_or_unclassifiable_identifier_raises_no_finding(
    runtime: _Runtime, identifier: str, country_code: str | None
) -> None:
    result = _run(runtime, _statement(identifier, DeclaredPartyKind.ENTITY, country_code=country_code))
    assert result.findings == ()
    assert result.filing_name is not None
    assert result.filing_name.party_kind == "entity"


def test_the_view_repeats_the_finding_for_the_stored_name(runtime: _Runtime) -> None:
    _run(runtime, _statement(_DNI, DeclaredPartyKind.ENTITY))
    viewed = _run(runtime, LedgerCounterpartyRequest(profile_id=UUID(_BUCKET_ID), action="view", tax_identifier=_DNI))
    assert [(f.declared_kind, f.observed_form) for f in viewed.findings] == [("entity", "natural_person")]
    unnamed = _run(
        runtime, LedgerCounterpartyRequest(profile_id=UUID(_BUCKET_ID), action="view", tax_identifier=_ENTITY)
    )
    assert unnamed.findings == ()


def test_the_finding_carries_kinds_only() -> None:
    with bundled_indexed_authority().operation() as operation:
        findings = filing_name_kind_findings(
            tax_identifier=_DNI, country_code="ES", declared_kind="entity", operation=operation
        )
    dumped = " ".join(str(value) for finding in findings for value in finding.model_dump().values())
    assert _DNI not in dumped
    assert set(findings[0].model_dump()) == {"code", "declared_kind", "observed_form", "words", "words_language"}


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_finding_serves_its_sentence_in_the_workers_language(language: OutputLanguage) -> None:
    with (
        override_settings(cadrumo_output_language=language.value),
        bundled_indexed_authority().operation() as operation,
    ):
        (finding,) = filing_name_kind_findings(
            tax_identifier=_DNI, country_code="ES", declared_kind="entity", operation=operation
        )
        entity = tr("application.ledger.counterparty.party_kinds.entity", locale=language.value)
        natural = tr("application.ledger.counterparty.party_kinds.natural_person", locale=language.value)

    assert finding.words_language is language
    assert finding.words is not None
    assert entity in finding.words
    assert natural in finding.words
    assert not re.search(r"\bapplication\.|\{|\}|%\(", finding.words)
    assert _DNI not in finding.words


def test_the_cli_renders_the_finding_in_served_words_without_the_party() -> None:
    with bundled_indexed_authority().operation() as operation:
        findings = filing_name_kind_findings(
            tax_identifier=_DNI, country_code=None, declared_kind="entity", operation=operation
        )
    (payload,) = filing_name_finding_payloads(findings)
    assert (payload.code, payload.declared_kind, payload.observed_form) == (
        FILING_NAME_KIND_CONTRADICTS_FORM_FINDING,
        DeclaredPartyKind.ENTITY,
        DeclaredPartyKind.NATURAL_PERSON,
    )
    (notice,) = filing_name_finding_notices(findings)
    assert notice.code == f"ledger.counterparty.{FILING_NAME_KIND_CONTRADICTS_FORM_FINDING}"
    assert notice.severity.value == "warning"
    assert "{" not in notice.message
    assert "cli.ledger" not in notice.message
    assert _DNI not in notice.message
    assert _DNI not in str(notice.context)


@pytest.mark.parametrize("identifier", ["12345678A", "", "not an identifier", "DE123456789"])
def test_a_form_the_kernel_does_not_accept_has_nothing_to_contradict(identifier: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        assert (
            filing_name_kind_findings(
                tax_identifier=identifier, country_code=None, declared_kind="entity", operation=operation
            )
            == ()
        )
