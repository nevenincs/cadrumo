"""Grounded tests for the Art. 82 LIRPF unidad-familiar flow validator.

The setup flow re-homes the Art. 82.1.2ª joint-taxation legal check as a
``familia`` section-exit cross-field validator. Every expected outcome here is
derived from the legal rule (Art. 82.1 LIRPF), never from the validator's own
output:

- Art. 82.1.1ª: a married couple not legally separated may opt for conjunta as
  a couple; children are optional.
- Art. 82.1.2ª: in legal-separation or no-marriage-bond cases the only conjunta
  path is the monoparental unit, which requires qualifying children. The
  no-marriage-bond trigger is registration-agnostic, so a de-facto couple
  (registered or not) is a monoparental-only situation exactly like soltero /
  separado-divorciado.

The tests exercise the domain modality helper, the registered validator closure
in isolation, the decorator that wires it onto the real projected setup
definition, and the live engine section-exit boundary (block then clear) — no
mocks; the real registry and engine fire.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core.renta_declaracion_type import RentaDeclaracionType
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....domain.contribuyente.renta_codes import SituacionFamiliar
from ...flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from ...flows.engine import SECTION_VERDICT_PREFIX, answer, next_page, start_flow
from ...flows.validators import ValidationVerdict, resolve_cross_field_validator
from ...flows.wizard_projection import flow_definition_from_wizard_flow
from ..catalogue import SETUP_FLOW
from ..commands import _SETUP_CHECKPOINT
from ..setup_legal_validators import (
    SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID,
    attach_setup_legal_validators,
    validate_unidad_familiar_conjunta,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_JOINT = RentaDeclaracionType.JOINT.value
_INDIVIDUAL = RentaDeclaracionType.INDIVIDUAL.value

_FAMILIA_SECTION_ID = "familia"
_TAXATION_TYPE_PAGE = "taxation-type"
_SITUACION_FAMILIAR_PAGE = "situacion-familiar"
_MINOR_CHILDREN_PAGE = "family-minor-children-in-unit"
_MONOPARENTAL_KEY = "wizard.setup.verifier.monoparental_requires_hijos_warning"


# ---------------------------------------------------------------------------
# Domain modality helper — grounded in Art. 82.1
# ---------------------------------------------------------------------------


def test_monoparental_required_is_registration_agnostic() -> None:
    """Art. 82.1.2ª keys the monoparental modality on the absence of a marriage
    bond, so every non-married situation — including a de-facto couple whether
    or not it is registered — is monoparental-only; only CASADO opts as a
    couple (Art. 82.1.1ª)."""
    assert SituacionFamiliar.CASADO.monoparental_required() is False
    for situacion in (
        SituacionFamiliar.SOLTERO,
        SituacionFamiliar.SEPARADO_DIVORCIADO,
        SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
        SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
    ):
        assert situacion.monoparental_required() is True, situacion


# ---------------------------------------------------------------------------
# Registered validator closure — grounded scenarios
# ---------------------------------------------------------------------------


def _verdicts(taxation: str, situacion: str, minor_children: str) -> tuple[ValidationVerdict, ...]:
    return validate_unidad_familiar_conjunta(
        {
            _TAXATION_TYPE_PAGE: taxation,
            _SITUACION_FAMILIAR_PAGE: situacion,
            _MINOR_CHILDREN_PAGE: minor_children,
        },
    )


def _has_failure(verdicts: tuple[ValidationVerdict, ...]) -> bool:
    return any(not verdict.ok for verdict in verdicts)


def test_joint_non_married_without_children_fails() -> None:
    """Art. 82.1.2ª: a joint declaration for a non-married situation with no
    minor children cannot form a unidad familiar — every such situation fails."""
    for situacion in (
        SituacionFamiliar.SOLTERO,
        SituacionFamiliar.SEPARADO_DIVORCIADO,
        SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
        SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
    ):
        verdicts = _verdicts(_JOINT, situacion.value, "false")
        assert _has_failure(verdicts), situacion
        failure = next(v for v in verdicts if not v.ok)
        assert failure.message_key == _MONOPARENTAL_KEY
        assert failure.context["check"] == "monoparental_requires_hijos"
        fields = failure.context["fields"]
        assert isinstance(fields, list)
        assert "situacion_familiar" in fields


def test_joint_non_married_with_children_passes() -> None:
    """Art. 82.1.2ª is satisfied when the monoparental unit has qualifying
    children."""
    for situacion in (SituacionFamiliar.SOLTERO, SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA):
        verdicts = _verdicts(_JOINT, situacion.value, "true")
        assert not _has_failure(verdicts), situacion


def test_married_joint_passes_without_children() -> None:
    """Art. 82.1.1ª: a married couple opts for conjunta as a couple; children
    are optional, so a childless married joint declaration must not fail."""
    verdicts = _verdicts(_JOINT, SituacionFamiliar.CASADO.value, "false")
    assert not _has_failure(verdicts)


def test_individual_taxation_never_fails() -> None:
    """The rule scopes to joint declarations; an individual declaration with a
    childless non-married situation is out of scope and passes."""
    verdicts = _verdicts(_INDIVIDUAL, SituacionFamiliar.SOLTERO.value, "false")
    assert not _has_failure(verdicts)


def test_blank_situacion_passes() -> None:
    """An undeclared family situation cannot be assessed against Art. 82 and is
    not refused at the boundary."""
    assert not _has_failure(_verdicts(_JOINT, "", "false"))


def test_antitautology_children_flag_flips_the_verdict() -> None:
    """A tautological check would return the same outcome regardless of the
    children fact; the monoparental rule must diverge on it."""
    without = _verdicts(_JOINT, SituacionFamiliar.SOLTERO.value, "false")
    with_children = _verdicts(_JOINT, SituacionFamiliar.SOLTERO.value, "true")
    assert _has_failure(without) and not _has_failure(with_children)


def test_verdict_context_carries_only_check_and_fields() -> None:
    """The redacted verdict never leaks a raw answer — only the stable check
    token and code-identifier field names."""
    failure = next(v for v in _verdicts(_JOINT, SituacionFamiliar.SOLTERO.value, "false") if not v.ok)
    assert set(failure.context) <= {"check", "fields"}


# ---------------------------------------------------------------------------
# Registration + real projected-definition wiring
# ---------------------------------------------------------------------------


def test_validator_is_registered_under_its_id() -> None:
    resolved = resolve_cross_field_validator(SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID)
    assert _has_failure(resolved({_TAXATION_TYPE_PAGE: _JOINT, _SITUACION_FAMILIAR_PAGE: "soltero"}))


def test_attach_wires_the_validator_onto_the_real_familia_section() -> None:
    """The decorator names the validator only on the real projected setup
    flow's familia section, leaving every other section untouched."""
    definition = attach_setup_legal_validators(
        flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=dict(_SETUP_CHECKPOINT)),
    )
    familia = next(section for section in definition.sections if section.id == _FAMILIA_SECTION_ID)
    assert SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID in familia.exit_validator_ids
    for section in definition.sections:
        if section.id != _FAMILIA_SECTION_ID:
            assert SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID not in section.exit_validator_ids


def test_attach_is_idempotent() -> None:
    once = attach_setup_legal_validators(
        flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=dict(_SETUP_CHECKPOINT)),
    )
    twice = attach_setup_legal_validators(once)
    familia = next(section for section in twice.sections if section.id == _FAMILIA_SECTION_ID)
    assert familia.exit_validator_ids.count(SETUP_UNIDAD_FAMILIAR_VALIDATOR_ID) == 1


# ---------------------------------------------------------------------------
# Live engine section-exit boundary — block then clear
# ---------------------------------------------------------------------------


def _copy(ref: str = "wizard.setup.familia.title") -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _text_page(page_id: str) -> FlowPage:
    return FlowPage(id=page_id, widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str, required=False)


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed by the engine."""


def _drive_definition() -> FlowDefinition:
    familia = FlowSection(
        id=_FAMILIA_SECTION_ID,
        title=_copy(),
        items=(
            _text_page(_TAXATION_TYPE_PAGE),
            _text_page(_SITUACION_FAMILIAR_PAGE),
            _text_page(_MINOR_CHILDREN_PAGE),
        ),
    )
    trailing = FlowSection(id="preferencias", title=_copy(), items=(_text_page("theme"),))
    definition = FlowDefinition(
        id="setup",
        title=_copy(),
        description=_copy(),
        sections=(familia, trailing),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    return attach_setup_legal_validators(definition)


def test_engine_section_exit_blocks_monoparental_without_children_then_clears() -> None:
    """Driving the real engine: leaving familia with a childless non-married
    joint declaration is blocked at the boundary (Art. 82.1.2ª); declaring
    children clears it and the cursor advances into the next section."""
    definition = _drive_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, _TAXATION_TYPE_PAGE, _JOINT)
    state = next_page(definition, state)
    state = answer(definition, state, _SITUACION_FAMILIAR_PAGE, SituacionFamiliar.SOLTERO.value)
    state = next_page(definition, state)
    state = answer(definition, state, _MINOR_CHILDREN_PAGE, "false")

    blocked = next_page(definition, state)
    section_key = f"{SECTION_VERDICT_PREFIX}{_FAMILIA_SECTION_ID}"
    assert blocked.cursor == _MINOR_CHILDREN_PAGE
    assert section_key in blocked.verdicts

    fixed = answer(definition, blocked, _MINOR_CHILDREN_PAGE, "true")
    advanced = next_page(definition, fixed)
    assert advanced.cursor == "theme"
    assert section_key not in advanced.verdicts
