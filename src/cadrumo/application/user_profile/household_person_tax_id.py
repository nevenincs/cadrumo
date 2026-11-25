"""The tax identifier a household member row may state.

An ascendant or a descendant is a person, so the identifier must be a NIF or a NIE
whose control letter holds. An entity identifier is refused with the same error as a
malformed one, so a refusal never says which part of the typed value was wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.identity.documents import IdentityDocument, IdentityError, validate_identity
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def canonical_person_tax_id(raw: str, *, operation: PinnedAuthorityOperation) -> str:
    """Return the canonical NIF or NIE of a person.

    Raises:
        IdentityError: The identifier is malformed, fails its control letter or names an entity.
    """
    tax_id_format = runtime_tax_id_format(authority=operation)
    canonical = validate_spanish_tax_id(raw, tax_id_format)
    if validate_identity(canonical, tax_id_format) is IdentityDocument.CIF:
        raise IdentityError("a person's tax identifier cannot be an entity identifier")
    return canonical
