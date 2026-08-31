"""Art. 82 LIRPF unidad-familiar validator for the interactive setup flow.

Art. 82.1 LIRPF defines the two unidad-familiar modalities eligible for
tributación conjunta (joint taxation):

- Modalidad 1ª (Art. 82.1.1ª): the married couple not legally separated,
  together with their minor or judicially-incapacitated children if any.
  Children are optional — a childless married couple may still opt for
  conjunta as a couple.
- Modalidad 2ª (Art. 82.1.2ª): in cases of legal separation, or where no
  marriage bond exists, the single parent and all the cohabiting children who
  meet the modalidad-1ª requirements — the monoparental unit. This modality
  requires qualifying children: no unidad familiar forms without them, and the
  absence of a marriage bond is registration-agnostic (a de-facto couple,
  registered or not, has no marriage bond).

The single flow validator this module registers enforces the modalidad-2ª
children requirement at ``familia`` section exit. A joint declaration whose
family situation is a non-married modality (:meth:`SituacionFamiliar.monoparental_required`)
and which declares no minor children in the unit cannot form a valid unidad
familiar, so it fails and blocks forward navigation with a typed verdict. A
married declaration (modalidad 1ª) and a monoparental declaration that does
carry children both pass. The verdict carries a catalogue key and redacted
context only — the raw answers never enter the diagnostic.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.renta_declaracion_type import RentaDeclaracionType
from ...domain.contribuyente.renta_codes import SituacionFamiliar
from ..flows.definition import FlowDefinition, FlowSection
from ..flows.validators import ValidationVerdict, register_cross_field_validator

SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID = "setup-familia-conjunta-unidad-familiar"
"""Registered id of the familia section-exit Art. 82.1.2ª validator."""

_FAMILIA_SECTION_ID = "familia"

# Setup-flow page ids carrying the three answers the Art. 82.1.2ª rule reads.
# These page ids are the same stable catalogue tokens the visibility
# conditions already key on (e.g. the joint-declaration gate on
# ``taxation-type``); the substrate hands flow validators the answer map keyed
# by page id.
_TAXATION_TYPE_PAGE = "taxation-type"
_SITUACION_FAMILIAR_PAGE = "situacion-familiar"
_MINOR_CHILDREN_PAGE = "family-minor-children-in-unit"

_MONOPARENTAL_REQUIRES_HIJOS_KEY = "wizard.setup.verifier.monoparental_requires_hijos_warning"
_MONOPARENTAL_CHECK = "monoparental_requires_hijos"

# Code-identifier field names surfaced in the redacted verdict context — never
# operator prose, never the raw answer.
_MONOPARENTAL_FIELDS = ("taxation_type", "situacion_familiar", "family_minor_children_in_unit")

_TRUE_TOKENS = frozenset({"true", "yes", "1", "y"})


def _parse_situacion(token: str) -> SituacionFamiliar | None:
    try:
        return SituacionFamiliar(token)
    except ValueError:
        return None


def validate_unidad_familiar_conjunta(answers: Mapping[str, str]) -> tuple[ValidationVerdict, ...]:
    """Enforce the Art. 82.1.2ª monoparental children requirement.

    A joint declaration (``taxation-type`` == JOINT) whose ``situacion-familiar``
    is a non-married modality forms a valid unidad familiar only as a
    monoparental unit, which Art. 82.1.2ª conditions on qualifying children.
    When no minor children are declared in the unit the verdict fails; a
    married (modalidad 1ª) or a child-bearing monoparental declaration passes.

    ``family-minor-children-in-unit`` is the sole qualifying-children proxy the
    setup flow models. Art. 82.1.1ª(b) also admits adult judicially
    incapacitated children under prorogated patria potestad into the unit, but
    the flow collects no field for that case and the registry's conjunta
    reduction keys on the same minor-children signal, so the hard refusal is
    exact within the declared data model. Modelling the incapacitated-adult
    axis later requires widening this predicate and the registry signal
    together, not relaxing this gate alone.
    """
    if answers.get(_TAXATION_TYPE_PAGE, "") != RentaDeclaracionType.JOINT.value:
        return (ValidationVerdict.passed(),)
    situacion = _parse_situacion(answers.get(_SITUACION_FAMILIAR_PAGE, ""))
    if situacion is None or not situacion.monoparental_required():
        return (ValidationVerdict.passed(),)
    if answers.get(_MINOR_CHILDREN_PAGE, "").strip().lower() in _TRUE_TOKENS:
        return (ValidationVerdict.passed(),)
    return (
        ValidationVerdict.failed(
            _MONOPARENTAL_REQUIRES_HIJOS_KEY,
            check=_MONOPARENTAL_CHECK,
            fields=list(_MONOPARENTAL_FIELDS),
        ),
    )


register_cross_field_validator(SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID, validate_unidad_familiar_conjunta)


def attach_setup_legal_validators(definition: FlowDefinition) -> FlowDefinition:
    """Return ``definition`` with the familia section carrying the Art. 82 exit validator.

    The setup flow projects from the one-shot catalogue (which declares no
    validator ids), so this decorator names the registered validator on the
    ``familia`` :class:`FlowSection`'s ``exit_validator_ids`` — mirroring how
    :func:`attach_format_hints` decorates the projected definition. Idempotent:
    a definition already carrying the id passes through untouched.
    """
    sections: list[FlowSection] = []
    for section in definition.sections:
        if section.id == _FAMILIA_SECTION_ID and SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID not in section.exit_validator_ids:
            sections.append(
                section.model_copy(
                    update={
                        "exit_validator_ids": (
                            *section.exit_validator_ids,
                            SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID,
                        ),
                    },
                ),
            )
        else:
            sections.append(section)
    return definition.model_copy(update={"sections": tuple(sections)})


__all__ = [
    "SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID",
    "attach_setup_legal_validators",
    "validate_unidad_familiar_conjunta",
]
