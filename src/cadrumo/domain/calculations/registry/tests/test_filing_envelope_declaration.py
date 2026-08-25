"""The variable-envelope declaration admits every official spelling and no other.

One declaration type carries every modelo whose design declares a ``Total:
Variable`` envelope, so its validators are the only thing standing between "this
design prints the shared grammar differently" and "this design violates it".
Each case below is a real spelling from the bundled corpus or a real way to get
the grammar wrong; none is hypothetical.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..schema_exports import (
    FilingEnvelopeCloserDerivation,
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
    FilingEnvelopeTotalDerivation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Every refusal below arrives as a pydantic ``ValidationError``: the model's own
#: ``model_validator`` raises :class:`RegistryValidationError`, which is a
#: ``ValueError``, and pydantic wraps it. Matching on the message rather than the
#: type keeps each assertion pinned to the specific contradiction it names.

_R = FilingEnvelopePrefixRole

#: Modelo 303's thirteen-row spelling, with its exact official widths.
_THIRTEEN_ROW: tuple[tuple[FilingEnvelopePrefixRole, int], ...] = (
    (_R.OPENING_TAG, 2),
    (_R.MODELO, 3),
    (_R.DISCRIMINANT, 1),
    (_R.FILING_YEAR, 4),
    (_R.PERIOD, 2),
    (_R.RECORD_TYPE, 5),
    (_R.AUX_OPENING_TAG, 5),
    (_R.PRE_PROGRAM_FILLER, 70),
    (_R.PROGRAM_IDENTIFIER, 4),
    (_R.BETWEEN_IDENTITIES_FILLER, 4),
    (_R.DEVELOPER_TAX_ID, 9),
    (_R.POST_DEVELOPER_FILLER, 213),
    (_R.AUX_CLOSING_TAG, 6),
)

#: Modelo 200's eight-row spelling: the same grammar, opening tag fused.
_EIGHT_ROW: tuple[tuple[FilingEnvelopePrefixRole, int], ...] = (
    (_R.COMPOSED_OPENING_TAG, 17),
    *_THIRTEEN_ROW[6:],
)


def _declaration(
    prefix: tuple[tuple[FilingEnvelopePrefixRole, int], ...],
    *,
    prefix_extent: int = 328,
) -> FilingEnvelopeDefinition:
    return FilingEnvelopeDefinition(
        source_ref="aeat-dr-303-2025",
        source_sha256="a" * 64,
        record_identity="DP30300",
        prefix_extent=prefix_extent,
        prefix_fields=tuple(FilingEnvelopePrefixFieldDeclaration(role=role, length=length) for role, length in prefix),
        body_record_ids=("body-a", "body-b"),
        product_identity_requirement="aeat-product-software-identity-v1",
        closer_derivation=FilingEnvelopeCloserDerivation.RELATIVE_CLOSER_V1,
        total_derivation=FilingEnvelopeTotalDerivation.EMITTED_BYTE_TOTAL_V1,
    )


@pytest.mark.parametrize(
    ("spelling", "prefix"),
    [("thirteen-row", _THIRTEEN_ROW), ("eight-row-composed", _EIGHT_ROW)],
)
def test_both_official_prefix_spellings_are_admitted(
    spelling: str,
    prefix: tuple[tuple[FilingEnvelopePrefixRole, int], ...],
) -> None:
    """The same 328-byte grammar, printed two ways, yields two valid declarations."""
    declaration = _declaration(prefix)

    assert declaration.prefix_extent == 328
    assert sum(field.length for field in declaration.prefix_fields) == 328
    assert len(declaration.prefix_fields) == len(prefix), spelling


def test_a_declaration_carrying_both_opening_tag_spellings_refuses() -> None:
    """The composed tag is an ALTERNATIVE to its six components, never an addition."""
    with pytest.raises(ValidationError, match="two spellings are exclusive"):
        _declaration(((_R.COMPOSED_OPENING_TAG, 17), *_THIRTEEN_ROW), prefix_extent=345)


def test_a_declaration_omitting_part_of_the_opening_tag_refuses() -> None:
    """Half the components is neither spelling, and would emit a truncated tag."""
    with pytest.raises(ValidationError, match="either the composed opening tag or every"):
        _declaration(((_R.OPENING_TAG, 2), (_R.MODELO, 3), *_THIRTEEN_ROW[6:]), prefix_extent=313)


def test_a_reordered_prefix_refuses() -> None:
    """Role order is the official source order; a permutation is a different record."""
    reordered = (_THIRTEEN_ROW[1], _THIRTEEN_ROW[0], *_THIRTEEN_ROW[2:])

    with pytest.raises(ValidationError, match="canonical source order"):
        _declaration(reordered)


def test_a_repeated_role_refuses() -> None:
    """A role names one slot; repeating it makes the declaration unreadable."""
    with pytest.raises(ValidationError, match="repeats a role"):
        _declaration((*_THIRTEEN_ROW, (_R.AUX_CLOSING_TAG, 6)), prefix_extent=334)


def test_a_prefix_extent_disagreeing_with_its_own_fields_refuses() -> None:
    """The extent is the sum it claims to be, or the renderer emits the wrong width."""
    with pytest.raises(ValidationError, match="prefix fields sum to"):
        _declaration(_THIRTEEN_ROW, prefix_extent=329)


def test_duplicate_body_records_refuse() -> None:
    """Body families are an ordered set; a repeat makes occurrence order ambiguous."""
    with pytest.raises(ValidationError, match="unique and ordered"):
        FilingEnvelopeDefinition(
            source_ref="aeat-dr-303-2025",
            source_sha256="a" * 64,
            record_identity="DP30300",
            prefix_extent=328,
            prefix_fields=tuple(
                FilingEnvelopePrefixFieldDeclaration(role=role, length=length) for role, length in _THIRTEEN_ROW
            ),
            body_record_ids=("body-a", "body-a"),
            product_identity_requirement="aeat-product-software-identity-v1",
            closer_derivation=FilingEnvelopeCloserDerivation.RELATIVE_CLOSER_V1,
            total_derivation=FilingEnvelopeTotalDerivation.EMITTED_BYTE_TOTAL_V1,
        )


def test_the_declaration_carries_no_modelo_of_its_own() -> None:
    """The modelo is read from the selected snapshot, never spelled twice.

    A second home for it could disagree with the authority that selected the
    layout, and the closer is derived from the modelo -- so a drifted copy here
    would silently address another modelo's declaration.
    """
    assert "modelo" not in FilingEnvelopeDefinition.model_fields
