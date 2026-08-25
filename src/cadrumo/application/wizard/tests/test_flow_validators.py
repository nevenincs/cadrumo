"""Receipt tests for the taxpayer-projection flow-scope validator.

The validator re-runs the real :func:`projection_for_taxpayer` constructor
over a staged answer set and maps each construction-time cross-field
failure to a typed verdict — no mocks, the real deadline-domain model
validators fire. Each named legal check drives an invalid staged answer
set and asserts its typed verdict row appears, keyed by the stable
``check`` context token. Assertions read verdict structure and catalogue
keys only, never the localized prose or the raw model message.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core.flows import (
    REPEATING_INSTANCE_SEPARATOR,
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ...flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from ...flows.validators import CrossFieldValidator, ValidationVerdict, resolve_cross_field_validator
from .. import (
    TAXPAYER_PROJECTION_VALIDATOR_ID,
    build_taxpayer_projection_validator,
    register_taxpayer_projection_validator,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FALLBACK_MESSAGE_KEY = "errors.refused.refused_user_profile_validation"

# Each named legal check now carries its own localized verifier verdict key.
_VERIFIER_KEYS: dict[str, str] = {
    "impatriado_requires_start_date": "wizard.setup.verifier.impatriado_requires_start_date",
    "non_resident_requires_country": "wizard.setup.verifier.non_resident_requires_country",
    "non_resident_requires_representante": "wizard.setup.verifier.non_resident_requires_representante",
}

# page-id -> schema-path (domain_key), mirroring the persistence layer's
# question-id -> profile_key serialisation for the identity/residence pages
# these three legal checks constrain.
_PAGE_DOMAIN_KEYS: dict[str, str] = {
    "irpf-special-regime": "irpf.special_regime",
    "irpf-special-regime-start-date": "irpf.special_regime_start_date",
    "fiscal-residency": "taxpayer_type.fiscal_residency",
    "country-of-fiscal-residence": "taxpayer_type.country_of_fiscal_residence",
    "representante-fiscal-nif": "taxpayer_type.representante_fiscal_nif",
    "representante-fiscal-nombre": "taxpayer_type.representante_fiscal_nombre",
}


@pytest.fixture(scope="module")
def validator() -> CrossFieldValidator:
    return build_taxpayer_projection_validator(_PAGE_DOMAIN_KEYS)


def _checks(verdicts: tuple[ValidationVerdict, ...]) -> set[str]:
    return {str(verdict.context["check"]) for verdict in verdicts if not verdict.ok}


def test_impatriado_without_start_date_yields_verdict(validator: CrossFieldValidator) -> None:
    """An IMPATRIADO election with no start date surfaces its typed verdict row."""
    verdicts = validator({"irpf-special-regime": "impatriado"})
    assert "impatriado_requires_start_date" in _checks(verdicts)
    row = next(v for v in verdicts if not v.ok and v.context["check"] == "impatriado_requires_start_date")
    assert row.message_key == _VERIFIER_KEYS["impatriado_requires_start_date"]
    fields = row.context["fields"]
    assert isinstance(fields, list)
    assert "special_regime_start_date" in fields


def test_non_resident_without_country_yields_verdict(validator: CrossFieldValidator) -> None:
    """A NON_RESIDENT_IRNR residency with no country surfaces its typed verdict row."""
    verdicts = validator({"fiscal-residency": "non_resident_irnr"})
    assert "non_resident_requires_country" in _checks(verdicts)
    row = next(v for v in verdicts if not v.ok and v.context["check"] == "non_resident_requires_country")
    assert row.message_key == _VERIFIER_KEYS["non_resident_requires_country"]


def test_non_resident_without_representante_yields_verdict(validator: CrossFieldValidator) -> None:
    """A non-EU/EEA non-resident with no fiscal representative surfaces its verdict row."""
    verdicts = validator(
        {
            "fiscal-residency": "non_resident_irnr",
            "country-of-fiscal-residence": "US",
        },
    )
    checks = _checks(verdicts)
    assert "non_resident_requires_representante" in checks
    row = next(v for v in verdicts if not v.ok and v.context["check"] == "non_resident_requires_representante")
    assert row.message_key == _VERIFIER_KEYS["non_resident_requires_representante"]
    fields = row.context["fields"]
    assert isinstance(fields, list)
    assert "representante_fiscal_nif" in fields


def test_valid_answer_set_passes(validator: CrossFieldValidator) -> None:
    """A fully-specified EU non-resident constructs cleanly — one passing verdict."""
    verdicts = validator(
        {
            "fiscal-residency": "non_resident_irnr",
            "country-of-fiscal-residence": "FR",
        },
    )
    assert all(verdict.ok for verdict in verdicts)


def test_verdict_context_never_carries_raw_model_message(validator: CrossFieldValidator) -> None:
    """The redacted verdict context exposes only the check token and field names."""
    verdicts = validator({"irpf-special-regime": "impatriado"})
    row = next(v for v in verdicts if not v.ok)
    assert set(row.context) <= {"check", "fields"}


def test_instance_scoped_answers_are_excluded(validator: CrossFieldValidator) -> None:
    """Repeating-group instance keys never enter the top-level taxpayer projection."""
    instance_key = f"descendientes{REPEATING_INSTANCE_SEPARATOR}0.nif"
    verdicts = validator({instance_key: "12345678Z"})
    assert all(verdict.ok for verdict in verdicts)


def test_registration_wires_the_validator_by_id() -> None:
    """Registering from a definition makes the validator resolvable under its id."""
    register_taxpayer_projection_validator(_definition())
    resolved = resolve_cross_field_validator(TAXPAYER_PROJECTION_VALIDATOR_ID)
    verdicts = resolved({"irpf-special-regime": "impatriado"})
    assert any(
        not verdict.ok and verdict.context.get("check") == "impatriado_requires_start_date" for verdict in verdicts
    )


def _definition() -> FlowDefinition:
    class _Answers(BaseModel):
        pass

    title = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")
    pages = tuple(
        FlowPage(
            id=page_id,
            widget=FlowWidgetKind.TEXT,
            prompt=title,
            answer_type=str,
            domain_key=domain_key,
            required=False,
        )
        for page_id, domain_key in _PAGE_DOMAIN_KEYS.items()
    )
    return FlowDefinition(
        id="taxpayer-projection-test",
        title=title,
        description=title,
        sections=(FlowSection(id="s", title=title, items=pages),),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
