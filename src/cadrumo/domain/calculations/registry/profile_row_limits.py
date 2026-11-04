"""The form and layout group that own the repeat limit of a stored profile row object.

A profile stores a household as ``{object_path}.{n}.{leaf}`` facts. Revisions read such
an object through repeating profile bindings, and a form layout opens one repeating
group over them, bounded by the repeat limit the design declares. The registry names the
one form and group that own that limit for each object, so a reader asks that layout
instead of scanning every form, and the registry build checks that the named group reads
the object and declares the limit;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from .errors import RegistryValidationError
from .form_codes import resolve_form_codes
from .profile_bindings import ProfileProvider
from .schema_form_layouts import FormLayoutDefinition, FormRepeatingGroupBlock

if TYPE_CHECKING:
    from .governed_fact_scope import GovernedFactSource
    from .ids import BindingId
    from .schema import ModeloRevision

_OWNERS_FACT: Final = "household-row-limit-owners"
_FORM_PREFIX: Final = "form"
_GROUP_PREFIX: Final = "group"


@dataclass(frozen=True, slots=True)
class RowLimitOwner:
    """The form and the repeating group of its layout that bound one profile row object."""

    form: str
    group_id: str


def row_limit_owners(*, authority: GovernedFactSource | None = None) -> Mapping[str, RowLimitOwner]:
    """Return the owner of the repeat limit of each stored profile row object, keyed by object path."""
    codes = resolve_form_codes(_OWNERS_FACT, authority=authority)
    forms = codes.under(_FORM_PREFIX)
    groups = codes.under(_GROUP_PREFIX)
    if set(forms) != set(groups):
        raise RegistryValidationError(f"form-code fact {_OWNERS_FACT!r} must name a form and a group for each object")
    return MappingProxyType(
        {path: RowLimitOwner(form=forms[path], group_id=groups[path]) for path in sorted(forms)},
    )


def row_reading_binding_ids(revision: ModeloRevision, object_path: str) -> frozenset[BindingId]:
    """Return the bindings of ``revision`` that read the rows stored under ``object_path``.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return frozenset(
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, ProfileProvider)
        and binding.provider.rows is not None
        and binding.provider.rows.object_path == object_path
    )


def repeating_group(layout: FormLayoutDefinition, group_id: str) -> FormRepeatingGroupBlock | None:
    """Return the repeating group of ``layout`` with the id ``group_id``, or ``None`` when it declares none."""
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, FormRepeatingGroupBlock) and block.id == group_id:
                    return block
    return None


__all__ = [
    "RowLimitOwner",
    "repeating_group",
    "row_limit_owners",
    "row_reading_binding_ids",
]
