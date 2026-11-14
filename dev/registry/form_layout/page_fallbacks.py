"""Build numbered-box and operator-input pages for positions without a form section."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormBlockDefinition,
    FormFieldBlock,
    FormPageDefinition,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .generation_constants import GENERAL_SECTION
from .generation_models import Build
from .heading_keys import form_heading_key, unique, unnamed_section_form_heading_key
from .official_text import node_slug
from .position_anchoring import casilla_box


def _restates_another_casillas_box(build: Build, casilla: CasillaDefinition) -> bool:
    """Say whether a casilla carries a number whose box another casilla holds as its id.

    The dictionary prints one number on several rows, and the registry keeps a
    casilla per concept; the form has the one box, owned by the casilla whose id
    it is. The other carries the value in the export and has no box of its own.
    """
    return (
        casilla.segmento is None
        and casilla.id != casilla.number
        and any(other.segmento is None and other.id == casilla.number for other in build.revision.casillas)
    )


def numbered_casillas(build: Build, primary: Mapping[str, int]) -> list[str]:
    """Return casillas with a numeric box and no official position, in box order."""
    remaining = [
        casilla
        for casilla in build.revision.casillas
        if casilla.id not in primary
        and casilla.id not in build.ambiguous
        and casilla_box(casilla.number, casilla.form_number) is not None
        and not _restates_another_casillas_box(build, casilla)
    ]
    remaining.sort(key=lambda casilla: (int(str(casilla_box(casilla.number, casilla.form_number))), casilla.id))
    return [casilla.id for casilla in remaining]


def numbered_page(build: Build, page_id: str, casilla_ids: Sequence[str]) -> FormPageDefinition:
    """Place casillas known only by their box number, grouped by their registry section's first token."""
    by_id = {casilla.id: casilla for casilla in build.revision.casillas}
    groups: dict[str, list[str]] = {}
    for casilla_id in casilla_ids:
        section = by_id[casilla_id].section
        groups.setdefault(node_slug(section[0]) if section else GENERAL_SECTION, []).append(casilla_id)
    sections = tuple(
        FormSectionDefinition(
            id=section_id,
            heading_key=(
                unnamed_section_form_heading_key(build.modelo_id, page_id, section_id)
                if section_id == GENERAL_SECTION
                else form_heading_key(build.modelo_id, "section", section_id)
            ),
            blocks=tuple(
                FormFieldBlock(id=f"field-{index + 1}", casilla_id=casilla_id)
                for index, casilla_id in enumerate(members)
            ),
        )
        for section_id, members in groups.items()
    )
    return FormPageDefinition(
        id=page_id, heading_key=form_heading_key(build.modelo_id, "page", page_id), sections=sections
    )


def inputs_page(
    build: Build,
    page_id: str,
    manual_bindings: Mapping[str, bool],
    placed: set[str],
) -> FormPageDefinition | None:
    """Declare manual-input bindings no casilla owns and no official position holds."""
    scalar = tuple(
        sorted(binding for binding, row_set in manual_bindings.items() if not row_set and binding not in placed)
    )
    row_sets = sorted(binding for binding, row_set in manual_bindings.items() if row_set)
    blocks: list[FormBlockDefinition] = []
    used: set[str] = {"binding-inputs"}
    if scalar:
        blocks.append(FormBindingInputsBlock(id="binding-inputs", binding_ids=scalar))
    blocks.extend(
        FormRepeatingGroupBlock(
            id=unique(node_slug(binding), used),
            row_source=FormRepeatingRowSource.ROW_SET_BINDING,
            binding_id=binding,
        )
        for binding in row_sets
    )
    if not blocks:
        return None
    section = FormSectionDefinition(
        id="inputs", heading_key=form_heading_key(build.modelo_id, "section", "inputs"), blocks=tuple(blocks)
    )
    return FormPageDefinition(
        id=page_id, heading_key=form_heading_key(build.modelo_id, "page", page_id), sections=(section,)
    )
