"""Select the boxes of a work form whose value is assumed and not yet confirmed by the filer.

The form classifies a box the calculation holds and nobody entered as
:attr:`ModeloFormOrigin.DEFAULT_TO_CONFIRM` (see ``held_value_origin``). This is
the one place that turns that classification into a list of boxes. The form's
export hold and the registered verify, export and local-filing gates all read
it, so what the form withholds on and what the backend refuses cannot differ.
"""

from __future__ import annotations

from typing import Protocol

from .work_form_declaration_facts import ModeloFormFiling
from .work_form_facts import ModeloFormFieldFactsLike, ModeloFormFieldSource
from .work_form_field_vocabulary import ModeloFormAddressV1, ModeloFormOrigin
from .work_form_next_step import applicable_fields


class _AssumedFieldSource[F: ModeloFormFieldFactsLike](ModeloFormFieldSource[F], Protocol):
    """A form's boxes in reading order, with whether the declaration is recorded as filed."""

    @property
    def filing(self) -> ModeloFormFiling | None:
        """The recorded filing; ``None`` when the declaration is not recorded as filed."""
        ...


def assumed_fields[F: ModeloFormFieldFactsLike](form: _AssumedFieldSource[F]) -> tuple[F, ...]:
    """The assumed values the filer is asked about: one field per address, on pages that apply.

    A declaration recorded as filed asks nothing more of the filer, so it has none.
    """
    if form.filing is not None:
        return ()
    seen: set[str] = set()
    assumed: list[F] = []
    for field in applicable_fields(form):
        key = _address_key(field.address)
        if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM and key not in seen:
            seen.add(key)
            assumed.append(field)
    return tuple(assumed)


def _address_key(address: ModeloFormAddressV1) -> str:
    return f"{address.kind}:{getattr(address, 'casilla_id', None) or getattr(address, 'binding_id', '')}"


__all__ = ["assumed_fields"]
