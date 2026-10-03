"""M604/M714 language is a filed casilla in the exact source-shaped prefix."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.export_envelope import render_declared_prefix
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema_exports import (
    FilingEnvelopePrefixFieldDeclaration as Field,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    FilingEnvelopePrefixRole as Role,
)
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_COMMON = (
    (Role.AUX_OPENING_TAG, 5),
    (Role.PRE_PROGRAM_FILLER, 30),
    (Role.LANGUAGE, 1),
    (Role.BETWEEN_LANGUAGE_PROGRAM_FILLER, 39),
    (Role.PROGRAM_IDENTIFIER, 4),
    (Role.BETWEEN_IDENTITIES_FILLER, 4),
    (Role.DEVELOPER_TAX_ID, 9),
    (Role.POST_DEVELOPER_FILLER, 213),
    (Role.AUX_CLOSING_TAG, 6),
)


def _identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C604",
        developer_tax_id="Y0000001S",
        evidence=(AeatProductSoftwareEvidence(reference="aeat-software-registration:c604", digest="a" * 64),),
    )


@pytest.mark.parametrize(
    "modelo,opening",
    (
        (
            "604",
            (
                (Role.OPENING_TAG, 2),
                (Role.MODELO, 3),
                (Role.DISCRIMINANT, 1),
                (Role.FILING_YEAR, 4),
                (Role.PERIOD, 2),
                (Role.RECORD_TYPE, 5),
            ),
        ),
        ("714", ((Role.COMPOSED_OPENING_TAG, 17),)),
    ),
)
def test_exact_language_prefix_from_approved_casilla(
    modelo: str, opening: tuple[tuple[Role, int], ...], authority_operation: PinnedAuthorityOperation
) -> None:
    fields = tuple(
        Field(role=role, length=length, casilla_id="decl.idioma" if role is Role.LANGUAGE else None)
        for role, length in (*opening, *_COMMON)
    )
    with validating_governed_facts(authority_operation):
        identity = _identity()
    for language in ("E", "C", "G", "V"):
        rendered = render_declared_prefix(
            fields,
            prefix_extent=328,
            modelo=Modelo(modelo),
            period=Period.from_year_and_code(2025, "0A"),
            product_software_identity=identity,
            casilla_values={"decl.idioma": language},
        )
        assert len(rendered) == 328
        assert rendered[:17] == f"<T{modelo}020250A0000>".encode("ascii")
        assert rendered[52:53] == language.encode("ascii")
        assert rendered[22:52] == b" " * 30
        assert rendered[53:92] == b" " * 39
        assert rendered[96:100] == b" " * 4
        assert rendered[109:322] == b" " * 213
    for value in (None, "", "X", "e", "EC"):
        with pytest.raises(FilingExportValidationError, match="language"):
            render_declared_prefix(
                fields,
                prefix_extent=328,
                modelo=Modelo(modelo),
                period=Period.from_year_and_code(2025, "0A"),
                product_software_identity=identity,
                casilla_values={} if value is None else {"decl.idioma": value},
            )


def test_language_casilla_cannot_be_relabelled_or_put_on_filler() -> None:
    with pytest.raises(ValueError, match=r"exact decl\.idioma"):
        Field(role=Role.LANGUAGE, length=1, casilla_id="other")
    with pytest.raises(ValueError, match="only the language"):
        Field(role=Role.PRE_PROGRAM_FILLER, length=30, casilla_id="decl.idioma")
