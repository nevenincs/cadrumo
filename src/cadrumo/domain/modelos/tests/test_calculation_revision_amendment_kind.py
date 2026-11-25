"""The amendment identity carries the one filing declaration vocabulary."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ..calculation_revision_amendment import (
    AMENDMENT_DECLARATION_KINDS,
    CalculationRevisionAmendmentIdentity,
    M303RectificativaMotive,
    filing_declaration_kind_for_amendment,
)
from ..errors import ModeloValidationError
from ..filing_record import FilingDeclarationKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AMENDED = "a" * 64


def test_the_amendment_kinds_are_every_declaration_kind_but_the_original() -> None:
    assert AMENDMENT_DECLARATION_KINDS == (
        FilingDeclarationKind.COMPLEMENTARIA,
        FilingDeclarationKind.SUSTITUTIVA,
        FilingDeclarationKind.RECTIFICATIVA,
    )


@pytest.mark.parametrize("kind", AMENDMENT_DECLARATION_KINDS)
def test_an_amendment_is_filed_as_its_own_declaration_kind(kind: FilingDeclarationKind) -> None:
    identity = CalculationRevisionAmendmentIdentity(
        kind=kind, amends_filing_record_id=_AMENDED, m303_rectificativa_motive=None
    )

    assert filing_declaration_kind_for_amendment(identity) is kind


def test_a_revision_without_an_amendment_identity_is_the_original() -> None:
    assert filing_declaration_kind_for_amendment(None) is FilingDeclarationKind.ORIGINAL


def test_an_amendment_identity_refuses_the_original_kind() -> None:
    with pytest.raises(ModeloValidationError, match="original"):
        CalculationRevisionAmendmentIdentity(
            kind=FilingDeclarationKind.ORIGINAL, amends_filing_record_id=_AMENDED, m303_rectificativa_motive=None
        )


@pytest.mark.parametrize("stored_kind", ["complementaria", "sustitutiva", "rectificativa"])
def test_an_identity_stored_under_the_retired_kind_enum_still_loads(stored_kind: str) -> None:
    stored = json.dumps({"kind": stored_kind, "amends_filing_record_id": _AMENDED, "m303_rectificativa_motive": None})

    identity = CalculationRevisionAmendmentIdentity.model_validate_json(stored)

    assert identity.kind is FilingDeclarationKind(stored_kind)
    assert json.loads(identity.model_dump_json())["kind"] == stored_kind
    assert filing_declaration_kind_for_amendment(identity) is FilingDeclarationKind(stored_kind)


def test_a_stored_motive_still_requires_the_rectificativa_kind() -> None:
    stored = json.dumps(
        {
            "kind": "rectificativa",
            "amends_filing_record_id": _AMENDED,
            "m303_rectificativa_motive": "rectificaciones",
        }
    )

    identity = CalculationRevisionAmendmentIdentity.model_validate_json(stored)

    assert identity.m303_rectificativa_motive is M303RectificativaMotive.RECTIFICACIONES
    with pytest.raises(ModeloValidationError, match="rectificativa"):
        CalculationRevisionAmendmentIdentity.model_validate_json(stored.replace("rectificativa", "complementaria", 1))


def test_a_stored_identity_never_reads_as_the_original() -> None:
    stored = json.dumps({"kind": "original", "amends_filing_record_id": _AMENDED, "m303_rectificativa_motive": None})

    with pytest.raises(ModeloValidationError, match="original"):
        CalculationRevisionAmendmentIdentity.model_validate_json(stored)


def test_a_stored_identity_of_an_unknown_kind_is_refused() -> None:
    stored = json.dumps({"kind": "unknown", "amends_filing_record_id": _AMENDED, "m303_rectificativa_motive": None})

    with pytest.raises(ValidationError):
        CalculationRevisionAmendmentIdentity.model_validate_json(stored)
